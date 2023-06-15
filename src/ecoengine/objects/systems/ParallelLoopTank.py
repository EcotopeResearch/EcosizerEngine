from ecoengine.objects.SystemConfig import SystemConfig
import numpy as np
from ecoengine.objects.Building import Building
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import checkLiqudWater

class ParallelLoopTank(SystemConfig):
    def __init__(self, safetyTM, setpointTM_F, TMonTemp_F, offTime_hr, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building = None,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, aquaFractLoadUp = None, aquaFractShed = None, 
                 loadUpT_F = None, systemModel = None, PVol_G_atStorageT = None, PCap_kBTUhr = None, TMVol_G = None, TMCap_kBTUhr = None):


        if TMonTemp_F == 0:
            TMonTemp_F = building.incomingT_F + 2 # TODO deal with this
        
        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building,
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, aquaFractShed, 
                 loadUpT_F, systemModel, PVol_G_atStorageT, PCap_kBTUhr)
        
        self._checkParallelLoopInputs(safetyTM, offTime_hr, setpointTM_F, TMonTemp_F)
        self.setpointTM_F = setpointTM_F
        self.TMonTemp_F = TMonTemp_F
        self.offTime_hr = offTime_hr # Hour
        self.safetyTM = safetyTM # Safety factor

        # size if needed
        if not PVol_G_atStorageT is None: # indicates system is sized
           if not (isinstance(TMVol_G, int) or isinstance(TMVol_G, float)) or TMVol_G <= 0: 
                raise Exception('Invalid input given for Temperature Maintenance Storage Volume, it must be a number greater than zero.')
           if not (isinstance(TMCap_kBTUhr, int) or isinstance(TMCap_kBTUhr, float)) or TMCap_kBTUhr <= 0: 
                raise Exception('Invalid input given for Temperature Maintenance Output Capacity, it must be a number greater than zero.')
           self.TMVol_G = TMVol_G
           self.TMCap_kBTUhr = TMCap_kBTUhr
        else:
            if setpointTM_F <= building.incomingT_F:
                raise Exception("The temperature maintenance setpoint temperature must be greater than the city cold water temperature")
            if TMonTemp_F <= building.incomingT_F:
                raise Exception("The temperature maintenance on temperature must be greater than the city cold water temperature")
            self.TMVol_G  =  (building.recirc_loss / rhoCp) * (self.offTime_hr / (self.setpointTM_F - self.TMonTemp_F))
            self.TMCap_kBTUhr = self.safetyTM * building.recirc_loss / 1000

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

    def getSizingResults(self):
        """
        Returns the minimum primary volume and heating capacity sizing results

        Returns
        -------
        list
            self.PVol_G_atStorageT, self.PCap_kBTUhr, self.TMVol_G, self.TMCap_kBTUhr
        """
        return [self.PVol_G_atStorageT, self.PCap_kBTUhr, self.TMVol_G, self.TMCap_kBTUhr]