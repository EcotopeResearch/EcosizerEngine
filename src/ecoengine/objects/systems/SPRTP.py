from ecoengine.objects.SystemConfig import SystemConfig
from ecoengine.objects.SimulationRun import SimulationRun
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import convertVolume
from ecoengine.objects.Building import Building
import numpy as np
from ecoengine.objects.systemConfigUtils import convertVolume, getPeakIndices, hrTo15MinList

class SPRTP(SystemConfig): # Single Pass Return to Primary (SPRTP)
    def __init__(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, aquaFractLoadUp = None, 
                 aquaFractShed = None, loadUpT_F = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, 
                 PCap_kBTUhr = None, ignoreShortCycleEr = False, useHPWHsimPrefMap = False, stratFactor = 1):
        
        if stratFactor > 1 or stratFactor <= 0: 
            raise Exception('Stratificationfactor must be greater than zero and less than or equal to 1.')
        
        self.strat_factor = stratFactor
        self.delta_energy = 0.0
        self.Recirc_Cap_kBTUhr = None
        self.tm_hourly_load = building.getHourlyLoadIncrease()
        
        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building, doLoadShift, 
                loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, aquaFractShed, loadUpT_F, systemModel, 
                numHeatPumps, PVol_G_atStorageT, PCap_kBTUhr, ignoreShortCycleEr, useHPWHsimPrefMap)
        
        self.strat_slope = 1.7 / (self.PVol_G_atStorageT/100)
        self.strat_inter = building.supplyT_F - (1.7 * self.aquaFract * 100) #TODO replace with on temp?
        
    def sizeSystem(self, building : Building):
        """
        Resizes the system with a new building.
        Also used for resizing the system after it has changed its loadshift settings using the original building the system was sized for

        Parameters
        ----------
        building : Building
            The building to size with
        """
        dhw_usage_magnitude = building.magnitude
        dhw_loadshape = building.loadshape
        # tm_hourly_load = building.getHourlyLoadIncrease()
        day_load = [(x * dhw_usage_magnitude) + self.tm_hourly_load for x in dhw_loadshape]

        building.magnitude = dhw_usage_magnitude + (self.tm_hourly_load * 24)
        building.loadshape = [x/building.magnitude for x in day_load]

        self.ignoreShortCycleEr = True
        super().sizeSystem(building)
        self.ignoreShortCycleEr = False
        building.magnitude = dhw_usage_magnitude
        building.loadshape = dhw_loadshape

        recirc_only_model = Building(
            magnitude=self.tm_hourly_load * 24,
            loadshape= [.1/.24] * 24,
            avgLoadshape= [.1/.24] * 24,
            incomingT_F=building.getDesignInlet(),
            supplyT_F=building.getDesignReturnTemp(),
            returnT_F=None,
            flowRate=None,
            climate=building.climateZone,
            ignoreRecirc=True,
            designOAT_F=building.designOAT_F
        )

        self.Recirc_Cap_kBTUhr = self._primaryHeatHrs2kBTUHR(self.maxDayRun_hr, self.loadUpHours, recirc_only_model, 
            effSwingVolFract = self.effSwingFract, primaryCurve = False, lsFractTotalVol = self.fract_total_vol)[0]
        
    def _calcRunningVol(self, heatHrs, onOffArr, loadshape, building : Building, effMixFract = 0):
        """
        Function to find the running volume for the hot water storage tank, which
        is needed for calculating the total volume for primary sizing and in the event of load shift sizing
        represents the entire volume.

        Implimented seperatly for Swing Tank systems

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
        effMixFract: Int
            unused value in this instance of the function. Used in Swing Tank implimentation

        Raises
        ------
        Exception: Error if oversizing system.

        Returns
        -------
        runV_G : float
            The running volume in gallons at supply temp.
        effMixFract: int
            Needed for swing tank implementation.
        """         
        runV_G, effMixFract = super()._calcRunningVol(heatHrs, onOffArr, loadshape, building, effMixFract)
        return runV_G/self.strat_factor, effMixFract
    
    def _calcRunningVolLS(self, loadUpHours, loadshape, building : Building, effMixFract = 1, lsFractTotalVol = 1):
        """
        Function to calculate the running volume if load shifting. Using the max generation rate between normal sizing
        and preliminary volume, the deficit between generation and hot water use is then added to the preliminary volume.

        Implemented separately for swing tank system.

        Parameters
        ------   
        loadUpHours : float
            Number of hours of scheduled load up before first shed. If sizing, this is set by user. If creating sizing
            plot, number may vary.  
        loadshape : ndarray
            normalized array of length 24 representing the daily loadshape for this calculation.
        building : Building
            The building the system is being sized for
        effMixFract : float
            Only used in swing tank implementation.

        Returns
        ------
        LSrunV_G : float
            Volume needed between primary shed aquastat and load up aquastat at supply temp.
        effMixFract : float
            Used for swing tank implementation.
        """
        LSrunV_G, effMixFract = super()._calcRunningVolLS(loadUpHours, loadshape, building, effMixFract, lsFractTotalVol)
        return LSrunV_G/self.strat_factor, effMixFract

    def _calcMinCyclingVol(self, building : Building, heatHrs):
        return pCompMinimumRunTime * (building.magnitude / heatHrs) * ((building.supplyT_F - building.getDesignInlet())/(self.getOffTriggerTemp('N') - building.getDesignReturnTemp()))

    def getSizingResults(self):
        """
        Returns the minimum primary volume and heating capacity sizing results

        Returns
        -------
        list
            self.PVol_G_atStorageT, self.PCap_kBTUhr, self.Recirc_Cap_kBTUhr
        """
        return [self.PVol_G_atStorageT, self.PCap_kBTUhr, self.Recirc_Cap_kBTUhr]
    
    def getTemperatureAtTankVol(self, tank_volume : float, incomingT_F : float, ls_mode : str = 'N') -> float:
        """
        Returns the temperature given a tank volume

        Parameters
        ----------
        tank_volume : float
            The tank height in question, given as a number of gallons. 0 gallons indicates the bottom of the tank. 
            self.PVol_G_atStorageT indicates the top of the tank
        incomingT_F : float
            Temperature of incoming city water

        Returns
        -------
        temp : float
            the temperature (F) at the specified tank volume
        """
        if tank_volume > self.PVol_G_atStorageT:
            raise Exception(f"Tank volume of {tank_volume} is larger than max volume of {self.PVol_G_atStorageT}.")
        temp = self.strat_slope * (tank_volume + self.delta_energy) + self.strat_inter
        if temp < incomingT_F:
            return incomingT_F
        elif temp > self.getOffTriggerTemp(ls_mode): #TODO make sure this is right (Ask Scott)
            return self.getOffTriggerTemp(ls_mode)
        return temp
    
    def getTankVolAtTemp(self, temp) -> float:
        """
        Returns
        -------
        tank_vol : float
            the lowest volume on the tank where the water is storage temperature
        """
        tank_vol = ((temp - self.strat_inter) / self.strat_slope) - self.delta_energy
        return tank_vol
    
    def getOffTriggerVolume(self, ls_mode):
        if ls_mode == 'S':
            return self.aquaFractShed * self.PVol_G_atStorageT
        elif ls_mode == 'L':
            return self.aquaFractLoadUp * self.PVol_G_atStorageT
        return self.aquaFract * self.PVol_G_atStorageT
    
    def getOffTriggerTemp(self, ls_mode):
        if ls_mode == 'S':
            return self.storageT_F
        elif ls_mode == 'L':
            return self.loadUpT_F
        return self.storageT_F
    
    def getOnTriggerVolume(self, ls_mode):
        if ls_mode == 'S':
            return self.aquaFractShed * self.PVol_G_atStorageT
        elif ls_mode == 'L':
            return self.aquaFractLoadUp * self.PVol_G_atStorageT
        return self.aquaFract * self.PVol_G_atStorageT
        
    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None):
        incomingWater_T = simRun.getIncomingWaterT(i)
        self.preSystemStepSetUp(simRun, i, incomingWater_T, minuteIntervals, oat)
        interval_tm_load = self.tm_hourly_load / (60//simRun.minuteIntervals)
        delta_draw_recirc = convertVolume(simRun.hwDemand[i] + interval_tm_load, self.storageT_F, incomingWater_T, simRun.building.supplyT_F)
        self.delta_energy = self.delta_energy - delta_draw_recirc
        ls_mode = simRun.getLoadShiftMode(i)
        # print(f"{i} The tank height of supply T is: {self.getTankVolAtTemp(simRun.building.supplyT_F)} / {self.PVol_G_atStorageT}")
        # print(f"delta_draw_recirc {simRun.hwDemand[i]} + {interval_tm_load} = {delta_draw_recirc}")
        if simRun.pheating:
            # add heat
            simRun.pRun[i] = 1.0
            delta_heat = convertVolume(simRun.hwGenRate, self.storageT_F, incomingWater_T, simRun.building.supplyT_F) #TODO convert to off trigger vol?
            self.delta_energy = self.delta_energy + delta_heat

            off_triggerV = self.getOffTriggerVolume(ls_mode)
            off_triggerT = self.getOffTriggerTemp(ls_mode)
            if self.getTemperatureAtTankVol(off_triggerV, incomingWater_T, ls_mode) >= off_triggerT:
                simRun.pheating = False
                lowest_vol = self.getTankVolAtTemp(off_triggerT)
                if lowest_vol < off_triggerV:
                    extra_generation = off_triggerV - lowest_vol
                    extra_gen_percent = extra_generation/delta_heat
                    simRun.pRun[i] = 1.0 - extra_gen_percent
                    self.delta_energy = self.delta_energy - extra_generation
            simRun.pGen[i] = simRun.pRun[i] * delta_heat
        else:
            simRun.pRun[i] = 0.0
            on_triggerV = self.getOnTriggerVolume(ls_mode)
            on_triggerT = simRun.building.supplyT_F # TODO switch out for on trigger method
            if self.getTemperatureAtTankVol(on_triggerV, incomingWater_T, ls_mode) <= on_triggerT:
                simRun.pheating = True
                highest_vol = self.getTankVolAtTemp(on_triggerT)
                if highest_vol > on_triggerV:
                    extra_loss = highest_vol - on_triggerV
                    gen_percent = extra_loss/delta_draw_recirc
                    simRun.pRun[i] = gen_percent
                    delta_heat = convertVolume(simRun.hwGenRate * gen_percent, self.storageT_F, incomingWater_T, simRun.building.supplyT_F) #TODO convert to off trigger vol?
                    simRun.pGen[i] = delta_heat
                    self.delta_energy = self.delta_energy + delta_heat
        simRun.pRun[i] = simRun.pRun[i] * minuteIntervals
        simRun.pV[i] = (self.PVol_G_atStorageT - self.getTankVolAtTemp(simRun.building.supplyT_F)) / self.strat_factor

    def setLoadUPVolumeAndTrigger(self, incomingWater_T):
        # if not doing load shift, this is not applicable
        if self.doLoadShift:
            # need to figure out how this affects strat function
            return
            # self.PConvertedLoadUPV_G_atStorageT = convertVolume(self.PVol_G_atStorageT, self.storageT_F, incomingWater_T, self.loadUpT_F)
            # self.Vtrig_loadUp = self.PConvertedLoadUPV_G_atStorageT * (1 - self.aquaFractLoadUp)
            # self.adjustedPConvertedLoadUPV_G_atStorageT = np.ceil(self.PConvertedLoadUPV_G_atStorageT * self.percentUseable)

    def primaryCurve(self, building : Building):
        """
        Sizes the primary system curve. Will catch the point at which the aquatstat
        fraction is too small for system and cuts the return arrays to match cutoff point.

        Parameters
        ----------
        building : Building
            the building this primary system curve is being sized for

        Returns
        -------
        volN : array
            Array of volume in the tank at each hour.

        primaryHeatHrs2kBTUHR : array
            Array of heating capacity in kBTU/hr
            
        heatHours : array
            Array of running hours per day corresponding to primaryHeatHrs2kBTUHR
            
        recIndex : int
            The index of the recommended heating rate. 
        """
        dhw_usage_magnitude = building.magnitude
        dhw_loadshape = building.loadshape
        # tm_hourly_load = building.getHourlyLoadIncrease()
        day_load = [(x * dhw_usage_magnitude) + self.tm_hourly_load for x in dhw_loadshape]

        building.magnitude = dhw_usage_magnitude + (self.tm_hourly_load * 24)
        building.loadshape = [x/building.magnitude for x in day_load]


        [volN, primaryHeatHrs2kBTUHR, heatHours, recIndex] = super().primaryCurve(building)

        building.magnitude = dhw_usage_magnitude
        building.loadshape = dhw_loadshape
        
        return [volN, primaryHeatHrs2kBTUHR, heatHours, recIndex]

    def lsSizedPoints(self, building : Building):
        """
        Creates points for sizing curve plot based on number of hours in first load up period. If "regular" sizing 
        drives algorithmn, regular sizing will be used. This prevents user from oversizing system by putting 
        ill-informed number of load up hours.

        Parameters
        ----------
        building : Building
            The building the system being sized for

        Returns
        lsSizingCombos : array
            Array of volume and capacity combinations sized based on the number of load up hours.
        """
        dhw_usage_magnitude = building.magnitude
        dhw_loadshape = building.loadshape
        day_load = [(x * dhw_usage_magnitude) + self.tm_hourly_load for x in dhw_loadshape]

        building.magnitude = dhw_usage_magnitude + (self.tm_hourly_load * 24)
        building.loadshape = [x/building.magnitude for x in day_load]


        [volN, primaryHeatHrs2kBTUHR, heatHours, recIndex] = super().lsSizedPoints(building)

        building.magnitude = dhw_usage_magnitude
        building.loadshape = dhw_loadshape
        
        return [volN, primaryHeatHrs2kBTUHR, heatHours, recIndex]
            
    def getInitializedSimulation(self, building : Building, initPV=None, initST=None, minuteIntervals = 1, nDays = 3, forcePeakyLoadshape = False) -> SimulationRun:
        """
        Returns initialized arrays needed for nDay simulation

        Parameters
        ----------
        building : Building
            The building for the simulation
        initPV : float
            the initial primary tank volume at the start of the simulation
        initST : float
            Not used in this instance of the function
        minuteIntervals : int
            the number of minutes per time interval for the simulation
        nDays : int
            the number of days that will be simulated 
        forcePeakyLoadshape : boolean (default False)
            if set to True, forces the most "peaky" load shape rather than average load shape

        Returns
        -------
        a SimulationRun object with all necessary components for running the simulation
        """
        self.delta_energy = 0.0
        simRun = super().getInitializedSimulation(building, initPV, initST, minuteIntervals, nDays, forcePeakyLoadshape)
        return simRun
    
    def resetToDefaultCapacity(self):
        self.delta_energy = 0.0 # TODO may be a better spott for this as a sim reset
        return super().resetToDefaultCapacity()