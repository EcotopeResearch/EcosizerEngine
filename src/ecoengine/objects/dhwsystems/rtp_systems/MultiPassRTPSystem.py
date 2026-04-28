from __future__ import annotations

from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.storage.EnergyTank import EnergyTank
from ecoengine.constants.constants import _RHO_CP
from .RTPSystem import RTPSystem
from ..utils import mixing_valve_behavior

_MPRTP_STRAT_SLOPE: float = 0.8
_MPRTP_MAX_DAILY_RUN_HR: float = 14.0


class MultiPassRTPSystem(RTPSystem):
    """
    Multi-pass Return-to-Primary system.

    Heating capacity is sized identically to SinglePassRTPSystem (DHW demand
    plus steady-state recirc loss scaled by the run-time ratio), but the
    default maximum daily run hours is 14 rather than 16.

    Running volume (tank size) is determined by a 2-day, 1-minute-timestep
    simulation called the "growing-slug" method:

    * The heater is assumed to run continuously at the sized capacity.
    * At each minute the mixing valve behavior determines how much water is
      drawn from primary storage and at what inlet temperature.
    * That drawn volume is added to a fully-mixed virtual "slug" representing
      the accumulated cold water that needs to be reheated.
    * The heater heats the slug each minute.
    * When the slug temperature reaches supply_temp_f it is considered "served"
      and the slug volume resets to zero.
    * The peak slug volume across the 2-day simulation is the minimum required
      physical tank volume.

    The resulting tank is an EnergyTank with strat_slope = 0.8.
    Load-shift sizing is not supported.
    """

    # ------------------------------------------------------------------
    # Factory constructor
    # ------------------------------------------------------------------

    @classmethod
    def from_size(
        cls,
        building,
        supply_temp_f: float,
        storage_temp_f: float,
        return_temp_f: float,
        return_flow_gpm: float,
        max_daily_run_hr: float = _MPRTP_MAX_DAILY_RUN_HR,
        defrost_factor: float = 1.0,
        control_schedule: list[str] | None = None,
        control_map: dict[str, Controls] | None = None,
        strat_slope: float = _MPRTP_STRAT_SLOPE,
    ) -> MultiPassRTPSystem:
        """
        Size the system for the given building, then build it.

        Parameters
        ----------
        building : Building
        supply_temp_f : float
        storage_temp_f : float
        return_temp_f : float
        return_flow_gpm : float
        max_daily_run_hr : float
            Maximum hours the heater may run per day. Default 14.
        defrost_factor : float
        control_schedule : list[str] | None
            Passed to WaterHeater; load-shift sizing is not supported and
            will raise if a ``"shed"`` key appears in control_map.
        control_map : dict[str, Controls] | None
        strat_slope : float
            EnergyTank stratification slope [°F / %-height]. Default 0.8.
        """
        system = cls(
            water_heaters=[],
            storage_tank=None,
            supply_temp_f=supply_temp_f,
            storage_temp_f=storage_temp_f,
            return_temp_f=return_temp_f,
            return_flow_gpm=return_flow_gpm,
            max_daily_run_hr=max_daily_run_hr,
            defrost_factor=defrost_factor,
        )
        system.size(building, control_map=control_map, strat_slope=strat_slope)

        cold_temp_f = system._require_design_inlet_temp(building)
        system.storage_tank = EnergyTank(
            total_volume_gal=system._minimum_storage_storageT_gal,
            cold_temp_f=cold_temp_f,
            storage_temp_f=storage_temp_f,
            strat_slope=strat_slope,
        )
        system.water_heaters = [WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=system._minimum_capacity_kbtuh,
            control_schedule=control_schedule,
            control_map=control_map,
        )]
        return system

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------

    def size(
        self,
        building,
        control_schedule: list[str] | None = None,
        control_map: dict[str, Controls] | None = None,
        strat_slope: float = _MPRTP_STRAT_SLOPE,
        load_shift_fract_total_vol: float = 1.0,
    ) -> None:
        """
        Size the multi-pass RTP system.

        Capacity is sized the same way as SinglePassRTPSystem (DHW load plus
        recirc contribution via RTPSystem._calc_required_capacity).  Storage
        volume comes from the growing-slug simulation in
        _calc_running_volume_supplyT_gal, which returns physical gallons
        directly — no stratification-factor conversion is applied.

        Parameters
        ----------
        building : Building
        control_schedule : list[str] | None
            Must not contain a load-shift schedule; raises ValueError if so.
        control_map : dict[str, Controls] | None
        strat_slope : float
        load_shift_fract_total_vol : float
            Unused; retained for interface compatibility.

        Raises
        ------
        ValueError
            If control_map contains a ``"shed"`` key (load-shift not supported).
        """
        if self._is_load_shifting(control_map):
            raise ValueError(
                "MultiPassRTPSystem does not support load-shift sizing. "
                "Remove the 'shed' key from control_map."
            )

        was_annual = building.is_annual_load_shape()
        if was_annual:
            building.set_to_daily_load_shape()

        try:
            capacity_kbtuh  = self._calc_required_capacity(building)
            storage_vol_gal = self._calc_running_volume_supplyT_gal(building, capacity_kbtuh)

            self._minimum_capacity_kbtuh       = capacity_kbtuh
            self._minimum_storage_storageT_gal = storage_vol_gal
            self._sizing_strat_slope           = strat_slope
        finally:
            if was_annual:
                building.set_to_annual_load_shape()

    # ------------------------------------------------------------------
    # Running volume — growing-slug simulation
    # ------------------------------------------------------------------

    def _calc_running_volume_supplyT_gal(
        self,
        building,
        capacity_kbtuh: float,
    ) -> float:
        """
        Determine the minimum physical tank volume [gallons] via the
        growing-slug method.

        Runs a 2-day, 1-minute-timestep simulation with the heater always on.
        The "slug" is a fully-mixed virtual tank representing water accumulated
        at the bottom of the primary storage that needs to be reheated.

        At each minute:
        1. mixing_valve_behavior() determines how much cold/warm water enters
           primary storage (storage_draw_gal at inlet_temp_f).
        2. That volume mixes into the slug via a weighted-average energy balance.
        3. The heater adds heat_kbtu_per_min to the slug.
        4. If the slug temperature reaches supply_temp_f it resets to zero
           (the water is now hot enough to serve demand).
        5. The maximum slug volume observed is the minimum required tank size.

        When demand is zero the slug is not grown (the recirc loss is already
        captured in capacity via _calc_required_capacity).

        Parameters
        ----------
        building : Building
        capacity_kbtuh : float
            Total heating capacity [kBTU/hr] from _calc_required_capacity.

        Returns
        -------
        float
            Minimum required physical tank volume [gallons].
        """
        cold_temp_f        = self._require_design_inlet_temp(building)
        interval_min       = 1
        n_timesteps        = 2 * 24 * 60          # 2-day simulation
        flow_per_min_gal   = self.return_flow_gpm * interval_min
        heat_kbtu_per_min  = capacity_kbtuh * interval_min / 60.0

        slug_vol_gal     = 0.0
        slug_temp_f      = cold_temp_f
        max_slug_vol_gal = 0.0

        for t in range(n_timesteps):
            demand_supplyT_gal = building.get_dhw_load_supplyT_gal(t, interval_min)

            if demand_supplyT_gal > 0:
                result     = mixing_valve_behavior(
                    demand_supplyT_gal,
                    flow_per_min_gal,
                    cold_temp_f,
                    self.supply_temp_f,
                    self.return_temp_f,
                    self.storage_temp_f,
                )
                draw_gal   = result["storage_draw_gal"]
                inlet_temp = result["inlet_temp_f"]
            else:
                draw_gal   = 0.0
                inlet_temp = cold_temp_f

            # Mix drawn volume into slug (weighted-average energy balance)
            if draw_gal > 0:
                if slug_vol_gal <= 0.0:
                    slug_vol_gal = draw_gal
                    slug_temp_f  = inlet_temp
                else:
                    slug_temp_f = (
                        (slug_vol_gal * slug_temp_f + draw_gal * inlet_temp)
                        / (slug_vol_gal + draw_gal)
                    )
                    slug_vol_gal += draw_gal

            # Heat slug (heater always on during sizing simulation)
            if slug_vol_gal > 0.0:
                slug_temp_f += heat_kbtu_per_min * 1000.0 / (slug_vol_gal * _RHO_CP)

            # Reset slug when it reaches supply temperature
            if slug_vol_gal > 0.0 and slug_temp_f >= self.supply_temp_f:
                slug_vol_gal = 0.0
                slug_temp_f  = cold_temp_f

            if slug_vol_gal > max_slug_vol_gal:
                max_slug_vol_gal = slug_vol_gal

        return max_slug_vol_gal

    # ------------------------------------------------------------------
    # Simulation (not yet implemented)
    # ------------------------------------------------------------------

    def simulate_step(
        self,
        building,
        timestep_interval: int,
        interval_min: int = 1,
        mode: str = "normal",
    ) -> dict:
        """Run one timestep for a multi-pass RTP system."""
        raise NotImplementedError("MultiPassRTPSystem simulation is not yet implemented.")
