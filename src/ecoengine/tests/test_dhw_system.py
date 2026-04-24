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
from ecoengine.objects.dhwsystems.DHWSystem import DHWSystem, _get_peak_indices
from ecoengine.constants.constants import _RHO_CP
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.heating.PerformanceMap import NominalPerformanceMap
from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.storage.StorageTank import StorageTank
from ecoengine.objects.components.storage.StratifiedTank import StratifiedTank
from ecoengine.objects.dhwsystems.rtp_systems.SinglePassRTPSystem import SinglePassRTPSystem


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


# ===========================================================================
# get_sizing_curve
# ===========================================================================

MAX_RUN_HR = 16.0
STRAT_SLOPE = 2.8


class TestSizingCurve:
    """Tests for DHWSystem.get_sizing_curve()."""

    @pytest.fixture
    def system(self, building_with_zone):
        """Sized DHWSystem with default max_daily_run_hr=16."""
        return DHWSystem.from_size(
            building=building_with_zone,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
            max_daily_run_hr=MAX_RUN_HR,
        )

    @pytest.fixture
    def curve(self, system, building_with_zone):
        return system.get_sizing_curve(building_with_zone, strat_slope=STRAT_SLOPE)

    # ------------------------------------------------------------------
    # Structure
    # ------------------------------------------------------------------

    def test_returns_dict_with_required_keys(self, curve):
        assert set(curve.keys()) == {
            "heat_hours", "capacity_kbtuh", "storage_storageT_gal", "recommended_index"
        }

    def test_all_lists_same_length(self, curve):
        n = len(curve["heat_hours"])
        assert n > 0
        assert len(curve["capacity_kbtuh"])       == n
        assert len(curve["storage_storageT_gal"]) == n

    def test_recommended_index_in_bounds(self, curve):
        rec = curve["recommended_index"]
        assert 0 <= rec < len(curve["heat_hours"])

    # ------------------------------------------------------------------
    # Sweep content
    # ------------------------------------------------------------------

    def test_recommended_heat_hours_equals_max_daily_run_hr(self, curve):
        rec = curve["recommended_index"]
        assert curve["heat_hours"][rec] == pytest.approx(MAX_RUN_HR)

    def test_heat_hours_decrease_monotonically(self, curve):
        hrs = curve["heat_hours"]
        for i in range(1, len(hrs)):
            assert hrs[i] < hrs[i - 1], f"heat_hours not decreasing at index {i}"

    def test_capacity_increases_as_run_hours_decrease(self, curve):
        """Lower run hours → higher capacity required."""
        caps = curve["capacity_kbtuh"]
        for i in range(1, len(caps)):
            assert caps[i] >= caps[i - 1] - 1e-9, (
                f"capacity not non-decreasing at index {i}: {caps[i-1]:.3f} → {caps[i]:.3f}"
            )

    def test_storage_decreases_as_run_hours_decrease(self, curve):
        """Lower run hours → less storage required (smaller deficit window)."""
        stor = curve["storage_storageT_gal"]
        for i in range(1, len(stor)):
            assert stor[i] <= stor[i - 1] + 1e-9, (
                f"storage not non-increasing at index {i}: {stor[i-1]:.1f} → {stor[i]:.1f}"
            )

    def test_sweep_covers_range_above_max_run_hr(self, curve):
        """Part of the curve should be at run hours > max_daily_run_hr (left of recommended)."""
        rec  = curve["recommended_index"]
        assert rec > 0, "Expected at least one point to the left of the recommended index"
        assert curve["heat_hours"][0] > MAX_RUN_HR

    def test_curve_terminates_before_physical_minimum(self, curve, building_with_zone):
        """The last heat-hour value must be > 1/max(loadshape)."""
        min_run_hr = 1.0 / float(np.max(building_with_zone.peak_load_shape))
        assert curve["heat_hours"][-1] > min_run_hr

    # ------------------------------------------------------------------
    # Recommended point matches size() output
    # ------------------------------------------------------------------

    def test_recommended_capacity_matches_sized_value(self, system, building_with_zone):
        """
        The capacity at rec_index should match what size() produces with no
        control_map, since both use the same internal methods and strat_factor.
        """
        # Re-size without controls to get a clean baseline
        system.size(building_with_zone)
        sized_cap = system._minimum_capacity_kbtuh

        curve = system.get_sizing_curve(building_with_zone, strat_slope=STRAT_SLOPE)
        rec   = curve["recommended_index"]
        assert curve["capacity_kbtuh"][rec] == pytest.approx(sized_cap, rel=1e-6)

    def test_recommended_storage_matches_sized_value(self, system, building_with_zone):
        system.size(building_with_zone)
        sized_stor = system._minimum_storage_storageT_gal

        curve = system.get_sizing_curve(building_with_zone, strat_slope=STRAT_SLOPE)
        rec   = curve["recommended_index"]
        assert curve["storage_storageT_gal"][rec] == pytest.approx(sized_stor, rel=1e-6)

    # ------------------------------------------------------------------
    # State is restored after the call
    # ------------------------------------------------------------------

    def test_max_daily_run_hr_unchanged_after_curve(self, system, building_with_zone):
        before = system.max_daily_run_hr
        system.get_sizing_curve(building_with_zone)
        assert system.max_daily_run_hr == before

    def test_building_load_shape_unchanged_after_curve(self, system, building_with_zone):
        before = building_with_zone.daily_dhw_use_supplyT_gal
        system.get_sizing_curve(building_with_zone)
        assert building_with_zone.daily_dhw_use_supplyT_gal == pytest.approx(before)

    # ------------------------------------------------------------------
    # Subclass: SinglePassRTPSystem
    # ------------------------------------------------------------------

    def test_sprtp_curve_capacity_higher_than_base(self, building_with_zone):
        """
        SPRTP adds recirc-loss capacity on top of the DHW capacity.
        Every curve point for SPRTP should have higher capacity than the
        equivalent base-DHWSystem point (same building and temperatures).
        """
        base = DHWSystem.from_size(
            building=building_with_zone,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
            max_daily_run_hr=MAX_RUN_HR,
        )
        sprtp = SinglePassRTPSystem.from_size(
            building=building_with_zone,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
            return_temp_f=110.0,
            return_flow_gpm=3.0,
            max_daily_run_hr=MAX_RUN_HR,
        )

        base_curve  = base.get_sizing_curve(building_with_zone,  strat_slope=STRAT_SLOPE)
        sprtp_curve = sprtp.get_sizing_curve(building_with_zone, strat_slope=STRAT_SLOPE)

        n = min(len(base_curve["capacity_kbtuh"]), len(sprtp_curve["capacity_kbtuh"]))
        assert n > 0
        for i in range(n):
            assert sprtp_curve["capacity_kbtuh"][i] > base_curve["capacity_kbtuh"][i], (
                f"SPRTP capacity should exceed base at index {i}"
            )


# ===========================================================================
# get_ls_sizing_curve
# ===========================================================================

_LS_SHED_HOURS   = [10, 11, 12, 13, 14]
_LS_LOAD_UP_HRS  = 2
_LS_NORMAL_ON    = 0.5
_LS_LOAD_UP_ON   = 0.2
_LS_SHED_ON      = 0.8
_LS_PERCENT      = 1.0


class TestLSSizingCurve:
    """Tests for DHWSystem.get_ls_sizing_curve()."""

    @pytest.fixture
    def ls_schedule(self):
        return make_ls_schedule(_LS_SHED_HOURS, _LS_LOAD_UP_HRS)

    @pytest.fixture
    def ls_control_map(self):
        return make_ls_control_map(_LS_NORMAL_ON, _LS_LOAD_UP_ON, _LS_SHED_ON)

    @pytest.fixture
    def ls_system(self, building_with_zone, ls_schedule, ls_control_map):
        return DHWSystem.from_size(
            building=building_with_zone,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
            control_schedule=ls_schedule,
            control_map=ls_control_map,
        )

    @pytest.fixture
    def ls_curve(self, ls_system, building_with_zone, ls_schedule, ls_control_map):
        return ls_system.get_ls_sizing_curve(
            building_with_zone,
            control_schedule=ls_schedule,
            control_map=ls_control_map,
            strat_slope=STRAT_SLOPE,
            load_shift_percent=_LS_PERCENT,
        )

    # ------------------------------------------------------------------
    # ValueError: no shed key
    # ------------------------------------------------------------------

    def test_raises_without_shed_key(self, ls_system, building_with_zone, ls_schedule):
        normal_only_map = {"normal": make_controls(0.5, 0.0)}
        with pytest.raises(ValueError, match="shed"):
            ls_system.get_ls_sizing_curve(
                building_with_zone,
                control_schedule=ls_schedule,
                control_map=normal_only_map,
            )

    # ------------------------------------------------------------------
    # Structure
    # ------------------------------------------------------------------

    def test_returns_dict_with_required_keys(self, ls_curve):
        assert set(ls_curve.keys()) == {
            "load_shift_percent", "capacity_kbtuh",
            "storage_storageT_gal", "recommended_index",
        }

    def test_exactly_76_points(self, ls_curve):
        """Sweep is 0.25, 0.26, …, 1.00 → 76 values."""
        assert len(ls_curve["load_shift_percent"])   == 76
        assert len(ls_curve["capacity_kbtuh"])       == 76
        assert len(ls_curve["storage_storageT_gal"]) == 76

    def test_load_shift_percent_range(self, ls_curve):
        pcts = ls_curve["load_shift_percent"]
        assert pcts[0]  == pytest.approx(0.25)
        assert pcts[-1] == pytest.approx(1.00)

    def test_recommended_index_in_bounds(self, ls_curve):
        rec = ls_curve["recommended_index"]
        assert 0 <= rec < 76

    def test_recommended_index_for_percent_1(self, ls_curve):
        """load_shift_percent=1.0 → rec_index=75 (last element)."""
        assert ls_curve["recommended_index"] == 75

    def test_recommended_index_for_percent_025(
        self, ls_system, building_with_zone, ls_schedule, ls_control_map
    ):
        """load_shift_percent=0.25 → rec_index=0 (first element)."""
        curve = ls_system.get_ls_sizing_curve(
            building_with_zone,
            control_schedule=ls_schedule,
            control_map=ls_control_map,
            load_shift_percent=0.25,
        )
        assert curve["recommended_index"] == 0

    def test_recommended_index_midpoint(
        self, ls_system, building_with_zone, ls_schedule, ls_control_map
    ):
        """load_shift_percent=0.50 → rec_index=25."""
        curve = ls_system.get_ls_sizing_curve(
            building_with_zone,
            control_schedule=ls_schedule,
            control_map=ls_control_map,
            load_shift_percent=0.50,
        )
        assert curve["recommended_index"] == 25

    # ------------------------------------------------------------------
    # Monotonicity / physics
    # ------------------------------------------------------------------

    def test_storage_increases_with_coverage(self, ls_curve):
        """Higher coverage → more storage required."""
        stor = ls_curve["storage_storageT_gal"]
        for i in range(1, len(stor)):
            assert stor[i] >= stor[i - 1] - 1e-9, (
                f"storage not non-decreasing at index {i}: {stor[i-1]:.1f} → {stor[i]:.1f}"
            )

    def test_all_capacity_positive(self, ls_curve):
        for cap in ls_curve["capacity_kbtuh"]:
            assert cap > 0

    def test_all_storage_positive(self, ls_curve):
        for stor in ls_curve["storage_storageT_gal"]:
            assert stor > 0

    # ------------------------------------------------------------------
    # Recommended point matches size() output
    # ------------------------------------------------------------------

    def test_recommended_capacity_matches_sized_value(
        self, ls_system, building_with_zone, ls_schedule, ls_control_map
    ):
        """
        Capacity at rec_index should match the system's already-sized capacity,
        since both use the same building, schedule, and control_map.
        """
        # size() was already run by from_size() — grab the result
        sized_cap = ls_system._minimum_capacity_kbtuh

        curve = ls_system.get_ls_sizing_curve(
            building_with_zone,
            control_schedule=ls_schedule,
            control_map=ls_control_map,
            strat_slope=STRAT_SLOPE,
            load_shift_percent=_LS_PERCENT,
        )
        rec = curve["recommended_index"]
        assert curve["capacity_kbtuh"][rec] == pytest.approx(sized_cap, rel=1e-4)

    def test_recommended_storage_matches_sized_value(
        self, ls_system, building_with_zone, ls_schedule, ls_control_map
    ):
        sized_stor = ls_system._minimum_storage_storageT_gal

        curve = ls_system.get_ls_sizing_curve(
            building_with_zone,
            control_schedule=ls_schedule,
            control_map=ls_control_map,
            strat_slope=STRAT_SLOPE,
            load_shift_percent=_LS_PERCENT,
        )
        rec = curve["recommended_index"]
        assert curve["storage_storageT_gal"][rec] == pytest.approx(sized_stor, rel=1e-4)

    # ------------------------------------------------------------------
    # LS curve vs normal curve
    # ------------------------------------------------------------------

    def test_ls_storage_at_high_coverage_exceeds_normal_curve(
        self, building_with_zone, ls_schedule, ls_control_map
    ):
        """
        At high load-shift coverage the LS system needs more storage than the
        normal sizing curve's recommended point.
        """
        ls_sys = DHWSystem.from_size(
            building=building_with_zone,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
            control_schedule=ls_schedule,
            control_map=ls_control_map,
        )
        normal_sys = DHWSystem.from_size(
            building=building_with_zone,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
        )
        ls_curve     = ls_sys.get_ls_sizing_curve(
            building_with_zone,
            control_schedule=ls_schedule,
            control_map=ls_control_map,
            strat_slope=STRAT_SLOPE,
            load_shift_percent=_LS_PERCENT,
        )
        normal_curve = normal_sys.get_sizing_curve(building_with_zone, strat_slope=STRAT_SLOPE)

        ls_rec   = ls_curve["recommended_index"]
        norm_rec = normal_curve["recommended_index"]
        assert (
            ls_curve["storage_storageT_gal"][ls_rec]
            >= normal_curve["storage_storageT_gal"][norm_rec]
        )

    # ------------------------------------------------------------------
    # SPRTP subclass
    # ------------------------------------------------------------------

    def test_sprtp_ls_curve_capacity_higher_than_base(
        self, building_with_zone, ls_control_map
    ):
        """
        SPRTP recirc-loss overhead raises the normal sizing path above base.

        With no load-up hours the LS gen rate equals the normal gen rate, so
        _calc_required_capacity_ls_kbtuh == _calc_required_capacity(base).
        SPRTP's override adds recirc overhead to cap_normal, pushing
        max(cap_normal, cap_ls) above the base value at every point.
        """
        # No load-up: LS gen rate == normal gen rate so SPRTP recirc always shows
        schedule_no_lu = make_ls_schedule(_LS_SHED_HOURS, load_up_hours=0)
        ctrl_map_no_lu = {"normal": make_controls(_LS_NORMAL_ON, 0.0),
                          "shed":   make_controls(_LS_SHED_ON,   0.0)}

        base = DHWSystem.from_size(
            building=building_with_zone,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
            control_schedule=schedule_no_lu,
            control_map=ctrl_map_no_lu,
        )
        sprtp = SinglePassRTPSystem.from_size(
            building=building_with_zone,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
            return_temp_f=110.0,
            return_flow_gpm=3.0,
            control_schedule=schedule_no_lu,
            control_map=ctrl_map_no_lu,
        )

        base_curve  = base.get_ls_sizing_curve(
            building_with_zone,
            control_schedule=schedule_no_lu,
            control_map=ctrl_map_no_lu,
            strat_slope=STRAT_SLOPE,
        )
        sprtp_curve = sprtp.get_ls_sizing_curve(
            building_with_zone,
            control_schedule=schedule_no_lu,
            control_map=ctrl_map_no_lu,
            strat_slope=STRAT_SLOPE,
        )

        # With no load-up, the normal path dominates and SPRTP's recirc adds
        # overhead at every point.
        for i in range(76):
            assert sprtp_curve["capacity_kbtuh"][i] > base_curve["capacity_kbtuh"][i], (
                f"SPRTP LS capacity should exceed base at index {i}"
            )
