from ecoengine.constants.Constants import *
from .Building import Building
from .SimulationRun import SimulationRun
from .PrefMapTracker import PrefMapTracker
import numpy as np
from scipy.stats import norm #lognorm
from .systemConfigUtils import *
from plotly.offline import plot
from plotly.graph_objs import Figure, Scatter

class SystemConfig:
    def __init__(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract = None, onT = None, offT = None, building : Building = None,
                 outletLoadUpT = None, onFractLoadUp = None, offFractLoadUp = None, onLoadUpT = None, offLoadUpT = None, 
                 onFractShed = None, offFractShed = None, onShedT = None, offShedT = None, 
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None,
                 systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, 
                 PCap_kBTUhr = None, useHPWHsimPrefMap = False, strat_factor = 1):
        
        # check inputs. Schedule not checked because it is checked elsewhere
        self._checkInputs(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, doLoadShift, loadShiftPercent)
        self.doLoadShift = doLoadShift
        self.maxCyclingCapacity_kBTUhr = None
        self.storageT_F = storageT_F
        self.defrostFactor = defrostFactor
        self.percentUseable = percentUseable
        self.compRuntime_hr = compRuntime_hr
        self.strat_factor = strat_factor # TODO check it
        self.setStratificationPercentageSlope()
        
        if onT is None:
            if building is None:
                raise Exception("if no building is provided, system must have a defined ON temperature.")
            elif not isinstance(building, Building):
                raise Exception("Error: Building is not valid.")
            onT = building.supplyT_F
        if offFract is None: offFract = onFract
        if offT is None: offT = storageT_F

        self.onFract = onFract
        self.onT = onT
        self.offFract = offFract
        self.offT = offT

        self.loadUpHours = None

        if doLoadShift:
            self._setLoadShift(loadShiftSchedule, loadUpHours, 
                               onFract, offFract, onT, offT,
                               outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT,
                               onFractShed, offFractShed, onShedT, offShedT, loadShiftPercent)
        
        else:
            self.loadShiftSchedule = [1] * 24
            self.fract_total_vol = 1 # fraction of total volume for for load shifting, or 1 if no load shifting

        #Check if need to increase sizing to meet lower runtimes for load shift
        self.maxDayRun_hr = min(self.compRuntime_hr, sum(self.loadShiftSchedule))

        #size system
        default_PCap_kBTUhr = None
        if not PVol_G_atStorageT is None:
            if not (isinstance(PVol_G_atStorageT, int) or isinstance(PVol_G_atStorageT, float)) or PVol_G_atStorageT <= 0: 
                raise Exception('Invalid input given for Primary Storage Volume, it must be a number greater than zero.')
            if not (isinstance(PCap_kBTUhr, int) or isinstance(PCap_kBTUhr, float)) or PCap_kBTUhr <= 0:
                # if systemModel and numHeatPumps are defined we do not nessesarily need PCap_kBTUhr
                if systemModel is None or numHeatPumps is None:
                    raise Exception('Invalid input given for Primary Output Capacity, must be a number greater than zero.')
            if PCap_kBTUhr is None and isinstance(building, Building):
                # get default capacity needed incase we need this for the simulation with performance maps
                self.sizeSystem(building)
                default_PCap_kBTUhr = self.PCap_kBTUhr
            self.PVol_G_atStorageT = PVol_G_atStorageT
            self.PCap_kBTUhr = PCap_kBTUhr
        else: 
            #size system based off of building
            self.sizeSystem(building)
        if self.doLoadShift:
            self.Vtrig_shed = self.PVol_G_atStorageT * (1 - self.onFractShed)
        if numHeatPumps is None and not systemModel is None and not building is None:
            # size number of heatpumps based on the coldest day
            self.perfMap = PrefMapTracker(self.PCap_kBTUhr if default_PCap_kBTUhr is None else default_PCap_kBTUhr, 
                                          modelName = systemModel, numHeatPumps = numHeatPumps, kBTUhr = True,
                                          designOAT_F=building.getDesignOAT(), designIncomingT_F=self.getDesignIncomingTemp(building),
                                          designOutT_F=self.storageT_F, usePkl=True if not (systemModel is None or useHPWHsimPrefMap) else False)
        else:
            self.perfMap = PrefMapTracker(self.PCap_kBTUhr if default_PCap_kBTUhr is None else default_PCap_kBTUhr, 
                                          modelName = systemModel, numHeatPumps = numHeatPumps, kBTUhr = True,
                                          usePkl=True if not (systemModel is None or useHPWHsimPrefMap) else False)
        
        # check that storage and load up temps are possible
        if not building is None and not systemModel is None and not systemModel[-2:] == 'MP':
            highest_possible_storage_temp, fifth_percentile_oat = building.getHighestStorageTempAtFifthPercentileOAT(self.perfMap)
            if highest_possible_storage_temp < self.storageT_F:
                raise Exception(f"The selected model can not produce a storage temperature of {self.storageT_F} degrees during the fifth percentile outdoor air temperature ({fifth_percentile_oat} F) in the selected climate (zip code). Please lower the storage temperature to at least {highest_possible_storage_temp} or select a different model.")
            elif hasattr(self, 'outletLoadUpT') and not self.offLoadUpT is None and highest_possible_storage_temp < self.outletLoadUpT:
                raise Exception(f"The selected model can not produce a storage temperature of {self.outletLoadUpT} degrees during the fifth percentile outdoor air temperature ({fifth_percentile_oat} F) in the selected climate (zip code). Please lower the load up temperature to at least {highest_possible_storage_temp} or select a different model.")

        self.strat_slope = self.stratPercentageSlope / (self.PVol_G_atStorageT/100)
        self.strat_inter = self.onT - (self.stratPercentageSlope * self.onFract * 100)

    def _checkInputs(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, doLoadShift, loadShiftPercent):
        if not (isinstance(storageT_F, int) or isinstance(storageT_F, float)) or not checkLiqudWater(storageT_F): 
            raise Exception(f'Invalid input given for Storage temp, it must be between 32 and 212F. {storageT_F}')
        if not (isinstance(defrostFactor, int) or isinstance(defrostFactor, float)) or defrostFactor < 0 or defrostFactor > 1:
            raise Exception("Invalid input given for Defrost Factor, must be a number between 0 and 1.")
        if not (isinstance(percentUseable, int) or isinstance(percentUseable, float)) or percentUseable > 1 or percentUseable <= 0:
            raise Exception("Invalid input given for percentUseable, must be a number between 0 and 1.")
        if not (isinstance(compRuntime_hr, int) or isinstance(compRuntime_hr, float)) or compRuntime_hr <= 0 or compRuntime_hr > 24:
            raise Exception("Invalid input given for compRuntime_hr, must be a number between 0 and 24.")
        if not (isinstance(onFract, int) or isinstance(onFract, float)) or onFract > 1 or onFract <= 0:
            raise Exception("Invalid input given for onFract must, be a number between 0 and 1.")
        if not isinstance(doLoadShift, bool):
            raise Exception("Invalid input given for doLoadShift, must be a boolean.")
        if doLoadShift and (not (isinstance(loadShiftPercent, int) or isinstance(loadShiftPercent, float)) or loadShiftPercent > 1 or loadShiftPercent < 0):
            raise Exception("Invalid input given for loadShiftPercent, must be a number between 0 and 1.")

    def setCapacity(self, PCap_kBTUhr = None, oat = None, incomingWater_T = None, useLoadUpTemp = False, cop = 2.5):
        if not PCap_kBTUhr is None:
            self.PCap_kBTUhr = PCap_kBTUhr
            self.PCap_input_kBTUhr = self.PCap_kBTUhr / cop
        elif not (oat is None or incomingWater_T is None or self.perfMap is None):
            if useLoadUpTemp and hasattr(self, 'outletLoadUpT') and not self.outletLoadUpT is None:
                self.PCap_kBTUhr, self.PCap_input_kBTUhr = self.perfMap.getCapacity(oat, incomingWater_T, self.outletLoadUpT, fallbackCapacity_kW = self.getOutputCapacity(kW = True))
            else:
                self.PCap_kBTUhr, self.PCap_input_kBTUhr = self.perfMap.getCapacity(oat, incomingWater_T, self.storageT_F, fallbackCapacity_kW = self.getOutputCapacity(kW = True))
        else:
           raise Exception("No capacity given or preformance map has not been set.")
        
    def resetToDefaultCapacity(self):
        self.PCap_kBTUhr = self.perfMap.getDefaultCapacity()

    def resetPerfMap(self):
        self.perfMap.resetFlags()

    def getDesignIncomingTemp(self, building: Building):
        return building.getHighestIncomingT_F()
    
    def reliedOnEr(self):
        return self.perfMap.didRelyOnEr()
    
    def tmReliedOnEr(self):
        return False
    
    def capedInlet(self):
        return self.perfMap.didCapInlet()
    
    def assumedHighDefaultCap(self):
        return self.perfMap.assumedHighDefaultCap
    
    def raisedInletTemp(self):
        return self.perfMap.raisedInletTemp
    
    def assumedCOP(self):
        return self.perfMap.timesAssumedCOP > 0

    def getOutputCapacity(self, kW = False):
        if self.PCap_kBTUhr is None:
            return None
        if kW:
            return self.PCap_kBTUhr/W_TO_BTUHR
        return self.PCap_kBTUhr
    
    def getInputCapacity(self, kW = False):
        if hasattr(self, 'PCap_input_kBTUhr'):
            if kW:
                return self.PCap_input_kBTUhr / W_TO_BTUHR
            return self.PCap_input_kBTUhr
        
        # else assume COP of 2.5
        if kW:
            return (self.PCap_kBTUhr / 2.5) / W_TO_BTUHR
        return self.PCap_kBTUhr / 2.5

    def setDoLoadShift(self, doLoadShift):
        if not isinstance(doLoadShift, bool):
            raise Exception("Invalid input given for doLoadShift, must be a boolean.")

        self.doLoadShift = doLoadShift

    def sizeSystem(self, building : Building):
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
        
        buildingWasAnnual = False
        if building.isAnnualLS():
            # set building load shape from annual to daily for sizing
            buildingWasAnnual = True
            building.setToDailyLS()

        # size the system
        self.PVol_G_atStorageT, self.effSwingFract = self.sizePrimaryTankVolume(self.maxDayRun_hr, self.loadUpHours, building, lsFractTotalVol = self.fract_total_vol)
        self.PCap_kBTUhr = self._primaryHeatHrs2kBTUHR(self.maxDayRun_hr, self.loadUpHours, building, 
            effSwingVolFract = self.effSwingFract, primaryCurve = False, lsFractTotalVol = self.fract_total_vol)[0]
        self.maxCyclingCapacity_kBTUhr = self.sizeStagedCapacity(building, self.PVol_G_atStorageT, self.offFract, self.offT)
        if buildingWasAnnual:
            # set building load shape back to annual
            building.setToAnnualLS()

    def getMaxCyclingCapacity_kBTUhr(self):
        return self.maxCyclingCapacity_kBTUhr

    def getSizingResults(self):
        """
        Returns the minimum primary volume and heating capacity sizing results. Implimented seperatly in Temp Maintenence systems.

        Returns
        -------
        list
            self.PVol_G_atStorageT, self.PCap_kBTUhr
        """
        return [self.PVol_G_atStorageT, self.PCap_kBTUhr]
    
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
        
        loadShapeN = building.loadshape
        if self.doLoadShift and len(loadShapeN) == 24 and not forcePeakyLoadshape:
            loadShapeN = building.avgLoadshape
        
        # Get the generation rate from the primary capacity
        hwGenRate = None
        if self.PCap_kBTUhr is None:
            if building.climateZone is None:
                raise Exception("Cannot run a simulation of this kind without either a climate zone or a default output capacity")
        else:
            hwGenRate = 1000 * self.PCap_kBTUhr / rhoCp / (building.supplyT_F - building.getIncomingWaterT(0)) \
                * self.defrostFactor
        loadshiftSched = np.tile(self.loadShiftSchedule, nDays) # TODO can we get rid of it?
        
        # Define the use of DHW with the normalized load shape
        hwDemand = building.magnitude * loadShapeN
        if (len(hwDemand) == 24):
            hwDemand = np.tile(hwDemand, nDays)
            hwDemand = hwDemand * self.fract_total_vol
        elif len(hwDemand) == 8760:
            hwDemand = hwDemand
        else:
            raise Exception("Invalid load shape. Must be length 24 (day) or length 8760 (year).")
        
        # set load shift schedule for the simulation
        LS_sched = ['N'] * 24
        if self.doLoadShift:
            LS_sched = ['S' if x == 0 else 'N' for x in self.loadShiftSchedule]
            #set load up hours pre-shed 1
            shedHours = [i for i in range(len(self.loadShiftSchedule)) if self.loadShiftSchedule[i] == 0] 
            LS_sched = ['L' if shedHours[0] - self.loadUpHours <= i <= shedHours[0] - 1 else LS_sched[i] for i, x in enumerate(LS_sched)]
            #check if there are two sheds, if so set all hours inbetween to load up
            try:
                secondShed = [[shedHours[i-1], shedHours[i]] for i in range(1, len(shedHours)) if shedHours[i] - shedHours[i-1] > 1][0]
                LS_sched = ['L' if secondShed[0] < i <= secondShed[1] - 1 else LS_sched[i] for i, x in enumerate(LS_sched)]
            except IndexError:
                pass

        if minuteIntervals == 1:
            # To per minute from per hour
            if not hwGenRate is None:
                hwGenRate = hwGenRate / 60
            hwDemand = np.array(hrToMinList(hwDemand)) / 60
            loadshiftSched = np.array(hrToMinList(loadshiftSched))
        elif minuteIntervals == 15:
            # To per 15 minute from per hour
            if not hwGenRate is None:
                hwGenRate = hwGenRate / 4
            hwDemand = np.array(hrTo15MinList(hwDemand)) / 4
            loadshiftSched = np.array(hrTo15MinList(loadshiftSched))
        elif minuteIntervals != 60:
            raise Exception("Invalid input given for granularity. Must be 1, 15, or 60.")

        pV = [0] * (len(hwDemand) - 1) + [(1-self.onFract)*self.PVol_G_atStorageT] # default to full up to aquastat fraction
        delta_energy = 0
        if initPV is not None:
            pV[-1] = initPV
            if initPV <= 0:
                pV[-1] = 0
                delta_energy = -1 * ((1-self.onFract)*self.PVol_G_atStorageT)
            elif initPV >= self.PVol_G_atStorageT * self.percentUseable:
                pV[-1] = self.PVol_G_atStorageT * self.percentUseable
                delta_energy = self.onFract*self.PVol_G_atStorageT - (1-self.percentUseable)*self.PVol_G_atStorageT # most full the tank can be
            else:
                start_vol = (1-self.onFract)*self.PVol_G_atStorageT
                delta_energy = initPV - start_vol
        return SimulationRun(hwGenRate, hwDemand, pV, building, loadshiftSched, minuteIntervals, self.doLoadShift, LS_sched, delta_energy)
    
    def preSystemStepSetUp(self, simRun : SimulationRun, i, incomingWater_T, minuteIntervals, oat, setLU : bool = True):
        """
        helper function for runOneSystemStep
        """
        if not (oat is None or self.perfMap is None):
            if i%(60/minuteIntervals) == 0: # we have reached the next hour and should thus be at the next OAT
                # set primary system capacity based on outdoor air temp and incoming water temp 
                self.setCapacity(oat = oat, incomingWater_T = incomingWater_T, useLoadUpTemp= simRun.getLoadShiftMode(i) == 'L')
                if simRun.passedCOPAssumptionThreshold(self.perfMap.timesAssumedCOP*(60/minuteIntervals)):
                    raise Exception("Could not run simulation because internal performance map for the primary model does not account for the climate zone of the input zip code. Please try with a different primary model or zip code.")
                hw_gen_for_interval = (1000 * self.PCap_kBTUhr / rhoCp / (simRun.building.supplyT_F - simRun.getIncomingWaterT(i)) * self.defrostFactor)/(60/minuteIntervals)
                for j in range(60//minuteIntervals):
                    simRun.addHWGen(hw_gen_for_interval)
        
    
    def getOffTriggerVolume(self, ls_mode):
        if ls_mode == 'S':
            return self.offFractShed * self.PVol_G_atStorageT
        elif ls_mode == 'L':
            return self.offFractLoadUp * self.PVol_G_atStorageT
        return self.offFract * self.PVol_G_atStorageT
    
    def getOnTriggerVolume(self, ls_mode):
        if ls_mode == 'S':
            return self.onFractShed * self.PVol_G_atStorageT
        elif ls_mode == 'L':
            return self.onFractLoadUp * self.PVol_G_atStorageT
        return self.onFract * self.PVol_G_atStorageT
    
    def getOffTriggerTemp(self, ls_mode):
        if ls_mode == 'S':
            return self.offShedT
        elif ls_mode == 'L':
            return self.offLoadUpT
        return self.offT
    
    def getOnTriggerTemp(self, ls_mode):
        if ls_mode == 'S':
            return self.onShedT
        elif ls_mode == 'L':
            return self.onLoadUpT
        return self.onT
    
    def getStorageOutletTemp(self, ls_mode):
        if ls_mode == 'L':
            return self.outletLoadUpT
        return self.storageT_F
    
    def getWaterDraw(self, demand_at_supply : float, storage_temp : float, supply_temp : float, incoming_water_temp : float, delta_energy : float, 
                     ls_mode : str, potential_generation : float = 0.0, water_draw_interval : float = 1) -> float:
        hw_load_at_storageT = convertVolume(demand_at_supply, storage_temp, incoming_water_temp, supply_temp)
        lowest_storage_vol = min(self.getTankVolAtTemp(storage_temp, delta_energy), self.PVol_G_atStorageT)
        storage_temp_vol = self.PVol_G_atStorageT - lowest_storage_vol + potential_generation
        if storage_temp_vol >= hw_load_at_storageT:
            return hw_load_at_storageT
        else:
            supplyT_demand_covered = max(0, convertVolume(storage_temp_vol, supply_temp, incoming_water_temp, storage_temp)) # max of 0 in case storage_temp_vol is negative
            remaining_demand = demand_at_supply - supplyT_demand_covered
            gallons_removed_from_storage = max(0, storage_temp_vol)
            gallons_added = 0
            while remaining_demand > 0:
                gallons_added = gallons_added + water_draw_interval
                top_of_tank_temp = self.getTemperatureAtTankVol(
                    tank_volume=self.PVol_G_atStorageT - (gallons_removed_from_storage + gallons_added),
                    incomingT_F=incoming_water_temp,
                    ls_mode=ls_mode,
                    delta_energy=delta_energy + potential_generation
                )
                if top_of_tank_temp < supply_temp:
                    raise Exception(f"DHW storage dropped below supply temperature. The system is undersized.") # TODO this doesn't account for heating though.
                galsAtSupply = convertVolume(water_draw_interval, supply_temp, incoming_water_temp, top_of_tank_temp)
                remaining_demand = remaining_demand - galsAtSupply
                if remaining_demand < 0:
                    gallons_added = gallons_added + (galsAtSupply*(remaining_demand/galsAtSupply)) # account for overdraw
                    remaining_demand = 0
            return gallons_removed_from_storage + gallons_added

    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None):
        incomingWater_T = simRun.getIncomingWaterT(i)
        ls_mode = simRun.getLoadShiftMode(i)
        self.preSystemStepSetUp(simRun, i, incomingWater_T, minuteIntervals, oat)
        storage_outlet_temp = self.getStorageOutletTemp(ls_mode) # TODO possible redistribution of stratification?
        possible_storage_generation = convertVolume(simRun.hwGenRate, storage_outlet_temp, incomingWater_T, simRun.building.supplyT_F)
        water_draw = self.getWaterDraw(simRun.hwDemand[i], storage_outlet_temp, simRun.building.supplyT_F, incomingWater_T, simRun.delta_energy, ls_mode,
                                       potential_generation=possible_storage_generation)
        self.runOnePrimaryStep(simRun, i, water_draw, incomingWater_T)

    def runOnePrimaryStep(self, simRun : SimulationRun, i : int, hw_load_at_storageT : float, entering_waterT : float, erCalc : bool = False):
        """
        Runs one step on the primary system. This changes the volume of the primary system
        by assuming there is hot water removed at a volume of hw_out and hot water
        generated or added at a volume of hw_in. This is assuming the system is perfectly
        stratified and all of the hot water above the cold temperature is at the storage temperature.

        Parameters
        ----------
        pheating : boolean
            indicates whether system is heating at the beginning of this step
        Vfull : float
            The maximum volume of the primary system at the storage temperature
        Vtrig : float
            The remaining volume of the primary storage volume when heating is
            triggered, note this equals V0*(1 - onFract) 
        Vcurr : float
            The primary volume at the beginning of the interval.
        hw_out : float
            The volume of DHW removed from the primary system at storage temp, assumed that
            100% of what of what is removed is replaced
        hw_in : float
            The volume of hot water that could be generated in a time step at storage temp if the primary tank was running the entire time
        Vtrig_previous : float
            Trigger from last time step to see if we missed any heating (may have changed if doing load shifting)

        Returns
        -------
        pheating : boolean
            Boolean indicating if the primary system is heating at the end of this step in the simulation 
        Vnew : float
            The new primary volume at the timestep.
        hw_generated : float
            The volume of hot water generated during the time step.
        time_ran : 
            The amount of time the primary tank ran

        """
        ls_mode = simRun.getLoadShiftMode(i)
        if i > 0 and ls_mode != simRun.getLoadShiftMode(i-1):
            simRun.pheating = False # reset primary heating when mode changes per NEEA sequence of operations

        storage_outlet_temp = self.getStorageOutletTemp(ls_mode) # TODO possible redistribution of stratification?
        simRun.delta_energy = simRun.delta_energy - hw_load_at_storageT
        simRun.pOnV[i] = self.getOnTriggerVolume(ls_mode)
        simRun.pOnT[i] = self.getOnTriggerTemp(ls_mode)
        simRun.pOffV[i] = self.getOffTriggerVolume(ls_mode)
        simRun.pOffT[i] = self.getOffTriggerTemp(ls_mode)
        simRun.hwDamandAtStorage[i] = hw_load_at_storageT

        if simRun.pheating:
            # add heat
            simRun.pRun[i] = 1.0
            delta_heat = convertVolume(simRun.hwGenRate, storage_outlet_temp, entering_waterT, simRun.building.supplyT_F)
            simRun.delta_energy = simRun.delta_energy + delta_heat
            if self.getTemperatureAtTankVol(simRun.pOffV[i], entering_waterT, ls_mode, simRun.delta_energy) >= simRun.pOffT[i]:
                simRun.pheating = False
                lowest_vol = self.getTankVolAtTemp(simRun.pOffT[i], simRun.delta_energy)
                if lowest_vol < simRun.pOffV[i]:
                    extra_generation = simRun.pOffV[i] - lowest_vol
                    extra_gen_percent = min(extra_generation/delta_heat, 1.0) # maximum of 1 time step of generation
                    simRun.pRun[i] = 1.0 - extra_gen_percent
                    simRun.delta_energy = simRun.delta_energy - (delta_heat * extra_gen_percent)
            simRun.pGen[i] = simRun.pRun[i] * delta_heat
        else:
            simRun.pRun[i] = 0.0
            if self.getTemperatureAtTankVol(simRun.pOnV[i], entering_waterT, ls_mode, simRun.delta_energy) <= simRun.pOnT[i]:
                simRun.pheating = True
                highest_vol = self.getTankVolAtTemp(simRun.pOnT[i], simRun.delta_energy)
                if highest_vol > simRun.pOnV[i]:
                    extra_loss = highest_vol - simRun.pOnV[i]
                    gen_percent = 1.0
                    if hw_load_at_storageT > 0:
                        gen_percent = min(extra_loss/hw_load_at_storageT, 1.0) # maximum of 1 time step of generation
                    simRun.pRun[i] = gen_percent
                    delta_heat = gen_percent * convertVolume(simRun.hwGenRate, storage_outlet_temp, entering_waterT, simRun.building.supplyT_F)
                    simRun.pGen[i] = delta_heat 
                    simRun.delta_energy = simRun.delta_energy + delta_heat
        
        simRun.pRun[i] = simRun.pRun[i] * simRun.minuteIntervals
        simRun.pV[i] = (self.PVol_G_atStorageT - self.getTankVolAtTemp(simRun.building.supplyT_F, simRun.delta_energy)) / self.strat_factor
        simRun.pTAtOn[i] = self.getTemperatureAtTankVol(simRun.pOnV[i], entering_waterT, ls_mode, simRun.delta_energy)
        simRun.pTAtOff[i] = self.getTemperatureAtTankVol(simRun.pOffV[i], entering_waterT, ls_mode, simRun.delta_energy)

        simRun.tempAt100[i] = self.getTemperatureAtTankVol(self.PVol_G_atStorageT, entering_waterT, ls_mode, simRun.delta_energy)
        simRun.tempAt75[i] = self.getTemperatureAtTankVol(self.PVol_G_atStorageT * 0.75, entering_waterT, ls_mode, simRun.delta_energy)
        simRun.tempAt50[i] = self.getTemperatureAtTankVol(self.PVol_G_atStorageT * 0.5, entering_waterT, ls_mode, simRun.delta_energy)
        simRun.tempAt25[i] = self.getTemperatureAtTankVol(self.PVol_G_atStorageT * 0.25, entering_waterT, ls_mode, simRun.delta_energy)
        simRun.tempAt0[i] = self.getTemperatureAtTankVol(0, entering_waterT, ls_mode, simRun.delta_energy)
        simRun.setpointPercentOn[i] = simRun.pOnV[i]/self.PVol_G_atStorageT
        simRun.setpointPercentOff[i] = simRun.pOffV[i]/self.PVol_G_atStorageT

        if simRun.pV[i] <= 0 and not erCalc:
            raise Exception("Primary storage ran out of Volume!")
        if simRun.pRun[i] < 0:
            raise Exception("Internal system error. time_ran was negative")


    def getTemperatureAtTankVol(self, tank_volume : float, incomingT_F : float, ls_mode : str = 'N', delta_energy : float = 0) -> float:
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
        temp = self.strat_slope * (tank_volume + delta_energy) + self.strat_inter
        if temp < incomingT_F:
            return incomingT_F
        elif temp > self.getStorageOutletTemp(ls_mode): #TODO make sure this is right (Ask Scott)
            return self.getStorageOutletTemp(ls_mode)
        return temp
    
    def getTankVolAtTemp(self, temp, delta_energy : float = 0) -> float:
        """
        Returns
        -------
        tank_vol : float
            the lowest volume on the tank where the water is storage temperature
        """
        tank_vol = ((temp - self.strat_inter) / self.strat_slope) - delta_energy
        return tank_vol
    
    def _setLoadShift(self, loadShiftSchedule, loadUpHours, onFract, offFract, onT, offT, outletLoadUpT, onFractLoadUp, 
                      offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT, loadShiftPercent=1):
        """
        Sets the load shifting schedule from input loadShiftSchedule

        Parameters
        ----------
        loadShiftSchedule : array_like
            List or array of 0's, 1's used for load shifting, 0 indicates system is off. 
        loadUpHours : float
            Number of hours spent loading up for first shed.
        onFract: float
            The fraction of the total height of the primary hot water tanks at which the ON temperature sensor is located.
        offFract : float
            The fraction of the total height of the primary hot water tanks at which the OFF temperature is located (defaults to onFract if not specified)
        onT : float
            The temperature detected at the onFract at which the HPWH system will be triggered to turn on. (defaults to supplyT_F if not specified)
        offT : float
            The temperature detected at the offFract at which the HPWH system will be triggered to turn off. (defaults to storageT_F if not specified)
        outletLoadUpT : float
        onFractLoadUp : float
            The fraction of the total height of the primary hot water tanks at which the ON temperature sensor is located during load up periods. (defaults to onFract if not specified)
        offFractLoadUp : float
            The fraction of the total height of the primary hot water tanks at which the OFF temperature sensor is located during load up periods. (defaults to offFract if not specified)
        onLoadUpT : float
            The temperature detected at the onFractLoadUp at which the HPWH system will be triggered to turn on during load up periods. (defaults to onT if not specified)
        offLoadUpT : float
            The temperature detected at the offFractLoadUp at which the HPWH system will be triggered to turn off during load up periods. (defaults to offT if not specified)
        onFractShed : float
            The fraction of the total height of the primary hot water tanks at which the ON temperature sensor is located during shed periods. (defaults to onFract if not specified)
        offFractShed : float
            The fraction of the total height of the primary hot water tanks at which the OFF temperature is located during shed priods (defaults to offFract if not specified)
        onShedT : float
            The temperature detected at the onFractShed at which the HPWH system will be triggered to turn on during shed periods. (defaults to onT if not specified)
        offShedT : float
            The temperature detected at the offFractShed at which the HPWH system will be triggered to turn off during shed periods. (defaults to offT if not specified)
        loadShiftPercent : float
            Percentile of days which need to be covered by load shifting

        """
        # Check
        if not(isinstance(loadShiftSchedule, list)):
            raise Exception("Invalid input given for schedule, must be an array of length 24.")
        if len(loadShiftSchedule) != 24: 
            raise Exception("Load shift is not of length 24 but instead has length of "+str(len(loadShiftSchedule))+".")
        if not all(i in [0,1] for i in loadShiftSchedule):
            raise Exception("Loadshift schedule must be comprised of 0s, 1s, and 2s for shed, normal, and load up operation.")
        if sum(loadShiftSchedule) == 0 :
            raise Exception("When using Load shift the HPWH's must run for at least 1 hour each day.")
        if loadShiftPercent < 0.25 :
            raise Exception("Load shift only available for above 25 percent of days.")
        if loadShiftPercent > 1 :
            raise Exception("Cannot load shift for more than 100 percent of days")
        
        if onFractLoadUp is None: onFractLoadUp = onFract
        if onFractShed is None: onFractShed = onFract
        if offFractLoadUp is None: offFractLoadUp = onFractLoadUp
        if offFractShed is None: offFractShed = onFractShed
        if offShedT is None: offShedT = offT
        if offLoadUpT is None: offLoadUpT = offT
        if onShedT is None: onShedT = onT
        if onLoadUpT is None: onLoadUpT = onT
        if outletLoadUpT is None: outletLoadUpT = self.storageT_F

        if not (isinstance(onFractLoadUp, int) or isinstance(onFractLoadUp, float)) or onFractLoadUp > onFract or onFractLoadUp <= 0:
            raise Exception("Invalid input given for load up ON fraction, must be a number between 0 and normal ON fraction.")
        if not (isinstance(onFractShed, int) or isinstance(onFractShed, float)) or onFractShed >= 1 or onFractShed < onFract:
            raise Exception("Invalid input given for shed ON fraction, must be a number between normal ON fraction and 1.")
        
        if not (isinstance(offFractLoadUp, int) or isinstance(offFractLoadUp, float)) or offFractLoadUp > offFract or offFractLoadUp <= 0:
            raise Exception("Invalid input given for load up OFF fraction, must be a number between 0 and normal OFF fraction.")
        if not (isinstance(offFractShed, int) or isinstance(offFractShed, float)) or offFractShed >= 1 or offFractShed < offFract:
            raise Exception("Invalid input given for shed ON fraction, must be a number between normal ON fraction and 1.")
        
        if not (isinstance(onLoadUpT, int) or isinstance(onLoadUpT, float)) or not checkLiqudWater(onLoadUpT):
            raise Exception("Invalid input given for load up ON temp, it must be a number between 32F and 212F.")
        if not (isinstance(onShedT, int) or isinstance(onShedT, float)) or not checkLiqudWater(onShedT):
            raise Exception("Invalid input given for shed ON temp, it must be a number between 32F and 212F.")
        
        if not (isinstance(offLoadUpT, int) or isinstance(offLoadUpT, float)) or not checkLiqudWater(offLoadUpT):
            raise Exception(f"Invalid input given for load up OFF temp, it must be a number between 32F and 212F.")
        if not (isinstance(offShedT, int) or isinstance(offShedT, float)) or not checkLiqudWater(offShedT):
            raise Exception("Invalid input given for shed OFF temp, it must be a number between 32F and 212F.")
        
        if not (isinstance(outletLoadUpT, int) or isinstance(outletLoadUpT, float)) or outletLoadUpT < self.storageT_F or not checkLiqudWater(offShedT):
            raise Exception("Invalid input given for load up storage temp, it must be a number between normal storage temp and 212F.")
        
        if not (isinstance(loadUpHours, int)) or loadUpHours > loadShiftSchedule.index(0): #make sure there are not more load up hours than nhours before first shed
            raise Exception("Invalid input given for load up hours, must be an integer less than or equal to hours in day before first shed period.") 

        self.loadShiftSchedule = loadShiftSchedule
        self.loadUpHours = loadUpHours
        
        self.offFractLoadUp = offFractLoadUp
        self.offFractShed = offFractShed
        self.onFractLoadUp = onFractLoadUp
        self.onFractShed = onFractShed
        self.offShedT = offShedT
        self.offLoadUpT = offLoadUpT
        self.onShedT = onShedT
        self.onLoadUpT = onLoadUpT
        self.outletLoadUpT = outletLoadUpT
        
        # adjust for cdf_shift
        if loadShiftPercent == 1: # meaing 100% of days covered by load shift
            self.fract_total_vol = 1
            
        else:
            # calculate fraction total hot water required to meet load shift days
            fract = norm_mean + norm_std * norm.ppf(loadShiftPercent) #TODO norm_mean and std are currently from multi-family, need other types eventually. For now, loadshifting will only be available for multi-family
            self.fract_total_vol = fract if fract <= 1. else 1.
        
        self.loadShiftPercent = loadShiftPercent
        self.doLoadShift = True

    def _primaryHeatHrs2kBTUHR(self, heathours, loadUpHours, building : Building, primaryCurve = False, effSwingVolFract=1, lsFractTotalVol = 1):
        """
        Converts from hours of heating in a day to heating capacity. If loadshifting compares this method to capacity needed to load up
        and takes maximum.

        Implimented seperatly in Swing Tank systems

        Parameters
        ----------
        heathours : float or numpy.ndarray
            The number of hours primary heating equipment can run.
        loadUpHours : float
            Number of hours spent loading up for first shed.
        building : Building
            The building the system being sized for
        primaryCurve : Bool
            Indicates that function is being called to generate the priamry
            sizing curve. This overrides LS sizing and sizes with "normal"
            sizing (default = False)
        effSwingVolFract : float or numpy.ndarray
            The fractional adjustment to the total hot water load for the
            primary system. Only used in a swing tank system.

        Returns
        -------
        heatCap
            The heating capacity in [kbtu/hr].
        genRate
            The generation rate in [gal/hr] when the heat pump is on. 
            If loadshifting this is the maximum between normal calculation
            and what is necessary to complete first load up.
        """
        checkHeatHours(heathours)
        genRate = building.magnitude * effSwingVolFract / heathours
        
        if self.doLoadShift and not primaryCurve:
            Vshift, VconsumedLU = self._calcPrelimVol(loadUpHours, building.avgLoadshape, building, lsFractTotalVol)
            strat_percent_of_tank = self.getStratificationFactor(self.onFract, self.onT, building.supplyT_F, self.storageT_F, as_percent_of_tank=True)
            lu_on_percent_of_tank = self.getStratificationFactor(self.onFractLoadUp, self.onLoadUpT, building.supplyT_F, self.storageT_F, as_percent_of_tank=True)
            shd_on_percent_of_tank = self.getStratificationFactor(self.onFractShed, self.onShedT, building.supplyT_F, self.storageT_F, as_percent_of_tank=True)
            # Vload = Vshift * (self.onFract - self.onFractLoadUp) / (self.onFractShed - self.onFractLoadUp) #volume in 'load up' portion of tank
            Vload = Vshift * (lu_on_percent_of_tank - strat_percent_of_tank) / (lu_on_percent_of_tank - shd_on_percent_of_tank) #volume in 'load up' portion of tank
            
            LUgenRate = (Vload + VconsumedLU) / loadUpHours #rate needed to load up tank and offset use during load up period
            #compare with original genRate
            genRate = max(LUgenRate, genRate)
            
        heatCap = genRate * rhoCp * \
            (building.supplyT_F - building.getLowestIncomingT_F()) / self.defrostFactor / 1000
       
        return heatCap, genRate
    
    def setStratificationPercentageSlope(self):
        self.stratPercentageSlope = 2.8 # degrees F per percentage point of volume on tank 

    def getStratificationFactor(self, aquafraction : float, tempSetpoint : float, supplyTemp : float, storageTemp : float, as_percent_of_tank : bool = False) -> float:
        """
        Calculates the stratification factor for the tank based on temperature distribution
        and aquastat position.

        Parameters
        ----------
        aquafraction : float
            The aquastat position as a fraction of tank volume (must be between 0 and 1)
        tempSetpoint : float
            The temperature setpoint in degrees Fahrenheit
        supplyTemp : float
            The supply temperature in degrees Fahrenheit
        storageTemp : float
            The storage temperature in degrees Fahrenheit
        as_percent_of_tank : bool
            Returns as a percentage of water in the tank is at or above supply temp at specified 
            setpoint trigger instead of simple stratification factor

        Returns
        -------
        float
            The stratification factor representing the ratio of effective volume above
            supply temperature to total volume above the aquastat position
        """
        #TODO might be useful to add more boundaries
        if aquafraction >= 1 or aquafraction <= 0:
            raise Exception(f"Aquastat fraction of {aquafraction} is not valid. Must be a float between 0 and 1.") 
        elif aquafraction < round(1.0-self.percentUseable, 4):
            raise Exception(f"Aquaustat fraction of {aquafraction} is unreachable because the bottom {(1.0-self.percentUseable)*100}% of the tank is unusable.")
        aquaPercent = aquafraction * 100
        tank_height_of_supply = aquaPercent + ((supplyTemp - tempSetpoint) / self.stratPercentageSlope)
        tank_height_of_storage = aquaPercent + ((storageTemp - tempSetpoint) / self.stratPercentageSlope)
        if tank_height_of_storage > 100: tank_height_of_storage = 100
        vol_storage_temp = (100 - tank_height_of_storage) * (storageTemp - supplyTemp)
        vol_above_supply = vol_storage_temp + (((tank_height_of_storage - tank_height_of_supply) * (storageTemp - supplyTemp))/2)
        stratification_factor = vol_above_supply/((100 - aquaPercent) * (storageTemp - supplyTemp))
        if as_percent_of_tank:
            return stratification_factor * (1 - aquafraction)
        return stratification_factor

    def sizeStagedCapacity(self, building : Building, totalVolAtStorage : float, offFraction : float, offTemperature : float):
        cyclingVol_G = totalVolAtStorage * (offFraction - (1 - self.percentUseable))
        genRate = cyclingVol_G / pCompMinimumRunTime
        maxCyclingCapacity_kBTUhr = genRate * rhoCp * \
            (offTemperature - building.getLowestIncomingT_F()) / self.defrostFactor / 1000 # TODO check this
        return maxCyclingCapacity_kBTUhr
    
    def sizePrimaryTankVolume(self, heatHrs, loadUpHours, building : Building, primaryCurve = False, lsFractTotalVol = 1.):
        """
        Calculates the primary storage using the Ecotope sizing methodology. Function is also used
        to generate primary sizing curve, which creates a curve with no load shifting and points
        with varying numbers of load up hours.

        Parameters
        ----------
        heatHrs : float
            The number of hours primary heating equipment can run in a day.
        loadUpHours : float
            Number of hours spent loading up for first shed.
        building : Building
            the building object the primary tank is being sized for.
        primaryCurve : Bool
            Indicates that function is being called to generate the priamry
            sizing curve. This overrides LS sizing and sizes with "normal"
            sizing (default = False)
        
        Raises
        ------
        ValueError: aquastat fraction is too low.
        ValueError: The minimum aquastat fraction is greater than 1.

        Returns
        -------
        totalVolMax : float
            The total storage volume in gallons adjusted to the storage tempreature
        effMixFract : float
            The fractional adjustment to the total hot water load for the
            primary system. Only used in a swing tank system.
        
        """
        if heatHrs <= 0 or heatHrs > 24:
            raise Exception("Heat hours is not within 1 - 24 hours")
        # Fraction used for adjusting swing tank volume.
        effMixFract = 1.
        minRunVol_G = pCompMinimumRunTime * (building.magnitude / heatHrs) # (generation rate - no usage) #REMOVED EFFMIXFRACT

        # Running vol
        runningVol_G, effMixFract = self._calcRunningVol(heatHrs, np.ones(24), building.loadshape, building, effMixFract)

        totalVolAtStorage = convertVolume(runningVol_G, self.storageT_F, building.getDesignInlet(), building.supplyT_F)
        strat_percent_of_tank = self.getStratificationFactor(self.onFract, self.onT, building.supplyT_F, self.storageT_F, as_percent_of_tank=True) 
        # print(f"strat_percent_of_tank is {strat_percent_of_tank} totalVolAtStorage is {totalVolAtStorage}")
        totalVolAtStorage *=  thermalStorageSF
        totalVolAtStorage = totalVolAtStorage/strat_percent_of_tank # Volume needed without loadshifting

        strat_percent_of_tank_off = self.getStratificationFactor(self.offFract, self.offT, building.supplyT_F, self.storageT_F, as_percent_of_tank=True)
        cyclingVol_G = totalVolAtStorage * (strat_percent_of_tank_off - strat_percent_of_tank) 

        if self.doLoadShift and not primaryCurve:
            LSrunningVol_G, LSeffMixFract = self._calcRunningVolLS(loadUpHours, building.avgLoadshape, building, effMixFract, lsFractTotalVol = lsFractTotalVol)
            lu_on_percent_of_tank = self.getStratificationFactor(self.onFractLoadUp, self.onLoadUpT, building.supplyT_F, self.storageT_F, as_percent_of_tank=True)
            shd_on_percent_of_tank = self.getStratificationFactor(self.onFractShed, self.onShedT, building.supplyT_F, self.storageT_F, as_percent_of_tank=True)
            ls_strat_percent_of_tank = lu_on_percent_of_tank - shd_on_percent_of_tank
            totalVolAtStorage_ls = convertVolume(LSrunningVol_G, self.storageT_F, building.getDesignInlet(), building.supplyT_F)
            totalVolAtStorage_ls *=  thermalStorageSF 
            totalVolAtStorage_ls = totalVolAtStorage_ls/ls_strat_percent_of_tank # Volume needed for loadshifting
            
            # Get total volume from max of primary method or load shift method
            if totalVolAtStorage_ls > totalVolAtStorage:
                totalVolAtStorage = totalVolAtStorage_ls
                effMixFract = LSeffMixFract

            lu_off_percent_of_tank = self.getStratificationFactor(self.offFractLoadUp, self.offLoadUpT, building.supplyT_F, self.storageT_F, as_percent_of_tank=True)
            LUcyclingVol_G = totalVolAtStorage * (lu_off_percent_of_tank - lu_on_percent_of_tank)
            
            if cyclingVol_G > LUcyclingVol_G:
                cyclingVol_G = LUcyclingVol_G

        if minRunVol_G > cyclingVol_G:
            self.cycle_percent = cyclingVol_G/minRunVol_G

        if building.getMinimumVolume() > totalVolAtStorage:
            raise Exception("ERROR ID 04","The sized volume is smaller than the minimum required volume for the building. Please increasing the hours the heat pump runs in a day to ensure adequate volume.",)

        return totalVolAtStorage, effMixFract
    
    def _calcMinCyclingVol(self, building : Building, heatHrs):
        return pCompMinimumRunTime * (building.magnitude / heatHrs)
    
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
        genRate = np.tile(onOffArr,2) / heatHrs #hourly
        diffN = genRate - np.tile(loadshape,2) #hourly
        diffInd = getPeakIndices(diffN[0:24]) #Days repeat so just get first day!
        diffN *= building.magnitude
        
        # Get the running volume ##############################################
        if len(diffInd) == 0:
            raise Exception("ERROR ID 03","The heating rate is greater than the peak volume the system is oversized! Try increasing the hours the heat pump runs in a day",)
        runV_G = 0
        for peakInd in diffInd:
            #Get the rest of the day from the start of the peak
            diffCum = np.cumsum(diffN[peakInd:])  #hourly
            runV_G = max(runV_G, -min(diffCum[diffCum<0.])) #Minimum value less than 0 or 0.
        return runV_G, effMixFract
    
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
        Vshift = self._calcPrelimVol(loadUpHours, loadshape, building, lsFractTotalVol = lsFractTotalVol)[0] #volume to make it through first shed
        
        genRateON = self._primaryHeatHrs2kBTUHR(self.maxDayRun_hr, loadUpHours, building, effSwingVolFract = effMixFract, primaryCurve = False, lsFractTotalVol = lsFractTotalVol)[1] #max generation rate from both methods
        genRate = [genRateON if x != 0 else 0 for x in self.loadShiftSchedule] #set generation rate during shed to 0
        genRate = np.tile(genRate, 2)
        
        diffN = genRate - np.tile(loadshape,2) * building.magnitude
        
        #get first index after shed
        shedEnd = [i for i,x in enumerate(genRate[1:],1) if x > genRate[i-1]][0] #start at beginning of first shed, fully loaded up equivalent to starting at the end of shed completely "empty"
        diffCum = np.cumsum(diffN[shedEnd:]) 
        LSrunV_G = -min(diffCum[diffCum<0.], default = 0) * lsFractTotalVol #numbers less than 0 are a hot water deficit, find the biggest deficit. if no deficit then 0.
        # TODO do we want to multiply LSrunV_G by lsFractTotalVol? that isn't really affected by cdf

        #add running volume to preliminary shifted volume
        LSrunV_G += Vshift
        
        return LSrunV_G, effMixFract 

    def _getTotalVolAtStorage(self, runningVol_G, incomingT_F, supplyT_F):
        """
        Calculates the maximum primary storage using the Ecotope sizing methodology. Swing Tanks implement sperately.

        Parameters
        ----------
        runningVol_G : float
            The running volume in gallons
        incomingT_F : float
            Incoming temp (in Fahrenhiet) of city water
        supplyT_F : float
            Supply temp (in Fahrenhiet) of water distributed to those in the building

        Returns
        -------
        totalVolMax : float
            The total storage volume in gallons adjusted to the storage tempreature.
        
        """
        
        return convertVolume(runningVol_G, self.storageT_F, incomingT_F, supplyT_F) / (1 - self.onFract)
    
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
        # Define the heating hours we'll check
        delta = -0.25
        maxHeatHours = 1/(max(building.loadshape))*1.001   
        arr1 = np.arange(24, self.maxDayRun_hr, delta) #TODO why are we going all the way to 24 hours ???
        recIndex = len(arr1)
        heatHours = np.concatenate((arr1, np.arange(self.maxDayRun_hr, maxHeatHours, delta)))
        
        volN = np.zeros(len(heatHours))
        effMixFract = np.ones(len(heatHours))
        for i in range(0,len(heatHours)):
            try:
                volN[i], effMixFract[i] = self.sizePrimaryTankVolume(heatHours[i], self.loadUpHours, building, primaryCurve = True, lsFractTotalVol = self.fract_total_vol)
            except ValueError:
                break
            except Exception as ex:
                if ex.args[0] == 'ERROR ID 03' or ex.args[0] == 'ERROR ID 04': # max hour/day generation is larger than peak
                    break
                else:
                    raise ex
        # Cut to the point the aquastat fraction was too small
        volN        = volN[:i]
        heatHours   = heatHours[:i]
        effMixFract = effMixFract[:i]

        return [volN, self._primaryHeatHrs2kBTUHR(heatHours, self.loadUpHours, building, 
            effSwingVolFract = effMixFract, primaryCurve = True, lsFractTotalVol = self.fract_total_vol)[0], heatHours, recIndex]

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
        if not self.doLoadShift:
            raise Exception("lsSizedPoints() only applicable to systems with load shifting.")
        
        volN = []
        capN = []
        effMixN = []
        N = []

        #load up hours to loop through
        i = 100
        # try:
        while i >= 25: #arbitrary stopping point, anything more than this will not result in different sizing
            #size the primary system based on the number of load up hours
            fract = norm_mean + norm_std * norm.ppf(i/100) #TODO norm_mean and std are currently from multi-family, need other types eventually. For now, loadshifting will only be available for multi-family
            fract = fract if fract <= 1. else 1.
            volN_i, effMixN_i = self.sizePrimaryTankVolume(heatHrs = self.maxDayRun_hr, loadUpHours = self.loadUpHours, building = building, primaryCurve = False, lsFractTotalVol = fract)
            volN.append(volN_i)
            effMixN.append(effMixN_i)
            capN.append(self._primaryHeatHrs2kBTUHR(self.maxDayRun_hr, self.loadUpHours, building, effSwingVolFract = effMixN_i, primaryCurve = False, lsFractTotalVol = fract)[0])
            N.append(i)
            i -= 1

        # except Exception:
    
        return [volN, capN, N, int(np.ceil((self.loadShiftPercent * 100)-25))]
    

    def getPrimaryCurveAndSlider(self, x, y, startind, y2 = None, returnAsDiv = True, lsPoints = None): #getPrimaryCurveAndSlider
        """
        Function to plot the the x and y curve and create a point that moves up
        and down the curve with a slider bar 

        Args
        --------
        x : array
            The x data
        y : array
            The y data
        startind : ind
            The index that the initial point starts on
        
        Returns
        --------
        plotdiv : a plotly div of the graph
        
        
        """
        fig = createSizingCurvePlot(x, y, startind, loadshifting = self.doLoadShift)
    
        # Create and add sliderbar steps
        steps = []
        for i in range(1,len(fig.data)):
        
            labelText = "Storage: "+("<b id='point_y'>" if self.doLoadShift else "<b id='point_x'>") + str(float(x[i-1] if not self.doLoadShift else y[i-1])) + "</b> Gal, Capacity: "+ \
                ("<b>" if self.doLoadShift else "<b id='point_y'>") + \
                str(round(y[i-1],1) if not self.doLoadShift else round(self.PCap_kBTUhr,2)) + "</b> kBTU/hr" 
            if y2 is not None:
                if self.doLoadShift:
                    labelText += ", Percent Load Shift Days Covered: <b id='point_x'>" + str(float(y2[i-1])) + "</b> %"
                else:
                    labelText += ", Compressor Runtime: <b>" + str(float(y2[i-1])) + "</b> hr" 
        
            step = dict(
                # this value must match the values in x = loads(form['x_data']) #json loads
                label = labelText,
                method="update",
                args=[{"visible": [False] * len(fig.data)},
                    ],  # layout attribute
            )
            step["args"][0]["visible"][0] = True  # Make sure first trace is visible since its the line
            step["args"][0]["visible"][i] = True  # Toggle i'th trace to "visible"
            steps.append(step)

        sliders = [dict(    
            steps=steps,
            active=startind,
            currentvalue=dict({
                'font': {'size': 16},
                'prefix': '<b>Primary System Size</b>, ',
                'visible': True,
                'xanchor': 'left'
                }), 
            pad={"t": 50},
            minorticklen=0,
            ticklen=0,
            bgcolor= "#CCD9DB",
            borderwidth = 0,
        )]
    
        fig.update_layout(
            sliders=sliders
        )

        if returnAsDiv:
            plot_div = plot(fig, output_type='div', show_link=False, link_text="",
                    include_plotlyjs = False)
            return plot_div
    
        return fig

    
    def _calcPrelimVol(self, loadUpHours, loadshape, building : Building, lsFractTotalVol = 1):
        '''
        Function to calculate volume shifted during first shed period, which is used to calculated generation rate
        needed for load up.

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
            Volume at supply temp between normal and load up AQ fract needed to make it through first shed period.
        VconsumedLU : float
            Volume at supply temp consumed during first load up period.
        '''
        shedHours = [i for i in range(len(self.loadShiftSchedule)) if self.loadShiftSchedule[i] == 0] #get all scheduled shed hours
        firstShed = [x for i,x in enumerate(shedHours) if x == shedHours[0] + i] #get first shed
        Vshift = sum([loadshape[i]*building.magnitude for i in firstShed]) * lsFractTotalVol #calculate vol used during first shed multiplied by cdf
        VconsumedLU = sum(loadshape[firstShed[0] - loadUpHours : firstShed[0]]) * building.magnitude
        
        return Vshift, VconsumedLU
    
class Primary(SystemConfig):
    def __init__(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building, outletLoadUpT,
                 onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, systemModel = None, 
                 numHeatPumps = None, PVol_G_atStorageT = None, PCap_kBTUhr = None, useHPWHsimPrefMap = False):
        
        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building, outletLoadUpT,
                 onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT, 
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                 PCap_kBTUhr, useHPWHsimPrefMap)


