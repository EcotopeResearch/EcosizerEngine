from __future__ import annotations

from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.storage.EnergyTank import EnergyTank
from ecoengine.objects.components.storage.MixedStorageTank import MixedStorageTank
from ecoengine.constants.constants import _RHO_CP, _W_TO_KBTUH
from ecoengine.interfaces.Simulator import _initial_percent_useable
from ..utils import mixing_valve_behavior
from .SinglePassRTPSystem import SinglePassRTPSystem, _SPRTP_STRAT_SLOPE

_GAS_DEADBAND_F: float = 8.0


class SP_RTPInSeriesSystem(SinglePassRTPSystem):
    """
    Single-pass RTP system with a gas water heater and storage tank in series.

    The primary HPWH (EnergyTank + WaterHeater) is intentionally capped at
    caller-supplied nominal specs.  A gas_water_heater backed by a
    gas_storage_tank (MixedStorageTank) covers any remaining capacity or
    volume shortfall.

    Construction
    ------------
    Use the factory classmethod rather than calling __init__ directly::

        system = SP_RTPInSeriesSystem.from_size(
            building               = building,
            supply_temp_f          = 120.0,
            storage_temp_f         = 150.0,
            return_temp_f          = 110.0,
            return_flow_gpm        = 3.0,
            nominal_capacity_kbtuh = 50.0,
            nominal_storage_gal    = 200.0,
        )
    """

    gas_water_heater: WaterHeater
    gas_storage_tank: MixedStorageTank

    # ------------------------------------------------------------------
    # Factory constructor
    # ------------------------------------------------------------------

    @classmethod
    def from_size(
        cls,
        building,
        supply_temp_f: float,
        storage_temp_f: float,
        return_temp_f: float,
        return_flow_gpm: float,
        nominal_capacity_kbtuh: float,
        nominal_storage_gal: float,
        max_daily_run_hr: float = 16.0,
        defrost_factor: float = 1.0,
        tm_safety_factor: float = 1.0,
        control_schedule: list[str] | None = None,
        control_map: dict[str, Controls] | None = None,
        strat_slope: float = _SPRTP_STRAT_SLOPE,
        load_shift_fract_total_vol: float = 1.0,
    ) -> SP_RTPInSeriesSystem:
        """
        Size the system for the given building, then build it.

        The primary HPWH is capped at ``nominal_capacity_kbtuh`` and
        ``nominal_storage_gal``; the gas backup is sized to cover the
        remainder via ``_size_gas_backup``.

        Parameters
        ----------
        building : Building
        supply_temp_f : float
            DHW delivery temperature [°F].
        storage_temp_f : float
            Hot water storage setpoint [°F].
        return_temp_f : float
            Recirculation loop return temperature [°F].
        return_flow_gpm : float
            Recirculation loop flow rate [GPM].
        nominal_capacity_kbtuh : float
            Primary HPWH heating capacity ceiling [kBTU/hr].
        nominal_storage_gal : float
            Primary storage tank volume ceiling [gal at storageT].
        max_daily_run_hr : float
            Maximum hours the primary heater may run per day. Default 16.
        defrost_factor : float
            Fraction of rated capacity available after defrost (0–1). Default 1.0.
        control_schedule : list[str] | None
            24-element list of control keys. None for no load-shifting.
        control_map : dict[str, Controls] | None
            Controls objects keyed by schedule label.
        strat_slope : float
            Temperature gradient [°F per %-height] for stratification factor.
        load_shift_fract_total_vol : float
            Demand scaling factor for load-shift sizing (0–1). Default 1.0.

        Returns
        -------
        SP_RTPInSeriesSystem
        """
        system = cls(
            water_heaters=[],
            storage_tank=None,
            supply_temp_f=supply_temp_f,
            storage_temp_f=storage_temp_f,
            return_temp_f=return_temp_f,
            return_flow_gpm=return_flow_gpm,
            max_daily_run_hr=max_daily_run_hr,
            defrost_factor=defrost_factor,
            tm_safety_factor=tm_safety_factor,
        )
        system.size(
            building,
            control_schedule=control_schedule,
            control_map=control_map,
            strat_slope=strat_slope,
            load_shift_fract_total_vol=load_shift_fract_total_vol,
        )

        # Primary HPWH: capped at caller-provided nominal specs
        system.storage_tank = EnergyTank(
            total_volume_gal=nominal_storage_gal,
            cold_temp_f=building.get_design_inlet_water_temp_f(),
            storage_temp_f=storage_temp_f,
            strat_slope=strat_slope,
        )
        system.water_heaters = [WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=nominal_capacity_kbtuh,
            control_schedule=control_schedule,
            control_map=control_map,
        )]

        # Gas backup controls: on at supply_temp, off at supply_temp + deadband
        gas_controls = Controls(
            on_sensor_fract=0.5,
            on_trigger_t_f=supply_temp_f + 5.0,
            off_sensor_fract=0.5,
            off_trigger_t_f=supply_temp_f + 5.0 + _GAS_DEADBAND_F,
            outlet_temp_f=supply_temp_f + 5.0 + _GAS_DEADBAND_F,
        )
        system._size_gas_backup(
            building=building,
            nominal_capacity_kbtuh=nominal_capacity_kbtuh,
            nominal_storage_gal=nominal_storage_gal,
            gas_controls=gas_controls,
        )
        return system

    # ------------------------------------------------------------------
    # Gas backup sizing
    # ------------------------------------------------------------------

    def _size_gas_backup(
        self,
        building,
        nominal_capacity_kbtuh: float,
        nominal_storage_gal: float,
        gas_controls: Controls,
    ) -> None:
        """
        Size gas_water_heater and gas_storage_tank by simulating 2 days as a
        plain SinglePassRTPSystem (undersized primary only) and finding the
        worst 30-minute outage window.

        Parameters
        ----------
        building : Building
        nominal_capacity_kbtuh : float
            Primary HPWH capacity ceiling [kBTU/hr].
        nominal_storage_gal : float
            Primary storage volume ceiling [gal at storageT].
        gas_controls : Controls
            Controls for the gas backup water heater.

        Raises
        ------
        ValueError
            If the primary SPRTP is already adequately sized (outage < 10 min
            and max deficit < 2 °F), meaning no gas backup is needed.
        """
        _WINDOW_MIN      = 30
        _MIN_OUTAGE_MIN  = 10
        _MIN_DEFICIT_F   = 2.0
        _TOTAL_STEPS     = 2 * 24 * 60   # 2 days at 1-min intervals

        # --- 1. Initialise primary tank at the same charge level used in simulation ---
        inlet_temp_f = building.get_design_inlet_water_temp_f()
        percent_useable = _initial_percent_useable(self)
        self.storage_tank.initialize(self.storage_temp_f, inlet_temp_f, percent_useable=percent_useable)

        # --- 2. Two-day simulation as SinglePassRTPSystem ---
        outage_volume_gal: list[float] = []
        outage_temp_delta_f: list[float] = []
        max_deficit_f: float = 0.0

        for t in range(_TOTAL_STEPS):
            step = SinglePassRTPSystem.simulate_step(self, building, t, interval_min=1)
            pre_top_temp = self.storage_tank.get_temperature_at_fraction(1.0)
            demand = step["demand_supplyT_gal"]
            if pre_top_temp < self.supply_temp_f:
                deficit_f = self.supply_temp_f - pre_top_temp
                max_deficit_f = max(max_deficit_f, deficit_f)
                outage_volume_gal.append(demand)
                outage_temp_delta_f.append(deficit_f)
            else:
                outage_volume_gal.append(0.0)
                outage_temp_delta_f.append(0.0)

        # --- 3. Check whether a gas backup is actually needed ---
        total_outage_min = sum(1 for v in outage_volume_gal if v > 0.0)
        if total_outage_min <= _MIN_OUTAGE_MIN and max_deficit_f <= _MIN_DEFICIT_F:
            raise ValueError(
                "The primary SinglePassRTPSystem is already adequately sized: "
                f"outage duration was {total_outage_min} min "
                f"(threshold {_MIN_OUTAGE_MIN} min) and max temperature deficit "
                f"was {max_deficit_f:.2f} °F (threshold {_MIN_DEFICIT_F:.1f} °F). "
                "No gas backup is required."
            )

        # --- 4. Sliding 30-minute window: find worst outage stretch ---
        window_vol = sum(outage_temp_delta_f[:_WINDOW_MIN])
        best_vol   = window_vol
        best_start = 0

        for i in range(1, _TOTAL_STEPS - _WINDOW_MIN + 1):
            window_vol += outage_temp_delta_f[i + _WINDOW_MIN - 1] - outage_temp_delta_f[i - 1]
            if window_vol > best_vol:
                best_vol   = window_vol
                best_start = i

        best_slice_vol   = outage_volume_gal[best_start : best_start + _WINDOW_MIN]
        best_slice_delta = outage_temp_delta_f[best_start : best_start + _WINDOW_MIN]

        gas_storage_vol_gal = sum(best_slice_vol)
        avg_peak_flow_gpm = gas_storage_vol_gal / _WINDOW_MIN
        avg_delta_f         = max(best_slice_delta)
        gas_capacity_kbtuh  = _RHO_CP * avg_peak_flow_gpm * avg_delta_f * 60.0 / 1000.0
        # TODO add thermal eficiency 

        # --- 5. Build gas backup components ---
        self.gas_water_heater = WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=gas_capacity_kbtuh,
            control_schedule=["normal"] * 24,
            control_map={"normal": gas_controls},
        )
        self.gas_storage_tank = MixedStorageTank(total_volume_gal=gas_storage_vol_gal)

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def simulate_step(
        self,
        building,
        timestep_interval: int,
        interval_min: int = 1,
        mode: str = "normal",
    ) -> dict:
        """
        Run one timestep for a single-pass RTP system.

        Delegates the DHW draw and heater logic to the base class, then
        applies recirculation losses to the storage tank.  The recirc
        return flow cools the bottom of the tank every minute, reducing
        usable volume.  The returned dict is updated to reflect post-recirc
        tank state.
        """
        # step = super().simulate_step(building, timestep_interval, interval_min, mode)
        use_avg = any(wh.is_load_shifting() for wh in self.water_heaters)
        demand_supplyT_gal = building.get_dhw_load_supplyT_gal(
            timestep_interval, interval_min, use_avg=use_avg
        )
        oat_f          = building.get_oat_f(timestep_interval, interval_min)
        inlet_temp_f   = building.get_inlet_water_temp_f(timestep_interval, interval_min)
        hour_of_day    = (timestep_interval * interval_min // 60) % 24
        outlet_temp_f  = self._get_outlet_temp_f(hour_of_day)
        mode = (
            self.water_heaters[0].control_schedule[hour_of_day]
            if self.water_heaters and self.water_heaters[0].control_schedule
            else "normal"
        )

        self.storage_tank.update_cold_temp_f(inlet_temp_f)
        # Update on/off state for each heater based on current tank condition
        for wh in self.water_heaters:
            wh.update_state(self.storage_tank, hour_of_day)

        # Apply heating from all active heaters to the tank
        total_kbtuh    = sum(
            wh.get_output_kbtuh(oat_f, wh.get_outlet_temp_f(hour_of_day), inlet_temp_f)
            for wh in self.water_heaters
        )
        total_kw: float | None = None
        active_kws = [
            wh.get_power_in_kw(oat_f, wh.get_outlet_temp_f(hour_of_day), inlet_temp_f)
            for wh in self.water_heaters
            if wh.is_active()
        ]
        if any(kw is not None for kw in active_kws):
            total_kw = sum(kw or 0.0 for kw in active_kws)

        self.storage_tank.heat(total_kbtuh, interval_min, outlet_temp_f)

        # --- Mixing valve draw ---
        gas_top_t    = self.gas_storage_tank.get_temperature_at_fraction(1.0)
        flow_per_min_gal = self.return_flow_gpm * interval_min
        result = mixing_valve_behavior(
            demand_supplyT_gal,
            flow_per_min_gal,
            inlet_temp_f,
            self.supply_temp_f,
            self.return_temp_f,
            gas_top_t,
        )
        draw_gal       = result["storage_draw_gal"]
        mv_inlet_temp_f = result["inlet_temp_f"]

        primary_draw_temp_f = self.storage_tank.get_average_draw_temp_f(draw_gal)
        self.storage_tank.draw_physical_gal(draw_gal, mv_inlet_temp_f, update_internal_cold_temp = False)

        # Gas water heater heating
        self.gas_storage_tank.mix_primary_inflow(draw_gal, primary_draw_temp_f)
        self.gas_water_heater.update_state(self.gas_storage_tank, hour_of_day)
        gas_ctrl     = self.gas_water_heater.get_controls_for_hour(hour_of_day)
        gas_outlet_f = gas_ctrl.outlet_temp_f if gas_ctrl is not None else self.supply_temp_f + _GAS_DEADBAND_F
        gas_kbtuh    = self.gas_water_heater.get_output_kbtuh(oat_f, gas_outlet_f)
        gas_kw_val   = ( # TODO figure out gas carbon outputs
            self.gas_water_heater.get_power_in_kw(oat_f, gas_outlet_f)
            if self.gas_water_heater.is_active()
            else None
        )
        self.gas_storage_tank.heat(gas_kbtuh, interval_min, gas_outlet_f)

        usable_vol_gal = self.storage_tank.get_usable_volume_supplyT_gal(
            self.supply_temp_f
        )
        tank_temps_f = [
            self.storage_tank.get_temperature_at_fraction(f)
            for f in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        ]

        return {
            "demand_supplyT_gal":        demand_supplyT_gal,
            "usable_volume_supplyT_gal": usable_vol_gal,
            "heater_output_kbtuh":       total_kbtuh,
            "heater_power_in_kw":        total_kw,
            "oat_f":                     oat_f,
            "inlet_water_temp_f":        inlet_temp_f,
            "tank_temps_f":              tank_temps_f,
            "mode":                      mode,
            "tm_tank_temp_f":          self.gas_storage_tank.get_temperature_at_fraction(1.0),
            "tm_heater_output_kbtuh":  gas_kbtuh,
            "tm_heater_input_kw":      gas_kbtuh / _W_TO_KBTUH,
            "delivery_temp_f":         self.gas_storage_tank.get_temperature_at_fraction(1.0),
        }
