_ANNUAL_DURATION_MIN = 365 * 24 * 60   # 525600
_DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

# Tank temperature nodes: fractional heights from bottom (0) to top (1)
_TANK_NODE_FRACTS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
_TANK_NODE_LABELS = ["Tank 0% (bottom)", "Tank 20%", "Tank 40%", "Tank 60%", "Tank 80%", "Tank 100% (top)"]
# Blue→red gradient avoiding CSS 'blue' (#0000FF) and 'red' (#FF0000)
_TANK_NODE_COLORS = ["#003f88", "#0077b6", "#00b4d8", "#f4a261", "#e76f51", "#9b2226"]


class SimulationRun:
    """
    Holds all per-timestep outputs from a simulation of a DHWSystem in a Building.

    Stores time-series data (energy use, tank volume, DHW demand, capacity) and
    provides methods to assess whether the system successfully met demand and to
    compute summary metrics for visualization and cost/emissions comparisons.
    """

    def __init__(
        self,
        duration_min: int,
        timestep_min: int,
        outlet_deficit_threshold_f: float = 5.0,
        outlet_deficit_max_min: int = 10,
    ) -> None:
        """
        Parameters
        ----------
        duration_min : int
            Total simulation duration in minutes.
        timestep_min : int
            Size of each simulation timestep in minutes (1 for 3-day, 10 for annual).
        outlet_deficit_threshold_f : float
            Degrees below supply temperature at which the top-of-tank outlet is
            considered to be in deficit. Default 5 °F.
        outlet_deficit_max_min : int
            Maximum consecutive minutes of outlet deficit before the simulation
            is halted early. Default 10 minutes.
        """
        self.duration_min  = duration_min
        self.timestep_min  = timestep_min
        self.num_steps     = duration_min // timestep_min

        # Per-timestep lists (appended by record_timestep)
        self.dhw_demand_supplyT_gal:    list[float] = []
        self.usable_volume_supplyT_gal: list[float] = []
        self.heater_output_kbtuh:       list[float] = []
        self.heater_power_in_kw:        list[float | None] = []
        self.oat_f:                     list[float] = []
        self.inlet_water_temp_f:        list[float] = []
        self.heater_mode:               list[str]   = []   # "normal", "shed", "loadUp", etc.

        # Tank temperature nodes — one list per fractional height
        # Indexed as: tank_temps_f[node_idx][timestep]
        # node_idx 0 = bottom (0%), 5 = top (100%)
        self.tank_temps_f: list[list[float]] = [[] for _ in _TANK_NODE_FRACTS]

        # TM (swing tank) per-timestep data — only populated for SwingSystem runs
        self.tm_tank_temp_f:           list[float] = []
        self.tm_heater_output_kbtuh:   list[float] = []

        # Cumulative outage counter [minutes]
        self.outage_minutes: int = 0

        # Set by Simulator after construction; used for unit conversions in output methods
        self.supply_temp_f: float | None = None

        # Outlet deficit stop condition
        self.outlet_deficit_threshold_f   = outlet_deficit_threshold_f
        self.outlet_deficit_max_min       = outlet_deficit_max_min
        self._outlet_deficit_consec_min   = 0   # internal consecutive-minute counter
        self.stopped_early: bool          = False

    def record_timestep(
        self,
        dhw_demand_supplyT_gal: float,
        usable_volume_supplyT_gal: float,
        heater_output_kbtuh: float,
        heater_power_in_kw: float | None,
        oat_f: float,
        inlet_water_temp_f: float,
        tank_temps_f: list[float],
        mode: str = "normal",
        tm_tank_temp_f: float | None = None,
        tm_heater_output_kbtuh: float | None = None,
    ) -> None:
        """
        Append one timestep's worth of data to the run record.

        Parameters
        ----------
        dhw_demand_supplyT_gal : float
            Hot water drawn this timestep at supply temperature [gallons].
        usable_volume_supplyT_gal : float
            Gallons at or above supply temperature remaining in tank after draw.
        heater_output_kbtuh : float
            Total heat delivered by active heaters this timestep [kBTU/hr].
        heater_power_in_kw : float | None
            Electrical power consumed by active heaters [kW]. None when no
            real performance map is available (e.g. NominalPerformanceMap).
        oat_f : float
            Outdoor air temperature this timestep [°F].
        inlet_water_temp_f : float
            Cold water inlet temperature this timestep [°F].
        tank_temps_f : list[float]
            Temperatures at each tank node (6 values, bottom to top) [°F].
            Must have the same length as _TANK_NODE_FRACTS.
        tm_tank_temp_f : float | None
            Current temperature of the TM (swing) tank [°F]. Only provided
            by SwingSystem; None for all other system types.
        tm_heater_output_kbtuh : float | None
            Heat output of the TM element this timestep [kBTU/hr]. None for
            non-swing systems.
        """
        self.dhw_demand_supplyT_gal.append(dhw_demand_supplyT_gal)
        self.usable_volume_supplyT_gal.append(usable_volume_supplyT_gal)
        self.heater_output_kbtuh.append(heater_output_kbtuh)
        self.heater_power_in_kw.append(heater_power_in_kw)
        self.oat_f.append(oat_f)
        self.inlet_water_temp_f.append(inlet_water_temp_f)
        self.heater_mode.append(mode)
        for node_idx, temp in enumerate(tank_temps_f):
            self.tank_temps_f[node_idx].append(temp)
        if tm_tank_temp_f is not None:
            self.tm_tank_temp_f.append(tm_tank_temp_f)
        if tm_heater_output_kbtuh is not None:
            self.tm_heater_output_kbtuh.append(tm_heater_output_kbtuh)

    def check_outlet_deficit(self, top_tank_temp_f: float, supply_temp_f: float) -> bool:
        """
        Track consecutive minutes where the top-of-tank temperature is more than
        ``outlet_deficit_threshold_f`` degrees below ``supply_temp_f``.

        Returns True (and sets ``stopped_early``) when the consecutive deficit
        duration exceeds ``outlet_deficit_max_min``, signalling the simulation
        loop to halt.  Resets the counter whenever the condition is not met.

        Parameters
        ----------
        top_tank_temp_f : float
            Current temperature at the top of the storage tank [°F].
        supply_temp_f : float
            System hot water delivery temperature [°F].

        Returns
        -------
        bool
            True if the simulation should stop immediately.
        """
        if top_tank_temp_f < supply_temp_f - self.outlet_deficit_threshold_f:
            self._outlet_deficit_consec_min += self.timestep_min
            if self._outlet_deficit_consec_min > self.outlet_deficit_max_min:
                self.stopped_early = True
                return True
        else:
            self._outlet_deficit_consec_min = 0
        return False

    def record_outage(self, duration_min: int) -> None:
        """
        Record a DHW outage (demand could not be met from tank).

        Parameters
        ----------
        duration_min : int
            Duration of this outage event [minutes].
        """
        self.outage_minutes += duration_min

    def is_successful(self, max_outage_min: int = 0) -> bool:
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
        return self.outage_minutes <= max_outage_min

    def get_total_energy_kwh(self) -> float:
        """
        Return total electrical energy consumed over the simulation [kWh].

        Timesteps with no power data (None) are treated as 0 kW.

        Returns
        -------
        float
        """
        hours_per_step = self.timestep_min / 60.0
        return sum(
            (p or 0.0) * hours_per_step
            for p in self.heater_power_in_kw
        )

    def get_peak_demand_kw(self) -> float:
        """
        Return peak instantaneous power draw observed during the simulation [kW].

        Returns
        -------
        float
        """
        non_none = [p for p in self.heater_power_in_kw if p is not None]
        return max(non_none) if non_none else 0.0

    def get_summary(self) -> dict:
        """
        Return a dict summarizing key simulation metrics.

        Returns
        -------
        dict
            Keys: 'successful', 'total_outage_min', 'total_energy_kwh',
            'peak_demand_kw', 'num_steps_recorded', 'stopped_early'.
        """
        return {
            "successful":          self.is_successful(),
            "total_outage_min":    self.outage_minutes,
            "total_energy_kwh":    self.get_total_energy_kwh(),
            "peak_demand_kw":      self.get_peak_demand_kw(),
            "num_steps_recorded":  len(self.dhw_demand_supplyT_gal),
            "stopped_early":       self.stopped_early,
        }

    def to_csv(self, filepath: str) -> None:
        """
        Write all per-timestep values to a CSV file.

        Columns: timestep, time_min, dhw_demand_supplyT_gal,
        usable_volume_supplyT_gal, heater_output_kbtuh, heater_power_in_kw,
        oat_f, inlet_water_temp_f, tank_temp_0pct, tank_temp_20pct, ..., tank_temp_100pct.

        Parameters
        ----------
        filepath : str
            Destination file path (e.g. ``'simulation_output.csv'``).
        """
        import csv as _csv
        n = len(self.dhw_demand_supplyT_gal)
        tank_col_names = [f"tank_temp_{int(f*100)}pct" for f in _TANK_NODE_FRACTS]
        with open(filepath, "w", newline="") as f:
            writer = _csv.writer(f)
            writer.writerow([
                "timestep", "time_min",
                "dhw_demand_supplyT_gal", "usable_volume_supplyT_gal",
                "heater_output_kbtuh", "heater_power_in_kw",
                "oat_f", "inlet_water_temp_f",
                *tank_col_names,
            ])
            for i in range(n):
                writer.writerow([
                    i,
                    i * self.timestep_min,
                    self.dhw_demand_supplyT_gal[i],
                    self.usable_volume_supplyT_gal[i],
                    self.heater_output_kbtuh[i],
                    self.heater_power_in_kw[i],
                    self.oat_f[i],
                    self.inlet_water_temp_f[i],
                    *(self.tank_temps_f[node][i] for node in range(len(_TANK_NODE_FRACTS))),
                ])

    def to_plotly(
        self,
        title: str = "Simulation Results",
        filepath: str | None = None,
        include_temperatures: bool = False,
    ) -> "plotly.graph_objects.Figure":
        """
        Return a Plotly figure with gallons/flow on the left Y axis and
        temperature on the right Y axis, both plotted against time (minutes).

        Left axis (Y1) — Volume / Flow Rate
        -------------------------------------
        * Usable tank volume at supply temperature [gal]        (green, solid)
        * DHW demand [gal/hr]                                   (blue, solid)
        * Heater generation [gal/hr]                            (red, solid)

        Right axis (Y2) — Temperature
        --------------------------------
        * Outdoor air temperature [°F]                          (orange, solid)
        * Inlet water temperature [°F]                          (steelblue, solid)
        * Tank temperatures at 0%, 20%, 40%, 60%, 80%, 100%     (blue→red gradient, dashed)

        Requires the ``plotly`` package::

            pip install plotly

        Parameters
        ----------
        title : str
            Figure title.
        filepath : str | None
            If provided, write the figure to this path as a self-contained
            HTML file (e.g. ``'output/simulation.html'``). The figure is
            also returned regardless.
        include_temperatures : bool
            If True, add a right Y axis with OAT, inlet water temperature, and
            all six tank node temperatures. If False (default), only the left
            gallons/flow-rate axis is shown.

        Returns
        -------
        plotly.graph_objects.Figure
        """
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
        except ImportError:
            raise ImportError(
                "plotly is required for to_plotly(). "
                "Install it with: pip install plotly"
            )

        time_min = [i * self.timestep_min for i in range(len(self.dhw_demand_supplyT_gal))]
        has_tm = bool(self.tm_tank_temp_f)

        if has_tm:
            fig = make_subplots(
                rows=2, cols=1,
                specs=[[{"secondary_y": True}], [{"secondary_y": True}]],
                shared_xaxes=True,
                vertical_spacing=0.08,
                row_heights=[0.65, 0.35],
                subplot_titles=["Primary System", "Temperature Maintenance (TM)"],
            )
        else:
            fig = make_subplots(specs=[[{"secondary_y": True}]])

        steps_per_hour = 60 / self.timestep_min

        # --- Row 1: Volume traces (Y1, left axis) ---
        fig.add_trace(
            go.Scatter(x=time_min, y=self.usable_volume_supplyT_gal,
                       name="Usable Volume (gal at or above Supply Temp)", line=dict(color="green", width=1.5)),
            secondary_y=False, **({} if not has_tm else {"row": 1, "col": 1}),
        )
        hourly_demand = [v * steps_per_hour for v in self.dhw_demand_supplyT_gal]
        fig.add_trace(
            go.Scatter(x=time_min, y=hourly_demand,
                       name="DHW Demand (gal/hr at Supply Temp)", line=dict(color="blue", width=1)),
            secondary_y=False, **({} if not has_tm else {"row": 1, "col": 1}),
        )

        if self.supply_temp_f is not None:
            _RHO_CP = 8.353535  # BTU / (gal·°F)
            heater_gph = [
                kbtuh * 1000.0
                / (_RHO_CP * max(1.0, self.supply_temp_f - inlet_t))
                for kbtuh, inlet_t in zip(
                    self.heater_output_kbtuh, self.inlet_water_temp_f
                )
            ]
            fig.add_trace(
                go.Scatter(x=time_min, y=heater_gph,
                           name="Heater Generation (gal/hr at Supply Temperature)", line=dict(color="red", width=1)),
                secondary_y=False, **({} if not has_tm else {"row": 1, "col": 1}),
            )

        if include_temperatures:
            # --- Temperature traces (Y2, right axis, row 1) ---
            fig.add_trace(
                go.Scatter(x=time_min, y=self.oat_f,
                           name="OAT (°F)", line=dict(color="orange", width=1)),
                secondary_y=True, **({} if not has_tm else {"row": 1, "col": 1}),
            )
            fig.add_trace(
                go.Scatter(x=time_min, y=self.inlet_water_temp_f,
                           name="Inlet Water (°F)", line=dict(color="steelblue", width=1)),
                secondary_y=True, **({} if not has_tm else {"row": 1, "col": 1}),
            )

            # --- Tank temperature traces (Y2, dashed, blue→red gradient) ---
            for label, color, temps in zip(_TANK_NODE_LABELS, _TANK_NODE_COLORS, self.tank_temps_f):
                if not temps:
                    continue
                fig.add_trace(
                    go.Scatter(
                        x=time_min,
                        y=temps,
                        name=label,
                        line=dict(color=color, width=1, dash="dash"),
                    ),
                    secondary_y=True, **({} if not has_tm else {"row": 1, "col": 1}),
                )

        # --- Row 2: TM (swing) tank panel ---
        if has_tm:
            tm_time = [i * self.timestep_min for i in range(len(self.tm_tank_temp_f))]
            # Left Y2: TM heater output [kBTU/hr]
            fig.add_trace(
                go.Scatter(x=tm_time, y=self.tm_heater_output_kbtuh,
                           name="TM Heater Output (kBTU/hr)",
                           line=dict(color="darkorange", width=1),
                           fill="tozeroy", fillcolor="rgba(255,165,0,0.15)"),
                secondary_y=False, row=2, col=1,
            )
            # Right Y2: TM tank temperature [°F]
            fig.add_trace(
                go.Scatter(x=tm_time, y=self.tm_tank_temp_f,
                           name="Swing Tank Temp (°F)",
                           line=dict(color="purple", width=1.5)),
                secondary_y=True, row=2, col=1,
            )

        # --- Load-shift shading: blue=shed, green=loadUp ---
        if self.heater_mode:
            _LS_COLORS = {"shed": "rgba(0,0,255,0.2)", "loadUp": "rgba(0,200,0,0.2)"}
            _LS_LEGEND_ADDED: set[str] = set()
            i = 0
            n = len(self.heater_mode)
            while i < n:
                m = self.heater_mode[i]
                if m in _LS_COLORS:
                    # Find end of this contiguous block
                    j = i + 1
                    while j < n and self.heater_mode[j] == m:
                        j += 1
                    x0 = time_min[i]
                    x1 = time_min[j - 1] + self.timestep_min
                    label = "Shed" if m == "shed" else "Load-Up"
                    fig.add_vrect(
                        x0=x0, x1=x1,
                        fillcolor=_LS_COLORS[m],
                        layer="below",
                        line_width=0,
                        annotation_text="" if m in _LS_LEGEND_ADDED else label,
                        annotation_position="top left",
                        annotation_font_size=10,
                    )
                    _LS_LEGEND_ADDED.add(m)
                    i = j
                else:
                    i += 1

        fig.update_xaxes(title_text="Time (minutes)", row=2 if has_tm else 1)
        if has_tm:
            fig.update_yaxes(title_text="Volume (gal) / Flow Rate (gal/hr)",
                             secondary_y=False, row=1, col=1)
            if include_temperatures:
                fig.update_yaxes(title_text="Temperature (°F)",
                                 secondary_y=True, row=1, col=1)
            fig.update_yaxes(title_text="TM Output (kBTU/hr)",
                             secondary_y=False, row=2, col=1)
            fig.update_yaxes(title_text="Swing Tank Temp (°F)",
                             secondary_y=True, row=2, col=1)
        else:
            fig.update_yaxes(title_text="Volume (gal) / Flow Rate (gal/hr)", secondary_y=False)
            if include_temperatures:
                fig.update_yaxes(title_text="Temperature (°F)", secondary_y=True)
        fig.update_layout(
            title_text=title,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.08,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor="rgba(0,0,0,0.2)",
                borderwidth=1,
            ),
        )

        if filepath is not None:
            fig.write_html(filepath)

        return fig

    def get_monthly_energy_kwh(self) -> list[float]:
        """
        Break down energy consumption by calendar month (annual runs only).

        For non-annual simulations, returns a 12-element list of zeros.

        Returns
        -------
        list[float]
            12-element list of energy [kWh] per month, January through December.
        """
        monthly = [0.0] * 12
        if self.duration_min != _ANNUAL_DURATION_MIN:
            return monthly

        hours_per_step = self.timestep_min / 60.0
        steps_per_day  = 24 * 60 // self.timestep_min
        step = 0
        for month_idx, days in enumerate(_DAYS_IN_MONTH):
            n_steps = days * steps_per_day
            monthly[month_idx] = sum(
                (self.heater_power_in_kw[i] or 0.0) * hours_per_step
                for i in range(step, min(step + n_steps, len(self.heater_power_in_kw)))
            )
            step += n_steps
        return monthly
