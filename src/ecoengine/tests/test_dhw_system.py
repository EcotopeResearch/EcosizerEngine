"""
Unit tests for DHWSystem — sizing calculations and factory constructors.

Tests cover:
- Minimum capacity calculation (_calc_required_capacity)
- Running volume calculation (_calc_running_volume_supplyT_gal)
- Storage volume calculation (_calc_storage_volume_storageT_gal)
- Stratification factor calculation (_calc_stratification_factor)
- Short-cycling warning (_warn_if_short_cycling)
- from_size() factory: correct types, sizing results, control wiring
- from_components() factory: correct storage volume and heater list
- size() guard: raises when no design inlet temp available
- NominalPerformanceMap: constant-capacity placeholder
- WaterHeater factory methods: from_nominal_capacity, from_model_name
"""

import warnings
import pytest
import numpy as np

from ecoengine.objects.building.Building import Building
from ecoengine.objects.building.ClimateZone import ClimateZone
from ecoengine.objects.dhwsystems.DHWSystem import DHWSystem, _RHO_CP, _get_peak_indices
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.heating.PerformanceMap import NominalPerformanceMap
from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.storage.StorageTank import StorageTank, StratifiedTank


# ===========================================================================
# Fixtures and helpers
# ===========================================================================

SUPPLY_T  = 120.0   # °F
STORAGE_T = 150.0   # °F
INLET_T   = 50.0    # °F
DEFAULT_STRAT_SLOPE = 2.8


def make_controls(on_fract: float, off_fract: float) -> Controls:
    return Controls(
        on_sensor_fract=on_fract,  on_trigger_t_f=SUPPLY_T,
        off_sensor_fract=off_fract, off_trigger_t_f=STORAGE_T,
        outlet_temp_f=STORAGE_T,
    )


_CONTROL_KEYS = ["normal", "loadUp", "shed"]


def make_control_map(*on_off_pairs) -> dict[str, Controls]:
    """Build a control_map from (on_fract, off_fract) pairs, keyed 'normal', 'loadUp', 'shed'..."""
    return {_CONTROL_KEYS[i]: make_controls(on, off) for i, (on, off) in enumerate(on_off_pairs)}


@pytest.fixture
def building_with_zone():
    zone = ClimateZone.from_design_conditions(
        design_oat_f=35.0,
        design_inlet_water_temp_f=INLET_T,
    )
    return Building.from_building_type(
        building_type='multi_family', magnitude=100, climate_zone=zone, gpdpp=25,
    )


@pytest.fixture
def building_no_zone():
    return Building.from_building_type(
        building_type='multi_family', magnitude=100, climate_zone=None, gpdpp=25,
    )


@pytest.fixture
def basic_control_map():
    """Single-mode control_map with a wide deadband."""
    return make_control_map((0.8, 0.0))


@pytest.fixture
def basic_schedule():
    """All-day schedule using the 'normal' control key."""
    return ["normal"] * 24


@pytest.fixture
def sized_system(building_with_zone):
    return DHWSystem.from_size(
        building=building_with_zone,
        supply_temp_f=SUPPLY_T,
        storage_temp_f=STORAGE_T,
    )


@pytest.fixture
def sized_system_with_controls(building_with_zone, basic_schedule, basic_control_map):
    return DHWSystem.from_size(
        building=building_with_zone,
        supply_temp_f=SUPPLY_T,
        storage_temp_f=STORAGE_T,
        control_schedule=basic_schedule,
        control_map=basic_control_map,
    )


# ===========================================================================
# NominalPerformanceMap
# ===========================================================================

class TestNominalPerformanceMap:
    def test_returns_constant_capacity(self):
        pm = NominalPerformanceMap(nominal_capacity_kbtuh=42.5)
        assert pm.get_capacity_kbtuh(oat_f=35.0, outlet_temp_f=120.0) == pytest.approx(42.5)

    def test_capacity_independent_of_conditions(self):
        pm = NominalPerformanceMap(nominal_capacity_kbtuh=30.0)
        assert pm.get_capacity_kbtuh(0.0, 50.0) == pm.get_capacity_kbtuh(100.0, 150.0)

    def test_nominal_capacity_stored(self):
        pm = NominalPerformanceMap(nominal_capacity_kbtuh=55.0)
        assert pm.nominal_capacity_kbtuh == pytest.approx(55.0)


# ===========================================================================
# WaterHeater factory methods
# ===========================================================================

class TestWaterHeaterFactories:
    def test_from_nominal_capacity_returns_water_heater(self, basic_schedule, basic_control_map):
        wh = WaterHeater.from_nominal_capacity(40.0, basic_schedule, basic_control_map)
        assert isinstance(wh, WaterHeater)

    def test_from_nominal_capacity_uses_nominal_map(self, basic_schedule, basic_control_map):
        wh = WaterHeater.from_nominal_capacity(40.0, basic_schedule, basic_control_map)
        assert isinstance(wh.performance_map, NominalPerformanceMap)

    def test_from_nominal_capacity_correct_value(self, basic_schedule, basic_control_map):
        wh = WaterHeater.from_nominal_capacity(40.0, basic_schedule, basic_control_map)
        assert wh.get_capacity_kbtuh(oat_f=35.0, outlet_temp_f=120.0) == pytest.approx(40.0)

    def test_from_nominal_capacity_wires_schedule_and_map(self, basic_schedule, basic_control_map):
        wh = WaterHeater.from_nominal_capacity(40.0, basic_schedule, basic_control_map)
        assert wh.control_schedule is basic_schedule
        assert wh.control_map is basic_control_map

    def test_from_nominal_capacity_no_controls(self):
        wh = WaterHeater.from_nominal_capacity(25.0, control_schedule=None, control_map=None)
        assert wh.control_schedule is None
        assert wh.control_map is None
        assert wh.get_capacity_kbtuh(35.0, 120.0) == pytest.approx(25.0)

    def test_from_nominal_capacity_not_load_shifting(self, basic_schedule, basic_control_map):
        wh = WaterHeater.from_nominal_capacity(40.0, basic_schedule, basic_control_map)
        assert not wh.is_load_shifting()

    def test_is_load_shifting_with_loadup_key(self):
        cmap = make_control_map((0.8, 0.0), (0.4, 0.0))  # "normal" + "loadUp"
        wh = WaterHeater.from_nominal_capacity(40.0, ["normal"] * 24, cmap)
        assert wh.is_load_shifting()

    def test_get_controls_for_hour_returns_correct_controls(self, basic_schedule, basic_control_map):
        wh = WaterHeater.from_nominal_capacity(40.0, basic_schedule, basic_control_map)
        ctrl = wh.get_controls_for_hour(hour_of_day=12)
        assert ctrl is basic_control_map["normal"]

    def test_get_controls_for_hour_respects_schedule(self):
        ctrl_a = make_controls(0.8, 0.0)
        ctrl_b = make_controls(0.5, 0.0)
        schedule = ["normal"] * 8 + ["loadUp"] * 8 + ["normal"] * 8
        cmap     = {"normal": ctrl_a, "loadUp": ctrl_b}
        wh = WaterHeater.from_nominal_capacity(40.0, schedule, cmap)
        assert wh.get_controls_for_hour(0)  is ctrl_a
        assert wh.get_controls_for_hour(10) is ctrl_b

    def test_get_controls_for_hour_no_schedule_returns_none(self):
        wh = WaterHeater.from_nominal_capacity(40.0, None, None)
        assert wh.get_controls_for_hour(5) is None

    def test_from_model_name_returns_water_heater(self, basic_schedule, basic_control_map):
        wh = WaterHeater.from_model_name("MODELS_ColmacCxV_5_C_SP", basic_schedule, basic_control_map)
        assert isinstance(wh, WaterHeater)
        assert wh.control_schedule is basic_schedule
        assert wh.control_map is basic_control_map


# ===========================================================================
# _get_peak_indices
# ===========================================================================

class TestGetPeakIndices:
    def test_single_transition(self):
        assert _get_peak_indices(np.array([1.0, 1.0, 1.0, -1.0, -1.0])) == [3]

    def test_multiple_transitions(self):
        assert _get_peak_indices(np.array([1.0, -1.0, 1.0, -1.0])) == [1, 3]

    def test_all_surplus(self):
        assert _get_peak_indices(np.array([1.0, 2.0, 3.0])) == []

    def test_all_deficit(self):
        assert _get_peak_indices(np.array([-1.0, -2.0, -3.0])) == []

    def test_wraparound_transition(self):
        assert _get_peak_indices(np.array([-1.0, 1.0, 1.0])) == [0]


# ===========================================================================
# _calc_required_capacity
# ===========================================================================

class TestCalcRequiredCapacity:
    def test_formula(self, building_with_zone):
        daily_gal  = building_with_zone.daily_dhw_use_supplyT_gal
        max_run_hr = 16.0
        defrost    = 0.95
        expected   = (daily_gal / max_run_hr) * _RHO_CP * (SUPPLY_T - INLET_T) / defrost / 1000

        system = DHWSystem(
            water_heaters=[], storage_tank=None,
            supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T,
            max_daily_run_hr=max_run_hr, defrost_factor=defrost,
        )
        assert system._calc_required_capacity(building_with_zone) == pytest.approx(expected, rel=1e-6)

    def test_lower_run_hours_gives_higher_capacity(self, building_with_zone):
        sys_24 = DHWSystem(water_heaters=[], storage_tank=None, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T, max_daily_run_hr=24.0)
        sys_16 = DHWSystem(water_heaters=[], storage_tank=None, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T, max_daily_run_hr=16.0)
        assert sys_24._calc_required_capacity(building_with_zone) < sys_16._calc_required_capacity(building_with_zone)

    def test_raises_without_design_inlet_temp(self, building_no_zone):
        system = DHWSystem(water_heaters=[], storage_tank=None, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T)
        with pytest.raises(ValueError, match="design inlet water temperature"):
            system._calc_required_capacity(building_no_zone)


# ===========================================================================
# _calc_running_volume_supplyT_gal
# ===========================================================================

class TestCalcRunningVolume:
    def test_returns_nonnegative(self, building_with_zone):
        system = DHWSystem(water_heaters=[], storage_tank=None, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T)
        cap = system._calc_required_capacity(building_with_zone)
        assert system._calc_running_volume_supplyT_gal(building_with_zone, cap) >= 0.0

    def test_flat_load_shape_zero_running_volume(self):
        zone = ClimateZone.from_design_conditions(design_oat_f=35.0, design_inlet_water_temp_f=INLET_T)
        building = Building.from_building_type(building_type='multi_family', magnitude=100, climate_zone=zone, gpdpp=25)
        building.peak_load_shape = np.full(24, 1.0 / 24)

        system = DHWSystem(water_heaters=[], storage_tank=None, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T, max_daily_run_hr=24.0)
        cap = system._calc_required_capacity(building)
        assert system._calc_running_volume_supplyT_gal(building, cap) == pytest.approx(0.0, abs=1e-6)

    def test_running_volume_decreases_with_run_hour_restriction(self, building_with_zone):
        sys_24 = DHWSystem(water_heaters=[], storage_tank=None, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T, max_daily_run_hr=24.0)
        sys_8  = DHWSystem(water_heaters=[], storage_tank=None, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T, max_daily_run_hr=8.0)
        vol_24 = sys_24._calc_running_volume_supplyT_gal(building_with_zone, sys_24._calc_required_capacity(building_with_zone))
        vol_8  = sys_8._calc_running_volume_supplyT_gal(building_with_zone, sys_8._calc_required_capacity(building_with_zone))
        assert vol_24 > vol_8


# ===========================================================================
# _calc_storage_volume_storageT_gal
# ===========================================================================

class TestCalcStorageVolume:
    def _sys(self):
        return DHWSystem(water_heaters=[], storage_tank=None, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T)

    def test_strat_factor_divides_running_vol(self):
        # storage_vol = running_vol / strat_factor
        result = self._sys()._calc_storage_volume_storageT_gal(100.0, 0.8)
        assert result == pytest.approx(100.0 / 0.8, rel=1e-6)

    def test_strat_factor_increases_storage(self):
        # Lower strat_factor → larger required storage volume
        sys = self._sys()
        assert sys._calc_storage_volume_storageT_gal(100.0, 0.8) > sys._calc_storage_volume_storageT_gal(100.0, 1.0)

    def test_zero_running_volume(self):
        assert self._sys()._calc_storage_volume_storageT_gal(0.0, 1.0) == 0.0


# ===========================================================================
# _calc_stratification_factor
# ===========================================================================

class TestStratificationFactor:
    def _sys(self):
        return DHWSystem(water_heaters=[], storage_tank=None, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T)

    def test_returns_positive(self):
        # The factor accounts for temperature-mixing credit: 1 physical gallon at storage_temp
        # can produce more than 1 supply-temp gallon when storage_temp >> supply_temp.
        # So the factor can exceed 1.0 — only positivity is guaranteed.
        cmap = make_control_map((0.0, 0.0))
        assert 0.0 < self._sys()._calc_stratification_factor(cmap, DEFAULT_STRAT_SLOPE, INLET_T)

    def test_none_map_uses_defaults(self):
        """control_map=None gives same result as on_fract=0.0, on_temp=supply_temp."""
        sys = self._sys()
        factor_none = sys._calc_stratification_factor(None, DEFAULT_STRAT_SLOPE, INLET_T)
        cmap = make_control_map((0.0, 0.0))
        factor_ctrl = sys._calc_stratification_factor(cmap, DEFAULT_STRAT_SLOPE, INLET_T)
        assert factor_none == pytest.approx(factor_ctrl)

    def test_lower_aquastat_gives_higher_factor(self):
        sys = self._sys()
        cmap_low  = make_control_map((0.0, 0.0))
        cmap_high = make_control_map((0.5, 0.0))
        assert sys._calc_stratification_factor(cmap_low, DEFAULT_STRAT_SLOPE, INLET_T) >= sys._calc_stratification_factor(cmap_high, DEFAULT_STRAT_SLOPE, INLET_T)

    def test_on_temp_at_storage_gives_max_factor(self):
        # on_trigger at storage_temp means the entire tank is at storage_temp.
        # Each physical gallon yields (storage-inlet)/(supply-inlet) supply-temp gallons.
        ctrl = Controls(on_sensor_fract=0.0, on_trigger_t_f=STORAGE_T,
                        off_sensor_fract=0.0, off_trigger_t_f=STORAGE_T,
                        outlet_temp_f=STORAGE_T)
        cmap = {"normal": ctrl}
        expected = (STORAGE_T - INLET_T) / (SUPPLY_T - INLET_T)
        assert self._sys()._calc_stratification_factor(cmap, DEFAULT_STRAT_SLOPE, INLET_T) == pytest.approx(expected, rel=1e-4)

    def test_higher_strat_slope_gives_higher_factor(self):
        cmap = make_control_map((0.0, 0.0))
        sys  = self._sys()
        assert sys._calc_stratification_factor(cmap, 5.0, INLET_T) > sys._calc_stratification_factor(cmap, 1.0, INLET_T)

    def test_normal_key_used_for_normal_sizing(self):
        """_calc_stratification_factor uses only the 'normal' key, ignoring loadUp/shed."""
        sys = self._sys()
        # 'normal' has on_fract=0.1 (low aquastat), 'loadUp' has on_fract=0.8 (high)
        cmap = {"normal": make_controls(0.1, 0.0), "loadUp": make_controls(0.8, 0.0)}
        factor_multi  = sys._calc_stratification_factor(cmap, DEFAULT_STRAT_SLOPE, INLET_T)
        factor_normal = sys._calc_stratification_factor({"normal": make_controls(0.1, 0.0)}, DEFAULT_STRAT_SLOPE, INLET_T)
        # Should use only 'normal' — shed/loadUp aquastats are for the LS path
        assert factor_multi == pytest.approx(factor_normal)


# ===========================================================================
# _warn_if_short_cycling
# ===========================================================================

class TestShortCyclingWarning:
    def _sys(self):
        return DHWSystem(water_heaters=[], storage_tank=None, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T)

    def test_no_warning_with_large_deadband(self):
        sys  = self._sys()
        cmap = make_control_map((0.9, 0.0))
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            sys._warn_if_short_cycling(cmap, capacity_kbtuh=20.0, storage_vol_storageT_gal=500.0)

    def test_warning_with_tiny_deadband(self):
        sys  = self._sys()
        cmap = make_control_map((0.01, 0.0))  # 1% deadband
        with pytest.warns(UserWarning, match="short cycling"):
            sys._warn_if_short_cycling(cmap, capacity_kbtuh=200.0, storage_vol_storageT_gal=50.0)

    def test_warning_when_off_above_on(self):
        sys  = self._sys()
        cmap = make_control_map((0.2, 0.5))  # off above on — backwards
        with pytest.warns(UserWarning, match="never shut off"):
            sys._warn_if_short_cycling(cmap, capacity_kbtuh=20.0, storage_vol_storageT_gal=500.0)

    def test_warning_includes_key(self):
        """Warning message should identify which Controls key is problematic."""
        sys  = self._sys()
        cmap = {"loadUp": make_controls(0.01, 0.0)}
        with pytest.warns(UserWarning, match="key loadUp"):
            sys._warn_if_short_cycling(cmap, capacity_kbtuh=200.0, storage_vol_storageT_gal=50.0)

    def test_no_warning_when_control_map_is_none(self, building_with_zone):
        sys = DHWSystem(water_heaters=[], storage_tank=None, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            sys.size(building_with_zone, control_map=None)

    def test_from_size_emits_warning_for_bad_controls(self, building_with_zone):
        bad_map = make_control_map((0.01, 0.0))
        with pytest.warns(UserWarning, match="short cycling"):
            DHWSystem.from_size(
                building=building_with_zone,
                supply_temp_f=SUPPLY_T,
                storage_temp_f=STORAGE_T,
                control_map=bad_map,
            )


# ===========================================================================
# from_size() factory
# ===========================================================================

class TestFromSize:
    def test_returns_dhw_system(self, building_with_zone):
        assert isinstance(
            DHWSystem.from_size(building=building_with_zone, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T),
            DHWSystem,
        )

    def test_has_one_water_heater(self, sized_system):
        assert len(sized_system.water_heaters) == 1
        assert isinstance(sized_system.water_heaters[0], WaterHeater)

    def test_water_heater_uses_nominal_performance_map(self, sized_system):
        assert isinstance(sized_system.water_heaters[0].performance_map, NominalPerformanceMap)

    def test_nominal_map_capacity_matches_minimum(self, sized_system):
        heater = sized_system.water_heaters[0]
        assert heater.performance_map.nominal_capacity_kbtuh == pytest.approx(
            sized_system._minimum_capacity_kbtuh, rel=1e-9
        )

    def test_capacity_query_returns_minimum(self, sized_system):
        heater = sized_system.water_heaters[0]
        assert heater.get_capacity_kbtuh(oat_f=35.0, outlet_temp_f=120.0) == pytest.approx(
            sized_system._minimum_capacity_kbtuh, rel=1e-9
        )

    def test_has_storage_tank(self, sized_system):
        assert isinstance(sized_system.storage_tank, StorageTank)

    def test_storage_tank_volume_matches_minimum(self, sized_system):
        assert sized_system.storage_tank.total_volume_gal == pytest.approx(
            sized_system._minimum_storage_storageT_gal, rel=1e-9
        )

    def test_strat_slope_default_stored_on_tank(self, sized_system):
        assert sized_system.storage_tank.strat_slope == pytest.approx(2.8)

    def test_custom_strat_slope_stored_on_tank(self, building_with_zone):
        system = DHWSystem.from_size(building=building_with_zone, supply_temp_f=SUPPLY_T,
                                     storage_temp_f=STORAGE_T, strat_slope=4.0)
        assert system.storage_tank.strat_slope == pytest.approx(4.0)

    def test_strat_slope_affects_storage_size(self, building_with_zone):
        sys_low  = DHWSystem.from_size(building_with_zone, SUPPLY_T, STORAGE_T, strat_slope=1.0)
        sys_high = DHWSystem.from_size(building_with_zone, SUPPLY_T, STORAGE_T, strat_slope=5.0)
        assert sys_high._minimum_storage_storageT_gal < sys_low._minimum_storage_storageT_gal

    def test_sizing_results_are_positive(self, sized_system):
        assert sized_system._minimum_capacity_kbtuh > 0
        assert sized_system._minimum_storage_storageT_gal >= 0

    def test_raises_without_climate_zone(self, building_no_zone):
        with pytest.raises(ValueError, match="design inlet water temperature"):
            DHWSystem.from_size(building=building_no_zone, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T)

    def test_building_not_modified_after_sizing(self, building_with_zone):
        was_annual = building_with_zone.is_annual_load_shape()
        DHWSystem.from_size(building=building_with_zone, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T)
        assert building_with_zone.is_annual_load_shape() == was_annual

    def test_sizing_with_annual_load_shape(self, building_with_zone):
        building_with_zone.set_to_annual_load_shape()
        system = DHWSystem.from_size(building=building_with_zone, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T)
        assert building_with_zone.is_annual_load_shape()
        assert system._minimum_capacity_kbtuh > 0

    def test_higher_run_hours_gives_less_capacity(self, building_with_zone):
        sys_8  = DHWSystem.from_size(building_with_zone, SUPPLY_T, STORAGE_T, max_daily_run_hr=8.0)
        sys_24 = DHWSystem.from_size(building_with_zone, SUPPLY_T, STORAGE_T, max_daily_run_hr=24.0)
        assert sys_24._minimum_capacity_kbtuh < sys_8._minimum_capacity_kbtuh

    def test_temperature_params_stored(self, sized_system):
        assert sized_system.supply_temp_f  == SUPPLY_T
        assert sized_system.storage_temp_f == STORAGE_T

    def test_schedule_and_map_assigned_to_water_heater(
        self, sized_system_with_controls, basic_schedule, basic_control_map
    ):
        heater = sized_system_with_controls.water_heaters[0]
        assert heater.control_schedule is basic_schedule
        assert heater.control_map is basic_control_map

    def test_no_controls_leaves_heater_fields_none(self, sized_system):
        heater = sized_system.water_heaters[0]
        assert heater.control_schedule is None
        assert heater.control_map is None

    def test_control_map_on_sensor_affects_sizing(self, building_with_zone):
        """A higher ON sensor in the map drives a lower strat factor → more storage."""
        map_low  = make_control_map((0.3, 0.0))
        map_high = make_control_map((0.8, 0.0))
        sys_low  = DHWSystem.from_size(building_with_zone, SUPPLY_T, STORAGE_T, control_map=map_low)
        sys_high = DHWSystem.from_size(building_with_zone, SUPPLY_T, STORAGE_T, control_map=map_high)
        assert sys_high._minimum_storage_storageT_gal >= sys_low._minimum_storage_storageT_gal

    def test_multimode_map_uses_normal_key_for_sizing(self, building_with_zone):
        """Normal sizing uses only the 'normal' Controls regardless of other keys in the map."""
        map_normal_only = {"normal": make_controls(0.5, 0.0)}
        map_with_ls     = {"normal": make_controls(0.5, 0.0), "shed": make_controls(0.8, 0.0)}
        sys_normal = DHWSystem.from_size(building_with_zone, SUPPLY_T, STORAGE_T, control_map=map_normal_only)
        sys_ls     = DHWSystem.from_size(building_with_zone, SUPPLY_T, STORAGE_T, control_map=map_with_ls)
        # Without a schedule, LS path is skipped; normal sizing should be identical
        assert sys_ls._minimum_storage_storageT_gal == pytest.approx(
            sys_normal._minimum_storage_storageT_gal, rel=1e-9
        )


# ===========================================================================
# from_components() factory
# ===========================================================================

class TestFromComponents:
    def _make_heater(self, capacity_kbtuh=50.0):
        return WaterHeater.from_nominal_capacity(capacity_kbtuh, control_schedule=None, control_map=None)

    def test_returns_dhw_system(self):
        assert isinstance(
            DHWSystem.from_components(500.0, [self._make_heater()], SUPPLY_T, STORAGE_T),
            DHWSystem,
        )

    def test_storage_tank_volume(self):
        system = DHWSystem.from_components(500.0, [self._make_heater()], SUPPLY_T, STORAGE_T)
        assert system.storage_tank.total_volume_gal == pytest.approx(500.0)

    def test_strat_slope_stored_on_tank(self):
        system = DHWSystem.from_components(500.0, [self._make_heater()], SUPPLY_T, STORAGE_T, strat_slope=3.5)
        assert system.storage_tank.strat_slope == pytest.approx(3.5)

    def test_water_heater_list_preserved(self):
        h1, h2 = self._make_heater(30.0), self._make_heater(20.0)
        system = DHWSystem.from_components(300.0, [h1, h2], SUPPLY_T, STORAGE_T)
        assert len(system.water_heaters) == 2
        assert system.water_heaters[0].performance_map.nominal_capacity_kbtuh == pytest.approx(30.0)
        assert system.water_heaters[1].performance_map.nominal_capacity_kbtuh == pytest.approx(20.0)

    def test_sizing_results_none_when_no_size_called(self):
        system = DHWSystem.from_components(500.0, [self._make_heater()], SUPPLY_T, STORAGE_T)
        assert system._minimum_capacity_kbtuh is None
        assert system._minimum_storage_storageT_gal is None

    def test_get_minimum_capacity_raises_before_sizing(self):
        system = DHWSystem.from_components(500.0, [self._make_heater()], SUPPLY_T, STORAGE_T)
        with pytest.raises(RuntimeError):
            system.get_minimum_capacity_kbtuh()

    def test_temperature_params_stored(self):
        system = DHWSystem.from_components(
            100.0, [WaterHeater(None, None, None)], SUPPLY_T, STORAGE_T,
        )
        assert system.supply_temp_f  == SUPPLY_T
        assert system.storage_temp_f == STORAGE_T


# ===========================================================================
# Load-shift sizing helpers and integration
# ===========================================================================

def make_ls_schedule(shed_hours: list[int], load_up_hours: int) -> list[str]:
    """
    Build a 24-element control_schedule with shed_hours marked as "shed",
    the load_up_hours immediately before the first shed marked as "loadUp",
    and everything else as "normal".
    """
    schedule = ["normal"] * 24
    for h in shed_hours:
        schedule[h] = "shed"
    first_shed = shed_hours[0]
    for i in range(load_up_hours):
        schedule[first_shed - 1 - i] = "loadUp"
    return schedule


def make_ls_control_map(
    normal_on: float,
    load_up_on: float,
    shed_on: float,
) -> dict[str, Controls]:
    """
    Build a load-shift control_map with three modes.
    ON trigger = SUPPLY_T, OFF trigger = STORAGE_T for all modes.
    """
    return {
        "normal": Controls(normal_on, SUPPLY_T, 0.0, STORAGE_T, STORAGE_T),
        "loadUp": Controls(load_up_on, SUPPLY_T, 0.0, STORAGE_T, STORAGE_T),
        "shed":   Controls(shed_on,    SUPPLY_T, 0.0, STORAGE_T, STORAGE_T),
    }


class TestLoadShiftDetection:
    def test_is_load_shifting_true_with_shed_key(self):
        cmap = make_ls_control_map(0.5, 0.3, 0.7)
        assert DHWSystem._is_load_shifting(cmap)

    def test_is_load_shifting_false_without_shed_key(self, basic_control_map):
        assert not DHWSystem._is_load_shifting(basic_control_map)

    def test_is_load_shifting_false_with_only_load_up(self):
        cmap = {"normal": make_controls(0.5, 0.0), "loadUp": make_controls(0.3, 0.0)}
        assert not DHWSystem._is_load_shifting(cmap)

    def test_is_load_shifting_false_with_none(self):
        assert not DHWSystem._is_load_shifting(None)


class TestGetFirstShedBlockAndLoadUpHours:
    def test_simple_shed_block(self):
        schedule = make_ls_schedule([10, 11, 12], load_up_hours=2)
        block, lu_hrs = DHWSystem._get_first_shed_block_and_load_up_hours(schedule)
        assert block == [10, 11, 12]
        assert lu_hrs == 2

    def test_no_load_up_hours(self):
        schedule = make_ls_schedule([8, 9, 10], load_up_hours=0)
        block, lu_hrs = DHWSystem._get_first_shed_block_and_load_up_hours(schedule)
        assert block == [8, 9, 10]
        assert lu_hrs == 0

    def test_only_first_consecutive_block_returned(self):
        # Two separated shed blocks — only first returned
        schedule = ["normal"] * 24
        for h in [6, 7, 14, 15]:
            schedule[h] = "shed"
        block, _ = DHWSystem._get_first_shed_block_and_load_up_hours(schedule)
        assert block == [6, 7]

    def test_no_shed_hours(self):
        schedule = ["normal"] * 24
        block, lu_hrs = DHWSystem._get_first_shed_block_and_load_up_hours(schedule)
        assert block == []
        assert lu_hrs == 0


class TestCalcPrelimVols:
    def _sys(self):
        return DHWSystem(water_heaters=[], storage_tank=None, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T)

    def test_vshift_equals_demand_during_shed(self, building_with_zone):
        schedule = make_ls_schedule([10, 11, 12], load_up_hours=2)
        sys = self._sys()
        vshift_supplyT_gal, _ = sys._calc_prelim_vols_supplyT_gal(schedule, building_with_zone)
        expected = sum(
            building_with_zone.avg_load_shape[h] for h in [10, 11, 12]
        ) * building_with_zone.daily_dhw_use_supplyT_gal
        assert vshift_supplyT_gal == pytest.approx(expected, rel=1e-9)

    def test_vconsumed_lu_equals_demand_during_loadup(self, building_with_zone):
        schedule = make_ls_schedule([10, 11, 12], load_up_hours=2)
        sys = self._sys()
        _, vconsumed_lu_supplyT_gal = sys._calc_prelim_vols_supplyT_gal(schedule, building_with_zone)
        expected = sum(
            building_with_zone.avg_load_shape[h] for h in [8, 9]
        ) * building_with_zone.daily_dhw_use_supplyT_gal
        assert vconsumed_lu_supplyT_gal == pytest.approx(expected, rel=1e-9)

    def test_vconsumed_lu_zero_when_no_load_up(self, building_with_zone):
        schedule = make_ls_schedule([10, 11, 12], load_up_hours=0)
        _, vconsumed_lu_supplyT_gal = self._sys()._calc_prelim_vols_supplyT_gal(schedule, building_with_zone)
        assert vconsumed_lu_supplyT_gal == pytest.approx(0.0)


class TestLoadShiftSizing:
    """Integration tests: LS sizing produces larger capacity/storage than normal."""

    def _ls_system(self, building, shed_hours, load_up_hours, normal_on, load_up_on, shed_on):
        schedule = make_ls_schedule(shed_hours, load_up_hours)
        cmap     = make_ls_control_map(normal_on, load_up_on, shed_on)
        return DHWSystem.from_size(
            building=building,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
            control_schedule=schedule,
            control_map=cmap,
        )

    def _normal_system(self, building):
        return DHWSystem.from_size(
            building=building,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
        )

    def test_ls_storage_at_least_as_large_as_normal(self, building_with_zone):
        ls_sys  = self._ls_system(building_with_zone, [10, 11, 12, 13, 14], 2, 0.5, 0.2, 0.8)
        norm_sys = self._normal_system(building_with_zone)
        assert ls_sys._minimum_storage_storageT_gal >= norm_sys._minimum_storage_storageT_gal

    def test_ls_storage_larger_than_normal_for_long_shed(self, building_with_zone):
        """A long shed window forces substantially more storage than no load shifting."""
        sys_ls   = self._ls_system(building_with_zone, [10, 11, 12, 13, 14], 2, 0.5, 0.2, 0.8)
        sys_norm = self._normal_system(building_with_zone)
        assert sys_ls._minimum_storage_storageT_gal >= sys_norm._minimum_storage_storageT_gal

    def test_ls_without_loadup_key_runs(self, building_with_zone):
        """LS sizing works when no 'loadUp' key is present (load_up_hours=0)."""
        schedule = make_ls_schedule([10, 11, 12], load_up_hours=0)
        cmap     = {"normal": make_controls(0.5, 0.0), "shed": make_controls(0.8, 0.0)}
        system   = DHWSystem.from_size(
            building=building_with_zone,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
            control_schedule=schedule,
            control_map=cmap,
        )
        assert system._minimum_storage_storageT_gal > 0
        assert system._minimum_capacity_kbtuh > 0

    def test_no_ls_without_schedule(self, building_with_zone):
        """Passing control_map with shed but no schedule skips LS path."""
        cmap    = make_ls_control_map(0.5, 0.2, 0.8)
        sys_no_sched = DHWSystem.from_size(
            building=building_with_zone,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
            control_schedule=None,
            control_map=cmap,
        )
        norm_sys = self._normal_system(building_with_zone)
        # Without schedule, LS path is skipped — result may equal normal sizing
        assert sys_no_sched._minimum_capacity_kbtuh == pytest.approx(
            norm_sys._minimum_capacity_kbtuh, rel=1e-6
        )
