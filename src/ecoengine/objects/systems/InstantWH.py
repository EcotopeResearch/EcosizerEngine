from ecoengine.objects.SystemConfig import SystemConfig
from ecoengine.objects.SimulationRun import SimulationRun
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import convertVolume

class InstantWH(SystemConfig):
    def __init__(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                 outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, systemModel = None, 
                 numHeatPumps = None, PVol_G_atStorageT = None, PCap_kBTUhr = None, useHPWHsimPrefMap = False):
        
        if doLoadShift:
            raise Exception("Instantaneous water heaters can not perform loadshifting because they do not have storage.")

        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                 outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT, 
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                 PCap_kBTUhr, useHPWHsimPrefMap)
        
    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None):
        incomingWater_T = simRun.getIncomingWaterT(i)
        self.preSystemStepSetUp(simRun, i, incomingWater_T, minuteIntervals, oat)
        
        # Get exiting and generating water volumes at storage temp
        mixedDHW = convertVolume(simRun.hwDemand[i], self.storageT_F, incomingWater_T, simRun.building.supplyT_F)
        # print("here")
        simRun.pV[i], simRun.pGen[i], simRun.pRun[i] = 0, mixedDHW, minuteIntervals
    
    def preSystemStepSetUp(self, simRun : SimulationRun, i, incomingWater_T, minuteIntervals, oat):
        """
        helper function for runOneSystemStep
        """
        delta_T = simRun.building.supplyT_F - incomingWater_T
        PCap_kBTUhr = (simRun.hwDemand[i] * rhoCp * (60/minuteIntervals) * delta_T) / self.defrostFactor / 1000.
        self.setCapacity(PCap_kBTUhr, cop=1.0)
        hw_gen_for_interval = (1000 * self.PCap_kBTUhr / rhoCp / delta_T * self.defrostFactor)/(60/minuteIntervals)
        simRun.addHWGen(hw_gen_for_interval)