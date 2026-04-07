from ecoengine.objects.simulation.SimulationRun import SimulationRun

THREE_DAY_DURATION_MIN = 3 * 24 * 60   # 4320 minutes
ANNUAL_DURATION_MIN    = 365 * 24 * 60  # 525600 minutes
THREE_DAY_TIMESTEP_MIN = 1
ANNUAL_TIMESTEP_MIN    = 10


def simulate(dhw_system, building, duration="3day"):
    """
    Run a time-step simulation of a sized DHWSystem in a Building.

    At every timestep the simulator:
      1. Queries the Building for DHW load, OAT, and cold water temperature.
      2. Queries each WaterHeater's Controls and the StorageTank state to
         determine whether to turn heaters on or off.
      3. Applies heating from active heaters to the storage tank.
      4. Draws water from the tank to meet DHW demand.
      5. Checks for a DHW outage; if cumulative outage exceeds the threshold
         the run is marked failed.

    Parameters
    ----------
    dhw_system : DHWSystem
        A sized DHWSystem instance (size() must have been called).
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
    pass


def simulate_3day(dhw_system, building):
    """
    Convenience wrapper: run a 3-day simulation at 1-minute timesteps.

    Parameters
    ----------
    dhw_system : DHWSystem
    building : Building

    Returns
    -------
    SimulationRun
    """
    pass


def simulate_annual(dhw_system, building):
    """
    Convenience wrapper: run a full annual simulation at 10-minute timesteps.

    Parameters
    ----------
    dhw_system : DHWSystem
    building : Building

    Returns
    -------
    SimulationRun
    """
    pass
