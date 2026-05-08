from __future__ import annotations

from ecoengine.constants.constants import _RHO_CP, _W_TO_KBTUH
from .DHWSystem import DHWSystem


class InstantWHSystem(DHWSystem):
    """
    Instantaneous (tankless) water heater system.

    No storage tank — the heater meets demand in real time each timestep.
    Sizing sets the minimum capacity needed to serve peak instantaneous demand;
    storage volume is always zero.  Load shifting is not supported because
    there is no tank to pre-charge.
    """

    def __init__(
        self,
        supply_temp_f: float,
        storage_temp_f: float,
        defrost_factor: float = 1.0,
    ):
        super().__init__(
            water_heaters=[],
            storage_tank=None,
            supply_temp_f=supply_temp_f,
            storage_temp_f=storage_temp_f,
            defrost_factor=defrost_factor,
        )

    # ------------------------------------------------------------------
    # Factory constructor
    # ------------------------------------------------------------------

    @classmethod
    def from_size(
        cls,
        building,
        supply_temp_f: float,
        storage_temp_f: float,
        defrost_factor: float = 1.0,
    ) -> InstantWHSystem:
        """
        Size the system for the given building, then return it.

        Parameters
        ----------
        building : Building
        supply_temp_f : float
        storage_temp_f : float
        defrost_factor : float
        """
        system = cls(
            supply_temp_f=supply_temp_f,
            storage_temp_f=storage_temp_f,
            defrost_factor=defrost_factor,
        )
        system.size(building)
        return system

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------

    def size(self, building, **kwargs) -> None:
        """
        Set minimum capacity to serve peak instantaneous demand.

        Capacity is the kBTU/hr required to heat the peak one-minute demand
        volume from design inlet temperature to supply temperature.  Storage
        volume is always zero.

        Parameters
        ----------
        building : Building
            Must have a ClimateZone so that design inlet temperature is available.
        **kwargs
            Accepted but ignored (load-shift params, strat_slope, etc.).
        """
        design_inlet_temp_f = self._require_design_inlet_temp(building)
        delta_t = self.supply_temp_f - design_inlet_temp_f

        # Peak instantaneous generation rate [gal/hr at supply temp]
        peak_gph = building.daily_dhw_use_supplyT_gal * float(max(building.peak_load_shape)) * 60.0

        self._minimum_capacity_kbtuh       = peak_gph * _RHO_CP * delta_t / self.defrost_factor / 1000.0
        self._minimum_storage_storageT_gal = 0.0

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def simulate_step(
        self,
        building,
        timestep_interval: int,
        interval_min: int = 1,
        mode: str = "normal",
    ) -> dict:
        """
        Serve demand instantly each timestep — no tank draw or charge cycle.

        Capacity is computed from this timestep's actual demand and inlet
        temperature, so it tracks demand exactly.  Usable volume is always
        zero (no storage).
        """
        demand_supplyT_gal = building.get_dhw_load_supplyT_gal(timestep_interval, interval_min)
        oat_f              = building.get_oat_f(timestep_interval, interval_min)
        inlet_temp_f       = building.get_inlet_water_temp_f(timestep_interval, interval_min)

        delta_t        = max(self.supply_temp_f - inlet_temp_f, 1.0)
        capacity_kbtuh = (
            demand_supplyT_gal * (60.0 / interval_min)
            * _RHO_CP * delta_t
            / self.defrost_factor / 1000.0
        )

        return {
            "demand_supplyT_gal":        demand_supplyT_gal,
            "usable_volume_supplyT_gal": 0.0,
            "heater_output_kbtuh":       capacity_kbtuh,
            "heater_power_in_kw":        capacity_kbtuh / _W_TO_KBTUH,  # COP of 1.0
            "oat_f":                     oat_f,
            "inlet_water_temp_f":        inlet_temp_f,
            "tank_temps_f":              [self.supply_temp_f] * 6,
            "mode":                      "normal",
        }
