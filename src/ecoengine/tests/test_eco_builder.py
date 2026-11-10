"""
Unit tests for EcoBuilder.

Test groups
-----------
TestDefineFields          — define_temperatures / define_storage_volume / define_recirc
TestBuildPerformanceMap   — model vs nominal maps, argument errors
TestBuildControlSetting   — Controls vs AlwaysOffControls, partial-None error
TestBuildControlSchedule  — start-time expansion and validation
TestBuildWaterHeater      — slot routing and validation
TestBuildSystem           — required fields, heater counts, warnings, unsized getters
TestMatchesEngine         — same components through EcoBuilder and EcosizerEngine
                            (pre-sized) give identical 3-day simulations
"""
import warnings

import pytest

from ecoengine.constants.constants import _BTUH_PER_W, _NOMINAL_COP_BY_HEATING_TYPE
from ecoengine.interfaces.EcoBuilder import EcoBuilder
from ecoengine.interfaces.EcosizerEngine import EcosizerEngine
from ecoengine.interfaces.Simulator import simulate_3day
from ecoengine.interfaces.system_assembly_utils import (
    default_in_series_gas_controls,
    default_tm_controls,
)
from ecoengine.objects.building.Building import Building
from ecoengine.objects.components.heating.Controls import AlwaysOffControls, Controls
from ecoengine.objects.components.heating.PerformanceMap import (
    NominalPerformanceMap,
    PklPerformanceMap,
)
from ecoengine.objects.dhwsystems.rtp_systems.SP_RTPInParallelSystem import default_gas_controls

_SUPPLY_T_F  = 120.0
_STORAGE_T_F = 150.0
_RETURN_T_F  = 110.0
_RETURN_GPM  = 5.0
_CLIMATE     = {"design_oat_f": 47.0, "design_inlet_water_temp_f": 55.0}


def _normal_controls(eb: EcoBuilder) -> Controls:
    return eb.build_control_setting(0.5, _SUPPLY_T_F, 0.1, _STORAGE_T_F, _STORAGE_T_F)


def _add_heater(eb: EcoBuilder, kbtuh: float, controls=None, **kwargs):
    controls = controls if controls is not None else _normal_controls(eb)
    return eb.build_water_heater(
        eb.build_performance_map(nominal_capacity_kbtuh=kbtuh),
        eb.build_control_schedule(),
        {"normal": controls},
        **kwargs,
    )


def _ready_builder() -> EcoBuilder:
    """Builder with temperatures, primary storage and one primary heater."""
    eb = EcoBuilder()
    eb.define_temperatures(_SUPPLY_T_F, _STORAGE_T_F)
    eb.define_storage_volume(300.0)
    _add_heater(eb, 100.0)
    return eb


# ---------------------------------------------------------------------------
# TestDefineFields
# ---------------------------------------------------------------------------

class TestDefineFields:
    def test_defaults(self):
        eb = EcoBuilder()
        assert eb.supply_temp_f is None and eb.storage_temp_f is None
        assert eb.water_heaters == [] and eb.tm_water_heaters == [] and eb.in_series_water_heaters == []
        assert eb.drawdown_fract == 1.0

    def test_heater_lists_not_shared_between_instances(self):
        a, b = EcoBuilder(), EcoBuilder()
        _add_heater(a, 10.0)
        assert b.water_heaters == []

    def test_define_temperatures_only_overwrites_given_values(self):
        eb = EcoBuilder()
        eb.define_temperatures(120.0, 150.0)
        eb.define_temperatures(storage_temp_f=140.0)
        assert (eb.supply_temp_f, eb.storage_temp_f) == (120.0, 140.0)

    @pytest.mark.parametrize("storage_type,field", [
        ("primary",   "primary_storage_vol_gal"),
        ("tm",        "tm_storage_vol_gal"),
        ("in_series", "in_series_storage_vol_gal"),
    ])
    def test_define_storage_volume_sets_field(self, storage_type, field):
        eb = EcoBuilder()
        eb.define_storage_volume(80.0, storage_type)
        assert getattr(eb, field) == 80.0

    def test_define_storage_volume_sets_supply_and_drawdown(self):
        eb = EcoBuilder()
        eb.define_storage_volume(500.0, drawdown_fract=0.8, supply_temp_f=125.0)
        assert (eb.drawdown_fract, eb.supply_temp_f) == (0.8, 125.0)

    @pytest.mark.parametrize("kwargs", [
        dict(gal=100.0, storage_type="gas"),
        dict(gal=0.0),
        dict(gal=100.0, storage_type="tm", drawdown_fract=0.5),
        dict(gal=100.0, drawdown_fract=0.0),
        dict(gal=100.0, drawdown_fract=1.5),
    ])
    def test_define_storage_volume_errors(self, kwargs):
        with pytest.raises(ValueError):
            EcoBuilder().define_storage_volume(**kwargs)

    def test_define_recirc(self):
        eb = EcoBuilder()
        eb.define_recirc(110.0, 5.0, supply_temp_f=118.0)
        assert (eb.return_temp_f, eb.return_flow_gpm, eb.supply_temp_f) == (110.0, 5.0, 118.0)


# ---------------------------------------------------------------------------
# TestBuildPerformanceMap
# ---------------------------------------------------------------------------

class TestBuildPerformanceMap:
    def test_nominal(self):
        pm = EcoBuilder().build_performance_map(nominal_capacity_kbtuh=250.0)
        assert isinstance(pm, NominalPerformanceMap)
        assert pm.get_capacity_kbtuh(47.0, 150.0) == pytest.approx(250.0)

    def test_model(self):
        pm = EcoBuilder().build_performance_map("MODELS_GenericHPWH3_C_SP", num_units=2)
        assert isinstance(pm, PklPerformanceMap)
        assert pm.num_units == 2

    def test_requires_model_or_capacity(self):
        with pytest.raises(ValueError, match="model_name or nominal_capacity_kbtuh"):
            EcoBuilder().build_performance_map()

    def test_num_units_requires_model(self):
        with pytest.raises(ValueError, match="num_units"):
            EcoBuilder().build_performance_map(nominal_capacity_kbtuh=100.0, num_units=2)


# ---------------------------------------------------------------------------
# TestBuildControlSetting
# ---------------------------------------------------------------------------

class TestBuildControlSetting:
    def test_returns_controls(self):
        c = EcoBuilder().build_control_setting(0.5, 120.0, 0.1, 150.0, 150.0)
        assert type(c) is Controls
        assert (c.on_sensor_fract, c.on_trigger_t_f, c.off_sensor_fract,
                c.off_trigger_t_f, c.outlet_temp_f) == (0.5, 120.0, 0.1, 150.0, 150.0)

    def test_all_none_returns_always_off(self):
        c = EcoBuilder().build_control_setting(None, None, None, None, 145.0)
        assert isinstance(c, AlwaysOffControls)
        assert c.outlet_temp_f == 145.0

    def test_partial_none_raises(self):
        with pytest.raises(ValueError, match="none of them"):
            EcoBuilder().build_control_setting(0.5, None, 0.1, 150.0, 150.0)


# ---------------------------------------------------------------------------
# TestBuildControlSchedule
# ---------------------------------------------------------------------------

class TestBuildControlSchedule:
    def test_none_is_all_normal(self):
        assert EcoBuilder().build_control_schedule() == ["normal"] * 24

    def test_shed_window(self):
        sched = EcoBuilder().build_control_schedule([["normal", 0], ["shed", 12], ["normal", 18]])
        assert sched == ["normal"] * 12 + ["shed"] * 6 + ["normal"] * 6

    def test_shed_to_end_of_day(self):
        sched = EcoBuilder().build_control_schedule([["normal", 0], ["shed", 12]])
        assert sched == ["normal"] * 12 + ["shed"] * 12

    def test_order_independent(self):
        sched = EcoBuilder().build_control_schedule([["shed", 12], ["normal", 0]])
        assert sched == ["normal"] * 12 + ["shed"] * 12

    @pytest.mark.parametrize("start_times", [
        [["normal", 15], ["shed", 12]],    # no hour 0
        [["normal", 0], ["shed", 0]],      # duplicate hour
        [["normal", 0], ["shed", 24]],     # out of range
        [["normal", 0], ["shed", 12.5]],   # not an int
        [["normal", 0], [3, 12]],          # mode not a string
        [["normal", 0, 1]],                # malformed entry
    ])
    def test_invalid(self, start_times):
        with pytest.raises(ValueError):
            EcoBuilder().build_control_schedule(start_times)


# ---------------------------------------------------------------------------
# TestBuildWaterHeater
# ---------------------------------------------------------------------------

class TestBuildWaterHeater:
    @pytest.mark.parametrize("system,field", [
        ("primary",   "water_heaters"),
        ("tm",        "tm_water_heaters"),
        ("in_series", "in_series_water_heaters"),
    ])
    def test_routes_to_slot(self, system, field):
        eb = EcoBuilder()
        wh = _add_heater(eb, 50.0, system=system)
        assert getattr(eb, field) == [wh]

    def test_none_slot_only_returns(self):
        eb = EcoBuilder()
        wh = _add_heater(eb, 50.0, system=None)
        assert wh.heating_type == "heat_pump"
        assert eb.water_heaters == eb.tm_water_heaters == eb.in_series_water_heaters == []

    def test_heating_type(self):
        assert _add_heater(EcoBuilder(), 50.0, heating_type="gas").heating_type == "gas"

    @pytest.mark.parametrize("heating_type", ["electric_resistance", "gas", "heat_pump"])
    def test_heating_type_sets_nominal_map_cop(self, heating_type):
        wh = _add_heater(EcoBuilder(), 50.0, heating_type=heating_type)
        expected_kw = 50.0 / _BTUH_PER_W / _NOMINAL_COP_BY_HEATING_TYPE[heating_type]
        assert wh.performance_map.heating_type == heating_type
        assert wh.get_power_in_kw(50.0, 140.0) == 0.0  # inactive
        wh.turn_on()
        assert wh.get_power_in_kw(50.0, 140.0) == pytest.approx(expected_kw)

    @pytest.mark.parametrize("kwargs", [dict(system="gas"), dict(heating_type="propane"), dict(heating_type="electric")])
    def test_bad_slot_or_heating_type(self, kwargs):
        with pytest.raises(ValueError):
            _add_heater(EcoBuilder(), 50.0, **kwargs)

    def test_requires_performance_map(self):
        eb = EcoBuilder()
        with pytest.raises(TypeError):
            eb.build_water_heater(50.0, ["normal"] * 24, {"normal": _normal_controls(eb)})

    def test_schedule_length(self):
        eb = EcoBuilder()
        with pytest.raises(ValueError, match="24 entries"):
            eb.build_water_heater(eb.build_performance_map(nominal_capacity_kbtuh=50.0),
                                  ["normal"] * 23, {"normal": _normal_controls(eb)})

    def test_mode_missing_from_map(self):
        eb = EcoBuilder()
        sched = eb.build_control_schedule([["normal", 0], ["shed", 16]])
        with pytest.raises(ValueError, match="shed"):
            eb.build_water_heater(eb.build_performance_map(nominal_capacity_kbtuh=50.0),
                                  sched, {"normal": _normal_controls(eb)})


# ---------------------------------------------------------------------------
# TestBuildSystem
# ---------------------------------------------------------------------------

class TestBuildSystem:
    def test_unknown_schematic(self):
        with pytest.raises(ValueError, match="Unknown schematic"):
            _ready_builder().build_system("not_a_schematic")

    def test_lists_all_missing_fields(self):
        with pytest.raises(ValueError) as exc:
            EcoBuilder().build_system("swing_tank")
        for field in ("supply_temp_f", "storage_temp_f", "water_heaters", "primary_storage_vol_gal",
                      "return_temp_f", "return_flow_gpm", "tm_water_heaters", "tm_storage_vol_gal"):
            assert field in str(exc.value)

    def test_in_series_requirements(self):
        eb = _ready_builder()
        eb.define_recirc(_RETURN_T_F, _RETURN_GPM)
        with pytest.raises(ValueError, match="in_series_water_heaters, in_series_storage_vol_gal"):
            eb.build_system("sprtp_in_series")

    def test_instant_wh_needs_no_storage(self):
        eb = EcoBuilder()
        eb.define_temperatures(_SUPPLY_T_F, _STORAGE_T_F)
        _add_heater(eb, 100.0)
        assert eb.build_system("instant_wh").storage_tank is None

    def test_alias_accepted(self):
        eb = _ready_builder()
        eb.define_recirc(_RETURN_T_F, _RETURN_GPM)
        assert type(eb.build_system("sprtp")).__name__ == "SinglePassRTPSystem"

    @pytest.mark.parametrize("n_gas", [0, 2])
    def test_sprtp_in_parallel_needs_one_gas_heater(self, n_gas):
        eb = _ready_builder()
        eb.define_recirc(_RETURN_T_F, _RETURN_GPM)
        for _ in range(n_gas):
            _add_heater(eb, 200.0, heating_type="gas")
        with pytest.raises(ValueError, match=f"found {n_gas}"):
            eb.build_system("sprtp_in_parallel")

    def test_sprtp_in_parallel_splits_gas_heater(self):
        eb = _ready_builder()
        eb.define_recirc(_RETURN_T_F, _RETURN_GPM)
        gas = _add_heater(eb, 200.0, heating_type="gas")
        system = eb.build_system("sprtp_in_parallel")
        assert system.gas_water_heater is gas
        assert system.water_heaters == [eb.water_heaters[0]]

    def test_sprtp_in_parallel_needs_an_electric_heater(self):
        eb = EcoBuilder()
        eb.define_temperatures(_SUPPLY_T_F, _STORAGE_T_F)
        eb.define_storage_volume(300.0)
        eb.define_recirc(_RETURN_T_F, _RETURN_GPM)
        _add_heater(eb, 200.0, heating_type="gas")
        with pytest.raises(ValueError, match="water_heaters"):
            eb.build_system("sprtp_in_parallel")

    def test_one_tm_heater_only(self):
        eb = _ready_builder()
        eb.define_recirc(_RETURN_T_F, _RETURN_GPM)
        eb.define_storage_volume(80.0, "tm")
        _add_heater(eb, 30.0, system="tm")
        _add_heater(eb, 30.0, system="tm")
        with pytest.raises(ValueError, match="one heater in tm_water_heaters"):
            eb.build_system("swing_tank")

    def test_parallel_loop_tm_temps_from_controls(self):
        eb = _ready_builder()
        eb.define_recirc(_RETURN_T_F, _RETURN_GPM)
        eb.define_storage_volume(80.0, "tm")
        _add_heater(eb, 30.0, eb.build_control_setting(0.5, 118.0, 0.5, 126.0, 126.0), system="tm")
        system = eb.build_system("parallel_loop")
        assert (system.tm_on_temp_f, system.tm_off_temp_f) == (118.0, 126.0)

    def test_drawdown_applied_to_mprtp_tank(self):
        eb = _ready_builder()
        eb.define_recirc(_RETURN_T_F, _RETURN_GPM)
        eb.define_storage_volume(300.0, drawdown_fract=0.7)
        assert eb.build_system("multi_pass_rtp").storage_tank.drawdown_fract == 0.7

    def test_warns_on_unused_fields(self):
        eb = _ready_builder()
        eb.define_storage_volume(80.0, "tm")
        eb.define_recirc(_RETURN_T_F, _RETURN_GPM)
        with pytest.warns(UserWarning, match="return_temp_f / return_flow_gpm, tm_storage_vol_gal"):
            eb.build_system("primary_no_recirc")

    def test_no_warning_when_all_fields_used(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            _ready_builder().build_system("primary_no_recirc")

    def test_controls_not_overridden(self):
        """Shed mode keeps the caller's Controls (no dual-fuel always-off override)."""
        eb = EcoBuilder()
        eb.define_temperatures(_SUPPLY_T_F, _STORAGE_T_F)
        eb.define_storage_volume(200.0)
        eb.define_recirc(_RETURN_T_F, _RETURN_GPM)
        shed = eb.build_control_setting(0.8, _SUPPLY_T_F, 0.1, _STORAGE_T_F, _STORAGE_T_F)
        eb.build_water_heater(
            eb.build_performance_map(nominal_capacity_kbtuh=60.0),
            eb.build_control_schedule([["normal", 0], ["shed", 16], ["normal", 20]]),
            {"normal": _normal_controls(eb), "shed": shed},
        )
        _add_heater(eb, 200.0, heating_type="gas")
        system = eb.build_system("sprtp_in_parallel")
        assert system.water_heaters[0].control_map["shed"] is shed

    def test_built_system_is_not_sized(self):
        system = _ready_builder().build_system("primary_no_recirc")
        with pytest.raises(RuntimeError, match="System was built, not sized"):
            system.get_minimum_capacity_kbtuh()

    def test_build_building_not_stored(self):
        eb = EcoBuilder()
        building = eb.build_building("multi_family", 100, _CLIMATE, gpdpp=25)
        assert isinstance(building, Building)
        assert not hasattr(eb, "building")


# ---------------------------------------------------------------------------
# TestMatchesEngine
# ---------------------------------------------------------------------------
# Each case: (primary kBTU/hr, primary gal, TM (gal, kBTU/hr), gas (gal, kBTU/hr), drawdown)

_MATCH_CASES = {
    "primary_no_recirc": (300.0, 500.0, None, None, None),
    "parallel_loop":     (300.0, 500.0, (100.0, 30.0), None, None),
    "swing_tank":        (300.0, 500.0, (100.0, 30.0), None, None),
    "single_pass_rtp":   (300.0, 500.0, None, None, None),
    "multi_pass_rtp":    (300.0, 500.0, None, None, 0.8),
    "instant_wh":        (800.0, None,  None, None, None),
    "sprtp_in_series":   (60.0, 200.0, None, (100.0, 200.0), None),
    "sprtp_in_parallel": (60.0, 200.0, None, (None, 200.0), None),
    "mprtp_in_series":   (60.0, 200.0, None, (100.0, 200.0), None),
    "swing_dual_fuel":   (60.0, 200.0, (100.0, 200.0), None, None),
}
_NO_RECIRC = {"primary_no_recirc", "instant_wh"}


def _engine_run(schematic, cap, vol, tm, gas, drawdown):
    kwargs = dict(
        building_type="multi_family", magnitude=100, gpdpp=25, zip_code_or_climate_zone=_CLIMATE,
        supply_temp_f=_SUPPLY_T_F, storage_temp_f=_STORAGE_T_F,
        heating_capacity_kbtuh=cap,
        storage_volume_storageT_gal=vol if vol is not None else 0.0,
    )
    if schematic not in _NO_RECIRC:
        kwargs.update(return_temp_f=_RETURN_T_F, return_flow_gpm=_RETURN_GPM)
    if tm:
        kwargs.update(tm_storage_vol=tm[0], tm_capacity_kbtuh=tm[1])
    if gas:
        kwargs["gas_capacity_kbtuh"] = gas[1]
        if gas[0] is not None:
            kwargs["gas_storage_vol_gal"] = gas[0]
    if drawdown is not None:
        kwargs["drawdown_fract"] = drawdown
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return EcosizerEngine(schematic=schematic, **kwargs).simulate_3day()


def _builder_run(schematic, cap, vol, tm, gas, drawdown):
    """Rebuild the engine's pre-sized system with EcoBuilder, using the engine's default controls."""
    eb = EcoBuilder()
    eb.define_temperatures(_SUPPLY_T_F, _STORAGE_T_F)
    if vol is not None:
        eb.define_storage_volume(vol, drawdown_fract=drawdown)
    if schematic not in _NO_RECIRC:
        eb.define_recirc(_RETURN_T_F, _RETURN_GPM)
    _add_heater(eb, cap)
    if tm:
        eb.define_storage_volume(tm[0], "tm")
        tm_controls = default_tm_controls(schematic, _SUPPLY_T_F, _SUPPLY_T_F, _SUPPLY_T_F + 8.0)
        _add_heater(eb, tm[1], tm_controls, system="tm")
    if gas and schematic == "sprtp_in_parallel":
        gas_controls = eb.build_control_setting(
            default_gas_controls.on_sensor_fract, default_gas_controls.on_trigger_t_f,
            default_gas_controls.off_sensor_fract, default_gas_controls.off_trigger_t_f,
            _STORAGE_T_F,
        )
        _add_heater(eb, gas[1], gas_controls, heating_type="gas")
    elif gas:
        eb.define_storage_volume(gas[0], "in_series")
        _add_heater(eb, gas[1], default_in_series_gas_controls(_SUPPLY_T_F),
                    heating_type="gas", system="in_series")
    building = eb.build_building("multi_family", 100, _CLIMATE, gpdpp=25)
    return simulate_3day(eb.build_system(schematic), building)


class TestMatchesEngine:
    @pytest.mark.parametrize("schematic", list(_MATCH_CASES))
    def test_same_simulation(self, schematic):
        engine_run  = _engine_run(schematic, *_MATCH_CASES[schematic])
        builder_run = _builder_run(schematic, *_MATCH_CASES[schematic])
        assert builder_run.heater_output_kbtuh == pytest.approx(engine_run.heater_output_kbtuh)
        assert [v or 0.0 for v in builder_run.tm_heater_output_kbtuh] == pytest.approx(
            [v or 0.0 for v in engine_run.tm_heater_output_kbtuh]
        )
        assert builder_run.usable_volume_supplyT_gal == pytest.approx(engine_run.usable_volume_supplyT_gal)
        assert builder_run.outage_minutes == engine_run.outage_minutes
