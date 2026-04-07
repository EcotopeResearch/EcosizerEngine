class SimulationRun:
    """
    Holds all per-timestep outputs from a simulation of a DHWSystem in a Building.

    Stores time-series data (energy use, tank volume, DHW demand, capacity) and
    provides methods to assess whether the system successfully met demand and to
    compute summary metrics for visualization and cost/emissions comparisons.
    """

    def __init__(self, duration_min, timestep_min):
        """
        Parameters
        ----------
        duration_min : int
            Total simulation duration in minutes.
        timestep_min : int
            Size of each simulation timestep in minutes (1 for 3-day, 10 for annual).
        """
        self.duration_min = duration_min
        self.timestep_min = timestep_min
        self.num_steps = duration_min // timestep_min

        # Per-timestep arrays (populated during simulation)
        self.dhw_demand_supplyT_gal = []
        self.usable_volume_supplyT_gal = []
        self.heater_output_kbtuh = []
        self.heater_power_in_kw = []
        self.oat_f = []
        self.inlet_water_temp_f = []
        self.outage_minutes = 0

    def record_timestep(
        self,
        dhw_demand_supplyT_gal,
        usable_volume_supplyT_gal,
        heater_output_kbtuh,
        heater_power_in_kw,
        oat_f,
        inlet_water_temp_f,
    ):
        """
        Append one timestep's worth of data to the run record.

        Parameters
        ----------
        dhw_demand_supplyT_gal : float
            Hot water drawn this timestep at supply temperature [gallons].
        usable_volume_supplyT_gal : float
            Gallons at or above supply temperature remaining in tank after draw.
        heater_output_kbtuh : float
        heater_power_in_kw : float
        oat_f : float
        inlet_water_temp_f : float
        """
        pass

    def record_outage(self, duration_min):
        """
        Record a DHW outage (demand could not be met from tank).

        Parameters
        ----------
        duration_min : int
            Duration of this outage event [minutes].
        """
        pass

    def is_successful(self, max_outage_min=0):
        """
        Return True if total outage time is within the acceptable threshold.

        Parameters
        ----------
        max_outage_min : int
            Maximum allowable cumulative outage [minutes]. Default 0 (no outages).

        Returns
        -------
        bool
        """
        pass

    def get_total_energy_kwh(self):
        """
        Return total electrical energy consumed over the simulation [kWh].

        Returns
        -------
        float
        """
        pass

    def get_peak_demand_kw(self):
        """
        Return peak instantaneous power draw observed during the simulation [kW].

        Returns
        -------
        float
        """
        pass

    def get_summary(self):
        """
        Return a dict summarizing key simulation metrics.

        Returns
        -------
        dict
            Keys include 'successful', 'total_energy_kwh', 'peak_demand_kw',
            'total_outage_min', etc.
        """
        pass

    def get_monthly_energy_kwh(self):
        """
        Break down energy consumption by calendar month (annual runs only).

        Returns
        -------
        list[float]
            12-element list of energy [kWh] per month.
        """
        pass
