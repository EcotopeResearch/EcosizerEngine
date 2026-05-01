from __future__ import annotations

from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.storage.SlugOverlayTank import SlugOverlayTank
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

    The resulting tank is a SlugOverlayTank with strat_slope = 0.8.

    Simulation
    ----------
    While not heating the system draws hot water via mixing_valve_behavior and
    removes the physical gallons from the SlugOverlayTank.  When the heater
    turns on, the tank's slug overlay is activated from the sub-supply-temp
    zone of the usable volume.  All demand draws and heater output are
    redirected to the slug until the slug temperature reaches supply_temp_f,
    at which point the heater turns off and the slug's BTUs are merged back
    into the tank.

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
        percent_useable: float = 1.0,
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
            SlugOverlayTank stratification slope [°F / %-height]. Default 0.8.
        percent_useable : float
            Fraction of total tank volume above the cold-water inlet pipe (0–1).
            Control on-sensors must sit above ``(1 - percent_useable)`` height.

        Raises
        ------
        ValueError
            If any on_sensor_fract in control_map falls inside the unusable zone.
        """
        if control_map and percent_useable < 1.0:
            cold_fract = 1.0 - percent_useable
            for key, ctrl in control_map.items():
                if ctrl.on_sensor_fract < cold_fract:
                    raise ValueError(
                        f"Control '{key}': on_sensor_fract={ctrl.on_sensor_fract:.3f} "
                        f"is in the unusable zone (must be >= {cold_fract:.3f} for "
                        f"percent_useable={percent_useable:.3f})."
                    )
                if ctrl.off_sensor_fract < cold_fract:
                    raise ValueError(
                        f"Control '{key}': off_sensor_fract={ctrl.off_sensor_fract:.3f} "
                        f"is in the unusable zone (must be >= {cold_fract:.3f} for "
                        f"percent_useable={percent_useable:.3f})."
                    )

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
        system.storage_tank = SlugOverlayTank(
            total_volume_gal=system._minimum_storage_storageT_gal,
            cold_temp_f=cold_temp_f,
            storage_temp_f=storage_temp_f,
            supply_temp_f=supply_temp_f,
            percent_useable=percent_useable,
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
            self._avg_storage_outlet_temp_f = min([self._calc_avg_hot_temp_at_on_trigger(control.on_sensor_fract, 
                                                                                         control.on_trigger_t_f,
                                                                                         strat_slope) 
                                                   for control in control_map.values()])
            capacity_kbtuh  = self._calc_required_capacity(building)
            running_vol_supplyT_gal = self._calc_running_volume_supplyT_gal(building, capacity_kbtuh)
            design_inlet_temp_f      = self._require_design_inlet_temp(building)
            strat_factor             = self._calc_stratification_factor(control_map, strat_slope, design_inlet_temp_f)
            storage_vol_storageT_gal = self._calc_storage_volume_storageT_gal(
                running_vol_supplyT_gal, strat_factor
            )

            self._minimum_capacity_kbtuh       = capacity_kbtuh
            self._minimum_storage_storageT_gal = storage_vol_storageT_gal
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

            # if demand_supplyT_gal > 0:
            result     = mixing_valve_behavior(
                demand_supplyT_gal,
                flow_per_min_gal,
                cold_temp_f,
                self.supply_temp_f,
                self.return_temp_f,
                self._avg_storage_outlet_temp_f,
            )
            draw_gal   = result["storage_draw_gal"]
            inlet_temp = result["inlet_temp_f"]
            # else:
            #     draw_gal   = 0.0
            #     inlet_temp = cold_temp_f

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
            if slug_vol_gal > 0.0 and slug_temp_f >= self.storage_temp_f: # Heres a place I messed with TODO
                slug_vol_gal = 0.0
                slug_temp_f  = cold_temp_f

            if slug_vol_gal > max_slug_vol_gal:
                max_slug_vol_gal = slug_vol_gal

        return max_slug_vol_gal

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
        Run one simulation timestep for a multi-pass RTP system.

        Order of operations
        -------------------
        1. Query Building for demand, OAT, and inlet water temperature.
        2. Keep the tank's cold-temp baseline current from the building inlet.
        3. Determine on/off heater state:
           - While NOT heating: use standard Controls logic.
           - While HEATING: turn off when slug temperature reaches supply_temp_f.
        4. Handle slug lifecycle transitions (activate on turn-on,
           deactivate on turn-off).
        5. Apply heating and demand via the mixing valve:
           - Heating: redirect draw and heater output to the slug.
           - Not heating: draw physical gallons from the tank via
             mixing_valve_behavior; warm-inlet energy credit is implicit in
             draw_physical_gal.
        6. Return per-step metrics.

        Parameters
        ----------
        building : Building
        timestep_interval : int
        interval_min : int
        mode : str
            Ignored; operating mode is set by the control schedule.

        Returns
        -------
        dict
        """
        tank: SlugOverlayTank = self.storage_tank

        demand_supplyT_gal = building.get_dhw_load_supplyT_gal(
            timestep_interval, interval_min
        )
        oat_f              = building.get_oat_f(timestep_interval, interval_min)
        inlet_water_temp_f = building.get_inlet_water_temp_f(
            timestep_interval, interval_min
        )
        hour_of_day = (timestep_interval * interval_min // 60) % 24
        mode = (
            self.water_heaters[0].control_schedule[hour_of_day]
            if self.water_heaters and self.water_heaters[0].control_schedule
            else "normal"
        )

        # Keep cold baseline current (important for annual simulations where
        # inlet water temperature changes by month).
        tank._cold_temp_f = inlet_water_temp_f

        was_heating = any(wh.is_active() for wh in self.water_heaters)

        # Standard aquastat logic applies: while heating the off-sensor sits inside
        # the fully-mixed slug zone, so get_temperature_at_fraction returns
        # slug_temp_f.  The heater turns off when slug_temp_f >= off_trigger_t_f.
        for wh in self.water_heaters:
            wh.update_state(tank, hour_of_day)

        is_heating = any(wh.is_active() for wh in self.water_heaters)

        # --- Slug lifecycle transitions ---
        # if not was_heating and is_heating:
        if is_heating:
            tank.activate_slug(self.supply_temp_f)
        elif was_heating and not is_heating:
            tank.deactivate_slug()

        # --- Heating capacity ---
        top_temp_f  = tank.get_temperature_at_fraction(1.0)
        total_kbtuh = sum(
            wh.get_output_kbtuh(oat_f, wh.get_outlet_temp_f(hour_of_day)) for wh in self.water_heaters
        )
        active_kws  = [
            wh.get_power_in_kw(oat_f, wh.get_outlet_temp_f(hour_of_day))
            for wh in self.water_heaters
            if wh.is_active()
        ]
        total_kw: float | None = (
            sum(kw or 0.0 for kw in active_kws)
            if any(kw is not None for kw in active_kws)
            else None
        )

        # --- Mixing valve draw ---
        flow_per_min_gal = self.return_flow_gpm * interval_min
        # if demand_supplyT_gal > 0 and top_temp_f > inlet_water_temp_f:
        result = mixing_valve_behavior(
            demand_supplyT_gal,
            flow_per_min_gal,
            inlet_water_temp_f,
            self.supply_temp_f,
            self.return_temp_f,
            top_temp_f,
        )
        draw_gal       = result["storage_draw_gal"]
        mv_inlet_temp_f = result["inlet_temp_f"]
        # else:
        #     draw_gal        = 0.0
        #     mv_inlet_temp_f = inlet_water_temp_f

        # --- Apply to tank ---
        if is_heating:
            # All heat and incoming water go to the slug.
            tank.heat_slug(total_kbtuh, interval_min)
            if tank.slug_temp_f >= self.supply_temp_f:
                tank.deactivate_slug()
        if draw_gal > 0:
            # if timestep_interval > 200 and timestep_interval < 250:
            #     print(f"draw_gal: {demand_supplyT_gal}, {draw_gal}, {mv_inlet_temp_f}")
            tank.draw_physical_gal(
                draw_gal, mv_inlet_temp_f, update_internal_cold_temp=False
            )

        usable_vol_gal = tank.get_usable_volume_supplyT_gal(self.supply_temp_f)
        tank_temps_f   = [
            tank.get_temperature_at_fraction(f)
            for f in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        ]
        # During slug heating top_temp_f may be at cold_temp_f (EnergyTank drained
        # into slug), which would falsely trip the outlet-deficit early-stop.  The
        # system is working normally while the heater is on, so suppress the check.
        delivery_temp_f = self.supply_temp_f if is_heating else top_temp_f

        return {
            "demand_supplyT_gal":        demand_supplyT_gal,
            "usable_volume_supplyT_gal": usable_vol_gal,
            "heater_output_kbtuh":       total_kbtuh,
            "heater_power_in_kw":        total_kw,
            "oat_f":                     oat_f,
            "inlet_water_temp_f":        inlet_water_temp_f,
            "tank_temps_f":              tank_temps_f,
            "mode":                      mode,
            "delivery_temp_f":           delivery_temp_f,
        }
