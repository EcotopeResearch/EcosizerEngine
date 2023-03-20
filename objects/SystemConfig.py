from constants.Constants import *
from objects.Building import Building
import numpy as np
from scipy.stats import norm #lognorm
from plotly.graph_objs import Figure, Scatter
from plotly.offline import plot
from plotly.subplots import make_subplots
from objects.systemConfigUtils import roundList, mixVolume, HRLIST_to_MINLIST, getPeakIndices, checkLiqudWater

class SystemConfig:
    def __init__(self, building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, 
                 doLoadShift = False, cdf_shift = 1, schedule = None):
        # TODO input checking - also for buildings

        # check inputs. Schedule not checked because it is checked elsewhere
        self._checkInputs(building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, doLoadShift, cdf_shift)
        
        self.doLoadShift = doLoadShift
        self.building = building        
        self.totalHWLoad = self.building.magnitude
        self.storageT_F = storageT_F
        self.defrostFactor = defrostFactor
        self.percentUseable = percentUseable
        self.compRuntime_hr = compRuntime_hr
        self.aquaFract = aquaFract

        if doLoadShift and not schedule is None:
            self.setLoadShift(schedule, cdf_shift)
        else:
            self.schedule = [1] * 24
            self.fract_total_vol = 1 # fraction of total volume for for load shifting, or 1 if no load shifting

        #Check if need to increase sizing to meet lower runtimes for load shift
        self.maxDayRun_hr = min(self.compRuntime_hr, sum(self.schedule))

        #size system
        self.PVol_G_atStorageT, self.effSwingFract, self.LSconstrained = self.sizePrimaryTankVolume(self.maxDayRun_hr)
        self.PCap_kBTUhr = self.primaryHeatHrs2kBTUHR(self.maxDayRun_hr, self.effSwingFract )

    def _checkInputs(self, building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, doLoadShift, cdf_shift):
        if not isinstance(building, Building):
            raise Exception("Error: Building is not valid.")
        if not (isinstance(storageT_F, int) or isinstance(storageT_F, float)) or not checkLiqudWater(storageT_F):
            raise Exception('Invalid input given for Storage temp, it must be between 32 and 212F.')
        if not (isinstance(defrostFactor, int) or isinstance(defrostFactor, float)) or defrostFactor < 0 or defrostFactor > 1:
            raise Exception("Invalid input given for Defrost Factor, must be a number between 0 and 1.")
        if not (isinstance(percentUseable, int) or isinstance(percentUseable, float)) or percentUseable > 1 or percentUseable < 0:
            raise Exception("Invalid input given for percentUseable, must be a number between 0 and 1.")
        if not isinstance(compRuntime_hr, int):
            raise Exception("Invalid input given for compRuntime_hr, must be an integer.")
        if not (isinstance(aquaFract, int) or isinstance(aquaFract, float)) or aquaFract > 1 or aquaFract < 0:
            raise Exception("Invalid input given for aquaFract must, be a number between 0 and 1.")
        if not (isinstance(cdf_shift, int) or isinstance(cdf_shift, float)) or cdf_shift > 1 or cdf_shift < 0:
            raise Exception("Invalid input given for cdf_shift, must be a number between 0 and 1.")
        if not isinstance(doLoadShift, bool):
            raise Exception("Invalid input given for doLoadShift, must be a boolean.")

    def getSizingResults(self):
        """
        Returns the minimum primary volume and heating capacity sizing results

        Returns
        -------
        list
            self.PVol_G_atStorageT, self.PCap_kBTUhr
        """
        return [self.PVol_G_atStorageT, self.PCap_kBTUhr]

    def simulate(self, initPV=None, initST=None, Pcapacity=None, Pvolume=None):
        """
        Inputs
        ------
        initPV : float
            Primary volume at start of the simulation
        initST : float
            Primary Swing tank at start of the simulation
        """

        G_hw, D_hw, V0, Vtrig, pV, pheating = self.getInitialSimulationValues(Pcapacity, Pvolume)

        hw_outSwing = [0] * (len(G_hw))
        hw_outSwing[0] = D_hw[0]
        prun = [0] * (len(G_hw))

        if initPV:
            pV[0] = initPV

        # Run the "simulation"
        for ii in range(1, len(G_hw)):
            mixedDHW = mixVolume(D_hw[ii], self.storageT_F, self.building.incomingT_F, self.building.supplyT_F)
            mixedGHW = mixVolume(G_hw[ii], self.storageT_F, self.building.incomingT_F, self.building.supplyT_F)
            pheating, pV[ii], prun[ii] = self.runOnePrimaryStep(pheating, V0, Vtrig, pV[ii-1], mixedDHW, mixedGHW)

        # The None's are placeholders for certain metrics from subclasses
        return [roundList(pV, 3),
                roundList(G_hw, 3),
                roundList(D_hw, 3),
                roundList(prun, 3),
                None,
                None,
                None]

    def getInitialSimulationValues(self, Pcapacity=None, Pvolume=None):
        """
        Returns sizing storage depletion and load results for water volumes at
        the supply temperature

        Parameters
        ----------
        Pcapacity : float
            The primary heating capacity in kBTUhr to use for the simulation,
            default is the sized system
        Pvolume : float
            The primary storage volume in gallons to  to use for the simulation,
            default is the sized system

        Returns
        -------
        list [ V, G_hw, D_hw, run ]
        V - Volume of HW in the tank with time at the strorage temperature.
        G_hw - The generation of HW with time at the supply temperature
        D_hw - The hot water demand with time at the tsupply temperature
        run - The actual output in gallons of the HPWH with time
        """
        if not Pcapacity:
            Pcapacity =  self.PCap_kBTUhr

        if not Pvolume:
            Pvolume =  self.PVol_G_atStorageT

        loadShapeN = self.building.loadshape
        if self.doLoadShift:
            loadShapeN = self.building.avgLoadshape

        # Get the generation rate from the primary capacity
        G_hw = 1000 * Pcapacity / rhoCp / (self.building.supplyT_F - self.building.incomingT_F) \
               * self.defrostFactor * np.tile(self.schedule,3)
        
        # Define the use of DHW with the normalized load shape
        D_hw = self.totalHWLoad * self.fract_total_vol * np.tile(loadShapeN, 3)

        # To per minute from per hour
        G_hw = np.array(HRLIST_to_MINLIST(G_hw)) / 60
        D_hw = np.array(HRLIST_to_MINLIST(D_hw)) / 60

        # Init the "simulation"
        V0 = np.ceil(Pvolume * self.percentUseable)
        Vtrig = np.ceil(Pvolume * (1 - self.aquaFract)) + 1 # To prevent negatives with any of that rounding math.
        pV = [V0] + [0] * (len(G_hw) - 1)

        pheating = False

        return G_hw, D_hw, V0, Vtrig, pV, pheating
    
    def setLoadShift(self, schedule, cdf_shift=1):
        """
        Sets the load shifting schedule from input schedule

        Parameters
        ----------
        schedule : array_like
            List or array of 0's and 1's for don't run and run.

        cdf_shift : float
            Percentile of days which need to be covered by load shifting

        """
        # Check
        if len(schedule) != 24 : #TODO ensure schedule is valid and add load up
            raise Exception("loadshift is not of length 24 but instead has length of "+str(len(schedule))+".")
        if sum(schedule) == 0 :
            raise Exception("When using Load shift the HPWH's must run for at least 1 hour each day.")
        if cdf_shift < 0.25 :
            raise Exception("Load shift only available for above 25 percent of days.")
        if cdf_shift > 1 :
            raise Exception("Cannot load shift for more than 100 percent of days")

        self.schedule = schedule
        self.loadshift = np.array(schedule, dtype = float)# Coerce to numpy array of data type float

        # adjust for cdf_shift
        if cdf_shift == 1: # meaing 100% of days covered by load shift
            self.fract_total_vol = 1
        else:
            # calculate fraction totalHWLoad of required to meet load shift days
            fract = norm_mean + norm_std * norm.ppf(cdf_shift) #TODO norm_mean and std are currently from multi-family, need other types
            self.fract_total_vol = fract if fract <= 1. else 1.
        
        self.doLoadShift = True # TODO necessary?

    def _checkHeatHours(self, heathours):
        """
        Quick check to see if heating hours is a valid number between 1 and 24

        Parameters
        ----------
        heathours (float or numpy.ndarray)
            The number of hours primary heating equipment can run.
        """
        if isinstance(heathours, np.ndarray):
            if any(heathours > 24) or any(heathours <= 0):
                raise Exception("Heat hours is not within 1 - 24 hours")
        else:
            if heathours > 24 or heathours <= 0:
                raise Exception("Heat hours is not within 1 - 24 hours")

    # SwingTank has it's own implimentation
    def primaryHeatHrs2kBTUHR(self, heathours, effSwingVolFract=1):
        """
        Converts from hours of heating in a day to heating capacity.

        Parameters
        ----------
        heathours : float or numpy.ndarray
            The number of hours primary heating equipment can run.

        effSwingVolFract : float or numpy.ndarray
            The fractional adjustment to the total hot water load for the
            primary system. Only used in a swing tank system.

        Returns
        -------
        heatCap
            The heating capacity in [btu/hr].
        """
        self._checkHeatHours(heathours)
        heatCap = self.totalHWLoad / heathours * rhoCp * \
            (self.building.supplyT_F - self.building.incomingT_F) / self.defrostFactor /1000.
        return heatCap
    
    def sizePrimaryTankVolume(self, heatHrs):
        """
        Calculates the primary storage using the Ecotope sizing methodology

        Parameters
        ----------
        heatHrs : float
            The number of hours primary heating equipment can run in a day.

        Returns
        -------
        totalVolMax : float
            The total storage volume in gallons adjusted to the storage tempreature
        """
        if heatHrs <= 0 or heatHrs > 24:
            raise Exception("Heat hours is not within 1 - 24 hours")
        # Fraction used for adjusting swing tank volume.
        effMixFract = 1.
        # If the system is sized for load shift days or the load shift
        # requirement is less than required
        largerLS = False

        # Running vol
        runningVol_G, effMixFract = self.calcRunningVol(heatHrs, np.ones(24), self.building.loadshape, effMixFract)

        # If doing load shift, solve for the runningVol_G and take the larger volume
        if self.doLoadShift:
            LSrunningVol_G = 0
            LSeffMixFract = 0
            # calculate loadshift sizing with avg loadshape (see page 19 of methodology documentation)
            LSrunningVol_G, LSeffMixFract = self.calcRunningVol(heatHrs, self.schedule, self.building.avgLoadshape, LSeffMixFract)
            LSrunningVol_G *= self.fract_total_vol

            # Get total volume from max of primary method or load shift method
            if LSrunningVol_G > runningVol_G:
                runningVol_G = LSrunningVol_G
                effMixFract = LSeffMixFract
                largerLS = True

        totalVolMax = self.getTotalVolMax(runningVol_G)

        # Check the Cycling Volume ############################################
        cyclingVol_G = totalVolMax * (self.aquaFract - (1 - self.percentUseable))
        minRunVol_G = pCompMinimumRunTime * (self.totalHWLoad * effMixFract / heatHrs) # (generation rate - no usage)

        if minRunVol_G > cyclingVol_G:
            min_AF = minRunVol_G / totalVolMax + (1 - self.percentUseable)
            if min_AF < 1:
                raise ValueError("01", "The aquastat fraction is too low in the storge system recommend increasing the maximum run hours in the day or increasing to a minimum of: ", round(min_AF,3))
            raise ValueError("02", "The minimum aquastat fraction is greater than 1. This is due to the storage efficency and/or the maximum run hours in the day may be too low. Try increasing these values, we reccomend 0.8 and 16 hours for these variables respectively." )

        # Return the temperature adjusted total volume ########################
        return totalVolMax, effMixFract, largerLS
    
    # @abstractmethod
    def calcRunningVol(self, heatHrs, onOffArr, loadshape, effMixFract = 0):
        """
        Function to find the running volume for the hot water storage tank, which
        is needed for calculating the total volume for primary sizing and in the event of load shift sizing
        represents the entire volume.

        Parameters
        ----------
        heatHrs : float
            The number of hours primary heating equipment can run in a day.
        onOffArr : ndarray
            array of 1/0's where 1's allow heat pump to run and 0's dissallow. of length 24.
        loadshape:
        effMixFract: Int
            will return effMixFract to retain the value. Needed because of SwingTank subclass implimentation

        Raises
        ------
        Exception: Error if oversizeing system.

        Returns
        -------
        runV_G : float
            The running volume in gallons

        """          
        genrate = np.tile(onOffArr,2) / heatHrs #hourly
        diffN = genrate - np.tile(loadshape,2) #hourly
        diffInd = getPeakIndices(diffN[0:24]) #Days repeat so just get first day!
        # print(self.totalHWLoad)
        diffN *= self.totalHWLoad
        # Get the running volume ##############################################
        if len(diffInd) == 0:
            raise Exception("ERROR ID 03","The heating rate is greater than the peak volume the system is oversized! Try increasing the hours the heat pump runs in a day", )
        runV_G = 0
        for peakInd in diffInd:
            #Get the rest of the day from the start of the peak
            diffCum = np.cumsum(diffN[peakInd:])  #hourly
            runV_G = max(runV_G, -min(diffCum[diffCum<0.])) #Minimum value less than 0 or 0.

        return runV_G, effMixFract
    
    def getTotalVolMax(self, runningVol_G):
        return mixVolume(runningVol_G, self.storageT_F, self.building.incomingT_F, self.building.supplyT_F) / (1-self.aquaFract)
    
    def primaryCurve(self):
        """
        Sizes the primary system curve. Will catch the point at which the aquatstat
        fraction is too small for system and cuts the return arrays to match cutoff point.

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
        maxHeatHours = 1/(max(self.building.loadshape))*1.001   
        
        arr1 = np.arange(24, self.maxDayRun_hr, delta)
        recIndex = len(arr1)
        heatHours = np.concatenate((arr1, np.arange(self.maxDayRun_hr, maxHeatHours, delta)))
        
        volN = np.zeros(len(heatHours))
        effMixFract = np.ones(len(heatHours))
        for ii in range(0,len(heatHours)):
            try:
                volN[ii], effMixFract[ii], _ = self.sizePrimaryTankVolume(heatHours[ii])
            except ValueError:
                break
        # Cut to the point the aquastat fraction was too small
        volN        = volN[:ii]
        heatHours   = heatHours[:ii]
        effMixFract = effMixFract[:ii]

        return [volN, self.primaryHeatHrs2kBTUHR(heatHours, effMixFract), heatHours, recIndex]

    
    def runOnePrimaryStep(self, pheating, V0, Vtrig, Vcurr, hw_out, hw_in):
        """
        Runs one step on the primary system. This changes the volume of the primary system
        by assuming there is hot water removed at a volume of hw_out and hot water
        generated or added at a volume of hw_in. This is assuming the system is perfectly
        stratified and all of the hot water above the cold temperature is at the storage temperature.

        Parameters
        ----------
        Vcurr : float
            The primary volume at the timestep.
        hw_out : float
            The volume of DHW removed from the primary system, assumed that
            100% of what of what is removed is replaced
        hw_in : float
            The volume of hot water generated in a time step

        Returns
        -------
        Vnew : float
            The new primary volume at the timestep.
        did_run : float
            The volume of hot water generated during the time step.

        """
        did_run = 0
        Vnew = 0
        if pheating:
            Vnew = Vcurr + hw_in - hw_out # If heating, generate HW and lose HW
            did_run = hw_in

        else:  # Else not heating,
            Vnew = Vcurr - hw_out # So lose HW
            if Vnew < Vtrig: # If should heat
                time_missed = (Vtrig - Vnew)/hw_out # Volume below turn on / rate of draw gives time below tigger
                Vnew += hw_in * time_missed # Start heating
                did_run = hw_in * time_missed
                pheating = True

        if Vnew > V0: # If overflow
            time_over = (Vnew - V0) / (hw_in - hw_out) # Volume over generated / rate of generation gives time above full
            Vnew = V0 - hw_out * time_over # Make full with missing volume
            did_run = hw_in * (1-time_over)
            pheating = False # Stop heating

        if Vnew < 0:
           raise Exception("Primary storage ran out of Volume!")

        return pheating, Vnew, did_run
    
    def plotStorageLoadSim(self, return_as_div=True):
        """
        Returns a plot of the of the simulation for the minimum sized primary
        system as a div or plotly figure. Can plot the minute level simulation

        Parameters
        ----------
        return_as_div
            A logical on the output, as a div (true) or as a figure (false)
        Returns
        -------
        div/fig
            plot_div
        """
        [V, G_hw, D_hw, run, _, _, _] = self.simulate()

        hrind_fromback = 24 # Look at the last 24 hours of the simulation not the whole thing
        run = np.array(run[-(60*hrind_fromback):])*60
        G_hw = np.array(G_hw[-(60*hrind_fromback):])*60
        D_hw = np.array(D_hw[-(60*hrind_fromback):])*60
        V = np.array(V[-(60*hrind_fromback):])

        if any(i < 0 for i in V):
            raise Exception("Primary storage ran out of Volume!")

        fig = Figure()

        # Do primary components
        x_data = list(range(len(V)))

        if self.doLoadShift:
            ls_off = [int(not x)* max(V)*2 for x in G_hw]
            fig.add_trace(Scatter(x=x_data, y=ls_off, name='Load Shift Off Period',
                                  mode='lines', line_shape='hv',
                                  opacity=0.5, marker_color='grey',
                                  fill='tonexty'))

        fig.add_trace(Scatter(x=x_data, y=V, name='Useful Storage Volume at Storage Temperature',
                              mode='lines', line_shape='hv',
                              opacity=0.8, marker_color='green'))
        fig.add_trace(Scatter(x=x_data, y=run, name = "Hot Water Generation at Storage Temperature",
                              mode='lines', line_shape='hv',
                              opacity=0.8, marker_color='red'))
        fig.add_trace(Scatter(x=x_data, y=D_hw, name='Hot Water Demand at Supply Temperature',
                              mode='lines', line_shape='hv',
                              opacity=0.8, marker_color='blue'))
        fig.update_yaxes(range=[0, np.ceil(max(np.append(V,D_hw))/100)*100])

        fig.update_layout(title="Hot Water Simulation",
                          xaxis_title= "Minute of Day",
                          yaxis_title="Gallons or\nGallons per Hour",
                          width=900,
                          height=700)

        if return_as_div:
            plot_div = plot(fig, output_type='div', show_link=False, link_text="",
                        include_plotlyjs = False)
            return plot_div
        return fig
    
    
class Primary(SystemConfig):
    def __init__(self, building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, 
                 doLoadShift = False, cdf_shift = 1, schedule = None):
        super().__init__(building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, 
                 doLoadShift, cdf_shift, schedule)

