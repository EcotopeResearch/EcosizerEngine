from ecoengine.objects.systems.SwingTank import SwingTank
from ecoengine.objects.SimulationRun import SimulationRun
import numpy as np
from ecoengine.objects.Building import Building
from ecoengine.constants.Constants import *
from ecoengine.objects.systemConfigUtils import convertVolume, getMixedTemp, createERSizingCurvePlot, getPeakIndices, checkHeatHours
from ecoengine.objects.PrefMapTracker import PrefMapTracker
from plotly.offline import plot

class SwingTankER(SwingTank):

    def __init__(self, safetyTM, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building : Building,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, aquaFractLoadUp = None, 
                 aquaFractShed = None, loadUpT_F = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, PCap_kBTUhr = None, 
                 ignoreShortCycleEr = False, useHPWHsimPrefMap = False, TMVol_G = None, TMCap_kBTUhr = None, sizeAdditionalER = True, additionalERSaftey = 1.0):

        super().__init__(safetyTM, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building,
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, 
                 aquaFractShed, loadUpT_F, systemModel, numHeatPumps, PVol_G_atStorageT, PCap_kBTUhr, 
                 ignoreShortCycleEr, useHPWHsimPrefMap, TMVol_G, TMCap_kBTUhr)

        self.original_TMCap_kBTUhr = self.TMCap_kBTUhr
        if sizeAdditionalER:
            self.setLoadUPVolumeAndTrigger(building.getDesignInlet())
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
        self.setLoadUPVolumeAndTrigger(building.getDesignInlet())

        # start the 72-hour sizing simulation to find HW deficit. Starting with the primary storage tank almost empty to ensure that water runs out if system is undersized.
        simRun = self.getInitializedSimulation(building, initPV = 0.1, initST=building.supplyT_F, minuteIntervals = minuteIntervals, nDays = 3, forcePeakyLoadshape = True)
        i = 0
        normalFunction = True
        swingV = [0]*len(simRun.hwDemand)
        waterDeficit = [0]*len(simRun.hwDemand)
        while i < len(simRun.hwDemand):
            if normalFunction:
                i = self._findNextIndexOfHWDeficit(simRun, i)
                if i < len(simRun.hwDemand):
                    normalFunction = False
            else:
                # get available supply temperature volume in system to simulate as though water is completely stratified swing tank
                swingV[i-1] = convertVolume(self.TMVol_G, building.supplyT_F, building.getDesignInlet(), simRun.tmT_F[i-1]) + \
                    convertVolume(simRun.pV[i-1], building.supplyT_F, building.getDesignInlet(), self.storageT_F)
                # get full hwGeneration rate of swing tank plus hw coming in from primary system
                fullHWGenRate = (1000 * self.original_TMCap_kBTUhr / (60/minuteIntervals) /rhoCp / (building.supplyT_F - building.getDesignInlet()) * self.defrostFactor) + \
                    simRun.hwGenRate
                recircLossAtTime = (building.recirc_loss / (rhoCp * (building.supplyT_F - building.getDesignInlet()))) / (60/minuteIntervals)
                while i < len(simRun.hwDemand) and not normalFunction:
                    waterLeavingSystem = simRun.hwDemand[i] + recircLossAtTime
                    if convertVolume(simRun.hwGenRate, self.storageT_F, building.getDesignInlet(), building.supplyT_F) >= simRun.hwDemand[i]:
                        simRun.pV[i-1] = 0
                        if swingV[i-1] <= self.TMVol_G:
                            # Once appropriatly sized, water should never dip below supply temp so correct to supply temp once deficit is no longer an issue
                            simRun.tmT_F[i-1] = building.supplyT_F
                        else:
                            simRun.tmT_F[i-1] =  ((swingV[i-1] * (building.supplyT_F - building.getDesignInlet()))/self.TMVol_G) + building.getDesignInlet()
                        normalFunction = True
                    else:
                        swingV[i] = swingV[i-1] + fullHWGenRate - waterLeavingSystem
                        waterDeficit[i] = max(waterLeavingSystem - fullHWGenRate, 0) # add water deficit if positive
                        i += 1
        # add additional ER to compensate for undersized CHPWH
        self.TMCap_kBTUhr = self.original_TMCap_kBTUhr + (((max(waterDeficit) * (60/minuteIntervals) * rhoCp * (building.supplyT_F - building.getDesignInlet())) / 1000.) * saftey_factor)

        # set performance map back to its original form
        self.perfMap = perfMap_holder
        self.resetToDefaultCapacity()
        return self.TMCap_kBTUhr

    def _findNextIndexOfHWDeficit(self, simRun : SimulationRun, i):
        incomingWater_T = simRun.building.getDesignInlet()
        while i < len(simRun.hwDemand):
            if simRun.pV[i-1] >= 0:
                # The following is esentially the normal swing tank runOneSystemStep() execpt uses design IWT instead of the climate-informed one
                # there is already no preSystemStepSetUp() because simulation is very basic
                simRun.hw_outSwing[i] = convertVolume(simRun.hwDemand[i], simRun.tmT_F[i-1], incomingWater_T, simRun.building.supplyT_F)    
                simRun.tmheating, simRun.tmT_F[i], simRun.tmRun[i] = self._runOneSwingStep(simRun.building, 
                    simRun.tmheating, simRun.tmT_F[i-1], simRun.hw_outSwing[i], self.storageT_F, minuteIntervals = simRun.minuteIntervals, erCalc = True)
                mixedGHW = convertVolume(simRun.hwGenRate, self.storageT_F, incomingWater_T, simRun.building.supplyT_F)
                simRun.pheating, simRun.pV[i], simRun.pGen[i], simRun.pRun[i] = self.runOnePrimaryStep(pheating = simRun.pheating,
                                                                                                        Vcurr = simRun.pV[i-1], 
                                                                                                        hw_out = simRun.hw_outSwing[i], 
                                                                                                        hw_in = mixedGHW, 
                                                                                                        mode = simRun.getLoadShiftMode(i),
                                                                                                        modeChanged = (simRun.getLoadShiftMode(i) != simRun.getLoadShiftMode(i-1)),
                                                                                                        minuteIntervals = simRun.minuteIntervals,
                                                                                                        erCalc = True)
            else:
                return i-1
            i += 1
        return i

    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None, erCalc=False):
        incomingWater_T = simRun.getIncomingWaterT(i)
        self.preSystemStepSetUp(simRun, i, incomingWater_T + 15.0, minuteIntervals, oat) # CHPWH IWT is assumed 15°F (adjustable) warmer than DCW temperature on average, based on lab test data. 

        # aquire draw amount for time step
        last_temp = simRun.tmT_F[i-1]
        simRun.hw_outSwing[i] = convertVolume(simRun.hwDemand[i], last_temp, incomingWater_T, simRun.building.supplyT_F)
        #Get the generation rate in storage temp
        mixedGHW = convertVolume(simRun.hwGenRate, self.storageT_F, incomingWater_T, simRun.building.supplyT_F)
        if simRun.hw_outSwing[i] > simRun.pV[i-1] + mixedGHW:
            hwVol_G = simRun.pV[i-1] + mixedGHW
            mixedT_F = getMixedTemp(incomingWater_T, self.storageT_F, simRun.hw_outSwing[i] - hwVol_G, hwVol_G)
            simRun.tmheating, simRun.tmT_F[i], simRun.tmRun[i] = self._runOneSwingStep(simRun.building, 
                simRun.tmheating, last_temp, simRun.hw_outSwing[i], mixedT_F, minuteIntervals = minuteIntervals)#, erCalc=True)
        else:
            simRun.tmheating, simRun.tmT_F[i], simRun.tmRun[i] = self._runOneSwingStep(simRun.building, 
                simRun.tmheating, last_temp, simRun.hw_outSwing[i], self.storageT_F, minuteIntervals = minuteIntervals)#, erCalc=True)

        simRun.pheating, simRun.pV[i], simRun.pGen[i], simRun.pRun[i] = self.runOnePrimaryStep(pheating = simRun.pheating,
                                                                                                Vcurr = simRun.pV[i-1], 
                                                                                                hw_out = simRun.hw_outSwing[i], 
                                                                                                hw_in = mixedGHW, 
                                                                                                mode = simRun.getLoadShiftMode(i),
                                                                                                modeChanged = (simRun.getLoadShiftMode(i) != simRun.getLoadShiftMode(i-1)),
                                                                                                minuteIntervals = minuteIntervals,
                                                                                                erCalc = True)
        if simRun.pV[i] < 0.:
            simRun.pV[i] = 0.

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
                er_cap_kBTUhr = self.sizeERElement(building, additionalERSaftey, 15)
            er_cap_kW.append(round(er_cap_kBTUhr/W_TO_BTUHR,0))
            fract_covered.append(i)
            i -= 10

        # except Exception:
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
        
            labelText = "Percent Coverage: <b id='point_x'>" + str(float(x[len(fig.data)-i-1])) + "</b> %, Electric Resistance Heating Capacity: <b id='point_y'>" + \
                str(round(y[len(fig.data)-i-1],1)) + "</b> kW" 
        
            step = dict(
                # this value must match the values in x = loads(form['x_data']) #json loads
                label = labelText,
                method="update",
                args=[{"visible": [False] * len(fig.data)},
                    ],  # layout attribute
            )
            step["args"][0]["visible"][0] = True  # Make sure first trace is visible since its the line
            step["args"][0]["visible"][len(fig.data)-i] = True  # Toggle i'th trace to "visible"
            steps.append(step)

        sliders = [dict(    
            steps=steps,
            active=len(x)-startind-1,
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