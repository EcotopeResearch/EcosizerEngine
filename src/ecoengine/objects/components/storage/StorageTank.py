class StorageTank:
    """
    Stratified storage tank model. Tracks temperature stratification (temperature
    at each height layer) and the volume of water at or above supply temperature.
    """

    def __init__(self, total_volume_gal, num_nodes=12):
        """
        Parameters
        ----------
        total_volume_gal : float
            Total physical tank volume [gallons].
        num_nodes : int
            Number of vertical temperature nodes used to model stratification.
        """
        self.total_volume_gal = total_volume_gal
        self.num_nodes = num_nodes
        self._node_temps = []  # temperature [°F] at each node, bottom to top

    def initialize(self, storage_temp_f, cold_temp_f, percent_useable):
        """
        Set initial temperature stratification profile.

        Parameters
        ----------
        storage_temp_f : float
            Hot storage setpoint temperature [°F].
        cold_temp_f : float
            Cold/incoming water temperature [°F].
        percent_useable : float
            Fraction of tank volume that starts hot (0–1).
        """
        pass

    def get_temperature_at_fraction(self, fract):
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

    def get_usable_volume_supplyT_gal(self, supply_temp_f):
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

    def draw(self, volume_supplyT_gal, cold_temp_f):
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

    def heat(self, kbtuh, duration_min, supply_temp_f):
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

    def add_recirc_return(self, flow_gpm, return_temp_f, duration_min):
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

    def get_stratification_factor(self, on_fract, supply_temp_f, storage_temp_f):
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
