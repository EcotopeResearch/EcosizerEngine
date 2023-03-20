from objects.SystemConfig import SystemConfig
import numpy as np
from objects.Building import Building
from constants.Constants import *
from objects.systemConfigUtils import roundList, mixVolume, HRLIST_to_MINLIST, getPeakIndices
from plotly.graph_objs import Figure, Scatter
from plotly.offline import plot
from plotly.subplots import make_subplots

class SwingTank(SystemConfig):

    Table_Napts = [0, 12, 24, 48, 96]
    sizingTable_EMASHRAE = ["80", "80", "80", "120 - 300", "120 - 300"]
    sizingTable_CA = ["80", "96", "168", "288", "480"]

    def __init__(self, safetyTM, building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, 
                 doLoadShift = False, cdf_shift = 1, schedule = None, CA = False):
        # if not hasattr(inputs, 'safetyTM'):
        #     raise Exception("safetyTM required")
        if safetyTM <= 1.:
            raise Exception("The saftey factor for the temperature maintenance system must be greater than 1 or the system will never keep up with the losses.")
        self.safetyTM = safetyTM
        self.TMVol_G = 300 # TODO Scott to figure out table stuff for self.TMVol_G use 120 for now TODO had to set to 300
        self.element_deadband_F = 8.
        self.TMCap_kBTUhr = self.safetyTM * building.recirc_loss / 1000.
        super().__init__(building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, 
                 doLoadShift, cdf_shift, schedule)
    
    def getSizingResults(self):
        """
        Returns the minimum primary volume and heating capacity sizing results

        Returns
        -------
        list
            self.PVol_G_atStorageT, self.PCap_kBTUhr, self.TMVol_G, self.TMCap_kBTUhr
        """
        return [self.PVol_G_atStorageT, self.PCap_kBTUhr, self.TMVol_G, self.TMCap_kBTUhr]
    
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
        effMixFract: int
            not used in this subclass implimentation but needed because of class inheritence

        Raises
        ------
        Exception: Error if oversizeing system.

        Returns
        -------
        runV_G : float
            The running volume in gallons

        """

        eff_HW_mix_faction = effMixFract
        genrate = np.tile(onOffArr,2) / heatHrs #hourly
        diffN   = genrate - np.tile(loadshape, 2) #hourly
        diffInd = getPeakIndices(diffN[0:24]) #Days repeat so just get first day!
                
        # Get the running volume ##############################################
        if len(diffInd) == 0:
            raise Exception("ERROR ID 03","The heating rate is greater than the peak volume the system is oversized! Try increasing the hours the heat pump runs in a day",)

        # Watch out for cases where the heating is to close to the initial peak value so also check the hour afterwards too.
        nRealpeaks = len(diffInd)
        diffInd = np.append(diffInd, diffInd+1)
        diffInd = diffInd[diffInd < 24]
        runV_G = 0
        for peakInd in diffInd:
            hw_out = np.tile(loadshape, 2)
            hw_out = np.array(HRLIST_to_MINLIST(hw_out[peakInd:peakInd+24])) \
                / 60 * self.totalHWLoad # to minute
            
            # Simulate the swing tank assuming it hits the peak just above the supply temperature.
            # Get the volume removed for the primary adjusted by the swing tank
            N = len(hw_out)
            [_, _, hw_out_from_swing] = self.simJustSwing(N, hw_out, self.building.supplyT_F + 0.1)

            # Get the effective adjusted hot water demand on the primary system at the storage temperature.
            temp_eff_HW_mix_faction = sum(hw_out_from_swing)/self.totalHWLoad #/2 because the sim goes for two days
            genrate_min = np.array(HRLIST_to_MINLIST(genrate[peakInd:peakInd+24])) \
                / 60 * self.totalHWLoad * temp_eff_HW_mix_faction # to minute

            # Get the new difference in generation and demand
            diffN = genrate_min - hw_out_from_swing
            # Get the rest of the day from the start of the peak
            diffCum = np.cumsum(diffN)

            # Check if additional cases saftey checks have oversized the system.
            if(np.where(diffInd == peakInd)[0][0] >= nRealpeaks):
                if not any(diffCum < 0.):
                    continue

            new_runV_G = -min(diffCum[diffCum<0.])

            if runV_G < new_runV_G:
                runV_G = new_runV_G #Minimum value less than 0 or 0.
                eff_HW_mix_faction = temp_eff_HW_mix_faction

        return runV_G, eff_HW_mix_faction
    
    def simJustSwing(self, N, hw_out, initST=None):
        """
        Inputs
        ------

        initST : float
            Primary Swing tank at start of sim
        """
        swingT = [self.building.supplyT_F] + [0] * (N - 1)
        D_hw = hw_out

        if initST:
            swingT[0] = initST
        
        # Run the "simulation"

        hw_outSwing = [0] * N
        hw_outSwing[0] = D_hw[0]
        srun = [0] * N
        swingheating = False

        for ii in range(1, N):

            hw_outSwing[ii] = mixVolume(D_hw[ii], swingT[ii-1], self.building.incomingT_F, self.building.supplyT_F)
            swingheating, swingT[ii], srun[ii] = self.runOneSwingStep(swingheating, swingT[ii-1], hw_outSwing[ii])

        return [swingT, srun, hw_outSwing]
    
    def runOneSwingStep(self, swingheating, Tcurr, hw_out):
        """
        Runs one step on the swing tank step. Since the swing tank is in series
        with the primary system the temperature needs to be tracked to inform
        inputs for primary step. The driving assumptions hereare that the swing
        tank is well mixed and can be tracked by the average tank temperature
        and that the system loses the recirculation loop losses as a constant
        Watts and thus the actual flow rate and return temperature from the
        loop are irrelevant.

        Parameters
        ----------
        Tcurr : float
            The current temperature at the timestep.
        hw_out : float
            The volume of DHW removed from the swing tank system.
        hw_in : float
            The volume of DHW added to the system.

        Returns
        -------
        Tnew : float
            The new swing tank tempeature the timestep assuming the tank is well mixed.
        did_run : int
            Logic if heated during time step (1) or not (0)

        """
        did_run = 0

        # Take out the recirc losses
        Tnew = Tcurr - self.building.recirc_loss / 60 / rhoCp / self.TMVol_G
        element_dT = self.TMCap_kBTUhr * 1000  / 60 / rhoCp / self.TMVol_G

        # Add in heat for a draw
        if hw_out:
            Tnew += hw_out * (self.storageT_F - Tcurr) / self.TMVol_G

        # Check if the element is heating
        if swingheating:
            Tnew += element_dT #If heating, generate HW and lose HW
            did_run = 1

            # Check if the element should turn off
            if Tnew > self.building.supplyT_F + self.element_deadband_F: # If too hot
                time_over = (Tnew - (self.building.supplyT_F + self.element_deadband_F)) / element_dT # Temp below turn on / rate of element heating gives time above trigger plus deadband
                Tnew -= element_dT * time_over # Make full with miss volume
                did_run = (1-time_over)

                swingheating = False
        else:
            if Tnew <= self.building.supplyT_F: # If the element should turn on
                time_missed = (self.building.supplyT_F - Tnew)/element_dT # Temp below turn on / rate of element heating gives time below tigger
                Tnew += element_dT * time_missed # Start heating

                did_run = time_missed
                swingheating = True # Start heating

        if Tnew < self.building.supplyT_F: # Check for errors
            raise Exception("The swing tank dropped below the supply temperature! The system is undersized")

        return swingheating, Tnew, did_run
    
    def getSizingTable(self, CA=True): #TODO do we need this?
        """
        Returns sizing table for a swing tank

        Returns
        -------
        list
            self.Table_Napts, self.Table
        """
        if CA:
            return list(zip(self.Table_Napts, self.sizingTable_CA))
        return list(zip(self.Table_Napts, self.sizingTable_EMASHRAE))
    
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
        heatCap = self.totalHWLoad * effSwingVolFract / heathours * rhoCp * \
            (self.storageT_F - self.building.incomingT_F) / self.defrostFactor /1000.
        return heatCap
    
    def getTotalVolMax(self, runningVol_G):
        # For a swing tank the storage volume is found at the appropriate temperature in calcRunningVol
        return runningVol_G / (1-self.aquaFract)

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

        swingT = [self.storageT_F] + [0] * (len(G_hw) - 1)
        srun = [0] * (len(G_hw))
        hw_outSwing = [0] * (len(G_hw))
        hw_outSwing[0] = D_hw[0]
        prun = [0] * (len(G_hw))

        if initPV:
            pV[0] = initPV
        if initST:
            swingT[0] = initST
        
        swingheating = False

        # Run the "simulation"
        for ii in range(1, len(G_hw)):
            hw_outSwing[ii] = mixVolume(D_hw[ii], swingT[ii-1], self.building.incomingT_F, self.building.supplyT_F)

            swingheating, swingT[ii], srun[ii] = self.runOneSwingStep(swingheating, swingT[ii-1], hw_outSwing[ii])
            #Get the mixed generation
            mixedGHW = mixVolume(G_hw[ii], self.storageT_F, self.building.incomingT_F, self.building.supplyT_F)
            pheating, pV[ii], prun[ii] = self.runOnePrimaryStep(pheating, V0, Vtrig, pV[ii-1], hw_outSwing[ii], mixedGHW)

        return [roundList(pV, 3),
                roundList(G_hw, 3),
                roundList(D_hw, 3),
                roundList(prun, 3),
                roundList(swingT, 3),
                roundList(srun, 3),
                hw_outSwing]

    def plotStorageLoadSim(self, return_as_div=True):
        hrind_fromback = 24 # Look at the last 24 hours of the simulation not the whole thing
        [V, G_hw, D_hw, run, swingT, srun, _] = self.simulate()

        run = np.array(run[-(60*hrind_fromback):])*60
        G_hw = np.array(G_hw[-(60*hrind_fromback):])*60
        D_hw = np.array(D_hw[-(60*hrind_fromback):])*60
        V = np.array(V[-(60*hrind_fromback):])

        if any(i < 0 for i in V):
            raise Exception("Primary storage ran out of Volume!")

        fig = make_subplots(rows=2, cols=1,
                            specs=[[{"secondary_y": False}],
                                    [{"secondary_y": True}]])


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

        # Do Swing Tank components:
        swingT = np.array(swingT[-(60*hrind_fromback):])
        srun = np.array(srun[-(60*hrind_fromback):]) * self.TMCap_kBTUhr/W_TO_BTUHR #srun is logical so convert to kW

        fig.add_trace(Scatter(x=x_data, y=swingT,
                                name='Swing Tank Temperature',
                                mode='lines', line_shape='hv',
                                opacity=0.8, marker_color='purple',yaxis="y2"),
                        row=2,col=1,
                        secondary_y=False )

        fig.add_trace(Scatter(x=x_data, y=srun,
                                name='Swing Tank Resistance Element',
                                mode='lines', line_shape='hv',
                                opacity=0.8, marker_color='goldenrod'),
                        row=2,col=1,
                        secondary_y=True)

        fig.update_yaxes(title_text="Swing Tank\nTemperature (\N{DEGREE SIGN}F)",
                            showgrid=False, row=2, col=1,
                            secondary_y=False, range=[self.building.supplyT_F-5, self.storageT_F])

        fig.update_yaxes(title_text="Resistance Element\nOutput (kW)",
                            showgrid=False, row=2, col=1,
                            secondary_y=True, range=[0,np.ceil(max(srun)/10)*10])

        if return_as_div:
            plot_div = plot(fig, output_type='div', show_link=False, link_text="",
                        include_plotlyjs = False)
            return plot_div
        return fig