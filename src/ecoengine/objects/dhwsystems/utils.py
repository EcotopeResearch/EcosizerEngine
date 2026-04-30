from ecoengine.objects.components.storage.StorageTank import StorageTank
from ecoengine.constants.constants import _RHO_CP

def mixing_valve_behavior(load_supplyT_gal : float, flow_returnT_gal : float, cold_temp_f : float, supply_temp_f : float, return_temp_f : float, storage_temp_f : float) -> dict:
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