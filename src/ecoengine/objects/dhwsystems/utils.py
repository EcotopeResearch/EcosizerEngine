from ecoengine.constants.constants import _RHO_CP
from ecoengine.objects.dhwsystems.DHWSystem import _get_peak_indices

def mixing_valve_behavior(load_supplyT_gal : float, flow_returnT_gal : float, cold_temp_f : float, supply_temp_f : float, return_temp_f : float, storage_temp_f : float) -> dict:
    """
    Calculate the storage draw volume and tank inlet temperature for one timestep
    given a thermostatic mixing valve serving both a DHW load and a recirculation loop.

    The mixing valve blends hot storage water with cold (or warm return) water to
    deliver exactly ``supply_temp_f`` to the building.  Three regimes exist:

    1. **Storage too cool** (``storage_temp_f <= supply_temp_f``): The valve cannot
       reach supply temp, so all demand and recirc flow comes from storage.  The
       inlet temperature is a blend of cold makeup and a derated recirc return.
    2. **High load** (``load_supplyT_gal > critical_flow_gal``): Demand is large
       enough that the mixing valve draws cold makeup water; the full recirc return
       is blended back to the building and nothing returns to the tank.
    3. **Low load** (``load_supplyT_gal <= critical_flow_gal``): Demand is small
       relative to recirc loss, so part of the recirc return is routed back into
       the tank.  The inlet is a blend of cold makeup and that returned recirc flow.

    Parameters
    ----------
    load_supplyT_gal : float
        DHW demand this timestep [gal at supply temperature].
    flow_returnT_gal : float
        Volume of recirculation return flow this timestep [gal at return temperature].
    cold_temp_f : float
        Cold inlet water temperature [°F].
    supply_temp_f : float
        Target mixed delivery temperature [°F].
    return_temp_f : float
        Recirculation loop return temperature [°F].
    storage_temp_f : float
        Current temperature at the top of the storage (or swing) tank [°F].

    Returns
    -------
    dict
        ``storage_draw_gal``          — volume drawn from the tank this timestep [gal].
        ``inlet_temp_f``              — blended temperature of water entering the tank [°F].
        ``cold_load_to_storage_gal``  — cold-side draw volume sent to the storage tank [gal].
    """
    # where there is no flow through the cold side of the mixing valve, when storage or swing is too cool
    # in swing tanks, cold inlet comes from the primary storage, is hot, and adds heat to swing tank (unless primary storage is out of hot water)
    if storage_temp_f <= supply_temp_f:
        storage_draw_gal = load_supplyT_gal + flow_returnT_gal
        recirc_loop_delta_f = supply_temp_f - return_temp_f
        derated_recirc_temp_f = max(storage_temp_f - recirc_loop_delta_f, cold_temp_f)
        inlet_temp_f = ((load_supplyT_gal * cold_temp_f) + (flow_returnT_gal * derated_recirc_temp_f)) / storage_draw_gal
        cold_load_to_storage_gal = load_supplyT_gal
    else:
    # For minute intervals, storage_temp_f is whatever temperature is at the top of the storage tank, set point storage temperature or not
        recirc_loss_btu = flow_returnT_gal * _RHO_CP * (supply_temp_f - return_temp_f)
        critical_flow_gal = recirc_loss_btu / (_RHO_CP * (storage_temp_f - supply_temp_f))
        # where all recirculation flows through the mixing valve back to the building, when flow is high 
        if load_supplyT_gal > critical_flow_gal:
            storage_draw_gal = (load_supplyT_gal * ((supply_temp_f - cold_temp_f) / (storage_temp_f - cold_temp_f))) + \
                (flow_returnT_gal * ((supply_temp_f - return_temp_f) / (storage_temp_f - cold_temp_f)))
            inlet_temp_f = cold_temp_f
            cold_load_to_storage_gal = load_supplyT_gal * ((supply_temp_f - cold_temp_f) / (storage_temp_f - cold_temp_f)) # TODO check w evan
        # where some of the recirculation return goes back to the storage or swing tank, lower flows
        else:
            storage_draw_gal = (load_supplyT_gal + flow_returnT_gal) * ((supply_temp_f - return_temp_f) / (storage_temp_f - return_temp_f))
            recirc_to_tank_gal = storage_draw_gal - load_supplyT_gal
            inlet_temp_f = ((load_supplyT_gal * cold_temp_f) + (recirc_to_tank_gal * return_temp_f)) / storage_draw_gal
            cold_load_to_storage_gal = load_supplyT_gal
    return {
        "storage_draw_gal" : storage_draw_gal,
        "inlet_temp_f" : inlet_temp_f,
        "cold_load_to_storage_gal" : cold_load_to_storage_gal,
    }

def mixing_valve_behavior_swing(load_supplyT_gal : float, flow_returnT_gal : float, cold_temp_f : float, supply_temp_f : float, return_temp_f : float, swing_storage_temp_f : float,
                                swing_inlet_temp : float) -> dict:
    """
    Variant of ``mixing_valve_behavior`` for swing tank systems where the cold
    side of the mixing valve is fed from primary storage (not city water).

    Identical regime logic to ``mixing_valve_behavior``, but ``cold_temp_f``
    represents the average temperature of the primary storage draw rather than
    city cold water, and ``swing_inlet_temp`` is used as the blending temperature
    for the storage-draw inlet in the low-load and under-temp regimes.

    Parameters
    ----------
    load_supplyT_gal : float
        DHW demand this timestep [gal at supply temperature].
    flow_returnT_gal : float
        Volume of recirculation return flow this timestep [gal at return temperature].
    cold_temp_f : float
        Cold inlet water temperature [°F].
    supply_temp_f : float
        Target mixed delivery temperature [°F].
    return_temp_f : float
        Recirculation loop return temperature [°F].
    swing_storage_temp_f : float
        Current temperature at the mid-point of the swing tank [°F].
    swing_inlet_temp : float
        Temperature of water entering the swing tank from the primary storage [°F].

    Returns
    -------
    dict
        ``storage_draw_gal``         — volume drawn from the swing tank [gal].
        ``inlet_temp_f``             — blended temperature entering the swing tank [°F].
        ``cold_load_to_storage_gal`` — cold-side draw volume pulled from primary storage [gal].
    """
    # where there is no flow through the cold side of the mixing valve, when storage or swing is too cool
    # in swing tanks, cold inlet comes from the primary storage, is hot, and adds heat to swing tank (unless primary storage is out of hot water)
    if swing_storage_temp_f <= supply_temp_f:
        storage_draw_gal = load_supplyT_gal + flow_returnT_gal
        recirc_loop_delta_f = supply_temp_f - return_temp_f
        derated_recirc_temp_f = max(swing_storage_temp_f - recirc_loop_delta_f, cold_temp_f)
        inlet_temp_f = ((load_supplyT_gal * swing_inlet_temp) + (flow_returnT_gal * derated_recirc_temp_f)) / storage_draw_gal
        cold_load_to_storage_gal = load_supplyT_gal
    else:
        # For minute intervals, storage_temp_f is whatever temperature is at the top of the storage tank, set point storage temperature or not
        recirc_loss_btu = flow_returnT_gal * _RHO_CP * (supply_temp_f - return_temp_f)
        critical_flow_gal = recirc_loss_btu / (_RHO_CP * (swing_storage_temp_f - supply_temp_f))
        # where all recirculation flows through the mixing valve back to the building, when flow is high 
        if load_supplyT_gal > critical_flow_gal:
            storage_draw_gal = (load_supplyT_gal * ((supply_temp_f - cold_temp_f) / (swing_storage_temp_f - cold_temp_f))) + \
                (flow_returnT_gal * ((supply_temp_f - return_temp_f) / (swing_storage_temp_f - cold_temp_f)))
            inlet_temp_f = swing_inlet_temp
            cold_load_to_storage_gal = load_supplyT_gal * ((supply_temp_f - cold_temp_f) / (swing_storage_temp_f - cold_temp_f)) # TODO check w evan
        # where some of the recirculation return goes back to the storage or swing tank, lower flows
        else:
            storage_draw_gal = (load_supplyT_gal + flow_returnT_gal) * ((supply_temp_f - return_temp_f) / (swing_storage_temp_f - return_temp_f))
            recirc_to_tank_gal = storage_draw_gal - load_supplyT_gal
            inlet_temp_f = ((load_supplyT_gal * swing_inlet_temp) + (recirc_to_tank_gal * return_temp_f)) / storage_draw_gal
            cold_load_to_storage_gal = load_supplyT_gal
    return {
        "storage_draw_gal" : storage_draw_gal,
        "inlet_temp_f" : inlet_temp_f,
        "cold_load_to_storage_gal" : cold_load_to_storage_gal,
    }

def ashrae_method_water_use_ratio(peak_min : int, total_gal : float) -> float:
    """
    Convert a measured peak-period consumption to an equivalent hourly rate
    using the ASHRAE diversity ratios from 2015 ASHRAE Handbook Table 50.15-7.

    A short burst of hot-water demand (e.g. 5 minutes of heavy use) is not
    representative of a sustained hourly load — the ASHRAE table captures how
    much of a peak burst is actually maintainable over a full hour.  Multiplying
    the naive extrapolated rate (total_gal × 60 / peak_min) by the ratio
    ``table_value / 4.8`` scales it down to that realistic hourly equivalent.

    Parameters
    ----------
    peak_min : int
        Duration of the measured peak period in minutes. Must be one of
        [5, 15, 30, 60].
    total_gal : float
        Total gallons consumed during the peak period.

    Returns
    -------
    float
        Equivalent hourly consumption rate [gal/hr] adjusted for ASHRAE
        diversity. At 60 minutes the input is returned unchanged (ratio = 1).

    Raises
    ------
    Exception
        If ``peak_min`` is not one of the four supported durations.
    """
    if peak_min not in [5, 15, 30, 60]:
        raise Exception(f"peak_min must be one of [5, 15, 30, 60]. Recieved {peak_min}")
    extrapolated_hourly_gal = total_gal * (60.0/(peak_min + 0.0))
    if peak_min == 5: return extrapolated_hourly_gal * (0.7/4.8)
    if peak_min == 15: return extrapolated_hourly_gal * (1.7/4.8)
    if peak_min == 30: return extrapolated_hourly_gal * (2.9/4.8)
    if peak_min == 60: return extrapolated_hourly_gal


# ---------------------------------------------------------------------------
# In-series gas backup sizing utilities
# ---------------------------------------------------------------------------

_ASHRAE_WINDOWS: list[int] = [5, 15, 30, 60]
_RECOMMENDED_WINDOW: int   = 30


def size_supplemental_heating_and_storage(
    primary_system,
    building,
    nominal_capacity_kbtuh: float,
    draw_variable: str = "draw_thru_system_gal",
    temperature_variable: str = None,
) -> tuple[list[float], list[float]]:
    """
    Run peak-aligned 2-day simulation(s) on an undersized primary system and
    return the worst-case outage profile for supplemental heating/storage sizing.

    The simulation starts at each hour where the primary (net of recirc loss)
    cannot keep up with demand.  The run producing the largest max temperature
    deficit is kept.  No components are built; the caller uses the returned
    arrays with ``gas_backup_from_window`` and ``get_ashrae_sizing_curve``.

    ``primary_system.simulate_step`` is called directly at each timestep.
    In-series subclasses (e.g. ``SP_RTPInSeriesSystem``) must detect that the
    supplemental tank has not been built yet and fall back to their parent
    ``simulate_step`` so that only the primary is simulated.

    Parameters
    ----------
    primary_system : DHWSystem
        The undersized primary system.  Must expose ``storage_tank``,
        ``storage_temp_f``, ``supply_temp_f``, ``get_recirc_loss_kbtuh()``,
        and ``get_initial_hot_fract()``.
    building : Building
        The building the system serves.
    nominal_capacity_kbtuh : float
        Primary heater capacity [kBTU/hr], used to find peak-demand hours.
    draw_variable : str
        Key in the ``simulate_step`` result dict that holds the per-timestep
        draw volume [gal].  Defaults to ``"draw_thru_system_gal"``.

    Returns
    -------
    tuple[list[float], list[float]]
        ``(outage_volume_gal, outage_temp_delta_f)`` — parallel lists of
        length 2 × 24 × 60 = 2880.

    Raises
    ------
    ValueError
        If the primary is already adequately sized (outage ≤ 10 min AND
        max deficit ≤ 2 °F), meaning no gas backup is required.
    """
    _MIN_OUTAGE_MIN = 10
    _MIN_DEFICIT_F  = 2.0
    _TOTAL_STEPS    = 2 * 24 * 60

    inlet_temp_f      = building.get_design_inlet_water_temp_f()
    initial_hot_fract = primary_system.get_initial_hot_fract()
    recirc_loss_kbtuh = primary_system.get_recirc_loss_kbtuh()

    if nominal_capacity_kbtuh <= recirc_loss_kbtuh:
        peak_start_minutes = [0]
    else:
        net_capacity_kbtuh = nominal_capacity_kbtuh - recirc_loss_kbtuh
        gen_rate_gph = (
            net_capacity_kbtuh * 1000.0
            / (_RHO_CP * (primary_system.supply_temp_f - inlet_temp_f))
        )
        hourly_diff_gph = (
            gen_rate_gph
            - building.daily_dhw_use_supplyT_gal * building.peak_load_shape
        )
        peak_indices       = _get_peak_indices(hourly_diff_gph)
        peak_start_minutes = [idx * 60 for idx in peak_indices] if peak_indices else [0]

    best_outage_volume_gal   = []
    best_outage_temp_delta_f = []
    best_max_delta: float    = -1.0

    for peak_start in peak_start_minutes:
        primary_system.storage_tank.initialize(
            primary_system.storage_temp_f, inlet_temp_f, initial_hot_fract=initial_hot_fract
        )
        run_volume_gal   = []
        run_temp_delta_f = []

        for t in range(peak_start, peak_start + _TOTAL_STEPS):
            step     = primary_system.simulate_step(building, t, 1)
            if temperature_variable is None:
                top_temp = primary_system.storage_tank.get_temperature_at_fraction(1.0)
            else:
                top_temp = step[temperature_variable]
            demand   = step[draw_variable]
            if top_temp < primary_system.supply_temp_f:
                deficit_f = primary_system.supply_temp_f - top_temp
                run_volume_gal.append(demand)
                run_temp_delta_f.append(deficit_f)
            else:
                run_volume_gal.append(0.0)
                run_temp_delta_f.append(0.0)

        run_max_delta = max(run_temp_delta_f)
        if run_max_delta > best_max_delta:
            best_max_delta           = run_max_delta
            best_outage_volume_gal   = run_volume_gal
            best_outage_temp_delta_f = run_temp_delta_f

    total_outage_min = sum(1 for v in best_outage_volume_gal if v > 0.0)
    if total_outage_min <= _MIN_OUTAGE_MIN and best_max_delta <= _MIN_DEFICIT_F:
        raise ValueError(
            "The primary system is already adequately sized: "
            f"outage duration was {total_outage_min} min "
            f"(threshold {_MIN_OUTAGE_MIN} min) and max temperature deficit "
            f"was {best_max_delta:.2f} °F (threshold {_MIN_DEFICIT_F:.1f} °F). "
            "No gas backup is required."
        )

    return best_outage_volume_gal, best_outage_temp_delta_f


def gas_backup_from_window(
    outage_volume_gal: list[float],
    outage_temp_delta_f: list[float],
    window_min: int,
) -> tuple[float, float]:
    """
    Find the worst contiguous ``window_min``-length stretch of the outage
    arrays and return the implied gas backup capacity and storage volume.

    Uses the ASHRAE diversity ratio (via ``ashrae_method_water_use_ratio``)
    to convert peak-window volume to a realistic hourly-equivalent storage
    requirement.  ``window_min`` must be one of [5, 15, 30, 60].

    Parameters
    ----------
    outage_volume_gal : list[float]
        Per-minute demand during primary outage (0 outside outage) [gal].
    outage_temp_delta_f : list[float]
        Per-minute temperature deficit during outage (0 outside) [°F].
    window_min : int
        Contiguous window length in minutes. Must be in [5, 15, 30, 60].

    Returns
    -------
    tuple[float, float]
        ``(gas_capacity_kbtuh, gas_storage_vol_gal)``
    """
    total_steps = len(outage_volume_gal)
    w = min(window_min, total_steps)

    # Score windows by sum(vol × delta) — the per-minute heat-deficit rate
    # integrated over the window — rather than sum(delta) alone.
    #
    # Using sum(delta) fails when the primary is fully depleted throughout the
    # outage and delta is therefore constant (e.g. SwingDualFuelSystem when
    # nominal_capacity ≈ recirc_loss): every window ties on delta and the
    # algorithm keeps best_start = 0, which may fall in an off-peak, low-flow
    # window where only recirc is flowing.  Scoring by vol × delta ensures a
    # high-demand peak window (large vol AND large delta) beats a low-flow
    # off-peak window regardless of whether delta is flat.
    #
    # To revert to the original delta-only scoring, replace the three lines
    # below that reference `heat_deficit` with:
    #   window_score = sum(outage_temp_delta_f[:w])
    #   ...
    #   window_score += outage_temp_delta_f[i + w - 1] - outage_temp_delta_f[i - 1]
    heat_deficit = outage_temp_delta_f
    window_score = sum(heat_deficit[:w])
    best_score   = window_score
    best_start   = 0

    for i in range(1, total_steps - w + 1):
        window_score += heat_deficit[i + w - 1] - heat_deficit[i - 1]
        if window_score > best_score:
            best_score = window_score
            best_start = i

    best_slice_vol   = outage_volume_gal[best_start : best_start + w]
    best_slice_delta = outage_temp_delta_f[best_start : best_start + w]

    gas_storage_vol_gal = ashrae_method_water_use_ratio(window_min, sum(best_slice_vol))
    avg_peak_flow_gpm   = gas_storage_vol_gal / w
    avg_delta_f = sum(best_slice_delta) / w if any(d > 0 for d in best_slice_delta) else 0.0
    gas_capacity_kbtuh  = _RHO_CP * avg_peak_flow_gpm * avg_delta_f * 60.0 / 1000.0

    return gas_capacity_kbtuh, gas_storage_vol_gal


def get_ashrae_sizing_curve(
    outage_volume_gal: list[float],
    outage_temp_delta_f: list[float]
) -> dict:
    """
    Compute the gas backup sizing curve across all ASHRAE window durations.

    Sweeps ``window_min`` over [5, 15, 30, 60] minutes, calling
    ``gas_backup_from_window`` at each size.  The 30-minute window is the
    recommended design point.

    Parameters
    ----------
    outage_volume_gal : list[float]
        Per-minute outage demand array from ``size_supplemental_heating_and_storage``.
    outage_temp_delta_f : list[float]
        Per-minute temperature deficit array from ``size_supplemental_heating_and_storage``.

    Returns
    -------
    dict
        ``"window_sizes"``       : list[int]   — ASHRAE window durations [min]
        ``"capacities_kbtuh"``   : list[float] — gas heater capacity [kBTU/hr]
        ``"storages_gal"``       : list[float] — gas storage volume [gal]
        ``"recommended_index"``  : int         — index of the 30-min window

    Raises
    ------
    RuntimeError
        If both outage arrays are empty.
    """
    if not outage_volume_gal:
        raise RuntimeError(
            "Outage arrays are empty. Call size_supplemental_heating_and_storage() first."
        )

    capacities = []
    storages   = []
    for w in _ASHRAE_WINDOWS:
        cap, vol = gas_backup_from_window(outage_volume_gal, outage_temp_delta_f, w)
        capacities.append(cap)
        storages.append(vol)

    return {
        "window_sizes":      _ASHRAE_WINDOWS,
        "capacities_kbtuh":  capacities,
        "storages_gal":      storages,
        "recommended_index": _ASHRAE_WINDOWS.index(_RECOMMENDED_WINDOW),
    }


def plot_ashrae_sizing_curve(
    curve: dict,
    title: str = "Gas Backup Sizing Curve",
) -> "plotly.graph_objects.Figure":
    """
    Build a Plotly sizing-curve figure from the dict returned by
    ``get_ashrae_sizing_curve``.

    The curve plots gas storage volume (x) vs. gas heating capacity (y) for
    each ASHRAE window duration, with a slider to select the design point.
    The recommended 30-minute window is the default active position.

    Parameters
    ----------
    curve : dict
        Output of ``get_ashrae_sizing_curve()``.
    title : str
        Figure title.

    Returns
    -------
    plotly.graph_objects.Figure

    Raises
    ------
    ImportError
        If plotly is not installed.
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        raise ImportError(
            "plotly is required for plot_ashrae_sizing_curve(). "
            "Install it with: pip install plotly"
        )

    window_sizes = curve["window_sizes"]
    capacities   = curve["capacities_kbtuh"]
    storages     = curve["storages_gal"]
    rec_idx      = curve["recommended_index"]

    hover = (
        "Window: <b>%{customdata} min</b><br>"
        "Gas storage: <b>%{x:.1f} gal</b><br>"
        "Gas capacity: <b>%{y:.1f} kBTU/hr</b>"
        "<extra></extra>"
    )

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=storages, y=capacities,
        mode="lines",
        line=dict(color="#28a745", width=3),
        customdata=window_sizes,
        hovertemplate=hover,
        showlegend=False,
    ))

    for i, w in enumerate(window_sizes):
        fig.add_trace(go.Scatter(
            x=[storages[i]], y=[capacities[i]],
            mode="markers",
            marker=dict(symbol="diamond", color="#2EA3F2", size=12),
            customdata=[w],
            hovertemplate=hover,
            showlegend=False,
            visible=(i == rec_idx),
        ))

    steps = []
    for i, w in enumerate(window_sizes):
        visibility = [True] + [j == i for j in range(len(window_sizes))]
        steps.append(dict(
            label=(
                f"Window: <b>{w} min</b>  |  "
                f"Storage: <b>{storages[i]:.1f} gal</b>  |  "
                f"Capacity: <b>{capacities[i]:.1f} kBTU/hr</b>"
            ),
            method="update",
            args=[{"visible": visibility}],
        ))

    fig.update_layout(
        title=title,
        xaxis_title="Gas Storage Volume (gal)",
        yaxis_title="Gas Heating Capacity (kBTU/hr)",
        showlegend=False,
        sliders=[dict(
            steps=steps,
            active=rec_idx,
            currentvalue=dict(
                prefix="<b>Selected size</b>: ",
                visible=True,
                font=dict(size=14),
                xanchor="left",
            ),
            pad={"t": 60},
            ticklen=0,
            minorticklen=0,
            bgcolor="#CCD9DB",
            borderwidth=0,
        )],
    )

    return fig