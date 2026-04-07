class UtilityCostTracker:
    """
    Stores the utility billing structure for a building's municipality and
    calculates energy costs from simulation output.

    Supports base charges, peak/off-peak demand charges ($/kW), and
    peak/off-peak energy charges ($/kWh) with optional seasonal variation.
    """

    def __init__(
        self,
        base_charge_per_month=0.0,
        peak_demand_per_kw=0.0,
        peak_energy_per_kwh=0.0,
        offpeak_demand_per_kw=0.0,
        offpeak_energy_per_kwh=0.0,
        peak_start_hour=None,
        peak_end_hour=None,
        peak_season_start_month=None,
        peak_season_end_month=None,
    ):
        """
        Parameters
        ----------
        base_charge_per_month : float
            Fixed monthly base charge [$].
        peak_demand_per_kw : float
            Peak demand charge [$/kW].
        peak_energy_per_kwh : float
            Peak energy rate [$/kWh].
        offpeak_demand_per_kw : float
            Off-peak demand charge [$/kW].
        offpeak_energy_per_kwh : float
            Off-peak energy rate [$/kWh].
        peak_start_hour : int, optional
            Hour of day when peak period begins (0–23).
        peak_end_hour : int, optional
            Hour of day when peak period ends (0–23).
        peak_season_start_month : int, optional
            Month when peak season begins (1–12).
        peak_season_end_month : int, optional
            Month when peak season ends (1–12).
        """
        self.base_charge_per_month = base_charge_per_month
        self.peak_demand_per_kw = peak_demand_per_kw
        self.peak_energy_per_kwh = peak_energy_per_kwh
        self.offpeak_demand_per_kw = offpeak_demand_per_kw
        self.offpeak_energy_per_kwh = offpeak_energy_per_kwh
        self.peak_start_hour = peak_start_hour
        self.peak_end_hour = peak_end_hour
        self.peak_season_start_month = peak_season_start_month
        self.peak_season_end_month = peak_season_end_month

    @classmethod
    def from_csv(cls, filepath):
        """
        Load a utility rate structure from a CSV file.

        Parameters
        ----------
        filepath : str

        Returns
        -------
        UtilityCostTracker
        """
        pass

    def is_peak_period(self, timestep_min):
        """
        Return True if the given timestep falls within the peak rate period.

        Parameters
        ----------
        timestep_min : int
            Minutes elapsed from the start of the simulation year.

        Returns
        -------
        bool
        """
        pass

    def calculate_annual_cost(self, simulation_run):
        """
        Compute total annual utility cost from a completed SimulationRun.

        Parameters
        ----------
        simulation_run : SimulationRun

        Returns
        -------
        float
            Total annual cost [$].
        """
        pass

    def calculate_monthly_costs(self, simulation_run):
        """
        Break down utility costs by month and charge type.

        Parameters
        ----------
        simulation_run : SimulationRun

        Returns
        -------
        dict
            Nested dict of {month: {charge_type: cost}}.
        """
        pass
