from __future__ import annotations

from .EnergyTank import EnergyTank, _DEFAULT_STRAT_SLOPE
from ecoengine.constants.constants import _RHO_CP


class SlugOverlayTank(EnergyTank):
    """
    EnergyTank with an active slug overlay for multi-pass RTP simulation.

    During a heating cycle the bottom of the usable zone acts as a
    fully-mixed "slug" of water being reheated by the heat pump.  This
    class overlays that slug on top of the EnergyTank's energy-based
    temperature profile so that:

    * Temperature queries below the slug return ``cold_temp_f``.
    * Temperature queries inside the slug return the uniform slug
      temperature (fully mixed).
    * Temperature queries above the slug use the base EnergyTank profile.
    * Usable-volume queries count the slug toward usable volume whenever
      the slug temperature is at or above ``supply_temp_f``.

    Slug lifecycle
    --------------
    1. ``activate_slug(supply_temp_f, percent_useable)`` — called when the
       heater turns on.  Initialises the slug from the EnergyTank zone
       between the top of the unusable region and the height at which the
       tank reaches ``supply_temp_f``.  That zone's energy is transferred
       out of the EnergyTank into the slug.
    2. ``add_to_slug(draw_gal, inlet_temp_f)`` — called each timestep when
       water is drawn and the slug is active.  Grows the slug by
       ``draw_gal`` via a weighted-average energy balance (capped at the
       usable volume).
    3. ``heat_slug(kbtuh, duration_min)`` — adds heater output to the slug.
    4. ``deactivate_slug()`` — called when the heater turns off.  Transfers
       all slug BTUs back into the EnergyTank and destroys the slug.

    When the slug is inactive all methods and overrides delegate directly
    to the base ``EnergyTank``.
    """

    def __init__(
        self,
        total_volume_gal: float,
        cold_temp_f: float,
        storage_temp_f: float,
        strat_slope: float = _DEFAULT_STRAT_SLOPE,
    ) -> None:
        super().__init__(total_volume_gal, cold_temp_f, storage_temp_f, strat_slope)
        self._slug_active: bool        = False
        self._slug_vol_gal: float      = 0.0
        self._slug_temp_f: float       = cold_temp_f
        self._cold_pct: float          = 0.0
        self._max_usable_vol_gal: float = 0.0

    # ------------------------------------------------------------------
    # Slug lifecycle
    # ------------------------------------------------------------------

    def is_slug_active(self) -> bool:
        """Return ``True`` if a slug overlay is currently active."""
        return self._slug_active

    def activate_slug(self, supply_temp_f: float, percent_useable: float) -> None:
        """
        Initialise the slug from the sub-supply-temperature portion of the
        usable zone and transfer its energy out of the EnergyTank.

        Parameters
        ----------
        supply_temp_f : float
            Hot-water delivery temperature [°F].
        percent_useable : float
            Fraction of total tank volume that is usable (0–1).
        """
        cold_pct     = (1.0 - percent_useable) * 100.0
        shift_pct    = self._shift_pct_from_energy()

        # Height at which the back-calculated profile equals supply_temp_f.
        x_supply_pct = (
            (supply_temp_f - self._cold_temp_f) / self.strat_slope - shift_pct
        )
        x_supply_pct = max(cold_pct, min(100.0, x_supply_pct))

        slug_vol_gal = max(
            0.0,
            (x_supply_pct - cold_pct) / 100.0 * self.total_volume_gal,
        )

        if slug_vol_gal > 0.0:
            slug_temp_f = self._zone_average_temp_f(cold_pct, x_supply_pct)
            self._energy_btu = max(
                0.0,
                self._energy_btu
                - slug_vol_gal * _RHO_CP * max(0.0, slug_temp_f - self._cold_temp_f),
            )
        else:
            slug_temp_f = self._cold_temp_f

        self._slug_active        = True
        self._slug_vol_gal       = slug_vol_gal
        self._slug_temp_f        = slug_temp_f
        self._cold_pct           = cold_pct
        self._max_usable_vol_gal = percent_useable * self.total_volume_gal

    def add_to_slug(self, draw_gal: float, inlet_temp_f: float) -> None:
        """
        Grow the slug by ``draw_gal`` gallons entering at ``inlet_temp_f``.

        Uses a weighted-average energy balance.  The slug cannot exceed
        the usable volume.

        Parameters
        ----------
        draw_gal : float
            Physical gallons drawn into the slug.
        inlet_temp_f : float
            Temperature of the incoming water [°F].
        """
        if not self._slug_active or draw_gal <= 0.0:
            return
        available   = self._max_usable_vol_gal - self._slug_vol_gal
        actual_draw = min(draw_gal, available)
        if actual_draw <= 0.0:
            return
        if self._slug_vol_gal <= 0.0:
            self._slug_temp_f  = inlet_temp_f
            self._slug_vol_gal = actual_draw
        else:
            self._slug_temp_f = (
                self._slug_vol_gal * self._slug_temp_f + actual_draw * inlet_temp_f
            ) / (self._slug_vol_gal + actual_draw)
            self._slug_vol_gal += actual_draw

    def heat_slug(self, kbtuh: float, duration_min: float) -> None:
        """
        Add heater output to the slug.

        Temperature is capped at ``storage_temp_f``.

        Parameters
        ----------
        kbtuh : float
            Heating capacity [kBTU/hr].
        duration_min : float
            Timestep length [minutes].
        """
        if not self._slug_active or self._slug_vol_gal <= 0.0 or kbtuh <= 0.0:
            return
        heat_btu          = kbtuh * 1000.0 * duration_min / 60.0
        self._slug_temp_f += heat_btu / (self._slug_vol_gal * _RHO_CP)
        self._slug_temp_f  = min(self._slug_temp_f, self._storage_temp_f)

    def deactivate_slug(self) -> None:
        """
        Transfer all slug BTUs back into the EnergyTank and destroy the slug.
        """
        if not self._slug_active:
            return
        slug_btu = max(
            0.0,
            self._slug_vol_gal * _RHO_CP * (self._slug_temp_f - self._cold_temp_f),
        )
        self._energy_btu  = min(self._energy_btu + slug_btu, self._max_energy_btu())
        self._slug_active  = False
        self._slug_vol_gal = 0.0
        self._slug_temp_f  = self._cold_temp_f

    # ------------------------------------------------------------------
    # Temperature and volume queries (overridden when slug is active)
    # ------------------------------------------------------------------

    def get_temperature_at_fraction(self, fract: float) -> float:
        """
        Return water temperature at fractional tank height (0=bottom, 1=top).

        When the slug is active the zone from the cold boundary up to the
        slug top returns the uniform slug temperature; below that is
        ``cold_temp_f``; above that uses the base EnergyTank profile.
        """
        if not self._slug_active:
            return super().get_temperature_at_fraction(fract)
        x_pct        = fract * 100.0
        slug_top_pct = self._cold_pct + (
            self._slug_vol_gal / self.total_volume_gal * 100.0
        )
        if x_pct < self._cold_pct:
            return self._cold_temp_f
        if x_pct < slug_top_pct:
            return max(self._cold_temp_f, min(self._storage_temp_f, self._slug_temp_f))
        return super().get_temperature_at_fraction(fract)

    def get_usable_volume_supplyT_gal(self, supply_temp_f: float) -> float:
        """
        Return gallons currently at or above ``supply_temp_f``.

        Combines the hot zone (from the base EnergyTank, which holds only
        the energy above the slug) with the slug volume when the slug
        temperature meets or exceeds ``supply_temp_f``.
        """
        if not self._slug_active:
            return super().get_usable_volume_supplyT_gal(supply_temp_f)
        hot_usable   = super().get_usable_volume_supplyT_gal(supply_temp_f)
        slug_usable  = (
            self._slug_vol_gal if self._slug_temp_f >= supply_temp_f else 0.0
        )
        return hot_usable + slug_usable
