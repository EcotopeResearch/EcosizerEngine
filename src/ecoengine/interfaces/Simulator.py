from ecoengine.objects.simulation.SimulationRun import SimulationRun

THREE_DAY_DURATION_MIN = 3 * 24 * 60    # 4320 minutes
ANNUAL_DURATION_MIN    = 365 * 24 * 60  # 525600 minutes
THREE_DAY_TIMESTEP_MIN = 1
ANNUAL_TIMESTEP_MIN    = 10


def simulate(dhw_system, building, duration="3day", **sim_run_kwargs) -> SimulationRun:
    """
    Run a time-step simulation of a sized DHWSystem in a Building.

    At every timestep the simulator:
      1. Delegates to DHWSystem.simulate_step() which queries the Building,
         updates heater states, applies heating, and draws from the tank.
      2. Records the returned per-step metrics into the SimulationRun.
      3. Checks for a DHW outage (usable tank volume <= 0).

    The storage tank is initialized before the loop at a charge level
    corresponding to the normal Controls on-aquastat fraction. If no Controls
    are present, the tank starts fully charged.

    Parameters
    ----------
    dhw_system : DHWSystem
        A sized DHWSystem instance (size() must have been called and the
        storage_tank must not be None).
    building : Building
        The building to simulate the system in.
    duration : str
        '3day' for a 3-day design-day simulation (1-minute steps) or
        'annual' for a full-year simulation (10-minute steps).

    Returns
    -------
    SimulationRun
        Object containing per-timestep outputs and summary metrics.

    Raises
    ------
    ValueError
        If duration is not '3day' or 'annual'.
    """
    if duration == "3day":
        duration_min  = THREE_DAY_DURATION_MIN
        timestep_min  = THREE_DAY_TIMESTEP_MIN
    elif duration == "annual":
        duration_min  = ANNUAL_DURATION_MIN
        timestep_min  = ANNUAL_TIMESTEP_MIN
    else:
        raise ValueError(f"duration must be '3day' or 'annual', got {duration!r}")

    sim_run = SimulationRun(duration_min, timestep_min, **sim_run_kwargs)

    # Initialize storage tanks
    inlet_temp_f    = building.get_design_inlet_water_temp_f() or 50.0
    percent_useable = _initial_percent_useable(dhw_system)
    if dhw_system.storage_tank is not None:
        dhw_system.storage_tank.initialize(
            storage_temp_f  = dhw_system.storage_temp_f,
            cold_temp_f     = inlet_temp_f,
            percent_useable = percent_useable,
        )
    # Initialize TM tank if present (ParallelLoopSystem, SwingSystem)
    tm_tank = getattr(dhw_system, "tm_storage_tank", None)
    if tm_tank is not None:
        tm_off_temp_f = getattr(dhw_system, "tm_off_temp_f", dhw_system.storage_temp_f)
        tm_tank.initialize(
            storage_temp_f  = tm_off_temp_f,
            cold_temp_f     = inlet_temp_f,
            percent_useable = 1.0,
        )

    sim_run.storage_temp_f = dhw_system.storage_temp_f

    num_steps = duration_min // timestep_min
    for i in range(num_steps):
        step = dhw_system.simulate_step(
            building          = building,
            timestep_interval = i,
            interval_min      = timestep_min,
        )

        sim_run.record_timestep(
            dhw_demand_supplyT_gal    = step["demand_supplyT_gal"],
            usable_volume_supplyT_gal = step["usable_volume_supplyT_gal"],
            heater_output_kbtuh       = step["heater_output_kbtuh"],
            heater_power_in_kw        = step["heater_power_in_kw"],
            oat_f                     = step["oat_f"],
            inlet_water_temp_f        = step["inlet_water_temp_f"],
            tank_temps_f              = step["tank_temps_f"],
            mode                      = step.get("mode", "normal"),
            tm_tank_temp_f            = step.get("tm_tank_temp_f"),
            tm_heater_output_kbtuh    = step.get("tm_heater_output_kbtuh"),
        )

        if step["usable_volume_supplyT_gal"] <= 0.0:
            sim_run.record_outage(timestep_min)

        # Check outlet-deficit stop condition (top-of-tank temp too far below supply)
        top_tank_temp_f = step["tank_temps_f"][-1]
        if sim_run.check_outlet_deficit(top_tank_temp_f, dhw_system.supply_temp_f):
            break

    return sim_run


def simulate_3day(dhw_system, building, **sim_run_kwargs) -> SimulationRun:
    """
    Convenience wrapper: run a 3-day simulation at 1-minute timesteps.

    Parameters
    ----------
    dhw_system : DHWSystem
    building : Building
    **sim_run_kwargs
        Forwarded to SimulationRun.__init__() (e.g. outlet_deficit_threshold_f).

    Returns
    -------
    SimulationRun
    """
    return simulate(dhw_system, building, duration="3day", **sim_run_kwargs)


def simulate_annual(dhw_system, building, **sim_run_kwargs) -> SimulationRun:
    """
    Convenience wrapper: run a full annual simulation at 10-minute timesteps.

    Parameters
    ----------
    dhw_system : DHWSystem
    building : Building
    **sim_run_kwargs
        Forwarded to SimulationRun.__init__().

    Returns
    -------
    SimulationRun
    """
    return simulate(dhw_system, building, duration="annual", **sim_run_kwargs)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _initial_percent_useable(dhw_system) -> float:
    """
    Determine the initial tank charge level (fraction hot) from the system's
    "normal" Controls on-aquastat fraction.

    Starting the tank at ``1 - on_sensor_fract`` matches the original
    engine's initialisation: the tank begins at the on-trigger level so the
    heater fires immediately on the first cold hour and the simulation
    reaches steady state quickly.

    Falls back to 1.0 (fully charged) when no Controls are configured.
    """
    for wh in dhw_system.water_heaters:
        if wh.control_map is None:
            continue
        # Prefer "normal" key; otherwise take the first available Controls.
        ctrl = wh.control_map.get("normal") or next(iter(wh.control_map.values()), None)
        if ctrl is not None:
            return max(0.0, min(1.0, 1.0 - ctrl.on_sensor_fract))
    return 1.0
