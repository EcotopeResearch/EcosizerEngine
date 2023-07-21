from ecoengine.objects.SystemConfig import SystemConfig
from ecoengine.objects.SimulationRun import SimulationRun
from ecoengine.objects.PrefMapTracker import PrefMapTracker
import numpy as np
from ecoengine.objects.Building import Building
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import checkLiqudWater

class ParallelLoopTank(SystemConfig):
    def __init__(self, safetyTM, setpointTM_F, TMonTemp_F, offTime_hr, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building = None,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, aquaFractLoadUp = None, aquaFractShed = None, 
                 loadUpT_F = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, PCap_kBTUhr = None, TMVol_G = None, TMCap_kBTUhr = None,
                 tmModel = None, tmNumHeatPumps = None):

        if TMonTemp_F == 0:
            TMonTemp_F = building.incomingT_F + 2 # TODO deal with this
            
        self._checkParallelLoopInputs(safetyTM, offTime_hr, setpointTM_F, TMonTemp_F)
        self.setpointTM_F = setpointTM_F
        self.TMonTemp_F = TMonTemp_F
        self.offTime_hr = offTime_hr # Hour
        self.safetyTM = safetyTM # Safety factor

        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building,
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, aquaFractShed, 
                 loadUpT_F, systemModel, numHeatPumps, PVol_G_atStorageT, PCap_kBTUhr)

        # size if needed, else all sizing is taken care of in super().__init__
        if not PVol_G_atStorageT is None: # indicates system is sized
           if not (isinstance(TMVol_G, int) or isinstance(TMVol_G, float)) or TMVol_G <= 0: 
                raise Exception('Invalid input given for Temperature Maintenance Storage Volume, it must be a number greater than zero.')
           if not (isinstance(TMCap_kBTUhr, int) or isinstance(TMCap_kBTUhr, float)) or TMCap_kBTUhr <= 0: 
                raise Exception('Invalid input given for Temperature Maintenance Output Capacity, it must be a number greater than zero.')
           self.TMVol_G = TMVol_G
           self.TMCap_kBTUhr = TMCap_kBTUhr

        # set performance map for tm tank
        self.tmPerfMap = PrefMapTracker(self.TMCap_kBTUhr, modelName = tmModel, numHeatPumps = tmNumHeatPumps, kBTUhr = True)

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
        if self.setpointTM_F <= building.incomingT_F:
            raise Exception("The temperature maintenance setpoint temperature must be greater than the city cold water temperature")
        if self.TMonTemp_F <= building.incomingT_F:
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
    
    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None):
        super().runOneSystemStep(simRun, i, minuteIntervals, oat)

        if not (oat is None or self.tmPerfMap is None):
            # set temperature maintenence capacity based on outdoor air temp and recirc water temp 
            self.setTMCapacity(oat = oat, incomingWater_T = (self.setpointTM_F + self.TMonTemp_F)/2.0)

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

    def getInitializedSimulation(self, building : Building, initPV=None, initST=None, minuteIntervals = 1, nDays = 3):
        simRun = super().getInitializedSimulation(building, initPV, initST, minuteIntervals, nDays)
        simRun.initializeTMValue(self.setpointTM_F, self.storageT_F, self.TMCap_kBTUhr, swingOut = False)
        return simRun
    
    def setTMCapacity(self, TMCap_kBTUhr = None, oat = None, incomingWater_T = None):
        if not TMCap_kBTUhr is None:
            self.TMCap_kBTUhr = TMCap_kBTUhr
            self.TMCap_input_kBTUhr = self.TMCap_kBTUhr / 2.5 # Assume COP of 2.5
        elif not (oat is None or incomingWater_T is None or self.tmPerfMap is None):
            self.TMCap_kBTUhr, self.TMCap_input_kBTUhr = self.tmPerfMap.getCapacity(oat, incomingWater_T, self.storageT_F)
        else:
           raise Exception("No capacity given or preformance map has not been set.")
        
    def getTMOutputCapacity(self, kW = False):
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