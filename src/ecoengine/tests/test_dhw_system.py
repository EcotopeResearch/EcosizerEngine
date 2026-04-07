"""
Unit tests for DHWSystem — sizing calculations and factory constructors.

Tests cover:
- Minimum capacity calculation (_calc_required_capacity)
- Running volume calculation (_calc_running_volume_supplyT_gal)
- Storage volume calculation (_calc_storage_volume_storageT_gal)
- Stratification factor calculation (_calc_stratification_factor)
- from_size() factory: correct types, sizing results stored
- from_components() factory: correct storage volume and heater list
- size() guard: raises when no design inlet temp available
"""

import pytest
import numpy as np

from ecoengine.objects.building.Building import Building
from ecoengine.objects.building.ClimateZone import ClimateZone
from ecoengine.objects.dhwsystems.DHWSystem import DHWSystem, _RHO_CP, _get_peak_indices
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.storage.StorageTank import StorageTank


# ===========================================================================
# Fixtures
# ===========================================================================

SUPPLY_T  = 120.0   # °F  — typical DHW supply temperature
STORAGE_T = 150.0   # °F  — typical HPWH storage temperature
INLET_T   = 50.0    # °F  — design cold-water inlet temperature


@pytest.fixture
def building_with_zone():
    """Multi-family building with a design-condition ClimateZone."""
    zone = ClimateZone.from_design_conditions(
        design_oat_f=35.0,
        design_inlet_water_temp_f=INLET_T,
    )
    return Building.from_building_type(
        building_type='multi_family',
        magnitude=100,
        climate_zone=zone,
        gpdpp=25,
    )


@pytest.fixture
def building_no_zone():
    """Multi-family building with no ClimateZone (no design temps available)."""
    return Building.from_building_type(
        building_type='multi_family',
        magnitude=100,
        climate_zone=None,
        gpdpp=25,
    )


@pytest.fixture
def sized_system(building_with_zone):
    """DHWSystem built via from_size() against the standard test building."""
    return DHWSystem.from_size(
        building=building_with_zone,
        supply_temp_f=SUPPLY_T,
        storage_temp_f=STORAGE_T,
    )


# ===========================================================================
# _get_peak_indices — module-level helper
# ===========================================================================

class TestGetPeakIndices:
    def test_single_transition(self):
        # surplus for first 3 hours, deficit the rest
        diff = np.array([1.0, 1.0, 1.0, -1.0, -1.0])
        assert _get_peak_indices(diff) == [3]

    def test_multiple_transitions(self):
        diff = np.array([1.0, -1.0, 1.0, -1.0])
        assert _get_peak_indices(diff) == [1, 3]

    def test_all_surplus(self):
        diff = np.array([1.0, 2.0, 3.0])
        assert _get_peak_indices(diff) == []

    def test_all_deficit(self):
        # Already in deficit from the start — the wrap-around index 0 triggers
        # because diff[-1] (last element = negative) is < 0 after diff[0] also < 0
        # Actually: diff[-1] = -3.0 >= 0? No. So no transition.
        diff = np.array([-1.0, -2.0, -3.0])
        assert _get_peak_indices(diff) == []

    def test_wraparound_transition(self):
        # Ends positive, starts negative → transition at index 0
        diff = np.array([-1.0, 1.0, 1.0])
        assert _get_peak_indices(diff) == [0]


# ===========================================================================
# _calc_required_capacity — sizing formula
# ===========================================================================

class TestCalcRequiredCapacity:
    def test_formula(self, building_with_zone):
        """Verify capacity matches the hand-calculated formula."""
        daily_gal     = building_with_zone.daily_dhw_use_supplyT_gal
        max_run_hr    = 16.0
        defrost       = 0.95
        delta_t       = SUPPLY_T - INLET_T

        expected_kbtuh = (daily_gal / max_run_hr) * _RHO_CP * delta_t / defrost / 1000

        system = DHWSystem(
            water_heaters=[],
            storage_tank=None,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
            max_daily_run_hr=max_run_hr,
            defrost_factor=defrost,
        )
        result = system._calc_required_capacity(building_with_zone)

        assert result == pytest.approx(expected_kbtuh, rel=1e-6)

    def test_max_run_24hr(self, building_with_zone):
        """At 24 hr/day run time the capacity is minimized."""
        system_24 = DHWSystem(
            water_heaters=[], storage_tank=None,
            supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T,
            max_daily_run_hr=24.0,
        )
        system_16 = DHWSystem(
            water_heaters=[], storage_tank=None,
            supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T,
            max_daily_run_hr=16.0,
        )
        cap_24 = system_24._calc_required_capacity(building_with_zone)
        cap_16 = system_16._calc_required_capacity(building_with_zone)
        assert cap_24 < cap_16

    def test_raises_without_design_inlet_temp(self, building_no_zone):
        """Should raise ValueError when no inlet temp is available."""
        system = DHWSystem(
            water_heaters=[], storage_tank=None,
            supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T,
        )
        with pytest.raises(ValueError, match="design inlet water temperature"):
            system._calc_required_capacity(building_no_zone)


# ===========================================================================
# _calc_running_volume_supplyT_gal
# ===========================================================================

class TestCalcRunningVolume:
    def test_returns_nonnegative(self, building_with_zone):
        """Running volume is always >= 0."""
        system = DHWSystem(
            water_heaters=[], storage_tank=None,
            supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T,
        )
        cap = system._calc_required_capacity(building_with_zone)
        vol = system._calc_running_volume_supplyT_gal(building_with_zone, cap)
        assert vol >= 0.0

    def test_flat_load_shape_zero_running_volume(self):
        """A perfectly flat load shape has no peak, so running volume = 0."""
        # Build a building whose load shape is uniform (1/24 each hour)
        zone = ClimateZone.from_design_conditions(
            design_oat_f=35.0,
            design_inlet_water_temp_f=INLET_T,
        )
        building = Building.from_building_type(
            building_type='multi_family',
            magnitude=100,
            climate_zone=zone,
            gpdpp=25,
        )
        # Override load shape to perfectly flat
        flat_shape = np.full(24, 1.0 / 24)
        building.peak_load_shape = flat_shape

        system = DHWSystem(
            water_heaters=[], storage_tank=None,
            supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T,
            max_daily_run_hr=24.0,
        )
        cap = system._calc_required_capacity(building)
        vol = system._calc_running_volume_supplyT_gal(building, cap)
        assert vol == pytest.approx(0.0, abs=1e-6)

    def test_running_volume_decreases_with_run_hour_restriction(self, building_with_zone):
        """Restricting run hours raises the generation rate, which covers peak demand
        more easily — so less storage is needed. Counterintuitively, vol_8 < vol_24."""
        system_24 = DHWSystem(
            water_heaters=[], storage_tank=None,
            supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T,
            max_daily_run_hr=24.0,
        )
        system_8 = DHWSystem(
            water_heaters=[], storage_tank=None,
            supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T,
            max_daily_run_hr=8.0,
        )
        cap_24 = system_24._calc_required_capacity(building_with_zone)
        cap_8  = system_8._calc_required_capacity(building_with_zone)
        vol_24 = system_24._calc_running_volume_supplyT_gal(building_with_zone, cap_24)
        vol_8  = system_8._calc_running_volume_supplyT_gal(building_with_zone, cap_8)
        assert vol_24 > vol_8


# ===========================================================================
# _calc_storage_volume_storageT_gal
# ===========================================================================

class TestCalcStorageVolume:
    def _make_system(self, **kwargs):
        defaults = dict(
            water_heaters=[], storage_tank=None,
            supply_temp_f=SUPPLY_T, storage_temp_f=STORAGE_T,
        )
        defaults.update(kwargs)
        return DHWSystem(**defaults)

    def test_temp_ratio_applied(self):
        """Storage volume > running volume when storage > supply."""
        system = self._make_system()
        # With strat_factor = 1.0 the only change is the temperature ratio
        temp_ratio = (SUPPLY_T - INLET_T) / (STORAGE_T - INLET_T)
        running_vol = 100.0
        expected = running_vol * temp_ratio / 1.0
        result = system._calc_storage_volume_storageT_gal(running_vol, 1.0, INLET_T)
        assert result == pytest.approx(expected, rel=1e-6)

    def test_strat_factor_increases_storage(self):
        """A lower strat factor (more mixing) requires a larger tank."""
        system = self._make_system()
        vol_ideal    = system._calc_storage_volume_storageT_gal(100.0, 1.0, INLET_T)
        vol_imperfect = system._calc_storage_volume_storageT_gal(100.0, 0.8, INLET_T)
        assert vol_imperfect > vol_ideal

    def test_zero_running_volume(self):
        """Zero running volume → zero storage required."""
        system = self._make_system()
        assert system._calc_storage_volume_storageT_gal(0.0, 1.0, INLET_T) == 0.0


# ===========================================================================
# _calc_stratification_factor
# ===========================================================================

class TestStratificationFactor:
    def _make_system(self, supply=SUPPLY_T, storage=STORAGE_T):
        return DHWSystem(
            water_heaters=[], storage_tank=None,
            supply_temp_f=supply, storage_temp_f=storage,
        )

    def test_returns_between_zero_and_one(self):
        system = self._make_system()
        factor = system._calc_stratification_factor(on_fract=0.0, on_temp_f=SUPPLY_T)
        assert 0.0 < factor <= 1.0

    def test_lower_aquastat_raises_factor(self):
        """An aquastat closer to the bottom means more of the tank is usable."""
        system = self._make_system()
        factor_low  = system._calc_stratification_factor(on_fract=0.0,  on_temp_f=SUPPLY_T)
        factor_high = system._calc_stratification_factor(on_fract=0.5,  on_temp_f=SUPPLY_T)
        assert factor_low >= factor_high

    def test_on_temp_at_or_above_storage_gives_factor_one(self):
        """When on_temp_f >= storage_temp_f the entire tank above the aquastat is
        fully hot, so the stratification factor equals 1.0."""
        system = self._make_system()
        factor = system._calc_stratification_factor(on_fract=0.0, on_temp_f=STORAGE_T)
        assert factor == pytest.approx(1.0)


# ===========================================================================
# from_size() factory
# ===========================================================================

class TestFromSize:
    def test_returns_dhw_system(self, building_with_zone):
        system = DHWSystem.from_size(
            building=building_with_zone,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
        )
        assert isinstance(system, DHWSystem)

    def test_has_one_water_heater(self, sized_system):
        assert len(sized_system.water_heaters) == 1
        assert isinstance(sized_system.water_heaters[0], WaterHeater)

    def test_water_heater_holds_minimum_capacity(self, sized_system):
        heater = sized_system.water_heaters[0]
        assert heater.nominal_capacity_kbtuh == pytest.approx(
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
            DHWSystem.from_size(
                building=building_no_zone,
                supply_temp_f=SUPPLY_T,
                storage_temp_f=STORAGE_T,
            )

    def test_building_not_modified_after_sizing(self, building_with_zone):
        """from_size() must leave the building's load shape state unchanged."""
        was_annual = building_with_zone.is_annual_load_shape()
        DHWSystem.from_size(
            building=building_with_zone,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
        )
        assert building_with_zone.is_annual_load_shape() == was_annual

    def test_sizing_with_annual_load_shape(self, building_with_zone):
        """from_size() should also work when building is in annual-shape mode
        and leave it in annual-shape mode afterwards."""
        building_with_zone.set_to_annual_load_shape()
        system = DHWSystem.from_size(
            building=building_with_zone,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
        )
        assert building_with_zone.is_annual_load_shape()
        assert system._minimum_capacity_kbtuh > 0

    def test_higher_run_hours_gives_less_capacity(self, building_with_zone):
        """More run hours → lower capacity required."""
        sys_8  = DHWSystem.from_size(building_with_zone, SUPPLY_T, STORAGE_T, max_daily_run_hr=8.0)
        sys_24 = DHWSystem.from_size(building_with_zone, SUPPLY_T, STORAGE_T, max_daily_run_hr=24.0)
        assert sys_24._minimum_capacity_kbtuh < sys_8._minimum_capacity_kbtuh

    def test_temperature_params_stored(self, sized_system):
        assert sized_system.supply_temp_f  == SUPPLY_T
        assert sized_system.storage_temp_f == STORAGE_T


# ===========================================================================
# from_components() factory
# ===========================================================================

class TestFromComponents:
    def test_returns_dhw_system(self):
        heaters = [WaterHeater(performance_map=None, controls=None, nominal_capacity_kbtuh=50.0)]
        system = DHWSystem.from_components(
            storage_volume_storageT_gal=500.0,
            water_heaters=heaters,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
        )
        assert isinstance(system, DHWSystem)

    def test_storage_tank_volume(self):
        heaters = [WaterHeater(performance_map=None, controls=None, nominal_capacity_kbtuh=50.0)]
        system = DHWSystem.from_components(
            storage_volume_storageT_gal=500.0,
            water_heaters=heaters,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
        )
        assert system.storage_tank.total_volume_gal == pytest.approx(500.0)

    def test_water_heater_list_preserved(self):
        h1 = WaterHeater(performance_map=None, controls=None, nominal_capacity_kbtuh=30.0)
        h2 = WaterHeater(performance_map=None, controls=None, nominal_capacity_kbtuh=20.0)
        system = DHWSystem.from_components(
            storage_volume_storageT_gal=300.0,
            water_heaters=[h1, h2],
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
        )
        assert len(system.water_heaters) == 2
        assert system.water_heaters[0].nominal_capacity_kbtuh == pytest.approx(30.0)
        assert system.water_heaters[1].nominal_capacity_kbtuh == pytest.approx(20.0)

    def test_sizing_results_none_when_no_size_called(self):
        """from_components bypasses sizing; sizing fields stay None."""
        heaters = [WaterHeater(performance_map=None, controls=None, nominal_capacity_kbtuh=50.0)]
        system = DHWSystem.from_components(
            storage_volume_storageT_gal=500.0,
            water_heaters=heaters,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
        )
        assert system._minimum_capacity_kbtuh is None
        assert system._minimum_storage_storageT_gal is None

    def test_get_minimum_capacity_raises_before_sizing(self):
        heaters = [WaterHeater(performance_map=None, controls=None, nominal_capacity_kbtuh=50.0)]
        system = DHWSystem.from_components(
            storage_volume_storageT_gal=500.0,
            water_heaters=heaters,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
        )
        with pytest.raises(RuntimeError):
            system.get_minimum_capacity_kbtuh()

    def test_temperature_params_stored(self):
        heaters = [WaterHeater(performance_map=None, controls=None)]
        system = DHWSystem.from_components(
            storage_volume_storageT_gal=100.0,
            water_heaters=heaters,
            supply_temp_f=SUPPLY_T,
            storage_temp_f=STORAGE_T,
        )
        assert system.supply_temp_f  == SUPPLY_T
        assert system.storage_temp_f == STORAGE_T
