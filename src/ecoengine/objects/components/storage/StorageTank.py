from __future__ import annotations

from abc import ABC, abstractmethod

# Default stratification slope [°F per percentage-point of tank height].
# Calibrated empirically for a standard 12-node tank model.
_DEFAULT_STRAT_SLOPE: float = 2.8

# Volumetric heat capacity of water [BTU / (gallon · °F)]
_RHO_CP: float = 8.353535


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class StorageTank(ABC):
    """
    Abstract base class for all storage tank models.

    Defines the interface that WaterHeater, Controls, and DHWSystem rely on.
    Concrete subclasses implement the thermal model (stratified vs. mixed).

    Every subclass must expose ``total_volume_gal`` as a plain attribute and
    implement the five simulation methods listed below.
    """

    total_volume_gal: float

    @abstractmethod
    def initialize(
        self,
        storage_temp_f: float,
        cold_temp_f: float,
        percent_useable: float,
    ) -> None:
        """Set initial tank thermal state before a simulation begins."""

    @abstractmethod
    def get_temperature_at_fraction(self, fract: float) -> float:
        """
        Return water temperature at fractional tank height (0=bottom, 1=top).
        Used by Controls to decide whether to fire the heater.
        """

    @abstractmethod
    def get_usable_volume_supplyT_gal(self, supply_temp_f: float) -> float:
        """Return gallons currently at or above supply temperature."""

    @abstractmethod
    def draw(
        self,
        volume_supplyT_gal: float,
        cold_temp_f: float,
        supply_temp_f: float,
        outlet_temp_f: float,
    ) -> None:
        """Remove DHW demand from the tank and replace with cold make-up water."""

    @abstractmethod
    def heat(
        self,
        kbtuh: float,
        duration_min: float,
        outlet_temp_f: float,
    ) -> None:
        """Apply heat from active water heaters for one timestep."""

    @abstractmethod
    def add_recirc_return(
        self,
        flow_gpm: float,
        return_temp_f: float,
        duration_min: float,
    ) -> None:
        """Mix recirculation loop return flow into the tank."""


# ---------------------------------------------------------------------------
# Stratified tank
# ---------------------------------------------------------------------------

class StratifiedTank(StorageTank):
    """
    Stratified storage tank model using a continuous linear temperature profile.

    Temperature profile
    -------------------
    The tank is hot on top and cold on bottom. Temperature as a function of
    height is described by three regions:

        T(x_pct) = inlet_temp_f                                   x_pct <= x_cold
                 = strat_slope * (x_pct + shift_pct) + strat_inter  x_cold < x_pct < x_hot
                 = outlet_temp_f                                   x_pct >= x_hot

    where x_pct is height as a percentage (0 = bottom, 100 = top) and
    shift_pct = delta_gal / total_volume_gal * 100 translates the gallons-based
    running tally into a percentage shift of the thermocline.

    delta_gal bookkeeping
    ---------------------
    ``_delta_gal`` tracks how much the thermocline has shifted from its
    initialized position, measured in gallons:

    * ``draw()`` decreases ``_delta_gal`` — cold water enters the bottom,
      the thermocline rises (less hot water available).
    * ``heat()`` increases ``_delta_gal`` — cold water is heated and moves to
      the top, the thermocline falls (more hot water available).
    """

    def __init__(
        self,
        total_volume_gal: float,
        num_nodes: int = 12,
        strat_slope: float = _DEFAULT_STRAT_SLOPE,
    ) -> None:
        """
        Parameters
        ----------
        total_volume_gal : float
            Total physical tank volume [gallons].
        num_nodes : int
            Number of vertical temperature nodes (retained for future use;
            the analytical profile model does not use discrete nodes).
        strat_slope : float
            Temperature gradient through the transition zone between cold and
            hot layers [°F per percentage-point of tank height]. Higher values
            mean a sharper thermocline (better stratification). Defaults to
            2.8, calibrated for a standard 12-node tank. DHWSystem subclasses
            that model different schematics may set a different value here.
        """
        self.total_volume_gal = total_volume_gal
        self.num_nodes        = num_nodes
        self.strat_slope      = strat_slope

        # Internal state — set by initialize()
        self._delta_gal:    float = 0.0
        self._strat_inter:  float = 0.0
        self._inlet_temp_f: float = 50.0   # updated each timestep by draw()
        self._outlet_temp_f: float = 140.0  # updated each timestep by heat()

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
        Set initial temperature stratification profile.

        Places the cold boundary (where T = cold_temp_f) at
        ``(1 - percent_useable) * 100`` percent height, so the top
        ``percent_useable`` fraction of the tank starts at storage temperature.

        Parameters
        ----------
        storage_temp_f : float
            Initial hot storage temperature [°F]. Also sets the initial
            outlet temperature cap.
        cold_temp_f : float
            Cold/incoming water temperature [°F].
        percent_useable : float
            Fraction of tank volume that starts hot (0–1).
        """
        self._inlet_temp_f  = cold_temp_f
        self._outlet_temp_f = storage_temp_f
        self._delta_gal     = 0.0

        # Solve for strat_inter so the ramp passes through cold_temp_f at
        # x_cold_pct with delta_gal = 0:
        #   strat_slope * x_cold_pct + strat_inter = cold_temp_f
        x_cold_pct = (1.0 - percent_useable) * 100.0
        self._strat_inter = cold_temp_f - self.strat_slope * x_cold_pct

    # ------------------------------------------------------------------
    # Temperature queries
    # ------------------------------------------------------------------

    def get_temperature_at_fraction(self, fract: float) -> float:
        """
        Return interpolated water temperature at a fractional tank height.

        Parameters
        ----------
        fract : float
            Fractional height from bottom (0) to top (1).

        Returns
        -------
        float
            Temperature [°F], clamped to [inlet_temp_f, outlet_temp_f].
        """
        x_pct     = fract * 100.0
        shift_pct = self._delta_gal / self.total_volume_gal * 100.0
        temp      = self.strat_slope * (x_pct + shift_pct) + self._strat_inter
        return max(self._inlet_temp_f, min(self._outlet_temp_f, temp))

    def get_usable_volume_supplyT_gal(self, supply_temp_f: float) -> float:
        """
        Return gallons of water currently at or above supply temperature.

        Parameters
        ----------
        supply_temp_f : float

        Returns
        -------
        float
        """
        # Solve for x_pct where T = supply_temp_f (lower boundary of usable zone):
        #   strat_slope * (x_pct + shift_pct) + strat_inter = supply_temp_f
        #   x_pct = (supply_temp_f - strat_inter) / strat_slope - shift_pct
        shift_pct     = self._delta_gal / self.total_volume_gal * 100.0
        x_supply_pct  = (supply_temp_f - self._strat_inter) / self.strat_slope - shift_pct
        x_supply_pct  = max(0.0, min(100.0, x_supply_pct))
        usable_fract  = (100.0 - x_supply_pct) / 100.0
        return usable_fract * self.total_volume_gal

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
        Remove hot water from the top of the tank and replace with cold at the
        bottom, representing DHW delivery to building occupants.

        Because storage temperature may exceed supply temperature, the actual
        physical volume removed from the tank is smaller than the supply-temp
        demand — the hot water is mixed with cold at the tap. The conversion is:

            physical_vol = volume_supplyT_gal
                           * (supply_temp_f - cold_temp_f)
                           / (outlet_temp_f - cold_temp_f)

        Decreases ``_delta_gal`` (thermocline rises → less hot water).

        Parameters
        ----------
        volume_supplyT_gal : float
            DHW demand in supply-temperature gallons [gal].
        cold_temp_f : float
            Incoming cold water temperature [°F]. Stored for subsequent
            temperature queries.
        supply_temp_f : float
            System supply (delivery) temperature [°F].
        outlet_temp_f : float
            Current maximum hot water temperature at the tank outlet [°F].
        """
        self._inlet_temp_f = cold_temp_f
        if outlet_temp_f <= cold_temp_f or volume_supplyT_gal <= 0.0:
            return
        physical_vol_gal = (
            volume_supplyT_gal
            * (supply_temp_f - cold_temp_f)
            / (outlet_temp_f - cold_temp_f)
        )
        self._delta_gal -= physical_vol_gal

    def heat(
        self,
        kbtuh: float,
        duration_min: float,
        outlet_temp_f: float,
    ) -> None:
        """
        Apply heat from active water heaters for one timestep.

        Models the HPWH drawing cold water from the bottom of the tank,
        heating it to ``outlet_temp_f``, and returning it to the top.

        Increases ``_delta_gal`` (thermocline falls → more hot water), capped
        when the tank is fully heated.

        Parameters
        ----------
        kbtuh : float
            Total heating rate from all active heaters [kBTU/hr].
        duration_min : float
            Length of the timestep [minutes].
        outlet_temp_f : float
            Maximum temperature the heater delivers to the tank top [°F].
            Sets the hot-zone temperature cap for subsequent temperature queries.
        """
        self._outlet_temp_f = outlet_temp_f
        if kbtuh <= 0.0 or outlet_temp_f <= self._inlet_temp_f:
            return

        heat_kbtu    = kbtuh * duration_min / 60.0           # kBTU
        v_heated_gal = heat_kbtu * 1000.0 / (_RHO_CP * (outlet_temp_f - self._inlet_temp_f))  # gal
        self._delta_gal += v_heated_gal

        # Cap: tank cannot be heated beyond "fully hot" (hot zone fills the
        # entire tank, x=0% is at outlet_temp_f):
        #   strat_slope * (0 + shift_pct_max) + strat_inter = outlet_temp_f
        #   shift_pct_max = (outlet_temp_f - strat_inter) / strat_slope
        shift_pct_max  = (outlet_temp_f - self._strat_inter) / self.strat_slope
        delta_gal_max  = shift_pct_max * self.total_volume_gal / 100.0
        self._delta_gal = min(self._delta_gal, delta_gal_max)

    def add_recirc_return(
        self,
        flow_gpm: float,
        return_temp_f: float,
        duration_min: float,
    ) -> None:
        """
        Mix recirculation loop return flow into the bottom of the tank.

        The recirc loop takes hot water from the tank top at ``outlet_temp_f``,
        circulates it through the building pipes, and returns it cooled to
        ``return_temp_f`` at the tank bottom. The total tank volume is unchanged,
        but the net energy loss reduces the hot zone.

        Net effect on ``_delta_gal``:
            vol * (return_temp_f - outlet_temp_f) / (outlet_temp_f - inlet_temp_f)
        (always negative → thermocline rises → less hot water)

        Parameters
        ----------
        flow_gpm : float
            Recirculation loop flow rate [GPM].
        return_temp_f : float
            Temperature of returning water [°F].
        duration_min : float
            Length of the timestep [minutes].
        """
        if self._outlet_temp_f <= self._inlet_temp_f:
            return
        vol_gal = flow_gpm * duration_min
        net_delta_gal = (
            vol_gal
            * (return_temp_f - self._outlet_temp_f)
            / (self._outlet_temp_f - self._inlet_temp_f)
        )
        self._delta_gal += net_delta_gal  # always negative

    # ------------------------------------------------------------------
    # Sizing support
    # ------------------------------------------------------------------

    def get_stratification_factor(
        self,
        on_fract: float,
        supply_temp_f: float,
        storage_temp_f: float,
    ) -> float:
        """
        Return the stratification factor: the fraction of total tank volume
        that is usable at supply temperature given the ON aquastat position.

        Matches the sizing formula used in DHWSystem:
            strat_factor_pct = (storage_temp_f - supply_temp_f) / strat_slope
            usable_fraction  = strat_factor_pct * (1 - on_fract)

        Parameters
        ----------
        on_fract : float
        supply_temp_f : float
        storage_temp_f : float

        Returns
        -------
        float
        """
        if storage_temp_f <= supply_temp_f:
            return 0.0
        strat_factor_pct = (storage_temp_f - supply_temp_f) / self.strat_slope
        return max(0.0, strat_factor_pct * (1.0 - on_fract))
