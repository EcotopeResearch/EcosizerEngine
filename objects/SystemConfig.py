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
        self.PVol_G_atStorageT, self.effSwingFract, self.LSconstrained = self.sizePrimaryTankVolume(self.maxDayRun_hr)
        self.PCap_kBTUhr = self.primaryHeatHrs2kBTUHR(self.maxDayRun_hr, self.effSwingFract )


    # @abstractmethod
    def simulate(self):
        pass

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

class SwingTank(SystemConfig):

    Table_Napts = [0, 12, 24, 48, 96]
    sizingTable_EMASHRAE = ["80", "80", "80", "120 - 300", "120 - 300"]
    sizingTable_CA = ["80", "96", "168", "288", "480"]

    def __init__(self, building, inputs, CA = False):
        if not hasattr(inputs, 'safetyTM'):
            raise Exception("safetyTM required")
        if inputs.safetyTM <= 1.:
            raise Exception("The saftey factor for the temperature maintenance system must be greater than 1 or the system will never keep up with the losses.")
        self.safetyTM = inputs.safetyTM
        self.TMVol_G = 120 # TODO Scott to figure out table stuff for self.TMVol_G use 120 for now
        self.swingheating = False
        self.element_deadband_F = 8.
        self.TMCap_kBTUhr = self.safetyTM * building.recirc_loss / 1000.
        super().__init__(building, inputs)

    def simulate(self):
        print("Heating capacity (PCap_kBTUhr)", self.PCap_kBTUhr)
        print("Swing Tank Volume (TMVol_G)", self.TMVol_G)
        print("Tank Volume (PVol_G_atStorageT)",self.PVol_G_atStorageT)
        print("Swing Resistance Element (TMCap_kBTUhr)", self.TMCap_kBTUhr)
    
    def calcRunningVol(self, heatHrs, onOffArr):
        """
        Function to find the running volume for the hot water storage tank, which
        is needed for calculating the total volume for primary sizing and in the event of load shift sizing
        represents the entire volume.

        Parameters
        ----------
        heatHrs : float
            The number of hours primary heating equipment can run in a day.
        onOffArr : ndarray
            array of 1/0's where 1's allow heat pump to run and 0's dissallow. of length 24.

        Raises
        ------
        Exception: Error if oversizeing system.

        Returns
        -------
        runV_G : float
            The running volume in gallons

        """
        print("hi I am here")

        genrate = np.tile(onOffArr,2) / heatHrs #hourly
        diffN   = genrate - np.tile(self.building.loadshape, 2) #hourly
        diffInd = self.getPeakIndices(diffN[0:24]) #Days repeat so just get first day!
                
        # Get the running volume ##############################################
        if len(diffInd) == 0:
            raise Exception("ERROR ID 03","The heating rate is greater than the peak volume the system is oversized! Try increasing the hours the heat pump runs in a day",)

        # Watch out for cases where the heating is to close to the initial peak value so also check the hour afterwards too.
        nRealpeaks = len(diffInd)
        diffInd = np.append(diffInd, diffInd+1)
        diffInd = diffInd[diffInd < 24]
        runV_G = 0
        for peakInd in diffInd:
            hw_out = np.tile(self.building.loadshape, 2)
            hw_out = np.array([x * 60 for x in (hw_out[peakInd:peakInd+24])]) \
                / 60 * self.totalHWLoad # to minute

            # Simulate the swing tank assuming it hits the peak just above the supply temperature.
            # Get the volume removed for the primary adjusted by the swing tank
            N = len(hw_out)
            [_, _, hw_out_from_swing] = self.simJustSwing(N, hw_out, self.building.supplyT_F + 0.1)

            # Get the effective adjusted hot water demand on the primary system at the storage temperature.
            temp_eff_HW_mix_faction = sum(hw_out_from_swing)/self.totalHWLoad #/2 because the sim goes for two days
            genrate_min = np.array([x * 60 for x in (genrate[peakInd:peakInd+24])]) \
                / 60 * self.totalHWLoad * temp_eff_HW_mix_faction # to minute

            # Get the new difference in generation and demand
            diffN = genrate_min - hw_out_from_swing
            # Get the rest of the day from the start of the peak
            diffCum = np.cumsum(diffN)

            # Check if additional cases saftey checks have oversized the system.
            if(np.where(diffInd == peakInd)[0][0] >= nRealpeaks):
                if not any(diffCum < 0.):
                    continue

            new_runV_G = -min(diffCum[diffCum<0.])
            
            if runV_G < new_runV_G:
                runV_G = new_runV_G #Minimum value less than 0 or 0.
                eff_HW_mix_faction = temp_eff_HW_mix_faction

        return runV_G, eff_HW_mix_faction
    
    def simJustSwing(self, N, hw_out, initST=None):
        """
        Inputs
        ------

        initST : float
            Primary Swing tank at start of sim
        """
        swingT = [self.building.supplyT_F] + [0] * (N - 1)
        D_hw = hw_out

        if initST:
            swingT[0] = initST
        # Run the "simulation"

        hw_outSwing = [0] * N
        srun = [0] * N

        for ii in range(1, N):

            hw_outSwing[ii] = self.mixVolume(D_hw[ii], swingT[ii-1], self.building.incomingT_F, self.building.supplyT_F)
            swingT[ii], srun[ii] = self.runOneSwingStep(swingT[ii-1], hw_outSwing[ii])

        return [swingT, srun, hw_outSwing]
    
    def runOneSwingStep(self, Tcurr, hw_out):
        """
        Runs one step on the swing tank step. Since the swing tank is in series
        with the primary system the temperature needs to be tracked to inform
        inputs for primary step. The driving assumptions hereare that the swing
        tank is well mixed and can be tracked by the average tank temperature
        and that the system loses the recirculation loop losses as a constant
        Watts and thus the actual flow rate and return temperature from the
        loop are irrelevant.

        Parameters
        ----------
        Tcurr : float
            The current temperature at the timestep.
        hw_out : float
            The volume of DHW removed from the swing tank system.
        hw_in : float
            The volume of DHW added to the system.

        Returns
        -------
        Tnew : float
            The new swing tank tempeature the timestep assuming the tank is well mixed.
        did_run : int
            Logic if heated during time step (1) or not (0)

        """
        did_run = 0

        # Take out the recirc losses
        Tnew = Tcurr - self.building.recirc_loss / 60 / rhoCp / self.TMVol_G
        element_dT = self.TMCap_kBTUhr * 1000  / 60 / rhoCp / self.TMVol_G

        # Add in heat for a draw
        if hw_out:
            Tnew += hw_out * (self.storageT_F - Tcurr) / self.TMVol_G

        # Check if the element is heating
        if self.swingheating:
            Tnew += element_dT #If heating, generate HW and lose HW
            did_run = 1

            # Check if the element should turn off
            if Tnew > self.building.supplyT_F + self.element_deadband_F: # If too hot
                time_over = (Tnew - (self.building.supplyT_F + self.element_deadband_F)) / element_dT # Temp below turn on / rate of element heating gives time above trigger plus deadband
                Tnew -= element_dT * time_over # Make full with miss volume
                did_run = (1-time_over)

                self.swingheating = False
        else:
            if Tnew <= self.building.supplyT_F: # If the element should turn on
                time_missed = (self.building.supplyT_F - Tnew)/element_dT # Temp below turn on / rate of element heating gives time below tigger
                Tnew += element_dT * time_missed # Start heating

                did_run = time_missed
                self.swingheating = True # Start heating

        if Tnew < self.building.supplyT_F: # Check for errors
            raise Exception("The swing tank dropped below the supply temperature! The system is undersized")

        #print(Tnew, Tcurr, self.swing_Ttrig, self.swingheating, did_run )

        return Tnew, did_run
    
    def getSizingTable(self, CA=True): #TODO do we need this?
        """
        Returns sizing table for a swing tank

        Returns
        -------
        list
            self.Table_Napts, self.Table
        """
        if CA:
            return list(zip(self.Table_Napts, self.sizingTable_CA))
        return list(zip(self.Table_Napts, self.sizingTable_EMASHRAE))
    
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
        heatCap = self.totalHWLoad * effSwingVolFract / heathours * rhoCp * \
            (self.storageT_F - self.building.incomingT_F) / self.defrostFactor /1000.
        return heatCap
    
    def getTotalVolMax(self, runningVol_G):
        # For a swing tank the storage volume is found at the appropriate temperature in calcRunningVol
        return runningVol_G / (1-self.aquaFract)
    
class Primary(SystemConfig):
    def __init__(self, building, inputs):
        super().__init__(building, inputs)
    
    def simulate(self):
        return super().simulate()

