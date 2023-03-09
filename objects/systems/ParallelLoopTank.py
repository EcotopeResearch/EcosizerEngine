from objects.SystemConfig import SystemConfig
import numpy as np
from objects.Building import Building
from constants.Constants import *

class ParallelLoopTank(SystemConfig):
    def __init__(self, safetyTM, setpointTM_F, TMonTemp_F, offTime_hr, building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, 
                 doLoadShift = False, cdf_shift = 1, schedule = None):
        # error handle
        # if not hasattr(inputs, 'safetyTM'):
        #     raise Exception("safetyTM required")
        # if not hasattr(inputs, 'setpointTM_F'):
        #     raise Exception("setpointTM_F required")
        # if not hasattr(inputs, 'TMonTemp_F'):
        #     raise Exception("TMonTemp_F required")
        # if not hasattr(inputs, 'offTime_hr'):
        #     raise Exception("offTime_hr required")
        
        # Quick Check the inputs makes sense
        if safetyTM <= 1.:
            raise Exception("The saftey factor for the temperature maintenance system must be greater than 1 or the system will never keep up with the losses.")
        if any(x==0 for x in [setpointTM_F, TMonTemp_F]):
            raise Exception("Error in initTempMaintInputs, paralleltank needs inputs != 0")
        if tmCompMinimumRunTime >= offTime_hr/(safetyTM - 1):
            raise Exception("The expected run time of the parallel tank is less time the minimum runtime for a HPWH of " + str(tmCompMinimumRunTime*60)+ " minutes.")
        if not self.checkLiqudWater(setpointTM_F):
            raise Exception('Invalid input given for setpointTM_F, it must be between 32 and 212F.\n')
        if not self.checkLiqudWater(TMonTemp_F):
            raise Exception('Invalid input given for TMonTemp_F, it must be between 32 and 212F.\n')
        if setpointTM_F <= TMonTemp_F:
            raise Exception("The temperature maintenance setpoint temperature must be greater than the turn on temperature")
        if setpointTM_F <= building.incomingT_F:
            raise Exception("The temperature maintenance setpoint temperature must be greater than the city cold water temperature ")
        if TMonTemp_F <= building.incomingT_F:
            raise Exception("The temperature maintenance turn on temperature must be greater than the city cold water temperature ")
        
        super().__init__(building, building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, 
                 doLoadShift, cdf_shift, schedule)
        self.setpointTM_F = setpointTM_F
        self.TMonTemp_F = TMonTemp_F
        self.offTime_hr = offTime_hr # Hour
        self.safetyTM = safetyTM # Safety factor

        self.TMVol_G  =  self.building.recirc_loss / rhoCp * self.offTime_hr / (self.setpointTM_F - self.TMonTemp_F)
        self.TMCap_kBTUhr = self.safetyTM * self.building.recirc_loss / 1000
    
    def checkLiqudWater(var_F):
        """
        Checks if the variable has a temperuter with in the range of liquid water at atm pressure

        Args:
            var_F (float): Temperature of water.

        Returns:
            bool: True if liquid, False if solid or gas.

        """
        if var_F < 32. or var_F > 212.:
            return False
        return True

    def simulate(self):
        print(self.TMonTemp_F)
        print(self.TMVol_G)