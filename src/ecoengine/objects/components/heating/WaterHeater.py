from __future__ import annotations

from typing import TYPE_CHECKING

from ecoengine.objects.components.heating.PerformanceMap import NominalPerformanceMap, PerformanceMap

if TYPE_CHECKING:
    from ecoengine.objects.components.heating.Controls import Controls
    from ecoengine.objects.components.storage.StorageTank import StorageTank


class WaterHeater:
    """
    Represents a single heat pump water heater unit. Owns a PerformanceMap,
    a control schedule, and a control map. Tracks its own active/inactive state.

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
        """
        self.performance_map  = performance_map
        self.control_schedule = control_schedule
        self.control_map      = control_map
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

        Returns
        -------
        WaterHeater
        """
        return cls(
            performance_map=NominalPerformanceMap(nominal_capacity_kbtuh),
            control_schedule=control_schedule,
            control_map=control_map,
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
            ),
            control_schedule=control_schedule,
            control_map=control_map,
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
    ) -> float | None:
        """
        Return electrical power input [kW] at current conditions.

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
            return self.performance_map.get_power_in_kw(oat_f, outlet_temp_f, inlet_temp_f)
        return None

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

    def update_state(self, storage_tank: StorageTank, hour_of_day: int) -> None:
        """
        Look up the active Controls for the given hour, then update
        active/inactive state based on current tank condition.

        If the heater is currently ON, check should_turn_off().
        If the heater is currently OFF, check should_turn_on().
        If no Controls are configured for this hour, state is unchanged.

        Parameters
        ----------
        storage_tank : StorageTank
        hour_of_day : int
            Hour of the day (0-23), used to select the active Controls from
            the control schedule.
        """
        controls = self.get_controls_for_hour(hour_of_day)
        if controls is None:
            return
        if self._active:
            if controls.should_turn_off(storage_tank):
                self.turn_off()
        else:
            if controls.should_turn_on(storage_tank):
                self.turn_on()
