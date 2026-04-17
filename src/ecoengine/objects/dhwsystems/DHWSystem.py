from __future__ import annotations

import warnings
import numpy as np
from statistics import NormalDist
from typing import TYPE_CHECKING

from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.storage.StorageTank import StorageTank, StratifiedTank

if TYPE_CHECKING:
    from ecoengine.objects.building.Building import Building

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------

# Volumetric heat capacity of water [BTU / (gallon * °F)]
_RHO_CP: float = 8.353535

# Normal distribution parameters for multi-family daily DHW demand variability.
# Used to compute fract_total_vol from load_shift_percent (percentile of days covered).
# Source: calibrated from multi-family occupancy stream data in original EcosizerEngine.
_LS_NORM_MEAN: float = 0.7052988591269841
_LS_NORM_STD:  float = 0.08236427664525116
_LS_NORM_DIST: NormalDist = NormalDist(mu=_LS_NORM_MEAN, sigma=_LS_NORM_STD)


def _load_shift_fract_total_vol(load_shift_percent: float) -> float:
    """
    Convert a load-shift coverage percentile to a demand scaling fraction.

    At load_shift_percent=1.0 the system is sized for 100% of days (no scaling).
    Below 1.0, daily demand is assumed to follow a normal distribution and the
    system is sized for the given percentile, accepting that higher-demand days
    will occasionally breach the shed window.

    Parameters
    ----------
    load_shift_percent : float
        Fraction of days the load-shift sizing must cover [0.25, 1.0].

    Returns
    -------
    float
        Scaling factor to apply to daily DHW demand during load-shift sizing (≤ 1.0).
    """
    if load_shift_percent >= 1.0:
        return 1.0
    fract = _LS_NORM_DIST.inv_cdf(load_shift_percent)
    return min(fract, 1.0)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _get_peak_indices(hourly_diff: np.ndarray) -> list[int]:
    """
    Return the hours where the system transitions from surplus to deficit,
    i.e. where hourly generation minus hourly demand goes from >= 0 to < 0.
    These are the starting points for cumulative-deficit accumulation.
    """
    n = len(hourly_diff)
    return [
        i for i in range(n)
        if hourly_diff[i - 1] >= 0 and hourly_diff[i] < 0
    ]


# ---------------------------------------------------------------------------
# DHWSystem
# ---------------------------------------------------------------------------

class DHWSystem:
    """
    Base class for all domestic hot water system configurations.

    Holds one or more WaterHeater objects, a StorageTank, and system-wide
    temperature setpoints. Subclasses implement configuration-specific sizing
    and simulation step logic.

    Construction
    ------------
    Do not call __init__ directly. Use one of the two factory class methods:

    * DHWSystem.from_size(building, controls, ...)
        Runs the sizing algorithm to find minimum required capacity and storage
        volume, then builds one WaterHeater holding all that capacity. The
        WaterHeater receives the provided Controls object; its on-sensor
        parameters drive the stratification factor used during sizing.

    * DHWSystem.from_components(storage_volume_storageT_gal, water_heaters, ...)
        Builds the system from explicitly provided components.
    """

    def __init__(
        self,
        water_heaters: list[WaterHeater],
        storage_tank: StorageTank | None,
        supply_temp_f: float,
        storage_temp_f: float,
        max_daily_run_hr: float = 16.0,
        defrost_factor: float = 1.0,
    ) -> None:
        """
        Parameters
        ----------
        water_heaters : list[WaterHeater]
            One or more heater units in this system.
        storage_tank : StorageTank | None
            Primary storage tank. None only during intermediate construction.
        supply_temp_f : float
            DHW delivery temperature to building occupants [°F].
        storage_temp_f : float
            Hot water storage setpoint temperature [°F].
        max_daily_run_hr : float
            Maximum hours the heating system may run per day (1-24). Used to
            calculate the required generation rate during sizing.
        defrost_factor : float
            Fraction of rated capacity available after accounting for defrost
            cycles (0-1). Typically 1.0 for non-frosting conditions.
        """
        self.water_heaters  = water_heaters
        self.storage_tank   = storage_tank
        self.supply_temp_f  = supply_temp_f
        self.storage_temp_f = storage_temp_f
        self.max_daily_run_hr = max_daily_run_hr
        self.defrost_factor   = defrost_factor

        # Sizing results — populated by size()
        self._minimum_capacity_kbtuh:        float | None = None
        self._minimum_storage_storageT_gal:  float | None = None

    # ------------------------------------------------------------------
    # Factory constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_size(
        cls,
        building: Building,
        supply_temp_f: float,
        storage_temp_f: float,
        max_daily_run_hr: float = 24.0,
        defrost_factor: float = 1.0,
        control_schedule: list[str] | None = None,
        control_map: dict[str, Controls] | None = None,
        strat_slope: float = 2.8,
        load_shift_fract_total_vol: float = 1.0,
    ) -> DHWSystem:
        """
        Size the system for the given building, then build it.

        Runs the sizing algorithm to determine the minimum required heating
        capacity and storage volume. Creates one WaterHeater backed by a
        NominalPerformanceMap (constant-output placeholder) holding all of the
        required capacity, and a StorageTank sized to the minimum required volume.

        The control_map is used during sizing: each Controls in the map
        contributes a stratification factor, and the minimum (worst-case) value
        drives storage volume. The same schedule and map are assigned to the
        created WaterHeater for use at simulation time.

        Parameters
        ----------
        building : Building
            The building whose DHW load drives the sizing calculation.
            Must have a ClimateZone (real or design-condition) so that design
            inlet water temperature is available.
        supply_temp_f : float
            DHW delivery temperature [°F].
        storage_temp_f : float
            Hot water storage setpoint [°F].
        max_daily_run_hr : float
            Maximum hours the system may run per day. Lower values drive
            higher capacity requirements and smaller storage requirements.
        defrost_factor : float
            Fraction of rated capacity available after defrost (0-1).
        control_schedule : list[str] | None
            24-element list mapping each hour of the day to a key in
            control_map. Standard keys are ``"normal"``, ``"loadUp"``, and
            ``"shed"``. Assigned to the created WaterHeater. None when no
            load-shifting or multi-mode control is required.
        control_map : dict[str, Controls] | None
            Maps control_schedule integers to Controls objects. All Controls
            in the map are considered during sizing (worst-case strat factor).
            None when no control logic is configured.
        strat_slope : float
            Temperature gradient through the tank's transition zone
            [°F per percentage-point of tank height]. Stored on the
            StorageTank and used during stratification factor calculations.
            Subclasses that model different tank geometries should override
            this via their own from_size() implementation.

        Returns
        -------
        DHWSystem
        """
        system = cls(
            water_heaters=[],
            storage_tank=None,
            supply_temp_f=supply_temp_f,
            storage_temp_f=storage_temp_f,
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

        system.storage_tank  = StratifiedTank(
            total_volume_gal=system._minimum_storage_storageT_gal,
            strat_slope=strat_slope,
        )
        system.water_heaters = [WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=system._minimum_capacity_kbtuh,
            control_schedule=control_schedule,
            control_map=control_map,
        )]
        return system

    @classmethod
    def from_components(
        cls,
        storage_volume_storageT_gal: float,
        water_heaters: list[WaterHeater],
        supply_temp_f: float,
        storage_temp_f: float,
        max_daily_run_hr: float = 24.0,
        defrost_factor: float = 1.0,
        strat_slope: float = 2.8,
    ) -> DHWSystem:
        """
        Build the system from explicitly provided storage volume and heaters.

        Use this path when storage volume and heating capacity are already
        known (e.g. from a previous sizing run, from equipment specs, or
        from user input) rather than being calculated from a building load.
        Each WaterHeater in the list should already carry its own Controls
        object.

        Parameters
        ----------
        storage_volume_storageT_gal : float
            Physical tank volume at storage temperature [gallons].
        water_heaters : list[WaterHeater]
            Pre-built list of WaterHeater objects for this system. There is
            no restriction on list length — one heater is the common case,
            but staged systems may have more.
        supply_temp_f : float
            DHW delivery temperature [°F].
        storage_temp_f : float
            Hot water storage setpoint [°F].
        max_daily_run_hr : float
            Maximum hours the system may run per day.
        defrost_factor : float
            Fraction of rated capacity available after defrost (0-1).
        strat_slope : float
            Temperature gradient through the tank's transition zone
            [°F per percentage-point of tank height]. Stored on the
            StorageTank for use during simulation.

        Returns
        -------
        DHWSystem
        """
        return cls(
            water_heaters=water_heaters,
            storage_tank=StratifiedTank(
                total_volume_gal=storage_volume_storageT_gal,
                strat_slope=strat_slope,
            ),
            supply_temp_f=supply_temp_f,
            storage_temp_f=storage_temp_f,
            max_daily_run_hr=max_daily_run_hr,
            defrost_factor=defrost_factor,
        )

    # ------------------------------------------------------------------
    # Sizing — public interface
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
        Compute the minimum heating capacity and storage volume for this
        system in the given building. Stores results internally; retrieve
        them with get_minimum_capacity_kbtuh() and
        get_minimum_storage_storageT_gal().

        Sizing is always performed on the 24-hour daily load shape. If the
        building is currently set to the annual shape, this method
        temporarily switches it back, sizes, then restores the annual shape.

        If the control_map contains a ``"shed"`` key, load-shift sizing is
        run in addition to normal sizing. The final capacity and storage volume
        are the maximum of the two paths.

        Parameters
        ----------
        building : Building
        control_schedule : list[str] | None
            24-element schedule of control keys (``"normal"``, ``"loadUp"``,
            ``"shed"``). Required for load-shift sizing; ignored otherwise.
        control_map : dict[str, Controls] | None
            All Controls objects that may be active during operation. Each
            Controls contributes a stratification factor; the minimum value
            (worst case) drives storage volume sizing. Each Controls is also
            checked for short-cycling risk. None uses sizing defaults.
        strat_slope : float
            Temperature gradient through the tank's transition zone
            [°F per percentage-point of tank height]. Should match the
            value that will be set on the StorageTank.
        load_shift_fract_total_vol : float
            Demand scaling factor for load-shift sizing (0–1). Derived from
            load_shift_percent via _load_shift_fract_total_vol(). Default 1.0
            (no scaling — size for 100% of days). Only applied to the LS sizing
            path; normal sizing is always against the full daily demand.

        Raises
        ------
        ValueError
            If the building has no design inlet water temperature available
            (no ClimateZone was provided at construction).
        """
        was_annual = building.is_annual_load_shape()
        if was_annual:
            building.set_to_daily_load_shape()

        # When load shifting, the heater cannot run during shed hours, so the
        # effective maximum daily run time is capped at the number of non-shed
        # hours. Matches original: maxDayRun_hr = min(compRuntime_hr, sum(loadShiftSchedule)).
        original_max_run_hr = self.max_daily_run_hr
        if control_schedule and self._is_load_shifting(control_map):
            non_shed_hours_hr = float(sum(1 for h in control_schedule if h != "shed"))
            self.max_daily_run_hr = min(self.max_daily_run_hr, non_shed_hours_hr)

        try:
            design_inlet_temp_f      = self._require_design_inlet_temp(building)
            capacity_kbtuh           = self._calc_required_capacity(building)
            running_vol_supplyT_gal  = self._calc_running_volume_supplyT_gal(building, capacity_kbtuh)
            strat_factor             = self._calc_stratification_factor(control_map, strat_slope, design_inlet_temp_f)
            storage_vol_storageT_gal = self._calc_storage_volume_storageT_gal(
                running_vol_supplyT_gal, strat_factor
            )

            if control_schedule and self._is_load_shifting(control_map):
                ls_capacity_kbtuh = self._calc_required_capacity_ls_kbtuh(
                    control_schedule, control_map, building, strat_slope,
                    fract_total_vol=load_shift_fract_total_vol,
                )
                gen_rate_ls_gph = self._calc_gen_rate_ls_gph(
                    control_schedule, control_map, building, strat_slope,
                    fract_total_vol=load_shift_fract_total_vol,
                )
                ls_running_vol_supplyT_gal = self._calc_running_volume_ls_supplyT_gal(
                    control_schedule, building, gen_rate_ls_gph,
                    fract_total_vol=load_shift_fract_total_vol,
                )
                ls_storage_vol_storageT_gal = self._calc_storage_volume_ls_storageT_gal(
                    ls_running_vol_supplyT_gal, control_map, strat_slope, design_inlet_temp_f
                )
                capacity_kbtuh           = max(capacity_kbtuh, ls_capacity_kbtuh)
                storage_vol_storageT_gal = max(storage_vol_storageT_gal, ls_storage_vol_storageT_gal)

            self._minimum_capacity_kbtuh       = capacity_kbtuh
            self._minimum_storage_storageT_gal = storage_vol_storageT_gal
            self._sizing_strat_slope           = strat_slope

            if control_map:
                self._warn_if_short_cycling(control_map, capacity_kbtuh, storage_vol_storageT_gal)

        finally:
            self.max_daily_run_hr = original_max_run_hr

        if was_annual:
            building.set_to_annual_load_shape()

    def get_minimum_capacity_kbtuh(self) -> float:
        """
        Return the minimum required heating capacity [kBTU/hr] from sizing.

        Raises
        ------
        RuntimeError
            If size() has not been called yet.
        """
        if self._minimum_capacity_kbtuh is None:
            raise RuntimeError("size() must be called before get_minimum_capacity_kbtuh().")
        return self._minimum_capacity_kbtuh

    def get_minimum_storage_storageT_gal(self) -> float:
        """
        Return the minimum required storage volume at storage temperature
        [gallons] from sizing.

        Raises
        ------
        RuntimeError
            If size() has not been called yet.
        """
        if self._minimum_storage_storageT_gal is None:
            raise RuntimeError("size() must be called before get_minimum_storage_storageT_gal().")
        return self._minimum_storage_storageT_gal

    def get_sizing_curve(
        self,
        building: Building,
        strat_slope: float = 2.8,
        step: float = 0.25,
    ) -> dict:
        """
        Compute the primary sizing curve — capacity vs. storage for varying run hours.

        Sweeps ``max_daily_run_hr`` from 24 down to the physical minimum
        (where the hourly generation rate equals peak hourly demand), sizing
        without load-shift at each point.  The resulting curve shows the
        full capacity-vs-storage tradeoff available to the designer.

        Because this calls the same internal sizing methods as ``size()``,
        subclass overrides (e.g. ``RTPSystem`` adding recirc capacity) are
        reflected automatically.

        The sweep is split into two segments:

        * ``[24, max_daily_run_hr)`` — the "over-designed" region to the left
          of the recommended point.
        * ``[max_daily_run_hr, min_run_hr)`` — the recommended point and
          everything to the right.

        ``recommended_index`` is the length of the first segment, i.e. the
        index in the returned lists that corresponds to ``max_daily_run_hr``.

        Parameters
        ----------
        building : Building
            The building whose DHW load drives the sizing.
        strat_slope : float
            Temperature gradient [°F per %-height] for the stratification
            factor calculation.  Should match the value used for sizing.
            Default 2.8.
        step : float
            Run-hour step size for the sweep.  Default 0.25 hr.

        Returns
        -------
        dict
            ``"heat_hours"``           : list[float] — run hrs at each point
            ``"capacity_kbtuh"``       : list[float] — capacity [kBTU/hr]
            ``"storage_storageT_gal"`` : list[float] — storage [gal at storageT]
            ``"recommended_index"``    : int — index of ``max_daily_run_hr``
        """
        was_annual = building.is_annual_load_shape()
        if was_annual:
            building.set_to_daily_load_shape()

        # Prefer the strat_slope that was actually used during size(), so the
        # curve is self-consistent with sizing results.
        _strat_slope = getattr(self, "_sizing_strat_slope", strat_slope)

        try:
            design_inlet = self._require_design_inlet_temp(building)
            # Stratification factor is independent of run hours — compute once.
            # Use the system's own control_map so the on-sensor fraction matches
            # what size() uses. Falls back to None (conservative ~3.0 factor) if
            # no water heaters have been attached yet.
            _cmap = self.water_heaters[0].control_map if self.water_heaters else None
            strat_factor = self._calc_stratification_factor(_cmap, _strat_slope, design_inlet)

            # Physical minimum: one hour of generation equals the peak demand hour.
            min_run_hr = 1.0 / float(np.max(building.peak_load_shape)) * 1.001

            # Build sweep: [24 → max_daily_run_hr) ++ [max_daily_run_hr → min_run_hr)
            arr1       = np.arange(24.0, self.max_daily_run_hr, -step)
            arr2       = np.arange(self.max_daily_run_hr, min_run_hr, -step)
            heat_hours = np.concatenate([arr1, arr2])
            rec_index  = len(arr1)   # index of the recommended point

            heat_hours_out: list[float] = []
            capacity_out:   list[float] = []
            storage_out:    list[float] = []

            original_run_hr = self.max_daily_run_hr
            try:
                for h in heat_hours:
                    self.max_daily_run_hr = float(h)
                    try:
                        cap         = self._calc_required_capacity(building)
                        running_vol = self._calc_running_volume_supplyT_gal(building, cap)
                        if running_vol == 0.0:
                            break   # generation exceeds peak demand — physical minimum reached
                        storage_vol = self._calc_storage_volume_storageT_gal(
                            running_vol, strat_factor
                        )
                    except (ValueError, RuntimeError):
                        break       # aquastat fraction or other sizing failure
                    heat_hours_out.append(float(h))
                    capacity_out.append(cap)
                    storage_out.append(storage_vol)
            finally:
                self.max_daily_run_hr = original_run_hr

            # If the sweep terminated before reaching the recommended point,
            # clamp so rec_index always points at a valid entry.
            rec_index = min(rec_index, max(0, len(heat_hours_out) - 1))

            return {
                "heat_hours":           heat_hours_out,
                "capacity_kbtuh":       capacity_out,
                "storage_storageT_gal": storage_out,
                "recommended_index":    rec_index,
            }
        finally:
            if was_annual:
                building.set_to_annual_load_shape()

    def get_ls_sizing_curve(
        self,
        building: Building,
        control_schedule: list[str],
        control_map: dict[str, Controls],
        strat_slope: float = 2.8,
        load_shift_percent: float = 1.0,
    ) -> dict:
        """
        Compute the load-shift sizing curve — capacity and storage as a function
        of demand-coverage percentile.

        Sweeps ``load_shift_percent`` from 0.25 to 1.00 in 0.01 steps (76
        points).  At each step the demand fraction ``fract_total_vol`` is
        derived from the normal-distribution model, and both normal and LS
        sizing are run; the maximum of each is stored.  This matches exactly
        what ``size()`` does at a given ``load_shift_fract_total_vol``.

        The x-axis of the resulting curve is the coverage percentile: at 1.00
        the system is sized to handle the most demanding day (largest storage /
        capacity); at 0.25 it accepts that 75 % of days will breach the shed
        window (smallest system).

        Parameters
        ----------
        building : Building
        control_schedule : list[str]
            24-element schedule with ``"normal"``, ``"loadUp"``, ``"shed"``
            keys.
        control_map : dict[str, Controls]
            Must include at least ``"normal"`` and ``"shed"`` entries.
        strat_slope : float
            Temperature gradient [°F per %-height] for stratification factor.
            Default 2.8.
        load_shift_percent : float
            The system's configured coverage percentile (0.25–1.0).  Used only
            to locate ``recommended_index`` in the returned arrays.
            Default 1.0.

        Returns
        -------
        dict
            ``"load_shift_percent"``   : list[float] — 0.25 → 1.00
            ``"capacity_kbtuh"``       : list[float]
            ``"storage_storageT_gal"`` : list[float]
            ``"recommended_index"``    : int

        Raises
        ------
        ValueError
            If ``control_map`` has no ``"shed"`` key (load-shift not configured).
        """
        if not self._is_load_shifting(control_map):
            raise ValueError(
                "get_ls_sizing_curve() requires a control_map with a 'shed' key. "
                "Use get_sizing_curve() for systems without load shifting."
            )

        was_annual = building.is_annual_load_shape()
        if was_annual:
            building.set_to_daily_load_shape()

        # Prefer the strat_slope that was actually used during size().
        _strat_slope = getattr(self, "_sizing_strat_slope", strat_slope)

        # Mirror size(): cap max_daily_run_hr to non-shed hours so the normal
        # pre-computation uses the same effective run time as size() does.
        original_max_run_hr = self.max_daily_run_hr
        non_shed_hours_hr   = float(sum(1 for h in control_schedule if h != "shed"))
        self.max_daily_run_hr = min(self.max_daily_run_hr, non_shed_hours_hr)

        try:
            design_inlet = self._require_design_inlet_temp(building)

            # Pre-compute quantities that don't vary with fract_total_vol.
            cap_normal     = self._calc_required_capacity(building)
            run_vol_normal = self._calc_running_volume_supplyT_gal(building, cap_normal)
            strat_normal   = self._calc_stratification_factor(
                control_map, _strat_slope, design_inlet
            )
            stor_normal    = self._calc_storage_volume_storageT_gal(
                run_vol_normal, strat_normal
            )

            # Sweep load_shift_percent from 0.25 to 1.00 in integer percentile steps.
            ls_percents: list[float] = [i / 100.0 for i in range(25, 101)]
            capacity_out: list[float] = []
            storage_out:  list[float] = []

            for ls_pct in ls_percents:
                fract = _load_shift_fract_total_vol(ls_pct)

                cap_ls = self._calc_required_capacity_ls_kbtuh(
                    control_schedule, control_map, building, _strat_slope, fract
                )
                gen_rate = self._calc_gen_rate_ls_gph(
                    control_schedule, control_map, building, _strat_slope, fract
                )
                run_vol_ls = self._calc_running_volume_ls_supplyT_gal(
                    control_schedule, building, gen_rate, fract
                )
                stor_ls = self._calc_storage_volume_ls_storageT_gal(
                    run_vol_ls, control_map, _strat_slope, design_inlet
                )

                capacity_out.append(max(cap_normal, cap_ls))
                storage_out.append(max(stor_normal, stor_ls))

            # Clamp load_shift_percent to the sweep range, then locate its index.
            ls_pct_clamped = max(0.25, min(1.0, load_shift_percent))
            rec_index      = round((ls_pct_clamped - 0.25) * 100)
            rec_index      = max(0, min(rec_index, len(ls_percents) - 1))

            return {
                "load_shift_percent":   ls_percents,
                "capacity_kbtuh":       capacity_out,
                "storage_storageT_gal": storage_out,
                "recommended_index":    rec_index,
            }
        finally:
            self.max_daily_run_hr = original_max_run_hr
            if was_annual:
                building.set_to_annual_load_shape()

    def plot_sizing_curve(
        self,
        building: Building,
        control_schedule: list[str] | None = None,
        control_map: dict[str, Controls] | None = None,
        load_shift_percent: float = 1.0,
        strat_slope: float = 2.8,
        title: str = "Primary Sizing Curve",
        filepath: str | None = None,
    ) -> "plotly.graph_objects.Figure":
        """
        Return a Plotly figure of the primary sizing curve with an interactive
        slider that moves a diamond marker along the curve.

        **Normal sizing** (no load-shift):

        * X-axis: primary tank volume [gal at storage temperature]
        * Y-axis: heating capacity [kBTU/hr]
        * Slider label: storage volume and run hours per day

        **Load-shift sizing** (control_map contains a ``"shed"`` key):

        * X-axis: load-shift coverage percentile [%]
        * Y-axis: primary tank volume [gal at storage temperature]
        * Slider label: % load-shift days covered and storage volume

        In both cases the recommended point (at ``max_daily_run_hr`` or the
        configured ``load_shift_percent``) is highlighted with a blue diamond
        at page load.

        Parameters
        ----------
        building : Building
        control_schedule : list[str] | None
            Required for load-shift plots; ignored otherwise.
        control_map : dict[str, Controls] | None
            If it contains a ``"shed"`` key the load-shift curve is produced;
            otherwise the normal sizing curve is used.
        load_shift_percent : float
            Configured load-shift coverage percentile (0.25–1.0).  Only used
            when producing the load-shift curve to position the recommended
            marker.  Default 1.0.
        strat_slope : float
            Temperature gradient [°F per %-height].  Default 2.8.
        title : str
            Figure title.  Default ``"Primary Sizing Curve"``.
        filepath : str | None
            If provided, write the figure to this path as a self-contained
            HTML file.  The figure is also returned regardless.

        Returns
        -------
        plotly.graph_objects.Figure

        Raises
        ------
        ImportError
            If ``plotly`` is not installed.
        """
        try:
            import plotly.graph_objects as go
        except ImportError:
            raise ImportError(
                "plotly is required for plot_sizing_curve(). "
                "Install it with: pip install plotly"
            )

        is_ls = self._is_load_shifting(control_map)

        if is_ls:
            curve = self.get_ls_sizing_curve(
                building,
                control_schedule=control_schedule,
                control_map=control_map,
                strat_slope=strat_slope,
                load_shift_percent=load_shift_percent,
            )
            # X = coverage % (multiply fraction by 100 for readability)
            x_vals  = [p * 100.0 for p in curve["load_shift_percent"]]
            y_vals  = curve["storage_storageT_gal"]
            x_label = "Load-Shift Days Covered (%)"
            y_label = "Primary Tank Volume (gal at Storage Temperature)"
            hover   = (
                "Load-shift coverage: <b>%{x:.0f}%</b><br>"
                "Storage: <b>%{y:.1f} gal</b>"
                "<extra></extra>"
            )
            def _slider_label(i: int) -> str:
                return (
                    f"Coverage: <b>{x_vals[i]:.0f}%</b>, "
                    f"Storage: <b>{y_vals[i]:.1f} gal</b>"
                )
        else:
            curve = self.get_sizing_curve(
                building,
                strat_slope=strat_slope,
            )
            x_vals     = curve["storage_storageT_gal"]
            y_vals     = curve["capacity_kbtuh"]
            heat_hours = curve["heat_hours"]
            x_label    = "Primary Tank Volume (gal at Storage Temperature)"
            y_label    = "Heating Capacity (kBTU/hr)"
            hover      = (
                "Storage: <b>%{x:.1f} gal</b><br>"
                "Capacity: <b>%{y:.1f} kBTU/hr</b>"
                "<extra></extra>"
            )
            # The raw curve is ordered high→low storage (high heat hours first).
            # Reverse so that the slider moves left-to-right in the same direction
            # as the diamond moves along the x-axis (low storage → high storage).
            _rec_raw = curve["recommended_index"]
            x_vals     = x_vals[::-1]
            y_vals     = y_vals[::-1]
            heat_hours = heat_hours[::-1]
            rec        = len(x_vals) - 1 - _rec_raw

            def _slider_label(i: int) -> str:
                return (
                    f"Storage: <b>{x_vals[i]:.1f} gal</b>, "
                    f"Capacity: <b>{y_vals[i]:.1f} kBTU/hr</b>, "
                    f"Run hours: <b>{heat_hours[i]:.2f} hr/day</b>"
                )

        if is_ls:
            rec = curve["recommended_index"]
        fig = go.Figure()

        # Trace 0: the full sizing curve (always visible)
        fig.add_trace(go.Scatter(
            x=x_vals, y=y_vals,
            mode="lines",
            line=dict(color="#28a745", width=3),
            hovertemplate=hover,
            showlegend=False,
        ))

        # Traces 1…n: one diamond marker per slider step (hidden by default)
        for i in range(len(x_vals)):
            fig.add_trace(go.Scatter(
                x=[x_vals[i]], y=[y_vals[i]],
                mode="markers",
                marker=dict(symbol="diamond", color="#2EA3F2", size=12),
                hovertemplate=hover,
                showlegend=False,
                visible=(i == rec),   # only the recommended point starts visible
            ))

        # Build slider steps — each reveals one diamond trace
        steps = []
        for i in range(len(x_vals)):
            visibility = [True] + [j == i for j in range(len(x_vals))]
            steps.append(dict(
                label=_slider_label(i),
                method="update",
                args=[{"visible": visibility}],
            ))

        fig.update_layout(
            title=title,
            xaxis_title=x_label,
            yaxis_title=y_label,
            showlegend=False,
            sliders=[dict(
                steps=steps,
                active=rec,
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

        if filepath is not None:
            fig.write_html(filepath)

        return fig

    # ------------------------------------------------------------------
    # Sizing — internal helpers
    # ------------------------------------------------------------------

    def _calc_required_capacity(self, building: Building) -> float:
        """
        Calculate total required heating capacity [kBTU/hr].

        The system must deliver the entire daily DHW load within
        max_daily_run_hr hours. The required generation rate (gallons per
        hour) combined with the temperature rise and heat capacity of water
        gives the minimum kBTU/hr needed.

        Formula
        -------
        capacity = (daily_gal / max_daily_run_hr) * RHO_CP
                   * (supply_temp - design_inlet_temp) / defrost_factor / 1000

        Parameters
        ----------
        building : Building

        Returns
        -------
        float
            Required capacity [kBTU/hr].
        """
        design_inlet_temp_f = self._require_design_inlet_temp(building)
        gen_rate_gph        = building.daily_dhw_use_supplyT_gal / self.max_daily_run_hr
        delta_t             = self.supply_temp_f - design_inlet_temp_f
        return gen_rate_gph * _RHO_CP * delta_t / self.defrost_factor / 1000

    def _calc_running_volume_supplyT_gal(
        self,
        building: Building,
        capacity_kbtuh: float,
    ) -> float:
        """
        Determine the running volume [gallons at supply temperature] — the
        amount of hot storage the system must have available at the start of
        the peak period to avoid running out during the design day.

        The algorithm tiles the 24-hour load shape twice (to handle
        midnight wrap-around), then finds the maximum cumulative deficit
        starting from each hour where demand exceeds generation.

        Parameters
        ----------
        building : Building
        capacity_kbtuh : float
            Required capacity [kBTU/hr] (used by subclasses; the base class
            derives generation rate directly from daily_gal / max_daily_run_hr).

        Returns
        -------
        float
            Running volume [gallons at supply temperature].
        """
        daily_gal  = building.daily_dhw_use_supplyT_gal
        load_shape = building.peak_load_shape  # 24 normalized fractions, sum = 1.0

        # Hourly generation rate: system delivers the full daily demand
        # within max_daily_run_hr hours, spread uniformly.
        gen_rate_gph      = daily_gal / self.max_daily_run_hr
        hourly_demand_gph = daily_gal * load_shape  # [gallons / hour] for each of 24 hours
        hourly_diff_gph   = gen_rate_gph - hourly_demand_gph  # positive = surplus, negative = deficit

        # Tile to two days so cumulative sums wrap around midnight correctly.
        tiled_diff = np.tile(hourly_diff_gph, 2)

        # Deficit accumulation starts at each transition from surplus to deficit.
        peak_indices = _get_peak_indices(hourly_diff_gph)
        if not peak_indices:
            # Generation rate exceeds peak hourly demand — no storage required.
            # This is the physical lower bound for max_daily_run_hr on the sizing curve.
            return 0.0

        running_vol = 0.0
        for idx in peak_indices:
            cum_diff   = np.cumsum(tiled_diff[idx:])
            neg_values = cum_diff[cum_diff < 0]
            if len(neg_values) > 0:
                running_vol = max(running_vol, float(-np.min(neg_values)))

        return running_vol

    def _calc_storage_volume_storageT_gal(
        self,
        running_volume_supplyT_gal: float,
        stratification_factor: float,
    ) -> float:
        """
        Convert running volume [gallons at supply temperature] to required
        physical storage volume [gallons].

        The stratification factor is the fraction of a 100-gallon physical
        tank that can be delivered as supply-temperature water (accounting for
        temperature mixing — hot water above supply mixes with cold inlet water
        to produce more than its physical volume at supply temperature).

        ``tank_size = running_vol / stratification_factor``

        Parameters
        ----------
        running_volume_supplyT_gal : float
            Cumulative deficit [gal at supply temperature].
        stratification_factor : float
            Supply-temperature gallons producible from a 100-gallon tank,
            expressed as a fraction (0–1+), from
            ``_calc_supply_temp_gal_from_100gal_tank() / 100``.

        Returns
        -------
        float
            Required physical storage volume [gallons].
        """
        return running_volume_supplyT_gal / stratification_factor

    def _calc_stratification_factor(
        self,
        control_map: dict[str, Controls] | None,
        strat_slope: float,
        inlet_temp_f: float,
    ) -> float:
        """
        Calculate the stratification factor for the normal operating mode.

        Returns ``_calc_supply_temp_gal_from_100gal_tank() / 100`` for the
        "normal" Controls entry (or a fallback if no controls are provided).
        This fraction directly drives storage volume sizing:

            tank_size = running_vol / stratification_factor

        When ``control_map`` is None or empty, sizing defaults to
        ``on_sensor_fract=0.0`` and ``on_trigger_t_f=supply_temp_f``.

        Parameters
        ----------
        control_map : dict[str, Controls] | None
        strat_slope : float
            Temperature gradient [°F per 1 % of tank height].
        inlet_temp_f : float
            Design cold-water inlet temperature [°F].

        Returns
        -------
        float
            Supply-temperature gallons from a 100-gallon tank, divided by 100.
        """
        if not control_map:
            return self._calc_supply_temp_gal_from_100gal_tank(
                0.0, self.supply_temp_f, strat_slope, inlet_temp_f
            ) / 100.0

        if "normal" in control_map:
            ctrl = control_map["normal"]
            return self._calc_supply_temp_gal_from_100gal_tank(
                ctrl.on_sensor_fract, ctrl.on_trigger_t_f, strat_slope, inlet_temp_f
            ) / 100.0

        # No "normal" key — use the worst-case (smallest factor) across all entries.
        return min(
            self._calc_supply_temp_gal_from_100gal_tank(
                ctrl.on_sensor_fract, ctrl.on_trigger_t_f, strat_slope, inlet_temp_f
            ) / 100.0
            for ctrl in control_map.values()
        )

    def _calc_supply_temp_gal_from_100gal_tank(
        self,
        on_fract: float,
        on_temp_f: float,
        strat_slope: float,
        inlet_temp_f: float,
    ) -> float:
        """
        Compute how many supply-temperature gallons a 100-gallon stratified
        tank can produce, given that the ON sensor reads ``on_temp_f`` at
        fractional height ``on_fract``.

        Hot water above supply temperature is mixed with cold inlet water, so
        1 physical gallon at temperature T produces:

            (T − inlet_temp_f) / (supply_temp_f − inlet_temp_f)

        supply-temperature gallons.

        Temperature profile assumed:
        - Below ``on_fract``: cold, not usable.
        - At ``on_fract``: exactly ``on_temp_f``.
        - Above ``on_fract``: rises linearly at ``strat_slope``
          [°F per 1 % of tank height], capping at ``storage_temp_f``.

        The integration runs from the height where T = ``supply_temp_f`` up
        to the top of the tank (100 %).  For a 100-gallon tank, 1 % = 1 gal.

        Parameters
        ----------
        on_fract : float
            Fractional height of the ON sensor (0 = bottom, 1 = top).
        on_temp_f : float
            Tank temperature at the ON sensor when the element fires [°F].
        strat_slope : float
            Temperature gradient above the sensor [°F per 1 % of tank height].
        inlet_temp_f : float
            Design cold-water inlet temperature [°F].

        Returns
        -------
        float
            Supply-temperature gallons producible from a 100-gallon tank.
        """
        on_pct       = on_fract * 100.0
        supply_delta = self.supply_temp_f - inlet_temp_f

        # Heights (% of tank) where the linear gradient crosses supply / storage.
        # T(h_pct) = on_temp + (h_pct − on_pct) × strat_slope   for h_pct ≥ on_pct
        supply_height_pct  = on_pct + (self.supply_temp_f  - on_temp_f) / strat_slope
        storage_height_pct = min(
            on_pct + (self.storage_temp_f - on_temp_f) / strat_slope,
            100.0,
        )

        # If on_temp ≥ supply_temp, all water above the sensor is already hot;
        # clamp so the full above-sensor zone is included.
        supply_height_pct = max(supply_height_pct, on_pct)

        if supply_height_pct >= 100.0:
            return 0.0   # entire tank is below supply temperature

        # Offsets from on_pct to the zone boundaries.
        s1 = supply_height_pct  - on_pct   # ≥ 0; where T = supply_temp
        s2 = storage_height_pct - on_pct   # where T = storage_temp (or top)

        # Transition zone [supply_height_pct → storage_height_pct]:
        # T(u) = on_temp + u × strat_slope   (u = h_pct − on_pct)
        # supply-gal per physical gal = (T(u) − inlet) / supply_delta
        # Integrate analytically (1 % height = 1 gallon in a 100-gal tank):
        #
        #   ∫ₛ₁ˢ² (a + u·s) / supply_delta du  where a = on_temp − inlet, s = strat_slope
        #       = [a·(s2−s1) + s·(s2²−s1²)/2] / supply_delta
        a = on_temp_f - inlet_temp_f
        transition_supply_gal = (
            a * (s2 - s1) + strat_slope * (s2 ** 2 - s1 ** 2) / 2.0
        ) / supply_delta

        # Fully-hot zone [storage_height_pct → 100 %]:
        # All at storage_temp_f.
        fully_hot_phys_gal   = max(0.0, 100.0 - storage_height_pct)
        fully_hot_supply_gal = fully_hot_phys_gal * (self.storage_temp_f - inlet_temp_f) / supply_delta

        return transition_supply_gal + fully_hot_supply_gal

    def _strat_factor_for_on_params(
        self,
        on_fract: float,
        on_temp_f: float,
        strat_slope: float,
    ) -> float:
        """
        Compute the stratification factor for a single (on_fract, on_temp_f) pair.

        The tank temperature profile is modeled as a linear gradient in the
        transition zone between cold and fully-hot layers. The slope of that
        gradient is strat_slope [°F / %-height].

        Parameters
        ----------
        on_fract : float
            Fractional height of the aquastat ON sensor (0 = bottom, 1 = top).
        on_temp_f : float
            Temperature at the aquastat sensor when the heater turns on [°F].
        strat_slope : float
            Temperature gradient [°F per percentage-point of tank height].

        Returns
        -------
        float
            Stratification factor (0-1). A value of 1.0 means all storage
            above the aquastat is at full storage temperature (ideal).
        """
        on_pct  = on_fract * 100
        delta_t = self.storage_temp_f - self.supply_temp_f

        # Tank height (%) where temperature profile crosses supply and storage setpoints
        supply_height_pct  = on_pct + (self.supply_temp_f  - on_temp_f) / strat_slope
        storage_height_pct = on_pct + (self.storage_temp_f - on_temp_f) / strat_slope
        storage_height_pct = min(storage_height_pct, 100.0)
        # TODO : if storage_height_pct is 100, shouldn't we realculate 
        #   delta_t based off of what temperature is actually at the top

        # Clamp supply_height_pct so the transition zone stays within [on_pct, 100].
        # If on_temp_f >= storage_temp_f the whole tank above the aquastat is fully
        # hot, which gives a factor of 1.0 — the clamp produces that naturally.
        supply_height_pct = max(supply_height_pct, on_pct)
        # TODO: shouldn't supply_height_pct always just be where supply temp percentage height is on the tank?
        #   If there is some water that is supply temp under on_pct, it is still usable water

        # Volume above supply temp = fully-hot zone + trapezoidal transition zone
        vol_fully_hot    = (100 - storage_height_pct) * delta_t
        vol_transition   = (storage_height_pct - supply_height_pct) * delta_t / 2
        # TODO : delta T in the above two lines should, I am pretty sure, be the difference between supply temp (or lowest emp in tank if whole tank is above supply)
        #   and true top of tank temperature
        vol_above_supply = vol_fully_hot + vol_transition

        # Ideal case: all volume above the aquastat is at full storage temp
        ideal_vol = (100 - on_pct) * delta_t
        # TODO : delta_t in this case is actually the difference between storage and supply as this is a perfectly stratified tank

        return vol_above_supply / ideal_vol

    def _strat_pct_of_tank(
        self,
        on_fract: float,
        on_temp_f: float,
        strat_slope: float,
    ) -> float:
        """
        Return the fraction of the *total* tank volume that is at or above
        supply temperature when the ON sensor is at on_fract and reads
        on_temp_f.

        This is the "percent of whole tank" form of the stratification factor:

            strat_pct = strat_factor * (1 - on_fract)

        Used in load-shift sizing where the effective storage band is the
        difference between two aquastat levels expressed as fractions of the
        entire tank volume, not just the volume above one aquastat.

        Parameters
        ----------
        on_fract : float
        on_temp_f : float
        strat_slope : float

        Returns
        -------
        float
        """
        return self._strat_factor_for_on_params(on_fract, on_temp_f, strat_slope) * (1.0 - on_fract)

    @staticmethod
    def _is_load_shifting(control_map: dict[str, Controls] | None) -> bool:
        """Return True if the control_map has a ``"shed"`` key."""
        return bool(control_map) and "shed" in control_map

    @staticmethod
    def _get_first_shed_block_and_load_up_hours(
        control_schedule: list[str],
    ) -> tuple[list[int], int]:
        """
        Find the first consecutive block of ``"shed"`` hours in the schedule
        and count the ``"loadUp"`` hours immediately preceding it.

        Parameters
        ----------
        control_schedule : list[str]
            24-element list of control keys.

        Returns
        -------
        first_shed_block : list[int]
            Hour indices (0-23) of the first consecutive ``"shed"`` run.
        load_up_hours : int
            Number of consecutive ``"loadUp"`` hours directly before the
            first shed block. 0 if no load-up hours are configured.
        """
        shed_indices = [h for h in range(24) if control_schedule[h] == "shed"]
        if not shed_indices:
            return [], 0

        # Build first consecutive shed block
        first_shed_block = [shed_indices[0]]
        for h in shed_indices[1:]:
            if h == first_shed_block[-1] + 1:
                first_shed_block.append(h)
            else:
                break

        # Count consecutive "loadUp" hours immediately before the first shed
        load_up_hours = 0
        h = first_shed_block[0] - 1
        while h >= 0 and control_schedule[h] == "loadUp":
            load_up_hours += 1
            h -= 1

        return first_shed_block, load_up_hours

    def _calc_prelim_vols_supplyT_gal(
        self,
        control_schedule: list[str],
        building: Building,
        fract_total_vol: float = 1.0,
    ) -> tuple[float, float]:
        """
        Calculate volumes consumed during the first shed block and the
        preceding load-up period.

        Parameters
        ----------
        control_schedule : list[str]
        building : Building
        fract_total_vol : float
            Demand scaling factor from load_shift_percent. Applied to vshift
            (the volume needed to carry through the first shed) to match the
            original's _calcPrelimVol behavior. Default 1.0 (no scaling).

        Returns
        -------
        vshift_supplyT_gal : float
            Volume [gal at supplyT] consumed during the first shed block,
            scaled by fract_total_vol.
        vconsumed_lu_supplyT_gal : float
            Volume [gal at supplyT] consumed during the load-up hours.
            The heater must both fill Vload AND offset this demand.
        """
        first_shed_block, load_up_hours = self._get_first_shed_block_and_load_up_hours(control_schedule)

        load_shape_gph = building.avg_load_shape * building.daily_dhw_use_supplyT_gal

        vshift_supplyT_gal       = float(sum(load_shape_gph[h] for h in first_shed_block)) * fract_total_vol
        lu_start                 = first_shed_block[0] - load_up_hours
        vconsumed_lu_supplyT_gal = float(sum(load_shape_gph[h] for h in range(lu_start, first_shed_block[0])))

        return vshift_supplyT_gal, vconsumed_lu_supplyT_gal

    def _calc_gen_rate_ls_gph(
        self,
        control_schedule: list[str],
        control_map: dict[str, Controls],
        building: Building,
        strat_slope: float,
        fract_total_vol: float = 1.0,
    ) -> float:
        """
        Calculate the load-shift generation rate [gal/hr at supplyT].

        The LS generation rate is the maximum of:

        * Normal gen rate: ``daily_gal / max_daily_run_hr``
        * Load-up gen rate: rate needed to fill the load-up portion of the
          tank AND offset demand during the load-up hours.

        When no ``"loadUp"`` key is in the map or ``load_up_hours == 0``,
        returns the normal gen rate.

        Parameters
        ----------
        control_schedule : list[str]
        control_map : dict[str, Controls]
        building : Building
        strat_slope : float
        fract_total_vol : float
            Demand scaling factor from load_shift_percent. Passed through to
            _calc_prelim_vols_supplyT_gal. Default 1.0 (no scaling).

        Returns
        -------
        float
            Generation rate [gal/hr at supplyT].
        """
        daily_gal           = building.daily_dhw_use_supplyT_gal
        normal_gen_rate_gph = daily_gal / self.max_daily_run_hr

        _, load_up_hours = self._get_first_shed_block_and_load_up_hours(control_schedule)
        if load_up_hours == 0:
            return normal_gen_rate_gph

        vshift_supplyT_gal, vconsumed_lu_supplyT_gal = self._calc_prelim_vols_supplyT_gal(
            control_schedule, building, fract_total_vol
        )

        normal_ctrl = control_map["normal"]
        lu_ctrl     = control_map.get("loadUp", normal_ctrl)
        shed_ctrl   = control_map["shed"]

        normal_strat_pct = self._strat_pct_of_tank(
            normal_ctrl.on_sensor_fract, normal_ctrl.on_trigger_t_f, strat_slope
        )
        lu_strat_pct = self._strat_pct_of_tank(
            lu_ctrl.on_sensor_fract, lu_ctrl.on_trigger_t_f, strat_slope
        )
        shed_strat_pct = self._strat_pct_of_tank(
            shed_ctrl.on_sensor_fract, shed_ctrl.on_trigger_t_f, strat_slope
        )

        ls_band = lu_strat_pct - shed_strat_pct
        if ls_band <= 0:
            return normal_gen_rate_gph

        # Volume in the load-up zone (between normal and load-up aquastats)
        vload_supplyT_gal = vshift_supplyT_gal * (lu_strat_pct - normal_strat_pct) / ls_band

        lu_gen_rate_gph = (vload_supplyT_gal + vconsumed_lu_supplyT_gal) / load_up_hours

        return max(normal_gen_rate_gph, lu_gen_rate_gph)

    def _calc_required_capacity_ls_kbtuh(
        self,
        control_schedule: list[str],
        control_map: dict[str, Controls],
        building: Building,
        strat_slope: float,
        fract_total_vol: float = 1.0,
    ) -> float:
        """
        Calculate required heating capacity [kBTU/hr] for load-shift sizing.

        Converts the load-shift generation rate (max of normal and load-up
        rates) to a heating capacity via the standard formula.

        Parameters
        ----------
        control_schedule : list[str]
        control_map : dict[str, Controls]
        building : Building
        strat_slope : float
        fract_total_vol : float
            Demand scaling factor from load_shift_percent. Passed through to
            _calc_gen_rate_ls_gph. Default 1.0 (no scaling).

        Returns
        -------
        float
            Required heating capacity [kBTU/hr].
        """
        design_inlet_temp_f = self._require_design_inlet_temp(building)
        gen_rate_ls_gph     = self._calc_gen_rate_ls_gph(
            control_schedule, control_map, building, strat_slope, fract_total_vol
        )
        delta_t = self.supply_temp_f - design_inlet_temp_f
        return gen_rate_ls_gph * _RHO_CP * delta_t / self.defrost_factor / 1000

    def _calc_running_volume_ls_supplyT_gal(
        self,
        control_schedule: list[str],
        building: Building,
        gen_rate_ls_gph: float,
        fract_total_vol: float = 1.0,
    ) -> float:
        """
        Calculate the load-shift running volume [gal at supplyT].

        The tank is modeled as "empty" (only Vshift above the shed aquastat)
        at the moment the first shed ends. From that point forward the
        cumulative deficit between generation and demand gives the additional
        volume needed above Vshift.

        Parameters
        ----------
        control_schedule : list[str]
        building : Building
        gen_rate_ls_gph : float
            Load-shift generation rate [gal/hr at supplyT], from
            _calc_gen_rate_ls_gph.
        fract_total_vol : float
            Demand scaling factor from load_shift_percent (0–1). Scales the
            daily demand profile so the system is sized for the given percentile
            of days rather than the absolute peak. Default 1.0 (no scaling).

        Returns
        -------
        float
            Load-shift running volume [gal at supplyT].
        """
        first_shed_block, _ = self._get_first_shed_block_and_load_up_hours(control_schedule)
        vshift_supplyT_gal, _ = self._calc_prelim_vols_supplyT_gal(
            control_schedule, building, fract_total_vol
        )

        load_shape = building.avg_load_shape
        daily_gal  = building.daily_dhw_use_supplyT_gal

        # 24-hr generation profile: gen_rate_ls during non-shed hours, 0 during shed
        gen_profile_gph    = np.array([
            0.0 if control_schedule[h] == "shed" else gen_rate_ls_gph
            for h in range(24)
        ])
        demand_profile_gph = daily_gal * load_shape
        diff_gph           = gen_profile_gph - demand_profile_gph

        # Accumulate deficit starting from the first hour after the shed ends.
        # The tank is "empty" at that point — it holds only Vshift above shedT.
        shed_end_idx = first_shed_block[-1] + 1
        tiled_diff   = np.tile(diff_gph, 2)
        cum_diff     = np.cumsum(tiled_diff[shed_end_idx:])
        neg_values   = cum_diff[cum_diff < 0]
        ls_deficit_supplyT_gal = float(-np.min(neg_values)) if len(neg_values) > 0 else 0.0

        # Post-multiply the deficit by fract_total_vol to match the original's behavior:
        # the sizing is against unscaled demand but the deficit is scaled back down.
        ls_deficit_supplyT_gal *= fract_total_vol

        return ls_deficit_supplyT_gal + vshift_supplyT_gal

    def _calc_storage_volume_ls_storageT_gal(
        self,
        ls_running_vol_supplyT_gal: float,
        control_map: dict[str, Controls],
        strat_slope: float,
        inlet_temp_f: float,
    ) -> float:
        """
        Convert the load-shift running volume [gal at supplyT] to required
        physical storage [gallons].

        The effective stratification denominator for load-shift sizing is the
        difference in supply-temperature capacity between the load-up and shed
        aquastat positions (both expressed as fractions of a 100-gallon tank).

        Parameters
        ----------
        ls_running_vol_supplyT_gal : float
        control_map : dict[str, Controls]
        strat_slope : float
        inlet_temp_f : float
            Design cold-water inlet temperature [°F].

        Returns
        -------
        float
            Required physical storage volume [gallons].
        """
        normal_ctrl = control_map["normal"]
        lu_ctrl     = control_map.get("loadUp", normal_ctrl)
        shed_ctrl   = control_map["shed"]

        lu_x   = self._calc_supply_temp_gal_from_100gal_tank(
            lu_ctrl.on_sensor_fract,   lu_ctrl.on_trigger_t_f,   strat_slope, inlet_temp_f
        )
        shed_x = self._calc_supply_temp_gal_from_100gal_tank(
            shed_ctrl.on_sensor_fract, shed_ctrl.on_trigger_t_f, strat_slope, inlet_temp_f
        )
        ls_band = (lu_x - shed_x) / 100.0

        return self._calc_storage_volume_storageT_gal(
            ls_running_vol_supplyT_gal, ls_band
        )

    def _require_design_inlet_temp(self, building: Building) -> float:
        """
        Return the design inlet water temperature, raising a clear error if
        it is unavailable (i.e. no ClimateZone was set on the building).
        """
        temp = building.get_design_inlet_water_temp_f()
        if temp is None:
            raise ValueError(
                "Sizing requires a design inlet water temperature. "
                "Provide a ClimateZone (via zip code, weather station, zone ID, "
                "or design_inlet_water_temp_f) when constructing the Building."
            )
        return temp

    # Minimum heater cycle time below which short cycling is flagged [minutes].
    _MIN_CYCLE_MIN: float = 10.0

    def _warn_if_short_cycling(
        self,
        control_map: dict[str, Controls],
        capacity_kbtuh: float,
        storage_vol_storageT_gal: float,
    ) -> None:
        """
        Emit a UserWarning for any Controls in the map that would cause short
        cycling or have backwards sensor positions.

        Each Controls in control_map is checked independently. Short cycling
        occurs when the deadband volume (between ON and OFF sensors) is small
        relative to the heater's output rate.

        Estimated cycle time per Controls:

            deadband_vol = (on_fract - off_fract) * storage_vol
            heat_rate_gph = capacity_kbtuh * 1000 / (RHO_CP * (storage_T - supply_T))
            cycle_time = deadband_vol / heat_rate_gph   [hours]

        Parameters
        ----------
        control_map : dict[str, Controls]
        capacity_kbtuh : float
            Minimum required heating capacity [kBTU/hr] from sizing.
        storage_vol_storageT_gal : float
            Minimum required storage volume [gallons] from sizing.
        """
        delta_t_storage = self.storage_temp_f - self.supply_temp_f
        if delta_t_storage <= 0:
            return  # degenerate temperatures — skip check

        heat_rate_gph = capacity_kbtuh * 1000 / (_RHO_CP * delta_t_storage)

        for key, ctrl in control_map.items():
            if ctrl.off_sensor_fract > ctrl.on_sensor_fract:
                warnings.warn(
                    f"Controls key {key}: off_sensor_fract ({ctrl.off_sensor_fract}) "
                    f"is above on_sensor_fract ({ctrl.on_sensor_fract}). "
                    f"Expected off <= on — the heater may never shut off.",
                    UserWarning,
                    stacklevel=4,
                )
                continue

            deadband_vol_gal = (ctrl.on_sensor_fract - ctrl.off_sensor_fract) * storage_vol_storageT_gal
            cycle_time_min   = (deadband_vol_gal / heat_rate_gph) * 60
            if cycle_time_min < self._MIN_CYCLE_MIN:
                warnings.warn(
                    f"Controls key {key}: short cycling risk — estimated cycle time is "
                    f"{cycle_time_min:.1f} min (minimum recommended: {self._MIN_CYCLE_MIN} min). "
                    f"Consider increasing storage volume or widening the sensor deadband "
                    f"(on_sensor_fract={ctrl.on_sensor_fract}, off_sensor_fract={ctrl.off_sensor_fract}).",
                    UserWarning,
                    stacklevel=4,
                )

    # ------------------------------------------------------------------
    # Simulation step (stubs — implemented in subclasses)
    # ------------------------------------------------------------------

    def simulate_step(
        self,
        building: Building,
        timestep_interval: int,
        interval_min: int = 1,
        mode: str = "normal",
    ) -> dict:
        """
        Execute one simulation timestep: query controls, apply heating,
        draw DHW from tank. Returns per-step metrics.

        Order of operations
        -------------------
        1. Query Building for demand, OAT, and inlet water temperature.
        2. Determine outlet_temp_f for the current hour from active Controls.
        3. Update each WaterHeater's on/off state via its Controls.
        4. Sum heating output from all active heaters; apply to storage tank.
        5. Draw DHW from tank to meet demand.
        6. Return per-step metrics dict.

        Parameters
        ----------
        building : Building
        timestep_interval : int
            Current simulation interval index from the start of the simulation.
        interval_min : int
            Length of each interval in minutes.
        mode : str
            Ignored — operating mode is determined automatically by each
            WaterHeater's control_schedule for the current hour.

        Returns
        -------
        dict
            Keys: 'demand_supplyT_gal', 'usable_volume_supplyT_gal',
            'heater_output_kbtuh', 'heater_power_in_kw', 'oat_f',
            'inlet_water_temp_f', 'tank_temps_f'.
        """
        use_avg = any(wh.is_load_shifting() for wh in self.water_heaters)
        demand_supplyT_gal = building.get_dhw_load_supplyT_gal(
            timestep_interval, interval_min, use_avg=use_avg
        )
        # NOTE: The original EcosizerEngine scaled hwDemand by fract_total_vol
        # (derived from load_shift_percent) in the simulation as well as sizing.
        # This codebase intentionally does NOT do that. Sizing is scaled so the
        # system is optimally sized for the target percentile of days, but the
        # simulation always runs against the full unscaled average daily demand.
        # The practical consequence: a system sized with load_shift_percent < 1.0
        # may show the primary heater firing during shed on some simulated days,
        # which is the expected and honest behavior for a design that accepts
        # occasional shed violations in exchange for a smaller tank.
        oat_f          = building.get_oat_f(timestep_interval, interval_min)
        inlet_temp_f   = building.get_inlet_water_temp_f(timestep_interval, interval_min)
        hour_of_day    = (timestep_interval * interval_min // 60) % 24
        outlet_temp_f  = self._get_outlet_temp_f(hour_of_day)
        mode = (
            self.water_heaters[0].control_schedule[hour_of_day]
            if self.water_heaters and self.water_heaters[0].control_schedule
            else "normal"
        )

        if self.storage_tank is not None:
            # Update on/off state for each heater based on current tank condition
            for wh in self.water_heaters:
                wh.update_state(self.storage_tank, hour_of_day)

            # Apply heating from all active heaters to the tank
            top_temp_f     = self.storage_tank.get_temperature_at_fraction(1.0)
            total_kbtuh    = sum(
                wh.get_output_kbtuh(oat_f, top_temp_f)
                for wh in self.water_heaters
            )
            total_kw: float | None = None
            active_kws = [
                wh.get_power_in_kw(oat_f, top_temp_f)
                for wh in self.water_heaters
                if wh.is_active()
            ]
            if any(kw is not None for kw in active_kws):
                total_kw = sum(kw or 0.0 for kw in active_kws)

            self.storage_tank.heat(total_kbtuh, interval_min, outlet_temp_f)

            # Draw hot water from tank to meet demand
            self.storage_tank.draw(
                demand_supplyT_gal, inlet_temp_f, self.supply_temp_f, outlet_temp_f
            )

            usable_vol_gal = self.storage_tank.get_usable_volume_supplyT_gal(
                self.supply_temp_f
            )
            tank_temps_f = [
                self.storage_tank.get_temperature_at_fraction(f)
                for f in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
            ]
        else:
            total_kbtuh    = 0.0
            total_kw       = None
            usable_vol_gal = 0.0
            tank_temps_f   = [0.0] * 6

        return {
            "demand_supplyT_gal":        demand_supplyT_gal,
            "usable_volume_supplyT_gal": usable_vol_gal,
            "heater_output_kbtuh":       total_kbtuh,
            "heater_power_in_kw":        total_kw,
            "oat_f":                     oat_f,
            "inlet_water_temp_f":        inlet_temp_f,
            "tank_temps_f":              tank_temps_f,
            "mode":                      mode,
        }

    def _get_outlet_temp_f(self, hour_of_day: int) -> float:
        """
        Return the maximum outlet temperature among all water heaters' active
        Controls for the given hour. Falls back to storage_temp_f if no
        Controls are configured.

        Parameters
        ----------
        hour_of_day : int
            Hour of the day (0-23).

        Returns
        -------
        float
        """
        outlet_temps = [
            wh.get_controls_for_hour(hour_of_day).outlet_temp_f
            for wh in self.water_heaters
            if wh.get_controls_for_hour(hour_of_day) is not None
        ]
        return max(outlet_temps) if outlet_temps else self.storage_temp_f

    def check_for_outage(self, demand_supplyT_gal: float) -> bool:
        """
        Return True if the storage tank cannot meet the given demand.

        Checks whether usable volume at supply temperature has reached zero.

        Parameters
        ----------
        demand_supplyT_gal : float
            Hot water demand at supply temperature [gallons].

        Returns
        -------
        bool
        """
        if self.storage_tank is None:
            return False
        return self.storage_tank.get_usable_volume_supplyT_gal(self.supply_temp_f) <= 0.0
