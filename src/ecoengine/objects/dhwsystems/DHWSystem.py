from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING

from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.heating.PerformanceMap import NominalPerformanceMap
from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.storage.StorageTank import StorageTank

if TYPE_CHECKING:
    from ecoengine.objects.building.Building import Building

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------

# Volumetric heat capacity of water [BTU / (gallon * °F)]
_RHO_CP: float = 8.353535

# Stratification model: temperature gradient in the transition zone of the
# tank [°F per percentage-point of tank height]. Calibrated empirically.
_STRAT_SLOPE: float = 2.8


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
        max_daily_run_hr: float = 24.0,
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
            Maximum hours the heating system may run per day (1–24). Used to
            calculate the required generation rate during sizing.
        defrost_factor : float
            Fraction of rated capacity available after accounting for defrost
            cycles (0–1). Typically 1.0 for non-frosting conditions.
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
        controls: Controls | None = None,
    ) -> DHWSystem:
        """
        Size the system for the given building, then build it.

        Runs the sizing algorithm to determine the minimum required heating
        capacity and storage volume. Creates one WaterHeater backed by a
        NominalPerformanceMap (constant-output placeholder) holding all of the
        required capacity, and a StorageTank sized to the minimum required volume.

        The Controls object serves double duty: its on-sensor parameters
        (on_sensor_fract, on_trigger_t_f) drive the stratification factor
        calculation during sizing, and the same Controls instance is assigned
        to the created WaterHeater for use at simulation time.

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
            Fraction of rated capacity available after defrost (0–1).
        controls : Controls | None
            Control setpoints for the heater. The on-sensor position and
            trigger temperature are used during sizing to compute the
            stratification factor. If None, defaults of on_sensor_fract=0.0
            and on_trigger_t_f=supply_temp_f are assumed.

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
        system.size(building, controls=controls)

        system.storage_tank  = StorageTank(
            total_volume_gal=system._minimum_storage_storageT_gal
        )
        system.water_heaters = [WaterHeater(
            performance_map=NominalPerformanceMap(system._minimum_capacity_kbtuh),
            controls=controls,
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
            Fraction of rated capacity available after defrost (0–1).

        Returns
        -------
        DHWSystem
        """
        return cls(
            water_heaters=water_heaters,
            storage_tank=StorageTank(total_volume_gal=storage_volume_storageT_gal),
            supply_temp_f=supply_temp_f,
            storage_temp_f=storage_temp_f,
            max_daily_run_hr=max_daily_run_hr,
            defrost_factor=defrost_factor,
        )

    # ------------------------------------------------------------------
    # Sizing — public interface
    # ------------------------------------------------------------------

    def size(self, building: Building, controls: Controls | None = None) -> None:
        """
        Compute the minimum heating capacity and storage volume for this
        system in the given building. Stores results internally; retrieve
        them with get_minimum_capacity_kbtuh() and
        get_minimum_storage_storageT_gal().

        Sizing is always performed on the 24-hour daily load shape. If the
        building is currently set to the annual shape, this method
        temporarily switches it back, sizes, then restores the annual shape.

        Parameters
        ----------
        building : Building
        controls : Controls | None
            Controls whose on-sensor parameters (on_sensor_fract,
            on_trigger_t_f) determine the stratification factor. If None,
            defaults of on_sensor_fract=0.0 and on_trigger_t_f=supply_temp_f
            are used.

        Raises
        ------
        ValueError
            If the building has no design inlet water temperature available
            (no ClimateZone was provided at construction).
        """
        on_fract  = controls.on_sensor_fract if controls is not None else 0.0
        on_temp_f = controls.on_trigger_t_f  if controls is not None else self.supply_temp_f

        was_annual = building.is_annual_load_shape()
        if was_annual:
            building.set_to_daily_load_shape()

        capacity_kbtuh       = self._calc_required_capacity(building)
        running_vol_supplyT  = self._calc_running_volume_supplyT_gal(building, capacity_kbtuh)
        strat_factor         = self._calc_stratification_factor(on_fract, on_temp_f)
        storage_vol_storageT = self._calc_storage_volume_storageT_gal(
            running_vol_supplyT, strat_factor, building.get_design_inlet_water_temp_f()
        )

        self._minimum_capacity_kbtuh       = capacity_kbtuh
        self._minimum_storage_storageT_gal = storage_vol_storageT

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
        on_fract: float,
        on_temp_f: float,
    ) -> float:
        """
        Calculate the stratification factor: the fraction of the volume
        above the aquastat that contains water at or above supply temperature.

        The tank temperature profile is modeled as a linear gradient in the
        transition zone between cold and fully-hot layers. The slope of that
        gradient is _STRAT_SLOPE [°F / %-height].

        Parameters
        ----------
        on_fract : float
            Fractional height of the aquastat ON sensor (0 = bottom, 1 = top).
            Taken from Controls.on_sensor_fract.
        on_temp_f : float
            Temperature at the aquastat sensor when the heater turns on [°F].
            Taken from Controls.on_trigger_t_f.

        Returns
        -------
        float
            Stratification factor (0–1). A value of 1.0 means all storage
            above the aquastat is at full storage temperature (ideal).
        """
        on_pct  = on_fract * 100
        delta_t = self.storage_temp_f - self.supply_temp_f

        # Tank height (%) where temperature profile crosses supply and storage setpoints
        supply_height_pct  = on_pct + (self.supply_temp_f  - on_temp_f) / _STRAT_SLOPE
        storage_height_pct = on_pct + (self.storage_temp_f - on_temp_f) / _STRAT_SLOPE
        storage_height_pct = min(storage_height_pct, 100.0)

        # Clamp supply_height_pct so the transition zone stays within [on_pct, 100].
        # If on_temp_f >= storage_temp_f the whole tank above the aquastat is fully
        # hot, which gives a factor of 1.0 — the clamp produces that naturally.
        supply_height_pct = max(supply_height_pct, on_pct)

        # Volume above supply temp = fully-hot zone + trapezoidal transition zone
        vol_fully_hot  = (100 - storage_height_pct) * delta_t
        vol_transition = (storage_height_pct - supply_height_pct) * delta_t / 2
        vol_above_supply = vol_fully_hot + vol_transition

        # Ideal case: all volume above the aquastat is at full storage temp
        ideal_vol = (100 - on_pct) * delta_t

        return vol_above_supply / ideal_vol

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
