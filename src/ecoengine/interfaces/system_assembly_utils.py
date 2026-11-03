"""
Shared helpers for building Buildings and assembling pre-sized DHWSystems.

Used by both ``EcosizerEngine`` (flat-parameter interface) and ``EcoBuilder``
(component-by-component interface), so that schematic dispatch, tank types,
stratification slopes, and required-field checks live in one place.

``assemble_dhw_system`` only wires components together. It never sizes
anything and never sets the ``_minimum_*`` sizing-result fields; callers that
have sizing values (``EcosizerEngine``) set those on the returned system.
"""
from __future__ import annotations

from ecoengine.objects.building.Building import Building
from ecoengine.objects.building.ClimateZone import ClimateZone
from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.storage.EnergyTank import EnergyTank
from ecoengine.objects.components.storage.MixedStorageTank import MixedStorageTank
from ecoengine.objects.components.storage.SlugOverlayTank import SlugOverlayTank
from ecoengine.objects.components.storage.StratifiedTank import StratifiedTank
from ecoengine.objects.dhwsystems.DHWSystem import DHWSystem
from ecoengine.objects.dhwsystems.InstantWHSystem import InstantWHSystem
from ecoengine.objects.dhwsystems.recirc_systems.ParallelLoopSystem import ParallelLoopSystem
from ecoengine.objects.dhwsystems.recirc_systems.SwingDualFuelSystem import SwingDualFuelSystem
from ecoengine.objects.dhwsystems.recirc_systems.SwingSystem import SwingSystem, _ELEMENT_DEADBAND_F
from ecoengine.objects.dhwsystems.rtp_systems.MP_RTPInSeriesSystem import MP_RTPInSeriesSystem
from ecoengine.objects.dhwsystems.rtp_systems.MultiPassRTPSystem import (
    MultiPassRTPSystem, _MPRTP_STRAT_SLOPE, _MPRTP_MAX_DAILY_RUN_HR,
)
from ecoengine.objects.dhwsystems.rtp_systems.SP_RTPInParallelSystem import SP_RTPInParallelSystem
from ecoengine.objects.dhwsystems.rtp_systems.SP_RTPInSeriesSystem import (
    SP_RTPInSeriesSystem, _GAS_DEADBAND_F,
)
from ecoengine.objects.dhwsystems.rtp_systems.SinglePassRTPSystem import (
    SinglePassRTPSystem, _SPRTP_STRAT_SLOPE,
)

# Legacy schematic names accepted as aliases for the canonical names.
_SCHEMATIC_ALIASES = {
    "singlepass_norecirc": "primary_no_recirc",
    "paralleltank":        "parallel_loop",
    "swingtank":           "swing_tank",
    "sprtp":               "single_pass_rtp",
    "mprtp":               "multi_pass_rtp",
}

SCHEMATICS = (
    "primary_no_recirc", "parallel_loop", "swing_tank", "single_pass_rtp",
    "multi_pass_rtp", "instant_wh", "sprtp_in_series", "sprtp_in_parallel",
    "mprtp_in_series", "swing_dual_fuel",
)
RECIRC_SCHEMATICS = frozenset({
    "parallel_loop", "swing_tank", "single_pass_rtp", "multi_pass_rtp",
    "sprtp_in_series", "sprtp_in_parallel", "mprtp_in_series", "swing_dual_fuel",
})
TM_SCHEMATICS        = frozenset({"parallel_loop", "swing_tank", "swing_dual_fuel"})
IN_SERIES_SCHEMATICS = frozenset({"sprtp_in_series", "mprtp_in_series"})
GAS_SCHEMATICS       = IN_SERIES_SCHEMATICS | {"sprtp_in_parallel"}


def canonical_schematic(schematic: str) -> str:
    """Return the canonical schematic name, resolving legacy aliases."""
    return _SCHEMATIC_ALIASES.get(schematic, schematic)


# ---------------------------------------------------------------------------
# Building / climate
# ---------------------------------------------------------------------------

def build_climate_zone(zip_code_or_climate_zone, climate_data_dir: str | None = None) -> ClimateZone:
    """
    Resolve a climate lookup key to a ClimateZone.

    Accepted forms: 5-digit CA zip code string → ``from_zip_code()``; int →
    ``from_zone_id()``; other string → ``from_weather_station()``; dict with
    ``'design_oat_f'`` and/or ``'design_inlet_water_temp_f'`` →
    ``from_design_conditions()``.
    """
    czv = zip_code_or_climate_zone
    cdd = climate_data_dir
    if isinstance(czv, dict):
        return ClimateZone.from_design_conditions(**czv)
    if isinstance(czv, str) and czv.isdigit() and len(czv) == 5:
        return ClimateZone.from_zip_code(czv, climate_data_dir=cdd)
    if isinstance(czv, int):
        return ClimateZone.from_zone_id(czv, climate_data_dir=cdd)
    if isinstance(czv, str):
        return ClimateZone.from_weather_station(czv, climate_data_dir=cdd)
    raise ValueError(
        f"Cannot determine ClimateZone from {czv!r}. "
        "Pass a 5-digit CA zip code string, a zone ID int (1–96), "
        "a weather station name string, or a dict with 'design_oat_f' "
        "and/or 'design_inlet_water_temp_f'."
    )


def build_building(
    building_type: str,
    magnitude: int | float,
    zip_code_or_climate_zone,
    gpdpp: float | None = None,
    custom_peak_load_shape: list[float] | None = None,
    custom_avg_load_shape: list[float] | None = None,
    climate_data_dir: str | None = None,
) -> Building:
    """Construct a Building for the given type, occupancy and climate lookup key."""
    return Building.from_building_type(
        building_type           = building_type,
        magnitude               = magnitude,
        climate_zone            = build_climate_zone(zip_code_or_climate_zone, climate_data_dir),
        gpdpp                   = gpdpp,
        custom_peak_load_shape  = custom_peak_load_shape,
        custom_avg_load_shape   = custom_avg_load_shape,
    )


# ---------------------------------------------------------------------------
# Default secondary-heater controls (used by EcosizerEngine)
# ---------------------------------------------------------------------------

def default_tm_controls(
    schematic: str,
    supply_temp_f: float,
    tm_on_temp_f: float | None = None,
    tm_off_temp_f: float | None = None,
) -> Controls:
    """
    Default TM heater Controls for ``parallel_loop``, ``swing_tank`` and
    ``swing_dual_fuel``.

    Parallel loop cycles between ``tm_on_temp_f`` and ``tm_off_temp_f``; the
    swing variants cycle from ``supply_temp_f`` up by ``_ELEMENT_DEADBAND_F``.
    """
    if canonical_schematic(schematic) == "parallel_loop":
        return Controls(
            on_sensor_fract=0.5,
            on_trigger_t_f=tm_on_temp_f,
            off_sensor_fract=0.5,
            off_trigger_t_f=tm_off_temp_f,
            outlet_temp_f=tm_off_temp_f,
        )
    return Controls(
        on_sensor_fract=0.5,
        on_trigger_t_f=supply_temp_f,
        off_sensor_fract=0.5,
        off_trigger_t_f=supply_temp_f + _ELEMENT_DEADBAND_F,
        outlet_temp_f=supply_temp_f + _ELEMENT_DEADBAND_F,
    )


def default_in_series_gas_controls(supply_temp_f: float) -> Controls:
    """Default gas heater Controls for ``sprtp_in_series`` and ``mprtp_in_series``."""
    return Controls(
        on_sensor_fract=0.5,
        on_trigger_t_f=supply_temp_f + 5.0,
        off_sensor_fract=0.5,
        off_trigger_t_f=supply_temp_f + 5.0 + _GAS_DEADBAND_F,
        outlet_temp_f=supply_temp_f + 5.0 + _GAS_DEADBAND_F,
    )


# ---------------------------------------------------------------------------
# DHWSystem assembly
# ---------------------------------------------------------------------------

def required_fields(schematic: str) -> list[str]:
    """
    ``assemble_dhw_system`` argument names that ``schematic`` needs set.

    Callers with their own field names (e.g. ``EcoBuilder``) can map these to
    report missing fields in their own terms.
    """
    schematic = canonical_schematic(schematic)
    required = ["supply_temp_f", "storage_temp_f", "water_heaters"]
    if schematic != "instant_wh":
        required.append("storage_vol_gal")
    if schematic in RECIRC_SCHEMATICS:
        required += ["return_temp_f", "return_flow_gpm"]
    if schematic in TM_SCHEMATICS:
        required += ["tm_water_heater", "tm_storage_vol_gal"]
    if schematic in GAS_SCHEMATICS:
        required.append("gas_water_heater")
    if schematic in IN_SERIES_SCHEMATICS:
        required.append("gas_storage_vol_gal")
    return required


def _missing_fields(schematic: str, fields: dict) -> list[str]:
    """Names of fields the schematic needs that are unset (None / empty)."""
    return [
        name for name in required_fields(schematic)
        if fields[name] is None or fields[name] == []
    ]


def assemble_dhw_system(
    schematic: str,
    water_heaters: list[WaterHeater],
    supply_temp_f: float,
    storage_temp_f: float,
    storage_vol_gal: float | None = None,
    *,
    return_temp_f: float | None = None,
    return_flow_gpm: float | None = None,
    tm_water_heater: WaterHeater | None = None,
    tm_storage_vol_gal: float | None = None,
    num_tm_heaters: int = 1,
    tm_on_temp_f: float | None = None,
    tm_off_temp_f: float | None = None,
    gas_water_heater: WaterHeater | None = None,
    gas_storage_vol_gal: float | None = None,
    cold_temp_f: float = 50.0,
    drawdown_fract: float = 1.0,
    max_daily_run_hr: float = 16.0,
    defrost_factor: float = 1.0,
    tm_safety_factor: float = 1.75,
    tm_off_time_hr: float = 0.5,
) -> DHWSystem:
    """
    Wire pre-built components into the DHWSystem subclass for ``schematic``.

    The schematic determines the system class, primary tank type and
    stratification slope. No sizing is performed and no ``_minimum_*``
    sizing-result fields are set.

    Parameters
    ----------
    schematic : str
        One of ``SCHEMATICS`` (legacy aliases accepted).
    water_heaters : list[WaterHeater]
        Primary heaters.
    supply_temp_f, storage_temp_f : float
        DHW delivery and storage setpoint temperatures [°F].
    storage_vol_gal : float, optional
        Primary tank volume [gal]. Required for all schematics except
        ``instant_wh``.
    return_temp_f, return_flow_gpm : float, optional
        Recirc loop return temperature [°F] and flow [GPM]. Required for
        recirc and RTP schematics.
    tm_water_heater, tm_storage_vol_gal : optional
        TM heater and tank volume [gal] for ``parallel_loop``, ``swing_tank``
        and ``swing_dual_fuel`` (gas swing tank).
    num_tm_heaters : int
        ``parallel_loop`` only: TM output multiplier. Default 1.
    tm_on_temp_f, tm_off_temp_f : float, optional
        ``parallel_loop`` only: TM tank cycling temperatures used during
        simulation. Default ``supply_temp_f`` and ``supply_temp_f + 8``.
    gas_water_heater : WaterHeater, optional
        Gas backup heater for ``sprtp_in_series``, ``mprtp_in_series`` and
        ``sprtp_in_parallel``.
    gas_storage_vol_gal : float, optional
        Gas tank volume [gal] for ``sprtp_in_series`` and ``mprtp_in_series``.
    cold_temp_f : float
        Initial cold temperature for RTP tanks [°F]. Default 50. Simulations
        re-initialize the tank, so this mainly matters for sizing.
    drawdown_fract : float
        ``multi_pass_rtp`` / ``mprtp_in_series`` only: fraction of the primary
        tank above the cold-water inlet. Default 1.0.
    max_daily_run_hr, defrost_factor, tm_safety_factor, tm_off_time_hr : float
        Stored on the system for sizing-related methods; not used to build it.

    Raises
    ------
    ValueError
        If the schematic is unknown, or any field it needs is missing (all
        missing fields are listed in one message).
    """
    schematic = canonical_schematic(schematic)
    if schematic not in SCHEMATICS:
        raise ValueError(
            f"Unknown schematic {schematic!r}. "
            "Supported values: 'primary_no_recirc', 'parallel_loop', 'swing_tank', "
            "'single_pass_rtp', 'multi_pass_rtp', 'instant_wh', 'sprtp_in_series', "
            "'sprtp_in_parallel', 'mprtp_in_series', 'swing_dual_fuel'."
        )
    missing = _missing_fields(schematic, {
        "supply_temp_f":       supply_temp_f,
        "storage_temp_f":      storage_temp_f,
        "water_heaters":       water_heaters,
        "storage_vol_gal":     storage_vol_gal,
        "return_temp_f":       return_temp_f,
        "return_flow_gpm":     return_flow_gpm,
        "tm_water_heater":     tm_water_heater,
        "tm_storage_vol_gal":  tm_storage_vol_gal,
        "gas_water_heater":    gas_water_heater,
        "gas_storage_vol_gal": gas_storage_vol_gal,
    })
    if missing:
        raise ValueError(f"Schematic '{schematic}' requires: {', '.join(missing)}.")

    temps  = dict(supply_temp_f=supply_temp_f, storage_temp_f=storage_temp_f)
    recirc = dict(return_temp_f=return_temp_f, return_flow_gpm=return_flow_gpm)

    if schematic == "primary_no_recirc":
        return DHWSystem(
            water_heaters=water_heaters,
            storage_tank=StratifiedTank(total_volume_gal=storage_vol_gal),
            max_daily_run_hr=max_daily_run_hr,
            defrost_factor=defrost_factor,
            **temps,
        )

    if schematic == "parallel_loop":
        return ParallelLoopSystem(
            water_heaters=water_heaters,
            storage_tank=StratifiedTank(total_volume_gal=storage_vol_gal),
            tm_on_temp_f=tm_on_temp_f if tm_on_temp_f is not None else supply_temp_f,
            tm_off_temp_f=tm_off_temp_f if tm_off_temp_f is not None else supply_temp_f + 8.0,
            tm_off_time_hr=tm_off_time_hr,
            tm_safety_factor=tm_safety_factor,
            tm_storage_tank=MixedStorageTank(total_volume_gal=tm_storage_vol_gal),
            tm_water_heater=tm_water_heater,
            num_tm_heaters=num_tm_heaters,
            max_daily_run_hr=max_daily_run_hr,
            defrost_factor=defrost_factor,
            **temps,
            **recirc,
        )

    if schematic in ("swing_tank", "swing_dual_fuel"):
        system_cls = SwingSystem if schematic == "swing_tank" else SwingDualFuelSystem
        system = system_cls(
            water_heaters=water_heaters,
            storage_tank=StratifiedTank(total_volume_gal=storage_vol_gal),
            tm_safety_factor=tm_safety_factor,
            max_daily_run_hr=max_daily_run_hr,
            defrost_factor=defrost_factor,
            **temps,
            **recirc,
        )
        system.tm_storage_tank = MixedStorageTank(total_volume_gal=tm_storage_vol_gal)
        system.tm_water_heater = tm_water_heater
        return system

    if schematic == "instant_wh":
        system = InstantWHSystem(defrost_factor=defrost_factor, **temps)
        system.water_heaters = water_heaters
        return system

    # --- RTP family ---
    if schematic in ("single_pass_rtp", "sprtp_in_series", "sprtp_in_parallel"):
        system_cls = {
            "single_pass_rtp":   SinglePassRTPSystem,
            "sprtp_in_series":   SP_RTPInSeriesSystem,
            "sprtp_in_parallel": SP_RTPInParallelSystem,
        }[schematic]
        storage_tank = EnergyTank(
            total_volume_gal=storage_vol_gal,
            cold_temp_f=cold_temp_f,
            storage_temp_f=storage_temp_f,
            strat_slope=_SPRTP_STRAT_SLOPE,
        )
        run_hr = max_daily_run_hr
    else:  # multi_pass_rtp, mprtp_in_series
        system_cls = MultiPassRTPSystem if schematic == "multi_pass_rtp" else MP_RTPInSeriesSystem
        storage_tank = SlugOverlayTank(
            total_volume_gal=storage_vol_gal,
            cold_temp_f=cold_temp_f,
            storage_temp_f=storage_temp_f,
            supply_temp_f=supply_temp_f,
            strat_slope=_MPRTP_STRAT_SLOPE,
            drawdown_fract=drawdown_fract,
        )
        run_hr = _MPRTP_MAX_DAILY_RUN_HR

    system = system_cls(
        water_heaters=water_heaters,
        storage_tank=storage_tank,
        max_daily_run_hr=run_hr,
        defrost_factor=defrost_factor,
        tm_safety_factor=tm_safety_factor,
        **temps,
        **recirc,
    )
    if schematic in GAS_SCHEMATICS:
        system.gas_water_heater = gas_water_heater
    if schematic in IN_SERIES_SCHEMATICS:
        system.gas_storage_tank = MixedStorageTank(total_volume_gal=gas_storage_vol_gal)
    return system
