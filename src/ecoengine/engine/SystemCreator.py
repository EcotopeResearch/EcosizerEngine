from ecoengine.objects.SystemConfig import *
from ecoengine.objects.systems.SwingTank import *
from ecoengine.objects.systems.ParallelLoopTank import *

def createSystem(schematic, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building = None, doLoadShift = False, 
                 aquaFractLoadUp = None, aquaFractShed = None, loadUpT_F = None, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, safetyTM = 1.75, 
                 setpointTM_F = 135, TMonTemp_F = 120, offTime_hr = 0.333, PVol_G_atStorageT = None, PCap_kBTUhr = None, TMVol_G = None, TMCap_kBTUhr = None,
                 systemModel = None):
    """
    Initializes and sizes the HPWH system. Both primary and tempurature maintenance (for parrallel loop and swing tank) are set up in this function.

    Attributes
    ----------
    schematic : String
        Indicates schematic type. Valid values are 'swingtank', 'paralleltank', and 'primary'
    storageT_F : float 
        The hot water storage temperature. [°F]
    defrostFactor : float 
        A multipier used to account for defrost in the final heating capacity. Default equals 1.
    percentUseable : float
        The fraction of the storage volume that can be filled with hot water.
    compRuntime_hr : float
        The number of hours the compressor will run on the design day. [Hr]
    aquaFract: float
        The fraction of the total height of the primary hot water tanks at which the Aquastat is located.
    building : Building
        Building object the HPWH system will be sized for.
    doLoadShift : boolean
        Set to true if doing loadshift
    aquaFractLoadUp : float
        The fraction of the total height of the primary hot water tanks at which the load up aquastat is located.
    aquaFractShed : float
        The fraction of the total height of the primary hot water tanks at which the shed aquastat is located.
    loadUpT_F : float
        The hot water storage temperature between the normal and load up aquastat. [°F]
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

    Raises
    ----------
    Exception: Error if schematic is not in list of valid schematic names.

    """
    
    match schematic:
        case 'swingtank':
            return SwingTank(safetyTM, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building,
                doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, aquaFractShed, loadUpT_F,
                systemModel, PVol_G_atStorageT, PCap_kBTUhr, TMVol_G, TMCap_kBTUhr)        
        case 'paralleltank':
            return ParallelLoopTank(safetyTM, setpointTM_F, TMonTemp_F, offTime_hr, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, 
                building, doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, aquaFractShed, loadUpT_F,
                systemModel, PVol_G_atStorageT, PCap_kBTUhr, TMVol_G, TMCap_kBTUhr)
        case 'primary':
            return Primary(storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building, 
                doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, aquaFractShed, loadUpT_F,
                systemModel, PVol_G_atStorageT, PCap_kBTUhr)
        case _:
            raise Exception("Unknown system schematic type.")
        