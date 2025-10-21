from ecoengine.objects.systems.SPRTP import SPRTP
from ecoengine.objects.SimulationRun import SimulationRun
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import convertVolume
from ecoengine.objects.Building import Building
import numpy as np
from ecoengine.objects.systemConfigUtils import convertVolume, getPeakIndices, hrTo15MinList

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
        
        self.sim_slug = True
        self.sim_vmix = -1
        self.sim_vtemp = -1

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
        # Cut to the point the aquastat fraction was too small
        volN        = volN[:i]
        heatHours   = heatHours[:i]
        effMixFract = effMixFract[:i]

        return [volN, self._primaryHeatHrs2kBTUHR(heatHours, self.loadUpHours, building, 
            effSwingVolFract = effMixFract, primaryCurve = True, lsFractTotalVol = self.fract_total_vol)[0], heatHours, recIndex]
    
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