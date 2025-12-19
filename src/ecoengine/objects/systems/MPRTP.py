from ecoengine.objects.systems.SPRTP import SPRTP
from ecoengine.objects.SimulationRun import SimulationRun
from ecoengine.constants.Constants import *
from ecoengine.objects.Building import Building
from ecoengine.objects.PrefMapTracker import PrefMapTracker
from scipy.stats import norm
import numpy as np
from ecoengine.objects.systemConfigUtils import convertVolume, getPeakIndices, hrTo15MinList, hrToMinList
class MPRTP(SPRTP): # Single Pass Return to Primary (SPRTP)
    def __init__(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building : Building = None,
                 outletLoadUpT = None, onFractLoadUp = None, offFractLoadUp = None, onLoadUpT = None, offLoadUpT = None, onFractShed = None, offFractShed = None, onShedT = None, offShedT = None,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, 
                 PCap_kBTUhr = None, useHPWHsimPrefMap = False, stratFactor = 1):
        self.sized_system = False
        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                 outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT, 
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                 PCap_kBTUhr, useHPWHsimPrefMap, stratFactor)
        if self.sized_system:
            self.PVol_G_atStorageT = self.adjust_storage_oversize(self.PVol_G_atStorageT, building)
            self.strat_slope = self.stratPercentageSlope / (self.PVol_G_atStorageT/100)

    def setStratificationPercentageSlope(self):
        self.stratPercentageSlope = 0.8 # degrees F per percentage point of volume on tank  

    def adjust_storage_oversize(self, original_vol : float, building : Building, saftey_buffer = .2):
        saved_stor_size = self.PVol_G_atStorageT
        step_size = saved_stor_size / 2.0
        og_strat_slope = self.strat_slope
        stor_size = original_vol
        oversize_amount = step_size
        continue_loop = True
        while oversize_amount < stor_size and continue_loop:
            self.PVol_G_atStorageT = stor_size - oversize_amount
            self.strat_slope = self.stratPercentageSlope / (self.PVol_G_atStorageT/100)
            completed_sim = self.miniSim(building)
            if completed_sim:
                oversize_amount = oversize_amount + step_size
            else:
                oversize_amount = oversize_amount - step_size
                if step_size < 0.5:
                    continue_loop = False
                else:
                    if step_size < 25 and step_size > 1:
                        step_size = step_size - 0.5
                    else:
                        step_size = step_size/2.0
                    oversize_amount = oversize_amount + step_size
        stor_size = stor_size - oversize_amount
        stor_size = self.PVol_G_atStorageT + (self.PVol_G_atStorageT * saftey_buffer)
        self.PVol_G_atStorageT = saved_stor_size
        self.strat_slope = og_strat_slope
        return stor_size
    
    def sizeSystem(self, building : Building):
        self.sized_system = True
        super().sizeSystem(building)
    #     self.strat_slope = self.stratPercentageSlope / (self.PVol_G_atStorageT/100)
    #     self.strat_inter = self.onT - (self.stratPercentageSlope * self.onFract * 100)
    #     self.perfMap = PrefMapTracker(self.PCap_kBTUhr)
    #     self.PVol_G_atStorageT = self.adjust_storage_oversize(self.PVol_G_atStorageT, building)

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

        # Define the heating hours we'll check
        delta = -1.0
        maxHeatHours = 1/(max(building.loadshape))*1.001   
        arr1 = np.arange(24 if self.maxDayRun_hr > 13 else 14, self.maxDayRun_hr, delta)
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
                mprtp = MPRTP(self.storageT_F, self.defrostFactor, self.percentUseable, heatHours[i], self.onFract, self.offFract, self.onT, self.offT, building,
                 doLoadShift = False)
                # if len(vol_list) > 1 and mprtp.PVol_G_atStorageT > vol_list[-1]:
                #     # no zig zags on the primary curve (fix for small weird bug of coincidence)
                #     mprtp.PVol_G_atStorageT = vol_list[-1] - 1
                if mprtp.miniSim(building):
                    heat_hours_list.append(heatHours[i])
                    vol_list.append(mprtp.PVol_G_atStorageT)
                    cap_list.append(mprtp.PCap_kBTUhr)
                elif heatHours[i] > self.maxDayRun_hr:
                    recIndex = recIndex - 1 
                # volN, effMixFract = self.sizePrimaryTankVolume(heatHours[i], self.loadUpHours, building, primaryCurve = True, lsFractTotalVol = self.fract_total_vol)
                # capN = self._primaryHeatHrs2kBTUHR(heatHours[i], self.loadUpHours, building, effSwingVolFract = effMixFract, primaryCurve = True, lsFractTotalVol = self.fract_total_vol)[0]
                # self.PCap_kBTUhr = capN
                # # volN = self.adjust_storage_oversize(volN, building)
                # self.PVol_G_atStorageT = volN
                # self.strat_slope = self.stratPercentageSlope / (self.PVol_G_atStorageT/100)
                # if self.miniSim(building):
                #     heat_hours_list.append(heatHours[i])
                #     vol_list.append(volN)
                #     cap_list.append(capN)
                # elif heatHours[i] > self.maxDayRun_hr:
                #     recIndex = recIndex - 1 
            except ValueError:
                break
            except Exception as ex:
                if ex.args[0] == 'ERROR ID 03' or ex.args[0] == 'ERROR ID 04':
                    break
                else:
                    raise ex

        self.PVol_G_atStorageT = og_vol
        self.PCap_kBTUhr = og_cap
        self.strat_slope = og_strat_slope

        building.magnitude = dhw_usage_magnitude
        building.loadshape = dhw_loadshape

        return [vol_list, cap_list, heat_hours_list, recIndex]
    
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
        # effMixN = []
        N = []

        #load up hours to loop through
        i = 100.
        # try:
        while i >= 25.: #arbitrary stopping point, anything more than this will not result in different sizing
            #size the primary system based on the number of load up hours
            # fract = norm_mean + norm_std * norm.ppf(i/100) #TODO norm_mean and std are currently from multi-family, need other types eventually. For now, loadshifting will only be available for multi-family
            # fract = fract if fract <= 1. else 1.
            mprtp = MPRTP(self.storageT_F, self.defrostFactor, self.percentUseable, self.maxDayRun_hr, self.onFract, self.offFract, self.onT, self.offT, building, self.outletLoadUpT,self.onFractLoadUp,
                          self.offFractLoadUp,self.onLoadUpT,self.offLoadUpT,self.onFractShed,self.offFractShed,self.onShedT,self.offShedT,self.doLoadShift, i/100., self.loadShiftSchedule,
                          self.loadUpHours)
            # volN_i, effMixN_i = self.sizePrimaryTankVolume(heatHrs = self.maxDayRun_hr, loadUpHours = self.loadUpHours, building = building, primaryCurve = False, lsFractTotalVol = fract)
            volN.append(mprtp.PVol_G_atStorageT)
            # effMixN.append(effMixN_i)
            capN.append(mprtp.PCap_kBTUhr)
            N.append(i)
            i -= 1

        # except Exception:
    
        return [volN, capN, N, int(np.ceil((self.loadShiftPercent * 100)-25))]
    
    
    def miniSim(self, building : Building):
        simRun = self.getInitializedSimulation(building)
        complete_success = True
        # Run the simulation
        try:
            for i in range(len(simRun.hwDemand)):
                self.runOneSystemStep(simRun, i, minuteIntervals = 1)
        except Exception as e:
            print(f'exception {self.maxDayRun_hr}', e)
            complete_success = False
        self.resetToDefaultCapacity()
        return complete_success
    
    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None):
        incomingWater_T = simRun.getIncomingWaterT(i)
        ls_mode = simRun.getLoadShiftMode(i)
        self.preSystemStepSetUp(simRun, i, incomingWater_T, minuteIntervals, oat) # TODO may be mix temp
        interval_tm_load = simRun.generateRecircLoss(i)
        storage_outlet_temp = self.getStorageOutletTemp(ls_mode) # TODO possible redistribution of stratification?
        possible_storage_generation = convertVolume(simRun.hwGenRate, storage_outlet_temp, incomingWater_T, simRun.building.supplyT_F)
        water_draw_at_recirc = self.getWaterDraw(self.tm_hourly_load / (60//simRun.minuteIntervals), storage_outlet_temp, simRun.building.supplyT_F, simRun.building.getDesignReturnTemp(), simRun.delta_energy, ls_mode)
        water_draw_at_city_temp = self.getWaterDraw(simRun.hwDemand[i], storage_outlet_temp, simRun.building.supplyT_F, incomingWater_T, simRun.delta_energy, ls_mode, possible_storage_generation)
        water_draw = self.getWaterDraw(simRun.hwDemand[i] + interval_tm_load, storage_outlet_temp, simRun.building.supplyT_F, incomingWater_T, simRun.delta_energy, ls_mode, possible_storage_generation)
        
        if simRun.slugSim:
            self._oneMixedSlugStep(simRun, incomingWater_T, water_draw_at_recirc, water_draw_at_city_temp, i)
            self.runOnePrimaryStep(simRun, i, water_draw, incomingWater_T)
            if simRun.mixT_F[i] < simRun.building.supplyT_F:
                simRun.pV[i] = (self.PVol_G_atStorageT * self.percentUseable) - simRun.mixV[i]
        elif simRun.pheating and not simRun.slugSim:
            self.runOnePrimaryStep(simRun, i, water_draw, incomingWater_T)
            mixV_high = self.getTankVolAtTemp(simRun.building.supplyT_F, simRun.delta_energy)
            mixV = mixV_high - (self.PVol_G_atStorageT * (1 - self.percentUseable)) 
            if mixV > 0:
                simRun.initializeMPRTPValue(mixV, 
                                        self._getAvgTempBetweenTwoVols((1 - self.percentUseable) * self.PVol_G_atStorageT, mixV_high, incomingWater_T, simRun.delta_energy, storage_outlet_temp), 
                                        i)
                if simRun.mixT_F[i] < simRun.building.supplyT_F:
                    simRun.pV[i] = (self.PVol_G_atStorageT * self.percentUseable) - simRun.mixV[i]
        else:
            self.runOnePrimaryStep(simRun, i, water_draw, incomingWater_T)
        simRun.cWV[i] = water_draw_at_city_temp
        simRun.rWV[i] = water_draw_at_recirc

    # def getCyclingTempAndPercent(self, onFract : float, onTemp : float, incomingTemp : float, supplyTemp : float):
    #     on_fract = onFract * 100
    #     cycle_bottom = (1 - self.percentUseable) * 100
    #     temp_at_cycle_bottom = onTemp - ((on_fract - cycle_bottom) * self.stratPercentageSlope)
    #     supply_temp_height = ((on_fract) - ((onTemp - supplyTemp)/self.stratPercentageSlope))
    #     temp_sum = 0
    #     placehold_temp = temp_at_cycle_bottom
    #     placehold_vol = cycle_bottom
    #     if temp_at_cycle_bottom <= incomingTemp:
    #         incoming_temp_height = ((on_fract) - ((onTemp - incomingTemp)/self.stratPercentageSlope))
    #         temp_sum = temp_sum + ((incoming_temp_height - cycle_bottom) * incomingTemp)
    #         placehold_temp = incomingTemp
    #         placehold_vol = incoming_temp_height
    #     avg_temp = placehold_temp + ((supplyTemp - placehold_temp)/2) # linear
    #     temp_sum = temp_sum + (avg_temp * (supply_temp_height - placehold_vol))
    #     return temp_sum / (supply_temp_height - cycle_bottom), (supply_temp_height - cycle_bottom)/100

    def _oneMixedSlugStep(self, simRun : SimulationRun, incomingWater_T, water_draw_at_recirc, water_draw_at_city_temp, i):
        if simRun.slugSim == False or i == 0:
            return
        simRun.cWV[i] = water_draw_at_city_temp
        simRun.rWV[i] = water_draw_at_recirc
        simRun.mixV[i] = simRun.mixV[i-1] + simRun.cWV[i] + simRun.rWV[i]
        
        energy_input = 0
        if simRun.pheating:
            energy_input = ((1000 * self.PCap_kBTUhr * self.defrostFactor) / (rhoCp * (60//simRun.minuteIntervals))) / simRun.mixV[i]

        temp_calc_total = (incomingWater_T * simRun.cWV[i]) + (simRun.building.getDesignReturnTemp() * simRun.rWV[i]) + (simRun.mixT_F[i-1] * simRun.mixV[i-1])
        simRun.slugEnergyInput[i] = energy_input
        simRun.mixT_F[i] = energy_input + (temp_calc_total / simRun.mixV[i])
        if simRun.mixV[i] >= self.PVol_G_atStorageT * self.percentUseable and simRun.mixT_F[i] < simRun.building.supplyT_F:
            raise Exception (f"MPRTP was not able to heat water fast enough. DHW outage occurred at time step {i}. Water temp at {simRun.mixT_F[i]} at {simRun.mixV[i]} of {self.PVol_G_atStorageT * self.percentUseable} g")
        elif simRun.mixT_F[i] >= simRun.building.supplyT_F:
            simRun.slugSim = False

    # def _oneSizingSlugStep(self, simRun : SimulationRun, incomingWater_T, i, sysCap_kBTUhr, ls_mode = 'N', lsFractTotalVol = 1.):
    #     simRun.cWV[i] = simRun.hwDemand[i]
    #     simRun.rWV[i] = simRun.building.recirc_loss / (60//simRun.minuteIntervals) / (rhoCp) / (simRun.building.supplyT_F - simRun.building.getDesignReturnTemp())
    #     simRun.mixV[i] = simRun.mixV[i-1] + simRun.cWV[i] + simRun.rWV[i]

    #     energy_in_btumin = 1000 * sysCap_kBTUhr / (60//simRun.minuteIntervals)
    #     temp_delta = ((energy_in_btumin * self.defrostFactor) / rhoCp) / simRun.mixV[i]
    #     if ls_mode == 'S':
    #         energy_in_btumin = 0
    #         temp_delta = 0
    #         if lsFractTotalVol < 1:
    #             simRun.cWV[i] = simRun.cWV[i] * lsFractTotalVol
    #             simRun.rWV[i] = simRun.rWV[i] * lsFractTotalVol
    #             simRun.mixV[i] = simRun.mixV[i-1] + simRun.cWV[i] + simRun.rWV[i]

    #     temp_calc_total = (incomingWater_T * simRun.cWV[i]) + (simRun.building.getDesignReturnTemp() * simRun.rWV[i]) + (simRun.mixT_F[i-1] * simRun.mixV[i-1])
        
    #     simRun.mixT_F[i] = temp_delta + (temp_calc_total / simRun.mixV[i])
    #     simRun.slugEnergyInput[i] = energy_in_btumin 

    #     # should comment out :::
    #     energy_to_heat_supply = (simRun.building.supplyT_F - incomingWater_T) * rhoCp * simRun.cWV[i]
    #     energy_to_heat_recirc = (simRun.building.supplyT_F - simRun.building.getDesignReturnTemp()) * rhoCp * simRun.rWV[i]
    #     simRun.pTAtOn[i] = simRun.building.recirc_loss / 60 # recirc loss
    #     simRun.pOnT[i] = simRun.cWV[i] * (self.storageT_F - incomingWater_T) * (rhoCp) # cw loss
    #     # print(f"{i} {simRun.pTAtOn[i]}, {simRun.mixV[i]}, {energy_in_btumin} {energy_to_heat_supply} {energy_to_heat_recirc} {energy_to_heat_supply + energy_to_heat_recirc - energy_in_btumin}")
    #     simRun.pOnT[i] = simRun.cWV[i] * (simRun.building.supplyT_F - incomingWater_T) * (rhoCp) # cw loss

    # old
    def _oneSizingSlugStep(self, simRun : SimulationRun, incomingWater_T, i, sysCap_kBTUhr, ls_mode = 'N', lsFractTotalVol = 1.):
        simRun.cWV[i] = convertVolume(simRun.hwDemand[i], self.storageT_F, incomingWater_T, simRun.building.supplyT_F)
        simRun.rWV[i] = simRun.building.recirc_loss / (60//simRun.minuteIntervals) / (rhoCp) / (self.storageT_F - simRun.building.getDesignReturnTemp())
        simRun.mixV[i] = simRun.mixV[i-1] + simRun.cWV[i] + simRun.rWV[i]

        energy_in_btumin = 1000 * sysCap_kBTUhr / (60//simRun.minuteIntervals)
        temp_delta = ((energy_in_btumin * self.defrostFactor) / rhoCp) / simRun.mixV[i]
        if ls_mode == 'S':
            energy_in_btumin = 0
            temp_delta = 0
            if lsFractTotalVol < 1:
                simRun.cWV[i] = simRun.cWV[i] * lsFractTotalVol
                simRun.rWV[i] = simRun.rWV[i] * lsFractTotalVol
                simRun.mixV[i] = simRun.mixV[i-1] + simRun.cWV[i] + simRun.rWV[i]

        temp_calc_total = (incomingWater_T * simRun.cWV[i]) + (simRun.building.getDesignReturnTemp() * simRun.rWV[i]) + (simRun.mixT_F[i-1] * simRun.mixV[i-1])
        
        simRun.mixT_F[i] = temp_delta + (temp_calc_total / simRun.mixV[i])
        simRun.slugEnergyInput[i] = energy_in_btumin 

        # should comment out :::
        # energy_to_heat_supply = (simRun.building.supplyT_F - incomingWater_T) * rhoCp * simRun.cWV[i]
        # energy_to_heat_recirc = (simRun.building.supplyT_F - simRun.building.getDesignReturnTemp()) * rhoCp * simRun.rWV[i]
        # simRun.pTAtOn[i] = simRun.building.recirc_loss / 60 # recirc loss
        # simRun.pOnT[i] = simRun.cWV[i] * (self.storageT_F - incomingWater_T) * (rhoCp) # cw loss
        # print(f"{i} {simRun.pTAtOn[i]}, {simRun.mixV[i]}, {energy_in_btumin} {energy_to_heat_supply} {energy_to_heat_recirc} {energy_to_heat_supply + energy_to_heat_recirc - energy_in_btumin}")
        # simRun.pOnT[i] = simRun.cWV[i] * (simRun.building.supplyT_F - incomingWater_T) * (rhoCp) # cw loss


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
    
    # def _estimateCycleVol(self, cycleTemp : float, supply_temp : float, sysCap_kBTUhr : float, run_minutes : float = 15):
    #     cycle_vol = (sysCap_kBTUhr*1000) / (60//run_minutes) / (rhoCp) / (supply_temp - cycleTemp)
    #     return cycle_vol

    
    # def _calcRunningVol(self, heatHrs, onOffArr, loadshape, building : Building, effMixFract = 0):
    #     """
    #     Function to find the running volume for the hot water storage tank, which
    #     is needed for calculating the total volume for primary sizing and in the event of load shift sizing
    #     represents the entire volume.

    #     Implimented seperatly for Swing Tank systems

    #     Parameters
    #     ----------
    #     heatHrs : float
    #         The number of hours primary heating equipment can run in a day.
    #     onOffArr : ndarray
    #         array of 1/0's where 1's allow heat pump to run and 0's dissallow. of length 24.
    #     loadshape : ndarray
    #         normalized array of length 24 representing the daily loadshape for this calculation.
    #     building : Building
    #         The building the system is being sized for
    #     effMixFract: Int
    #         unused value in this instance of the function. Used in Swing Tank implimentation

    #     Raises
    #     ------
    #     Exception: Error if oversizing system.

    #     Returns
    #     -------
    #     runV_G : float
    #         The running volume in gallons at supply temp.
    #     effMixFract: int
    #         Needed for swing tank implementation.
    #     """ 
    #     new_loadshape, new_magnitude = self._getIntegratedLoadshapeAndMagnitude(loadshape, building) # includes recirc loss 
    #     genRate = np.tile(onOffArr,2) / heatHrs #hourly
    #     diffN = genRate - np.tile(new_loadshape,2) #hourly
    #     diffInd = getPeakIndices(diffN[0:24]) #Days repeat so just get first day!
    #     diffN *= new_magnitude

    #     sysCap_kBTUhr, hwGenRate = self._primaryHeatHrs2kBTUHR(heatHrs, self.loadUpHours, building, 
    #         effSwingVolFract = effMixFract, primaryCurve = True, lsFractTotalVol = self.fract_total_vol) #TODO maybe primaryCurve should be false?
        
    #     # because in sizing, recirc loss is added to building demand, we must take it out of building demand for this calculation
    #     hwDemand = np.tile(loadshape,2) * building.magnitude
    #     hwDemand = np.array(hrToMinList(hwDemand)) / 60
        
    #     # Get the running volume ##############################################
    #     if len(diffInd) == 0:
    #         raise Exception("ERROR ID 03","The heating rate is greater than the peak volume the system is oversized! Try increasing the hours the heat pump runs in a day",)
    #     runV_G = 0
    #     cycle_temp, cycle_percent = self.getCyclingTempAndPercent(self.onFract, self.onT, building.getDesignInlet(), building.supplyT_F)
    #     estimate_cycle_vol = self._estimateCycleVol(cycle_temp, building.supplyT_F, sysCap_kBTUhr)
    #     print(f"cycle_temp = {cycle_temp}, cycle_percent = {cycle_percent}, estimate_cycle_vol = {estimate_cycle_vol}")
    #     # size cycling as 15 min run time
    #     for peakInd in diffInd:
    #         peak_sim = SimulationRun([hwGenRate/60]*48*60, hwDemand, 0, building, np.array(hrToMinList(self.loadShiftSchedule)), 1, self.doLoadShift)
    #         peak_sim.initializeMPRTPValue(0, 0, 0)
    #         peak_sim.mixT_F[peakInd*60-1] = cycle_temp
    #         peak_sim.mixV[peakInd*60-1] = estimate_cycle_vol
    #         for i in range(peakInd*60, 48*60):
    #             self._oneSizingSlugStep(peak_sim, building.getDesignInlet(), i, sysCap_kBTUhr)
    #             if peak_sim.mixT_F[i] >= building.supplyT_F: #self.storageT_F: #
    #                 break
    #         peakVol = max(peak_sim.mixV)
    #         runV_G = max(runV_G, peakVol)

    #     # runV_G = convertVolume(runV_G - estimate_cycle_vol, building.supplyT_F, building.getDesignInlet(), self.storageT_F) # expected return is in supply temp
    #     return runV_G - estimate_cycle_vol, effMixFract
    
    # # TODO figure out good method
    # def _calcRunningVolLS(self, loadUpHours, loadshape, building : Building, effMixFract = 1, lsFractTotalVol = 1):
    #     """
    #     Function to calculate the running volume if load shifting. Using the max generation rate between normal sizing
    #     and preliminary volume, the deficit between generation and hot water use is then added to the preliminary volume.

    #     Implemented separately for swing tank system.

    #     Parameters
    #     ------   
    #     loadUpHours : float
    #         Number of hours of scheduled load up before first shed. If sizing, this is set by user. If creating sizing
    #         plot, number may vary.  
    #     loadshape : ndarray
    #         normalized array of length 24 representing the daily loadshape for this calculation.
    #     building : Building
    #         The building the system is being sized for
    #     effMixFract : float
    #         Only used in swing tank implementation.

    #     Returns
    #     ------
    #     LSrunV_G : float
    #         Volume needed between primary shed aquastat and load up aquastat at supply temp.
    #     effMixFract : float
    #         Used for swing tank implementation.
    #     """
    #     sysCap_kBTUhr, genRateON = self._primaryHeatHrs2kBTUHR(self.maxDayRun_hr, loadUpHours, building, 
    #         effSwingVolFract = effMixFract, primaryCurve = False, lsFractTotalVol = lsFractTotalVol) #max generation rate from both methods
    #     genRate = [genRateON if x != 0 else 0 for x in self.loadShiftSchedule] #set generation rate during shed to 0
    #     genRate = np.tile(genRate, 2)

    #     # because in sizing, recirc loss is added to building demand, we must take it out of building demand for this calculation
    #     day_load = [(hour_load * building.magnitude) for hour_load in loadshape]
    #     hwDemand = np.tile(day_load,2)
    #     hwDemand = np.array(hrToMinList(hwDemand)) / 60
        
    #     # Get the running volume ##############################################
    #     peak_sim = SimulationRun([genRateON/60]*48*60, hwDemand, 0, building, np.array(hrToMinList(self.loadShiftSchedule)), 1, self.doLoadShift,
    #                              LS_sched=['N' if hour > 0 else 'S' for hour in self.loadShiftSchedule])
    #     cycle_temp, cycle_percent = self.getCyclingTempAndPercent(self.onFract, self.onT, building.getDesignInlet(), building.supplyT_F)
    #     estimate_cycle_vol = self._estimateCycleVol(cycle_temp, building.supplyT_F, sysCap_kBTUhr)
    #     # print(f"ls cycle_temp = {cycle_temp}, cycle_percent = {cycle_percent}, estimate_cycle_vol = {estimate_cycle_vol}")
    #     peak_sim.initializeMPRTPValue(estimate_cycle_vol, cycle_temp, 0)
    #     runV_G = 0
    #     for i in range(0, 48*60):
    #         self._oneSizingSlugStep(peak_sim, building.getDesignInlet(), i, sysCap_kBTUhr, ls_mode = peak_sim.getLoadShiftMode(i), lsFractTotalVol = lsFractTotalVol)
    #         if peak_sim.mixT_F[i] >= building.supplyT_F:
    #             runV_G = max(runV_G, peak_sim.mixV[i])
    #             peak_sim.mixV[i] = cycle_temp
    #             peak_sim.mixT_F[i] = estimate_cycle_vol
    #     peakVol = max(peak_sim.mixV)
    #     runV_G = max(runV_G, peakVol)

    #     return runV_G - estimate_cycle_vol, effMixFract
    
    # old
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
        new_loadshape, new_magnitude = self._getIntegratedLoadshapeAndMagnitude(loadshape, building) # includes recirc loss 
        genRate = np.tile(onOffArr,2) / heatHrs #hourly
        diffN = genRate - np.tile(new_loadshape,2) #hourly
        diffInd = getPeakIndices(diffN[0:24]) #Days repeat so just get first day!
        diffN *= new_magnitude

        sysCap_kBTUhr, hwGenRate = self._primaryHeatHrs2kBTUHR(heatHrs, self.loadUpHours, building, 
            effSwingVolFract = effMixFract, primaryCurve = True, lsFractTotalVol = self.fract_total_vol) #TODO maybe primaryCurve should be false?
        
        # because in sizing, recirc loss is added to building demand, we must take it out of building demand for this calculation
        hwDemand = np.tile(loadshape,2) * building.magnitude
        hwDemand = np.array(hrToMinList(hwDemand)) / 60
        
        # Get the running volume ##############################################
        if len(diffInd) == 0:
            raise Exception("ERROR ID 03","The heating rate is greater than the peak volume, the system is oversized! Try lowering the flow rate or raising the return temperature of the recirculation loop for a more variable load.",)
        runV_G = 0
        # size cycling as 15 min run time
        for peakInd in diffInd:
            peak_sim = SimulationRun([hwGenRate/60]*48*60, hwDemand, 0, building, np.array(hrToMinList(self.loadShiftSchedule)), 1, self.doLoadShift)
            peak_sim.initializeMPRTPValue(0, 0, 0)
            for i in range(peakInd*60, 48*60):
                self._oneSizingSlugStep(peak_sim, building.getDesignInlet(), i, sysCap_kBTUhr)
                if peak_sim.mixT_F[i] >= self.storageT_F: #building.supplyT_F:
                    break
            peakVol = max(peak_sim.mixV)
            runV_G = max(runV_G, peakVol)

        runV_G = convertVolume(runV_G, building.supplyT_F, building.getDesignInlet(), self.storageT_F) # expected return is in supply temp
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
        sysCap_kBTUhr, genRateON = self._primaryHeatHrs2kBTUHR(self.maxDayRun_hr, loadUpHours, building, 
            effSwingVolFract = effMixFract, primaryCurve = False, lsFractTotalVol = lsFractTotalVol) #max generation rate from both methods
        genRate = [genRateON if x != 0 else 0 for x in self.loadShiftSchedule] #set generation rate during shed to 0
        genRate = np.tile(genRate, 2)

        # because in sizing, recirc loss is added to building demand, we must take it out of building demand for this calculation
        day_load = [(hour_load * building.magnitude) for hour_load in loadshape]
        hwDemand = np.tile(day_load,2)
        hwDemand = np.array(hrToMinList(hwDemand)) / 60
        
        # Get the running volume ##############################################
        peak_sim = SimulationRun([genRateON/60]*48*60, hwDemand, 0, building, np.array(hrToMinList(self.loadShiftSchedule)), 1, self.doLoadShift,
                                 LS_sched=['N' if hour > 0 else 'S' for hour in self.loadShiftSchedule])
        peak_sim.initializeMPRTPValue(0, 0, 0)
        runV_G = 0
        for i in range(0, 48*60):
            self._oneSizingSlugStep(peak_sim, building.getDesignInlet(), i, sysCap_kBTUhr, ls_mode = peak_sim.getLoadShiftMode(i), lsFractTotalVol = lsFractTotalVol)
            if peak_sim.mixT_F[i] >= self.storageT_F:
                runV_G = max(runV_G, peak_sim.mixV[i])
                peak_sim.mixV[i] = 0
        peakVol = max(peak_sim.mixV)
        runV_G = max(runV_G, peakVol)
        runV_G = convertVolume(runV_G, building.supplyT_F, building.getDesignInlet(), self.storageT_F) # expected return is in supply temp
        return runV_G, effMixFract

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