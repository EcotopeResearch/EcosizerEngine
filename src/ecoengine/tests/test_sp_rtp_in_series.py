"""
Unit and integration tests for SP_RTPInSeriesSystem.

These tests serve as a regression guard during the planned refactor that will
move _size_gas_backup(), _gas_backup_from_window(), and get_sizing_curve()
logic into dhwsystems/utils.py as standalone functions.

Test groups
-----------
TestFromSize            — construction and component sanity after from_size()
TestOutageArrays        — outage_volume_gal / outage_heat_required_kbtuh contract
TestAdequatelySized     — ValueError when primary doesn't need gas backup
TestThreeDaySim         — integration: sized system must pass 3-day simulation
TestGasBackupFromWindow — unit tests for _gas_backup_from_window()
TestGetSizingCurve      — Plotly figure structure from get_sizing_curve()
"""
import pytest

from ecoengine.objects.building.Building import Building
from ecoengine.objects.building.ClimateZone import ClimateZone
from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.storage.MixedStorageTank import MixedStorageTank
from ecoengine.objects.dhwsystems.rtp_systems.SinglePassRTPSystem import SinglePassRTPSystem
from ecoengine.objects.dhwsystems.rtp_systems.SP_RTPInSeriesSystem import SP_RTPInSeriesSystem
from ecoengine.interfaces.Simulator import simulate_3day

# ---------------------------------------------------------------------------
# Shared parameters (match the demo script)
# ---------------------------------------------------------------------------
_DESIGN_OAT_F   = 47.0
_DESIGN_INLET_F = 55.0
_SUPPLY_T_F     = 120.0
_STORAGE_T_F    = 140.0
_RETURN_T_F     = 100.0
_RETURN_GPM     = 3.0

_TOTAL_STEPS = 2 * 24 * 60   # 2 days at 1-min intervals


def _zone() -> ClimateZone:
    return ClimateZone.from_design_conditions(
        design_oat_f=_DESIGN_OAT_F,
        design_inlet_water_temp_f=_DESIGN_INLET_F,
    )


def _controls() -> Controls:
    return Controls(
        on_sensor_fract=0.4,
        on_trigger_t_f=_SUPPLY_T_F,
        off_sensor_fract=0.2,
        off_trigger_t_f=_STORAGE_T_F - 10.0,
        outlet_temp_f=_STORAGE_T_F,
    )


def _build_system(building_type: str, magnitude: int, primary_fraction: float) -> tuple:
    """Return (building, SP_RTPInSeriesSystem) sized at primary_fraction of full SPRTP."""
    zone     = _zone()
    building = Building.from_building_type(building_type, magnitude, zone)
    ctrl     = _controls()

    ref = SinglePassRTPSystem.from_size(
        building=building,
        supply_temp_f=_SUPPLY_T_F,
        storage_temp_f=_STORAGE_T_F,
        return_temp_f=_RETURN_T_F,
        return_flow_gpm=_RETURN_GPM,
        control_schedule=["normal"] * 24,
        control_map={"normal": ctrl},
    )
    system = SP_RTPInSeriesSystem.from_size(
        building=building,
        supply_temp_f=_SUPPLY_T_F,
        storage_temp_f=_STORAGE_T_F,
        return_temp_f=_RETURN_T_F,
        return_flow_gpm=_RETURN_GPM,
        nominal_capacity_kbtuh=ref._minimum_capacity_kbtuh * primary_fraction,
        nominal_storage_gal=ref._minimum_storage_storageT_gal * primary_fraction,
        control_schedule=["normal"] * 24,
        control_map={"normal": ctrl},
    )
    return building, system


# ---------------------------------------------------------------------------
# TestFromSize — construction and component sanity
# ---------------------------------------------------------------------------

@pytest.mark.filterwarnings("ignore::UserWarning")
class TestFromSize:
    """from_size() builds a complete system with plausible gas backup components."""

    def test_gas_water_heater_is_water_heater(self):
        _, system = _build_system("multi_family", 100, 0.70)
        assert isinstance(system.gas_water_heater, WaterHeater)

    def test_gas_storage_tank_is_mixed_tank(self):
        _, system = _build_system("multi_family", 100, 0.70)
        assert isinstance(system.gas_storage_tank, MixedStorageTank)

    def test_gas_heater_capacity_positive(self):
        _, system = _build_system("multi_family", 100, 0.70)
        cap = system.gas_water_heater.get_capacity_kbtuh(_DESIGN_OAT_F, _SUPPLY_T_F + 13.0)
        assert cap > 0.0

    def test_gas_tank_volume_positive(self):
        _, system = _build_system("multi_family", 100, 0.70)
        assert system.gas_storage_tank.total_volume_gal > 0.0


# ---------------------------------------------------------------------------
# TestOutageArrays — outage_volume_gal / outage_heat_required_kbtuh contract
# ---------------------------------------------------------------------------

@pytest.mark.filterwarnings("ignore::UserWarning")
class TestOutageArrays:
    """Outage arrays are populated correctly after from_size()."""

    def test_outage_volume_length(self):
        _, system = _build_system("multi_family", 100, 0.70)
        assert len(system.outage_volume_gal) == _TOTAL_STEPS

    def test_outage_heat_required_length(self):
        _, system = _build_system("multi_family", 100, 0.70)
        assert len(system.outage_heat_required_kbtuh) == _TOTAL_STEPS

    def test_outage_volume_non_negative(self):
        _, system = _build_system("multi_family", 100, 0.70)
        assert all(v >= 0.0 for v in system.outage_volume_gal)

    def test_outage_heat_required_non_negative(self):
        _, system = _build_system("multi_family", 100, 0.70)
        assert all(d >= 0.0 for d in system.outage_heat_required_kbtuh)

    def test_some_outage_minutes_exist(self):
        """At 70% primary the outage arrays must contain at least one non-zero entry."""
        _, system = _build_system("multi_family", 100, 0.70)
        assert any(v > 0.0 for v in system.outage_volume_gal)


# ---------------------------------------------------------------------------
# TestAdequatelySized — ValueError when gas backup is not needed
# ---------------------------------------------------------------------------

@pytest.mark.filterwarnings("ignore::UserWarning")
class TestAdequatelySized:
    """from_size() raises ValueError when the primary is not actually undersized."""

    def test_raises_for_oversized_primary(self):
        """A 200%-capacity primary clearly needs no gas backup."""
        zone     = _zone()
        building = Building.from_building_type("multi_family", 100, zone)
        ctrl     = _controls()
        ref = SinglePassRTPSystem.from_size(
            building=building,
            supply_temp_f=_SUPPLY_T_F,
            storage_temp_f=_STORAGE_T_F,
            return_temp_f=_RETURN_T_F,
            return_flow_gpm=_RETURN_GPM,
            control_schedule=["normal"] * 24,
            control_map={"normal": ctrl},
        )
        with pytest.raises(ValueError, match="already adequately sized"):
            SP_RTPInSeriesSystem.from_size(
                building=building,
                supply_temp_f=_SUPPLY_T_F,
                storage_temp_f=_STORAGE_T_F,
                return_temp_f=_RETURN_T_F,
                return_flow_gpm=_RETURN_GPM,
                nominal_capacity_kbtuh=ref._minimum_capacity_kbtuh * 2.0,
                nominal_storage_gal=ref._minimum_storage_storageT_gal * 2.0,
                control_schedule=["normal"] * 24,
                control_map={"normal": ctrl},
            )


# ---------------------------------------------------------------------------
# TestThreeDaySim — integration: sized system passes 3-day simulation
# ---------------------------------------------------------------------------

@pytest.mark.filterwarnings("ignore::UserWarning")
class TestThreeDaySim:
    """SP_RTPInSeriesSystem sized at 70% primary must pass the 3-day design-day sim."""

    def test_multi_family_100_units(self):
        building, system = _build_system("multi_family", 100, 0.70)
        sim = simulate_3day(system, building)
        assert sim.is_successful(), sim.get_failure_message()

    def test_motel_80_rooms(self):
        building, system = _build_system("motel", 80, 0.70)
        sim = simulate_3day(system, building)
        assert sim.is_successful(), sim.get_failure_message()

    def test_elementary_school_100_students(self):
        building, system = _build_system("elementary_school", 100, 0.70)
        sim = simulate_3day(system, building)
        assert sim.is_successful(), sim.get_failure_message()


# ---------------------------------------------------------------------------
# TestGasBackupFromWindow — unit tests for _gas_backup_from_window()
# ---------------------------------------------------------------------------

@pytest.mark.filterwarnings("ignore::UserWarning")
class TestGasBackupFromWindow:
    """_gas_backup_from_window() returns physically sensible values."""

    def test_all_zeros_returns_zero_capacity(self):
        """All-zero outage arrays produce zero capacity and volume."""
        _, system = _build_system("multi_family", 100, 0.70)
        system.outage_volume_gal          = [0.0] * _TOTAL_STEPS
        system.outage_heat_required_kbtuh = [0.0] * _TOTAL_STEPS
        cap, vol = system._gas_backup_from_window(30)
        assert cap == pytest.approx(0.0)
        assert vol == pytest.approx(0.0)

    def test_returns_positive_for_real_outage(self):
        """A real undersized system produces positive capacity and volume."""
        _, system = _build_system("multi_family", 100, 0.70)
        cap, vol = system._gas_backup_from_window(30)
        assert cap > 0.0
        assert vol > 0.0

    def test_larger_window_more_storage(self):
        """A 60-minute window should yield at least as much storage as a 5-minute window."""
        _, system = _build_system("multi_family", 100, 0.70)
        _, vol_60 = system._gas_backup_from_window(60)
        _, vol_5  = system._gas_backup_from_window(5)
        assert vol_60 >= vol_5

    def test_window_clamped_to_array_length(self):
        """window_min larger than the array does not raise; clamps to array length."""
        _, system = _build_system("multi_family", 100, 0.70)
        system.outage_volume_gal          = [1.0] * 5
        system.outage_heat_required_kbtuh = [2.0] * 5
        # window_min=15 > len=5; should clamp and use a valid ASHRAE window
        cap, vol = system._gas_backup_from_window(15)
        assert cap >= 0.0
        assert vol >= 0.0


# ---------------------------------------------------------------------------
# TestGetSizingCurve — Plotly figure structure
# ---------------------------------------------------------------------------

@pytest.mark.filterwarnings("ignore::UserWarning")
class TestGetSizingCurve:
    """get_sizing_curve() returns a correctly structured data dict."""

    def test_raises_before_sizing(self):
        """get_sizing_curve() raises RuntimeError when outage arrays are absent."""
        building, system = _build_system("multi_family", 100, 0.70)
        del system.outage_volume_gal
        with pytest.raises(RuntimeError, match="outage data is not available"):
            system.get_sizing_curve(building)

    def test_dict_keys(self):
        """Dict has the four expected keys."""
        building, system = _build_system("multi_family", 100, 0.70)
        curve = system.get_sizing_curve(building)
        assert set(curve.keys()) == {"window_sizes", "capacities_kbtuh", "storages_gal", "recommended_index"}

    def test_window_sizes(self):
        """window_sizes contains the four ASHRAE durations."""
        building, system = _build_system("multi_family", 100, 0.70)
        assert system.get_sizing_curve(building)["window_sizes"] == [5, 15, 30, 60]

    def test_recommended_index_is_30_min(self):
        """recommended_index points to the 30-minute window."""
        building, system = _build_system("multi_family", 100, 0.70)
        curve = system.get_sizing_curve(building)
        assert curve["window_sizes"][curve["recommended_index"]] == 30

    def test_capacities_and_storages_positive(self):
        """All capacities and storages are positive for a real undersized system."""
        building, system = _build_system("multi_family", 100, 0.70)
        curve = system.get_sizing_curve(building)
        assert all(c > 0.0 for c in curve["capacities_kbtuh"])
        assert all(s > 0.0 for s in curve["storages_gal"])

    def test_dummy_params_have_no_effect(self):
        """building/strat_slope/step are accepted for signature parity but change nothing."""
        building, system = _build_system("multi_family", 100, 0.70)
        default_curve = system.get_sizing_curve(building)
        other_curve = system.get_sizing_curve(building, strat_slope=1.0, step=5.0)
        assert default_curve == other_curve


@pytest.mark.filterwarnings("ignore::UserWarning")
class TestPlotSizingCurve:
    """plot_sizing_curve() returns a correctly structured Plotly figure."""

    def test_trace_count(self):
        """Figure has 1 line trace + one marker per ASHRAE window (4 windows → 5 total)."""
        building, system = _build_system("multi_family", 100, 0.70)
        fig = system.plot_sizing_curve(building)
        assert len(fig.data) == 5

    def test_slider_step_count(self):
        """Slider has one step per ASHRAE window size."""
        building, system = _build_system("multi_family", 100, 0.70)
        fig = system.plot_sizing_curve(building)
        assert len(fig.layout.sliders[0].steps) == 4

    def test_recommended_slider_position(self):
        """The active slider position corresponds to the 30-minute window."""
        building, system = _build_system("multi_family", 100, 0.70)
        fig = system.plot_sizing_curve(building)
        active = fig.layout.sliders[0].active
        assert [5, 15, 30, 60][active] == 30
