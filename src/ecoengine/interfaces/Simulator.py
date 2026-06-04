from ecoengine.objects.simulation.SimulationRun import SimulationRun
from ecoengine.objects.building.Building import Building
from ecoengine.objects.dhwsystems.DHWSystem import DHWSystem

THREE_DAY_DURATION_MIN = 3 * 24 * 60    # 4320 minutes
ANNUAL_DURATION_MIN    = 365 * 24 * 60  # 525600 minutes
THREE_DAY_TIMESTEP_MIN = 1
ANNUAL_TIMESTEP_MIN    = 10


def simulate(dhw_system: DHWSystem, building: Building, duration: str = "3day", **sim_run_kwargs) -> SimulationRun:
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

    from ecoengine.objects.dhwsystems.recirc_systems.SwingSystem import SwingSystem
    from ecoengine.objects.dhwsystems.recirc_systems.SwingERTrdOffSystem import SwingERTrdOffSystem
    from ecoengine.objects.dhwsystems.rtp_systems.SP_RTPInSeriesSystem import SP_RTPInSeriesSystem, _GAS_DEADBAND_F
    from ecoengine.objects.dhwsystems.rtp_systems.MP_RTPInSeriesSystem import MP_RTPInSeriesSystem
    _is_in_series = isinstance(dhw_system, (SP_RTPInSeriesSystem, MP_RTPInSeriesSystem))
    sim_run.show_tm_panel = (
        isinstance(dhw_system, SwingSystem)
        or isinstance(dhw_system, SwingERTrdOffSystem)
        or _is_in_series
    )
    if _is_in_series:
        sim_run.tm_panel_label = "In Series Heating"

    # Initialize storage tanks
    inlet_temp_f    = building.get_design_inlet_water_temp_f() or 50.0
    percent_useable = dhw_system.get_initial_percent_useable()
    if dhw_system.storage_tank is not None:
        dhw_system.storage_tank.initialize(
            storage_temp_f  = dhw_system.storage_temp_f,
            cold_temp_f     = inlet_temp_f,
            percent_useable = percent_useable, # TODO I don't think this is right
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
    # Initialize gas backup tank if present (SP_RTPInSeriesSystem)
    gas_tank = getattr(dhw_system, "gas_storage_tank", None)
    if gas_tank is not None:
        gas_tank.initialize(
            storage_temp_f  = dhw_system.supply_temp_f + _GAS_DEADBAND_F,
            cold_temp_f     = inlet_temp_f,
            percent_useable = 1.0,
        )

    sim_run.supply_temp_f = dhw_system.supply_temp_f
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
            tm_heater_input_kw    = step.get("tm_heater_input_kw"),
        )

        if step["usable_volume_supplyT_gal"] <= 0.0:
            if not sim_run.show_tm_panel or step.get("tm_tank_temp_f") < dhw_system.supply_temp_f:
                sim_run.record_outage(timestep_min)

        # Check outlet-deficit stop condition. For systems where the TM/swing
        # tank is the actual delivery point (e.g. SwingSystem), use its
        # temperature; for all others fall back to the primary tank top.
        delivery_temp_f = step.get("delivery_temp_f", step["tank_temps_f"][-1])
        if sim_run.check_outlet_deficit(delivery_temp_f, dhw_system.supply_temp_f):
            break
    return sim_run


def simulate_3day(dhw_system: DHWSystem, building: Building, **sim_run_kwargs) -> SimulationRun:
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


def simulate_annual(dhw_system: DHWSystem, building: Building, **sim_run_kwargs) -> SimulationRun:
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
