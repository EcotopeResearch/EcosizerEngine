from ecoengine.objects.SystemConfig import SystemConfig
from ecoengine.objects.SimulationRun import SimulationRun
from ecoengine.objects.PrefMapTracker import PrefMapTracker
import numpy as np
from ecoengine.objects.Building import Building
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import checkLiqudWater

class ParallelLoopTank(SystemConfig):
    def __init__(self, safetyTM, setpointTM_F, TMonTemp_F, offTime_hr, storageT_F, defrostFactor, percentUseable, compRuntime_hr,  onFract, offFract, onT, offT, building = None,
                 outletLoadUpT = None, onFractLoadUp = None, offFractLoadUp = None, onLoadUpT = None, offLoadUpT = None, onFractShed = None, offFractShed = None, onShedT = None, offShedT = None,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, systemModel = None, 
                 numHeatPumps = None, PVol_G_atStorageT = None, PCap_kBTUhr = None,
                 useHPWHsimPrefMap = False, TMVol_G = None, TMCap_kBTUhr = None, tmModel = None, tmNumHeatPumps = None):


        if TMonTemp_F == 0:
            TMonTemp_F = building.getAvgIncomingWaterT() + 2
            
        self._checkParallelLoopInputs(safetyTM, offTime_hr, setpointTM_F, TMonTemp_F)
        self.setpointTM_F = setpointTM_F
        self.TMonTemp_F = TMonTemp_F
        self.offTime_hr = offTime_hr # Hour
        self.safetyTM = safetyTM # Safety factor

        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                 outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT, 
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                 PCap_kBTUhr, useHPWHsimPrefMap)

        # size if needed, else all sizing is taken care of in super().__init__
        if not PVol_G_atStorageT is None: # indicates system is sized
           if not (isinstance(TMVol_G, int) or isinstance(TMVol_G, float)) or TMVol_G <= 0: 
                raise Exception('Invalid input given for Temperature Maintenance Storage Volume, it must be a number greater than zero.')
           if (tmModel is None or numHeatPumps is None) and (not (isinstance(TMCap_kBTUhr, int) or isinstance(TMCap_kBTUhr, float)) or TMCap_kBTUhr <= 0):
                raise Exception('Invalid input given for Temperature Maintenance Output Capacity, it must be a number greater than zero.')
           self.TMVol_G = TMVol_G
           self.TMCap_kBTUhr = TMCap_kBTUhr
        if self.TMCap_kBTUhr is None and isinstance(building, Building):
            self.TMCap_kBTUhr = self.safetyTM * building.recirc_loss / 1000
        # set performance map for tm tank
        if not tmModel is None and not tmModel[-2:] == 'MP':
            raise Exception("Parallel loop tank model must be a multipass system.")
        self.tmPerfMap = PrefMapTracker(self.TMCap_kBTUhr, modelName = tmModel, numHeatPumps = tmNumHeatPumps, kBTUhr = True, 
                                        usePkl=True if not (tmModel is None or useHPWHsimPrefMap) else False)

    def _checkParallelLoopInputs(self, safetyTM, offTime_hr, setpointTM_F, TMonTemp_F):
        # Quick Check to make sure the inputs make sense
        
        if not (isinstance(safetyTM, float) or isinstance(safetyTM, int)) or safetyTM <= 1.:
            raise Exception("The saftey factor for the temperature maintenance system must be greater than 1 or the system will never keep up with the losses.")
        if not (isinstance(offTime_hr, float) or isinstance(offTime_hr, int)) or offTime_hr > 1 or offTime_hr <= 0:
            raise Exception("The One Cycle Off Time the temperature maintenance system must be a float bigger than zero and less than or equal to one hour.")
        if tmCompMinimumRunTime >= offTime_hr/(safetyTM - 1.):
            raise Exception("The expected run time of the parallel tank is less time the minimum runtime for a HPWH of " + str(tmCompMinimumRunTime*60)+ " minutes.")
        if not (isinstance(setpointTM_F, int) or isinstance(setpointTM_F, float)) or not checkLiqudWater(setpointTM_F):
            raise Exception('Invalid input given for setpointTM_F, it must be between 32 and 212F.')
        if not (isinstance(TMonTemp_F, int) or isinstance(TMonTemp_F, float)) or not checkLiqudWater(TMonTemp_F): #TODO confirm both ints and floats work
            raise Exception('Invalid input given for TMonTemp_F, it must be between 32 and 212F.')
        if setpointTM_F <= TMonTemp_F:
            raise Exception("The temperature maintenance setpoint temperature must be greater than the turn on temperature")
        
    def getDesignIncomingTemp(self, building: Building):
        return building.getHighestIncomingT_F() + 15.0

    def sizeSystem(self, building):
        """
        Resizes the system with a new building.
        Also used for resizing the system after it has changed its loadshift settings using the original building the system was sized for

        Parameters
        ----------
        building : Building
            The building to size with
        """
        super().sizeSystem(building)
        if self.setpointTM_F <= building.getHighestIncomingT_F():
            raise Exception("The temperature maintenance setpoint temperature must be greater than the city cold water temperature")
        if self.TMonTemp_F <= building.getHighestIncomingT_F():
            raise Exception("The temperature maintenance on temperature must be greater than the city cold water temperature")
        self.TMVol_G  =  (building.recirc_loss / rhoCp) * (self.offTime_hr / (self.setpointTM_F - self.TMonTemp_F))
        self.TMCap_kBTUhr = self.safetyTM * building.recirc_loss / 1000

    def getSizingResults(self):
        """
        Returns the minimum primary volume and heating capacity sizing results

        Returns
        -------
        list
            self.PVol_G_atStorageT, self.PCap_kBTUhr, self.TMVol_G, self.TMCap_kBTUhr
        """
        return [self.PVol_G_atStorageT, self.PCap_kBTUhr, self.TMVol_G, self.TMCap_kBTUhr]
    
    def preSystemStepSetUp(self, simRun : SimulationRun, i, incomingWater_T, minuteIntervals, oat):
        """
        helper function for runOneSystemStep
        """
        if not (oat is None or self.perfMap is None):
            if i%(60/minuteIntervals) == 0: # we have reached the next hour and should thus be at the next OAT
                # set primary system capacity based on outdoor air temp and incoming water temp 
                self.setCapacity(oat = oat, incomingWater_T = incomingWater_T + 15.0, useLoadUpTemp= simRun.getLoadShiftMode(i) == 'L') # CHPWH IWT is assumed 15°F (adjustable) warmer than DCW temperature on average, based on lab test data.
                if simRun.passedCOPAssumptionThreshold(self.perfMap.timesAssumedCOP*(60/minuteIntervals)):
                    raise Exception("Could not run simulation because internal performance map for the primary model does not account for the climate zone of the input zip code. Please try with a different primary model or zip code.")
                hw_gen_for_interval = (1000 * self.PCap_kBTUhr / rhoCp / (simRun.building.supplyT_F - simRun.getIncomingWaterT(i)) * self.defrostFactor)/(60/minuteIntervals)
                for j in range(60//minuteIntervals):
                    simRun.addHWGen(hw_gen_for_interval)
    
    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None):
        super().runOneSystemStep(simRun, i, minuteIntervals, oat)

        if not (oat is None or self.tmPerfMap is None):
            # set temperature maintenance capacity based on outdoor air temp and recirc water temp 
            self.setTMCapacity(oat = oat, incomingWater_T = (self.setpointTM_F + self.TMonTemp_F)/2.0)
            if simRun.passedCOPAssumptionThreshold(self.tmPerfMap.timesAssumedCOP):
                raise Exception("Could not run simulation because internal performance map for the temperature maintenance model does not account for the climate zone of the input zip code. Please try with a different temperature maintenance model or zip code.")

        timeDivisor = 60 // minuteIntervals
        time_running = 0

        # Take out the recirc losses from TM temperature
        Tnew = simRun.tmT_F[i-1] - simRun.building.recirc_loss / timeDivisor / rhoCp / self.TMVol_G
        element_dT = self.TMCap_kBTUhr * 1000  / timeDivisor / rhoCp / self.TMVol_G
        
        # Check if the element is heating
        if simRun.tmheating:
            Tnew += element_dT # if heating, generate HW
            time_running = 1

            # Check if the element should turn off
            if Tnew > self.setpointTM_F:
                time_over = (Tnew - self.setpointTM_F) / element_dT # Temp below turn on / rate of element heating gives time above trigger
                Tnew -= element_dT * time_over # Make full with miss volume
                time_running = (1-time_over)
                simRun.tmheating = False
        elif Tnew <= self.TMonTemp_F: # If the element should turn on
            time_running = (self.TMonTemp_F - Tnew)/element_dT # Temp below turn on / rate of element heating gives time below tigger
            Tnew += element_dT * time_running # Start heating 
            simRun.tmheating = True # Start heating
        
        # multiply did_run to reflect the time durration of the interval.
        simRun.tmRun[i] = time_running * minuteIntervals
        simRun.tmT_F[i] = Tnew

    def getInitializedSimulation(self, building : Building, initPV=None, initST=None, minuteIntervals = 1, nDays = 3, forcePeakyLoadshape = False) -> SimulationRun:
        simRun = super().getInitializedSimulation(building, initPV, initST, minuteIntervals, nDays, forcePeakyLoadshape)
        simRun.initializeTMValue(self.setpointTM_F, self.storageT_F, self.TMCap_kBTUhr, swingOut = False)
        return simRun
    
    def resetToDefaultCapacity(self):
        self.TMCap_kBTUhr = self.tmPerfMap.getDefaultCapacity()
        super().resetToDefaultCapacity()
    
    def tmReliedOnEr(self):
        return self.tmPerfMap.didRelyOnEr()
    
    def setTMCapacity(self, TMCap_kBTUhr = None, oat = None, incomingWater_T = None):
        if not TMCap_kBTUhr is None:
            self.TMCap_kBTUhr = TMCap_kBTUhr
            self.TMCap_input_kBTUhr = self.TMCap_kBTUhr / 2.5 # Assume COP of 2.5
        elif not (oat is None or incomingWater_T is None or self.tmPerfMap is None):
            self.TMCap_kBTUhr, self.TMCap_input_kBTUhr = self.tmPerfMap.getCapacity(oat, incomingWater_T, self.storageT_F, fallbackCapacity_kW = self.getTMOutputCapacity(kW = True))
        else:
           raise Exception("No capacity given or preformance map has not been set.")
        
    def getTMOutputCapacity(self, kW = False):
        if self.TMCap_kBTUhr is None:
            return None
        if kW:
            return self.TMCap_kBTUhr/W_TO_BTUHR
        return self.TMCap_kBTUhr
    
    def getTMInputCapacity(self, kW = False):
        if hasattr(self, 'TMCap_input_kBTUhr'):
            if kW:
                return self.TMCap_input_kBTUhr / W_TO_BTUHR
            return self.TMCap_input_kBTUhr
        
        # else assume COP of 2.5
        if kW:
            return (self.TMCap_kBTUhr / 2.5) / W_TO_BTUHR
        return self.TMCap_kBTUhr / 2.5