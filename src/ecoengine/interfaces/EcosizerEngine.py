from .Simulator import simulate_3day, simulate_annual


class EcosizerEngine:
    """
    Primary backend interface for the Ecosizer tool.

    Accepts building and system parameters, orchestrates Building and DHWSystem
    construction, performs sizing, and runs simulations. All validation of input
    ranges is expected to be handled by the frontend before calling this class.
    """

    def __init__(
        self,
        building_type,
        magnitude,
        zip_code_or_climate_zone,
        supply_temp_f,
        storage_temp_f,
        schematic,
        num_heaters=1,
        hpwh_model=None,
        storage_volume_storageT_gal=None,
        percent_useable=0.9,
        aquastat_fract=0.5,
        # Recirculation inputs (optional)
        return_temp_f=None,
        return_flow_gpm=None,
        recirc_loss_watts_per_apt=None,
        # Load shift inputs (optional)
        load_shift_schedule=None,
        load_up_hours=0,
        # Advanced controls (optional)
        on_sensor_fract=None,
        off_sensor_fract=None,
        on_trigger_t_f=None,
        off_trigger_t_f=None,
        # Utility cost inputs (optional)
        utility_cost_tracker=None,
        # CBECC-Res compliance mode
        california_spec_mode=False,
    ):
        """
        Parameters
        ----------
        building_type : str
            Building use type (e.g. 'multi_family', 'office_building').
        magnitude : int or float
            Occupancy metric appropriate for the building type.
        zip_code_or_climate_zone : str or int
            Used to look up ambient climate data.
        supply_temp_f : float
            DHW delivery temperature [°F].
        storage_temp_f : float
            Hot water storage setpoint [°F].
        schematic : str
            Piping configuration identifier (e.g. 'swing_tank', 'parallel_loop',
            'primary_no_recirc', 'sp_rtp', 'mp_rtp', 'instant_wh').
        num_heaters : int
            Number of primary heat pump units.
        hpwh_model : str, optional
            HPWH model name for performance map lookup.
        storage_volume_storageT_gal : float, optional
            Override for primary storage volume at storage temperature [gallons]. If None, minimum is used.
        percent_useable : float
            Fraction of tank volume available as hot water (0–1).
        aquastat_fract : float
            Fractional tank height of the ON aquastat (0–1).
        return_temp_f : float, optional
            Recirc loop return temperature [°F].
        return_flow_gpm : float, optional
            Recirc loop flow rate [GPM].
        recirc_loss_watts_per_apt : float, optional
            Alternative recirc loss input [W per apartment].
        load_shift_schedule : list[int], optional
            24-element list of 0s/1s (0 = shed, 1 = run).
        load_up_hours : float
            Hours spent in load-up mode before first shed.
        on_sensor_fract : float, optional
        off_sensor_fract : float, optional
        on_trigger_t_f : float, optional
        off_trigger_t_f : float, optional
        utility_cost_tracker : UtilityCostTracker, optional
        california_spec_mode : bool
            If True, lock certain variables to CBECC-Res standards.
        """
        self.building_type = building_type
        self.magnitude = magnitude
        self.zip_code_or_climate_zone = zip_code_or_climate_zone
        self.supply_temp_f = supply_temp_f
        self.storage_temp_f = storage_temp_f
        self.schematic = schematic
        self.num_heaters = num_heaters
        self.hpwh_model = hpwh_model
        self.storage_volume_storageT_gal = storage_volume_storageT_gal
        self.percent_useable = percent_useable
        self.aquastat_fract = aquastat_fract
        self.return_temp_f = return_temp_f
        self.return_flow_gpm = return_flow_gpm
        self.recirc_loss_watts_per_apt = recirc_loss_watts_per_apt
        self.load_shift_schedule = load_shift_schedule
        self.load_up_hours = load_up_hours
        self.on_sensor_fract = on_sensor_fract
        self.off_sensor_fract = off_sensor_fract
        self.on_trigger_t_f = on_trigger_t_f
        self.off_trigger_t_f = off_trigger_t_f
        self.utility_cost_tracker = utility_cost_tracker
        self.california_spec_mode = california_spec_mode

        # Populated after build/size
        self._building = None
        self._dhw_system = None

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def build(self):
        """
        Construct the Building and DHWSystem objects from the stored parameters.
        Must be called before size() or any simulate method.
        """
        pass

    def _build_building(self):
        """
        Construct and return the Building object (includes ClimateZone lookup
        and load shape selection).

        Returns
        -------
        Building
        """
        pass

    def _build_dhw_system(self):
        """
        Construct and return the appropriate DHWSystem subclass based on
        self.schematic.

        Returns
        -------
        DHWSystem
        """
        pass

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------

    def size(self):
        """
        Size the DHW system for the building. Calls build() if not already done.

        Returns
        -------
        dict
            Sizing results including minimum capacity, minimum storage, and
            the primary sizing curve.
        """
        pass

    def get_sizing_results(self):
        """
        Return the most recent sizing results as a dict.

        Returns
        -------
        dict
            Keys: 'min_capacity_kbtuh', 'min_storage_storageT_gal', 'sizing_curve'.
        """
        pass

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def simulate_3day(self):
        """
        Run a 3-day design-day simulation. Sizes first if needed.

        Returns
        -------
        SimulationRun
        """
        pass

    def simulate_annual(self):
        """
        Run a full annual simulation. Sizes first if needed.

        Returns
        -------
        SimulationRun
        """
        pass

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def get_simulation_summary(self, simulation_run):
        """
        Return a summary dict from a completed SimulationRun, suitable for
        passing back to the frontend.

        Parameters
        ----------
        simulation_run : SimulationRun

        Returns
        -------
        dict
        """
        pass

    def get_annual_cost_estimate(self, simulation_run):
        """
        Compute annual utility cost from a completed annual SimulationRun using
        the UtilityCostTracker attached to the Building.

        Parameters
        ----------
        simulation_run : SimulationRun

        Returns
        -------
        dict
            Monthly costs grouped by charge type.
        """
        pass
