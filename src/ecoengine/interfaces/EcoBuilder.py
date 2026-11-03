"""
EcoBuilder — build a pre-sized DHWSystem component by component.

Where ``EcosizerEngine`` takes one flat set of parameters and sizes the
system, ``EcoBuilder`` lets the caller define each piece (heaters, controls,
tanks, recirc loop) in any order and then assemble them with
``build_system()``. Nothing is sized: the system is built from exactly the
components supplied, so ``_minimum_*`` sizing results are never set.

Example::

    eb = EcoBuilder()
    eb.define_temperatures(supply_temp_f=120.0, storage_temp_f=150.0)
    eb.define_storage_volume(500.0)
    schedule = eb.build_control_schedule([["normal", 0], ["shed", 16], ["normal", 20]])
    cmap = {
        "normal": eb.build_control_setting(0.5, 120.0, 0.1, 150.0, 150.0),
        "shed":   eb.build_control_setting(None, None, None, None, 150.0),
    }
    eb.build_water_heater(eb.build_performance_map(nominal_capacity_kbtuh=300.0),
                          schedule, cmap)
    system   = eb.build_system("primary_no_recirc")
    building = eb.build_building("multi_family", 100, "95823")
"""
from __future__ import annotations

import warnings

from ecoengine.objects.building.Building import Building
from ecoengine.objects.components.heating.Controls import AlwaysOffControls, Controls
from ecoengine.objects.components.heating.PerformanceMap import (
    NominalPerformanceMap,
    PerformanceMap,
)
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.dhwsystems.DHWSystem import DHWSystem
from .system_assembly_utils import (
    IN_SERIES_SCHEMATICS,
    RECIRC_SCHEMATICS,
    SCHEMATICS,
    TM_SCHEMATICS,
    assemble_dhw_system,
    build_building,
    canonical_schematic,
    required_fields,
)

_SYSTEM_SLOTS  = ("primary", "tm", "in_series")
_FUEL_TYPES    = ("electric", "gas")
_MP_SCHEMATICS = frozenset({"multi_pass_rtp", "mprtp_in_series"})

# assemble_dhw_system argument name → EcoBuilder field name (for error messages)
_FIELD_NAMES = {
    "supply_temp_f":       "supply_temp_f",
    "storage_temp_f":      "storage_temp_f",
    "water_heaters":       "water_heaters",
    "storage_vol_gal":     "primary_storage_vol_gal",
    "return_temp_f":       "return_temp_f",
    "return_flow_gpm":     "return_flow_gpm",
    "tm_water_heater":     "tm_water_heaters",
    "tm_storage_vol_gal":  "tm_storage_vol_gal",
    "gas_water_heater":    "in_series_water_heaters",
    "gas_storage_vol_gal": "in_series_storage_vol_gal",
}


class EcoBuilder:
    """
    Collects DHW system components and assembles them into a pre-sized
    DHWSystem.

    Attributes
    ----------
    supply_temp_f, storage_temp_f : float | None
        DHW delivery and storage setpoint temperatures [°F].
    water_heaters : list[WaterHeater]
        Heaters heating the primary storage tank. For ``sprtp_in_parallel``
        this list also holds the single gas backup heater
        (``fuel_type='gas'``).
    tm_water_heaters : list[WaterHeater]
        Heaters for the temperature-maintenance tank, if applicable.
    in_series_water_heaters : list[WaterHeater]
        Gas heaters for the in-series tank (``sprtp_in_series``,
        ``mprtp_in_series``).
    primary_storage_vol_gal, tm_storage_vol_gal, in_series_storage_vol_gal : float | None
        Tank volumes [gal].
    drawdown_fract : float
        Fraction of the primary tank above the cold-water inlet. Only used by
        ``multi_pass_rtp`` and ``mprtp_in_series``. Default 1.0.
    return_temp_f, return_flow_gpm : float | None
        Recirc loop return temperature [°F] and flow rate [GPM].
    """

    def __init__(self, perf_map_dir: str | None = None, climate_data_dir: str | None = None) -> None:
        """
        Parameters
        ----------
        perf_map_dir : str, optional
            Directory with ``maps.json`` and ``pkls/`` used by
            ``build_performance_map()``. Defaults to the bundled data.
        climate_data_dir : str, optional
            Climate data directory used by ``build_building()``. Defaults to
            the bundled data.
        """
        self.perf_map_dir     = perf_map_dir
        self.climate_data_dir = climate_data_dir

        self.supply_temp_f:  float | None = None
        self.storage_temp_f: float | None = None

        self.water_heaters:           list[WaterHeater] = []
        self.tm_water_heaters:        list[WaterHeater] = []
        self.in_series_water_heaters: list[WaterHeater] = []

        self.primary_storage_vol_gal:   float | None = None
        self.tm_storage_vol_gal:        float | None = None
        self.in_series_storage_vol_gal: float | None = None
        self.drawdown_fract:            float        = 1.0

        self.return_temp_f:   float | None = None
        self.return_flow_gpm: float | None = None

    # ------------------------------------------------------------------
    # System-level settings
    # ------------------------------------------------------------------

    def define_temperatures(
        self,
        supply_temp_f: float | None = None,
        storage_temp_f: float | None = None,
    ) -> None:
        """Set (or overwrite) the supply and/or storage temperature [°F]."""
        if supply_temp_f is not None:
            self.supply_temp_f = supply_temp_f
        if storage_temp_f is not None:
            self.storage_temp_f = storage_temp_f

    def define_storage_volume(
        self,
        gal: float,
        storage_type: str = "primary",
        drawdown_fract: float | None = None,
        supply_temp_f: float | None = None,
    ) -> None:
        """
        Set (or overwrite) a tank volume.

        Parameters
        ----------
        gal : float
            Tank volume [gal]. Must be > 0.
        storage_type : str
            ``'primary'``, ``'tm'`` or ``'in_series'``.
        drawdown_fract : float, optional
            ``'primary'`` only: fraction of the tank above the cold-water
            inlet (0 < drawdown_fract <= 1). Only used by multi-pass RTP
            schematics.
        supply_temp_f : float, optional
            Also sets (or overwrites) the supply temperature [°F].

        Raises
        ------
        ValueError
            On an unknown ``storage_type``, a non-positive volume, or an
            invalid ``drawdown_fract``.
        """
        if storage_type not in _SYSTEM_SLOTS:
            raise ValueError(
                f"storage_type must be one of {_SYSTEM_SLOTS}, got {storage_type!r}."
            )
        if gal is None or gal <= 0:
            raise ValueError(f"Storage volume must be > 0 gal, got {gal!r}.")
        if drawdown_fract is not None:
            if storage_type != "primary":
                raise ValueError("drawdown_fract only applies to the primary tank.")
            if not 0.0 < drawdown_fract <= 1.0:
                raise ValueError(f"drawdown_fract must be in (0, 1], got {drawdown_fract!r}.")
            self.drawdown_fract = drawdown_fract

        setattr(self, f"{storage_type}_storage_vol_gal", gal)
        self.define_temperatures(supply_temp_f=supply_temp_f)

    def define_recirc(
        self,
        return_temp_f: float,
        return_flow_gpm: float,
        supply_temp_f: float | None = None,
    ) -> None:
        """
        Set (or overwrite) the recirc loop return temperature [°F] and flow
        [GPM], and optionally the supply temperature [°F].
        """
        self.return_temp_f   = return_temp_f
        self.return_flow_gpm = return_flow_gpm
        self.define_temperatures(supply_temp_f=supply_temp_f)

    # ------------------------------------------------------------------
    # Component builders
    # ------------------------------------------------------------------

    def build_performance_map(
        self,
        model_name: str | None = None,
        nominal_capacity_kbtuh: float | None = None,
        num_units: int = 1,
        design_inlet_temp_f: float = 50.0,
    ) -> PerformanceMap:
        """
        Build a PerformanceMap for use in ``build_water_heater()``.

        Parameters
        ----------
        model_name : str, optional
            Model name from ``maps.json``. When given, the map is loaded from
            the registry and ``nominal_capacity_kbtuh`` (total, all units) is
            only used as the electric-resistance fallback below the map's
            minimum OAT.
        nominal_capacity_kbtuh : float, optional
            Without ``model_name``: the constant total capacity [kBTU/hr] of a
            ``NominalPerformanceMap``.
        num_units : int
            Number of identical units (model maps only). Default 1.
        design_inlet_temp_f : float
            Fallback inlet temperature for model maps [°F]. Default 50.

        Raises
        ------
        ValueError
            If neither ``model_name`` nor ``nominal_capacity_kbtuh`` is given,
            or ``num_units != 1`` without ``model_name``.
        """
        if model_name is not None:
            return PerformanceMap.from_model_name(
                model_name,
                num_units=num_units,
                design_inlet_temp_f=design_inlet_temp_f,
                nominal_capacity_kbtuh=nominal_capacity_kbtuh,
                perf_map_dir=self.perf_map_dir,
            )
        if nominal_capacity_kbtuh is None:
            raise ValueError("build_performance_map requires model_name or nominal_capacity_kbtuh.")
        if num_units != 1:
            raise ValueError(
                "num_units only applies to model maps; pass the total capacity "
                "as nominal_capacity_kbtuh instead."
            )
        return NominalPerformanceMap(nominal_capacity_kbtuh)

    def build_control_setting(
        self,
        on_sensor_fract: float | None,
        on_trigger_t_f: float | None,
        off_sensor_fract: float | None,
        off_trigger_t_f: float | None,
        outlet_temp_f: float,
    ) -> Controls:
        """
        Build a Controls object for one operating mode of a control map.

        If the four sensor/trigger values are all None, returns an
        ``AlwaysOffControls`` (heater never fires in that mode).

        Raises
        ------
        ValueError
            If only some of the four sensor/trigger values are None.
        """
        sensor_values = (on_sensor_fract, on_trigger_t_f, off_sensor_fract, off_trigger_t_f)
        if all(v is None for v in sensor_values):
            return AlwaysOffControls(outlet_temp_f=outlet_temp_f)
        if any(v is None for v in sensor_values):
            raise ValueError(
                "Set all of on_sensor_fract, on_trigger_t_f, off_sensor_fract and "
                "off_trigger_t_f, or none of them (for an always-off mode)."
            )
        return Controls(
            on_sensor_fract  = on_sensor_fract,
            on_trigger_t_f   = on_trigger_t_f,
            off_sensor_fract = off_sensor_fract,
            off_trigger_t_f  = off_trigger_t_f,
            outlet_temp_f    = outlet_temp_f,
        )

    def build_control_schedule(self, start_times: list[list] | None = None) -> list[str]:
        """
        Build a 24-hour control schedule from mode start hours.

        Each mode runs from its start hour until the next mode's start hour
        (or the end of the day).

        Parameters
        ----------
        start_times : list[[str, int]], optional
            ``[mode, start_hour]`` pairs, in any order. One must start at
            hour 0. None → ``['normal'] * 24``.

            ``[['normal', 0], ['shed', 12], ['normal', 18]]`` → normal except
            hours 12–17 shed.

        Raises
        ------
        ValueError
            If no mode starts at hour 0, an hour is not an int in 0–23, two
            modes share a start hour, or an entry is malformed.
        """
        if start_times is None:
            return ["normal"] * 24

        entries = []
        for entry in start_times:
            if len(entry) != 2:
                raise ValueError(f"Each start time must be [mode, hour], got {entry!r}.")
            mode, hour = entry
            if not isinstance(mode, str):
                raise ValueError(f"Mode must be a string, got {mode!r}.")
            if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
                raise ValueError(f"Start hour must be an int in 0–23, got {hour!r}.")
            entries.append((hour, mode))

        hours = [h for h, _ in entries]
        if len(set(hours)) != len(hours):
            raise ValueError(f"Two modes share a start hour: {start_times!r}.")
        if 0 not in hours:
            raise ValueError(
                f"No mode starts at hour 0, so the start of the day is ambiguous: {start_times!r}."
            )

        entries.sort()
        schedule = []
        for i, (start, mode) in enumerate(entries):
            end = entries[i + 1][0] if i + 1 < len(entries) else 24
            schedule += [mode] * (end - start)
        return schedule

    def build_water_heater(
        self,
        performance_map: PerformanceMap,
        control_schedule: list[str],
        control_map: dict[str, Controls],
        fuel_type: str = "electric",
        system: str | None = "primary",
    ) -> WaterHeater:
        """
        Build a WaterHeater and add it to a heater list.

        Parameters
        ----------
        performance_map : PerformanceMap
            From ``build_performance_map()``.
        control_schedule : list[str]
            24-element schedule, e.g. from ``build_control_schedule()``.
        control_map : dict[str, Controls]
            Controls for every mode in ``control_schedule``.
        fuel_type : str
            ``'electric'`` or ``'gas'``.
        system : str | None
            ``'primary'`` → ``water_heaters``, ``'tm'`` → ``tm_water_heaters``,
            ``'in_series'`` → ``in_series_water_heaters``, None → not added
            to any list (just returned).

        Raises
        ------
        ValueError
            On an unknown ``system`` or ``fuel_type``, a schedule that is not
            24 entries long, or schedule modes missing from ``control_map``.
        TypeError
            If ``performance_map`` is not a PerformanceMap.
        """
        if system is not None and system not in _SYSTEM_SLOTS:
            raise ValueError(f"system must be one of {_SYSTEM_SLOTS} or None, got {system!r}.")
        if fuel_type not in _FUEL_TYPES:
            raise ValueError(f"fuel_type must be one of {_FUEL_TYPES}, got {fuel_type!r}.")
        if not isinstance(performance_map, PerformanceMap):
            raise TypeError(
                "performance_map must be a PerformanceMap; use build_performance_map()."
            )
        if len(control_schedule) != 24:
            raise ValueError(
                f"control_schedule must have 24 entries, got {len(control_schedule)}."
            )
        missing_modes = sorted(set(control_schedule) - set(control_map))
        if missing_modes:
            raise ValueError(f"control_map has no Controls for mode(s): {', '.join(missing_modes)}.")

        heater = WaterHeater(
            performance_map  = performance_map,
            control_schedule = list(control_schedule),
            control_map      = dict(control_map),
            fuel_type        = fuel_type,
        )
        if system is not None:
            getattr(self, "water_heaters" if system == "primary" else f"{system}_water_heaters").append(heater)
        return heater

    def build_building(
        self,
        building_type: str,
        magnitude: int | float,
        zip_code_or_climate_zone,
        gpdpp: float | None = None,
        custom_peak_load_shape: list[float] | None = None,
        custom_avg_load_shape: list[float] | None = None,
    ) -> Building:
        """
        Build and return a Building. The Building is not stored on the builder.

        ``zip_code_or_climate_zone`` takes the same forms as in
        ``EcosizerEngine``: a 5-digit CA zip string, a zone ID int, a weather
        station name, or a dict with ``'design_oat_f'`` and/or
        ``'design_inlet_water_temp_f'``.
        """
        return build_building(
            building_type            = building_type,
            magnitude                = magnitude,
            zip_code_or_climate_zone = zip_code_or_climate_zone,
            gpdpp                    = gpdpp,
            custom_peak_load_shape   = custom_peak_load_shape,
            custom_avg_load_shape    = custom_avg_load_shape,
            climate_data_dir         = self.climate_data_dir,
        )

    # ------------------------------------------------------------------
    # Assembly
    # ------------------------------------------------------------------

    def build_system(self, schematic: str) -> DHWSystem:
        """
        Assemble the defined components into a DHWSystem.

        No sizing is done and no controls are overridden: every heater runs
        on the control map it was built with. Heater objects are shared with
        the returned system, so building twice from the same builder gives
        two systems that share heaters.

        Schematic notes
        ---------------
        * ``sprtp_in_parallel``: exactly one primary heater must have
          ``fuel_type='gas'``; it becomes the gas backup heater.
        * ``parallel_loop``: the TM tank's cycling temperatures are taken
          from the TM heater's hour-0 controls (``on_trigger_t_f`` /
          ``off_trigger_t_f``).
        * TM and in-series slots accept one heater for now.

        Raises
        ------
        ValueError
            If the schematic is unknown, required fields are missing (all
            listed in one message), or heater counts are wrong.
        """
        name = canonical_schematic(schematic)
        if name not in SCHEMATICS:
            raise ValueError(
                f"Unknown schematic {schematic!r}. Supported values: {', '.join(SCHEMATICS)}."
            )

        primary_heaters = list(self.water_heaters)
        gas_heater = None
        if name == "sprtp_in_parallel":
            gas_heaters = [wh for wh in primary_heaters if wh.fuel_type == "gas"]
            if len(gas_heaters) != 1:
                raise ValueError(
                    "sprtp_in_parallel requires exactly one primary heater with "
                    f"fuel_type='gas'; found {len(gas_heaters)}."
                )
            gas_heater      = gas_heaters[0]
            primary_heaters = [wh for wh in primary_heaters if wh is not gas_heater]
        elif name in IN_SERIES_SCHEMATICS:
            gas_heater = self._single_heater(self.in_series_water_heaters, "in_series_water_heaters", name)

        tm_heater = (
            self._single_heater(self.tm_water_heaters, "tm_water_heaters", name)
            if name in TM_SCHEMATICS else None
        )

        fields = {
            "supply_temp_f":       self.supply_temp_f,
            "storage_temp_f":      self.storage_temp_f,
            "water_heaters":       primary_heaters,
            "storage_vol_gal":     self.primary_storage_vol_gal,
            "return_temp_f":       self.return_temp_f,
            "return_flow_gpm":     self.return_flow_gpm,
            "tm_water_heater":     tm_heater,
            "tm_storage_vol_gal":  self.tm_storage_vol_gal,
            "gas_water_heater":    gas_heater,
            "gas_storage_vol_gal": self.in_series_storage_vol_gal,
        }
        missing = [
            _FIELD_NAMES[f] for f in required_fields(name)
            if fields[f] is None or fields[f] == []
        ]
        if missing:
            raise ValueError(f"Schematic '{name}' requires: {', '.join(missing)}.")

        self._warn_unused_fields(name)

        tm_on_temp_f = tm_off_temp_f = None
        if name == "parallel_loop":
            tm_controls   = tm_heater.get_controls_for_hour(0)
            tm_on_temp_f  = tm_controls.on_trigger_t_f
            tm_off_temp_f = tm_controls.off_trigger_t_f

        return assemble_dhw_system(
            name,
            primary_heaters,
            self.supply_temp_f,
            self.storage_temp_f,
            self.primary_storage_vol_gal,
            return_temp_f       = self.return_temp_f,
            return_flow_gpm     = self.return_flow_gpm,
            tm_water_heater     = tm_heater,
            tm_storage_vol_gal  = self.tm_storage_vol_gal,
            tm_on_temp_f        = tm_on_temp_f,
            tm_off_temp_f       = tm_off_temp_f,
            gas_water_heater    = gas_heater,
            gas_storage_vol_gal = self.in_series_storage_vol_gal,
            drawdown_fract      = self.drawdown_fract,
        )

    @staticmethod
    def _single_heater(heaters: list[WaterHeater], field: str, schematic: str) -> WaterHeater | None:
        """Return the only heater in ``heaters`` (None if empty); error if more than one."""
        if len(heaters) > 1:
            raise ValueError(
                f"Schematic '{schematic}' supports one heater in {field} for now; "
                f"found {len(heaters)}."
            )
        return heaters[0] if heaters else None

    def _warn_unused_fields(self, schematic: str) -> None:
        """Warn about defined fields that ``schematic`` does not use."""
        unused = []
        if schematic == "instant_wh" and self.primary_storage_vol_gal is not None:
            unused.append("primary_storage_vol_gal")
        if schematic not in RECIRC_SCHEMATICS and (
            self.return_temp_f is not None or self.return_flow_gpm is not None
        ):
            unused.append("return_temp_f / return_flow_gpm")
        if schematic not in TM_SCHEMATICS:
            if self.tm_water_heaters:
                unused.append("tm_water_heaters")
            if self.tm_storage_vol_gal is not None:
                unused.append("tm_storage_vol_gal")
        if schematic not in IN_SERIES_SCHEMATICS:
            if self.in_series_water_heaters:
                unused.append("in_series_water_heaters")
            if self.in_series_storage_vol_gal is not None:
                unused.append("in_series_storage_vol_gal")
        if schematic not in _MP_SCHEMATICS and self.drawdown_fract != 1.0:
            unused.append("drawdown_fract")
        if unused:
            warnings.warn(
                f"Schematic '{schematic}' does not use: {', '.join(unused)}. These will be ignored.",
                stacklevel=3,
            )
