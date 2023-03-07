from abc import ABC, abstractmethod
from constants.Constants import *
from objects.Building import Building
# Functions to gather data from JSON
import os
import json
import numpy as np
from scipy.stats import norm #lognorm

class SystemConfig(ABC):
    def __init__(self, building, inputs):
        # check inputs
        if not hasattr(inputs, 'storageT_F'):
            raise Exception("storageT_F required.")
        if not hasattr(inputs, 'defrostFactor'):
            raise Exception("defrostFactor required.")
        if not hasattr(inputs, 'percentUseable'):
            raise Exception("percentUseable required.")
        if not hasattr(inputs, 'compRuntime_hr'):
            raise Exception("compRuntime_hr required.")
        if not hasattr(inputs, 'aquaFract'):
            raise Exception("aquaFract required.")
        
        self.doLoadShift = False # do we need this? TODO
        if(isinstance(building, Building)):
            self.building = building
        else:
            raise Exception("Error: Building is not valid.")
        
        self.totalHWLoad = self.building.magnitude
        self.storageT_F = inputs.storageT_F
        self.defrostFactor = inputs.defrostFactor
        self.percentUseable = inputs.percentUseable
        self.compRuntime_hr = inputs.compRuntime_hr
        self.aquaFract = inputs.aquaFract

        if hasattr(inputs, 'doLoadShift') and inputs.doLoadShift:
            cdf_shift = 1
            if hasattr(inputs, 'cdf_shift'):
                cdf_shift = inputs.cdf_shift
            if hasattr(inputs, 'schedule'):
                self.setLoadShift(inputs.schedule, cdf_shift)
        else:
            self.schedule = [1] * 24

        #Check if need to increase sizing to meet lower runtimes for load shift
        self.maxDayRun_hr = min(self.compRuntime_hr, sum(self.schedule))

        #size system
        print("hello hello ---->", self.maxDayRun_hr)
        self.PVol_G_atStorageT, self.effSwingFract, self.LSconstrained = self.sizePrimaryTankVolume(self.maxDayRun_hr)
        print("effSwingFract ---->", self.effSwingFract)
        # print("fract_total_vol ---->", self.fract_total_vol)
        print("self.doLoadShift",self.doLoadShift)
        print("totalHWLoad ---->", self.totalHWLoad)
        self.PCap_kBTUhr = self.primaryHeatHrs2kBTUHR(self.maxDayRun_hr, self.effSwingFract )


    # @abstractmethod
    def simulate(self):
        pass

    def HRLIST_to_MINLIST(self, a_list):
        """
        TODO get description for this

        """
        out_list = []
        for num in a_list:
            out_list += [num]*60
        return out_list
    
    def setLoadShift(self, schedule, cdf_shift=1):
        """
        Sets the load shifting schedule from input schedule

        Parameters
        ----------
        schedule : array_like
            List or array of 0's and 1's for don't run and run.

        cdf_shift : float
            Percentile of days which need to be covered by load shifting

        """
        # Check
        if len(schedule) != 24 : #TODO ensure schedule is valid and add load up
            raise Exception("loadshift is not of length 24 but instead has length of "+str(len(schedule))+".")
        if sum(schedule) == 0 :
            raise Exception("When using Load shift the HPWH's must run for at least 1 hour each day.")
        if cdf_shift < 0.25 :
            raise Exception("Load shift only available for above 25 percent of days.")
        if cdf_shift > 1 :
            raise Exception("Cannot load shift for more than 100 percent of days")

        self.schedule = schedule
        self.loadshift = np.array(schedule, dtype = float)# Coerce to numpy array of data type float

        # adjust for cdf_shift
        if cdf_shift == 1: # meaing 100% of days covered by load shift
            self.fract_total_vol = 1
        else:
            # calculate fraction totalHWLoad of required to meet load shift days
            fract = norm_mean + norm_std * norm.ppf(cdf_shift) #TODO norm_mean and std are currently from multi-family, need other types
            self.fract_total_vol = fract if fract <= 1. else 1.
        
        self.doLoadShift = True # TODO necessary?

    def _checkHeatHours(self, heathours):
        """
        Quick check to see if heating hours is a valid number between 1 and 24

        Parameters
        ----------
        heathours (float or numpy.ndarray)
            The number of hours primary heating equipment can run.
        """
        if isinstance(heathours, np.ndarray):
            if any(heathours > 24) or any(heathours <= 0):
                raise Exception("Heat hours is not within 1 - 24 hours")
        else:
            if heathours > 24 or heathours <= 0:
                raise Exception("Heat hours is not within 1 - 24 hours")

    def primaryHeatHrs2kBTUHR(self, heathours, effSwingVolFract=1):
        """
        Converts from hours of heating in a day to heating capacity.

        Parameters
        ----------
        heathours : float or numpy.ndarray
            The number of hours primary heating equipment can run.

        effSwingVolFract : float or numpy.ndarray
            The fractional adjustment to the total hot water load for the
            primary system. Only used in a swing tank system.

        Returns
        -------
        heatCap
            The heating capacity in [btu/hr].
        """
        self._checkHeatHours(heathours)
        heatCap = self.totalHWLoad / heathours * rhoCp * \
            (self.building.supplyT_F - self.building.incomingT_F) / self.defrostFactor /1000.
        return heatCap

    def getPeakIndices(self, diff1):
        """
        Finds the points of an array where the values go from positive to negative

        Parameters
        ----------
        diff1 : array_like
            A 1 dimensional array.

        Returns
        -------
        ndarray
            Array of indices in which input array changes from positive to negative
        """
        if not isinstance(diff1, np.ndarray):
            diff1 = np.array(diff1)
        diff1 = np.insert(diff1, 0, 0)
        diff1[diff1==0] = .0001 #Got to catch this error in the algorithm. Damn 0s.
        return np.where(np.diff(np.sign(diff1))<0)[0]
    
    def mixVolume(self, vol, hotT, coldT, outT):
        """
        Adjusts the volume of water such that the hotT water and outT water have the
        same amount of energy, meaning different volumes.

        Parameters
        ----------
        vol : float
            The reference volume to convert.
        hotT : float
            The hot water temperature used for mixing.
        coldT : float
            The cold water tempeature used for mixing.
        outT : float
            The out water temperature from mixing.

        Returns
        -------
        float
            Temperature adjusted volume.

        """
        fraction = (outT - coldT) / (hotT - coldT)

        return vol * fraction
    
    def sizePrimaryTankVolume(self, heatHrs):
        """
        Calculates the primary storage using the Ecotope sizing methodology

        Parameters
        ----------
        heatHrs : float
            The number of hours primary heating equipment can run in a day.

        Returns
        -------
        totalVolMax : float
            The total storage volume in gallons adjusted to the storage tempreature
        """
        if heatHrs <= 0 or heatHrs > 24:
            raise Exception("Heat hours is not within 1 - 24 hours")
        # Fraction used for adjusting swing tank volume.
        effMixFract = 1.
        # If the system is sized for load shift days or the load shift
        # requirement is less than required
        largerLS = False

        # Running vol
        runningVol_G, effMixFract = self.calcRunningVol(heatHrs, np.ones(24))
        print("ok now effMixFract", effMixFract)

        # If doing load shift, solve for the runningVol_G and take the larger volume
        if self.doLoadShift:
            LSrunningVol_G = 0
            LSeffMixFract = 0
            LSrunningVol_G = self.calcRunningVol(heatHrs, self.schedule) # original used avg loadshape? TODO ?
            LSrunningVol_G *= self.fract_total_vol

            # Get total volume from max of primary method or load shift method
            if LSrunningVol_G > runningVol_G:
                runningVol_G = LSrunningVol_G
                effMixFract = LSeffMixFract
                largerLS = True

        print("runningVol_G !!!!!! ", runningVol_G)
        print("self.aquaFract !!!!!! ", self.aquaFract)
        totalVolMax = self.getTotalVolMax(runningVol_G) / (1-self.aquaFract)

        # Check the Cycling Volume ############################################
        cyclingVol_G = totalVolMax * (self.aquaFract - (1 - self.percentUseable))
        minRunVol_G = pCompMinimumRunTime * (self.totalHWLoad * effMixFract / heatHrs) # (generation rate - no usage)

        if minRunVol_G > cyclingVol_G:
            min_AF = minRunVol_G / totalVolMax + (1 - self.percentUseable)
            if min_AF < 1:
                raise ValueError("01", "The aquastat fraction is too low in the storge system recommend increasing the maximum run hours in the day or increasing to a minimum of: ", round(min_AF,3))
            raise ValueError("02", "The minimum aquastat fraction is greater than 1. This is due to the storage efficency and/or the maximum run hours in the day may be too low. Try increasing these values, we reccomend 0.8 and 16 hours for these variables respectively." )

        # Return the temperature adjusted total volume ########################
        return totalVolMax, effMixFract, largerLS
    
    # @abstractmethod
    def calcRunningVol(self, heatHrs, onOffArr):
        print("hopefully should not be printing this")
        return 0, 1
    
    def getTotalVolMax(self, runningVol_G):
        return self.mixVolume(runningVol_G, self.storageT_F, self.building.incomingT_F, self.building.supplyT_F) / (1-self.aquaFract)

class ParallelLoopTank(SystemConfig):
    def __init__(self, building, inputs):
        # error handle
        if not hasattr(inputs, 'safetyTM'):
            raise Exception("safetyTM required")
        if not hasattr(inputs, 'setpointTM_F'):
            raise Exception("setpointTM_F required")
        if not hasattr(inputs, 'TMonTemp_F'):
            raise Exception("TMonTemp_F required")
        if not hasattr(inputs, 'offTime_hr'):
            raise Exception("offTime_hr required")
        
        # Quick Check the inputs makes sense
        if inputs.safetyTM <= 1.:
            raise Exception("The saftey factor for the temperature maintenance system must be greater than 1 or the system will never keep up with the losses.")
        if any(x==0 for x in [inputs.setpointTM_F, inputs.TMonTemp_F]):
            raise Exception("Error in initTempMaintInputs, paralleltank needs inputs != 0")
        if tmCompMinimumRunTime >= inputs.offTime_hr/(inputs.safetyTM - 1):
            raise Exception("The expected run time of the parallel tank is less time the minimum runtime for a HPWH of " + str(tmCompMinimumRunTime*60)+ " minutes.")
        if not self.checkLiqudWater(inputs.setpointTM_F):
            raise Exception('Invalid input given for setpointTM_F, it must be between 32 and 212F.\n')
        if not self.checkLiqudWater(inputs.TMonTemp_F):
            raise Exception('Invalid input given for TMonTemp_F, it must be between 32 and 212F.\n')
        if inputs.setpointTM_F <= inputs.TMonTemp_F:
            raise Exception("The temperature maintenance setpoint temperature must be greater than the turn on temperature")
        if inputs.setpointTM_F <= building.incomingT_F:
            raise Exception("The temperature maintenance setpoint temperature must be greater than the city cold water temperature ")
        if inputs.TMonTemp_F <= building.incomingT_F:
            raise Exception("The temperature maintenance turn on temperature must be greater than the city cold water temperature ")
        
        super().__init__(building, inputs)
        self.setpointTM_F = inputs.setpointTM_F
        self.TMonTemp_F = inputs.TMonTemp_F
        self.offTime_hr = inputs.offTime_hr # Hour
        self.safetyTM = inputs.safetyTM # Safety factor

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
    
class Primary(SystemConfig):
    def __init__(self, building, inputs):
        super().__init__(building, inputs)
    
    def simulate(self):
        return super().simulate()

