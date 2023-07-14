from .Building import Building
import numpy as np
from ecoengine.constants.Constants import *
from .systemConfigUtils import hrToMinList, roundList, hrTo15MinList
from plotly.graph_objs import Figure, Scatter
from plotly.offline import plot
from plotly.subplots import make_subplots
import os
import csv
 # TODO add initial values to csv output?
 #TODO csv output?
class SimulationRun:
    def __init__(self, hwGenRate, hwDemand, V0, Vtrig, pV, pGen, pRun, pheating, mixedStorT_F, building : Building, loadShiftSchedule, minuteIntervals = 1, doLoadshift = False):
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
        self.hwGenRate = hwGenRate # Can be initialized to None if hwGen is found dynamically
        self.hwDemand = hwDemand
        self.Vtrig = Vtrig
        self.pV = pV
        self.pheating = pheating
        self.pGen = pGen
        self.pRun = pRun # amount of time in interval primary tank is heating
        self.mixedStorT_F = mixedStorT_F
        self.building = building
        self.minuteIntervals = minuteIntervals
        self.doLoadShift = doLoadshift
        self.loadShiftSchedule = loadShiftSchedule
        self.monthlyCityWaterT_F = None
        self.oat = [] # oat by hour
        self.cap = [] # capacity at every time interval
        self.kGperkWh = [] # the kG CO2 per kWh at every time interval
        self.hwGen = []

    def initializeSwingValue(self, initST, storageT_F, TMCap_kBTUhr):
        self.swingT_F = [0] * (len(self.hwDemand) - 1) + [self.mixedStorT_F]
        self.sRun = [0] * (len(self.hwDemand))
        self.hw_outSwing = [0] * (len(self.hwDemand))
        self.hw_outSwing[0] = self.hwDemand[0]
        if initST:
            self.swingT_F[-1] = initST
        self.swingheating = False

        # next two items are for the resulting plotly plot
        self.storageT_F = storageT_F
        self.TMCap_kBTUhr = TMCap_kBTUhr

    def getIncomingWaterT(self, i):
        if self.monthlyCityWaterT_F is None:
            return self.building.incomingT_F # default city water temp
        else:
            dayOfYear = (i // (60/self.minuteIntervals)) // 24
            if dayOfYear < 31:
                # jan
                return self.monthlyCityWaterT_F[0]
            elif dayOfYear < 59:
                # feb
                return self.monthlyCityWaterT_F[1]
            elif dayOfYear < 90:
                # mar
                return self.monthlyCityWaterT_F[2]
            elif dayOfYear < 120:
                # apr
                return self.monthlyCityWaterT_F[3]
            elif dayOfYear < 151:
                # may
                return self.monthlyCityWaterT_F[4]
            elif dayOfYear < 181:
                # jun
                return self.monthlyCityWaterT_F[5]
            elif dayOfYear < 212:
                # jul
                return self.monthlyCityWaterT_F[6]
            elif dayOfYear < 243:
                # aug
                return self.monthlyCityWaterT_F[7]
            elif dayOfYear < 273:
                # sep
                return self.monthlyCityWaterT_F[8]
            elif dayOfYear < 304:
                # oct
                return self.monthlyCityWaterT_F[9]
            elif dayOfYear < 334:
                # nov
                return self.monthlyCityWaterT_F[10]
            elif dayOfYear < 365:
                # dec
                return self.monthlyCityWaterT_F[11]
            else:
                raise Exception("Cold water temperature data not available past one year.")
            
    def getAvgIncomingWaterT(self):
        """
        Returns the average incoming water temperature for the year in fahrenheit as a float
        """
        if self.monthlyCityWaterT_F is None:
            return self.building.incomingT_F # default city water temp
        else:
            return ((self.monthlyCityWaterT_F[0]*31) + (self.monthlyCityWaterT_F[1]*28) + (self.monthlyCityWaterT_F[2]*31) + (self.monthlyCityWaterT_F[3]*30) \
                + (self.monthlyCityWaterT_F[4]*31) + (self.monthlyCityWaterT_F[5]*30) + (self.monthlyCityWaterT_F[6]*31) + (self.monthlyCityWaterT_F[7]*31) \
                + (self.monthlyCityWaterT_F[8]*30) + (self.monthlyCityWaterT_F[9]*31) + (self.monthlyCityWaterT_F[10]*30) + (self.monthlyCityWaterT_F[11]*31)) / 365
    
    def setMonthlyCityWaterT_F(self, monthlyCityWaterT_F):
        if len(monthlyCityWaterT_F) != 12:
            raise Exception("Monthly city water temperature data must have 12 entries (one for every month).")
        for i in range(12):
            if not isinstance(monthlyCityWaterT_F[i], float):
                raise Exception(str(monthlyCityWaterT_F[i]) + " is an invalid city water tempurature for month "+str(i+1)+".")
        self.monthlyCityWaterT_F = monthlyCityWaterT_F

    def addOat(self, oat_value):
        if not (isinstance(oat_value, float) or isinstance(oat_value, int)):
            raise Exception(str(oat_value) + " is an invalid outdoor air tempurature.")
        self.oat.append(oat_value)
    
    def addCap(self, cap_value):
        if not (isinstance(cap_value, float) or isinstance(cap_value, int)):
            raise Exception(str(cap_value) + " is an invalid system capacity.")
        self.cap.append(cap_value)

    def addKGperkWh(self, kGperkWh_value):
        if not (isinstance(kGperkWh_value, float) or isinstance(kGperkWh_value, int)):
            raise Exception(str(kGperkWh_value) + " is an invalid system kGperkWh value.")
        self.kGperkWh.append(kGperkWh_value)

    def addHWGen(self, hwGen):
        if not (isinstance(hwGen, float) or isinstance(hwGen, int)):
            raise Exception(str(hwGen) + " is an invalid hot water generation value.")
        self.hwGen.append(hwGen)
        self.hwGenRate = hwGen

    def getPrimaryVolume(self):
        """
        Returns a list from the simulation of the volume of the primary tank by timestep
        """
        return roundList(self.pV, 3)

    def getHWDemand(self):
        """
        Returns a list from the simulation of the hot water demand by timestep
        """
        return roundList(self.hwDemand, 3)
    
    def getHWGeneration(self):
        """
        Returns a list from the simulation of the theoretical hot water generation of the primary tank by timestep
        """
        if len(self.hwGen) == 0:
            self.hwGen = self.hwGenRate * self.loadShiftSchedule
        return roundList(self.hwGen, 3)
    
    def getPrimaryGeneration(self):
        """
        Returns a list from the simulation of the actual hot water generation of the primary tank by timestep
        """
        return roundList(self.pGen, 3)
    
    def getPrimaryRun(self):
        """
        Returns a list from the simulation of the amount of time the primary tank is running in minutes per timestep
        """
        return self.pRun
    
    def getSwingTemp(self):
        """
        Returns a list from the simulation of the swing tank temperature in (F) by timestep
        """
        if hasattr(self, 'swingT_F'):
            return roundList(self.swingT_F, 3)
        else:
            return []
        
    def getSwingRun(self):
        """
        Returns a list from the simulation of the amount of time the swing tank is running in minutes per timestep
        """
        if hasattr(self, 'sRun'):
            return roundList(self.sRun, 3)
        else:
            return []
        
    def getSwingTemp(self):
        """
        Returns a list from the simulation of the amount of water coming out of the swing tank in gallons by timestep
        """
        if hasattr(self, 'hw_outSwing'):
            return self.hw_outSwing
        else:
            return []
        
    def getOAT(self):
        """
        Returns a list from the simulation of the Outdoor Air Temperature in (F) by timestep
        """
        if len(self.oat) == 8760:
            if self.minuteIntervals == 15:
                return hrTo15MinList(self.oat)
            elif self.minuteIntervals == 1:
                return hrToMinList(self.oat)
            else:
                return self.oat
        else:
            return []
        
    def getPrimaryOutputCapacity(self):
        """
        Returns a list from the simulation of the get Primary Output Capacity in kW by timestep
        """
        return self.cap
    
    def getkGCO2perkWh(self):
        """
        Returns a list from the simulation of the get output of kG CO2 per kWh by timestep
        """
        return self.kGperkWh
    
    def getkGCO2perkWhSum(self):
        """
        Returns the sum from the simulation of the get output of kG CO2 per kWh by timestep
        """
        return sum(self.kGperkWh)

    def returnSimResult(self, kWhCalc = False):
        if len(self.hwGen) == 0:
            self.hwGen = self.hwGenRate * self.loadShiftSchedule
        retList = [roundList(self.pV, 3),
            roundList(self.hwGen, 3),
            roundList(self.hwDemand, 3),
            roundList(self.pGen, 3)]
        
        if hasattr(self, 'swingT_F'):
            retList.append(roundList(self.swingT_F, 3))
        if hasattr(self, 'sRun'):
            retList.append(roundList(self.sRun, 3))
        if hasattr(self, 'hw_outSwing'):
            retList.append(self.hw_outSwing)

        if kWhCalc and len(self.oat) == 8760: #Year long calc
            retList.append(self.pRun)
            if self.minuteIntervals == 15:
                retList.append(hrTo15MinList(self.oat))
            elif self.minuteIntervals == 1:
                retList.append(hrToMinList(self.oat))
            else:
                retList.append(self.oat)
            retList.append(self.cap)
            retList.append(self.kGperkWh)
            retList.append(sum(self.kGperkWh))
            retList.append(self.getAvgIncomingWaterT())               
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
        # TODO make this function work for not 1 minute intervals
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