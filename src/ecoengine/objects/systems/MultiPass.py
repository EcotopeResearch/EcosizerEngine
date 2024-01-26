from ecoengine.objects.SystemConfig import SystemConfig
from ecoengine.objects.SimulationRun import SimulationRun
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import convertVolume

class MultiPass(SystemConfig):
    def __init__(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, aquaFractLoadUp = None, 
                 aquaFractShed = None, loadUpT_F = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, 
                 PCap_kBTUhr = None, ignoreShortCycleEr = False, useHPWHsimPrefMap = False, inletWaterAdjustment = 0.5):
        
        aquaFract = 0.15
        aquaFractLoadUp = 0.15
        aquaFractShed = 0.3
        self.inletWaterAdjustment = inletWaterAdjustment
        if not systemModel is None and not systemModel[-2:] == 'MP':
            raise Exception("Multipass (with recirc) tank model must be a multipass system.")

        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building, doLoadShift, 
                loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, aquaFractShed, loadUpT_F, systemModel, 
                numHeatPumps, PVol_G_atStorageT, PCap_kBTUhr, ignoreShortCycleEr, useHPWHsimPrefMap)
        
    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None):
        averageWater_T = self.storageT_F - 15 #simRun.getIncomingWaterT(i) + ((self.storageT_F - simRun.getIncomingWaterT(i)) * self.inletWaterAdjustment) This is the way HPWHsim does it
        self.preSystemStepSetUp(simRun, i, averageWater_T, minuteIntervals, oat)

        # Get exiting and generating water volumes at storage temp
        mixedDHW = convertVolume(simRun.hwDemand[i], self.storageT_F, simRun.getIncomingWaterT(i), simRun.building.supplyT_F)
        mixedGHW = convertVolume(simRun.hwGenRate, self.storageT_F, simRun.getIncomingWaterT(i), simRun.building.supplyT_F)

        simRun.pheating, simRun.pV[i], simRun.pGen[i], simRun.pRun[i] = self.runOnePrimaryStep(pheating = simRun.pheating,
                                                                                            Vcurr = simRun.pV[i-1], 
                                                                                            hw_out = mixedDHW, 
                                                                                            hw_in = mixedGHW, 
                                                                                            mode = simRun.getLoadShiftMode(i),
                                                                                            modeChanged = (simRun.getLoadShiftMode(i) != simRun.getLoadShiftMode(i-1)),
                                                                                            minuteIntervals = minuteIntervals) 