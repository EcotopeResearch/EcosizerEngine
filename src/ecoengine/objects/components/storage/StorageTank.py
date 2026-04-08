from __future__ import annotations

# Default stratification slope [°F per percentage-point of tank height].
# Calibrated empirically for a standard 12-node tank model.
_DEFAULT_STRAT_SLOPE: float = 2.8


class StorageTank:
    """
    Stratified storage tank model. Tracks temperature stratification (temperature
    at each height layer) and the volume of water at or above supply temperature.

    The strat_slope parameter controls how steeply the temperature gradient
    rises through the transition zone between cold and hot layers. DHWSystem
    subclasses that model different tank geometries or mixing assumptions
    should override this value when constructing the tank.
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
            Number of vertical temperature nodes used to model stratification.
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
        self._node_temps: list[float] = []  # temperature [°F] at each node, bottom to top

    def initialize(
        self,
        storage_temp_f: float,
        cold_temp_f: float,
        percent_useable: float,
    ) -> None:
        """
        Set initial temperature stratification profile.

        Parameters
        ----------
        storage_temp_f : float
            Hot storage setpoint temperature [°F].
        cold_temp_f : float
            Cold/incoming water temperature [°F].
        percent_useable : float
            Fraction of tank volume that starts hot (0-1).
        """
        pass

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
            Temperature [°F].
        """
        pass

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
        pass

    def draw(self, volume_supplyT_gal: float, cold_temp_f: float) -> None:
        """
        Remove hot water from the top of the tank and replace with cold at the bottom.

        Parameters
        ----------
        volume_supplyT_gal : float
            Volume of supply-temperature water drawn [gallons].
        cold_temp_f : float
            Temperature of incoming cold water [°F].
        """
        pass

    def heat(self, kbtuh: float, duration_min: float, supply_temp_f: float) -> None:
        """
        Apply heat from active water heaters to the tank for one timestep.

        Parameters
        ----------
        kbtuh : float
            Total heating rate from all active heaters [kBTU/hr].
        duration_min : float
            Length of the timestep [minutes].
        supply_temp_f : float
            System supply temperature; caps heating at storage setpoint [°F].
        """
        pass

    def add_recirc_return(
        self,
        flow_gpm: float,
        return_temp_f: float,
        duration_min: float,
    ) -> None:
        """
        Mix recirculation loop return flow into the bottom of the tank.

        Parameters
        ----------
        flow_gpm : float
            Recirculation loop flow rate [GPM].
        return_temp_f : float
            Temperature of returning water [°F].
        duration_min : float
            Length of the timestep [minutes].
        """
        pass

    def get_stratification_factor(
        self,
        on_fract: float,
        supply_temp_f: float,
        storage_temp_f: float,
    ) -> float:
        """
        Calculate the stratification factor: ratio of actual usable volume to
        perfectly-stratified usable volume, given the ON aquastat position.

        Parameters
        ----------
        on_fract : float
        supply_temp_f : float
        storage_temp_f : float

        Returns
        -------
        float
        """
        pass
