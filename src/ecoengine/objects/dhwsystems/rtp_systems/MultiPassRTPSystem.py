from __future__ import annotations

import numpy as np

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
        # Capacity Boost
        inlet_temp_f    = building.get_design_inlet_water_temp_f() or 50.0
        ctrl = control_map.get("normal") or next(iter(control_map.values()), None)
        starting_percent_usable = max(0.0, min(1.0, 1.0 - ctrl.on_sensor_fract))
        for _ in range(3):
            system.storage_tank.initialize(
                storage_temp_f  = system.storage_temp_f,
                cold_temp_f     = inlet_temp_f,
                percent_useable = starting_percent_usable
            )
            minutes = 24 * 60 * 3
            deficit_minutes = 0
            min_tank_outlet_f = supply_temp_f
            heater_on = False
            start_heat_min = 0
            for i in range(minutes):
                step = system.simulate_step(
                    building          = building,
                    timestep_interval = i,
                    interval_min      = 1,
                )
                if step["heater_output_kbtuh"] > 0 and not heater_on:
                    heater_on = True
                    start_heat_min = i
                elif step["heater_output_kbtuh"] <= 0 and heater_on:
                    heater_on = False

                if step["usable_volume_supplyT_gal"] <= 0.0:
                    # Outage
                    tank_outlet_f = step["tank_temps_f"][-1]
                    if tank_outlet_f < min_tank_outlet_f:
                        deficit_minutes = i - start_heat_min
                        min_tank_outlet_f = tank_outlet_f
            
            if deficit_minutes > 0:
                capacity_increase_kbtu = ((system.storage_tank.total_volume_gal * percent_useable) * _RHO_CP * (supply_temp_f - min_tank_outlet_f))/1000
                print(f"capacity increase of {capacity_increase_kbtu / (deficit_minutes/60)}")
                if capacity_increase_kbtu > 0:
                    system._minimum_capacity_kbtuh = system._minimum_capacity_kbtuh + (capacity_increase_kbtu / (deficit_minutes/60))
                    system.water_heaters = [WaterHeater.from_nominal_capacity(
                        nominal_capacity_kbtuh=system._minimum_capacity_kbtuh,
                        control_schedule=control_schedule,
                        control_map=control_map,
                    )]
            else:
                break
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
    # Sizing curve
    # ------------------------------------------------------------------

    def get_sizing_curve(
        self,
        building,
        strat_slope: float = _MPRTP_STRAT_SLOPE,
        step: float = 0.5,
    ) -> dict:
        """
        Compute the MPRTP sizing curve — capacity vs. storage for decreasing
        run hours.

        Unlike other DHW systems, MPRTP does not model an "over-designed" region
        above the default ``max_daily_run_hr``.  The curve only sweeps downward
        from the system's ``max_daily_run_hr`` to the physical minimum.

        Each point is produced by a full ``from_size()`` call so that the
        capacity-boost simulation loop (which may increase capacity beyond the
        analytic estimate) is applied at every run-hour value, not just the
        recommended point.

        ``recommended_index`` is always 0 — the first point corresponds to the
        configured ``max_daily_run_hr`` and is the recommended design.

        Parameters
        ----------
        building : Building
        strat_slope : float
            Stratification slope [°F per %-height].  Defaults to 0.8.
        step : float
            Run-hour step size for the sweep.  Default 0.5 hr.

        Returns
        -------
        dict
            ``"heat_hours"``           : list[float] — run hrs at each point
            ``"capacity_kbtuh"``       : list[float] — capacity [kBTU/hr]
            ``"storage_storageT_gal"`` : list[float] — storage [gal at storageT]
            ``"recommended_index"``    : int — always 0 for MPRTP
        """
        was_annual = building.is_annual_load_shape()
        if was_annual:
            building.set_to_daily_load_shape()

        _strat_slope = getattr(self, "_sizing_strat_slope", strat_slope)

        # Pull parameters from the already-sized system so every curve point
        # uses identical inputs to the recommended design.
        _cmap    = self.water_heaters[0].control_map     if self.water_heaters else None
        _sched   = self.water_heaters[0].control_schedule if self.water_heaters else None
        _pct_use = (
            self.storage_tank.percent_useable
            if self.storage_tank and hasattr(self.storage_tank, "percent_useable")
            else 1.0
        )

        try:
            # Physical minimum: one hour of generation equals the peak demand hour.
            min_run_hr = 1.0 / float(np.max(building.peak_load_shape)) * 1.001

            # Sweep only downward from the recommended max_daily_run_hr.
            heat_hours = np.arange(self.max_daily_run_hr, min_run_hr, -step)

            heat_hours_out: list[float] = []
            capacity_out:   list[float] = []
            storage_out:    list[float] = []

            for h in heat_hours:
                try:
                    pt = MultiPassRTPSystem.from_size(
                        building         = building,
                        supply_temp_f    = self.supply_temp_f,
                        storage_temp_f   = self.storage_temp_f,
                        return_temp_f    = self.return_temp_f,
                        return_flow_gpm  = self.return_flow_gpm,
                        max_daily_run_hr = float(h),
                        defrost_factor   = self.defrost_factor,
                        control_schedule = _sched,
                        control_map      = _cmap,
                        strat_slope      = _strat_slope,
                        percent_useable  = _pct_use,
                    )
                except (ValueError, RuntimeError, ZeroDivisionError):
                    break
                vol = pt._minimum_storage_storageT_gal
                if vol == 0.0:
                    break
                heat_hours_out.append(float(h))
                capacity_out.append(pt._minimum_capacity_kbtuh)
                storage_out.append(vol)

            return {
                "heat_hours":           heat_hours_out,
                "capacity_kbtuh":       capacity_out,
                "storage_storageT_gal": storage_out,
                "recommended_index":    0,
            }
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
        # if tank._slug_top_pct >= 99 and top_temp_f != tank.slug_temp_f:
        #     print(f"what gives? {tank._slug_top_pct}, {top_temp_f}, {tank.slug_temp_f}")
        #     tank.get_temperature_at_fraction(1.0, verbose = True)
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

        # --- Apply to tank ---
        if is_heating:
            if tank.is_slug_active() and tank._slug_vol_gal > 0:
                # Sub-supply water exists: heat it via the slug.
                tank.heat_slug(total_kbtuh, interval_min)
        if draw_gal > 0:
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
            "oat_f":                     top_temp_f,
            "inlet_water_temp_f":        inlet_water_temp_f,
            "tank_temps_f":              tank_temps_f,
            "mode":                      mode,
            "delivery_temp_f":           delivery_temp_f,
        }
