from ecoengine.objects.systems.PrimaryWithRecirc import PrimaryWithRecirc
from ecoengine.constants.Constants import *

class MultiPassRecirc(PrimaryWithRecirc):
    def __init__(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, aquaFractLoadUp = None, 
                 aquaFractShed = None, loadUpT_F = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, PCap_kBTUhr = None, inletWaterAdjustment = 0.5):
        # set static aquastat fractions, ignore inputs
        aquaFract = 0.15
        aquaFractLoadUp = 0.15
        aquaFractShed = 0.3
        
        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building, doLoadShift, 
                loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, aquaFractShed, loadUpT_F, systemModel, 
                numHeatPumps, PVol_G_atStorageT, PCap_kBTUhr, inletWaterAdjustment)