from ecoengine.objects.SystemConfig import SystemConfig
from ecoengine.objects.SimulationRun import SimulationRun
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import mixVolume

class MultiPass(SystemConfig):
    def __init__(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, aquaFractLoadUp = None, 
                 aquaFractShed = None, loadUpT_F = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, PCap_kBTUhr = None, inletWaterAdjustment = 0.5):
        
        aquaFract = 0.15
        aquaFractLoadUp = 0.15
        aquaFractShed = 0.3
        self.inletWaterAdjustment = inletWaterAdjustment

        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building, doLoadShift, 
                loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, aquaFractShed, loadUpT_F, systemModel, 
                numHeatPumps, PVol_G_atStorageT, PCap_kBTUhr)
        
    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None):
        
        incomingWater_T = simRun.getIncomingWaterT(i) + ((self.storageT_F - simRun.getIncomingWaterT(i)) * self.inletWaterAdjustment) 

        if not (oat is None or self.perfMap is None):
            # set primary system capacity based on outdoor ait temp and incoming water temp 
            self.setCapacity(oat = oat, incomingWater_T = incomingWater_T)
            simRun.addHWGen((1000 * self.PCap_kBTUhr / rhoCp / (simRun.building.supplyT_F - simRun.getIncomingWaterT(i)) \
               * self.defrostFactor)/(60/minuteIntervals))
        
        tankStorageT_F = simRun.mixedStorT_F
        if self.doLoadShift and simRun.getLoadShiftMode(i) == 'L':
            tankStorageT_F = self.loadUpT_F

        # Get exiting and generating water volumes at storage temp
        mixedDHW = mixVolume(simRun.hwDemand[i], tankStorageT_F, simRun.getIncomingWaterT(i), simRun.building.supplyT_F)
        mixedGHW = mixVolume(simRun.hwGenRate, tankStorageT_F, simRun.getIncomingWaterT(i), simRun.building.supplyT_F)

        simRun.pheating, simRun.pV[i], simRun.pGen[i], simRun.pRun[i] = self.runOnePrimaryStep(pheating = simRun.pheating, 
                                                                                            V0 = simRun.V0, 
                                                                                            Vtrig = simRun.Vtrig[i], 
                                                                                            Vcurr = simRun.pV[i-1], 
                                                                                            hw_out = mixedDHW, 
                                                                                            hw_in = mixedGHW, 
                                                                                            Vtrig_previous = simRun.Vtrig[i-1],
                                                                                            minuteIntervals = minuteIntervals) 