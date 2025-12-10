from ecoengine.objects.SystemConfig import SystemConfig
from ecoengine.objects.SimulationRun import SimulationRun
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import convertVolume

class MultiPass(SystemConfig):
    def __init__(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                 outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, systemModel = None, 
                 numHeatPumps = None, PVol_G_atStorageT = None, PCap_kBTUhr = None, useHPWHsimPrefMap = False, inletWaterAdjustment = 0.5):
        onFract = 0.15
        onFractLoadUp = 0.15
        onFractShed = 0.3
        self.inletWaterAdjustment = inletWaterAdjustment
        if not systemModel is None and not systemModel[-2:] == 'MP':
            raise Exception("Multipass (with recirc) tank model must be a multipass system.")

        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                 outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT, 
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                 PCap_kBTUhr, useHPWHsimPrefMap)
        
    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None):
        averageWater_T = self.storageT_F - 15 #simRun.getIncomingWaterT(i) + ((self.storageT_F - simRun.getIncomingWaterT(i)) * self.inletWaterAdjustment) This is the way HPWHsim does it
        self.preSystemStepSetUp(simRun, i, averageWater_T, minuteIntervals, oat)

        # Get exiting and generating water volumes at storage temp
        hw_load_at_storageT = convertVolume(simRun.hwDemand[i], self.storageT_F, simRun.getIncomingWaterT(i), simRun.building.supplyT_F)
       
        self.runOnePrimaryStep(simRun, i, hw_load_at_storageT, simRun.getIncomingWaterT(i))
