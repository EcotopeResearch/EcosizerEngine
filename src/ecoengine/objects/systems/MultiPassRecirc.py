from ecoengine.objects.systems.PrimaryWithRecirc import PrimaryWithRecirc
from ecoengine.objects.SimulationRun import SimulationRun
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import convertVolume

class MultiPassRecirc(PrimaryWithRecirc):
    def __init__(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                 outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, systemModel = None, 
                 numHeatPumps = None, PVol_G_atStorageT = None, PCap_kBTUhr = None, useHPWHsimPrefMap = False, inletWaterAdjustment = 0.5):
        # set static aquastat fractions, ignore inputs
        
        onFract = 0.15
        onFractLoadUp = 0.15
        onFractShed = 0.3
        if not systemModel is None and not systemModel[-2:] == 'MP':
            raise Exception("Multipass (with recirc) tank model must be a multipass system.")
        
        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                 outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT, 
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                 PCap_kBTUhr, useHPWHsimPrefMap, inletWaterAdjustment)
        
    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None):
        
        averageInletWater_T = self.storageT_F - 15# Multi pass return to primary: CHPWH IWT is assumed 15°F cooler than storage temperature on average, based on lab test data.
        self.preSystemStepSetUp(simRun, i, averageInletWater_T, minuteIntervals, oat)
        # Account for recirculation losses at storage temperature
        exitingWater = simRun.hwDemand[i] + simRun.generateRecircLoss(i)
        
        # get both water leaving system and rate of hw generatipon in storage temp
        mixedDHW = convertVolume(exitingWater, self.storageT_F, simRun.getIncomingWaterT(i), simRun.building.supplyT_F) 
        self.runOnePrimaryStep(simRun, i, mixedDHW, simRun.getIncomingWaterT(i))
