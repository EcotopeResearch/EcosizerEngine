from __future__ import annotations

import warnings
import numpy as np
from typing import TYPE_CHECKING

from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.storage.StorageTank import StorageTank

if TYPE_CHECKING:
    from ecoengine.objects.building.Building import Building

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------

# Volumetric heat capacity of water [BTU / (gallon * °F)]
_RHO_CP: float = 8.353535


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
        system.size(building, control_schedule=control_schedule, control_map=control_map, strat_slope=strat_slope)

        system.storage_tank  = StorageTank(
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
            storage_tank=StorageTank(
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
            strat_factor             = self._calc_stratification_factor(control_map, strat_slope)
            storage_vol_storageT_gal = self._calc_storage_volume_storageT_gal(
                running_vol_supplyT_gal, strat_factor, design_inlet_temp_f
            )

            if control_schedule and self._is_load_shifting(control_map):
                ls_capacity_kbtuh = self._calc_required_capacity_ls_kbtuh(
                    control_schedule, control_map, building, strat_slope
                )
                gen_rate_ls_gph = self._calc_gen_rate_ls_gph(
                    control_schedule, control_map, building, strat_slope
                )
                ls_running_vol_supplyT_gal = self._calc_running_volume_ls_supplyT_gal(
                    control_schedule, building, gen_rate_ls_gph
                )
                ls_storage_vol_storageT_gal = self._calc_storage_volume_ls_storageT_gal(
                    ls_running_vol_supplyT_gal, control_map, design_inlet_temp_f, strat_slope
                )
                capacity_kbtuh           = max(capacity_kbtuh, ls_capacity_kbtuh)
                storage_vol_storageT_gal = max(storage_vol_storageT_gal, ls_storage_vol_storageT_gal)

            self._minimum_capacity_kbtuh       = capacity_kbtuh
            self._minimum_storage_storageT_gal = storage_vol_storageT_gal

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

    def get_sizing_curve(self) -> list[tuple[float, float]]:
        """
        Return the Primary Sizing Curve — pairs of (capacity_kbtuh, storage_storageT_gal)
        representing the capacity-vs-storage tradeoff across different run-hour assumptions.

        Returns
        -------
        list[tuple[float, float]]
        """
        pass

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
            print("Warning: The HPWH capacity has been sized greater than the largest peak in the building's load. This system will function as an instantaneous water heater.")
            print("Please use a more 'peaky' load shape or raise the number of hours in a day the HPWH should run.")
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
        design_inlet_temp_f: float,
    ) -> float:
        """
        Convert running volume [gallons at supply temperature] to required
        physical storage volume [gallons at storage temperature].

        Two adjustments are applied:

        1. **Temperature conversion** — storage is hotter than supply, so
           fewer gallons of stored water hold the same thermal energy:
           ``vol_storageT = vol_supplyT * (supply - inlet) / (storage - inlet)``

        2. **Stratification factor** — the tank is not perfectly stratified;
           only a fraction of the volume above the aquastat is usable at or
           above supply temperature.  The volume is divided by this fraction
           to find the required physical tank size.

        Parameters
        ----------
        running_volume_supplyT_gal : float
        stratification_factor : float
        design_inlet_temp_f : float
            Design cold-water inlet temperature [°F].

        Returns
        -------
        float
            Required storage volume [gallons at storage temperature].
        """
        # Step 1 — temperature-equivalent volume at storage temperature
        temp_ratio       = ((self.supply_temp_f  - design_inlet_temp_f) /
                            (self.storage_temp_f - design_inlet_temp_f))
        vol_at_storageT  = running_volume_supplyT_gal * temp_ratio

        # Step 2 — account for imperfect stratification
        return vol_at_storageT / stratification_factor

    def _calc_stratification_factor(
        self,
        control_map: dict[str, Controls] | None,
        strat_slope: float,
    ) -> float:
        """
        Calculate the worst-case stratification factor across all Controls in
        the control_map.

        Each Controls object produces a stratification factor based on its
        on_sensor_fract and on_trigger_t_f. For conservative sizing the
        minimum factor (least favorable stratification) is returned, since a
        lower factor requires a larger storage volume.

        When control_map is None or empty, sizing defaults of
        on_sensor_fract=0.0 and on_trigger_t_f=supply_temp_f are used.

        Parameters
        ----------
        control_map : dict[str, Controls] | None
            All Controls objects that may be active during operation.
        strat_slope : float
            Temperature gradient [°F per percentage-point of tank height].
            Taken from StorageTank.strat_slope.

        Returns
        -------
        float
            Effective tank fraction (0-1) for the normal operating mode.
            This is the "percent of whole tank" form:
            ``strat_factor * (1 - on_fract)``, matching the original sizing
            formula which divides running volume by the fraction of the *total*
            tank volume that is usable at or above supply temperature.
        """
        if not control_map:
            return self._strat_pct_of_tank(0.0, self.supply_temp_f, strat_slope)

        # Normal sizing uses the "normal" aquastat position only.
        # "loadUp" and "shed" aquastats are handled exclusively in the LS path.
        # For maps without a "normal" key (custom non-standard configs), fall
        # back to worst-case across all entries.
        if "normal" in control_map:
            ctrl = control_map["normal"]
            return self._strat_pct_of_tank(ctrl.on_sensor_fract, ctrl.on_trigger_t_f, strat_slope)

        return min(
            self._strat_pct_of_tank(
                ctrl.on_sensor_fract, ctrl.on_trigger_t_f, strat_slope
            )
            for ctrl in control_map.values()
        )

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

        # Clamp supply_height_pct so the transition zone stays within [on_pct, 100].
        # If on_temp_f >= storage_temp_f the whole tank above the aquastat is fully
        # hot, which gives a factor of 1.0 — the clamp produces that naturally.
        supply_height_pct = max(supply_height_pct, on_pct)

        # Volume above supply temp = fully-hot zone + trapezoidal transition zone
        vol_fully_hot    = (100 - storage_height_pct) * delta_t
        vol_transition   = (storage_height_pct - supply_height_pct) * delta_t / 2
        vol_above_supply = vol_fully_hot + vol_transition

        # Ideal case: all volume above the aquastat is at full storage temp
        ideal_vol = (100 - on_pct) * delta_t

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
    ) -> tuple[float, float]:
        """
        Calculate volumes consumed during the first shed block and the
        preceding load-up period.

        Parameters
        ----------
        control_schedule : list[str]
        building : Building

        Returns
        -------
        vshift_supplyT_gal : float
            Volume [gal at supplyT] consumed during the first shed block.
            Must be stored above the shed aquastat before entering shed.
        vconsumed_lu_supplyT_gal : float
            Volume [gal at supplyT] consumed during the load-up hours.
            The heater must both fill Vload AND offset this demand.
        """
        first_shed_block, load_up_hours = self._get_first_shed_block_and_load_up_hours(control_schedule)

        load_shape_gph = building.avg_load_shape * building.daily_dhw_use_supplyT_gal

        vshift_supplyT_gal       = float(sum(load_shape_gph[h] for h in first_shed_block))
        lu_start                 = first_shed_block[0] - load_up_hours
        vconsumed_lu_supplyT_gal = float(sum(load_shape_gph[h] for h in range(lu_start, first_shed_block[0])))

        return vshift_supplyT_gal, vconsumed_lu_supplyT_gal

    def _calc_gen_rate_ls_gph(
        self,
        control_schedule: list[str],
        control_map: dict[str, Controls],
        building: Building,
        strat_slope: float,
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
            control_schedule, building
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

        Returns
        -------
        float
            Required heating capacity [kBTU/hr].
        """
        design_inlet_temp_f = self._require_design_inlet_temp(building)
        gen_rate_ls_gph     = self._calc_gen_rate_ls_gph(
            control_schedule, control_map, building, strat_slope
        )
        delta_t = self.supply_temp_f - design_inlet_temp_f
        return gen_rate_ls_gph * _RHO_CP * delta_t / self.defrost_factor / 1000

    def _calc_running_volume_ls_supplyT_gal(
        self,
        control_schedule: list[str],
        building: Building,
        gen_rate_ls_gph: float,
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

        Returns
        -------
        float
            Load-shift running volume [gal at supplyT].
        """
        first_shed_block, _ = self._get_first_shed_block_and_load_up_hours(control_schedule)
        vshift_supplyT_gal, _ = self._calc_prelim_vols_supplyT_gal(control_schedule, building)

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

        return ls_deficit_supplyT_gal + vshift_supplyT_gal

    def _calc_storage_volume_ls_storageT_gal(
        self,
        ls_running_vol_supplyT_gal: float,
        control_map: dict[str, Controls],
        design_inlet_temp_f: float,
        strat_slope: float,
    ) -> float:
        """
        Convert the load-shift running volume [gal at supplyT] to required
        physical storage [gal at storageT].

        The effective stratification denominator for load-shift sizing is the
        band between the load-up and shed aquastat levels expressed as
        fractions of the total tank (``lu_strat_pct - shed_strat_pct``).
        This replaces the single strat factor used in normal sizing.

        Parameters
        ----------
        ls_running_vol_supplyT_gal : float
        control_map : dict[str, Controls]
        design_inlet_temp_f : float
        strat_slope : float

        Returns
        -------
        float
            Required storage volume [gal at storageT].
        """
        normal_ctrl = control_map["normal"]
        lu_ctrl     = control_map.get("loadUp", normal_ctrl)
        shed_ctrl   = control_map["shed"]

        lu_strat_pct   = self._strat_pct_of_tank(
            lu_ctrl.on_sensor_fract,   lu_ctrl.on_trigger_t_f,   strat_slope
        )
        shed_strat_pct = self._strat_pct_of_tank(
            shed_ctrl.on_sensor_fract, shed_ctrl.on_trigger_t_f, strat_slope
        )
        ls_band = lu_strat_pct - shed_strat_pct

        return self._calc_storage_volume_storageT_gal(
            ls_running_vol_supplyT_gal, ls_band, design_inlet_temp_f
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

        Parameters
        ----------
        building : Building
        timestep_interval : int
            Current simulation interval index from the start of the simulation.
        interval_min : int
            Length of each interval in minutes.
        mode : str
            Operating mode: 'normal', 'load_up', or 'shed'.

        Returns
        -------
        dict
            Per-timestep metrics (demand, usable volume, heater output, power).
        """
        pass

    def check_for_outage(self, demand_supplyT_gal: float) -> bool:
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
