from objects.SystemConfig import *
from objects.systems.SwingTank import *

def createSystem(schematic, building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, doLoadShift = False, 
                 cdf_shift = 1, schedule = None, safetyTM = 0, setpointTM_F = 0, TMonTemp_F = 0, offTime_hr = 0, CA = False):
    
    match schematic:
        case 'swingtank':
            return SwingTank(safetyTM, building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, 
                             doLoadShift, cdf_shift, schedule, CA)
        case _:
            raise Exception("Not prepared for that type yet.")
        