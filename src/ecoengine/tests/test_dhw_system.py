"""
Unit tests for DHWSystem — sizing calculations and factory constructors.

Tests cover:
- Minimum capacity calculation (_calc_required_capacity)
- Running volume calculation (_calc_running_volume_supplyT_gal)
- Storage volume calculation (_calc_storage_volume_storageT_gal)
- Stratification factor calculation (_calc_stratification_factor)
- Short-cycling warning (_warn_if_short_cycling)
- from_size() factory: correct types, sizing results stored, Controls wiring
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
from ecoengine.objects.components.storage.StorageTank import StorageTank


# ===========================================================================
# Fixtures
# ===========================================================================

SUPPLY_T  = 120.0   # °F
STORAGE_T = 150.0   # °F
INLET_T   = 50.0    # °F


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
def basic_controls():
    """Controls with a wide deadband (on at bottom, off at 80%)."""
    return Controls(
        on_sensor_fract=0.0,
        on_trigger_t_f=SUPPLY_T,
        off_sensor_fract=0.8,
        off_trigger_t_f=STORAGE_T,
    )


@pytest.fixture
def sized_system(building_with_zone):
    return DHWSystem.from_size(
        building=building_with_zone,
        supply_temp_f=SUPPLY_T,
        storage_temp_f=STORAGE_T,
    )


@pytest.fixture
def sized_system_with_controls(building_with_zone, basic_controls):
    return DHWSystem.from_size(
        building=building_with_zone,
        supply_temp_f=SUPPLY_T,
        storage_temp_f=STORAGE_T,
        controls=basic_controls,
    )


# ===========================================================================
# NominalPerformanceMap
# ===========================================================================

class TestNominalPerformanceMap:
    def test_returns_constant_capacity(self):
        pm = NominalPerformanceMap(nominal_capacity_kbtuh=42.5)
        assert pm.get_capacity_kbtuh(oat_f=35.0, water_temp_f=120.0) == pytest.approx(42.5)

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
    def test_from_nominal_capacity_returns_water_heater(self, basic_controls):
        wh = WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=40.0,
            controls=basic_controls,
        )
        assert isinstance(wh, WaterHeater)

    def test_from_nominal_capacity_uses_nominal_map(self, basic_controls):
        wh = WaterHeater.from_nominal_capacity(nominal_capacity_kbtuh=40.0, controls=basic_controls)
        assert isinstance(wh.performance_map, NominalPerformanceMap)

    def test_from_nominal_capacity_correct_value(self, basic_controls):
        wh = WaterHeater.from_nominal_capacity(nominal_capacity_kbtuh=40.0, controls=basic_controls)
        assert wh.get_capacity_kbtuh(oat_f=35.0, water_temp_f=120.0) == pytest.approx(40.0)

    def test_from_nominal_capacity_wires_controls(self, basic_controls):
        wh = WaterHeater.from_nominal_capacity(nominal_capacity_kbtuh=40.0, controls=basic_controls)
        assert wh.controls is basic_controls

    def test_from_nominal_capacity_model_name(self, basic_controls):
        wh = WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=40.0, controls=basic_controls, model_name="test_unit",
        )
        assert wh.model_name == "test_unit"

    def test_from_nominal_capacity_no_controls(self):
        wh = WaterHeater.from_nominal_capacity(nominal_capacity_kbtuh=25.0, controls=None)
        assert wh.controls is None
        assert wh.get_capacity_kbtuh(35.0, 120.0) == pytest.approx(25.0)

    def test_from_model_name_is_stub(self, basic_controls):
        """from_model_name is a stub — just verify it exists and is callable."""
        # Should return None (stub body is `pass`) without raising
        result = WaterHeater.from_model_name(model_name="some_model", controls=basic_controls)
        assert result is None  # stub returns None


# ===========================================================================
# _get_peak_indices — module-level helper
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

    def test_temp_ratio_applied(self):
        result = self._sys()._calc_storage_volume_storageT_gal(100.0, 1.0, INLET_T)
        assert result == pytest.approx(100.0 * (SUPPLY_T - INLET_T) / (STORAGE_T - INLET_T), rel=1e-6)

    def test_strat_factor_increases_storage(self):
        sys = self._sys()
        assert sys._calc_storage_volume_storageT_gal(100.0, 0.8, INLET_T) > sys._calc_storage_volume_storageT_gal(100.0, 1.0, INLET_T)

    def test_zero_running_volume(self):
        assert self._sys()._calc_storage_volume_storageT_gal(0.0, 1.0, INLET_T) == 0.0


# ===========================================================================
# _calc_stratification_factor
# ===========================================================================

class TestStratificationFactor:
    def _sys(self):
        return DHWSystem(water_heaters=[], storage_tank=None, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T)

    def test_returns_between_zero_and_one(self):
        assert 0.0 < self._sys()._calc_stratification_factor(0.0, SUPPLY_T) <= 1.0

    def test_lower_aquastat_gives_higher_factor(self):
        sys = self._sys()
        assert sys._calc_stratification_factor(0.0, SUPPLY_T) >= sys._calc_stratification_factor(0.5, SUPPLY_T)

    def test_on_temp_at_storage_gives_factor_one(self):
        assert self._sys()._calc_stratification_factor(0.0, STORAGE_T) == pytest.approx(1.0)


# ===========================================================================
# _warn_if_short_cycling
# ===========================================================================

class TestShortCyclingWarning:
    def _sys(self):
        return DHWSystem(water_heaters=[], storage_tank=None, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T)

    def _controls(self, on_fract, off_fract):
        return Controls(
            on_sensor_fract=on_fract,  on_trigger_t_f=SUPPLY_T,
            off_sensor_fract=off_fract, off_trigger_t_f=STORAGE_T,
        )

    def test_no_warning_with_large_deadband(self):
        """Wide deadband → long cycle time → no warning."""
        sys = self._sys()
        ctrl = self._controls(0.0, 0.9)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            sys._warn_if_short_cycling(ctrl, capacity_kbtuh=20.0, storage_vol_storageT_gal=500.0)

    def test_warning_with_tiny_deadband(self):
        """Tiny deadband → short cycle time → UserWarning."""
        sys = self._sys()
        ctrl = self._controls(0.0, 0.01)  # only 1% of tank between sensors
        with pytest.warns(UserWarning, match="Short cycling"):
            sys._warn_if_short_cycling(ctrl, capacity_kbtuh=200.0, storage_vol_storageT_gal=50.0)

    def test_warning_when_off_below_on(self):
        """off_sensor_fract <= on_sensor_fract emits a different warning."""
        sys = self._sys()
        ctrl = self._controls(0.5, 0.2)  # off below on — heater never shuts off
        with pytest.warns(UserWarning, match="never shut off"):
            sys._warn_if_short_cycling(ctrl, capacity_kbtuh=20.0, storage_vol_storageT_gal=500.0)

    def test_no_warning_when_controls_is_none(self, building_with_zone):
        """size() with controls=None skips the short-cycling check entirely."""
        sys = DHWSystem(water_heaters=[], storage_tank=None, supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            sys.size(building_with_zone, controls=None)  # must not raise

    def test_from_size_emits_warning_for_bad_controls(self, building_with_zone):
        """from_size() propagates the short-cycling warning when controls are tight."""
        bad_ctrl = self._controls(0.0, 0.01)
        with pytest.warns(UserWarning, match="Short cycling"):
            DHWSystem.from_size(
                building=building_with_zone,
                supply_temp_f=SUPPLY_T,
                storage_temp_f=STORAGE_T,
                controls=bad_ctrl,
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
        assert heater.get_capacity_kbtuh(oat_f=35.0, water_temp_f=120.0) == pytest.approx(
            sized_system._minimum_capacity_kbtuh, rel=1e-9
        )

    def test_has_storage_tank(self, sized_system):
        assert isinstance(sized_system.storage_tank, StorageTank)

    def test_storage_tank_volume_matches_minimum(self, sized_system):
        assert sized_system.storage_tank.total_volume_gal == pytest.approx(
            sized_system._minimum_storage_storageT_gal, rel=1e-9
        )

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

    def test_controls_assigned_to_water_heater(self, sized_system_with_controls, basic_controls):
        assert sized_system_with_controls.water_heaters[0].controls is basic_controls

    def test_no_controls_leaves_heater_controls_none(self, sized_system):
        assert sized_system.water_heaters[0].controls is None

    def test_controls_on_sensor_fract_affects_sizing(self, building_with_zone):
        """A higher aquastat reduces the strat factor and requires more storage."""
        ctrl_low  = Controls(on_sensor_fract=0.0, on_trigger_t_f=SUPPLY_T, off_sensor_fract=0.8, off_trigger_t_f=STORAGE_T)
        ctrl_high = Controls(on_sensor_fract=0.5, on_trigger_t_f=SUPPLY_T, off_sensor_fract=0.9, off_trigger_t_f=STORAGE_T)
        sys_low  = DHWSystem.from_size(building_with_zone, SUPPLY_T, STORAGE_T, controls=ctrl_low)
        sys_high = DHWSystem.from_size(building_with_zone, SUPPLY_T, STORAGE_T, controls=ctrl_high)
        assert sys_high._minimum_storage_storageT_gal >= sys_low._minimum_storage_storageT_gal


# ===========================================================================
# from_components() factory
# ===========================================================================

class TestFromComponents:
    def _make_heater(self, capacity_kbtuh=50.0):
        return WaterHeater.from_nominal_capacity(capacity_kbtuh, controls=None)

    def test_returns_dhw_system(self):
        assert isinstance(
            DHWSystem.from_components(500.0, [self._make_heater()], SUPPLY_T, STORAGE_T),
            DHWSystem,
        )

    def test_storage_tank_volume(self):
        system = DHWSystem.from_components(500.0, [self._make_heater()], SUPPLY_T, STORAGE_T)
        assert system.storage_tank.total_volume_gal == pytest.approx(500.0)

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
        system = DHWSystem.from_components(100.0, [WaterHeater(None, None)], SUPPLY_T, STORAGE_T)
        assert system.supply_temp_f  == SUPPLY_T
        assert system.storage_temp_f == STORAGE_T
