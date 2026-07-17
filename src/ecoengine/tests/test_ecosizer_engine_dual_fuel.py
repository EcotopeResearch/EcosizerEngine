"""
Unit tests for EcosizerEngine._build_dhw_system()'s dual-fuel schematics:
'sprtp_in_series', 'sprtp_in_parallel', 'mprtp_in_series', 'swing_dual_fuel'.

These schematics always require heating_capacity_kbtuh and
storage_volume_storageT_gal (the primary heater/tank is intentionally capped
at these values, never auto-sized) and bypass the generic pre-sized dispatch
in favor of each class's own from_size(), which also auto-sizes a gas backup.

Test groups
-----------
TestRequiredSizingParams  — ValueError when heating_capacity_kbtuh /
                             storage_volume_storageT_gal are missing
TestBuildsCorrectClass    — _dhw_system is an instance of the expected class
TestThreeDaySim           — sized system must pass the 3-day design-day sim
"""
import pytest

from ecoengine.interfaces.EcosizerEngine import EcosizerEngine
from ecoengine.objects.dhwsystems.rtp_systems.SP_RTPInSeriesSystem import SP_RTPInSeriesSystem
from ecoengine.objects.dhwsystems.rtp_systems.SP_RTPInParallelSystem import SP_RTPInParallelSystem
from ecoengine.objects.dhwsystems.rtp_systems.MP_RTPInSeriesSystem import MP_RTPInSeriesSystem
from ecoengine.objects.dhwsystems.recirc_systems.SwingDualFuelSystem import SwingDualFuelSystem

# ---------------------------------------------------------------------------
# Shared parameters
# ---------------------------------------------------------------------------
_DESIGN_OAT_F   = 47.0
_DESIGN_INLET_F = 55.0
_SUPPLY_T_F     = 120.0
_STORAGE_T_F    = 140.0
_RETURN_T_F     = 100.0
_RETURN_GPM     = 3.0

_NOMINAL_CAPACITY_KBTUH = 40.0
_NOMINAL_STORAGE_GAL    = 150.0

_DUAL_FUEL_SCHEMATICS = [
    ("sprtp_in_series",   SP_RTPInSeriesSystem),
    ("sprtp_in_parallel", SP_RTPInParallelSystem),
    ("mprtp_in_series",   MP_RTPInSeriesSystem),
    ("swing_dual_fuel",   SwingDualFuelSystem),
]

# SwingDualFuelSystem names its backup heater tm_water_heater (swing-tank
# element); the three RTP dual-fuel classes name it gas_water_heater.
_BACKUP_HEATER_ATTR = {
    SP_RTPInSeriesSystem:   "gas_water_heater",
    SP_RTPInParallelSystem: "gas_water_heater",
    MP_RTPInSeriesSystem:   "gas_water_heater",
    SwingDualFuelSystem:    "tm_water_heater",
}


def _common_kwargs() -> dict:
    """Base EcosizerEngine kwargs shared by all dual-fuel schematic tests."""
    return dict(
        building_type            = "multi_family",
        magnitude                = 100,
        gpdpp                    = 25,
        zip_code_or_climate_zone = {
            "design_oat_f": _DESIGN_OAT_F,
            "design_inlet_water_temp_f": _DESIGN_INLET_F,
        },
        supply_temp_f   = _SUPPLY_T_F,
        storage_temp_f  = _STORAGE_T_F,
        return_temp_f   = _RETURN_T_F,
        return_flow_gpm = _RETURN_GPM,
    )


def _build_engine(schematic: str, **overrides) -> EcosizerEngine:
    kwargs = _common_kwargs()
    kwargs.update(overrides)
    return EcosizerEngine(schematic=schematic, **kwargs)


# ---------------------------------------------------------------------------
# TestRequiredSizingParams — ValueError when sizing params are missing
# ---------------------------------------------------------------------------

@pytest.mark.filterwarnings("ignore::UserWarning")
class TestRequiredSizingParams:
    """
    heating_capacity_kbtuh and storage_volume_storageT_gal are both required
    (not optional) for dual-fuel schematics; missing either raises ValueError.
    """

    @pytest.mark.parametrize("schematic, cls", _DUAL_FUEL_SCHEMATICS)
    def test_missing_both_raises(self, schematic, cls):
        with pytest.raises(ValueError, match="heating_capacity_kbtuh"):
            _build_engine(schematic)

    @pytest.mark.parametrize("schematic, cls", _DUAL_FUEL_SCHEMATICS)
    def test_missing_heating_capacity_raises(self, schematic, cls):
        with pytest.raises(ValueError, match="heating_capacity_kbtuh"):
            _build_engine(schematic, storage_volume_storageT_gal=_NOMINAL_STORAGE_GAL)

    @pytest.mark.parametrize("schematic, cls", _DUAL_FUEL_SCHEMATICS)
    def test_missing_storage_volume_raises(self, schematic, cls):
        with pytest.raises(ValueError, match="storage_volume_storageT_gal"):
            _build_engine(schematic, heating_capacity_kbtuh=_NOMINAL_CAPACITY_KBTUH)

    @pytest.mark.parametrize("schematic, cls", _DUAL_FUEL_SCHEMATICS)
    def test_both_provided_does_not_raise(self, schematic, cls):
        _build_engine(
            schematic,
            heating_capacity_kbtuh=_NOMINAL_CAPACITY_KBTUH,
            storage_volume_storageT_gal=_NOMINAL_STORAGE_GAL,
        )


# ---------------------------------------------------------------------------
# TestBuildsCorrectClass — _dhw_system is an instance of the expected class
# ---------------------------------------------------------------------------

@pytest.mark.filterwarnings("ignore::UserWarning")
class TestBuildsCorrectClass:
    """Each dual-fuel schematic dispatches to its corresponding DHWSystem subclass."""

    @pytest.mark.parametrize("schematic, cls", _DUAL_FUEL_SCHEMATICS)
    def test_dhw_system_is_expected_class(self, schematic, cls):
        engine = _build_engine(
            schematic,
            heating_capacity_kbtuh=_NOMINAL_CAPACITY_KBTUH,
            storage_volume_storageT_gal=_NOMINAL_STORAGE_GAL,
        )
        assert isinstance(engine._dhw_system, cls)

    @pytest.mark.parametrize("schematic, cls", _DUAL_FUEL_SCHEMATICS)
    def test_backup_heater_capacity_positive(self, schematic, cls):
        engine = _build_engine(
            schematic,
            heating_capacity_kbtuh=_NOMINAL_CAPACITY_KBTUH,
            storage_volume_storageT_gal=_NOMINAL_STORAGE_GAL,
        )
        backup_heater = getattr(engine._dhw_system, _BACKUP_HEATER_ATTR[cls])
        cap = backup_heater.get_capacity_kbtuh(_DESIGN_OAT_F, _STORAGE_T_F)
        assert cap > 0.0


# ---------------------------------------------------------------------------
# TestThreeDaySim — sized system must pass the 3-day design-day sim
# ---------------------------------------------------------------------------

@pytest.mark.filterwarnings("ignore::UserWarning")
class TestThreeDaySim:
    """Every dual-fuel schematic, once sized via EcosizerEngine, must pass simulate_3day()."""

    @pytest.mark.parametrize("schematic, cls", _DUAL_FUEL_SCHEMATICS)
    def test_three_day_sim_passes(self, schematic, cls):
        engine = _build_engine(
            schematic,
            heating_capacity_kbtuh=_NOMINAL_CAPACITY_KBTUH,
            storage_volume_storageT_gal=_NOMINAL_STORAGE_GAL,
        )
        sim = engine.simulate_3day()
        assert sim.is_successful(), sim.get_failure_message()
