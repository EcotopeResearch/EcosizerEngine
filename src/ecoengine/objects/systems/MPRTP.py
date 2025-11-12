from ecoengine.objects.systems.SPRTP import SPRTP
from ecoengine.objects.SimulationRun import SimulationRun
from ecoengine.constants.Constants import *
from ecoengine.objects.Building import Building
import numpy as np
from ecoengine.objects.systemConfigUtils import convertVolume, getPeakIndices, hrTo15MinList
import csv

class MPRTP(SPRTP): # Single Pass Return to Primary (SPRTP)
    def __init__(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building = None,
                 outletLoadUpT = None, onFractLoadUp = None, offFractLoadUp = None, onLoadUpT = None, offLoadUpT = None, onFractShed = None, offFractShed = None, onShedT = None, offShedT = None,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, 
                 PCap_kBTUhr = None, ignoreShortCycleEr = False, useHPWHsimPrefMap = False, stratFactor = 1):
        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                 outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT, 
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                 PCap_kBTUhr, ignoreShortCycleEr, useHPWHsimPrefMap, stratFactor)

    def setStratificationPercentageSlope(self):
        self.stratPercentageSlope = 0.8 # degrees F per percentage point of volume on tank  

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

        # Define the heating hours we'll check
        delta = -0.25
        maxHeatHours = 1/(max(building.loadshape))*1.001   
        arr1 = np.arange(24, self.maxDayRun_hr, delta)
        recIndex = len(arr1)
        heatHours = np.concatenate((arr1, np.arange(self.maxDayRun_hr, maxHeatHours, delta)))
        heat_hours_list = [] 
        vol_list = []
        cap_list = []
        og_vol = self.PVol_G_atStorageT
        og_cap = self.PCap_kBTUhr
        og_strat_slope = self.strat_slope
        for i in range(0,len(heatHours)):
            try:
                building.magnitude = dhw_usage_magnitude + (self.tm_hourly_load * 24)
                building.loadshape = [x/building.magnitude for x in day_load]
                self.ignoreShortCycleEr = True

                volN, effMixFract = self.sizePrimaryTankVolume(heatHours[i], self.loadUpHours, building, primaryCurve = True, lsFractTotalVol = self.fract_total_vol)
                capN = self._primaryHeatHrs2kBTUHR(heatHours[i], self.loadUpHours, building, effSwingVolFract = effMixFract, primaryCurve = True, lsFractTotalVol = self.fract_total_vol)[0]
                self.PVol_G_atStorageT = volN
                self.PCap_kBTUhr = capN
                self.strat_slope = 0.8 / (self.PVol_G_atStorageT/100)
                building.magnitude = dhw_usage_magnitude
                building.loadshape = dhw_loadshape
                #check cycling error
                self.ignoreShortCycleEr = False
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
                self._primaryHeatHrs2kBTUHR(heatHours[i], self.loadUpHours, recirc_only_model, 
                    effSwingVolFract = self.effSwingFract, primaryCurve = True, lsFractTotalVol = self.fract_total_vol)[0]
                if self.miniSim(building):
                    heat_hours_list.append(heatHours[i])
                    vol_list.append(volN)
                    cap_list.append(capN)
                elif heatHours[i] > self.maxDayRun_hr:
                    recIndex = recIndex - 1 
            except ValueError:
                break
            except Exception as ex:
                if ex.args[0] == 'ERROR ID 03':
                    break
                else:
                    raise ex

        self.PVol_G_atStorageT = og_vol
        self.PCap_kBTUhr = og_cap
        self.strat_slope = og_strat_slope

        building.magnitude = dhw_usage_magnitude
        building.loadshape = dhw_loadshape

        return [vol_list, cap_list, heat_hours_list, recIndex]
    
    
    def miniSim(self, building : Building):
        simRun = self.getInitializedSimulation(building)
        complete_success = True
        # Run the simulation
        try:
            for i in range(len(simRun.hwDemand)):
                self.runOneSystemStep(simRun, i, minuteIntervals = 1)
        except Exception as e:
            print('exception', e)
            complete_success = False
        self.resetToDefaultCapacity()
        return complete_success
    
    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None):
        incomingWater_T = simRun.getIncomingWaterT(i)
        ls_mode = simRun.getLoadShiftMode(i)
        self.preSystemStepSetUp(simRun, i, incomingWater_T, minuteIntervals, oat) # TODO may be mix temp
        interval_tm_load = self.tm_hourly_load / (60//simRun.minuteIntervals)
        storage_outlet_temp = self.getStorageOutletTemp(ls_mode) # TODO possible redistribution of stratification?
        water_draw = self.getWaterDraw(simRun.hwDemand[i] + interval_tm_load, storage_outlet_temp, simRun.building.supplyT_F, incomingWater_T, simRun.delta_energy, ls_mode)
        
        if simRun.slugSim:
            self._oneMixedSlugStep(simRun, incomingWater_T, storage_outlet_temp, i)

        not_pheating = ls_mode != simRun.getLoadShiftMode(i-1) or not simRun.pheating   
        self.runOnePrimaryStep(simRun, i, water_draw, incomingWater_T)
        started_pheating = simRun.pheating and not_pheating
        if started_pheating:
            mixV_high = self.getTankVolAtTemp(simRun.building.supplyT_F)
            mixV = mixV_high - (self.PVol_G_atStorageT * (1 - self.percentUseable)) 
            simRun.initializeMPRTPValue(mixV, 
                                        self._getAvgTempBetweenTwoVols((1 - self.percentUseable) * self.PVol_G_atStorageT, mixV_high, incomingWater_T, simRun.delta_energy, storage_outlet_temp), 
                                        i)
    

    def _oneMixedSlugStep(self, simRun : SimulationRun, incomingWater_T, storage_outlet_temp, i):
        if simRun.slugSim == False or i == 0:
            return
        prV = self.getWaterDraw(simRun.hwDemand[i], storage_outlet_temp, simRun.building.supplyT_F, incomingWater_T, simRun.delta_energy, simRun.getLoadShiftMode(i))
        # prV = convertVolume(simRun.hwDemand[i], storage_outlet_temp, incomingWater_T, simRun.building.supplyT_F)
        rcV = simRun.building.getDesignReturnFlow()
        simRun.mixV[i] = simRun.mixV[i-1] + prV + rcV

        energy_input = (1000 * self.PCap_kBTUhr * self.defrostFactor) / (rhoCp * 60) 

        temp_calc_total = energy_input + (incomingWater_T * prV) + (simRun.building.getDesignReturnTemp() * rcV) + (simRun.mixT_F[i-1] * simRun.mixV[i-1])

        simRun.mixT_F[i] = temp_calc_total / simRun.mixV[i]
        if simRun.mixV[i] >= self.PVol_G_atStorageT * self.percentUseable and simRun.mixT_F[i] < simRun.building.supplyT_F:
            raise Exception (f"MPRTP was not able to heat water fast enough. DHW outage occurred at time step {i}. Water temp at {simRun.mixT_F[i]} at {simRun.mixV[i]} of {self.PVol_G_atStorageT * self.percentUseable} g")
        elif simRun.mixT_F[i] >= simRun.building.supplyT_F:
            simRun.slugSim = False

    def _getAvgTempBetweenTwoVols(self, low_vol, high_vol, incomingT_F, delta_energy : float, storage_temp : float):
        if low_vol > high_vol:
            raise Exception(f"low_vol of {low_vol} is higher than high_vol of {high_vol}")
        elif low_vol == high_vol:
            return self.getTemperatureAtTankVol(low_vol, incomingT_F, delta_energy=delta_energy)
        low_temp = self.getTemperatureAtTankVol(low_vol, incomingT_F, delta_energy=delta_energy)
        high_temp = self.getTemperatureAtTankVol(high_vol, incomingT_F, delta_energy=delta_energy)
        vol_of_slug = high_vol - low_vol
        temp_sum = 0.
        if low_temp <= incomingT_F:
            top_of_cold = self.getTankVolAtTemp(incomingT_F, delta_energy=delta_energy)
            temp_sum = temp_sum + (incomingT_F * (top_of_cold - low_vol))
            low_vol = top_of_cold
        if high_temp >= storage_temp:
            bottom_of_hot = self.getTankVolAtTemp(storage_temp, delta_energy=delta_energy)
            temp_sum = temp_sum + (storage_temp * (high_vol - bottom_of_hot))
            high_vol = bottom_of_hot
        mid_temp = low_temp + ((high_temp-low_temp)/2) # average because it is linear
        temp_sum = temp_sum + (mid_temp * (high_vol - low_vol))
        return temp_sum/vol_of_slug 

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
        cyclingV = self.PVol_G_atStorageT * (self.onFract - (1 - self.percentUseable))
        mixT_F = self._getAvgTempBetweenTwoVols((1 - self.percentUseable) * self.PVol_G_atStorageT, self.onFract * self.PVol_G_atStorageT, simRun.getIncomingWaterT(0), simRun.delta_energy, self.getStorageOutletTemp(simRun.getLoadShiftMode(0)))

        simRun.initializeMPRTPValue(cyclingV, mixT_F)
        return simRun