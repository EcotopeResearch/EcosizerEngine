from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from ecoengine.constants.constants import _HEATING_TYPES
from ecoengine.objects.components.heating.PerformanceMap import NominalPerformanceMap, PerformanceMap

HeatingType = Literal["electric_resistance", "gas", "heat_pump"]

if TYPE_CHECKING:
    from ecoengine.objects.components.heating.Controls import Controls
    from ecoengine.objects.components.storage.StorageTank import StorageTank


class WaterHeater:
    """
    Represents a water heater. And owns a PerformanceMap,
    a control schedule, and a control map. Tracks its own active/inactive state.
    The Performance map can be used to simulate heat pump, gas fired, or electric resitance. 

    Control schedule and map
    ------------------------
    control_schedule : list[str]
        24-element list (one entry per hour of the day). Each value is a
        string key into control_map, selecting which Controls object is
        active during that hour. Standard keys are ``"normal"``, ``"loadUp"``,
        and ``"shed"``.
    control_map : dict[str, Controls]
        Maps schedule keys to Controls objects. For a simple single-mode
        system use ``{"normal": controls}`` with
        ``control_schedule = ["normal"] * 24``.

        When the map contains only ``"normal"``, the system is not load
        shifting. When it also contains ``"loadUp"`` and/or ``"shed"`` keys,
        load-shift sizing and simulation logic is activated.

    Construction
    ------------
    Use one of the factory class methods rather than calling __init__ directly:

    * WaterHeater.from_nominal_capacity(nominal_capacity_kbtuh, control_schedule, control_map)
        Creates a NominalPerformanceMap (constant-output placeholder). Use this
        during preliminary sizing before a real equipment model is selected.

    * WaterHeater.from_model_name(model_name, control_schedule, control_map)
        Loads a PerformanceMap from the equipment model registry by name. Use
        this when the specific HPWH model is known.
    """

    def __init__(
        self,
        performance_map: PerformanceMap | None,
        control_schedule: list[str] | None,
        control_map: dict[str, Controls] | None,
        heating_type: HeatingType = "heat_pump",
    ) -> None:
        """
        Parameters
        ----------
        performance_map : PerformanceMap | None
            Performance map for this HPWH model. If None, all capacity/power
            queries return None. Prefer the factory class methods.
        control_schedule : list[str] | None
            24-element list mapping each hour to a key in control_map.
            None when no control logic is configured.
        control_map : dict[str, Controls] | None
            Maps schedule strings to Controls objects.
            None when no control logic is configured.
        heating_type : "electric_resistance" | "gas" | "heat_pump"
            Heating technology. Default is "heat_pump". When
            ``performance_map`` is a ``NominalPerformanceMap``, the heater
            stores a copy of it with this heating type, so its power uses the
            matching nominal COP. The passed map is not modified.

        Raises
        ------
        ValueError
            If ``heating_type`` is not a known heating type.
        """
        if heating_type not in _HEATING_TYPES:
            raise ValueError(f"heating_type must be one of {_HEATING_TYPES}, got {heating_type!r}.")
        if isinstance(performance_map, NominalPerformanceMap) and performance_map.heating_type != heating_type:
            performance_map = NominalPerformanceMap(
                performance_map.nominal_capacity_kbtuh,
                model_name=performance_map.model_name,
                heating_type=heating_type,
            )
        self.performance_map  = performance_map
        self.control_schedule = control_schedule
        self.control_map      = control_map
        self.heating_type     = heating_type
        self._active          = False

    # ------------------------------------------------------------------
    # Factory constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_nominal_capacity(
        cls,
        nominal_capacity_kbtuh: float,
        control_schedule: list[str] | None,
        control_map: dict[str, Controls] | None,
        heating_type: HeatingType = "heat_pump",
    ) -> WaterHeater:
        """
        Create a WaterHeater with a constant-capacity placeholder performance map.

        The heater will report nominal_capacity_kbtuh for every OAT and water
        temperature query. Use this during preliminary sizing before a specific
        HPWH model has been selected.

        Parameters
        ----------
        nominal_capacity_kbtuh : float
            Fixed heating output capacity [kBTU/hr].
        control_schedule : list[str] | None
            24-element list mapping each hour to a key in control_map.
        control_map : dict[str, Controls] | None
            Maps schedule strings to Controls objects.
        heating_type : "electric_resistance" | "gas" | "heat_pump"
            Heating technology; selects the nominal COP used for power input.
            Default is "heat_pump".

        Returns
        -------
        WaterHeater
        """
        return cls(
            performance_map=NominalPerformanceMap(nominal_capacity_kbtuh, heating_type=heating_type),
            control_schedule=control_schedule,
            control_map=control_map,
            heating_type=heating_type,
        )

    @classmethod
    def from_model_name(
        cls,
        model_name: str,
        control_schedule: list[str] | None,
        control_map: dict[str, Controls] | None,
        num_units: int = 1,
        design_inlet_temp_f: float = 50.0,
        nominal_capacity_kbtuh: float | None = None,
        heating_type: HeatingType = "heat_pump",
        perf_map_dir: str | None = None,
    ) -> WaterHeater:
        """
        Create a WaterHeater by loading its PerformanceMap from the equipment
        model registry using the model name string.

        Parameters
        ----------
        model_name : str
            Equipment model identifier as it appears in the model registry
            (e.g. ``'Rheem_PROPH80_T2_RH380-30'``).
        control_schedule : list[str] | None
            24-element list mapping each hour to a key in control_map.
        control_map : dict[str, Controls] | None
            Maps schedule strings to Controls objects.
        num_units : int
            Number of identical units deployed; outputs scale linearly. Default 1.
        design_inlet_temp_f : float
            Cold-water inlet temperature used when not supplied per-call. Default 50 °F.
        nominal_capacity_kbtuh : float | None
            Total system capacity for ER fallback sizing. Default None.
        heating_type : "electric_resistance" | "gas" | "heat_pump"
            Heating technology label. Default is "heat_pump". Does not change
            the model map, which has its own power data.
        perf_map_dir : str | None
            Path to directory containing ``maps.json`` and ``pkls/``.
            Passed through to ``PerformanceMap.from_model_name()``.

        Returns
        -------
        WaterHeater
        """
        return cls(
            performance_map=PerformanceMap.from_model_name(
                model_name,
                num_units=num_units,
                design_inlet_temp_f=design_inlet_temp_f,
                nominal_capacity_kbtuh=nominal_capacity_kbtuh,
                perf_map_dir=perf_map_dir,
            ),
            control_schedule=control_schedule,
            control_map=control_map,
            heating_type=heating_type,
        )

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def is_active(self) -> bool:
        """Return True if this heater is currently running."""
        return self._active

    def turn_on(self) -> None:
        """Activate this heater."""
        self._active = True

    def turn_off(self) -> None:
        """Deactivate this heater."""
        self._active = False

    def is_load_shifting(self) -> bool:
        """Return True if this heater has load-shift modes configured."""
        if self.control_map is None:
            return False
        return "loadUp" in self.control_map or "shed" in self.control_map

    def get_controls_for_hour(self, hour_of_day: int) -> Controls | None:
        """
        Return the Controls object active during the given hour.

        Parameters
        ----------
        hour_of_day : int
            Hour of the day (0-23).

        Returns
        -------
        Controls | None
            None if no control schedule/map is configured.
        """
        if self.control_schedule is None or self.control_map is None:
            return None
        key = self.control_schedule[hour_of_day]
        return self.control_map.get(key)

    # ------------------------------------------------------------------
    # Performance queries
    # ------------------------------------------------------------------

    def get_capacity_kbtuh(
        self,
        oat_f: float,
        outlet_temp_f: float,
        inlet_temp_f: float | None = None,
    ) -> float | None:
        """
        Return heating output capacity [kBTU/hr] at current conditions.

        Parameters
        ----------
        oat_f : float
        outlet_temp_f : float
        inlet_temp_f : float | None
            Cold-water inlet temperature. Falls back to the performance map's
            design_inlet_temp_f when not provided.

        Returns
        -------
        float | None
        """
        if self.performance_map is not None:
            return self.performance_map.get_capacity_kbtuh(oat_f, outlet_temp_f, inlet_temp_f)
        return None

    def get_power_in_kw(
        self,
        oat_f: float,
        outlet_temp_f: float,
        inlet_temp_f: float | None = None,
    ) -> float:
        """
        Return actual power input this timestep [kW]: the performance map's
        power if active, 0 if not.

        Parameters
        ----------
        oat_f : float
        outlet_temp_f : float
        inlet_temp_f : float | None
            Cold-water inlet temperature. Falls back to the performance map's
            design_inlet_temp_f when not provided.

        Returns
        -------
        float
            0.0 when the heater is inactive, has no performance map, or the
            map has no power data.
        """
        if not self._active or self.performance_map is None:
            return 0.0
        kw = self.performance_map.get_power_in_kw(oat_f, outlet_temp_f, inlet_temp_f)
        return kw if kw is not None else 0.0

    def get_output_kbtuh(
        self,
        oat_f: float,
        outlet_temp_f: float,
        inlet_temp_f: float | None = None,
    ) -> float:
        """
        Return actual heating output this timestep: capacity if active, 0 if not.

        Parameters
        ----------
        oat_f : float
        outlet_temp_f : float
        inlet_temp_f : float | None
            Cold-water inlet temperature forwarded to the performance map.

        Returns
        -------
        float
        """
        if not self._active:
            return 0.0
        cap = self.get_capacity_kbtuh(oat_f, outlet_temp_f, inlet_temp_f)
        return cap if cap is not None else 0.0
    
    def get_outlet_temp_f(self, hour_of_day: int) -> float:
        """
        Look up the active Outlet Temperature for Controls for the given hour

        Parameters
        ----------
        hour_of_day : int
            Hour of the day (0-23), used to select the active Controls from
            the control schedule.

        Raises
        ------
        ValueError
            If no Controls are configured for the given hour.
        """
        controls = self.get_controls_for_hour(hour_of_day)
        if controls is None:
            raise ValueError(f"No Controls configured for hour {hour_of_day}.")
        return controls.outlet_temp_f

    def update_state(
        self,
        storage_tank: StorageTank,
        timestep_interval: int,
        interval_min: int = 1,
    ) -> None:
        """
        Look up the active Controls for this timestep's hour, then update
        active/inactive state based on current tank condition.

        On the first interval after a mode change in the control schedule,
        the heater is turned off before the control check.
        If the heater is currently ON, check should_turn_off().
        If the heater is currently OFF, check should_turn_on().

        Parameters
        ----------
        storage_tank : StorageTank
        timestep_interval : int
            Number of elapsed intervals since the start of the simulation.
        interval_min : int
            Length of each interval [minutes]. Default 1.

        Raises
        ------
        ValueError
            If no Controls are configured for this timestep's hour.
        """
        hour_of_day = (timestep_interval * interval_min // 60) % 24
        controls = self.get_controls_for_hour(hour_of_day)
        if controls is None:
            raise ValueError(f"No Controls configured for hour {hour_of_day}.")

        # QPL Alignment block : QPL states Upon change of load shift operation, disable all heaters if “on sensor” is warmer than “on temperature”.
        # To do this in EcosizerEngine, we turn off water heaters on the first interval of a mode change.
        # previous_hour is the hour of the previous timestep, so it differs from hour_of_day
        # only on the first interval of an hour (timestep 0 → hour 23).
        previous_hour = ((timestep_interval - 1) * interval_min // 60) % 24
        if self.control_schedule[hour_of_day] != self.control_schedule[previous_hour]:
            self.turn_off()

        # control logic
        if self._active:
            if controls.should_turn_off(storage_tank):
                self.turn_off()
        else:
            if controls.should_turn_on(storage_tank):
                self.turn_on()
