from .Building import Building
import numpy as np
from ecoengine.constants.Constants import *
from .systemConfigUtils import hrToMinList, roundList
from plotly.graph_objs import Figure, Scatter
from plotly.offline import plot
from plotly.subplots import make_subplots

class SimulationRun:
    def __init__(self, hwGenRate, hwDemand, V0, Vtrig, pV, pGen, pheating, mixedStorT_F, building : Building, loadShiftSchedule, doLoadshift = False):
        """
        Initializes arrays needed for 3-day simulation

        Parameters
        ----------
        hwGenRate : list
            The generation of HW with time at the supply temperature
        hwDemand : list
            The hot water demand with time at the tsupply temperature
        V0 : float
            The storage volume of the primary system at the storage temperature
        Vtrig : list
            The remaining volume of the primary storage volume when heating is
            triggered, note this equals V0*(1 - aquaFract[i]) 
        pV : list 
            Volume of HW in the tank with time at the storage temperature. Initialized to array of 0s with pV[0] set to V0
        pheating : boolean 
            set to false. Simulation starts with a full tank so primary heating starts off
        pGen : list 
            The generation of HW with time at the storage temperature
        """
        self.V0 = V0 
        self.hwGenRate = hwGenRate
        self.hwDemand = hwDemand
        self.Vtrig = Vtrig
        self.pV = pV
        self.pheating = pheating
        self.pGen = pGen
        self.mixedStorT_F = mixedStorT_F
        self.building = building
        self.doLoadShift = doLoadshift
        self.loadShiftSchedule = loadShiftSchedule

    def getIncomingWaterT(self, i):
        return self.building.incomingT_F

    def returnSimResult(self):
        retList = [roundList(self.pV, 3),
            roundList(self.hwGenRate * self.loadShiftSchedule, 3),
            roundList(self.hwDemand, 3),
            roundList(self.pGen, 3)]
        
        if hasattr(self, 'swingT_F'):
            retList.append(roundList(self.swingT_F, 3))
        if hasattr(self, 'sRun'):
            retList.append(roundList(self.sRun, 3))
        if hasattr(self, 'hw_outSwing'):
            retList.append(self.hw_outSwing)

        return retList
    
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
        hrind_fromback = 24 # Look at the last 24 hours of the simulation not the whole thing

        run = np.array(roundList(self.pGen,3)[-(60*hrind_fromback):])*60
        loadShiftSchedule = np.array(self.loadShiftSchedule[-(60*hrind_fromback):])*60
        hwDemand = np.array(roundList(self.hwDemand,3)[-(60*hrind_fromback):])*60
        V = np.array(roundList(self.pV,3)[-(60*hrind_fromback):])

        if any(i < 0 for i in V):
            raise Exception("Primary storage ran out of Volume!")

        fig = Figure()

        #swing tank
        if hasattr(self, 'swingT_F') and hasattr(self, 'sRun') and hasattr(self, 'TMCap_kBTUhr') and hasattr(self, 'storageT_F'):
            fig = make_subplots(rows=2, cols=1,
                                specs=[[{"secondary_y": False}],
                                        [{"secondary_y": True}]])


        # Do primary components
        x_data = list(range(len(V)))

        if self.doLoadShift:
            ls_off = [int(not x)* max(V)*2 for x in loadShiftSchedule]
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
        fig.add_trace(Scatter(x=x_data, y=hwDemand, name='Hot Water Demand at Supply Temperature',
                              mode='lines', line_shape='hv',
                              opacity=0.8, marker_color='blue'))
        fig.update_yaxes(range=[0, np.ceil(max(np.append(V,hwDemand))/100)*100])
        
        fig.update_layout(title="Hot Water Simulation",
                          xaxis_title= "Minute of Day",
                          yaxis_title="Gallons or\nGallons per Hour",
                          width=900,
                          height=700)
        
        # Swing tank
        if hasattr(self, 'swingT_F') and hasattr(self, 'sRun') and hasattr(self, 'TMCap_kBTUhr') and hasattr(self, 'storageT_F'):

            # Do Swing Tank components:
            swingT_F = np.array(roundList(self.swingT_F,3)[-(60*hrind_fromback):])
            sRun = np.array(roundList(self.sRun,3)[-(60*hrind_fromback):]) * self.TMCap_kBTUhr/W_TO_BTUHR #sRun is logical so convert to kW

            fig.add_trace(Scatter(x=x_data, y=swingT_F,
                                    name='Swing Tank Temperature',
                                    mode='lines', line_shape='hv',
                                    opacity=0.8, marker_color='purple',yaxis="y2"),
                            row=2,col=1,
                            secondary_y=False )

            fig.add_trace(Scatter(x=x_data, y=sRun,
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
                                secondary_y=True, range=[0,np.ceil(max(sRun)/10)*10])

        if return_as_div:
            plot_div = plot(fig, output_type='div', show_link=False, link_text="",
                        include_plotlyjs = False)
            return plot_div
        return fig 