from __future__ import annotations

from .StorageTank import StorageTank, _RHO_CP


class MixedStorageTank(StorageTank):
    """
    Fully-mixed (uniform temperature) storage tank model.

    Unlike the stratified StratifiedTank, the entire volume is assumed to be
    at a single uniform temperature at all times.  This matches the behaviour
    of a temperature-maintenance (TM) tank in a parallel-loop system, where
    the tank is small and continuously stirred by the recirc loop.

    Interface contract
    ------------------
    * ``get_temperature_at_fraction()`` returns the same value for any height.
    * ``get_usable_volume_supplyT_gal()`` returns the full tank volume when
      the temperature is at or above supply, otherwise 0.
    * ``heat()`` raises the tank temperature proportionally to heat added.
    * ``draw()`` cools the tank proportionally to cold make-up water added.
    * ``add_recirc_return()`` applies a net temperature drop equal to the
      recirc heat loss for the timestep.
    """

    def __init__(self, total_volume_gal: float) -> None:
        """
        Parameters
        ----------
        total_volume_gal : float
            Total physical tank volume [gallons].
        """
        self.total_volume_gal = total_volume_gal
        self._temperature_f: float = 0.0   # set by initialize()

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
        Set the uniform tank temperature before a simulation begins.

        For a fully-mixed tank, ``percent_useable`` does not have a spatial
        meaning; the tank is simply initialized at ``storage_temp_f``.

        Parameters
        ----------
        storage_temp_f : float
            Initial tank temperature [°F].
        cold_temp_f : float
            Cold water temperature — stored for energy-balance calculations.
        percent_useable : float
            Ignored for the mixed model (all volume is always at one temp).
        """
        self._temperature_f = storage_temp_f
        self._cold_temp_f   = cold_temp_f

    # ------------------------------------------------------------------
    # Temperature queries
    # ------------------------------------------------------------------

    def get_temperature_at_fraction(self, fract: float) -> float:
        """Return the uniform tank temperature (identical at all heights)."""
        return self._temperature_f

    def get_usable_volume_supplyT_gal(self, supply_temp_f: float) -> float:
        """Return full tank volume if at or above supply temperature, else 0."""
        return self.total_volume_gal if self._temperature_f >= supply_temp_f else 0.0

    # ------------------------------------------------------------------
    # Simulation operations
    # ------------------------------------------------------------------

    def draw(
        self,
        volume_supplyT_gal: float,
        cold_temp_f: float,
        supply_temp_f: float,
        outlet_temp_f: float,
    ) -> None:
        """
        Remove DHW demand from the tank and replace with cold make-up water.

        Uses a simple energy-balance mix: physically removes hot water at the
        current tank temperature and replaces it with cold water, cooling the
        tank uniformly.

        The physical volume removed is adjusted for the temperature difference
        between storage and supply (the same conversion used by StratifiedTank).

        Parameters
        ----------
        volume_supplyT_gal : float
            DHW demand in supply-temperature gallons [gal].
        cold_temp_f : float
            Incoming cold water temperature [°F].
        supply_temp_f : float
            System supply (delivery) temperature [°F].
        outlet_temp_f : float
            Current hot water delivery temperature — used for physical-volume
            conversion (same formula as StratifiedTank).
        """
        self._cold_temp_f = cold_temp_f
        if self._temperature_f <= cold_temp_f or volume_supplyT_gal <= 0.0:
            return
        # Physical gallons removed from tank
        physical_vol_gal = (
            volume_supplyT_gal
            * (supply_temp_f - cold_temp_f)
            / max(self._temperature_f - cold_temp_f, 1e-6)
        )
        # Energy balance: mix physical_vol of cold water into the remaining hot tank
        remaining_gal = self.total_volume_gal - physical_vol_gal
        if remaining_gal <= 0.0:
            self._temperature_f = cold_temp_f
            return
        total_energy_btu = remaining_gal * _RHO_CP * self._temperature_f + physical_vol_gal * _RHO_CP * cold_temp_f
        self._temperature_f = total_energy_btu / (self.total_volume_gal * _RHO_CP)

    def heat(
        self,
        kbtuh: float,
        duration_min: float,
        outlet_temp_f: float,
    ) -> None:
        """
        Apply heat from active water heaters for one timestep.

        Raises the uniform tank temperature proportionally to heat added,
        capped at ``outlet_temp_f``.

        Parameters
        ----------
        kbtuh : float
            Total heating rate from all active heaters [kBTU/hr].
        duration_min : float
            Length of the timestep [minutes].
        outlet_temp_f : float
            Maximum temperature the heater can deliver [°F].
        """
        if kbtuh <= 0.0:
            return
        heat_kbtu = kbtuh * duration_min / 60.0   # kBTU
        delta_t   = heat_kbtu * 1000.0 / (self.total_volume_gal * _RHO_CP)
        self._temperature_f = self._temperature_f + delta_t
        # self._temperature_f = min(self._temperature_f + delta_t, outlet_temp_f)

    def add_recirc_return(
        self,
        flow_gpm: float,
        return_temp_f: float,
        duration_min: float,
    ) -> None:
        """
        Apply the net temperature drop from recirc loop losses.

        The recirc loop continuously draws hot water from the tank at the
        current temperature and returns it cooled to ``return_temp_f``. For a
        fully-mixed tank, the net effect is a uniform temperature drop computed
        from the energy removed:

            ΔT = flow_gpm × duration_min × (return_temp_f − tank_temp) / total_volume_gal

        (ΔT is negative when return_temp_f < tank_temp, i.e., heat is lost.)

        Parameters
        ----------
        flow_gpm : float
            Recirculation loop flow rate [GPM].
        return_temp_f : float
            Temperature of water returning from the recirc loop [°F].
        duration_min : float
            Length of the timestep [minutes].
        """
        vol_circulated_gal = flow_gpm * duration_min
        delta_t = (
            vol_circulated_gal
            * (return_temp_f - self._temperature_f)
            / self.total_volume_gal
        )
        self._temperature_f += delta_t  # always negative when return < tank temp

    def apply_fixed_heat_loss_kbtuh(self, kbtuh: float, duration_min: float) -> None:
        """
        Apply a fixed heat loss rate to the tank regardless of current temperature.

        Used by the swing tank simulation to apply recirculation heat loss at the
        same constant rate used during sizing (``RecircSystem.get_recirc_loss_kbtuh``),
        so that sizing and runtime physics remain consistent.

        Parameters
        ----------
        kbtuh : float
            Heat loss rate [kBTU/hr].
        duration_min : float
            Timestep duration [minutes].
        """
        if kbtuh <= 0.0 or duration_min <= 0.0:
            return
        heat_kbtu = kbtuh * duration_min / 60.0
        delta_t   = heat_kbtu * 1000.0 / (self.total_volume_gal * _RHO_CP)
        self._temperature_f -= delta_t

    def mix_primary_inflow(self, gal: float, primary_temp_f: float) -> None:
        """
        Model primary hot water flowing into the swing tank while the same volume
        exits to the building.

        The total tank volume is unchanged; the incoming primary water at
        ``primary_temp_f`` displaces an equal volume of the existing tank contents,
        raising or lowering the uniform temperature via an energy balance:

            T_new = (gal × primary_temp + (V - gal) × T_curr) / V

        Parameters
        ----------
        gal : float
            Volume of primary hot water flowing into the tank this timestep [gal].
        primary_temp_f : float
            Temperature of water entering from the primary storage [°F].
        """
        if gal <= 0.0:
            return
        vol_remaining = self.total_volume_gal - gal
        if vol_remaining <= 0.0:
            self._temperature_f = primary_temp_f
            return
        total_energy = (
            gal * _RHO_CP * primary_temp_f
            + vol_remaining * _RHO_CP * self._temperature_f
        )
        self._temperature_f = total_energy / (self.total_volume_gal * _RHO_CP)

    def get_average_draw_temp_f(self, draw_gal: float) -> float:
        """Return the uniform tank temperature (fully mixed — no stratification)."""
        return self._temperature_f

    def draw_physical_gal(self, gal: float, inlet_temp_f: float) -> None:
        """
        Remove ``gal`` physical gallons and replace with cold make-up water.

        For a fully-mixed tank this is an energy-balance mix: the removed hot
        water is replaced by ``gal`` gallons of cold water at ``inlet_temp_f``.
        """
        if gal <= 0.0:
            return
        remaining_gal = self.total_volume_gal - gal
        if remaining_gal <= 0.0:
            self._temperature_f = inlet_temp_f
            return
        total_energy = (
            remaining_gal * _RHO_CP * self._temperature_f
            + gal * _RHO_CP * inlet_temp_f
        )
        self._temperature_f = total_energy / (self.total_volume_gal * _RHO_CP)
