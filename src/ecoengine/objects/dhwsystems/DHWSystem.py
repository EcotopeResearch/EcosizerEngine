class DHWSystem:
    """
    Base class for all domestic hot water system configurations.

    Holds one or more WaterHeater objects, a StorageTank, and system-wide
    temperature setpoints. Subclasses implement configuration-specific sizing
    and simulation step logic.
    """

    def __init__(
        self,
        water_heaters,
        storage_tank,
        supply_temp_f,
        storage_temp_f,
    ):
        """
        Parameters
        ----------
        water_heaters : list[WaterHeater]
            One or more heater units in this system.
        storage_tank : StorageTank
            Primary storage tank for this system.
        supply_temp_f : float
            DHW delivery temperature to building occupants [°F].
        storage_temp_f : float
            Hot water storage setpoint temperature [°F].
        """
        self.water_heaters = water_heaters
        self.storage_tank = storage_tank
        self.supply_temp_f = supply_temp_f
        self.storage_temp_f = storage_temp_f

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------

    def size(self, building):
        """
        Compute the minimum heating capacity and storage volume for this system
        in the given building. Populates sizing results on this object.

        Parameters
        ----------
        building : Building
        """
        pass

    def get_minimum_capacity_kbtuh(self):
        """
        Return the minimum required heating capacity [kBTU/hr] after sizing.

        Returns
        -------
        float
        """
        pass

    def get_minimum_storage_storageT_gal(self):
        """
        Return the minimum required storage volume at storage temperature [gallons] after sizing.

        Returns
        -------
        float
        """
        pass

    def get_sizing_curve(self):
        """
        Return the Primary Sizing Curve — pairs of (capacity_kbtuh, storage_storageT_gal)
        representing the capacity-vs-storage tradeoff.

        Returns
        -------
        list[tuple[float, float]]
        """
        pass

    def _calc_required_capacity(self, building):
        """
        Calculate total required heating capacity based on daily DHW load and
        daily run hours.

        Parameters
        ----------
        building : Building

        Returns
        -------
        float
            Required capacity [kBTU/hr].
        """
        pass

    def _calc_running_volume_supplyT_gal(self, building, capacity_kbtuh):
        """
        Determine the running volume (hot water needed in storage when the
        system turns on) as the maximum DHW deficit during peak periods.

        Parameters
        ----------
        building : Building
        capacity_kbtuh : float

        Returns
        -------
        float
            Running volume [gallons at supply temperature].
        """
        pass

    def _calc_storage_volume_storageT_gal(self, running_volume_supplyT_gal, stratification_factor):
        """
        Convert running volume (at supply temperature) to required storage volume
        (at storage temperature) using the stratification factor.

        Parameters
        ----------
        running_volume_supplyT_gal : float
        stratification_factor : float

        Returns
        -------
        float
            Required storage volume [gallons at storage temperature].
        """
        pass

    # ------------------------------------------------------------------
    # Simulation step
    # ------------------------------------------------------------------

    def simulate_step(self, building, timestep_min, mode="normal"):
        """
        Execute one simulation timestep: query controls, apply heating,
        draw DHW from tank. Returns per-step metrics.

        Parameters
        ----------
        building : Building
        timestep_min : int
            Current simulation time [minutes from start].
        mode : str
            Operating mode: 'normal', 'load_up', or 'shed'.

        Returns
        -------
        dict
            Per-timestep metrics (demand, usable volume, heater output, power).
        """
        pass

    def check_for_outage(self, demand_supplyT_gal):
        """
        Return True if the storage tank cannot meet the given demand.

        Parameters
        ----------
        demand_supplyT_gal : float
            Hot water demand at supply temperature [gallons].

        Returns
        -------
        bool
        """
        pass
