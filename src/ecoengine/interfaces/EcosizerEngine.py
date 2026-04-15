from __future__ import annotations

import warnings
from .Simulator import simulate_3day as _simulate_3day, simulate_annual as _simulate_annual


# ---------------------------------------------------------------------------
# Schematic → DHWSystem class registry
# ---------------------------------------------------------------------------

_RECIRC_SCHEMATICS = {"parallel_loop", "swing_tank", "single_pass_rtp"}


class EcosizerEngine:
    """
    Primary backend interface for the Ecosizer tool.

    Accepts building and system parameters, builds and sizes the appropriate
    DHWSystem subclass, and runs simulations. All input-range validation is
    expected to be handled by the frontend before calling this class.

    Construction immediately builds and sizes the system — no separate build()
    or size() calls are required::

        engine = EcosizerEngine(
            building_type            = "multi_family",
            magnitude                = 100,
            zip_code_or_climate_zone = {"design_oat_f": 47, "design_inlet_water_temp_f": 47},
            supply_temp_f            = 125.0,
            storage_temp_f           = 150.0,
            schematic                = "primary_no_recirc",
        )
        result = engine.simulate_3day()
        result.to_plotly(filepath="output.html")
    """

    def __init__(
        self,
        building_type: str,
        magnitude: int | float,
        zip_code_or_climate_zone,
        supply_temp_f: float,
        storage_temp_f: float,
        schematic: str,
        # Building inputs
        gpdpp: float | None = None,
        # Primary heater inputs
        num_heaters: int = 1,
        hpwh_model: str | None = None,
        max_daily_run_hr: float = 16.0,
        defrost_factor: float = 1.0,
        # Aquastat / controls
        aquastat_fract: float = 0.5,
        off_sensor_fract: float = 0.1,
        on_trigger_t_f: float | None = None,
        off_trigger_t_f: float | None = None,
        # Load shift (optional)
        load_shift_schedule: list[int] | None = None,
        load_up_hours: int = 0,
        shed_aquastat_fract: float | None = None,
        load_up_aquastat_fract: float | None = None,
        shed_off_sensor_fract: float | None = None,
        load_up_off_sensor_fract: float | None = None,
        load_up_off_trigger_t_f: float | None = None,
        load_shift_percent: float = 0.95,
        # Recirculation (required for recirc schematics)
        return_temp_f: float | None = None,
        return_flow_gpm: float | None = None,
        # ParallelLoop TM controls
        tm_on_temp_f: float | None = None,
        tm_off_temp_f: float | None = None,
        tm_off_time_hr: float = 0.5,
        tm_safety_factor: float = 1.75,
        # Utility cost (optional)
        utility_cost_tracker=None,
        # CBECC-Res compliance mode
        california_spec_mode: bool = False,
    ):
        """
        Parameters
        ----------
        building_type : str
            Building use type (e.g. ``'multi_family'``, ``'office'``).
        magnitude : int or float
            Occupancy metric appropriate to the building type (people, units, etc.).
        zip_code_or_climate_zone : str | int | dict
            Climate lookup key. Accepted forms:

            * 5-digit CA zip code string or int → ``ClimateZone.from_zip_code()``
            * Integer 1–96 → ``ClimateZone.from_zone_id()``
            * Non-numeric string → ``ClimateZone.from_weather_station()``
            * Dict with keys ``'design_oat_f'`` and/or ``'design_inlet_water_temp_f'``
              → ``ClimateZone.from_design_conditions()``

        supply_temp_f : float
            DHW delivery temperature [°F].
        storage_temp_f : float
            Hot water storage setpoint [°F].
        schematic : str
            Piping configuration. Supported values:

            * ``'primary_no_recirc'`` — base DHWSystem (heat pump + stratified tank)
            * ``'parallel_loop'``    — separate TM tank in parallel for recirc losses
            * ``'swing_tank'``       — (not yet implemented)

        gpdpp : float, optional
            Gallons per person per day. If None, building-type defaults are used.
        num_heaters : int
            Number of primary HPWH units. Default 1.
        hpwh_model : str, optional
            HPWH model name for performance map lookup (future use).
        max_daily_run_hr : float
            Maximum hours the primary heating system may run per day. Default 16.
        defrost_factor : float
            Fraction of rated capacity available after defrost cycles (0–1). Default 1.0.
        aquastat_fract : float
            Fractional tank height of the ON aquastat (0–1). Default 0.5.
        off_sensor_fract : float
            Fractional tank height of the OFF aquastat (0–1). Default 0.1.
        on_trigger_t_f : float, optional
            Temperature at which the ON aquastat fires. Defaults to supply_temp_f.
        off_trigger_t_f : float, optional
            Temperature at which the OFF aquastat fires. Defaults to storage_temp_f.
        load_shift_schedule : list[int], optional
            24-element list (0 = shed hour, 1 = run hour). None → no load shifting.
        load_up_hours : int
            Hours spent in load-up mode before the first shed window.
        shed_aquastat_fract : float, optional
            ON aquastat fraction during shed hours (higher → more storage).
        load_up_aquastat_fract : float, optional
            ON aquastat fraction during load-up hours (lower → fires sooner).
        shed_off_sensor_fract : float, optional
            OFF aquastat fraction during shed hours. Defaults to off_sensor_fract.
        load_up_off_sensor_fract : float, optional
            OFF aquastat fraction during load-up hours. Defaults to off_sensor_fract.
        load_up_off_trigger_t_f : float, optional
            OFF trigger temperature during load-up hours. Defaults to off_trigger_t_f.
        load_shift_percent : float
            Percentile of days the load-shift sizing must cover [0.25, 1.0].
            Default 0.95 — size for 95% of days, accepting that the highest-demand
            5% of days may occasionally breach the shed window. Only applied
            during load-shift sizing; normal sizing always uses the full daily demand.
        return_temp_f : float, optional
            Recirc loop return temperature [°F]. Required for recirc schematics.
        return_flow_gpm : float, optional
            Recirc loop flow rate [GPM]. Required for recirc schematics.
        tm_on_temp_f : float, optional
            TM element turn-on temperature [°F]. Defaults to supply_temp_f − 5.
        tm_off_temp_f : float, optional
            TM element turn-off temperature [°F]. Defaults to supply_temp_f.
        tm_off_time_hr : float
            Max TM heater off-cycle duration [hr]. Default 0.5.
        tm_safety_factor : float
            TM capacity safety multiplier (> 1.0). Default 1.2.
        utility_cost_tracker : UtilityCostTracker, optional
            Attached to the building for annual cost estimates.
        california_spec_mode : bool
            If True, apply CBECC-Res sizing standards. Default False.
        """
        self.building_type             = building_type
        self.magnitude                 = magnitude
        self.zip_code_or_climate_zone  = zip_code_or_climate_zone
        self.supply_temp_f             = supply_temp_f
        self.storage_temp_f            = storage_temp_f
        self.schematic                 = schematic
        self.gpdpp                     = gpdpp
        self.num_heaters               = num_heaters
        self.hpwh_model                = hpwh_model
        self.max_daily_run_hr          = max_daily_run_hr
        self.defrost_factor            = defrost_factor
        self.aquastat_fract            = aquastat_fract
        self.off_sensor_fract          = off_sensor_fract
        self.on_trigger_t_f            = on_trigger_t_f
        self.off_trigger_t_f           = off_trigger_t_f
        self.load_shift_schedule       = load_shift_schedule
        self.load_up_hours             = load_up_hours
        self.shed_aquastat_fract       = shed_aquastat_fract
        self.load_up_aquastat_fract    = load_up_aquastat_fract
        self.shed_off_sensor_fract     = shed_off_sensor_fract
        self.load_up_off_sensor_fract  = load_up_off_sensor_fract
        self.load_up_off_trigger_t_f   = load_up_off_trigger_t_f
        self.load_shift_percent        = load_shift_percent
        self.return_temp_f             = return_temp_f
        self.return_flow_gpm           = return_flow_gpm
        self.tm_on_temp_f              = tm_on_temp_f if tm_on_temp_f is not None else supply_temp_f - 5.0
        self.tm_off_temp_f             = tm_off_temp_f if tm_off_temp_f is not None else supply_temp_f
        self.tm_off_time_hr            = tm_off_time_hr
        self.tm_safety_factor          = tm_safety_factor
        self.utility_cost_tracker      = utility_cost_tracker
        self.california_spec_mode      = california_spec_mode

        self._building    = None
        self._dhw_system  = None

        # Build and size immediately
        self.build()

    # ------------------------------------------------------------------
    # Build orchestration
    # ------------------------------------------------------------------

    def build(self) -> None:
        """Build the Building and DHWSystem (including sizing) from stored params."""
        self._building   = self._build_building()
        self._dhw_system = self._build_dhw_system()

    def _build_building(self):
        """Construct and return the Building for the configured type and climate."""
        from ecoengine.objects.building.Building import Building
        from ecoengine.objects.building.ClimateZone import ClimateZone

        zone = self._build_climate_zone(ClimateZone)
        return Building.from_building_type(
            building_type = self.building_type,
            magnitude     = self.magnitude,
            climate_zone  = zone,
            gpdpp         = self.gpdpp,
        )

    def _build_climate_zone(self, ClimateZone):
        """Resolve zip_code_or_climate_zone to a ClimateZone instance."""
        czv = self.zip_code_or_climate_zone
        if isinstance(czv, dict):
            return ClimateZone.from_design_conditions(**czv)
        if isinstance(czv, str) and czv.isdigit() and len(czv) == 5:
            return ClimateZone.from_zip_code(czv)
        if isinstance(czv, int) and 1 <= czv <= 96:
            return ClimateZone.from_zone_id(czv)
        if isinstance(czv, str):
            return ClimateZone.from_weather_station(czv)
        raise ValueError(
            f"Cannot determine ClimateZone from {czv!r}. "
            "Pass a 5-digit CA zip code string, a zone ID int (1–96), "
            "a weather station name string, or a dict with 'design_oat_f' "
            "and/or 'design_inlet_water_temp_f'."
        )

    def _build_control_map(self):
        """
        Build the control_schedule and control_map from stored aquastat parameters.

        Returns (control_schedule, control_map).
        """
        from ecoengine.objects.components.heating.Controls import Controls

        on_t  = self.on_trigger_t_f  if self.on_trigger_t_f  is not None else self.supply_temp_f
        off_t = self.off_trigger_t_f if self.off_trigger_t_f is not None else self.storage_temp_f

        normal = Controls(
            on_sensor_fract  = self.aquastat_fract,
            on_trigger_t_f   = on_t,
            off_sensor_fract = self.off_sensor_fract,
            off_trigger_t_f  = off_t,
            outlet_temp_f    = self.storage_temp_f,
        )

        if not self.load_shift_schedule:
            return ["normal"] * 24, {"normal": normal}

        # Build schedule from 24-element 0/1 list (0 = shed, 1 = run)
        schedule = []
        shed_hours = [h for h, v in enumerate(self.load_shift_schedule) if v == 0]
        first_shed = shed_hours[0] if shed_hours else None

        for hour in range(24):
            if self.load_shift_schedule[hour] == 0:
                schedule.append("shed")
            elif (
                first_shed is not None
                and self.load_up_hours > 0
                and first_shed - self.load_up_hours <= hour < first_shed
            ):
                schedule.append("loadUp")
            else:
                schedule.append("normal")

        cmap = {"normal": normal}

        shed_on_fract  = self.shed_aquastat_fract if self.shed_aquastat_fract is not None else self.aquastat_fract
        shed_off_fract = self.shed_off_sensor_fract if self.shed_off_sensor_fract is not None else self.off_sensor_fract
        cmap["shed"] = Controls(
            on_sensor_fract  = shed_on_fract,
            on_trigger_t_f   = on_t,
            off_sensor_fract = shed_off_fract,
            off_trigger_t_f  = off_t,
            outlet_temp_f    = self.storage_temp_f,
        )

        if self.load_up_hours > 0 and self.load_up_aquastat_fract is not None:
            lu_off_fract = self.load_up_off_sensor_fract if self.load_up_off_sensor_fract is not None else self.off_sensor_fract
            lu_off_t     = self.load_up_off_trigger_t_f  if self.load_up_off_trigger_t_f  is not None else off_t
            cmap["loadUp"] = Controls(
                on_sensor_fract  = self.load_up_aquastat_fract,
                on_trigger_t_f   = on_t,
                off_sensor_fract = lu_off_fract,
                off_trigger_t_f  = lu_off_t,
                outlet_temp_f    = self.storage_temp_f,
            )

        return schedule, cmap

    def _build_dhw_system(self):
        """
        Construct and return the appropriate sized DHWSystem subclass based on
        self.schematic.

        Supported schematics
        --------------------
        * ``'primary_no_recirc'`` → DHWSystem
        * ``'parallel_loop'``    → ParallelLoopSystem

        Raises
        ------
        ValueError
            If the schematic is not recognised or required recirc params are missing.
        NotImplementedError
            If the schematic is recognised but not yet fully implemented.
        """
        from ecoengine.objects.dhwsystems.DHWSystem import DHWSystem, _load_shift_fract_total_vol

        control_schedule, control_map = self._build_control_map()
        ls_fract = (
            _load_shift_fract_total_vol(self.load_shift_percent)
            if self.load_shift_schedule
            else 1.0
        )

        if self.schematic == "primary_no_recirc":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return DHWSystem.from_size(
                    building                   = self._building,
                    supply_temp_f              = self.supply_temp_f,
                    storage_temp_f             = self.storage_temp_f,
                    max_daily_run_hr           = self.max_daily_run_hr,
                    defrost_factor             = self.defrost_factor,
                    control_schedule           = control_schedule,
                    control_map                = control_map,
                    load_shift_fract_total_vol = ls_fract,
                )

        if self.schematic == "parallel_loop":
            from ecoengine.objects.dhwsystems.recirc_systems.ParallelLoopSystem import ParallelLoopSystem
            self._require_recirc_params()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return ParallelLoopSystem.from_size(
                    building                   = self._building,
                    supply_temp_f              = self.supply_temp_f,
                    storage_temp_f             = self.storage_temp_f,
                    return_temp_f              = self.return_temp_f,
                    return_flow_gpm            = self.return_flow_gpm,
                    tm_on_temp_f               = self.tm_on_temp_f,
                    tm_off_temp_f              = self.tm_off_temp_f,
                    tm_off_time_hr             = self.tm_off_time_hr,
                    tm_safety_factor           = self.tm_safety_factor,
                    max_daily_run_hr           = self.max_daily_run_hr,
                    defrost_factor             = self.defrost_factor,
                    control_schedule           = control_schedule,
                    control_map                = control_map,
                    load_shift_fract_total_vol = ls_fract,
                )

        if self.schematic == "swing_tank":
            from ecoengine.objects.dhwsystems.recirc_systems.SwingSystem import SwingSystem
            self._require_recirc_params()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return SwingSystem.from_size(
                    building                   = self._building,
                    supply_temp_f              = self.supply_temp_f,
                    storage_temp_f             = self.storage_temp_f,
                    return_temp_f              = self.return_temp_f,
                    return_flow_gpm            = self.return_flow_gpm,
                    tm_safety_factor           = self.tm_safety_factor,
                    max_daily_run_hr           = self.max_daily_run_hr,
                    defrost_factor             = self.defrost_factor,
                    control_schedule           = control_schedule,
                    control_map                = control_map,
                    load_shift_fract_total_vol = ls_fract,
                )

        if self.schematic == "single_pass_rtp":
            from ecoengine.objects.dhwsystems.rtp_systems.SinglePassRTPSystem import SinglePassRTPSystem
            self._require_recirc_params()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return SinglePassRTPSystem.from_size(
                    building                   = self._building,
                    supply_temp_f              = self.supply_temp_f,
                    storage_temp_f             = self.storage_temp_f,
                    return_temp_f              = self.return_temp_f,
                    return_flow_gpm            = self.return_flow_gpm,
                    max_daily_run_hr           = self.max_daily_run_hr,
                    defrost_factor             = self.defrost_factor,
                    control_schedule           = control_schedule,
                    control_map                = control_map,
                    load_shift_fract_total_vol = ls_fract,
                )

        raise ValueError(
            f"Unknown schematic {self.schematic!r}. "
            "Supported values: 'primary_no_recirc', 'parallel_loop', 'swing_tank', 'single_pass_rtp'."
        )

    def _require_recirc_params(self) -> None:
        missing = [
            name for name, val in [
                ("return_temp_f",   self.return_temp_f),
                ("return_flow_gpm", self.return_flow_gpm),
            ]
            if val is None
        ]
        if missing:
            raise ValueError(
                f"Schematic '{self.schematic}' requires: {', '.join(missing)}."
            )

    # ------------------------------------------------------------------
    # Sizing results
    # ------------------------------------------------------------------

    def get_sizing_results(self) -> dict:
        """
        Return the sizing results from the built DHWSystem.

        Returns
        -------
        dict
            Always contains ``'min_capacity_kbtuh'`` and ``'min_storage_storageT_gal'``.
            Parallel loop systems also include ``'min_tm_volume_gal'`` and
            ``'min_tm_capacity_kbtuh'``.
        """
        sys = self._dhw_system
        result = {
            "min_capacity_kbtuh":      sys._minimum_capacity_kbtuh,
            "min_storage_storageT_gal": sys._minimum_storage_storageT_gal,
        }
        if hasattr(sys, "_minimum_tm_volume_gal") and sys._minimum_tm_volume_gal is not None:
            result["min_tm_volume_gal"]      = sys._minimum_tm_volume_gal
            result["min_tm_capacity_kbtuh"]  = sys._minimum_tm_capacity_kbtuh
        return result

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def simulate_3day(self, **sim_run_kwargs):
        """
        Run a 3-day design-day simulation at 1-minute timesteps.

        Parameters
        ----------
        **sim_run_kwargs
            Optional keyword arguments forwarded to SimulationRun.__init__(),
            e.g. ``outlet_deficit_threshold_f=5.0``, ``outlet_deficit_max_min=10``.

        Returns
        -------
        SimulationRun
        """
        return _simulate_3day(self._dhw_system, self._building, **sim_run_kwargs)

    def simulate_annual(self, **sim_run_kwargs):
        """
        Run a full annual simulation at 10-minute timesteps.

        Parameters
        ----------
        **sim_run_kwargs
            Optional keyword arguments forwarded to SimulationRun.__init__().

        Returns
        -------
        SimulationRun
        """
        return _simulate_annual(self._dhw_system, self._building, **sim_run_kwargs)

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def get_simulation_summary(self, simulation_run) -> dict:
        """
        Return a summary dict from a completed SimulationRun.

        Parameters
        ----------
        simulation_run : SimulationRun

        Returns
        -------
        dict
            Keys: 'successful', 'total_outage_min', 'total_energy_kwh',
            'peak_demand_kw', 'num_steps_recorded', 'stopped_early'.
        """
        return simulation_run.get_summary()

    def get_annual_cost_estimate(self, simulation_run) -> dict:
        """
        Compute annual utility cost from a completed annual SimulationRun.

        Parameters
        ----------
        simulation_run : SimulationRun

        Returns
        -------
        dict
            Monthly energy breakdown (kWh) by month.
        """
        return {"monthly_energy_kwh": simulation_run.get_monthly_energy_kwh()}
