from ecoengine.objects.SystemConfig import *
from ecoengine.objects.systems.SwingTank import *
from ecoengine.objects.systems.ParallelLoopTank import *
from ecoengine.objects.systems.MultiPass import *
from ecoengine.objects.systems.MultiPassRecirc import *
from ecoengine.objects.systems.PrimaryWithRecirc import *
from ecoengine.objects.systems.SwingTankER import *
from ecoengine.objects.systems.InstantWH import *
from ecoengine.objects.systems.SPRTP import *
from ecoengine.objects.systems.MPRTP import *

def createSystem(schematic, storageT_F, defrostFactor, percentUseable, compRuntime_hr,
                 onFract, offFract = None, onT = None, offT = None,
                 building = None, doLoadShift = False, outletLoadUpT = None,
                 onFractLoadUp = None, offFractLoadUp = None, onLoadUpT = None, offLoadUpT = None, 
                 onFractShed = None, offFractShed = None, onShedT = None, offShedT = None, 
                 loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, safetyTM = 1.75, 
                 setpointTM_F = 135, TMonTemp_F = 120, offTime_hr = 0.333, PVol_G_atStorageT = None, PCap_kBTUhr = None, TMVol_G = None, TMCap_kBTUhr = None,
                 systemModel = None, numHeatPumps = None, tmModel = None, tmNumHeatPumps = None, inletWaterAdjustment = None,
                 useHPWHsimPrefMap = False, sizeAdditionalER = True, additionalERSaftey = 1.0) -> SystemConfig:
    """
    Initializes and sizes the HPWH system. Both primary and tempurature maintenance (for parrallel loop and swing tank) are set up in this function.

    Attributes
    ----------
    schematic : String
        Indicates schematic type. Valid values are 'swingtank', 'paralleltank', 'multipass', and 'primary'
    storageT_F : float 
        The hot water storage temperature. [°F]
    defrostFactor : float 
        A multipier used to account for defrost in the final heating capacity. Default equals 1.
    percentUseable : float
        The fraction of the storage volume that can be filled with hot water.
    compRuntime_hr : float
        The number of hours the compressor will run on the design day. [Hr]

    onFract: float
        The fraction of the total height of the primary hot water tanks at which the ON temperature sensor is located.
    offFract : float
        The fraction of the total height of the primary hot water tanks at which the OFF temperature is located (defaults to onFract if not specified)
    onT : float
        The temperature detected at the onFract at which the HPWH system will be triggered to turn on. (defaults to supplyT_F if not specified)
    offT : float
        The temperature detected at the offFract at which the HPWH system will be triggered to turn off. (defaults to storageT_F if not specified)

    building : Building
        Building object the HPWH system will be sized for.
    doLoadShift : boolean
        Set to true if doing loadshift

    outletLoadUpT : float 
        The hot water outlet temperature during load up mode. [°F]
    onFractLoadUp : float
        The fraction of the total height of the primary hot water tanks at which the ON temperature sensor is located during load up periods. (defaults to onFract if not specified)
    offFractLoadUp : float
        The fraction of the total height of the primary hot water tanks at which the OFF temperature sensor is located during load up periods. (defaults to offFract if not specified)
    onLoadUpT : float
        The temperature detected at the onFractLoadUp at which the HPWH system will be triggered to turn on during load up periods. (defaults to onT if not specified)
    offLoadUpT : float
        The temperature detected at the offFractLoadUp at which the HPWH system will be triggered to turn off during load up periods. (defaults to offT if not specified)
    onFractShed : float
        The fraction of the total height of the primary hot water tanks at which the ON temperature sensor is located during shed periods. (defaults to onFract if not specified)
    offFractShed : float
        The fraction of the total height of the primary hot water tanks at which the OFF temperature is located during shed priods (defaults to offFract if not specified)
    onShedT : float
        The temperature detected at the onFractShed at which the HPWH system will be triggered to turn on during shed periods. (defaults to onT if not specified)
    offShedT : float
        The temperature detected at the offFractShed at which the HPWH system will be triggered to turn off during shed periods. (defaults to offT if not specified)

    loadShiftPercent: float
        Percentage of days the load shift will be met
    loadShiftSchedule : array_like
        List or array of 0's and 1's for don't run and run respectively. Used for load shifting 
    loadUpHours : float
        Number of hours spent loading up for first shed.
    safetyTM : float
        The saftey factor for the temperature maintenance system.
    setpointTM_F : float
        The setpoint of the temprature maintence tank. Defaults to 130 °F.
    TMonTemp_F : float
        The temperature where parallel loop tank will turn on.
        Defaults to 120 °F.
    offTime_hr: integer
        Maximum hours per day the temperature maintenance equipment can run.
    PVol_G_atStorageT : float
        For pre-sized systems, the total/maximum storage volume for water at storage temperature for the system in gallons
    PCap_kBTUhr : float
        For pre-sized systems, the output capacity for the system in kBTUhr
    TMVol_G : float
        For applicable pre-sized systems, the temperature maintenance volume for the system in gallons
    TMCap_kBTUhr : float
        For applicable pre-sized systems, the output capacity for temperature maintenance for the system in kBTUhr
    systemModel : String
        The make/model of the HPWH being used.
    numHeatPumps : int
        The number of heatpumps the HPWH model is using
    tmModel : String
        The make/model of the HPWH being used for the temperature maintenance system.
    tmNumHeatPumps : int
        The number of heat pumps on the temperature maintenance system
    inletWaterAdjustment : float
        adjustment for inlet water temperature fraction for primary recirculation systems
    useHPWHsimPrefMap : boolean
        if available for the HPWH model in systemModel and/or tmModel, the system will use the preformance map from HPWHsim if useHPWHsimPrefMap is set to True. 
        Otherwise, it will use the most recent data model.
    sizeAdditionalER : boolean
        if set to True for a swingtank_er schematic, will size for additional ER element. False if there is no need to size additional ER for swingtank_er schematic
    additionalERSaftey : float
        applicable for ER trade off swing tank only. Saftey factor to apply to additional electric resistance sizing
        
    Raises
    ----------
    Exception: Error if schematic is not in list of valid schematic names.

    """
    
    match schematic:
        case 'swingtank':
            return SwingTank(safetyTM, storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT,
                doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                PCap_kBTUhr, useHPWHsimPrefMap, TMVol_G, TMCap_kBTUhr)   
        case 'swingtank_er':
            return SwingTankER(safetyTM, storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT,
                doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                PCap_kBTUhr, useHPWHsimPrefMap, TMVol_G, TMCap_kBTUhr, 
                sizeAdditionalER, additionalERSaftey)       
        case 'paralleltank':
            return ParallelLoopTank(safetyTM, setpointTM_F, TMonTemp_F, offTime_hr, storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT,
                doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                PCap_kBTUhr, useHPWHsimPrefMap, TMVol_G, TMCap_kBTUhr, tmModel, tmNumHeatPumps)
        case 'multipass_norecirc': # same as multipass
            if inletWaterAdjustment is None:
                inletWaterAdjustment = 0.5
            return MultiPass(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT,
                doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                PCap_kBTUhr, useHPWHsimPrefMap, inletWaterAdjustment)
        case 'multipass': # same as multipass_norecirc
            if inletWaterAdjustment is None:
                inletWaterAdjustment = 0.5
            return MultiPass(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT,
                doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                PCap_kBTUhr, useHPWHsimPrefMap, inletWaterAdjustment)
        case 'multipass_rtp':
            if inletWaterAdjustment is None:
                inletWaterAdjustment = 0.5
            return MultiPassRecirc(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT,
                doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                PCap_kBTUhr, useHPWHsimPrefMap, inletWaterAdjustment)
        case 'primary': # same as singlepass_norecirc
            return Primary(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                 outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT,
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                 PCap_kBTUhr, useHPWHsimPrefMap)
        case 'singlepass_norecirc': # same as primary
            return Primary(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                 outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT,
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                 PCap_kBTUhr, useHPWHsimPrefMap)
        case 'sprtp':
            return SPRTP(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                 outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT,
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                 PCap_kBTUhr, useHPWHsimPrefMap)
        case 'mprtp':
            return MPRTP(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                 outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT,
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                 PCap_kBTUhr, useHPWHsimPrefMap)
        case 'singlepass_rtp':
            if inletWaterAdjustment is None:
                inletWaterAdjustment = 0.25
            return PrimaryWithRecirc(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT,
                doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                PCap_kBTUhr, useHPWHsimPrefMap, inletWaterAdjustment)
        case 'instant_wh':
            return InstantWH(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                 outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT,
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                 PCap_kBTUhr, useHPWHsimPrefMap)
        case _:
            raise Exception("Unknown system schematic type: "+str(schematic))
        