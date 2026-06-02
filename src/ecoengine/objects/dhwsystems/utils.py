from ecoengine.constants.constants import _RHO_CP

def mixing_valve_behavior(load_supplyT_gal : float, flow_returnT_gal : float, cold_temp_f : float, supply_temp_f : float, return_temp_f : float, storage_temp_f : float) -> dict:
    if storage_temp_f <= supply_temp_f:
        storage_draw_gal = load_supplyT_gal + flow_returnT_gal
        recirc_loop_delta_f = supply_temp_f - return_temp_f
        derated_recirc_temp_f = storage_temp_f - recirc_loop_delta_f
        inlet_temp_f = ((load_supplyT_gal * cold_temp_f) + (flow_returnT_gal * derated_recirc_temp_f)) / storage_draw_gal
    else:
    # For minute intervals, storage_temp_f is whatever temperature is at the top of the storage tank, set point storage temperature or not
        recirc_loss_btu = flow_returnT_gal * _RHO_CP * (supply_temp_f - return_temp_f)
        critical_flow_gal = recirc_loss_btu / (_RHO_CP * (storage_temp_f - supply_temp_f))

        if load_supplyT_gal > critical_flow_gal:
            storage_draw_gal = (load_supplyT_gal * ((supply_temp_f - cold_temp_f) / (storage_temp_f - cold_temp_f))) + \
                (flow_returnT_gal * ((supply_temp_f - return_temp_f) / (storage_temp_f - cold_temp_f)))
            inlet_temp_f = cold_temp_f
        else:
            storage_draw_gal = (load_supplyT_gal + flow_returnT_gal) * ((supply_temp_f - return_temp_f) / (storage_temp_f - return_temp_f))
            recirc_to_tank_gal = storage_draw_gal - load_supplyT_gal
            inlet_temp_f = ((load_supplyT_gal * cold_temp_f) + (recirc_to_tank_gal * return_temp_f)) / storage_draw_gal
    return {
        "storage_draw_gal" : storage_draw_gal,
        "inlet_temp_f" : inlet_temp_f
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