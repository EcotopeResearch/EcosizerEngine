from objects.SystemConfig import SystemConfig
import numpy as np
from objects.Building import Building
from constants.Constants import *

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
        self.TMVol_G = 300 # TODO Scott to figure out table stuff for self.TMVol_G use 120 for now TODO had to set to 300
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
            hw_out = np.array(self.HRLIST_to_MINLIST(hw_out[peakInd:peakInd+24])) \
                / 60 * self.totalHWLoad # to minute
            
            # Simulate the swing tank assuming it hits the peak just above the supply temperature.
            # Get the volume removed for the primary adjusted by the swing tank
            N = len(hw_out)
            [_, _, hw_out_from_swing] = self.simJustSwing(N, hw_out, self.building.supplyT_F + 0.1)

            # Get the effective adjusted hot water demand on the primary system at the storage temperature.
            temp_eff_HW_mix_faction = sum(hw_out_from_swing)/self.totalHWLoad #/2 because the sim goes for two days
            genrate_min = np.array(self.HRLIST_to_MINLIST(genrate[peakInd:peakInd+24])) \
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
        hw_outSwing[0] = D_hw[0]
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
        return runningVol_G