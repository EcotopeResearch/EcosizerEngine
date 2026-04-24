from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from typing import TYPE_CHECKING

from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.storage.MixedStorageTank import MixedStorageTank
from ecoengine.objects.components.storage.StratifiedTank import StratifiedTank
from ecoengine.objects.dhwsystems.DHWSystem import _get_peak_indices
from .SwingSystem import SwingSystem, _ELEMENT_DEADBAND_F, _hr_to_min
from ecoengine.constants.constants import _RHO_CP, _W_TO_KBTUH

if TYPE_CHECKING:
    from ecoengine.objects.building.Building import Building


class SwingERTrdOffSystem(SwingSystem):
    """
    Swing tank system with an electric resistance (ER) element sized to
    compensate when the primary HPWH cannot maintain the swing tank at supply
    temperature during peak demand events.

    This class is identical to SwingSystem in all simulation behaviour —
    ``simulate_step()`` is fully inherited without override.  The only
    runtime difference is that the ``tm_water_heater`` carries a higher
    ``nominal_capacity_kbtuh``: the base temperature-maintenance capacity
    (sized to handle recirc losses) plus the ER addition (sized to close the
    worst-case single-minute temperature deficit found by the sizing simulation).

    Sizing flow
    -----------
    1. ``SwingSystem.size()`` — TM volume, running volume, primary capacity.
    2. ``_size_er_element()`` — 2-day sizing simulation (primary empty + full
       start); finds max swing-tank temperature deficit; computes ER capacity.
    3. ``_minimum_tm_capacity_kbtuh`` is bumped by the ER result before
       ``from_size()`` builds the ``tm_water_heater``.

    Construction
    ------------
    Two factory classmethods are provided:

    ``from_size`` — full sizing from scratch::

        system = SwingERTrdOffSystem.from_size(
            building        = building,
            supply_temp_f   = 120.0,
            storage_temp_f  = 150.0,
            return_temp_f   = 110.0,
            return_flow_gpm = 3.0,
            er_safety_factor = 1.0,
        )

    ``from_components`` — sizes only the ER element given pre-built (possibly
    undersized) primary components::

        system = SwingERTrdOffSystem.from_components(
            water_heaters           = swing.water_heaters,
            storage_tank            = swing.storage_tank,
            tm_storage_tank         = swing.tm_storage_tank,
            initial_tm_capacity_kbtuh = swing.tm_water_heater.performance_map.nominal_capacity_kbtuh,
            building                = building,
            supply_temp_f           = 120.0,
            storage_temp_f          = 150.0,
            return_temp_f           = 110.0,
            return_flow_gpm         = 3.0,
        )
    """

    def __init__(
        self,
        water_heaters,
        storage_tank,
        supply_temp_f: float,
        storage_temp_f: float,
        return_temp_f: float,
        return_flow_gpm: float,
        tm_safety_factor: float = 1.2,
        er_safety_factor: float = 1.0,
        max_daily_run_hr: float = 24.0,
        defrost_factor: float = 1.0,
    ):
        super().__init__(
            water_heaters=water_heaters,
            storage_tank=storage_tank,
            supply_temp_f=supply_temp_f,
            storage_temp_f=storage_temp_f,
            return_temp_f=return_temp_f,
            return_flow_gpm=return_flow_gpm,
            tm_safety_factor=tm_safety_factor,
            max_daily_run_hr=max_daily_run_hr,
            defrost_factor=defrost_factor,
        )
        self.er_safety_factor = er_safety_factor
        # Set by _size_er_element(); stores the ER addition only (not base TM).
        self._er_capacity_kbtuh: float | None = None

    # ------------------------------------------------------------------
    # Factory constructor
    # ------------------------------------------------------------------

    @classmethod
    def from_components(
        cls,
        water_heaters: list[WaterHeater],
        storage_tank,
        tm_storage_tank: MixedStorageTank,
        initial_tm_capacity_kbtuh: float,
        building: Building,
        supply_temp_f: float,
        storage_temp_f: float,
        return_temp_f: float,
        return_flow_gpm: float,
        er_safety_factor: float = 1.0,
        control_schedule: list[str] | None = None,
        control_map: dict[str, Controls] | None = None,
    ) -> SwingERTrdOffSystem:
        """
        Build a ``SwingERTrdOffSystem`` from pre-sized components by sizing only
        the ER element of the swing tank.

        Use this when you already have a ``SwingSystem`` whose primary water
        heaters and/or primary storage tank have been intentionally undersized,
        and you want to compensate by adding an ER element to the swing tank.
        The primary components are accepted as-is; only the swing tank TM
        element capacity is recomputed.

        Parameters
        ----------
        water_heaters : list[WaterHeater]
            Pre-built primary water heaters (already at their final, possibly
            reduced, capacity).
        storage_tank : StorageTank
            Pre-built primary storage tank.
        tm_storage_tank : MixedStorageTank
            Pre-built swing tank (its ``total_volume_gal`` drives ER sizing).
        initial_tm_capacity_kbtuh : float
            Starting TM element capacity [kBTU/hr] before any ER addition.
            Typically taken from the original ``SwingSystem.tm_water_heater``.
        building : Building
            Building model used for the ER sizing simulation.
        supply_temp_f : float
            Hot-water supply temperature [°F].
        storage_temp_f : float
            Primary storage temperature [°F].
        return_temp_f : float
            Recirculation loop return temperature [°F].
        return_flow_gpm : float
            Recirculation loop flow rate [GPM].
        er_safety_factor : float
            Multiplier applied to the raw ER capacity result (default 1.0).
        control_schedule : list[str] | None
            24-element hour-of-day schedule for the primary heaters' controls.
        control_map : dict[str, Controls] | None
            Controls map for the primary heaters.

        Returns
        -------
        SwingERTrdOffSystem
            Fully constructed system with ``tm_water_heater`` sized to include
            the ER addition.  Primary components are the objects passed in.
        """
        system = cls(
            water_heaters=water_heaters,
            storage_tank=storage_tank,
            supply_temp_f=supply_temp_f,
            storage_temp_f=storage_temp_f,
            return_temp_f=return_temp_f,
            return_flow_gpm=return_flow_gpm,
            er_safety_factor=er_safety_factor,
        )

        # Populate sizing state from the pre-built components so that
        # _size_er_element() has all the values it needs.
        design_oat_f = building.get_design_oat_f()
        design_inlet_temp_f = system._require_design_inlet_temp(building)
        system._minimum_capacity_kbtuh = sum(
            wh.performance_map.get_capacity_kbtuh(design_oat_f, storage_temp_f, design_inlet_temp_f)
            for wh in water_heaters
        )
        system._minimum_storage_storageT_gal = storage_tank.total_volume_gal
        system._minimum_tm_volume_gal        = tm_storage_tank.total_volume_gal
        system._minimum_tm_capacity_kbtuh    = initial_tm_capacity_kbtuh

        # Assign the swing tank; _size_er_element will bump _minimum_tm_capacity_kbtuh.
        system.tm_storage_tank = tm_storage_tank

        system._size_er_element(building)

        tm_controls = Controls(
            on_sensor_fract  = 0.5,
            on_trigger_t_f   = supply_temp_f,
            off_sensor_fract = 0.5,
            off_trigger_t_f  = supply_temp_f + _ELEMENT_DEADBAND_F,
            outlet_temp_f    = supply_temp_f + _ELEMENT_DEADBAND_F,
        )
        system.tm_water_heater = WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=system._minimum_tm_capacity_kbtuh,
            control_schedule=["normal"] * 24,
            control_map={"normal": tm_controls},
        )

        return system

    @classmethod
    def from_size(
        cls,
        building: Building,
        supply_temp_f: float,
        storage_temp_f: float,
        return_temp_f: float,
        return_flow_gpm: float,
        tm_safety_factor: float = 1.2,
        er_safety_factor: float = 1.0,
        max_daily_run_hr: float = 24.0,
        defrost_factor: float = 1.0,
        control_schedule: list[str] | None = None,
        control_map: dict[str, Controls] | None = None,
        strat_slope: float = 2.8,
        load_shift_fract_total_vol: float = 1.0,
    ) -> SwingERTrdOffSystem:
        system = cls(
            water_heaters=[],
            storage_tank=None,
            supply_temp_f=supply_temp_f,
            storage_temp_f=storage_temp_f,
            return_temp_f=return_temp_f,
            return_flow_gpm=return_flow_gpm,
            tm_safety_factor=tm_safety_factor,
            er_safety_factor=er_safety_factor,
            max_daily_run_hr=max_daily_run_hr,
            defrost_factor=defrost_factor,
        )
        system.size(
            building,
            control_schedule=control_schedule,
            control_map=control_map,
            strat_slope=strat_slope,
            load_shift_fract_total_vol=load_shift_fract_total_vol,
        )

        # Primary components
        system.storage_tank = StratifiedTank(
            total_volume_gal=system._minimum_storage_storageT_gal,
            strat_slope=strat_slope,
        )
        system.water_heaters = [WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=system._minimum_capacity_kbtuh,
            control_schedule=control_schedule,
            control_map=control_map,
        )]

        # TM (swing tank) components — capacity already includes the ER addition
        system.tm_storage_tank = MixedStorageTank(
            total_volume_gal=system._minimum_tm_volume_gal,
        )
        tm_controls = Controls(
            on_sensor_fract  = 0.5,
            on_trigger_t_f   = supply_temp_f,
            off_sensor_fract = 0.5,
            off_trigger_t_f  = supply_temp_f + _ELEMENT_DEADBAND_F,
            outlet_temp_f    = supply_temp_f + _ELEMENT_DEADBAND_F,
        )
        system.tm_water_heater = WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=system._minimum_tm_capacity_kbtuh,
            control_schedule=["normal"] * 24,
            control_map={"normal": tm_controls},
        )

        return system

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------

    def size(
        self,
        building: Building,
        control_schedule: list[str] | None = None,
        control_map: dict[str, Controls] | None = None,
        strat_slope: float = 2.8,
        load_shift_fract_total_vol: float = 1.0,
    ) -> None:
        """
        Size the system: base SwingSystem sizing followed by ER element sizing.
        """
        super().size(
            building,
            control_schedule=control_schedule,
            control_map=control_map,
            strat_slope=strat_slope,
            load_shift_fract_total_vol=load_shift_fract_total_vol,
        )
        self._size_er_element(building)

    def _size_er_element(self, building: Building) -> None:
        """
        Determine additional ER capacity for the swing tank TM element by
        simulating the full system over 2 days with two initial primary-tank
        conditions (primary empty and primary full).

        Mirrors ``SwingTankER.sizeERElement()`` from the original codebase.

        Algorithm
        ---------
        At each minute step:

        1. Compute the hot-water volume the swing tank must draw from the
           primary based on the current swing tank temperature.
        2. Update the primary tank level (bounded) based on HPWH generation
           minus that draw.  When the primary is depleted, the swing tank
           receives water at ``inlet_temp_f`` rather than ``storage_temp_f``.
        3. Advance the swing tank one step using the base TM capacity only.
           When the tank falls below ``supply_temp_f``, record the deficit
           and clamp to ``supply_temp_f`` (simulating ER closing the gap).

        When the primary tank is empty the HPWH is still running; its output
        flows directly to the swing tank, so the feed temperature is blended
        (hot HPWH output + cold city water) rather than pure cold.

        ER capacity formula::

            er_cap = (tm_vol × rhoCp × 60 × max_deficit / 1000) × er_safety_factor

        This is the instantaneous power needed to raise the entire swing tank
        volume by ``max_deficit`` degrees in one minute.

        Parameters
        ----------
        building : Building
        """
        inlet_t_f = self._require_design_inlet_temp(building)

        # Primary HPWH capacity at design conditions.
        # The original codebase queried the real performance map at
        # (design_OAT, design_inlet + 15.0°F, storage_temp_f) to find the
        # HPWH's actual output at worst-case conditions.  With NominalPerformanceMap
        # the result is always _minimum_capacity_kbtuh regardless of temperatures,
        # so we use it directly.  The +15.0°F inlet offset is preserved here for
        # reference when this path is extended to real performance maps.
        # TODO: confirm why +15°F is used for the inlet temperature here
        hpwh_design_kbtuh = self._minimum_capacity_kbtuh

        # Primary HPWH generation rate [gal/min at storage temp]
        gen_gpm = (
            hpwh_design_kbtuh * 1000.0
            / (_RHO_CP * (self.storage_temp_f - inlet_t_f))
            / 60.0
        )

        # 2-day minute-resolution demand array starting from the peak demand hour.
        daily_gal  = building.daily_dhw_use_supplyT_gal
        load_shape = building.peak_load_shape   # 24 normalised fractions
        hourly_diff = np.ones(24) / self.max_daily_run_hr - load_shape
        peak_indices = _get_peak_indices(hourly_diff)
        peak_idx = peak_indices[0] if peak_indices else 0

        # 3 days tiled so we can slice 48 hours from any peak index
        hw_out_hourly = np.tile(load_shape * daily_gal, 3)[peak_idx : peak_idx + 48]
        hw_out_min    = _hr_to_min(hw_out_hourly) / 60.0   # [gal/min at supply temp]
        n_steps       = len(hw_out_min)

        # Base TM capacity before ER addition — used throughout the sizing sim
        base_tm_kbtuh = self._minimum_tm_capacity_kbtuh

        max_deficit = 0.0

        # Run two scenarios: primary starts empty (0 gal) and primary starts full
        for primary_init_gal in (0.0, self._minimum_storage_storageT_gal):
            swing_t       = self.supply_temp_f
            swingheating  = False
            primary_level = primary_init_gal

            for i in range(n_steps):
                # Hot water drawn from primary this minute [gal at swing temp]
                if swing_t > inlet_t_f:
                    hw_from_primary = (
                        hw_out_min[i]
                        * (self.supply_temp_f - inlet_t_f)
                        / (swing_t - inlet_t_f)
                    )
                else:
                    hw_from_primary = hw_out_min[i]

                # Total hot water available this minute: stored hot + HPWH generation.
                # Even when the primary tank is empty, the HPWH is running and its
                # output flows straight through to the swing tank, so the feed is a
                # blend of hot HPWH output and cold city water rather than pure cold.
                hot_available = primary_level + gen_gpm
                if hw_from_primary <= 0.0 or hot_available <= 0.0:
                    feed_temp = inlet_t_f
                elif hw_from_primary <= hot_available:
                    feed_temp = self.storage_temp_f   # full demand met at storage temp
                else:
                    # Blend: hot_available gal at storage_temp + shortfall at inlet_t_f
                    feed_temp = (
                        hot_available * self.storage_temp_f
                        + (hw_from_primary - hot_available) * inlet_t_f
                    ) / hw_from_primary

                # Update primary tank level
                primary_level = min(
                    max(primary_level + gen_gpm - hw_from_primary, 0.0),
                    self._minimum_storage_storageT_gal,
                )

                swingheating, swing_t, deficit = self._run_one_swing_step_er(
                    swingheating, swing_t, hw_from_primary, feed_temp, base_tm_kbtuh,
                )
                if deficit > max_deficit:
                    max_deficit = deficit

        # ER capacity: power needed to close max_deficit across the whole swing
        # tank volume in one minute
        er_cap = (
            self._minimum_tm_volume_gal
            * _RHO_CP
            * 60.0
            * max_deficit
            / 1000.0
        ) * self.er_safety_factor

        self._er_capacity_kbtuh        = er_cap
        self._minimum_tm_capacity_kbtuh += er_cap

    def _run_one_swing_step_er(
        self,
        swingheating: bool,
        t_curr: float,
        hw_out: float,
        primary_storage_t_f: float,
        tm_capacity_kbtuh: float,
    ) -> tuple[bool, float, float]:
        """
        Advance the swing tank by one minute during the ER sizing simulation.

        Identical to ``SwingSystem._run_one_swing_step()`` except:

        * ``tm_capacity_kbtuh`` is passed explicitly (the base TM capacity,
          before any ER addition).
        * Instead of raising when the tank falls below ``supply_temp_f``, the
          deficit is recorded and the tank is clamped to ``supply_temp_f``,
          simulating the (yet-to-be-sized) ER element closing the gap.  The
          simulation then continues from ``supply_temp_f`` on the next step.

        Parameters
        ----------
        swingheating : bool
            True if the TM element was active at the start of this step.
        t_curr : float
            Swing tank temperature at the start of this step [°F].
        hw_out : float
            Volume drawn from primary storage into the swing tank this minute [gal].
        primary_storage_t_f : float
            Temperature of inflow from primary (``storage_temp_f`` when
            primary has hot water, ``inlet_temp_f`` when it is depleted).
        tm_capacity_kbtuh : float
            Base TM element capacity [kBTU/hr] (does not include ER addition).

        Returns
        -------
        swingheating : bool
        t_new : float
            Swing tank temperature after this step [°F].
        deficit_f : float
            Degrees the tank fell below ``supply_temp_f`` before clamping.
            0.0 when the base TM element alone maintained temperature.
        """
        tm_vol = self._minimum_tm_volume_gal
        t_new  = t_curr

        # Mix primary inflow into swing tank
        if hw_out > 0:
            vol_remaining = tm_vol - hw_out
            if vol_remaining <= 0:
                raise ValueError(
                    f"Swing tank ({tm_vol:.0f} gal) is undersized: "
                    f"per-minute draw of {hw_out:.3f} gal exceeds tank volume."
                )
            t_new = (hw_out * primary_storage_t_f + t_curr * vol_remaining) / tm_vol

        # Recirculation heat loss [°F/min]
        recirc_btuhr = self.get_recirc_loss_kbtuh() * 1000.0
        t_new -= recirc_btuhr / 60.0 / (_RHO_CP * tm_vol)

        # TM element heat rate [°F/min] using base (pre-ER) capacity
        element_dT = tm_capacity_kbtuh * 1000.0 / 60.0 / (_RHO_CP * tm_vol)

        if swingheating:
            t_new += element_dT
            if t_new > self.supply_temp_f + _ELEMENT_DEADBAND_F:
                time_over    = min(
                    (t_new - (self.supply_temp_f + _ELEMENT_DEADBAND_F)) / element_dT, 1.0
                )
                t_new       -= element_dT * time_over
                swingheating = False
        elif t_new <= self.supply_temp_f:
            time_missed  = min((self.supply_temp_f - t_new) / element_dT, 1.0)
            t_new       += element_dT * time_missed
            swingheating = True

        # Record deficit and clamp — ER is assumed to close the gap this step
        deficit = 0.0
        if t_new < self.supply_temp_f:
            deficit = self.supply_temp_f - t_new
            t_new   = self.supply_temp_f

        return swingheating, t_new, deficit

    # ------------------------------------------------------------------
    # ER sizing result accessors
    # ------------------------------------------------------------------

    def get_er_capacity_kbtuh(self) -> float:
        """Return the additional ER capacity added to the TM element [kBTU/hr]."""
        if self._er_capacity_kbtuh is None:
            raise RuntimeError("size() must be called before get_er_capacity_kbtuh().")
        return self._er_capacity_kbtuh

    def get_er_capacity_kw(self) -> float:
        """Return the additional ER capacity added to the TM element [kW]."""
        return self.get_er_capacity_kbtuh() / _W_TO_KBTUH

    # ------------------------------------------------------------------
    # ER sizing curve (trade-off plot)
    # ------------------------------------------------------------------

    def get_er_sized_points(
        self,
        building: Building,
        additional_er_safety: float = 1.0,
    ) -> tuple[list[float], list[float], int]:
        """
        Compute ER element size vs. percent-of-peak-load-covered trade-off points.

        Iterates building magnitude from 120% down to the fraction where no ER
        is needed, sizing the ER element at each step.  At 100% the already-
        computed sizing result is used directly.

        Parameters
        ----------
        building : Building
            Building used during sizing.  ``magnitude`` is temporarily mutated
            and restored before the method returns.
        additional_er_safety : float
            Safety factor applied to ER sizing for all fractions except 100%
            (which uses the value from the original ``size()`` call).

        Returns
        -------
        er_cap_kw : list[float]
            Total TM element capacity (base + ER) [kW] at each fraction,
            ordered from lowest to highest coverage.
        fract_covered : list[float]
            Percent-of-building values (e.g. 60.0, 70.0, … 120.0), same order.
        startind : int
            Index in the returned lists corresponding to 100% coverage (the
            actual sized system).
        """
        if self._er_capacity_kbtuh is None or self._er_capacity_kbtuh <= 0:
            raise RuntimeError(
                "get_er_sized_points() requires a system where ER sizing was "
                "needed.  No ER addition was found — check that size() has been "
                "called and that peak demand exceeds primary HPWH capacity."
            )

        original_daily_gal   = building.daily_dhw_use_supplyT_gal
        base_tm_kbtuh        = self._minimum_tm_capacity_kbtuh - self._er_capacity_kbtuh
        original_total_tm    = self._minimum_tm_capacity_kbtuh
        original_er_kbtuh    = self._er_capacity_kbtuh
        original_er_safety   = self.er_safety_factor

        er_cap_kw: list[float]    = []
        fract_covered: list[float] = []
        startind = 0

        i = 120.0
        while i > 0:
            if i == 100.0:
                startind   = len(fract_covered)
                total_tm_i = original_total_tm
                er_needed  = True
            else:
                building.daily_dhw_use_supplyT_gal = original_daily_gal * (i / 100.0)
                self._minimum_tm_capacity_kbtuh    = base_tm_kbtuh
                self._er_capacity_kbtuh            = None
                self.er_safety_factor              = additional_er_safety
                self._size_er_element(building)
                self.er_safety_factor              = original_er_safety
                total_tm_i = self._minimum_tm_capacity_kbtuh
                er_needed  = bool(self._er_capacity_kbtuh and self._er_capacity_kbtuh > 0)

            er_cap_kw.append(round(total_tm_i / _W_TO_KBTUH, 0))
            fract_covered.append(i)
            i -= 10.0

            if not er_needed:
                break  # no ER at this fraction; lower fractions won't need it either

        # Restore mutated state
        building.daily_dhw_use_supplyT_gal = original_daily_gal
        self._minimum_tm_capacity_kbtuh    = original_total_tm
        self._er_capacity_kbtuh            = original_er_kbtuh

        # Lists were built high-to-low; reverse so x is ascending
        fract_covered.reverse()
        er_cap_kw.reverse()
        startind = (len(fract_covered) - 1) - startind

        return er_cap_kw, fract_covered, startind

    def get_er_sizing_curve(
        self,
        building: Building,
        additional_er_safety: float = 1.0,
    ) -> go.Figure:
        """
        Return a Plotly figure showing the ER element size vs. percent coverage
        trade-off curve, with a slider to select the operating point.

        The curve traces total TM element capacity (base + ER) [kW] against the
        fraction of peak building load covered by the primary HPWH (%).  A
        diamond marker and slider indicate the 100%-coverage (actual sized) point.

        Parameters
        ----------
        building : Building
        additional_er_safety : float
            Safety factor for the re-sizing iterations (default 1.0).

        Returns
        -------
        plotly.graph_objects.Figure
        """
        er_cap_kw, fract_covered, startind = self.get_er_sized_points(
            building, additional_er_safety
        )

        fig = go.Figure()

        # --- main curve ---
        fig.add_trace(go.Scatter(
            x=fract_covered,
            y=er_cap_kw,
            visible=True,
            line=dict(color="#28a745", width=4),
            hovertemplate=(
                "Percent Coverage: %{x:.1f}%<br>"
                "ER Heating Capacity: %{y:.1f} kW"
            ),
            opacity=0.8,
        ))

        # --- one hidden marker per point (revealed by slider) ---
        for ii in range(len(fract_covered)):
            fig.add_trace(go.Scatter(
                x=[fract_covered[ii]],
                y=[er_cap_kw[ii]],
                visible=False,
                mode="markers",
                marker_symbol="diamond",
                opacity=1,
                marker_color="#2EA3F2",
                marker_size=10,
                name="System Size",
                hoverlabel=dict(font=dict(color="white"), bordercolor="white"),
            ))

        # Make the starting marker visible
        fig.data[startind + 1].visible = True

        fig.update_layout(
            title="Electric Resistance Sizing Curve",
            xaxis_title="Percent Coverage (%)",
            yaxis_title="Electric Resistance Heating Capacity (kW)",
            showlegend=False,
        )

        # --- slider ---
        steps = []
        for ii in range(1, len(fig.data)):
            label = (
                f"Percent Coverage: <b>{fract_covered[ii - 1]:.0f}</b> %, "
                f"Electric Resistance Heating Capacity: "
                f"<b>{er_cap_kw[ii - 1]:.1f}</b> kW"
            )
            step = dict(
                label=label,
                method="update",
                args=[{"visible": [False] * len(fig.data)}],
            )
            step["args"][0]["visible"][0]  = True   # curve always visible
            step["args"][0]["visible"][ii] = True   # this marker
            steps.append(step)

        fig.update_layout(sliders=[dict(
            steps=steps,
            active=startind,
            currentvalue=dict(
                font={"size": 16},
                prefix="<b>Electric Resistance Size</b> ",
                visible=True,
                xanchor="left",
            ),
            pad={"t": 50},
            minorticklen=0,
            ticklen=0,
            bgcolor="#CCD9DB",
            borderwidth=0,
        )])

        return fig
