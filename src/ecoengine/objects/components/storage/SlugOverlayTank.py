from __future__ import annotations

from .EnergyTank import EnergyTank, _DEFAULT_STRAT_SLOPE
from ecoengine.constants.constants import _RHO_CP


class SlugOverlayTank(EnergyTank):
    """
    EnergyTank with an active slug overlay for multi-pass RTP simulation.

    Physical geometry
    -----------------
    ``percent_useable`` is the fraction of tank volume above the cold-water inlet
    pipe.  The zone below the inlet (``1 - percent_useable``) can never hold hot
    water and is permanently excluded from slug and usable-volume calculations.
    ``_cold_pct`` and ``_max_usable_vol_gal`` are computed from this value once at
    construction and never change.

    Slug overlay
    ------------
    During a heating cycle the bottom of the usable zone acts as a fully-mixed
    "slug" of water being reheated by the heat pump.  This class overlays that
    slug on top of the EnergyTank's energy-based temperature profile so that:

    * Temperature queries below the slug return ``cold_temp_f``.
    * Temperature queries inside the slug return the uniform slug temperature.
    * Temperature queries above the slug use the base EnergyTank profile.
    * Usable-volume queries count the slug toward usable volume whenever the
      slug temperature is at or above ``supply_temp_f``.

    Slug lifecycle
    --------------
    1. ``activate_slug(supply_temp_f)`` — called when the heater turns on.
       Initialises the slug from the EnergyTank zone between ``_cold_pct`` and
       the height at which the profile equals ``supply_temp_f``.  That zone's
       energy is transferred out of the EnergyTank into the slug.
    2. ``add_to_slug(draw_gal, inlet_temp_f)`` — called each timestep while the
       slug is active.  Grows the slug by ``draw_gal`` via a weighted-average
       energy balance (capped at ``_max_usable_vol_gal``).
    3. ``heat_slug(kbtuh, duration_min)`` — adds heater output to the slug.
    4. ``deactivate_slug()`` — called when the heater turns off.  Transfers all
       slug BTUs back into the EnergyTank and destroys the slug.

    When the slug is inactive all methods delegate directly to the base EnergyTank.
    """

    def __init__(
        self,
        total_volume_gal: float,
        cold_temp_f: float,
        storage_temp_f: float,
        supply_temp_f: float,
        percent_useable: float = 1.0,
        strat_slope: float = _DEFAULT_STRAT_SLOPE,
    ) -> None:
        """
        Parameters
        ----------
        total_volume_gal : float
        cold_temp_f : float
        storage_temp_f : float
        supply_temp_f : float
            Hot-water delivery temperature [°F].  Stored so that ``initialize()``
            can charge the tank to the correct energy level.
        percent_useable : float
            Fraction of total tank volume above the cold-water inlet pipe (0–1).
            Defaults to 1.0 (inlet at the very bottom).  Control sensors must be
            placed above ``(1 - percent_useable) × total_volume_gal`` height.
        strat_slope : float
            EnergyTank stratification slope [°F / %-height].
        """
        super().__init__(total_volume_gal, cold_temp_f, storage_temp_f, strat_slope)
        self._supply_temp_f: float      = supply_temp_f
        self.percent_useable: float     = percent_useable
        # Fixed geometry derived once from percent_useable
        self._cold_pct: float           = (1.0 - percent_useable) * 100.0
        self._max_usable_vol_gal: float = percent_useable * total_volume_gal
        # Slug state (inactive at construction)
        self._slug_active: bool         = False
        self._slug_vol_gal: float       = 0.0
        self._slug_temp_f: float        = cold_temp_f
        self._slug_top_pct: float       = self._cold_pct

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(
        self,
        storage_temp_f: float,
        cold_temp_f: float,
        percent_useable: float,
    ) -> None:
        """
        Set initial energy so that ``percent_useable`` fraction of total tank
        volume is at or above ``supply_temp_f``.

        Overrides EnergyTank.initialize() because that method places the
        thermocline using ``s_init = (percent_useable − 1) × 100``, which with a
        gentle strat_slope (< 1 °F / %-height) leaves zero usable volume at
        supply temperature.  Here we invert the usable-volume formula directly:

            desired x_supply_pct = (1 − percent_useable) × 100
            shift_pct = (supply_temp_f − cold_temp_f) / strat_slope − x_supply_pct
        """
        self._cold_temp_f    = cold_temp_f
        self._storage_temp_f = storage_temp_f
        self._slug_active    = False
        self._slug_vol_gal   = 0.0
        self._slug_temp_f    = cold_temp_f
        self._slug_top_pct   = self._cold_pct

        dT = storage_temp_f - cold_temp_f
        if dT <= 0.0 or self.strat_slope <= 0.0 or percent_useable <= 0.0:
            self._energy_btu = 0.0
            return

        x_supply_pct = (1.0 - percent_useable) * 100.0
        shift_pct    = (self._supply_temp_f - cold_temp_f) / self.strat_slope - x_supply_pct
        self._energy_btu = max(0.0, min(
            self._energy_at_shift_pct(shift_pct),
            self._max_energy_btu(),
        ))

    # ------------------------------------------------------------------
    # Slug lifecycle
    # ------------------------------------------------------------------

    def is_slug_active(self) -> bool:
        """Return ``True`` if a slug overlay is currently active."""
        return self._slug_active

    def activate_slug(self, supply_temp_f: float) -> None:
        """
        Initialise the slug from the sub-supply-temperature portion of the
        usable zone and transfer its energy out of the EnergyTank.

        The slug spans from ``_cold_pct`` up to the height at which the
        back-calculated EnergyTank profile equals ``supply_temp_f``.  The
        energy in that zone is extracted from the EnergyTank so that the slug
        and the EnergyTank never double-count the same BTUs.

        Parameters
        ----------
        supply_temp_f : float
            Hot-water delivery temperature [°F].
        """
        if self._slug_active:
            return
        shift_pct    = self._shift_pct_from_energy()
        x_supply_pct = (supply_temp_f - self._cold_temp_f) / self.strat_slope - shift_pct
        x_supply_pct = max(self._cold_pct, min(100.0, x_supply_pct))
        slug_vol_gal = max(
            0.0,
            (x_supply_pct - self._cold_pct) / 100.0 * self.total_volume_gal,
        )
        if slug_vol_gal > 0.0:
            slug_temp_f  = self._zone_average_temp_f(self._cold_pct, x_supply_pct)
            # slug_btu     = slug_vol_gal * _RHO_CP * max(0.0, slug_temp_f - self._cold_temp_f)
            # self._energy_btu = max(0.0, self._energy_btu - slug_btu)
        else:
            slug_temp_f = self._cold_temp_f

        self._slug_active    = True
        self._slug_vol_gal   = slug_vol_gal
        self._slug_temp_f    = slug_temp_f
        self._slug_top_pct   = (
            self._cold_pct + slug_vol_gal / self.total_volume_gal * 100.0
            if self.total_volume_gal > 0.0 else self._cold_pct
        )
        self._original_slug_vol_gal = self._slug_vol_gal

        # No kbtu left behind - get KBTUs from bottom of the tank and apply them to the slug
        below_slug_temp_f = self._zone_average_temp_f(0.0, self._cold_pct)
        if below_slug_temp_f > self._cold_temp_f:
            cold_vol_gal = self._cold_pct/100.0 * self.total_volume_gal
            below_slug_btu = cold_vol_gal * _RHO_CP * (below_slug_temp_f - self._cold_temp_f)
            self._slug_temp_f += below_slug_btu / (self._slug_vol_gal * _RHO_CP)

    def add_to_slug(self, draw_gal: float, inlet_temp_f: float) -> None:
        """
        Grow the slug by ``draw_gal`` gallons entering at ``inlet_temp_f``.

        Uses a weighted-average energy balance.  The slug cannot exceed
        ``_max_usable_vol_gal`` (the physically usable tank volume).

        Parameters
        ----------
        draw_gal : float
        inlet_temp_f : float
        """
        if not self._slug_active or draw_gal <= 0.0:
            return
        if self._slug_vol_gal <= 0.0:
            self._slug_temp_f  = inlet_temp_f
            self._slug_vol_gal = draw_gal
        else:
            self._slug_temp_f = (
                self._slug_vol_gal * self._slug_temp_f + draw_gal * inlet_temp_f
            ) / (self._slug_vol_gal + draw_gal)
            self._slug_vol_gal += draw_gal
        self._slug_top_pct = (
            self._cold_pct + self._slug_vol_gal / self.total_volume_gal * 100.0
            if self.total_volume_gal > 0.0 else self._cold_pct
        )

    def heat_slug(self, kbtuh: float, duration_min: float) -> None:
        """
        Add heater output to the slug.  Temperature is capped at ``storage_temp_f``.

        Parameters
        ----------
        kbtuh : float
        duration_min : float
        """
        if not self._slug_active or self._slug_vol_gal <= 0.0 or kbtuh <= 0.0:
            return
        heat_btu          = kbtuh * 1000.0 * duration_min / 60.0
        self._slug_temp_f += heat_btu / (self._slug_vol_gal * _RHO_CP)
        self._slug_temp_f  = min(self._slug_temp_f, self._storage_temp_f)

    @property
    def slug_temp_f(self) -> float:
        """Current slug temperature [°F].  Meaningful only when slug is active."""
        return self._slug_temp_f

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

        # Energy in the below-inlet zone (0% → _cold_pct%) is never touched by
        # slug operations but must be preserved when _energy_btu is reassigned.
        # Computed now while _energy_btu still reflects the full pre-deactivation
        # profile, then added to both assignment branches below.
        below_inlet_btu = 0.0
        if self._cold_pct > 0.0:
            below_inlet_gal = self._cold_pct / 100.0 * self.total_volume_gal
            below_avg_temp  = self._zone_average_temp_f(0.0, self._cold_pct)
            below_inlet_btu = max(
                0.0,
                below_inlet_gal * _RHO_CP * (below_avg_temp - self._cold_temp_f),
            )

        if self._slug_top_pct >= 100.0:
            self._energy_btu = slug_btu #+ below_inlet_btu
        else:
            total_slug_growth_gal = self._slug_vol_gal - self._original_slug_vol_gal
            above_slug_gal = max(0.0, self._max_usable_vol_gal - self._slug_vol_gal)
            above_slug_pct = 100.0 - self._slug_top_pct
            slug_growth_vol_pct = (total_slug_growth_gal / self.total_volume_gal) * 100.0
            top_of_tank_pct = 100.0 - slug_growth_vol_pct
            above_slug_temp_f = self._zone_average_temp_f(top_of_tank_pct - above_slug_pct, top_of_tank_pct)
            above_slug_btu = max(
                0.0,
                above_slug_gal * _RHO_CP * (above_slug_temp_f - self._cold_temp_f),
            )
            self._energy_btu = above_slug_btu + slug_btu # + below_inlet_btu
        self._slug_active  = False
        self._slug_vol_gal = 0.0
        self._original_slug_vol_gal = 0.0
        self._slug_temp_f  = self._cold_temp_f
        self._slug_top_pct = self._cold_pct

    # ------------------------------------------------------------------
    # Temperature and volume queries (overridden when slug is active)
    # ------------------------------------------------------------------

    def get_average_draw_temp_f(self, draw_gal: float) -> float:
        """
        Return the volume-weighted average temperature of the top ``draw_gal``
        physical gallons.

        Analytically integrates the back-calculated stratified profile over
        the draw zone (top of tank downward).
        """
        if not self._slug_active:
            return super().get_average_draw_temp_f(draw_gal)
        draw_gal_pct = draw_gal/self.total_volume_gal * 100.0
        if 100.0 - draw_gal_pct >= self._slug_top_pct:
            # All draw above slug
            return super().get_average_draw_temp_f(draw_gal)
        non_slug_draw_pct = 100.0 - self._slug_top_pct
        slug_draw_pct = draw_gal_pct - non_slug_draw_pct
        return ((super().get_average_draw_temp_f(self.total_volume_gal * (non_slug_draw_pct/100.0)) * non_slug_draw_pct) + (self._slug_temp_f * slug_draw_pct)) / draw_gal_pct
    
    def get_temperature_at_fraction(self, fract: float) -> float:
        """
        Return water temperature at fractional tank height (0=bottom, 1=top).

        When the slug is active:
        * below the slug (``< _cold_pct``) → ``cold_temp_f``
        * inside the slug → uniform ``slug_temp_f``
        * above the slug → base EnergyTank profile
        """
        if not self._slug_active:
            return super().get_temperature_at_fraction(fract)
        x_pct = fract * 100.0
        if x_pct < self._cold_pct:
            return self._cold_temp_f
        if x_pct <= self._slug_top_pct:
            return max(self._cold_temp_f, min(self._storage_temp_f, self._slug_temp_f))
        total_slug_growth_gal = self._slug_vol_gal - self._original_slug_vol_gal
        fract_minus_slug_vol = fract - (total_slug_growth_gal/self.total_volume_gal)
        return super().get_temperature_at_fraction(fract_minus_slug_vol)

    def get_usable_volume_supplyT_gal(self, supply_temp_f: float) -> float:
        """
        Return gallons currently at or above ``supply_temp_f``.

        Combines the EnergyTank hot zone (above the slug) with the slug volume
        when the slug temperature meets or exceeds ``supply_temp_f``.
        """
        if not self._slug_active:
            return super().get_usable_volume_supplyT_gal(supply_temp_f)
        # hot_usable  = super().get_usable_volume_supplyT_gal(supply_temp_f)
        hot_usable = self._max_usable_vol_gal - self._slug_vol_gal # should all be aupply or above
        slug_usable = self._slug_vol_gal if self._slug_temp_f >= supply_temp_f else 0.0
        return hot_usable + slug_usable
    
    def draw_physical_gal(
        self,
        gal: float,
        inlet_temp_f: float,
        supply_temp_f: float | None = None,
        update_internal_cold_temp: bool = True,
    ) -> None:
        """
        Remove ``gal`` physical gallons from the top of the tank and replace
        with make-up water at the bottom.

        The energy removed equals ``gal × _RHO_CP × (avg_top_temp − inlet_temp_f)``
        where ``avg_top_temp`` is from ``get_average_draw_temp_f(gal)``.

        Parameters
        ----------
        gal : float
        inlet_temp_f : float
            Temperature of make-up water entering the bottom.
        supply_temp_f : float | None
            Unused; kept for interface compatibility.
        update_internal_cold_temp : bool
            When ``True`` (default) ``_cold_temp_f`` is updated to
            ``inlet_temp_f``.  Pass ``False`` when the inlet is a warm
            mixing-valve return (to avoid corrupting the cold baseline).
        """
        if not self._slug_active:
            return super().draw_physical_gal(gal, inlet_temp_f, supply_temp_f, update_internal_cold_temp)
        
        # available_gal   = self._max_usable_vol_gal - self._slug_vol_gal
        available_gal = max(0.0, self._max_usable_vol_gal - self._slug_vol_gal)
        if available_gal < gal:
            remove_from_slug_gal = gal - available_gal # draw gallons from slug
            self._slug_vol_gal = self._slug_vol_gal - remove_from_slug_gal
        self.add_to_slug(gal, inlet_temp_f)