from ecoengine.objects.systems.SwingTank import SwingTank
from ecoengine.objects.SimulationRun import SimulationRun
import numpy as np
from ecoengine.objects.Building import Building
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import convertVolume, getMixedTemp, hrToMinList, getPeakIndices, checkHeatHours

class SwingTankER(SwingTank):

    def __init__(self, safetyTM, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building : Building,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, aquaFractLoadUp = None, 
                 aquaFractShed = None, loadUpT_F = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, PCap_kBTUhr = None, TMVol_G = None, 
                 TMCap_kBTUhr = None):

        super().__init__(safetyTM, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building,
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, 
                 aquaFractShed, loadUpT_F, systemModel, numHeatPumps, PVol_G_atStorageT, PCap_kBTUhr, TMVol_G, 
                 TMCap_kBTUhr)
        
        self.setLoadUPVolumeAndTrigger(building.incomingT_F)
        self.sizeERElement(building)
            
    def sizeERElement(self, building : Building):

        minuteIntervals = 1
        if building is None:
            raise Exception("Cannot size additional swing tank electric resistance without building parameter.")
        simRun = self.getInitializedSimulation(building, minuteIntervals = minuteIntervals, nDays = 2)
        #TODO handle for preformance maps (this means adding oat among other things....)
        i = 0
        normalFunction = True
        swingV = [0]*len(simRun.hwDemand)
        waterDeficit = [0]*len(simRun.hwDemand)
        while i < len(simRun.hwDemand):
            if normalFunction:
                i = self.findNextIndexOfHWDeficit(simRun, i, minuteIntervals = minuteIntervals)
                # print(f"index of HW deficit is {i}")
                if i < len(simRun.hwDemand):
                    normalFunction = False
            else:
                # get available supply temperature volume in system and pretend it is all in completely stratified swing tank
                swingV[i-1] = convertVolume(self.TMVol_G, building.supplyT_F, simRun.getIncomingWaterT(i-1), simRun.tmT_F[i-1]) + \
                    convertVolume(simRun.pV[i-1], building.supplyT_F, simRun.getIncomingWaterT(i-1), self.storageT_F)
                # print(f"ok we are in here now, swing vol is {swingV[i-1]} gal at supply temp")
                # get full hwGeneration rate of swing tank plus hw coming in from primary system
                fullHWGenRate = (1000 * self.TMCap_kBTUhr / (60/minuteIntervals) /rhoCp / (building.supplyT_F - simRun.getIncomingWaterT(i-1)) * self.defrostFactor) + simRun.hwGenRate
                recircLossAtTime = (building.recirc_loss / (rhoCp * (building.supplyT_F - simRun.getIncomingWaterT(i)))) / (60/minuteIntervals)
                # print(f"we generate {fullHWGenRate} gal total supply temp water, primary generates {simRun.hwGenRate} of that")
                while i < len(simRun.hwDemand) and not normalFunction:
                    waterLeavingSystem = simRun.hwDemand[i] + recircLossAtTime
                    # print(f"at index {i}, we lose {waterLeavingSystem} ({simRun.hwDemand[i]} from demand), meaning a {waterLeavingSystem-fullHWGenRate} gal deficit, so there will be {swingV[i-1] + fullHWGenRate - waterLeavingSystem} in swing")
                    # if fullHWGenRate >= waterLeavingSystem:
                    if convertVolume(simRun.hwGenRate, self.storageT_F, building.incomingT_F, building.supplyT_F) >= simRun.hwDemand[i]:
                        simRun.pV[i-1] = 0
                        if swingV[i-1] <= self.TMVol_G:
                            simRun.tmT_F[i-1] = building.supplyT_F
                        else:
                            simRun.tmT_F[i-1] =  ((swingV[i-1] * (building.supplyT_F - building.incomingT_F))/self.TMVol_G) + building.incomingT_F
                        # print(f"and we are back to normal at index {i}")
                        normalFunction = True
                        # return
                    else:
                        swingV[i] = swingV[i-1] + fullHWGenRate - waterLeavingSystem
                        waterDeficit[i] = waterLeavingSystem - fullHWGenRate
                        # waterDeficit[i] = self.TMVol_G - swingV[i]
                        i += 1


        # for i in range(len(swingV)):
        #     print(f"{i} swingV: {swingV[i]}, waterDeficit: {waterDeficit[i]}, simRun.pV {simRun.pV[i]}, simRun.tmT_F {simRun.tmT_F[i]}")
        # print("max deficit", max(waterDeficit))
        # print("hour of highest", waterDeficit.index(max(waterDeficit)))
        # print("original self.TMCap_kBTUhr", self.TMCap_kBTUhr)
        # print("simRun.hwGenRate",simRun.hwGenRate)
        self.TMCap_kBTUhr += (max(waterDeficit) * (60/minuteIntervals) * rhoCp * (building.supplyT_F - building.incomingT_F)) / 1000.  # additional ER to compensate
        # print("new self.TMCap_kBTUhr", self.TMCap_kBTUhr)
        # print("///////////////////////////////////////////////////////////////")
        return
    
    def findNextIndexOfHWDeficit(self, simRun : SimulationRun, i, minuteIntervals = 60, oat = None):
        while i < len(simRun.hwDemand):
            if simRun.pV[i-1] >= 0:
                super().runOneSystemStep(simRun, i, minuteIntervals, oat, erCalc=True)
            else:
                return i-1
            i += 1
        return i

    def runOneERCalcStep(self, simRun : SimulationRun, i, minuteIntervals = 60, oat = None):

        simRun.hw_outSwing[i] = convertVolume(simRun.hwDemand[i], simRun.tmT_F[i-1], incomingWater_T, simRun.building.supplyT_F)
        #Get the generation rate in storage temp
        mixedGHW = convertVolume(simRun.hwGenRate, self.storageT_F, incomingWater_T, simRun.building.supplyT_F)
        if simRun.pV[i-1] + mixedGHW > simRun.hw_outSwing[i]: # if 
            super().runOneSystemStep(simRun, i, minuteIntervals, oat, erCalc=True)
        else:
            incomingWater_T = simRun.getIncomingWaterT(i)
            # if primary system is out of hot water, the swing tank is working as an additional heat source so capacity is combined for hot water generation rate
            combinedHWGenRate = (1000 * (self.PCap_kBTUhr + self.TMCap_kBTUhr) / rhoCp / (simRun.building.supplyT_F - incomingWater_T) * self.defrostFactor)/(60/minuteIntervals)
            simRun.tmheating = True
            simRun.tmT_F[i] = simRun.building.supplyT_F 
            simRun.tmRun[i] = minuteIntervals

            #Get the mixed generation
            mixedGHW = convertVolume(combinedHWGenRate, self.storageT_F, incomingWater_T, simRun.building.supplyT_F)
            # get exiting water at storage temperature
            # Account for recirculation losses at storage temperature
            exitingWater = simRun.hwDemand[i] + simRun.generateRecircLoss(i)
            mixedDHW = convertVolume(exitingWater, self.storageT_F, incomingWater_T, simRun.building.supplyT_F)

            simRun.pheating, simRun.pV[i], simRun.pGen[i], simRun.pRun[i] = self.runOnePrimaryStep(pheating = simRun.pheating,
                                                                                                Vcurr = simRun.pV[i-1], 
                                                                                                hw_out = mixedDHW, 
                                                                                                hw_in = mixedGHW, 
                                                                                                mode = simRun.getLoadShiftMode(i),
                                                                                                modeChanged = (simRun.getLoadShiftMode(i) != simRun.getLoadShiftMode(i-1)),
                                                                                                minuteIntervals = minuteIntervals,
                                                                                                erCalc=True)
            
    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None, erCalc=False):
        incomingWater_T = simRun.getIncomingWaterT(i)
        if i > 0 and incomingWater_T != simRun.getIncomingWaterT(i-1):
            self.setLoadUPVolumeAndTrigger(incomingWater_T)
        if not (oat is None or self.perfMap is None):
            # set primary system capacity based on outdoor ait temp and incoming water temp 
            self.setCapacity(oat = oat, incomingWater_T = incomingWater_T)
            simRun.addHWGen((1000 * self.PCap_kBTUhr / rhoCp / (simRun.building.supplyT_F - incomingWater_T) \
               * self.defrostFactor)/(60/minuteIntervals))
            
        # aquire draw amount for time step
        last_temp = simRun.tmT_F[i-1]
        # if erCalc and simRun.tmT_F[i-1] < simRun.building.supplyT_F:  
        #     last_temp = simRun.building.supplyT_F
        simRun.hw_outSwing[i] = convertVolume(simRun.hwDemand[i], last_temp, incomingWater_T, simRun.building.supplyT_F)
        #Get the generation rate in storage temp
        mixedGHW = convertVolume(simRun.hwGenRate, self.storageT_F, incomingWater_T, simRun.building.supplyT_F)
        if simRun.hw_outSwing[i] > simRun.pV[i-1] + mixedGHW:
            hwVol_G = simRun.pV[i-1] + mixedGHW
            mixedT_F = getMixedTemp(incomingWater_T, self.storageT_F, simRun.hw_outSwing[i] - hwVol_G, hwVol_G)
            simRun.tmheating, simRun.tmT_F[i], simRun.tmRun[i] = self._runOneSwingStep(simRun.building, simRun.tmheating, last_temp, simRun.hw_outSwing[i], mixedT_F, minuteIntervals = minuteIntervals, erCalc=True)
        else:
            simRun.tmheating, simRun.tmT_F[i], simRun.tmRun[i] = self._runOneSwingStep(simRun.building, simRun.tmheating, last_temp, simRun.hw_outSwing[i], self.storageT_F, minuteIntervals = minuteIntervals, erCalc=True)

        simRun.pheating, simRun.pV[i], simRun.pGen[i], simRun.pRun[i] = self.runOnePrimaryStep(pheating = simRun.pheating,
                                                                                                Vcurr = simRun.pV[i-1], 
                                                                                                hw_out = simRun.hw_outSwing[i], 
                                                                                                hw_in = mixedGHW, 
                                                                                                mode = simRun.getLoadShiftMode(i),
                                                                                                modeChanged = (simRun.getLoadShiftMode(i) != simRun.getLoadShiftMode(i-1)),
                                                                                                minuteIntervals = minuteIntervals,
                                                                                                erCalc = True)
        if simRun.pV[i] < 0.:
            simRun.pV[i] = 0.