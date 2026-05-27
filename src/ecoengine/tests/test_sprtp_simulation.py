"""
Integration tests: SinglePassRTPSystem sizing → 3-day simulation.

Each test case sizes an SPRTP system for a specific building type and
magnitude, then runs a 3-day design-day simulation and asserts that no
DHW outage occurs.  The intent is to catch regressions where the sizing
algorithm produces a system that cannot actually meet demand in simulation.
"""
import pytest

from ecoengine.objects.building.Building import Building
from ecoengine.objects.building.ClimateZone import ClimateZone
from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.dhwsystems.rtp_systems.SinglePassRTPSystem import SinglePassRTPSystem
from ecoengine.interfaces.Simulator import simulate_3day

# ---------------------------------------------------------------------------
# Shared parameters
# ---------------------------------------------------------------------------
_DESIGN_OAT_F   = 47.0   # °F
_DESIGN_INLET_F = 55.0   # °F

_SUPPLY_T   = 120.0   # °F
_STORAGE_T  = 140.0   # °F
_RETURN_T   = 100.0   # °F
_RETURN_GPM = 3.0     # GPM


def _zone() -> ClimateZone:
    return ClimateZone.from_design_conditions(
        design_oat_f=_DESIGN_OAT_F,
        design_inlet_water_temp_f=_DESIGN_INLET_F,
    )


def _default_controls() -> Controls:
    """Normal-mode aquastat: turns ON when mid-tank drops to supply temp,
    OFF when bottom rises to storage temp (tank fully recharged)."""
    return Controls(
        on_sensor_fract=0.5,
        on_trigger_t_f=_SUPPLY_T,
        off_sensor_fract=0.0,
        off_trigger_t_f=_STORAGE_T,
        outlet_temp_f=_STORAGE_T,
    )


def _size_and_simulate(building_type: str, magnitude: int) -> None:
    """Size an SPRTP system for the given building and assert the 3-day sim passes."""
    zone     = _zone()
    building = Building.from_building_type(
        building_type=building_type,
        magnitude=magnitude,
        climate_zone=zone,
    )

    control_map      = {"normal": _default_controls()}
    control_schedule = ["normal"] * 24

    system = SinglePassRTPSystem.from_size(
        building=building,
        supply_temp_f=_SUPPLY_T,
        storage_temp_f=_STORAGE_T,
        return_temp_f=_RETURN_T,
        return_flow_gpm=_RETURN_GPM,
        control_schedule=control_schedule,
        control_map=control_map,
    )

    sim = simulate_3day(system, building)
    assert sim.is_successful(), (
        f"3-day simulation failed for {building_type} magnitude={magnitude}: "
        f"{sim.get_failure_message()}"
    )


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestSPRTPSimulationPasses:
    """
    Integration tests: size → simulate for several building types and
    magnitudes.  Any DHW outage in the 3-day sim is a regression.
    """

    def test_multi_family_small(self):
        """Small multi-family building (50 units)."""
        _size_and_simulate("multi_family", 50)

    def test_multi_family_medium(self):
        """Medium multi-family building (150 units)."""
        _size_and_simulate("multi_family", 150)

    def test_multi_family_large(self):
        """Large multi-family building (400 units)."""
        _size_and_simulate("multi_family", 400)

    def test_apartment_medium(self):
        """Apartment building (100 units)."""
        _size_and_simulate("apartment", 100)

    def test_motel_medium(self):
        """Motel (80 rooms)."""
        _size_and_simulate("motel", 80)

    def test_nursing_home_medium(self):
        """Nursing home (120 beds)."""
        _size_and_simulate("nursing_home", 120)

    def test_office_building_large(self):
        """Large office building (500 occupants)."""
        _size_and_simulate("office_building", 500)


# ---------------------------------------------------------------------------
# Failure cases — deliberately undersized systems must fail the 3-day sim
# ---------------------------------------------------------------------------

def _size_small_simulate_large(building_type: str, small_mag: int, large_mag: int) -> None:
    """Size for small_mag, then run the sim against large_mag — expect failure."""
    zone          = _zone()
    small_building = Building.from_building_type(building_type=building_type, magnitude=small_mag,  climate_zone=zone)
    large_building = Building.from_building_type(building_type=building_type, magnitude=large_mag, climate_zone=zone)

    control_map      = {"normal": _default_controls()}
    control_schedule = ["normal"] * 24

    system = SinglePassRTPSystem.from_size(
        building=small_building,
        supply_temp_f=_SUPPLY_T,
        storage_temp_f=_STORAGE_T,
        return_temp_f=_RETURN_T,
        return_flow_gpm=_RETURN_GPM,
        control_schedule=control_schedule,
        control_map=control_map,
    )

    sim = simulate_3day(system, large_building)
    assert not sim.is_successful(), (
        f"Expected failure for {building_type} sized at {small_mag} but simulated at {large_mag}, "
        f"but simulation passed."
    )


@pytest.mark.filterwarnings("ignore::UserWarning")
class TestSPRTPSimulationFails:
    """
    Integration tests: a severely undersized SPRTP must produce a DHW outage.
    Each case sizes for ~10–20 % of the simulated load.
    """

    def test_multi_family_undersized(self):
        """System sized for 20 units cannot serve 200 units."""
        _size_small_simulate_large("multi_family", 20, 200)

    def test_apartment_undersized(self):
        """System sized for 10 units cannot serve 150 units."""
        _size_small_simulate_large("apartment", 10, 150)

    def test_motel_undersized(self):
        """System sized for 10 rooms cannot serve 100 rooms."""
        _size_small_simulate_large("motel", 10, 100)
