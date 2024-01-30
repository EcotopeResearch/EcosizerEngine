from ecoengine.objects.SystemConfig import SystemConfig
from ecoengine.objects.SimulationRun import SimulationRun
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import convertVolume
from ecoengine.objects.Building import Building

class PrimaryWithRecirc(SystemConfig):
    def __init__(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, aquaFractLoadUp = None, 
                 aquaFractShed = None, loadUpT_F = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, 
                 PCap_kBTUhr = None, ignoreShortCycleEr = False, useHPWHsimPrefMap = False, inletWaterAdjustment = 0.25):
        
        self.inletWaterAdjustment = inletWaterAdjustment
        
        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building, doLoadShift, 
                loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, aquaFractShed, loadUpT_F, systemModel, 
                numHeatPumps, PVol_G_atStorageT, PCap_kBTUhr, ignoreShortCycleEr, useHPWHsimPrefMap)
        
    def getDesignIncomingTemp(self, building: Building):
        return building.getHighestIncomingT_F() + ((self.storageT_F - building.getHighestIncomingT_F()) * self.inletWaterAdjustment)
        
    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None):
        
        averageInletWater_T = simRun.getIncomingWaterT(i) + ((self.storageT_F - simRun.getIncomingWaterT(i)) * self.inletWaterAdjustment) 
        self.preSystemStepSetUp(simRun, i, averageInletWater_T, minuteIntervals, oat)
        # Account for recirculation losses at storage temperature
        exitingWater = simRun.hwDemand[i] + simRun.generateRecircLoss(i)
        
        # get both water leaving system and rate of hw generatipon in storage temp
        mixedDHW = convertVolume(exitingWater, self.storageT_F, simRun.getIncomingWaterT(i), simRun.building.supplyT_F) 
        mixedGHW = convertVolume(simRun.hwGenRate, self.storageT_F, simRun.getIncomingWaterT(i), simRun.building.supplyT_F)

        simRun.pheating, simRun.pV[i], simRun.pGen[i], simRun.pRun[i] = self.runOnePrimaryStep( pheating = simRun.pheating,
                                                                                                Vcurr = simRun.pV[i-1], 
                                                                                                hw_out = mixedDHW, 
                                                                                                hw_in = mixedGHW, 
                                                                                                mode = simRun.getLoadShiftMode(i),
                                                                                                modeChanged = (simRun.getLoadShiftMode(i) != simRun.getLoadShiftMode(i-1)),
                                                                                                minuteIntervals = minuteIntervals)