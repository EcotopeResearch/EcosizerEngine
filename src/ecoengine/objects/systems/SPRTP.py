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

        super().sizeSystem(building)

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
    
    def getTemperatureAtTankVol(self, tank_volume : float, building : Building, ls_mode : str = 'N') -> float:
        """
        Returns the temperature given a tank volume

        Parameters
        ----------
        tank_volume : float
            The tank height in question, given as a number of gallons. 0 gallons indicates the bottom of the tank. 
            self.PVol_G_atStorageT indicates the top of the tank

        Returns
        -------
        temp : float
            the temperature (F) at the specified tank volume
        """
        if tank_volume > self.PVol_G_atStorageT:
            raise Exception(f"Tank volume of {tank_volume} is larger than max volume of {self.PVol_G_atStorageT}.")
        temp = self.strat_slope * (tank_volume + self.delta_energy) + self.strat_inter
        if temp < building.incomingT_F:
            return building.incomingT_F
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
            if self.getTemperatureAtTankVol(off_triggerV, simRun.building, ls_mode) >= off_triggerT:
                print(f"{i}: turning off at {self.getTemperatureAtTankVol(off_triggerV, simRun.building, ls_mode)} degrees")
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
            if self.getTemperatureAtTankVol(on_triggerV, simRun.building, ls_mode) <= on_triggerT:
                print(f"{i}: turning on at {self.getTemperatureAtTankVol(on_triggerV, simRun.building, ls_mode)} degrees. {delta_draw_recirc}")
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
            
    # def getInitializedSimulation(self, building : Building, initPV=None, initST=None, minuteIntervals = 1, nDays = 3, forcePeakyLoadshape = False) -> SimulationRun:
    #     """
    #     Returns initialized arrays needed for nDay simulation

    #     Parameters
    #     ----------
    #     building : Building
    #         The building for the simulation
    #     initPV : float
    #         the initial primary tank volume at the start of the simulation
    #     initST : float
    #         Not used in this instance of the function
    #     minuteIntervals : int
    #         the number of minutes per time interval for the simulation
    #     nDays : int
    #         the number of days that will be simulated 
    #     forcePeakyLoadshape : boolean (default False)
    #         if set to True, forces the most "peaky" load shape rather than average load shape

    #     Returns
    #     -------
    #     a SimulationRun object with all necessary components for running the simulation
    #     """
        
    #     loadShapeN = building.loadshape
    #     if self.doLoadShift and len(loadShapeN) == 24 and not forcePeakyLoadshape:
    #         loadShapeN = building.avgLoadshape
        
    #     # Get the generation rate from the primary capacity
    #     hwGenRate = None
    #     if self.PCap_kBTUhr is None:
    #         if building.climateZone is None:
    #             raise Exception("Cannot run a simulation of this kind without either a climate zone or a default output capacity")
    #     else:
    #         hwGenRate = 1000 * self.PCap_kBTUhr / rhoCp / (building.supplyT_F - building.getIncomingWaterT(0)) \
    #             * self.defrostFactor
    #     loadshiftSched = np.tile(self.loadShiftSchedule, nDays) # TODO can we get rid of it?
        
    #     # Define the use of DHW with the normalized load shape
    #     hwDemand = building.magnitude * loadShapeN
    #     if (len(hwDemand) == 24):
    #         hwDemand = np.tile(hwDemand, nDays)
    #         hwDemand = hwDemand * self.fract_total_vol
    #     elif len(hwDemand) == 8760:
    #         hwDemand = hwDemand
    #     else:
    #         raise Exception("Invalid load shape. Must be length 24 (day) or length 8760 (year).")

    #     # Init the "simulation"
    #     V0_normal = self.adjustedPVol_G_atStorageT
        
    #     # set load shift schedule for the simulation
    #     LS_sched = ['N'] * 24
    #     if self.doLoadShift:
    #         LS_sched = ['S' if x == 0 else 'N' for x in self.loadShiftSchedule]
    #         #set load up hours pre-shed 1
    #         shedHours = [i for i in range(len(self.loadShiftSchedule)) if self.loadShiftSchedule[i] == 0] 
    #         LS_sched = ['L' if shedHours[0] - self.loadUpHours <= i <= shedHours[0] - 1 else LS_sched[i] for i, x in enumerate(LS_sched)]
    #         #check if there are two sheds, if so set all hours inbetween to load up
    #         try:
    #             secondShed = [[shedHours[i-1], shedHours[i]] for i in range(1, len(shedHours)) if shedHours[i] - shedHours[i-1] > 1][0]
    #             LS_sched = ['L' if secondShed[0] < i <= secondShed[1] - 1 else LS_sched[i] for i, x in enumerate(LS_sched)]
    #         except IndexError:
    #             pass

    #     if minuteIntervals == 1:
    #         # To per minute from per hour
    #         if not hwGenRate is None:
    #             hwGenRate = hwGenRate / 60
    #         hwDemand = np.array(hrToMinList(hwDemand)) / 60
    #         loadshiftSched = np.array(hrToMinList(loadshiftSched))
    #     elif minuteIntervals == 15:
    #         # To per 15 minute from per hour
    #         if not hwGenRate is None:
    #             hwGenRate = hwGenRate / 4
    #         hwDemand = np.array(hrTo15MinList(hwDemand)) / 4
    #         loadshiftSched = np.array(hrTo15MinList(loadshiftSched))
    #     elif minuteIntervals != 60:
    #         raise Exception("Invalid input given for granularity. Must be 1, 15, or 60.")

    #     pV = [0] * (len(hwDemand) - 1) + [V0_normal]

    #     if initPV is not None:
    #         pV[-1] = initPV
    #     return SimulationRun(hwGenRate, hwDemand, V0_normal, pV, building, loadshiftSched, minuteIntervals, self.doLoadShift, LS_sched)

        # on_trigger = 
        # pheating = False
        # if self.getTemperatureAtTankVol(self.aquaFract * self.PVol_G_atStorageT) <= self.supplyT_F:


        # simRun.pheating, simRun.pV[i], simRun.pGen[i], simRun.pRun[i] = self.runOnePrimaryStep(pheating = simRun.pheating,
        #                                                                                     Vcurr = simRun.pV[i-1], 
        #                                                                                     hw_out = mixedDHW, 
        #                                                                                     hw_in = mixedGHW, 
        #                                                                                     mode = simRun.getLoadShiftMode(i),
        #                                                                                     modeChanged = (simRun.getLoadShiftMode(i) != simRun.getLoadShiftMode(i-1)),
        #                                                                                     minuteIntervals = minuteIntervals) 
    

    # def getInitializedSimulation(self, building : Building, initPV=None, initST=None, minuteIntervals = 1, nDays = 3, forcePeakyLoadshape = False) -> SimulationRun:
    #     """
    #     Returns initialized arrays needed for nDay simulation

    #     Parameters
    #     ----------
    #     building : Building
    #         The building for the simulation
    #     initPV : float
    #         the initial primary tank volume at the start of the simulation
    #     initST : float
    #         Not used in this instance of the function
    #     minuteIntervals : int
    #         the number of minutes per time interval for the simulation
    #     nDays : int
    #         the number of days that will be simulated 
    #     forcePeakyLoadshape : boolean (default False)
    #         if set to True, forces the most "peaky" load shape rather than average load shape

    #     Returns
    #     -------
    #     a SimulationRun object with all necessary components for running the simulation
    #     """
        
    #     loadShapeN = building.loadshape
    #     if self.doLoadShift and len(loadShapeN) == 24 and not forcePeakyLoadshape:
    #         loadShapeN = building.avgLoadshape
        
    #     # Get the generation rate from the primary capacity
    #     hwGenRate = None
    #     if self.PCap_kBTUhr is None:
    #         if building.climateZone is None:
    #             raise Exception("Cannot run a simulation of this kind without either a climate zone or a default output capacity")
    #     else:
    #         hwGenRate = 1000 * self.PCap_kBTUhr / rhoCp / (building.supplyT_F - building.getIncomingWaterT(0)) \
    #             * self.defrostFactor
    #     loadshiftSched = np.tile(self.loadShiftSchedule, nDays) # TODO can we get rid of it?
        
    #     # Define the use of DHW with the normalized load shape
    #     hwDemand = building.magnitude * loadShapeN
    #     if (len(hwDemand) == 24):
    #         hwDemand = np.tile(hwDemand, nDays)
    #         hwDemand = hwDemand * self.fract_total_vol
    #     elif len(hwDemand) == 8760:
    #         hwDemand = hwDemand
    #     else:
    #         raise Exception("Invalid load shape. Must be length 24 (day) or length 8760 (year).")

    #     # Init the "simulation"
    #     V0_normal = self.adjustedPVol_G_atStorageT
        
    #     # set load shift schedule for the simulation
    #     LS_sched = ['N'] * 24
    #     if self.doLoadShift:
    #         LS_sched = ['S' if x == 0 else 'N' for x in self.loadShiftSchedule]
    #         #set load up hours pre-shed 1
    #         shedHours = [i for i in range(len(self.loadShiftSchedule)) if self.loadShiftSchedule[i] == 0] 
    #         LS_sched = ['L' if shedHours[0] - self.loadUpHours <= i <= shedHours[0] - 1 else LS_sched[i] for i, x in enumerate(LS_sched)]
    #         #check if there are two sheds, if so set all hours inbetween to load up
    #         try:
    #             secondShed = [[shedHours[i-1], shedHours[i]] for i in range(1, len(shedHours)) if shedHours[i] - shedHours[i-1] > 1][0]
    #             LS_sched = ['L' if secondShed[0] < i <= secondShed[1] - 1 else LS_sched[i] for i, x in enumerate(LS_sched)]
    #         except IndexError:
    #             pass

    #     if minuteIntervals == 1:
    #         # To per minute from per hour
    #         if not hwGenRate is None:
    #             hwGenRate = hwGenRate / 60
    #         hwDemand = np.array(hrToMinList(hwDemand)) / 60
    #         loadshiftSched = np.array(hrToMinList(loadshiftSched))
    #     elif minuteIntervals == 15:
    #         # To per 15 minute from per hour
    #         if not hwGenRate is None:
    #             hwGenRate = hwGenRate / 4
    #         hwDemand = np.array(hrTo15MinList(hwDemand)) / 4
    #         loadshiftSched = np.array(hrTo15MinList(loadshiftSched))
    #     elif minuteIntervals != 60:
    #         raise Exception("Invalid input given for granularity. Must be 1, 15, or 60.")

    #     pV = [0] * (len(hwDemand) - 1) + [V0_normal]

    #     if initPV is not None:
    #         pV[-1] = initPV
    #     return SimulationRun(hwGenRate, hwDemand, V0_normal, pV, building, loadshiftSched, minuteIntervals, self.doLoadShift, LS_sched)