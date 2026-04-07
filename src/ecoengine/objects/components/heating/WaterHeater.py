from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecoengine.objects.components.heating.PerformanceMap import PerformanceMap
    from ecoengine.objects.components.heating.Controls import Controls
    from ecoengine.objects.components.storage.StorageTank import StorageTank


class WaterHeater:
    """
    Represents a single heat pump water heater unit. Owns a PerformanceMap
    and a Controls object. Tracks its own active/inactive state.
    """

    def __init__(
        self,
        performance_map: PerformanceMap | None,
        controls: Controls | None,
        model_name: str = "",
        nominal_capacity_kbtuh: float | None = None,
    ) -> None:
        """
        Parameters
        ----------
        performance_map : PerformanceMap | None
            Performance map for this specific HPWH model. If None, capacity
            queries fall back to nominal_capacity_kbtuh.
        controls : Controls | None
            Control setpoints and logic for this heater.
        model_name : str
            Human-readable model identifier.
        nominal_capacity_kbtuh : float | None
            Rated heating output capacity [kBTU/hr]. Used as a fallback when
            no performance_map is provided (e.g. during preliminary sizing).
        """
        self.performance_map = performance_map
        self.controls = controls
        self.model_name = model_name
        self.nominal_capacity_kbtuh = nominal_capacity_kbtuh
        self._active = False

    def is_active(self) -> bool:
        """Return True if this heater is currently running."""
        return self._active

    def turn_on(self) -> None:
        """Activate this heater."""
        self._active = True

    def turn_off(self) -> None:
        """Deactivate this heater."""
        self._active = False

    def get_capacity_kbtuh(self, oat_f: float, water_temp_f: float) -> float | None:
        """
        Return heating output capacity [kBTU/hr] at current conditions.

        If a performance_map is available it is used; otherwise falls back to
        nominal_capacity_kbtuh (set at construction during sizing). Returns
        None when neither is available.

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
            pass  # TODO: return self.performance_map.get_capacity_kbtuh(oat_f, water_temp_f)
        return self.nominal_capacity_kbtuh

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
        pass

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
