from ecosizer_engine_package.objects.SystemConfig import *
from ecosizer_engine_package.objects.systems.SwingTank import *
from ecosizer_engine_package.objects.systems.ParallelLoopTank import *

def createSystem(schematic, building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, doLoadShift = False, 
                 loadShiftPercent = 1, loadShiftSchedule = None, safetyTM = 1.75, setpointTM_F = 135, TMonTemp_F = 120, offTime_hr = 0.333):
    """
    Initializes and sizes the HPWH system. Both primary and tempurature maintenance (for parrallel loop and swing tank) are set up in this function.

    Attributes
    ----------
    schematic : String
        Indicates schematic type. Valid values are 'swingtank', 'paralleltank', and 'primary'
    building : Building
        Building object the HPWH system will be sized for.
    storageT_F : float 
        The hot water storage temperature. [°F]
    defrostFactor : float 
        A multipier used to account for defrost in the final heating capacity. Default equals 1.
    percentUseable : float
        The fraction of the storage volume that can be filled with hot water.
    compRuntime_hr : float
        The number of hours the compressor will run on the design day. [Hr]
    aquaFract: float
        The fraction of the total hieght of the primary hot water tanks at which the Aquastat is located.
    doLoadShift : boolean
        Set to true if doing loadshift
    loadShiftPercent: float
        Percentage of days the load shift will be met
    loadShiftSchedule : array_like
        List or array of 0's and 1's for don't run and run respectively. Used for load shifting
    safetyTM : float
        The saftey factor for the temperature maintenance system.
    setpointTM_F : float
        The setpoint of the temprature maintence tank. Defaults to 130 °F.
    TMonTemp_F : float
        The temperature where parallel loop tank will turn on.
        Defaults to 120 °F.
    offTime_hr: integer
        Maximum hours per day the temperature maintenance equipment can run.

    Raises
    ----------
    Exception: Error if schematic is not in list of valid schematic names.

    """
    
    match schematic:
        case 'swingtank':
            return SwingTank(safetyTM, building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, 
                             doLoadShift, loadShiftPercent, loadShiftSchedule)        
        case 'paralleltank':
            return ParallelLoopTank(safetyTM, setpointTM_F, TMonTemp_F, offTime_hr, building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, 
                 doLoadShift, loadShiftPercent, loadShiftSchedule)
        case 'primary':
            return Primary(building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, doLoadShift, loadShiftPercent, loadShiftSchedule)
        case _:
            raise Exception("Unknown system schematic type.")
        