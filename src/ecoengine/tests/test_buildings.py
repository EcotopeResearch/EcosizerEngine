"""
Unit tests for Building.from_building_type() and the Building object.

Ported from EcosizerEngine/src/ecoengine/tests/test_buildings.py.

Architecture notes (why some assertions differ from the original):
- incomingT_F, supplyT_F   → moved to DHWSystem / ClimateZone; not on Building
- recirc_loss               → moved to RecircSystem; not on Building
- building.magnitude        → now building.daily_dhw_use_supplyT_gal
- building.loadshape        → now building.peak_load_shape
- building.avgLoadshape     → now building.avg_load_shape
- climate zone / zip code   → ClimateZone object (not yet implemented); placeholder tests marked accordingly
- annual load shapes        → set_to_annual_load_shape() / is_annual_load_shape() on Building
- multi-use buildings       → not yet implemented; placeholder tests marked accordingly
"""

import pytest
import numpy as np
from ecoengine.objects.building.Building import Building, _validate_load_shape
from ecoengine.objects.building.ClimateZone import ClimateZone


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def multi_family():
    return Building.from_building_type(
        building_type = 'multi_family',
        magnitude     = 100,
        climate_zone  = None,
        gpdpp         = 25,
    )

@pytest.fixture
def multi_family_with_bedrooms():
    return Building.from_building_type(
        building_type = 'multi_family',
        magnitude     = 100,
        climate_zone  = None,
        standard_gpd  = 'ca',
        n_br          = [0, 1, 5, 3, 2, 0],
    )

@pytest.fixture
def nursing_home_and_office():
    return Building.from_building_type(
        building_type = ['nursing_home', 'office_building'],
        magnitude     = [100, 75],
        climate_zone  = None,
    )


# ===========================================================================
# Multi-family basic results
# Originally: test_multiFamilyResults
# Changed: magnitude → daily_dhw_use_supplyT_gal
#          incomingT_F / supplyT_F / recirc_loss removed (not Building fields)
# ===========================================================================

def test_multi_family_daily_use(multi_family):
    assert multi_family.daily_dhw_use_supplyT_gal == 2500
    assert len(multi_family.peak_load_shape) == 24
    assert abs(sum(multi_family.peak_load_shape) - 1.0) < 1e-6


# ===========================================================================
# Multi-family with CA bedroom-based GPD
# Originally: test_multiFamilyWithBedroomsResults
# Changed: magnitude → daily_dhw_use_supplyT_gal; recirc / temps removed
# ===========================================================================

def test_multi_family_with_bedrooms_daily_use(multi_family_with_bedrooms):
    assert multi_family_with_bedrooms.daily_dhw_use_supplyT_gal == 2350.0
    assert len(multi_family_with_bedrooms.peak_load_shape) == 24


# ===========================================================================
# Multi-use results
# Originally: test_multiUseResults
# PLACEHOLDER — multi-use buildings not yet implemented
# ===========================================================================

def test_multi_use_results(nursing_home_and_office):
    b = nursing_home_and_office
    assert round(b.daily_dhw_use_supplyT_gal, 1) == 2497.5
    assert len(b.peak_load_shape) == 24
    assert abs(sum(b.peak_load_shape) - 1.0) < 1e-6


# ===========================================================================
# Magnitudes — standard single building types
# Originally: test_magnitudes (subset of non-multi-use, non-None-type rows)
# ===========================================================================

@pytest.mark.parametrize("building_type, magnitude, expected_gal", [
    ("apartment",        100, 5460.0),
    ("elementary_school",100,  134.0),
    ("food_service_a",   100, 1103.2),
    ("food_service_b",   100,  644.0),
    ("junior_high",      100,  375.0),
    ("mens_dorm",        100, 2360.0),
    ("motel",            100, 2140.0),
    ("nursing_home",     100, 2340.0),
    ("office_building",  100,  210.0),
    ("senior_high",      100,  326.0),
    ("womens_dorm",      100, 1960.0),
])
def test_magnitudes_standard_types(building_type, magnitude, expected_gal):
    b = Building.from_building_type(building_type, magnitude, climate_zone=None)
    assert round(b.daily_dhw_use_supplyT_gal, 1) == expected_gal


# Originally: test_magnitudes row — (None, [0,...,1,...], [100], 100)
# building_type=None with explicit magnitude and normalized custom load shape.
# In new arch, use Building() constructor directly (no named building type).
def test_magnitude_custom_loadshape_explicit():
    custom = [0]*8 + [1] + [0]*15   # normalized, sums to 1
    b = Building(
        climate_zone              = None,
        daily_dhw_use_supplyT_gal = 100,
        peak_load_shape           = np.array(custom),
        avg_load_shape            = np.array(custom),
    )
    assert round(b.daily_dhw_use_supplyT_gal, 1) == 100


# Originally: test_magnitudes row — (None, [0,...,100,50,...], None, 150)
# building_type=None, magnitude derived from sum of unnormalized load shape.
# In new arch, caller is responsible for computing magnitude = sum(raw_shape)
# and normalizing the shape before passing to Building().
def test_magnitude_derived_from_unnormalized_loadshape():
    raw    = [0]*8 + [100, 50] + [0]*14   # sums to 150
    total  = sum(raw)
    normed = np.array([x / total for x in raw])
    b = Building(
        climate_zone              = None,
        daily_dhw_use_supplyT_gal = float(total),
        peak_load_shape           = normed,
        avg_load_shape            = normed,
    )
    assert round(b.daily_dhw_use_supplyT_gal, 1) == 150.0


# For the ["office_building", None] case the None slot requires a custom load shape.
_CUSTOM_SHAPE_FOR_NONE = [0]*8 + [100, 50] + [0]*14  # sums to 150, unnormalized → derived gal

@pytest.mark.parametrize("building_types, magnitudes, custom_peak, expected_gal", [
    (["office_building", None], [100, None],
     [None, _CUSTOM_SHAPE_FOR_NONE], 360.0),
    (["womens_dorm", "junior_high"], [100, 5],
     None, 1978.8),
])
def test_magnitudes_multi_use(building_types, magnitudes, custom_peak, expected_gal):
    b = Building.from_building_type(
        building_types, magnitudes, climate_zone=None,
        custom_peak_load_shape=custom_peak,
    )
    assert round(b.daily_dhw_use_supplyT_gal, 1) == expected_gal


# ===========================================================================
# Default load shapes — first 3 elements of peak_load_shape
# Originally: test_default_loadshapes
# ===========================================================================

@pytest.mark.parametrize("building_type, magnitude, expected_first_3", [
    ("apartment", 100, np.array([0.046728972, 0.044392523, 0.037383178])),
])
def test_default_load_shapes_single_type(building_type, magnitude, expected_first_3):
    b = Building.from_building_type(building_type, magnitude, climate_zone=None)
    assert np.array_equal(
        np.round(b.peak_load_shape[:3], decimals=5),
        np.round(expected_first_3, decimals=5),
    )


@pytest.mark.parametrize("building_types, magnitudes, expected_first_3", [
    (["food_service_a", "nursing_home"], [100, 50],  np.array([0.,      0.00256, 0.00256])),
    (["womens_dorm",    "junior_high"],  [100, 5],   np.array([0.30202, 0.12085, 0.0363])),
    (["womens_dorm",    "junior_high"],  [5,   100], np.array([0.06559, 0.03012, 0.01243])),
    (["womens_dorm", "junior_high", "food_service_a", "nursing_home", "apartment"],
     [5, 100, 50, 200, 500], np.array([0.03959, 0.03786, 0.03181])),
])
def test_default_load_shapes_multi_use(building_types, magnitudes, expected_first_3):
    b = Building.from_building_type(building_types, magnitudes, climate_zone=None)
    assert np.array_equal(
        np.round(b.peak_load_shape[:3], decimals=5),
        np.round(expected_first_3, decimals=5),
    )


# ===========================================================================
# Custom load shapes
# Originally: test_custom_loadshapes
# ===========================================================================

def test_custom_loadshape_with_building_type():
    # Original: ([1,0,...], "apartment", 100) → loadshape[:3] = [1, 0, 0]
    custom = [1] + [0]*23
    b = Building.from_building_type(
        'apartment', 100, climate_zone=None,
        custom_peak_load_shape=custom,
    )
    assert np.array_equal(np.round(b.peak_load_shape[:3], 5), np.array([1, 0, 0]))


def test_custom_loadshape_no_building_type():
    # Original: ([1,0,...], None, 100) → loadshape[:3] = [1, 0, 0]
    # In new arch, use Building() constructor directly.
    custom = np.array([1] + [0]*23, dtype=float)
    b = Building(
        climate_zone              = None,
        daily_dhw_use_supplyT_gal = 100,
        peak_load_shape           = custom,
        avg_load_shape            = custom,
    )
    assert np.array_equal(np.round(b.peak_load_shape[:3], 5), np.array([1, 0, 0]))


def test_custom_loadshape_multi_use():
    # womens_dorm: 5 students → 5 * 19.6 = 98 gal; shape [1, 0, ...]
    # junior_high: 100 students → 100 * 3.75 = 375 gal; shape [0, 1, 0, ...]
    # blended[0] = (98*1 + 375*0) / 473 ≈ 0.20719
    # blended[1] = (98*0 + 375*1) / 473 ≈ 0.79281
    custom_shapes = [[1] + [0]*23, [0, 1] + [0]*22]
    b = Building.from_building_type(
        ["womens_dorm", "junior_high"], [5, 100],
        climate_zone=None,
        custom_peak_load_shape=custom_shapes,
    )
    assert np.array_equal(
        np.round(b.peak_load_shape[:3], decimals=5),
        np.array([0.20719, 0.79281, 0.]),
    )


# ===========================================================================
# Annual load shapes
# ===========================================================================

def test_annual_ls_for_multi_family(multi_family_with_bedrooms):
    # Starts as a 24-hour daily shape
    assert len(multi_family_with_bedrooms.peak_load_shape) == 24
    assert len(multi_family_with_bedrooms.avg_load_shape)  == 24
    assert not multi_family_with_bedrooms.is_annual_load_shape()

    # Switch to annual — both shapes become the same 8760-element array
    multi_family_with_bedrooms.set_to_annual_load_shape()
    assert len(multi_family_with_bedrooms.peak_load_shape) == 8760
    assert len(multi_family_with_bedrooms.avg_load_shape)  == 8760
    assert multi_family_with_bedrooms.is_annual_load_shape()
    assert np.array_equal(
        multi_family_with_bedrooms.peak_load_shape,
        multi_family_with_bedrooms.avg_load_shape,
    )

    # Switch back to daily — shapes restore independently
    multi_family_with_bedrooms.set_to_daily_load_shape()
    assert len(multi_family_with_bedrooms.peak_load_shape) == 24
    assert not multi_family_with_bedrooms.is_annual_load_shape()


def test_annual_ls_for_non_multi_family(nursing_home_and_office):
    # Non-multifamily buildings cannot use annual load shapes
    assert not nursing_home_and_office.is_annual_load_shape()
    with pytest.raises(ValueError, match="only available for multi_family"):
        nursing_home_and_office.set_to_annual_load_shape()
    # Shape unchanged after failed call
    assert len(nursing_home_and_office.peak_load_shape) == 24


def test_annual_ls_from_instantiation():
    # annual=True on from_building_type immediately loads the 8760 shape
    building = Building.from_building_type('multi_family', 100, None, annual=True)
    assert building.is_annual_load_shape()
    assert len(building.peak_load_shape) == 8760

    # non-multifamily with annual=True should raise
    with pytest.raises(ValueError, match="only available for multi_family"):
        Building.from_building_type('apartment', 100, None, annual=True)


def test_dhw_load_annual_shape_uses_yearly_index():
    """
    With an annual load shape, hour index into the 8760-element array directly
    rather than wrapping at 24. Hour 25 (day 2 hour 1) should differ from
    hour 1 (day 1 hour 1) if the annual shape varies day-to-day.
    """
    building = Building.from_building_type('multi_family', 100, None, annual=True)
    assert building.is_annual_load_shape()

    # The annual shape does vary by day, so hour 1 and hour 25 are different
    load_hour1  = building.get_dhw_load_supplyT_gal(1  * 60, interval_min=1)
    load_hour25 = building.get_dhw_load_supplyT_gal(25 * 60, interval_min=1)
    assert load_hour1 != pytest.approx(load_hour25, rel=1e-3)

    # Summing all 8760 one-hour intervals gives daily_gal * sum(annual_shape)
    annual_sum = sum(
        building.get_dhw_load_supplyT_gal(h, interval_min=60)
        for h in range(8760)
    )
    expected = building.daily_dhw_use_supplyT_gal * sum(building.peak_load_shape)
    assert annual_sum == pytest.approx(expected, rel=1e-6)


# ===========================================================================
# Climate zone / zip code lookups
# PLACEHOLDER — ClimateZone not yet implemented
# ===========================================================================

@pytest.mark.parametrize("zip_code, expected_climate_zone, building_type, magnitude", [
    (94922,  1,    "apartment",                      100),
    (94565,  12,   ["womens_dorm", "junior_high"],   [100, 50]),
    (None,   None, "multi_family",                   100),
])
def test_zip_codes_to_climate_zones(zip_code, expected_climate_zone, building_type, magnitude):
    climate_zone = ClimateZone.from_zip_code(zip_code) if zip_code is not None else None
    building = Building.from_building_type(building_type, magnitude, climate_zone)

    if expected_climate_zone is None:
        assert building.climate_zone is None
    else:
        assert building.climate_zone.zone_id == expected_climate_zone


@pytest.mark.parametrize("zip_code, design_oat, building_type, magnitude, expected_oat", [
    # Real climate zone (zip 94565 → zone 12): design OAT is the annual minimum
    (94565, None, ["womens_dorm", "junior_high"], [100, 50], 26.96),
    # No climate zone, explicit design OAT: constant-value dummy zone is created
    (None,  17.0, "apartment",                    100,       17.0),
    # No climate zone, no design OAT: no climate data at all → None
    (None,  None, "multi_family",                 100,       None),
])
def test_design_oat(zip_code, design_oat, building_type, magnitude, expected_oat):
    climate_zone = ClimateZone.from_zip_code(zip_code) if zip_code is not None else None
    building = Building.from_building_type(
        building_type, magnitude, climate_zone, design_oat_f=design_oat
    )

    result = building.get_design_oat_f()
    if expected_oat is None:
        assert result is None
    else:
        assert result == pytest.approx(expected_oat, rel=1e-3)


@pytest.mark.parametrize("climate_zone, jan_in_t, sep_in_t, oct_in_t", [
    (1,  50.108, 54.734, 54.59),
    (6,  59.306, 65.876, 64.742),
    (18, 46.9,   61.0,   58.6),
])
def test_climate_zone_temps(climate_zone, jan_in_t, sep_in_t, oct_in_t):
    cz = ClimateZone.from_zone_id(climate_zone)

    # Inlet water temperature is stored per-month; query via a representative
    # 1-minute-interval timestep at the start of each month.
    # interval_min defaults to 1, so timestep_interval == elapsed minutes.
    jan_start = 0                    # Jan 1, 00:00  (minute 0)
    sep_start = 243 * 24 * 60        # Sep 1, 00:00  (minute 349,920)
    oct_start = 273 * 24 * 60        # Oct 1, 00:00  (minute 393,120)

    assert cz.get_inlet_water_temp_f(jan_start) == pytest.approx(jan_in_t, rel=1e-4)
    assert cz.get_inlet_water_temp_f(jan_start/6, 6) == pytest.approx(jan_in_t, rel=1e-4)
    assert cz.get_inlet_water_temp_f(sep_start) == pytest.approx(sep_in_t, rel=1e-4)
    assert cz.get_inlet_water_temp_f(sep_start/15, 15) == pytest.approx(sep_in_t, rel=1e-4)
    assert cz.get_inlet_water_temp_f(oct_start) == pytest.approx(oct_in_t, rel=1e-4)
    assert cz.get_inlet_water_temp_f(oct_start/20, 20) == pytest.approx(oct_in_t, rel=1e-4)


# ===========================================================================
# Design-condition (constant) ClimateZone
# ===========================================================================

def test_design_condition_zone_oat():
    """from_design_conditions creates a zone that always returns the given OAT."""
    cz = ClimateZone.from_design_conditions(design_oat_f=15.0)

    # Every timestep returns the same constant, regardless of time
    assert cz.get_oat_f(0)           == 15.0
    assert cz.get_oat_f(100 * 60)    == 15.0
    assert cz.get_oat_f(4380 * 60)   == 15.0
    assert cz.get_oat_f(100, interval_min=60) == 15.0
    assert cz.get_design_oat_f()     == 15.0


def test_design_condition_zone_inlet_water_temp():
    """from_design_conditions creates a zone that always returns the given inlet temp."""
    cz = ClimateZone.from_design_conditions(design_inlet_water_temp_f=55.0)

    assert cz.get_inlet_water_temp_f(0)         == 55.0
    assert cz.get_inlet_water_temp_f(243 * 24 * 60) == 55.0  # September
    assert cz.get_design_inlet_water_temp_f()   == 55.0


def test_design_condition_zone_both():
    """from_design_conditions handles both conditions at once."""
    cz = ClimateZone.from_design_conditions(design_oat_f=20.0, design_inlet_water_temp_f=48.0)
    assert cz.get_oat_f(0)               == 20.0
    assert cz.get_inlet_water_temp_f(0)  == 48.0
    assert cz.get_design_oat_f()         == 20.0
    assert cz.get_design_inlet_water_temp_f() == 48.0
    assert cz.zone_id is None


def test_building_creates_dummy_zone_from_design_conditions():
    """
    Building creates a constant ClimateZone automatically when no real zone is
    given but design_oat_f or design_inlet_water_temp_f are provided.
    """
    building = Building.from_building_type(
        'apartment', 100, climate_zone=None,
        design_oat_f=12.0, design_inlet_water_temp_f=50.0,
    )
    assert building.climate_zone is not None
    assert building.climate_zone.zone_id is None

    # OAT and inlet water queries return the constants at any timestep
    assert building.get_oat_f(0)                  == 12.0
    assert building.get_oat_f(4380 * 60)           == 12.0
    assert building.get_inlet_water_temp_f(0)      == 50.0
    assert building.get_inlet_water_temp_f(243 * 24 * 60) == 50.0

    # Design condition queries also return the constants
    assert building.get_design_oat_f()             == 12.0
    assert building.get_design_inlet_water_temp_f() == 50.0


def test_building_no_dummy_zone_when_real_zone_provided():
    """
    When a real ClimateZone is given, design_oat_f is ignored — the real zone
    takes precedence and its data is used for both simulation and design queries.
    """
    real_zone = ClimateZone.from_zip_code(94565)  # zone 12
    building  = Building.from_building_type(
        'apartment', 100, climate_zone=real_zone, design_oat_f=999.0
    )
    # The real zone is stored, not the design-condition constant
    assert building.climate_zone is real_zone
    assert building.get_design_oat_f() == pytest.approx(26.96, rel=1e-3)


# ===========================================================================
# Outdoor air temperature lookups
# ===========================================================================

@pytest.mark.parametrize("climate_zone, h0_oat, h100_oat, h4380_oat", [
    (1,  35.06, 41.0,  64.04),
    (6,  53.96, 46.04, 71.96),
    (18, 37.4,  21.4,  68.0),
])
def test_climate_zone_oat(climate_zone, h0_oat, h100_oat, h4380_oat):
    cz = ClimateZone.from_zone_id(climate_zone)

    # OAT data is hourly; query at the first minute of hours 0, 100, and 4380.
    # interval_min defaults to 1, so timestep_interval == elapsed minutes.
    assert cz.get_oat_f(0)         == pytest.approx(h0_oat,   rel=1e-4)
    assert cz.get_oat_f(100 * 60)  == pytest.approx(h100_oat, rel=1e-4)
    assert cz.get_oat_f(4380 * 60) == pytest.approx(h4380_oat, rel=1e-4)

    # Same OAT regardless of how interval_min is set, as long as the actual
    # minute is the same.
    assert cz.get_oat_f(100 * 6,  10) == pytest.approx(h100_oat,  rel=1e-4)  # 10-min intervals
    assert cz.get_oat_f(100,      60) == pytest.approx(h100_oat,  rel=1e-4)  # hourly intervals
    assert cz.get_oat_f(4380 * 4, 15) == pytest.approx(h4380_oat, rel=1e-4)  # 15-min intervals


# ===========================================================================
# DHW load per timestep
# ===========================================================================

def test_dhw_load_value_at_known_timestep():
    """Verify the per-interval load formula against hand-calculated values."""
    # Apartment, 100 units → 5460 gal/day; peak_load_shape[0] = 0.046728972
    building = Building.from_building_type('apartment', 100, None)
    peak_ls_0 = building.peak_load_shape[0]   # fraction at hour 0
    daily     = building.daily_dhw_use_supplyT_gal  # 5460.0 gal

    # 1-minute interval at hour 0:  daily * shape[0] * (1 min / 60 min per hour)
    assert building.get_dhw_load_supplyT_gal(0, interval_min=1) == pytest.approx(
        daily * peak_ls_0 / 60, rel=1e-9
    )
    # 15-minute interval at hour 0: same shape fraction, scaled up 15×
    assert building.get_dhw_load_supplyT_gal(0, interval_min=15) == pytest.approx(
        daily * peak_ls_0 * 15 / 60, rel=1e-9
    )
    # 60-minute interval at hour 0: full hourly volume
    assert building.get_dhw_load_supplyT_gal(0, interval_min=60) == pytest.approx(
        daily * peak_ls_0, rel=1e-9
    )


@pytest.mark.parametrize("interval_min", [1, 10, 15, 60])
def test_dhw_load_sums_to_daily_total(interval_min):
    """Summing all intervals in a day must equal the daily DHW total."""
    building = Building.from_building_type('apartment', 100, None)
    daily    = building.daily_dhw_use_supplyT_gal

    intervals_per_day = (24 * 60) // interval_min
    total = sum(
        building.get_dhw_load_supplyT_gal(t, interval_min)
        for t in range(intervals_per_day)
    )
    assert total == pytest.approx(daily, rel=1e-6)


def test_dhw_load_interval_min_proportional():
    """
    Two calls at the same actual minute but different interval_min values
    should return loads proportional to interval_min.
    """
    building = Building.from_building_type('nursing_home', 50, None)

    load_1min  = building.get_dhw_load_supplyT_gal(60, interval_min=1)   # minute 60 → hour 1
    load_10min = building.get_dhw_load_supplyT_gal(6,  interval_min=10)  # minute 60 → hour 1
    load_60min = building.get_dhw_load_supplyT_gal(1,  interval_min=60)  # minute 60 → hour 1

    # All three are at the same hour → load scales linearly with interval_min
    assert load_10min == pytest.approx(load_1min  * 10, rel=1e-9)
    assert load_60min == pytest.approx(load_1min  * 60, rel=1e-9)


def test_dhw_load_wraps_at_day_boundary():
    """Minute 1440 (start of day 2) maps to hour 0, same as minute 0."""
    building = Building.from_building_type('motel', 20, None)

    load_day1_hour0 = building.get_dhw_load_supplyT_gal(0,        interval_min=1)
    load_day2_hour0 = building.get_dhw_load_supplyT_gal(24 * 60,  interval_min=1)
    load_day7_hour0 = building.get_dhw_load_supplyT_gal(7 * 24 * 60, interval_min=1)

    assert load_day2_hour0 == pytest.approx(load_day1_hour0, rel=1e-9)
    assert load_day7_hour0 == pytest.approx(load_day1_hour0, rel=1e-9)


def test_dhw_load_use_avg_differs_from_peak():
    """use_avg=True should return avg_load_shape values, not peak."""
    # Apartment's peak and avg shapes differ (confirmed from JSON).
    building = Building.from_building_type('apartment', 100, None)

    # Hour 9 has the largest divergence between peak (0.117) and avg (0.037)
    t_hour9 = 9 * 60  # minute 540 → hour 9

    peak_load = building.get_dhw_load_supplyT_gal(t_hour9, use_avg=False)
    avg_load  = building.get_dhw_load_supplyT_gal(t_hour9, use_avg=True)

    assert peak_load != pytest.approx(avg_load, rel=1e-3)
    # Verify exact values match the stored shapes
    daily = building.daily_dhw_use_supplyT_gal
    assert peak_load == pytest.approx(daily * building.peak_load_shape[9] / 60, rel=1e-9)
    assert avg_load  == pytest.approx(daily * building.avg_load_shape[9]  / 60, rel=1e-9)


# ===========================================================================
# Validation errors for Building.from_building_type
# Originally: test_invalid_building_parameter_errors (subset applicable to Building)
# ===========================================================================

def test_invalid_building_parameter_errors():
    # --- multi_family gpdpp ---
    with pytest.raises(ValueError, match="gpdpp must be a number"):
        Building.from_building_type('multi_family', 4, None, gpdpp=None)

    # --- standard_gpd not a string ---
    with pytest.raises(ValueError, match="standard_gpd must be one of"):
        Building.from_building_type('multi_family', 4, None, gpdpp=25, standard_gpd=5)

    # --- standard_gpd unrecognized string ---
    with pytest.raises(ValueError, match="standard_gpd must be one of"):
        Building.from_building_type('multi_family', 4, None, gpdpp=25, standard_gpd='yabadabado')

    # --- unknown building type ---
    with pytest.raises(ValueError, match="Unrecognized building_type 'climbing_gym'"):
        Building.from_building_type('climbing_gym', 4, None)

    # --- custom peak load shape wrong length ---
    with pytest.raises(ValueError, match="must have 24 elements"):
        Building.from_building_type('mens_dorm', 4, None, custom_peak_load_shape=[1, 2, 3, 4, 5])

    # --- custom peak load shape not normalized ---
    with pytest.raises(ValueError, match="must sum to 1.0"):
        Building.from_building_type('mens_dorm', 4, None,
            custom_peak_load_shape=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24])

    # --- custom peak load shape negative values ---
    with pytest.raises(ValueError, match="cannot contain negative"):
        Building.from_building_type('mens_dorm', 4, None,
            custom_peak_load_shape=[1,2,-3,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])

    # --- custom avg load shape wrong length ---
    with pytest.raises(ValueError, match="must have 24 elements"):
        Building.from_building_type('mens_dorm', 4, None, custom_avg_load_shape=[1, 2, 3, 4, 5])

    # --- custom avg load shape not normalized ---
    with pytest.raises(ValueError, match="must sum to 1.0"):
        Building.from_building_type('mens_dorm', 4, None,
            custom_avg_load_shape=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24])

    # --- custom avg load shape negative values ---
    with pytest.raises(ValueError, match="cannot contain negative"):
        Building.from_building_type('mens_dorm', 4, None,
            custom_avg_load_shape=[1,2,-3,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])

    # --- non-positive magnitude ---
    with pytest.raises(ValueError, match="magnitude must be a positive number"):
        Building.from_building_type('mens_dorm', 0, None)
    with pytest.raises(ValueError, match="magnitude must be a positive number"):
        Building.from_building_type('mens_dorm', -5, None)

    # --- building_type not a string ---
    with pytest.raises(ValueError, match="building_type must be a string"):
        Building.from_building_type(123, 4, None)


# The following error cases from the original live outside Building in the new
# architecture and will be covered in their respective test files:
#
#   nApt / Wapt must be int     → test_systems.py  (RecircSystem)
#   supply / return / flow temp → test_systems.py  (DHWSystem)
#   climate zone / zip code     → test_climate_zone.py  (ClimateZone)
#   designOAT_F                 → test_climate_zone.py  (ClimateZone)
#   multi-use magnitude errors  → test_buildings.py once multi-use is implemented
