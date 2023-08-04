from ecoengine.objects.SystemConfig import SystemConfig
from ecoengine.objects.SimulationRun import SimulationRun
import numpy as np
from ecoengine.objects.Building import Building
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import mixVolume, hrToMinList, getPeakIndices, checkHeatHours

class SwingTank(SystemConfig):

    #Assuming that these swing sizing methodologies will be dropped in next code cycle so they likely can be removed, it not we will need to implement additional swing sizing
    Table_Napts = [0, 12, 24, 48, 96]
    sizingTable = [40, 50, 80, 100, 120, 160, 175, 240, 350, 400, 500, 600, 800, 1000, 1250] #multiples of standard tank sizes 
    sizingTable_CA = [80, 96, 168, 288, 480]

    def __init__(self, safetyTM, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building = None,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, aquaFractLoadUp = None, 
                 aquaFractShed = None, loadUpT_F = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, PCap_kBTUhr = None, TMVol_G = None, 
                 TMCap_kBTUhr = None):
        # check Saftey factor
        if not (isinstance(safetyTM, float) or isinstance(safetyTM, int)) or safetyTM <= 1.:
            raise Exception("The saftey factor for the temperature maintenance system must be greater than 1 or the system will never keep up with the losses.")
        
        self.safetyTM = safetyTM
        self.element_deadband_F = 8.0
        
        # size if needed, else all sizing is taken care of in super().__init__
        if not PVol_G_atStorageT is None: # indicates system is sized
           if not (isinstance(TMVol_G, int) or isinstance(TMVol_G, float)) or TMVol_G <= 0: 
                raise Exception('Invalid input given for Temperature Maintenance Storage Volume, it must be a number greater than zero.')
           if not (isinstance(TMCap_kBTUhr, int) or isinstance(TMCap_kBTUhr, float)) or TMCap_kBTUhr <= 0: 
                raise Exception('Invalid input given for Temperature Maintenance Output Capacity, it must be a number greater than zero.')
           self.TMVol_G = TMVol_G
           self.CA_TMVol_G = min([x for x in self.sizingTable_CA if x >= TMVol_G]) if TMVol_G < 480 else 480
           self.TMCap_kBTUhr = TMCap_kBTUhr

        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building,
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, aquaFractShed, 
                 loadUpT_F, systemModel, numHeatPumps, PVol_G_atStorageT, PCap_kBTUhr)
        
    def getSizingResults(self):
        """
        Returns the minimum primary volume and heating capacity sizing results

        Returns
        -------
        list
            self.PVol_G_atStorageT, self.PCap_kBTUhr, self.TMVol_G, self.TMCap_kBTUhr, self.CA_TMVol_G
        """
        return [self.PVol_G_atStorageT, self.PCap_kBTUhr, self.TMVol_G, self.TMCap_kBTUhr, self.CA_TMVol_G]
    
    def sizeSystem(self, building):
        """
        Resizes the system with a new building.
        Also used for resizing the system after it has changed its loadshift settings using the original building the system was sized for

        Parameters
        ----------
        building : Building
            The building to size with
        """
        if not isinstance(building, Building):
            raise Exception("Error: Building is not valid.")
        #check if recirc losses require tank larger than 350 gallons
        if building.recirc_loss / (watt_per_gal_recirc_factor * W_TO_BTUHR) > max(self.sizingTable):
            raise Exception("Recirculation losses are too high, consider using multiple central plants.")

        self.TMVol_G = min([x for x in self.sizingTable if x >= (building.recirc_loss / (watt_per_gal_recirc_factor * W_TO_BTUHR))]) 
        self.CA_TMVol_G = min([x for x in self.sizingTable_CA if x >= (building.recirc_loss / (watt_per_gal_recirc_factor * W_TO_BTUHR))]) if self.TMVol_G < 480 else 480
        self.TMCap_kBTUhr = self.safetyTM * building.recirc_loss / 1000.
        super().sizeSystem(building)

    def _calcRunningVol(self, heatHrs, onOffArr, loadshape, building, effMixFract = 0.):
        """
        Function to find the running volume for the hot water storage tank, which
        is needed for calculating the total volume for primary sizing. Calculation 
        is done in swing tank reference frame. Volume is at swing tank temperature, 
        which is equal to the volume displaced from the primary storage tank. Volume is 
        converted to supply temp for consistency.

        Parameters
        ----------
        heatHrs : float
            The number of hours primary heating equipment can run in a day.
        onOffArr : ndarray
            array of 1/0's where 1's allow heat pump to run and 0's dissallow. of length 24.
        loadshape : ndarray
            normalized array of length 24 representing the daily loadshape for this calculation.
        building : Building
            The building the system is being sized for
        effMixFract: float
            The fractional adjustment to the total hot water load for the primary system.
            
        Raises
        ------
        Exception: Error if oversizing system.

        Returns
        -------
        runV_G : float
            The running volume in gallons at supply temp.
        eff_HW_mix_faction : float
            The fractional adjustment to the total hot water load for the
            primary system. Only used in a swing tank system.

        """

        eff_HW_mix_fraction = effMixFract
        genRate = np.tile(onOffArr,2) / heatHrs #hourly 
        diffN   = genRate - np.tile(loadshape, 2) #hourly
        diffInd = getPeakIndices(diffN[0:24]) #Days repeat so just get first day!
        
        # Get the running volume ##############################################
        if len(diffInd) == 0:
            raise Exception("ERROR ID 03","The heating rate is greater than the peak volume the system is oversized! Try increasing the hours the heat pump runs in a day",)

        # Watch out for cases where the heating is to close to the initial peak value so also check the hour afterwards too.
        nRealpeaks = len(diffInd)
        diffInd = np.append(diffInd, diffInd+1)
        diffInd = diffInd[diffInd < 24]
        runV_G = 0
        
        for peakInd in diffInd:
            hw_out = np.tile(loadshape, 2)
            hw_out = np.array(hrToMinList(hw_out[peakInd:peakInd+24])) \
                / 60 * building.magnitude # to minute
            # Simulate the swing tank assuming it hits the peak just above the supply temperature.
            # Get the volume removed for the primary adjusted by the swing tank
            [_, _, hw_out_from_swing] = self._simJustSwing(len(hw_out), hw_out, building, building.supplyT_F + 0.1)  
            
            # Get the effective adjusted hot water demand on the primary system at the storage temperature.
            temp_eff_HW_mix_fraction = sum(hw_out_from_swing)/building.magnitude
            genRate_min = np.array(hrToMinList(genRate[peakInd:peakInd+24])) \
                / 60 * building.magnitude * temp_eff_HW_mix_fraction # to minute 
        
            # Get the new difference in generation and demand at storage temp
            diffN = genRate_min - hw_out_from_swing

            # Get the rest of the day from the start of the peak
            diffCum = np.cumsum(diffN)

            # Check if additional cases saftey checks have oversized the system.
            if(np.where(diffInd == peakInd)[0][0] >= nRealpeaks):
                if not any(diffCum < 0.):
                    continue

            new_runV_G = -min(diffCum[diffCum<0.])
            
            if runV_G < new_runV_G:
                runV_G = new_runV_G #Minimum value less than 0 or 0.
                eff_HW_mix_fraction = temp_eff_HW_mix_fraction
    
        #convert to supply so that we can reuse functionality 
        storMixedT_F = self.mixStorageTemps(runV_G, building.incomingT_F, building.supplyT_F)[0]
        runV_G = runV_G * (storMixedT_F - building.incomingT_F) / (building.supplyT_F - building.incomingT_F) 
        
        return runV_G, eff_HW_mix_fraction
    

    def _calcRunningVolLS(self, loadUpHours, loadshape, building, effMixFract):
        """
        Function to to find the adjusted hot water demand on the primary system by the swing tank. Function
        uses maximum generation rate between standard method and rate needed to load up then finds the 
        deficit in volume at storage temp (running volume) and adds to preliminary volume. Volume is converted
        to supply temp for consistency.

        Parameters
        ----------
        loadUpHours : float
            Number of hours of scheduled load up before first shed. If sizing, this is set by user. If creating sizing
            plot, number may vary. 
        loadshape : ndarray
            normalized array of length 24 representing the daily loadshape for this calculation.
        building : Building
            The building the system is being sized for 
        effMixFract: float
            The fractional adjustment to the total hot water load for the primary system.
            
        Raises
        ------
        Exception: Error if oversizing system.

        Returns
        -------
        runV_G : float
            The running volume in gallons at supply temp.
        eff_HW_mix_faction : float
            The fractional adjustment to the total hot water load for the
            primary system. Only used in a swing tank system.

        """
        Vshift = self._calcPrelimVol(loadUpHours, loadshape, building)[0]

        genRateON = self._primaryHeatHrs2kBTUHR(self.maxDayRun_hr,  loadUpHours, building, effSwingVolFract = effMixFract, primaryCurve = False)[1] #max generation rate in storage/swing frame
        genRate = np.tile([genRateON if x != 0 else 0 for x in self.loadShiftSchedule], 2) #set generation rate during shed to 0
        
        #get first index after shed and go through next 24 hours
        shedEnd = [i for i,x in enumerate(genRate[1:],1) if x > genRate[i-1]][0] #start at beginning of first shed, fully loaded up equivalent to starting at the end of shed completely "empty"
        hw_out = np.tile(loadshape, 2) 
        hw_out = np.array(hrToMinList(hw_out[shedEnd:shedEnd+24])) \
                / 60 * building.magnitude # to minute
        
        # Simulate the swing tank assuming it hits the peak just above the supply temperature.
        [_, _, hw_out_from_swing] = self._simJustSwing(len(hw_out), hw_out, building, building.supplyT_F + 0.1) #VOLUME OF HOT WATER NEEDED AT STORAGE TEMP
        
        # Get the effective adjusted hot water demand on the primary system at the storage temperature.
        eff_HW_mix_fraction = sum(hw_out_from_swing)/building.magnitude
        genRate_min = np.array(hrToMinList(genRate[shedEnd:shedEnd+24])) \
                / 60 #* building.magnitude #* eff_HW_mix_fraction
        
        #get difference in generation and demand
        diffN = genRate_min - hw_out_from_swing

        #get the rest of the day from the start of the peak
        diffCum = np.cumsum(diffN)

        #get the biggest deficit and add to preliminary volume
        runV_G = -min(diffCum[diffCum<0.], default = 0)
        runV_G += Vshift
       
        #get mixed storage temp
        mixedStorT_F = self.mixStorageTemps(runV_G, building.incomingT_F, building.supplyT_F)[0]
        
        #convert from storage to supply volume
        runV_G = runV_G * (mixedStorT_F- building.incomingT_F) / (building.supplyT_F - building.incomingT_F) 
        
        return runV_G, eff_HW_mix_fraction

    
    def _calcPrelimVol(self, loadUpHours, loadshape, building):
        '''
        Function to calculate volume shifted during first shed period in order to calculate generation rate,
        adjusted for swing tank usage. Values are in swing tank reference frame and thus at storage temperature.

        Parameters
        ----------
        loadUpHours : float
            Number of hours of scheduled load up before first shed. If sizing, this is set by user. If creating sizing
            plot, number may vary. 
        loadshape : ndarray
            normalized array of length 24 representing the daily loadshape for this calculation.
        building : Building
            The building object being sized for 

        Returns 
        ----------
        Vshift : float
            Volume at storage temp between normal and load up AQ fract needed to make it through first shed period.
        VconsumedLU : float
            Volume at storage temp consumed during first load up period.
        '''
        shedHours = [i for i in range(len(self.loadShiftSchedule)) if self.loadShiftSchedule[i] == 0] #get all scheduled shed hours
        firstShed = [x for i,x in enumerate(shedHours) if x == shedHours[0] + i] #get first shed
        Vshift = sum([loadshape[i] * building.magnitude for i in firstShed])#calculate vol used during first shed
        VconsumedLU = sum(loadshape[firstShed[0]-loadUpHours : firstShed[0]]) * building.magnitude
        
        #get swing tank contribution for shed period
        hw_out = np.array(hrToMinList(loadshape[i] for i in firstShed)) / 60 * building.magnitude 
        [_, _, hw_out_from_swing] = self._simJustSwing(len(hw_out), hw_out, building, building.supplyT_F + 0.1)
        effMixFract = sum(hw_out_from_swing) / Vshift
        Vshift *= effMixFract #volume needed for shift at storage temperature
      
        #get swing tank contribution for load up period
        hw_out = np.array(hrToMinList(loadshape[firstShed[0] - loadUpHours:firstShed[0]])) / 60 * building.magnitude
        [_, _, hw_out_from_swing] = self._simJustSwing(len(hw_out), hw_out, building, building.supplyT_F + 0.1)
        effMixFract = sum(hw_out_from_swing) / VconsumedLU 
        VconsumedLU *= effMixFract
       
        return Vshift, VconsumedLU


    def _simJustSwing(self, N, hw_out, building, initST = None):
        """
        Parameters
        ----------
        N : int
            the length of the simulation in hours
        hw_out : list

        building : Building
            building being simulated on

        initST : float
            Primary Swing tank at start of sim

        Returns
        -------
        hw_outSwing : list
            Hot water exiting swing tank at swing tank temperature - this is the demand on the 
            primary system.

        """
        swingT_F = [building.supplyT_F] + [0] * (N - 1)
        hwDemand = hw_out

        if initST:
            swingT_F[0] = initST
        
        # Run the "simulation"
        hw_outSwing = [0] * N
        hw_outSwing[0] = hwDemand[0]
        tmRun = [0] * N
        swingheating = False

        for i in range(1, N):
            hw_outSwing[i] = mixVolume(hwDemand[i], swingT_F[i-1], building.incomingT_F, building.supplyT_F)
            primaryStorageT_F = self.mixStorageTemps(hw_outSwing[i], building.incomingT_F, building.supplyT_F)[0]
            swingheating, swingT_F[i], tmRun[i] = self._runOneSwingStep(building, swingheating, swingT_F[i-1], hw_outSwing[i], primaryStorageT_F)
        
        return [swingT_F, tmRun, hw_outSwing]
    
    def _runOneSwingStep(self, building : Building, swingheating, Tcurr, hw_out, primaryStorageT_F, minuteIntervals = 1):
        """
        Runs one step on the swing tank step. Since the swing tank is in series
        with the primary system the temperature needs to be tracked to inform
        inputs for primary step. The driving assumptions here are that the swing
        tank is well mixed and can be tracked by the average tank temperature
        and that the system loses the recirculation loop losses as a constant
        Watts and thus the actual flow rate and return temperature from the
        loop are irrelevant.

        Parameters
        ----------
        building : Building
            the building object for the simulation
        swingheating : float
            True if tank is heating at the begining of this time step
        Tcurr : float
            The temperature at the begining of the timestep.
        hw_out : float
            The volume of DHW removed from the swing tank system.
        primaryStorageT_F : float
            Temperature of the hot water in th primary storage tank (F)
        minuteIntervals : float
            The number of minutes in the interval.

        Returns
        -------
        swingheating : float
            True if tank is heating at the end of this time step
        Tnew : float
            The new swing tank tempeature for the timestep assuming the tank is well mixed.
        time_run : int
            The amount of thime the swing tank ran during the interval
        """
        time_running = 0 

        timeDivisor = 60 // minuteIntervals

        # Take out the recirc losses
        Tnew = Tcurr - building.recirc_loss / timeDivisor / rhoCp / self.TMVol_G
        element_dT = self.TMCap_kBTUhr * 1000  / timeDivisor / rhoCp / self.TMVol_G

        # Add in heat for a draw
        if hw_out:
            Tnew += hw_out * (primaryStorageT_F - Tcurr) / self.TMVol_G 
        
        # Check if the element is heating
        if swingheating:
            Tnew += element_dT #If heating, generate HW and lose HW
            time_running = 1

            # Check if the element should turn off
            if Tnew > building.supplyT_F + self.element_deadband_F: # If too hot
                time_over = (Tnew - (building.supplyT_F + self.element_deadband_F)) / element_dT # Temp below turn on / rate of element heating gives time above trigger plus deadband
                Tnew -= element_dT * time_over # Make full with miss volume
                time_running = (1-time_over)
                swingheating = False

        elif Tnew <= building.supplyT_F: # If the element should turn on
            time_missed = (building.supplyT_F - Tnew)/element_dT # Temp below turn on / rate of element heating gives time below tigger
            Tnew += element_dT * time_missed # Start heating 
            time_running = time_missed
            swingheating = True # Start heating

        if Tnew < building.supplyT_F: # Check for errors
            raise Exception("The swing tank dropped below the supply temperature! The system is undersized")
        
        # multiply time_running to reflect the time durration of the interval.
        time_run = time_running * minuteIntervals

        return swingheating, Tnew, time_run
    
    def _primaryHeatHrs2kBTUHR(self, heathours, loadUpHours, building, effSwingVolFract, primaryCurve = False,):
        """
        Converts from hours of heating in a day to heating capacity. Takes maximum from 
        standard method based on number of heating hours and load shift method based on
        load up hours.

        Parameters
        ----------
        heathours : float or numpy.ndarray
            The number of hours primary heating equipment can run.
        loadUpHours : float
            Number of scheduled load up hours before first shed period.
        building : Building
            The building the system being sized for
        PrimaryCurve : 
            Determines whether or not LS sizing is ignored. Used for generating sizing curve
            with "normal" sizing algorithm.
        effSwingVolFract : float or numpy.ndarray
            The fractional adjustment to the total hot water load for the
            primary system. Only used in a swing tank system.

        Returns
        -------
        heatCap
            The heating capacity in [btu/hr].
        genRate
            The generation rate in [gal/hr].
        """
        checkHeatHours(heathours)
        
        genRate = building.magnitude * effSwingVolFract / heathours
        heatCap = genRate * rhoCp * \
            (self.storageT_F - building.incomingT_F) / self.defrostFactor / 1000 #use storage temp instead of supply temp
        
        if self.doLoadShift and not primaryCurve:
            Vshift, VconsumedLU = self._calcPrelimVol(loadUpHours, building.avgLoadshape, building) 
            Vload = Vshift * (self.aquaFract - self.aquaFractLoadUp) / (self.aquaFractShed - self.aquaFractLoadUp) #volume in 'load up' portion of tank
            LUgenRate = (Vload + VconsumedLU) / loadUpHours #rate needed to load up tank and offset use 
            LUheatCap = LUgenRate * rhoCp * \
                (self.storageT_F - building.incomingT_F) / self.defrostFactor / 1000
            #TODO putting these in supply temp instead of storage... make sure this is correct
            #compare swing and loadshift capacity
            
            if LUheatCap > heatCap:
                heatCap = LUheatCap
                genRate = LUgenRate
            
        return heatCap, genRate
    
    def getInitializedSimulation(self, building : Building, initPV=None, initST=None, minuteIntervals = 1, nDays = 3):
        simRun = super().getInitializedSimulation(building, initPV, initST, minuteIntervals, nDays)
        simRun.initializeTMValue(initST, self.storageT_F, self.TMCap_kBTUhr)
        return simRun

    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None):
        incomingWater_T = simRun.getIncomingWaterT(i)
        if not (oat is None or self.perfMap is None):
            # set primary system capacity based on outdoor ait temp and incoming water temp 
            self.setCapacity(oat = oat, incomingWater_T = incomingWater_T)
            simRun.addHWGen((1000 * self.PCap_kBTUhr / rhoCp / (simRun.building.supplyT_F - incomingWater_T) \
               * self.defrostFactor)/(60/minuteIntervals))
            
        # aquire draw amount for time step
        simRun.hw_outSwing[i] = mixVolume(simRun.hwDemand[i], simRun.tmT_F[i-1], incomingWater_T, simRun.building.supplyT_F)
            
        simRun.tmheating, simRun.tmT_F[i], simRun.tmRun[i] = self._runOneSwingStep(simRun.building, simRun.tmheating, simRun.tmT_F[i-1], simRun.hw_outSwing[i], simRun.mixedStorT_F, minuteIntervals = minuteIntervals)
        
        #Get the mixed generation
        mixedGHW = mixVolume(simRun.hwGenRate, simRun.mixedStorT_F, incomingWater_T, simRun.building.supplyT_F)

        simRun.pheating, simRun.pV[i], simRun.pGen[i], simRun.pRun[i] = self.runOnePrimaryStep(pheating = simRun.pheating, 
                                                                                               V0 = simRun.V0, 
                                                                                               Vtrig = simRun.Vtrig[i], 
                                                                                               Vcurr = simRun.pV[i-1], 
                                                                                               hw_out = simRun.hw_outSwing[i], 
                                                                                               hw_in = mixedGHW,
                                                                                               Vtrig_previous = simRun.Vtrig[i-1],
                                                                                               minuteIntervals = minuteIntervals)
    
    def getTMOutputCapacity(self, kW = False):
        if kW:
            return self.TMCap_kBTUhr/W_TO_BTUHR
        return self.TMCap_kBTUhr
    
    def getTMInputCapacity(self, kW = False):
        # assume COP of 1
        if kW:
            return (self.TMCap_kBTUhr) / W_TO_BTUHR
        return self.TMCap_kBTUhr
   