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
    outage_volume_gal: list[float]
    outage_temp_delta_f: list[float]

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
        self.outage_volume_gal   = []
        self.outage_temp_delta_f = []
        max_deficit_f: float = 0.0

        for t in range(_TOTAL_STEPS):
            step = SinglePassRTPSystem.simulate_step(self, building, t, interval_min=1)
            pre_top_temp = self.storage_tank.get_temperature_at_fraction(1.0)
            demand = step["demand_supplyT_gal"]
            if pre_top_temp < self.supply_temp_f:
                deficit_f = self.supply_temp_f - pre_top_temp
                max_deficit_f = max(max_deficit_f, deficit_f)
                self.outage_volume_gal.append(demand)
                self.outage_temp_delta_f.append(deficit_f)
            else:
                self.outage_volume_gal.append(0.0)
                self.outage_temp_delta_f.append(0.0)

        # --- 3. Check whether a gas backup is actually needed ---
        total_outage_min = sum(1 for v in self.outage_volume_gal if v > 0.0)
        if total_outage_min <= _MIN_OUTAGE_MIN and max_deficit_f <= _MIN_DEFICIT_F:
            raise ValueError(
                "The primary SinglePassRTPSystem is already adequately sized: "
                f"outage duration was {total_outage_min} min "
                f"(threshold {_MIN_OUTAGE_MIN} min) and max temperature deficit "
                f"was {max_deficit_f:.2f} °F (threshold {_MIN_DEFICIT_F:.1f} °F). "
                "No gas backup is required."
            )

        # --- 4. Size gas backup at the default 30-minute window ---
        gas_capacity_kbtuh, gas_storage_vol_gal = self._gas_backup_from_window(_WINDOW_MIN)
        # TODO add thermal efficiency

        # --- 5. Build gas backup components ---
        self.gas_water_heater = WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=gas_capacity_kbtuh,
            control_schedule=["normal"] * 24,
            control_map={"normal": gas_controls},
        )
        self.gas_storage_tank = MixedStorageTank(total_volume_gal=gas_storage_vol_gal)

    # ------------------------------------------------------------------
    # Gas backup sizing helpers
    # ------------------------------------------------------------------

    def _gas_backup_from_window(self, window_min: int) -> tuple[float, float]:
        """
        Find the worst ``window_min``-length stretch of the sizing-sim outage
        arrays and return the implied gas backup requirements.

        Parameters
        ----------
        window_min : int
            Contiguous window length in minutes.

        Returns
        -------
        tuple[float, float]
            ``(gas_capacity_kbtuh, gas_storage_vol_gal)``
        """
        total_steps = len(self.outage_volume_gal)
        w = min(window_min, total_steps)

        window_score = sum(self.outage_temp_delta_f[:w])
        best_score   = window_score
        best_start   = 0

        for i in range(1, total_steps - w + 1):
            window_score += self.outage_temp_delta_f[i + w - 1] - self.outage_temp_delta_f[i - 1]
            if window_score > best_score:
                best_score = window_score
                best_start = i

        best_slice_vol   = self.outage_volume_gal[best_start : best_start + w]
        best_slice_delta = self.outage_temp_delta_f[best_start : best_start + w]

        gas_storage_vol_gal = sum(best_slice_vol)
        avg_peak_flow_gpm   = gas_storage_vol_gal / w
        avg_delta_f         = max(best_slice_delta) if any(d > 0 for d in best_slice_delta) else 0.0
        gas_capacity_kbtuh  = _RHO_CP * avg_peak_flow_gpm * avg_delta_f * 60.0 / 1000.0

        return gas_capacity_kbtuh, gas_storage_vol_gal

    def get_sizing_curve(self) -> "plotly.graph_objects.Figure":
        """
        Return a Plotly sizing-curve figure for the gas backup system.

        Sweeps window sizes from 60 down to 5 minutes in 5-minute steps,
        computing the gas capacity and storage implied by each window.  The
        30-minute window (the default used by ``_size_gas_backup``) is
        highlighted as the recommended design point.

        Returns
        -------
        plotly.graph_objects.Figure

        Raises
        ------
        RuntimeError
            If ``from_size()`` has not been called (outage arrays not populated).
        """
        if not getattr(self, "outage_volume_gal", None):
            raise RuntimeError(
                "Gas backup outage data is not available. Call from_size() first."
            )

        try:
            import plotly.graph_objects as go
        except ImportError:
            raise ImportError(
                "plotly is required for get_sizing_curve(). "
                "Install it with: pip install plotly"
            )

        _RECOMMENDED_WINDOW = 30
        # Ascending order so the slider moves left-to-right as storage increases,
        # matching the direction the diamond travels on the curve.
        window_sizes = list(range(5, 65, 5))   # [5, 10, …, 60]

        capacities = []
        storages   = []
        for w in window_sizes:
            cap, vol = self._gas_backup_from_window(w)
            capacities.append(cap)
            storages.append(vol)

        rec_idx = window_sizes.index(_RECOMMENDED_WINDOW)

        hover = (
            "Window: <b>%{customdata} min</b><br>"
            "Gas storage: <b>%{x:.1f} gal</b><br>"
            "Gas capacity: <b>%{y:.1f} kBTU/hr</b>"
            "<extra></extra>"
        )

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=storages, y=capacities,
            mode="lines",
            line=dict(color="#28a745", width=3),
            customdata=window_sizes,
            hovertemplate=hover,
            showlegend=False,
        ))

        for i, w in enumerate(window_sizes):
            fig.add_trace(go.Scatter(
                x=[storages[i]], y=[capacities[i]],
                mode="markers",
                marker=dict(symbol="diamond", color="#2EA3F2", size=12),
                customdata=[w],
                hovertemplate=hover,
                showlegend=False,
                visible=(i == rec_idx),
            ))

        steps = []
        for i, w in enumerate(window_sizes):
            visibility = [True] + [j == i for j in range(len(window_sizes))]
            steps.append(dict(
                label=(
                    f"Window: <b>{w} min</b>  |  "
                    f"Storage: <b>{storages[i]:.1f} gal</b>  |  "
                    f"Capacity: <b>{capacities[i]:.1f} kBTU/hr</b>"
                ),
                method="update",
                args=[{"visible": visibility}],
            ))

        fig.update_layout(
            title="Gas Backup Sizing Curve — SP RTP In-Series",
            xaxis_title="Gas Storage Volume (gal)",
            yaxis_title="Gas Heating Capacity (kBTU/hr)",
            showlegend=False,
            sliders=[dict(
                steps=steps,
                active=rec_idx,
                currentvalue=dict(
                    prefix="<b>Selected size</b>: ",
                    visible=True,
                    font=dict(size=14),
                    xanchor="left",
                ),
                pad={"t": 60},
                ticklen=0,
                minorticklen=0,
                bgcolor="#CCD9DB",
                borderwidth=0,
            )],
        )

        return fig

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
