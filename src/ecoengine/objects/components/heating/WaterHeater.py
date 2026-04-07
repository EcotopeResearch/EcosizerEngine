from __future__ import annotations

from typing import TYPE_CHECKING

from ecoengine.objects.components.heating.PerformanceMap import NominalPerformanceMap

if TYPE_CHECKING:
    from ecoengine.objects.components.heating.PerformanceMap import PerformanceMap
    from ecoengine.objects.components.heating.Controls import Controls
    from ecoengine.objects.components.storage.StorageTank import StorageTank


class WaterHeater:
    """
    Represents a single heat pump water heater unit. Owns a PerformanceMap
    and a Controls object. Tracks its own active/inactive state.

    Construction
    ------------
    Use one of the factory class methods rather than calling __init__ directly:

    * WaterHeater.from_nominal_capacity(nominal_capacity_kbtuh, controls, ...)
        Creates a NominalPerformanceMap (constant-output placeholder). Use this
        during preliminary sizing before a real equipment model is selected.

    * WaterHeater.from_model_name(model_name, controls)
        Loads a PerformanceMap from the equipment model registry by name. Use
        this when the specific HPWH model is known.
    """

    def __init__(
        self,
        performance_map: PerformanceMap | None,
        controls: Controls | None,
        model_name: str = "",
    ) -> None:
        """
        Parameters
        ----------
        performance_map : PerformanceMap | None
            Performance map for this HPWH model. If None, all capacity/power
            queries return None. Prefer the factory class methods over passing
            a map directly.
        controls : Controls | None
            Control setpoints and logic for this heater.
        model_name : str
            Human-readable model identifier.
        """
        self.performance_map = performance_map
        self.controls        = controls
        self.model_name      = model_name
        self._active         = False

    # ------------------------------------------------------------------
    # Factory constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_nominal_capacity(
        cls,
        nominal_capacity_kbtuh: float,
        controls: Controls | None,
        model_name: str = "",
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
        controls : Controls | None
            Control setpoints and logic for this heater.
        model_name : str
            Optional human-readable identifier.

        Returns
        -------
        WaterHeater
        """
        return cls(
            performance_map=NominalPerformanceMap(nominal_capacity_kbtuh),
            controls=controls,
            model_name=model_name,
        )

    @classmethod
    def from_model_name(
        cls,
        model_name: str,
        controls: Controls | None,
    ) -> WaterHeater:
        """
        Create a WaterHeater by loading its PerformanceMap from the equipment
        model registry using the model name string.

        Parameters
        ----------
        model_name : str
            Equipment model identifier as it appears in the model registry
            (e.g. ``'Rheem_PROPH80_T2_RH380-30'``).
        controls : Controls | None
            Control setpoints and logic for this heater.

        Returns
        -------
        WaterHeater
        """
        pass  # TODO: load PerformanceMap from model registry by model_name

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

    # ------------------------------------------------------------------
    # Performance queries
    # ------------------------------------------------------------------

    def get_capacity_kbtuh(self, oat_f: float, water_temp_f: float) -> float | None:
        """
        Return heating output capacity [kBTU/hr] at current conditions.

        Delegates to performance_map.get_capacity_kbtuh(). Returns None when
        no performance map is assigned.

        Parameters
        ----------
        oat_f : float
            Outdoor air temperature [°F].
        water_temp_f : float
            Entering water temperature [°F].

        Returns
        -------
        float | None
        """
        if self.performance_map is not None:
            return self.performance_map.get_capacity_kbtuh(oat_f, water_temp_f)
        return None

    def get_power_in_kw(self, oat_f: float, water_temp_f: float) -> float | None:
        """
        Return electrical power input [kW] at current conditions.

        Parameters
        ----------
        oat_f : float
        water_temp_f : float

        Returns
        -------
        float | None
        """
        if self.performance_map is not None:
            return self.performance_map.get_power_in_kw(oat_f, water_temp_f)
        return None

    def get_output_kbtuh(self, oat_f: float, water_temp_f: float) -> float | None:
        """
        Return actual heating output this timestep (0 if inactive).

        Parameters
        ----------
        oat_f : float
        water_temp_f : float

        Returns
        -------
        float | None
        """
        pass

    def update_state(self, storage_tank: StorageTank, mode: str = "normal") -> None:
        """
        Check controls and update active/inactive state based on current tank condition.

        Parameters
        ----------
        storage_tank : StorageTank
        mode : str
            One of 'normal', 'load_up', or 'shed'.
        """
        pass
