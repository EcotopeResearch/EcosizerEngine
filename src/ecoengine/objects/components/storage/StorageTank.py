from __future__ import annotations

from abc import ABC, abstractmethod


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class StorageTank(ABC):
    """
    Abstract base class for all storage tank models.

    Defines the interface that WaterHeater, Controls, and DHWSystem rely on.
    Concrete subclasses implement the thermal model (stratified vs. mixed).

    Every subclass must expose ``total_volume_gal`` as a plain attribute and
    implement the five simulation methods listed below.
    """

    total_volume_gal: float

    @abstractmethod
    def initialize(
        self,
        storage_temp_f: float,
        cold_temp_f: float,
        percent_useable: float,
    ) -> None:
        """Set initial tank thermal state before a simulation begins."""

    @abstractmethod
    def get_temperature_at_fraction(self, fract: float) -> float:
        """
        Return water temperature at fractional tank height (0=bottom, 1=top).
        Used by Controls to decide whether to fire the heater.
        """

    @abstractmethod
    def get_usable_volume_supplyT_gal(self, supply_temp_f: float) -> float:
        """Return gallons currently at or above supply temperature."""

    @abstractmethod
    def draw(
        self,
        volume_supplyT_gal: float,
        cold_temp_f: float,
        supply_temp_f: float,
        outlet_temp_f: float,
    ) -> None:
        """Remove DHW demand from the tank and replace with cold make-up water."""

    @abstractmethod
    def heat(
        self,
        kbtuh: float,
        duration_min: float,
        outlet_temp_f: float,
    ) -> None:
        """Apply heat from active water heaters for one timestep."""

    @abstractmethod
    def add_recirc_return(
        self,
        flow_gpm: float,
        return_temp_f: float,
        duration_min: float,
        supply_temp_f: float | None = None,
    ) -> None:
        """
        Apply recirculation loop heat loss to the tank.

        Parameters
        ----------
        flow_gpm : float
            Recirculation loop flow rate [GPM].
        return_temp_f : float
            Temperature of water returning from the recirc loop [°F].
        duration_min : float
            Length of the timestep [minutes].
        supply_temp_f : float | None
            DHW delivery temperature [°F].  This determines how much heat the
            recirc loop actually loses: ``loss = flow × rho_cp × (supply_temp - return_temp)``.
            If ``None``, defaults to ``outlet_temp_f`` (the tank's current hot-end
            temperature), which gives the correct result for TM tanks where the
            supply and storage temperatures are equal.  Pass explicitly for
            primary storage tanks (SPRTP) where ``supply_temp_f < storage_temp_f``.
        """

    @abstractmethod
    def get_average_draw_temp_f(self, draw_gal: float) -> float:
        """
        Return the volume-weighted average temperature of the top ``draw_gal``
        physical gallons.

        Used by SwingSystem to determine the effective feed temperature from the
        primary storage tank when the hot zone may be partially depleted.
        """

    @abstractmethod
    def draw_physical_gal(
        self,
        gal: float,
        inlet_temp_f: float,
        supply_temp_f: float | None = None,
    ) -> None:
        """
        Remove ``gal`` physical gallons from the top of the tank and replace
        with cold make-up water at the bottom.

        Unlike ``draw()``, no supply-temperature conversion is applied — the
        caller provides physical gallons directly. ``supply_temp_f`` is used
        by stratified tanks to floor ``_delta_gal`` at the no-usable-hot-water
        state rather than the absolute fully-cold state.
        """
