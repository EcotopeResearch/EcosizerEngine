from ecoengine.objects.SystemConfig import SystemConfig
from ecoengine.objects.SimulationRun import SimulationRun
from ecoengine.constants.Constants import *
from ecoengine.objects.Building import Building
import numpy as np
from ecoengine.objects.systemConfigUtils import convertVolume, getPeakIndices, hrTo15MinList

class SPRTP(SystemConfig): # Single Pass Return to Primary (SPRTP)
    def __init__(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building : Building = None, outletLoadUpT = None,
                 onFractLoadUp = None, offFractLoadUp = None, onLoadUpT = None, offLoadUpT = None, onFractShed = None, offFractShed = None, onShedT = None, offShedT = None,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, 
                 PCap_kBTUhr = None, useHPWHsimPrefMap = False, stratFactor = 1):

        if stratFactor > 1 or stratFactor <= 0: 
            raise Exception('Stratificationfactor must be greater than zero and less than or equal to 1.')
        
        self.strat_factor = stratFactor
        self.Recirc_Cap_kBTUhr = None
        self.tm_hourly_load = building.getHourlyLoadIncrease()
        
        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                 outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT, 
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                 PCap_kBTUhr, useHPWHsimPrefMap)

    def setStratificationPercentageSlope(self):
        self.stratPercentageSlope = 1.7 # degrees F per percentage point of volume on tank 

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
        recirc_vol_in_cw_per_hr = building.recirc_loss / ((rhoCp) * (building.supplyT_F - building.getLowestIncomingT_F()))
        recirc_only_model = Building(
            magnitude=recirc_vol_in_cw_per_hr * 24,
            loadshape= [.1/.24] * 24,
            avgLoadshape= [.1/.24] * 24,
            incomingT_F=building.getLowestIncomingT_F(),
            supplyT_F=building.supplyT_F,
            returnT_F=None,
            flowRate=None,
            climate=None,
            ignoreRecirc=True,
            designOAT_F=None
        )

        recirc_Cap_kBTUhr, genRate_from_return = super()._primaryHeatHrs2kBTUHR(heathours, loadUpHours, recirc_only_model, primaryCurve,
            effSwingVolFract, lsFractTotalVol)
        
        usage_Cap_kBTUhr, genRate_from_cW = super()._primaryHeatHrs2kBTUHR(heathours, loadUpHours, building, primaryCurve,
            effSwingVolFract, lsFractTotalVol)
        
        heatCap = usage_Cap_kBTUhr + recirc_Cap_kBTUhr
        genRate_supply = genRate_from_cW + genRate_from_return
        return heatCap, genRate_supply
    
    def _getIntegratedLoadshapeAndMagnitude(self, loadshape, building : Building):
        recirc_vol_in_cw_per_hr = building.recirc_loss / ((rhoCp) * (building.supplyT_F - building.getLowestIncomingT_F()))
        day_load = [(x * building.magnitude) + recirc_vol_in_cw_per_hr for x in loadshape]
        new_magnitude = building.magnitude + (recirc_vol_in_cw_per_hr * 24)
        new_loadshape = [x/new_magnitude for x in day_load]

        return new_loadshape, new_magnitude

    def _calcRunningVol(self, heatHrs, onOffArr, loadshape, building : Building, effMixFract = 0):
        dhw_usage_magnitude = building.magnitude
        new_loadshape, new_magnitude = self._getIntegratedLoadshapeAndMagnitude(loadshape, building)
        building.magnitude = new_magnitude
        
        runV_G, effMixFract = super()._calcRunningVol(heatHrs, onOffArr, new_loadshape, building, effMixFract) 

        building.magnitude = dhw_usage_magnitude

        return runV_G, effMixFract
    
    def _calcRunningVolLS(self, loadUpHours, loadshape, building : Building, effMixFract = 1, lsFractTotalVol = 1):
        dhw_usage_magnitude = building.magnitude
        new_loadshape, new_magnitude = self._getIntegratedLoadshapeAndMagnitude(loadshape, building)
        building.magnitude = new_magnitude
        
        runV_G, effMixFract = super()._calcRunningVolLS(loadUpHours, new_loadshape, building, effMixFract, lsFractTotalVol) 

        building.magnitude = dhw_usage_magnitude

        return runV_G, effMixFract

        
    def sizeSystem(self, building : Building):
        """
        Resizes the system with a new building.
        Also used for resizing the system after it has changed its loadshift settings using the original building the system was sized for

        Parameters
        ----------
        building : Building
            The building to size with
        """
        super().sizeSystem(building)
        
        recirc_only_model = Building(
            magnitude=self.tm_hourly_load * 24,
            loadshape= [.1/.24] * 24,
            avgLoadshape= [.1/.24] * 24,
            incomingT_F=building.getDesignReturnTemp(),
            supplyT_F=building.supplyT_F,
            returnT_F=None,
            flowRate=None,
            climate=None,
            ignoreRecirc=True,
            designOAT_F=None
        )

        self.Recirc_Cap_kBTUhr = super()._primaryHeatHrs2kBTUHR(self.maxDayRun_hr, self.loadUpHours, recirc_only_model, 
            effSwingVolFract = self.effSwingFract, primaryCurve = False, lsFractTotalVol = self.fract_total_vol)[0]

    def _calcMinCyclingVol(self, building : Building, heatHrs):
        return pCompMinimumRunTime * (building.magnitude / heatHrs) * ((building.supplyT_F - building.getDesignInlet())/(self.getOffTriggerTemp('N') - building.getDesignReturnTemp()))

    def sizeStagedCapacity(self, building : Building, totalVolAtStorage : float, offFraction : float, offTemperature : float):
        cyclingVol_G = totalVolAtStorage * (offFraction - (1 - self.percentUseable))
        genRate = cyclingVol_G / pCompMinimumRunTime
        maxCyclingCapacity_kBTUhr = genRate * rhoCp * \
            (offTemperature - building.getDesignReturnTemp()) / self.defrostFactor / 1000 # TODO check this
        return maxCyclingCapacity_kBTUhr + (building.recirc_loss / 1000.) # Add recirc loss
    
    def getSizingResults(self):
        """
        Returns the minimum primary volume and heating capacity sizing results

        Returns
        -------
        list
            self.PVol_G_atStorageT, self.PCap_kBTUhr, self.Recirc_Cap_kBTUhr
        """
        return [self.PVol_G_atStorageT, self.PCap_kBTUhr, self.Recirc_Cap_kBTUhr]
        
    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None):
        incomingWater_T = simRun.getIncomingWaterT(i)
        ls_mode = simRun.getLoadShiftMode(i)
        self.preSystemStepSetUp(simRun, i, incomingWater_T, minuteIntervals, oat)
        interval_tm_load = simRun.generateRecircLoss(i) # interval load converted to city water -> supply temp
        storage_outlet_temp = self.getStorageOutletTemp(ls_mode)
        possible_storage_generation = convertVolume(simRun.hwGenRate, storage_outlet_temp, incomingWater_T, simRun.building.supplyT_F)
        water_draw = self.getWaterDraw(simRun.hwDemand[i] + interval_tm_load, storage_outlet_temp, simRun.building.supplyT_F, incomingWater_T, simRun.delta_energy, ls_mode,
                                       potential_generation=possible_storage_generation, water_draw_interval=0.1)
        self.runOnePrimaryStep(simRun, i, water_draw, incomingWater_T)

    def runOneRecircStep(self, simRun : SimulationRun, i : int, hw_load_at_storageT : float, entering_waterT : float, erCalc : bool = False):
        """
        Runs one step on the recirc system. This changes the volume of the primary system
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
        simRun = super().getInitializedSimulation(building, initPV, initST, minuteIntervals, nDays, forcePeakyLoadshape)
        return simRun