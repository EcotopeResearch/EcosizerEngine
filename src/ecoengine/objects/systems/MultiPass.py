from ecoengine.objects.SystemConfig import SystemConfig
from ecoengine.objects.SimulationRun import SimulationRun
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import convertVolume

class MultiPass(SystemConfig):
    def __init__(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, aquaFractLoadUp = None, 
                 aquaFractShed = None, loadUpT_F = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, 
                 PCap_kBTUhr = None, ignoreShortCycleEr = False, inletWaterAdjustment = 0.5):
        
        aquaFract = 0.15
        aquaFractLoadUp = 0.15
        aquaFractShed = 0.3
        self.inletWaterAdjustment = inletWaterAdjustment

        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building, doLoadShift, 
                loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, aquaFractShed, loadUpT_F, systemModel, 
                numHeatPumps, PVol_G_atStorageT, PCap_kBTUhr, ignoreShortCycleEr)
        
    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None):
        
        incomingWater_T = simRun.getIncomingWaterT(i) + ((self.storageT_F - simRun.getIncomingWaterT(i)) * self.inletWaterAdjustment) 
        if i > 0 and simRun.getIncomingWaterT(i) != simRun.getIncomingWaterT(i-1):
            self.setLoadUPVolumeAndTrigger(simRun.getIncomingWaterT(i))
        if not (oat is None or self.perfMap is None):
            # set primary system capacity based on outdoor ait temp and incoming water temp 
            self.setCapacity(oat = oat, incomingWater_T = incomingWater_T)
            simRun.addHWGen((1000 * self.PCap_kBTUhr / rhoCp / (simRun.building.supplyT_F - simRun.getIncomingWaterT(i)) \
               * self.defrostFactor)/(60/minuteIntervals))

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