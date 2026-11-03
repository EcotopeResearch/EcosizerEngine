"""
Equivalence tests: EcoBuilder vs. pre-sized EcosizerEngine.

Each case describes one system once (``_Spec``). ``_engine_run`` turns the
spec into EcosizerEngine pre-sized parameters; ``_builder_run`` builds the same
system component by component with EcoBuilder, reproducing the engine's
control logic by hand (default TM / gas controls, load-shift schedule, the
dual-fuel always-off shed override). Both systems then run the 3-day
design-day simulation and every recorded series must match.

Every schematic in ``SCHEMATICS`` is run in four variants:

* ``base``      — one nominal heater, default "normal" controls
* ``ls``        — load shift with load-up and shed windows
* ``model``     — two units of a pkl performance map, real CA climate
* ``controls``  — two nominal heaters, custom aquastat / TM / gas controls
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import pytest

from ecoengine.interfaces.EcoBuilder import EcoBuilder
from ecoengine.interfaces.EcosizerEngine import EcosizerEngine
from ecoengine.interfaces.Simulator import simulate_3day
from ecoengine.interfaces.system_assembly_utils import (
    GAS_SCHEMATICS,
    IN_SERIES_SCHEMATICS,
    RECIRC_SCHEMATICS,
    SCHEMATICS,
    TM_SCHEMATICS,
    default_in_series_gas_controls,
    default_tm_controls,
)
from ecoengine.objects.dhwsystems.rtp_systems.SP_RTPInParallelSystem import default_gas_controls

_REL = 1e-12

_SUPPLY_T_F  = 120.0
_STORAGE_T_F = 150.0
_RETURN_T_F  = 110.0
_RETURN_GPM  = 5.0
_BUILDING    = dict(building_type="multi_family", magnitude=100, gpdpp=25)
_DESIGN      = {"design_oat_f": 47.0, "design_inlet_water_temp_f": 55.0}
_MODEL       = "MODELS_GenericHPWH3_C_SP"

_DUAL_FUEL = frozenset({"sprtp_in_series", "sprtp_in_parallel", "mprtp_in_series", "swing_dual_fuel"})

# Load shift: normal 0-13, loadUp 14-15, shed 16-19, normal 20-23
_LS_SCHEDULE      = [1] * 16 + [0] * 4 + [1] * 4
_LS_LOAD_UP_HOURS = 2
_LS_START_TIMES   = [["normal", 0], ["loadUp", 14], ["shed", 16], ["normal", 20]]
_LS_SHED_FRACT    = 0.8
_LS_LOAD_UP_FRACT = 0.2


@dataclass(frozen=True)
class _Spec:
    """One system, described once for both build paths."""
    schematic: str
    cap: float                                   # total primary capacity [kBTU/hr]
    vol: float | None                            # primary storage [gal]; None for instant_wh
    tm: tuple[float, float] | None = None        # (TM gal, TM kBTU/hr)
    gas: tuple[float | None, float] | None = None  # (in-series gal or None, gas kBTU/hr)
    drawdown: float = 1.0
    num_heaters: int = 1
    model: str | None = None                     # pkl performance map name
    load_shift: bool = False
    climate: object = None                       # zip / zone / dict; None → _DESIGN
    # Custom normal controls (on_fract, on_t, off_fract, off_t); None → engine defaults
    aquastat: tuple[float, float, float, float] | None = None
    tm_temps: tuple[float, float] | None = None  # parallel_loop (on, off) [°F]
    # sprtp_in_parallel gas controls (on_fract, on_t, off_fract, off_t); None → defaults
    gas_controls: tuple[float, float, float, float] | None = None

    @property
    def climate_key(self):
        return _DESIGN if self.climate is None else self.climate


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

def _base_kwargs(schematic: str) -> dict:
    """Capacity, volumes and sub-systems per schematic."""
    if schematic == "instant_wh":
        return dict(cap=800.0, vol=None)
    if schematic in _DUAL_FUEL:
        kw = dict(cap=60.0, vol=200.0)
        if schematic == "swing_dual_fuel":
            kw["tm"] = (100.0, 200.0)
        elif schematic == "sprtp_in_parallel":
            kw["gas"] = (None, 200.0)
        else:
            kw["gas"] = (100.0, 200.0)
        return kw
    kw = dict(cap=300.0, vol=500.0)
    if schematic in TM_SCHEMATICS:
        kw["tm"] = (100.0, 30.0)
    if schematic == "multi_pass_rtp":
        kw["drawdown"] = 0.8
    return kw


def _variants(schematic: str) -> dict[str, _Spec]:
    base = _base_kwargs(schematic)
    controls = dict(base, num_heaters=2, aquastat=(0.4, 125.0, 0.2, 145.0))
    if schematic == "parallel_loop":
        controls["tm_temps"] = (115.0, 125.0)
    if schematic == "sprtp_in_parallel":
        controls["gas_controls"] = (0.3, 122.0, 0.2, 140.0)
    return {
        "base":     _Spec(schematic, **base),
        "ls":       _Spec(schematic, **base, load_shift=True),
        "model":    _Spec(schematic, **base, model=_MODEL, num_heaters=2, climate="95823"),
        "controls": _Spec(schematic, **controls),
    }


_CASES = {
    f"{schematic}|{variant}": spec
    for schematic in SCHEMATICS
    for variant, spec in _variants(schematic).items()
}


# ---------------------------------------------------------------------------
# EcosizerEngine path
# ---------------------------------------------------------------------------

def _engine_run(spec: _Spec):
    s = spec.schematic
    kwargs = dict(
        **_BUILDING,
        zip_code_or_climate_zone    = spec.climate_key,
        supply_temp_f               = _SUPPLY_T_F,
        storage_temp_f              = _STORAGE_T_F,
        heating_capacity_kbtuh      = spec.cap,
        storage_volume_storageT_gal = spec.vol if spec.vol is not None else 0.0,
        num_heaters                 = spec.num_heaters,
        drawdown_fract              = spec.drawdown,
    )
    if spec.model is not None:
        kwargs["hpwh_model"] = spec.model
    if s in RECIRC_SCHEMATICS:
        kwargs.update(return_temp_f=_RETURN_T_F, return_flow_gpm=_RETURN_GPM)
    if spec.tm is not None:
        kwargs.update(tm_storage_vol=spec.tm[0], tm_capacity_kbtuh=spec.tm[1])
    if spec.tm_temps is not None:
        kwargs.update(tm_on_temp_f=spec.tm_temps[0], tm_off_temp_f=spec.tm_temps[1])
    if spec.gas is not None:
        kwargs["gas_capacity_kbtuh"] = spec.gas[1]
        if spec.gas[0] is not None:
            kwargs["gas_storage_vol_gal"] = spec.gas[0]
    if spec.gas_controls is not None:
        on_f, on_t, off_f, off_t = spec.gas_controls
        kwargs.update(gas_aquastat_fract=on_f, gas_on_trigger_t_f=on_t,
                      gas_off_sensor_fract=off_f, gas_off_trigger_t_f=off_t)
    if spec.aquastat is not None:
        on_f, on_t, off_f, off_t = spec.aquastat
        kwargs.update(aquastat_fract=on_f, on_trigger_t_f=on_t,
                      off_sensor_fract=off_f, off_trigger_t_f=off_t)
    if spec.load_shift:
        kwargs.update(load_shift_schedule=_LS_SCHEDULE, load_up_hours=_LS_LOAD_UP_HOURS,
                      shed_aquastat_fract=_LS_SHED_FRACT, load_up_aquastat_fract=_LS_LOAD_UP_FRACT)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        engine = EcosizerEngine(schematic=s, **kwargs)
        return engine, engine.simulate_3day()


# ---------------------------------------------------------------------------
# EcoBuilder path
# ---------------------------------------------------------------------------

def _primary_controls(eb: EcoBuilder, spec: _Spec):
    """The engine's primary schedule and control map, rebuilt with EcoBuilder."""
    on_f, on_t, off_f, off_t = spec.aquastat or (0.5, _SUPPLY_T_F, 0.1, _STORAGE_T_F)
    cmap = {"normal": eb.build_control_setting(on_f, on_t, off_f, off_t, _STORAGE_T_F)}
    if not spec.load_shift:
        return eb.build_control_schedule(), cmap

    if spec.schematic in _DUAL_FUEL:
        # Engine forces the primary heater off during shed for dual-fuel systems
        cmap["shed"] = eb.build_control_setting(None, None, None, None, _STORAGE_T_F)
    else:
        cmap["shed"] = eb.build_control_setting(_LS_SHED_FRACT, on_t, off_f, off_t, _STORAGE_T_F)
    cmap["loadUp"] = eb.build_control_setting(_LS_LOAD_UP_FRACT, on_t, off_f, off_t, _STORAGE_T_F)
    return eb.build_control_schedule(_LS_START_TIMES), cmap


def _add_heater(eb: EcoBuilder, kbtuh, schedule, cmap, **kwargs):
    eb.build_water_heater(
        eb.build_performance_map(nominal_capacity_kbtuh=kbtuh), schedule, cmap, **kwargs
    )


def _builder_run(spec: _Spec, design_inlet_temp_f: float):
    s  = spec.schematic
    eb = EcoBuilder()
    eb.define_temperatures(_SUPPLY_T_F, _STORAGE_T_F)
    if spec.vol is not None:
        eb.define_storage_volume(
            spec.vol, drawdown_fract=spec.drawdown if spec.drawdown != 1.0 else None
        )
    if s in RECIRC_SCHEMATICS:
        eb.define_recirc(_RETURN_T_F, _RETURN_GPM)

    # Primary heaters: a model map is one WaterHeater with num_units; nominal
    # capacity is split evenly across num_heaters WaterHeaters.
    schedule, cmap = _primary_controls(eb, spec)
    if spec.model is not None:
        pm = eb.build_performance_map(spec.model, num_units=spec.num_heaters,
                                      design_inlet_temp_f=design_inlet_temp_f)
        eb.build_water_heater(pm, schedule, cmap)
    else:
        for _ in range(spec.num_heaters):
            _add_heater(eb, spec.cap / spec.num_heaters, schedule, cmap)

    normal_only = eb.build_control_schedule()
    if spec.tm is not None:
        eb.define_storage_volume(spec.tm[0], "tm")
        tm_on, tm_off = spec.tm_temps or (_SUPPLY_T_F, _SUPPLY_T_F + 8.0)
        tm_controls = default_tm_controls(s, _SUPPLY_T_F, tm_on, tm_off)
        _add_heater(eb, spec.tm[1], normal_only, {"normal": tm_controls}, system="tm")

    if s == "sprtp_in_parallel":
        on_f, on_t, off_f, off_t = spec.gas_controls or (
            default_gas_controls.on_sensor_fract, default_gas_controls.on_trigger_t_f,
            default_gas_controls.off_sensor_fract, default_gas_controls.off_trigger_t_f,
        )
        gas_controls = eb.build_control_setting(on_f, on_t, off_f, off_t, _STORAGE_T_F)
        _add_heater(eb, spec.gas[1], normal_only, {"normal": gas_controls}, fuel_type="gas")
    elif s in IN_SERIES_SCHEMATICS:
        eb.define_storage_volume(spec.gas[0], "in_series")
        _add_heater(eb, spec.gas[1], normal_only,
                    {"normal": default_in_series_gas_controls(_SUPPLY_T_F)},
                    fuel_type="gas", system="in_series")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        system = eb.build_system(s)
        building = eb.build_building(zip_code_or_climate_zone=spec.climate_key, **_BUILDING)
        return system, simulate_3day(system, building)


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

_SERIES = (
    "dhw_demand_supplyT_gal", "usable_volume_supplyT_gal", "heater_output_kbtuh",
    "heater_power_in_kw", "oat_f", "inlet_water_temp_f", "heater_mode",
    "tm_tank_temp_f", "tm_heater_output_kbtuh", "tm_heater_input_kw", "delivery_temp_f",
)


def _assert_series_equal(name: str, actual: list, expected: list) -> None:
    assert len(actual) == len(expected), f"{name}: length {len(actual)} != {len(expected)}"
    for i, (a, e) in enumerate(zip(actual, expected)):
        if isinstance(e, (int, float)) and not isinstance(e, bool) and a is not None:
            assert a == pytest.approx(e, rel=_REL, abs=1e-9), f"{name}[{i}]: {a} != {e}"
        else:
            assert a == e, f"{name}[{i}]: {a!r} != {e!r}"


class TestBuilderMatchesEngine:
    def test_every_schematic_covered(self):
        assert {key.split("|")[0] for key in _CASES} == set(SCHEMATICS)

    @pytest.mark.parametrize("case", list(_CASES))
    def test_same_3day_simulation(self, case):
        spec = _CASES[case]
        engine, engine_run = _engine_run(spec)
        design_inlet = engine._building.get_design_inlet_water_temp_f() or 50.0
        builder_system, builder_run = _builder_run(spec, design_inlet)

        assert type(builder_system) is type(engine._dhw_system)

        for name in _SERIES:
            _assert_series_equal(name, getattr(builder_run, name), getattr(engine_run, name))
        for node, (b_node, e_node) in enumerate(zip(builder_run.tank_temps_f, engine_run.tank_temps_f)):
            _assert_series_equal(f"tank_temps_f[{node}]", b_node, e_node)
        assert builder_run.outage_minutes == engine_run.outage_minutes
        assert builder_run.stopped_early  == engine_run.stopped_early
        assert builder_run.is_successful() == engine_run.is_successful()
