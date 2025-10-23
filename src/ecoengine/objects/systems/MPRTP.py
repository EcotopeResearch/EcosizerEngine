from ecoengine.objects.systems.SPRTP import SPRTP
from ecoengine.objects.SimulationRun import SimulationRun
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import convertVolume
from ecoengine.objects.Building import Building
import numpy as np
from ecoengine.objects.systemConfigUtils import convertVolume, getPeakIndices, hrTo15MinList
import csv

class MPRTP(SPRTP): # Single Pass Return to Primary (SPRTP)
    def __init__(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, aquaFractLoadUp = None, 
                 aquaFractShed = None, loadUpT_F = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, 
                 PCap_kBTUhr = None, ignoreShortCycleEr = False, useHPWHsimPrefMap = False, stratFactor = 1):
        
        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building, doLoadShift, 
                loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, aquaFractShed, loadUpT_F, systemModel, 
                numHeatPumps, PVol_G_atStorageT, PCap_kBTUhr, ignoreShortCycleEr, useHPWHsimPrefMap, stratFactor)
        
        self.strat_slope = 0.8 / (self.PVol_G_atStorageT/100)
        self.strat_inter = building.supplyT_F - (0.8 * self.aquaFract * 100) #TODO replace with on temp?

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
        arr1 = np.arange(24, self.maxDayRun_hr, delta) #TODO why are we going all the way to 24 hours ???
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
                print(f"sizing {i}, {heatHours[i]}, {self.delta_energy}")
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
                
                print(f"V: {self.PVol_G_atStorageT}, C: {self.PCap_kBTUhr}, slope: {self.strat_slope}")
                if self.miniSim(building):
                    heat_hours_list.append(heatHours[i])
                    vol_list.append(volN)
                    cap_list.append(capN)
                elif heatHours[i] > self.maxDayRun_hr:
                    recIndex = recIndex - 1 
            except ValueError:
                break

        self.PVol_G_atStorageT = og_vol
        self.PCap_kBTUhr = og_cap
        self.strat_slope = og_strat_slope

        building.magnitude = dhw_usage_magnitude
        building.loadshape = dhw_loadshape

        print(f"complete... {self.PVol_G_atStorageT}, {self.PCap_kBTUhr}, {self.strat_slope}")

        return [vol_list, cap_list, heat_hours_list, recIndex]
    
    
    def miniSim(self, building : Building):
        # print("1")
        simRun = self.getInitializedSimulation(building)
        # print("2")
        self.setLoadUPVolumeAndTrigger(simRun.getIncomingWaterT(0)) # set initial load up volume and aquafraction adjusted for useful energy
        # print("3")
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
        self.preSystemStepSetUp(simRun, i, incomingWater_T, minuteIntervals, oat)
        interval_tm_load = self.tm_hourly_load / (60//simRun.minuteIntervals)
        delta_draw_recirc = convertVolume(simRun.hwDemand[i] + interval_tm_load, self.storageT_F, incomingWater_T, simRun.building.supplyT_F)
        self.delta_energy = self.delta_energy - delta_draw_recirc
        ls_mode = simRun.getLoadShiftMode(i)

        if simRun.slugSim:
            self._oneMixedSlugStep(simRun, incomingWater_T, i)

        if simRun.pheating:
            # add heat
            simRun.pRun[i] = 1.0
            delta_heat = convertVolume(simRun.hwGenRate, self.storageT_F, incomingWater_T, simRun.building.supplyT_F) #TODO convert to off trigger vol?
            self.delta_energy = self.delta_energy + delta_heat

            off_triggerV = self.getOffTriggerVolume(ls_mode)
            off_triggerT = self.getOffTriggerTemp(ls_mode)
            if self.getTemperatureAtTankVol(off_triggerV, incomingWater_T, ls_mode) >= off_triggerT:
                # print(f"{i}: turning off at {self.getTemperatureAtTankVol(off_triggerV, incomingWater_T, ls_mode)} degrees")
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
                # print(f"{i}: turning on at {self.getTemperatureAtTankVol(on_triggerV, incomingWater_T, ls_mode)} degrees. {delta_draw_recirc}")
                simRun.pheating = True
                highest_vol = self.getTankVolAtTemp(on_triggerT)
                if highest_vol > on_triggerV:
                    extra_loss = highest_vol - on_triggerV
                    gen_percent = extra_loss/delta_draw_recirc
                    simRun.pRun[i] = gen_percent
                    delta_heat = convertVolume(simRun.hwGenRate * gen_percent, self.storageT_F, incomingWater_T, simRun.building.supplyT_F) #TODO convert to off trigger vol?
                    simRun.pGen[i] = delta_heat
                    self.delta_energy = self.delta_energy + delta_heat

                mixV_high = self.getTankVolAtTemp(simRun.building.supplyT_F)
                mixV = mixV_high - (self.PVol_G_atStorageT * (1 - self.percentUseable)) 
                # if (1 - self.percentUseable) * self.PVol_G_atStorageT > mixV_high:
                    # print(f"fails at {i}, {self.delta_energy}, {delta_heat}, {self.delta_energy - delta_heat}, {highest_vol}, {on_triggerV}, {simRun.hwGenRate}")
                    # print(f"(({on_triggerT} - {self.strat_inter}) / {self.strat_slope}) - {self.delta_energy - delta_heat}")
                simRun.initializeMPRTPValue(mixV, 
                                            self._getAvgTempBetweenTwoVols((1 - self.percentUseable) * self.PVol_G_atStorageT, mixV_high, incomingWater_T), 
                                            i)
                
        simRun.pRun[i] = simRun.pRun[i] * minuteIntervals
        simRun.pV[i] = (self.PVol_G_atStorageT - self.getTankVolAtTemp(simRun.building.supplyT_F)) / self.strat_factor

    def _oneMixedSlugStep(self, simRun : SimulationRun, incomingWater_T, i):
        if simRun.slugSim == False or i == 0:
            return
        prV = convertVolume(simRun.hwDemand[i], self.storageT_F, incomingWater_T, simRun.building.supplyT_F)
        rcV = simRun.building.getDesignReturnFlow()
        simRun.mixV[i] = simRun.mixV[i-1] + prV + rcV

        energy_input = (1000 * self.PCap_kBTUhr * self.defrostFactor) / (rhoCp * 60) 

        temp_calc_total = energy_input + (incomingWater_T * prV) + (simRun.building.getDesignReturnTemp() * rcV) + (simRun.mixT_F[i-1] * simRun.mixV[i-1])


        # print("prV!", prV)
        # print("self.PCap_kBTUhr!", self.PCap_kBTUhr)

        # print("rhoCp!", rhoCp)
        # print("rcV!", rcV)
        # print("simRun.mixT_F[i-1]!", simRun.mixT_F[i-1])
        # print("simRun.mixV[i-1]!", simRun.mixV[i-1])

        # print("incomingWater_T!", incomingWater_T)

        # print("simRun.building.getDesignReturnTemp()!", simRun.building.getDesignReturnTemp())

        simRun.mixT_F[i] = temp_calc_total / simRun.mixV[i]

        # print(f"     simRun.mixT_F[i] = {simRun.mixT_F[i]}")


        # with open('your_file.csv', 'a', newline='', encoding='utf-8') as file:
        #     writer = csv.writer(file)
        #     if i == 1:
        #         writer.writerow(["i", "prV", "rcV","mixV[i-1]", "incomingWater_T", "returnT", "mixT_F[i-1]", "energy_input", "existing_energy", "mixV[i]", "mixT_F[i]"])
        #     writer.writerow([i, prV, rcV, simRun.mixV[i-1], incomingWater_T, simRun.building.getDesignReturnTemp(), simRun.mixT_F[i-1], energy_input, 
        #                      (incomingWater_T * prV) + (simRun.building.getDesignReturnTemp() * rcV) + (simRun.mixT_F[i-1] * simRun.mixV[i-1]), simRun.mixV[i], simRun.mixT_F[i]])  # Replace with your data

        if simRun.mixV[i] >= self.PVol_G_atStorageT * self.percentUseable and simRun.mixT_F[i] < simRun.building.supplyT_F:
            print(f"step {i}: prV = {prV}, rcV = {rcV}, mixV = {simRun.mixV[i-1]}")
            print(f"    incomingWater_T = {incomingWater_T}, returnT = {simRun.building.getDesignReturnTemp()}, mixT = {simRun.mixT_F[i-1]}")
            print("     self.PCap_kBTUhr", self.PCap_kBTUhr)
            print(f"    energy input energy_input = {energy_input/ simRun.mixV[i]} into {((incomingWater_T * prV) + (simRun.building.getDesignReturnTemp() * rcV) + (simRun.mixT_F[i-1] * simRun.mixV[i-1]))/ simRun.mixV[i]}")
            raise Exception (f"{i} MPRTP was not able to heat water fast enough. DHW outage occurred. Water temp at {simRun.mixT_F[i]} at {simRun.mixV[i]} of {self.PVol_G_atStorageT * self.percentUseable} g")
        elif simRun.mixT_F[i] >= simRun.building.supplyT_F:
            simRun.slugSim = False

    def _getAvgTempBetweenTwoVols(self, low_vol, high_vol, incomingT_F):
        if low_vol > high_vol:
            raise Exception(f"low_vol of {low_vol} is higher than high_vol of {high_vol}")
        elif low_vol == high_vol:
            return self.getTemperatureAtTankVol(low_vol, incomingT_F)
        low_temp = self.getTemperatureAtTankVol(low_vol, incomingT_F)
        high_temp = self.getTemperatureAtTankVol(high_vol, incomingT_F)
        vol_of_slug = high_vol - low_vol
        temp_sum = 0.
        if low_temp <= incomingT_F:
            top_of_cold = self.getTankVolAtTemp(incomingT_F)
            temp_sum = temp_sum + (incomingT_F * (top_of_cold - low_vol))
            low_vol = top_of_cold
        if high_temp >= self.storageT_F:
            bottom_of_hot = self.getTankVolAtTemp(self.storageT_F)
            temp_sum = temp_sum + (self.storageT_F * (high_vol - bottom_of_hot))
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
        cyclingV = self.PVol_G_atStorageT * (self.aquaFract - (1 - self.percentUseable))
        mixT_F = self._getAvgTempBetweenTwoVols((1 - self.percentUseable) * self.PVol_G_atStorageT, self.aquaFract * self.PVol_G_atStorageT, simRun.getIncomingWaterT(0))

        simRun.initializeMPRTPValue(cyclingV, mixT_F)
        return simRun