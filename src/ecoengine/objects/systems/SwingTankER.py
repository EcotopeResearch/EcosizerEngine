from ecoengine.objects.systems.SwingTank import SwingTank
from ecoengine.objects.SimulationRun import SimulationRun
import numpy as np
from ecoengine.objects.Building import Building
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import convertVolume, getMixedTemp, hrToMinList, getPeakIndices, checkHeatHours
from ecoengine.objects.PrefMapTracker import PrefMapTracker

class SwingTankER(SwingTank):

    def __init__(self, safetyTM, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building : Building,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, aquaFractLoadUp = None, 
                 aquaFractShed = None, loadUpT_F = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, PCap_kBTUhr = None, 
                 ignoreShortCycleEr = False, useHPWHsimPrefMap = False, TMVol_G = None, TMCap_kBTUhr = None, sizeAdditionalER = True, additionalERSaftey = 1.0):

        super().__init__(safetyTM, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building,
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, 
                 aquaFractShed, loadUpT_F, systemModel, numHeatPumps, PVol_G_atStorageT, PCap_kBTUhr, 
                 ignoreShortCycleEr, useHPWHsimPrefMap, TMVol_G, TMCap_kBTUhr)

        if sizeAdditionalER:
            self.setLoadUPVolumeAndTrigger(building.getDesignInlet())
            self.sizeERElement(building, additionalERSaftey)

    def sizeERElement(self, building : Building, saftey_factor = 1.0):
        if building is None:
            raise Exception("Cannot size additional swing tank electric resistance without building parameter.")
        elif self.perfMap is None:
            raise Exception("Performance map for system has not been set. Cannot size additional swing tank electric resistance.")
        
        # get base output capacity for primary HPWH using design climate temperatures
        self.perfMap.resetFlags()
        output_kBTUhr, input_kBTUhr = self.perfMap.getCapacity(building.getDesignOAT(), building.getDesignInlet() + 15.0, self.storageT_F) # Add 15 degrees to IWT as per swing tank norm 
        if sum(self.perfMap.getExtrapolationFlags()) > 0:
            # TODO If we need to deal with actual models with this later, we will need to determine what extrapolations will cause errors
            raise Exception("Design climate values (OAT, incoming water temperature) were outside of performance map for the CHPWH model chosen.")
        self.perfMap.resetFlags()

        # create a temporary performance map that will return ONLY that output capacity values for the sizing simulation
        perfMap_holder = self.perfMap # Store existing performance map in a temporary variable
        self.perfMap = PrefMapTracker(output_kBTUhr, usePkl=False, kBTUhr = True) # create simple performance map that only uses default output capacity
        self.setCapacity(self.perfMap.getDefaultCapacity())
        self.setLoadUPVolumeAndTrigger(building.getDesignInlet())

        # start the 72-hour sizing simulation to find HW deficit. Starting with the primary storage tank almost empty to ensure that water runs out if system is undersized.
        minuteIntervals = 1
        simRun = self.getInitializedSimulation(building, initPV = 0.1, initST=135, minuteIntervals = minuteIntervals, nDays = 3, forcePeakyLoadshape = True)
        i = 0
        normalFunction = True
        swingV = [0]*len(simRun.hwDemand)
        waterDeficit = [0]*len(simRun.hwDemand)
        while i < len(simRun.hwDemand):
            if normalFunction:
                i = self._findNextIndexOfHWDeficit(simRun, i)
                if i < len(simRun.hwDemand):
                    normalFunction = False
            else:
                # get available supply temperature volume in system to simulate as though water is completely stratified swing tank
                swingV[i-1] = convertVolume(self.TMVol_G, building.supplyT_F, building.getDesignInlet(), simRun.tmT_F[i-1]) + \
                    convertVolume(simRun.pV[i-1], building.supplyT_F, building.getDesignInlet(), self.storageT_F)
                # get full hwGeneration rate of swing tank plus hw coming in from primary system
                fullHWGenRate = (1000 * self.TMCap_kBTUhr / (60/minuteIntervals) /rhoCp / (building.supplyT_F - building.getDesignInlet()) * self.defrostFactor) + \
                    simRun.hwGenRate
                recircLossAtTime = (building.recirc_loss / (rhoCp * (building.supplyT_F - building.getDesignInlet()))) / (60/minuteIntervals)
                while i < len(simRun.hwDemand) and not normalFunction:
                    waterLeavingSystem = simRun.hwDemand[i] + recircLossAtTime
                    if convertVolume(simRun.hwGenRate, self.storageT_F, building.getDesignInlet(), building.supplyT_F) >= simRun.hwDemand[i]:
                        simRun.pV[i-1] = 0
                        if swingV[i-1] <= self.TMVol_G:
                            simRun.tmT_F[i-1] = building.supplyT_F
                        else:
                            simRun.tmT_F[i-1] =  ((swingV[i-1] * (building.supplyT_F - building.getDesignInlet()))/self.TMVol_G) + building.getDesignInlet()
                        normalFunction = True
                    else:
                        swingV[i] = swingV[i-1] + fullHWGenRate - waterLeavingSystem
                        waterDeficit[i] = max(waterLeavingSystem - fullHWGenRate, 0) # add water deficit if positive
                        i += 1
        # add additional ER to compensate for undersized CHPWH
        self.TMCap_kBTUhr += ((max(waterDeficit) * (60/minuteIntervals) * rhoCp * (building.supplyT_F - building.getDesignInlet())) / 1000.) * saftey_factor

        # set performance map back to its original form
        self.perfMap = perfMap_holder
        self.resetToDefaultCapacity()
        return

    def _findNextIndexOfHWDeficit(self, simRun : SimulationRun, i):
        incomingWater_T = simRun.building.getDesignInlet()
        while i < len(simRun.hwDemand):
            if simRun.pV[i-1] >= 0:
                # The following is esentially the normal swing tank runOneSystemStep() execpt uses design IWT instead of the climate-informed one
                # there is already no preSystemStepSetUp() because simulation is very basic
                simRun.hw_outSwing[i] = convertVolume(simRun.hwDemand[i], simRun.tmT_F[i-1], incomingWater_T, simRun.building.supplyT_F)    
                simRun.tmheating, simRun.tmT_F[i], simRun.tmRun[i] = self._runOneSwingStep(simRun.building, 
                    simRun.tmheating, simRun.tmT_F[i-1], simRun.hw_outSwing[i], self.storageT_F, minuteIntervals = simRun.minuteIntervals, erCalc = True)
                mixedGHW = convertVolume(simRun.hwGenRate, self.storageT_F, incomingWater_T, simRun.building.supplyT_F)
                simRun.pheating, simRun.pV[i], simRun.pGen[i], simRun.pRun[i] = self.runOnePrimaryStep(pheating = simRun.pheating,
                                                                                                        Vcurr = simRun.pV[i-1], 
                                                                                                        hw_out = simRun.hw_outSwing[i], 
                                                                                                        hw_in = mixedGHW, 
                                                                                                        mode = simRun.getLoadShiftMode(i),
                                                                                                        modeChanged = (simRun.getLoadShiftMode(i) != simRun.getLoadShiftMode(i-1)),
                                                                                                        minuteIntervals = simRun.minuteIntervals,
                                                                                                        erCalc = True)
            else:
                return i-1
            i += 1
        return i

    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None, erCalc=False):
        incomingWater_T = simRun.getIncomingWaterT(i)
        self.preSystemStepSetUp(simRun, i, incomingWater_T + 15.0, minuteIntervals, oat) # CHPWH IWT is assumed 15°F (adjustable) warmer than DCW temperature on average, based on lab test data. 

        # aquire draw amount for time step
        last_temp = simRun.tmT_F[i-1]
        simRun.hw_outSwing[i] = convertVolume(simRun.hwDemand[i], last_temp, incomingWater_T, simRun.building.supplyT_F)
        #Get the generation rate in storage temp
        mixedGHW = convertVolume(simRun.hwGenRate, self.storageT_F, incomingWater_T, simRun.building.supplyT_F)
        if simRun.hw_outSwing[i] > simRun.pV[i-1] + mixedGHW:
            hwVol_G = simRun.pV[i-1] + mixedGHW
            mixedT_F = getMixedTemp(incomingWater_T, self.storageT_F, simRun.hw_outSwing[i] - hwVol_G, hwVol_G)
            simRun.tmheating, simRun.tmT_F[i], simRun.tmRun[i] = self._runOneSwingStep(simRun.building, 
                simRun.tmheating, last_temp, simRun.hw_outSwing[i], mixedT_F, minuteIntervals = minuteIntervals)#, erCalc=True)
        else:
            simRun.tmheating, simRun.tmT_F[i], simRun.tmRun[i] = self._runOneSwingStep(simRun.building, 
                simRun.tmheating, last_temp, simRun.hw_outSwing[i], self.storageT_F, minuteIntervals = minuteIntervals)#, erCalc=True)

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