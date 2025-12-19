from ecoengine.objects.systems.SwingTank import SwingTank
from ecoengine.objects.SimulationRun import SimulationRun
import numpy as np
from ecoengine.objects.Building import Building
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import convertVolume, getMixedTemp, createERSizingCurvePlot, getPeakIndices, checkHeatHours
from ecoengine.objects.PrefMapTracker import PrefMapTracker
from plotly.offline import plot

class SwingTankER(SwingTank):

    def __init__(self, safetyTM, storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building = None, outletLoadUpT = None,
                 onFractLoadUp = None, offFractLoadUp = None, onLoadUpT = None, offLoadUpT = None, onFractShed = None, offFractShed = None, onShedT = None, offShedT = None,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, 
                 PCap_kBTUhr = None, useHPWHsimPrefMap = False, TMVol_G = None, TMCap_kBTUhr = None, sizeAdditionalER = True, additionalERSaftey = 1.0):

        super().__init__(safetyTM, storageT_F, defrostFactor, percentUseable, compRuntime_hr, onFract, offFract, onT, offT, building,
                 outletLoadUpT, onFractLoadUp, offFractLoadUp, onLoadUpT, offLoadUpT, onFractShed, offFractShed, onShedT, offShedT,
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, systemModel, numHeatPumps, PVol_G_atStorageT, 
                 PCap_kBTUhr, useHPWHsimPrefMap, TMVol_G, TMCap_kBTUhr)

        self.original_TMCap_kBTUhr = self.TMCap_kBTUhr
        if sizeAdditionalER:
            self.sizeERElement(building, additionalERSaftey)

    def sizeERElement(self, building : Building, saftey_factor = 1.0, minuteIntervals = 1):
        if building is None:
            raise Exception("Cannot size additional swing tank electric resistance without building parameter.")
        elif self.perfMap is None:
            raise Exception("Performance map for system has not been set. Cannot size additional swing tank electric resistance.")
        
        self.TMCap_kBTUhr = self.original_TMCap_kBTUhr
        # get base output capacity for primary HPWH using design climate temperatures
        self.perfMap.resetFlags()
        output_kBTUhr, input_kBTUhr = self.perfMap.getCapacity(building.getDesignOAT(), building.getDesignInlet() + 15.0, self.storageT_F) # Add 15 degrees to IWT as per swing tank norm 
        if sum(self.perfMap.getExtrapolationFlags()) > 0:
            # TODO If we need to deal with actual models with this later, we will need to determine what extrapolations will cause errors
            raise Exception("Design climate values (OAT, incoming water temperature) were outside of performance map for the CHPWH model chosen.")
        self.perfMap.resetFlags()

        # create a temporary performance map that will return ONLY that output capacity values for the sizing simulation
        perfMap_holder = self.perfMap # Store existing performance map in a temporary variable
        self.perfMap = PrefMapTracker(output_kBTUhr, usePkl=False, kBTUhr = True) # create simple performance map that only uses default output capacity
        self.setCapacity(self.perfMap.getDefaultCapacity())

        # start the 72-hour sizing simulation to find HW deficit. Starting with the primary storage tank almost empty to ensure that water runs out if system is undersized.
        simRun_empty = self.getInitializedSimulation(building, initPV = 0, initST=building.supplyT_F, minuteIntervals = minuteIntervals, nDays = 2, forcePeakyLoadshape = True)
        simRun_full = self.getInitializedSimulation(building, initPV = None, initST=building.supplyT_F, minuteIntervals = minuteIntervals, nDays = 2, forcePeakyLoadshape = True)
        i = 0
        tempDeficit = [0]*len(simRun_empty.hwDemand)
        while i < len(simRun_empty.hwDemand):
            self.runOneSystemStep(simRun_empty, i, minuteIntervals = minuteIntervals, oat = None, erCalc=True)
            self.runOneSystemStep(simRun_full, i, minuteIntervals = minuteIntervals, oat = None, erCalc=True)
            if simRun_empty.tmT_F[i] < building.supplyT_F:
                tempDeficit[i] = simRun_empty.building.supplyT_F - simRun_empty.tmT_F[i]
                simRun_empty.tmT_F[i] = building.supplyT_F
            if simRun_full.tmT_F[i] < building.supplyT_F:
                tempDeficit[i] = max(simRun_full.building.supplyT_F - simRun_full.tmT_F[i], tempDeficit[i])
                simRun_full.tmT_F[i] = building.supplyT_F
            i = i + 1

        self.TMCap_kBTUhr = self.original_TMCap_kBTUhr + (((self.TMVol_G * (60/minuteIntervals) * rhoCp * (max(tempDeficit))) / 1000.) * saftey_factor)
        # set performance map back to its original form
        self.perfMap = perfMap_holder
        self.resetToDefaultCapacity()
        return self.TMCap_kBTUhr

    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None, erCalc=False):
        incomingWater_T = simRun.getIncomingWaterT(i)
        self.preSystemStepSetUp(simRun, i, incomingWater_T + 15.0, minuteIntervals, oat) # CHPWH IWT is assumed 15°F (adjustable) warmer than DCW temperature on average, based on lab test data. 
        ls_mode = simRun.getLoadShiftMode(i)
        # aquire draw amount for time step
        last_temp = simRun.tmT_F[i-1]
        simRun.hw_outSwing[i] = convertVolume(simRun.hwDemand[i], last_temp, incomingWater_T, simRun.building.supplyT_F)
        #Get the generation rate in storage temp
        mixedGHW = convertVolume(simRun.hwGenRate, self.getStorageOutletTemp(ls_mode), incomingWater_T, simRun.building.supplyT_F)
        if simRun.hw_outSwing[i] > simRun.pV[i-1] + mixedGHW:
            hwVol_G = simRun.pV[i-1] + mixedGHW
            mixedT_F = getMixedTemp(incomingWater_T, self.getStorageOutletTemp(ls_mode), simRun.hw_outSwing[i] - hwVol_G, hwVol_G)
            simRun.tmheating, simRun.tmT_F[i], simRun.tmRun[i] = self._runOneSwingStep(simRun.building, 
                simRun.tmheating, last_temp, simRun.hw_outSwing[i], mixedT_F, minuteIntervals = minuteIntervals, erCalc=erCalc)
        else:
            simRun.tmheating, simRun.tmT_F[i], simRun.tmRun[i] = self._runOneSwingStep(simRun.building, 
                simRun.tmheating, last_temp, simRun.hw_outSwing[i], self.getStorageOutletTemp(ls_mode), minuteIntervals = minuteIntervals, erCalc=erCalc)

        self.runOnePrimaryStep(simRun, i, simRun.hw_outSwing[i], incomingWater_T, erCalc = True)

        if simRun.pV[i] < 0.:
            simRun.pV[i] = 0.
            simRun.delta_energy = -1 * ((1-self.onFract)*self.PVol_G_atStorageT) # delta energy cannot shrink past empty tank
            

    def getERCapacityDif(self, kW = True):
        TMCap_kBTUhr_dif = self.TMCap_kBTUhr - self.original_TMCap_kBTUhr
        if kW:
            return TMCap_kBTUhr_dif / W_TO_BTUHR
        return TMCap_kBTUhr_dif
    
    def erSizedPoints(self, building : Building, additionalERSaftey = 1.0):
        """
        Creates points for sizing curve plot based on percent of load covered.

        Parameters
        ----------
        building : Building
            The building the system being sized for
        additionalERSaftey : int
            saftey factor to be applied to electric resistance sizing

        Returns
        erSizingCombos : array
            Array of volume and capacity combinations sized based on the number of load up hours.
        """
        if self.TMCap_kBTUhr <= self.original_TMCap_kBTUhr:
            raise Exception("Electric Resistance Sizing Graph can not be generated because no additional electric resistance is needed")
        
        original_magnitude = building.magnitude
        original_erSize_kBTUhr = self.TMCap_kBTUhr
        
        er_cap_kW = []
        fract_covered = []
        i = 120.
        startind = 0
        # try:
        while self.TMCap_kBTUhr > self.original_TMCap_kBTUhr and i > 0: # stopping point is normal sizing point
            if i == 100:
                startind = len(fract_covered)
                er_cap_kBTUhr = original_erSize_kBTUhr
            else:
                fract = i/100.
                building.magnitude = original_magnitude * fract
                er_cap_kBTUhr = self.sizeERElement(building, additionalERSaftey, 1)
            er_cap_kW.append(round(er_cap_kBTUhr/W_TO_BTUHR,0))
            fract_covered.append(i)
            i -= 10

        # reverse the lists because they are backwards:
        fract_covered.reverse()
        er_cap_kW.reverse()
        startind = (len(fract_covered)-1)-startind

        building.magnitude = original_magnitude
        self.TMCap_kBTUhr = original_erSize_kBTUhr
        return [er_cap_kW, fract_covered, startind] # TODO edge cases around start index
    
    
    def getERCurveAndSlider(self, x, y, startind, returnAsDiv = True):
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
        return_as_div : boolean
            A logical on the output, as a div string (true) or as a figure (false)
        
        Returns
        --------
        plotdiv : a plotly div of the graph
        
        
        """
        fig = createERSizingCurvePlot(x, y, startind)
    
        # Create and add sliderbar steps
        steps = []
        for i in range(1,len(fig.data)):
        
            labelText = "Percent Coverage: <b id='point_x'>" + str(float(x[i-1])) + "</b> %, Electric Resistance Heating Capacity: <b id='point_y'>" + \
                str(round(y[i-1],1)) + "</b> kW" 
        
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
                'prefix': '<b>Electric Resistance Size</b> ',
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