from .Building import Building
import numpy as np
from ecoengine.constants.Constants import *
from .systemConfigUtils import hrToMinList, roundList, hrTo15MinList
from plotly.graph_objs import Figure, Scatter
from plotly.offline import plot
from plotly.subplots import make_subplots
import csv

class SimulationRun:
    """
    Attributes
    ----------
    hwGenRate : list
        The generation of HW with time at the supply temperature
    hwDemand : list
        The hot water demand with time at the supply temperature
    V0 : float
        The storage volume of the primary system at the storage temperature
    pV : list 
        Volume of HW in the tank with time at the storage temperature. Initialized to array of 0s with pV[0] set to V0
    building : Building 
        the Building object the simulation will be run for
    minuteIntervals : int
        the minutes per time interval for the simulation. Only 1, 15, and 60 are accepted
    doLoadshift : boolean
        set to True if doing loadshift
    LS_sched : list
        list length 24 corresponding to hours of the day filled with 'N' for normal, 'L' for load up, and 'S' for shed
    """
    def __init__(self, hwGenRate, hwDemand, V0, pV, building : Building, loadShiftSchedule, minuteIntervals = 1, doLoadshift = False, LS_sched = []):
        if minuteIntervals != 1 and minuteIntervals != 15 and minuteIntervals != 60:
            raise Exception("Simulations can only take place over 1, 15, or 60 minute intervals")

        self.V0 = V0 
        self.hwGenRate = hwGenRate # Can be initialized to None if hwGen is found dynamically
        self.hwDemand = hwDemand
        self.pV = pV
        self.pheating = False # set to false. Simulation starts with primary heating off
        self.pGen = [0] * len(hwDemand) # The generation of HW with time at the storage temperature
        self.pRun = [0] * len(hwDemand) # amount of time in interval primary tank is heating
        self.building = building
        self.minuteIntervals = minuteIntervals
        self.doLoadShift = doLoadshift
        self.loadShiftSchedule = loadShiftSchedule # TODO get rid of this if you can
        self.monthlyCityWaterT_F = None
        self.oat = [] # oat by hour
        self.cap_out = [] # output capacity at every time interval
        self.cap_in = [] # input capacity at every time interval
        self.kGCO2 = [] # the kG CO2 released at every time interval
        self.hwGen = []
        self.hwGean_at_storage_t = []
        self.recircLoss = []
        self.LS_sched = LS_sched

    def initializeTMValue(self, initST, storageT_F, TMCap_kBTUhr, swingOut = True):
        """
        Initializes temperature maintenance values

        Parameters
        ----------
        initST : float
            temperature maintenance tank temperature at start of the simulation.
        storageT_F : float
            storage temperature setpoint for temperature maintenance system
        TMCap_kBTUhr : float
            temperature maintenance heating capacity in kBTUhr
        swingOut : boolean
            set to True for swing tank systems so that DHW leaving temperature maintenance system is recorded
        """
        self.tmT_F = [0] * (len(self.hwDemand) - 1) + [storageT_F]
        self.tmRun = [0] * (len(self.hwDemand))
        if swingOut:
            self.hw_outSwing = [0] * (len(self.hwDemand))
        # self.hw_outSwing[0] = self.hwDemand[0]
        if initST:
            self.tmT_F[-1] = initST
        self.tmheating = False

        self.tm_cap_out = [] # output tm capacity at every time interval
        self.tm_cap_in = [] # input tm capacity at every time interval

        # next two items are for the resulting plotly plot
        self.storageT_F = storageT_F
        self.TMCap_kBTUhr = TMCap_kBTUhr

    def getLoadShiftMode(self, i):
        """
        returns the load shifting setting at interval i of the simulation

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        loadshiftMode : string
            The load shift mode of the system at interval i. Returns 'N', 'L', or 'S' for normal, load, or shed mode respectively  
        """
        return self.LS_sched[int((i//(60/self.minuteIntervals))%24)] # returns 'N', 'L', or 'S' for normal, load, or shed mode respectively

    def getIncomingWaterT(self, i):
        """
        returns incoming water temperature (F) at interval i of the simulation

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        waterT_F : float
            The incoming water temperature (F) at interval i of the simulation 
        """
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

        Returns
        -------
        waterT_F : float
            The average incoming water temperature (F) of the simulation 
        """
        if self.monthlyCityWaterT_F is None:
            return self.building.incomingT_F # default city water temp
        else:
            return ((self.monthlyCityWaterT_F[0]*31) + (self.monthlyCityWaterT_F[1]*28) + (self.monthlyCityWaterT_F[2]*31) + (self.monthlyCityWaterT_F[3]*30) \
                + (self.monthlyCityWaterT_F[4]*31) + (self.monthlyCityWaterT_F[5]*30) + (self.monthlyCityWaterT_F[6]*31) + (self.monthlyCityWaterT_F[7]*31) \
                + (self.monthlyCityWaterT_F[8]*30) + (self.monthlyCityWaterT_F[9]*31) + (self.monthlyCityWaterT_F[10]*30) + (self.monthlyCityWaterT_F[11]*31)) / 365
    
    def setMonthlyCityWaterT_F(self, monthlyCityWaterT_F):
        """
        sets monthly incoming water temperature (F) for each month of an annual simulation

        Parameters
        ----------
        monthlyCityWaterT_F : List
            List of floats representing the incoming water temperature at each month. must be length 12.

        Raises
        ----------
        Exception: Error if monthlyCityWaterT_F is not length 12 or contains wrong data type

        """
        if len(monthlyCityWaterT_F) != 12:
            raise Exception("Monthly city water temperature data must have 12 entries (one for every month).")
        for i in range(12):
            if not isinstance(monthlyCityWaterT_F[i], float):
                raise Exception(str(monthlyCityWaterT_F[i]) + " is an invalid city water tempurature for month "+str(i+1)+".")
        self.monthlyCityWaterT_F = monthlyCityWaterT_F

    def generateRecircLoss(self, i : int):
        """
        Returns recirculation loss from primary system at supply temp at interval i in gallons

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        recirculationLoss : float
            the recirculation loss from primary system at supply temp at interval i in gallons

        Raises
        ----------
        Exception: Error if attempt is made to find recirculation loss outside of scope of simulation
        """
        if i < len(self.recircLoss):
            return self.recircLoss[i]
        elif i > len(self.hwDemand):
            raise Exception(f"Recirculation data is only available for one year. Attempted to generate information for interval {i}, however there are only {len(self.hwDemand)} {self.minuteIntervals}-minute intervals in a year.")
        
        recircLossAtTime = (self.building.recirc_loss / (rhoCp * (self.building.supplyT_F - self.getIncomingWaterT(i)))) / (60/self.minuteIntervals)
        if i == len(self.recircLoss):
            self.recircLoss.append(recircLossAtTime)
        return recircLossAtTime
    
    def getRecircLoss(self, i : int = None):
        """
        Returns list of recirculation loss from primary system at supply temp in gallons at every interval in simulation

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        recirculationLoss : float
            the recirculation loss from primary system at supply temp at interval i in gallons or the entire list of recirculation losses at every interval if i is undefined
        """
        if len(self.recircLoss) == 0:
            self.recircLoss = [0]*len(self.hwDemand)
        
        if i is None:
            return self.recircLoss
        return self.recircLoss[i]
    
    def addOat(self, oat_value):
        """
        adds outdoor air temperature (F) to the simulation at timestep

        Parameters
        ----------
        oat_value : float
            float representing the outdoor air temperature (F) current timestep.

        Raises
        ----------
        Exception: Error if oat_value contains the wrong data type
        """
        if not (isinstance(oat_value, float) or isinstance(oat_value, int)):
            raise Exception(str(oat_value) + " is an invalid outdoor air tempurature.")
        self.oat.append(oat_value)
    
    def addCap(self, out_cap_value, in_cap_value):
        """
        adds calculated capacity values to the simulation at timestep

        Parameters
        ----------
        out_cap_value : float
            float representing the primary system's output capacity in kW during current timestep.
        in_cap_value : float
            float representing the primary system's input capacity in kW during current timestep.

        Raises
        ----------
        Exception: Error if out_cap_value or in_cap_value contains the wrong data type
        """
        if not (isinstance(out_cap_value, float) or isinstance(out_cap_value, int)):
            raise Exception(str(out_cap_value) + " is an invalid system capacity.")
        if not (isinstance(in_cap_value, float) or isinstance(in_cap_value, int)):
            raise Exception(str(in_cap_value) + " is an invalid system capacity.")
        
        self.cap_out.append(out_cap_value)
        self.cap_in.append(in_cap_value)

    def addTMCap(self, out_tm_cap_value, in_tm_cap_value):
        """
        adds calculated capacity values for temperature maintenance sysyem to the simulation at timestep

        Parameters
        ----------
        out_tm_cap_value : float
            float representing the temperature maintenance system's output capacity in kW during current timestep.
        in_tm_cap_value : float
            float representing the temperature maintenance system's input capacity in kW during current timestep.

        Raises
        ----------
        Exception: Error if out_tm_cap_value or in_tm_cap_value contains the wrong data type
        """
        if not (isinstance(out_tm_cap_value, float) or isinstance(out_tm_cap_value, int)):
            raise Exception(str(out_tm_cap_value) + " is an invalid system capacity.")
        if not (isinstance(in_tm_cap_value, float) or isinstance(in_tm_cap_value, int)):
            raise Exception(str(in_tm_cap_value) + " is an invalid system capacity.")
        
        self.tm_cap_out.append(out_tm_cap_value)
        self.tm_cap_in.append(in_tm_cap_value)

    def getCapOut(self, i : int = None):
        """
        Returns a list of the output capacity in kW for the primary system at every timestep
        or, if i is defined, returns index i of that list

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        capacityOut_kW : float
            the output capacity in kW for the primary system at interval i in gallons or the entire list of output capacity in kW at every interval if i is undefined
        """
        if i is None:
            return self.cap_out
        return self.cap_out[i]
    
    def getCapIn(self, i : int = None):
        """
        Returns a list of the input capacity in kW for the primary system at every timestep
        or, if i is defined, returns index i of that list

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        capacityIn_kW : float
            the input capacity in kW for the primary system at interval i in gallons or the entire list of input capacity in kW at every interval if i is undefined
        """
        if i is None:
            return self.cap_in
        return self.cap_in[i]
    
    def getTMCapOut(self, i : int = None):
        """
        Returns a list of the output capacity in kW for the temperature maintenance system at every timestep
        or, if i is defined, returns index i of that list

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        capacityOut_kW : float
            the output capacity in kW for the temperature maintenance system at interval i in gallons or the entire list of output capacity in kW at every interval if i is undefined
        """
        if hasattr(self, 'tm_cap_out'):
            if i is None:
                return self.tm_cap_out
            return self.tm_cap_out[i]
        elif i is None:
            return []
        return 0
    
    def getTMCapIn(self, i : int = None):
        """
        Returns a list of the input capacity in kW for the temperature maintenance system at every timestep
        or, if i is defined, returns index i of that list

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        capacityIn_kW : float
            the input capacity in kW for the temperature maintenance system at interval i in gallons or the entire list of input capacity in kW at every interval if i is undefined
        """
        if hasattr(self, 'tm_cap_in'):
            if i is None:
                return self.tm_cap_in
            return self.tm_cap_in[i]
        elif i is None:
            return []
        return 0

    def addKGCO2(self, kGCO2_value):
        """
        add a calculated kGCO2 emission value to the simulation

        Parameters
        ----------
        kGCO2_value : float
            float representing the amount of CO2 emitted in kg during the current time step for later use in kgCO2 calculation.

        Raises
        ----------
        Exception: Error if kGCO2_value contains wrong data type
        """
        if not (isinstance(kGCO2_value, float) or isinstance(kGCO2_value, int)):
            raise Exception(str(kGCO2_value) + " is an invalid value for number of kG of CO2.")
        self.kGCO2.append(kGCO2_value)

    def addHWGen(self, hwGen):
        """
        add a calculated hot water generation value to the simulation

        Parameters
        ----------
        hwGen : float
            float representing the amount of hot water generated at supply temperature in gallons during current timestep.

        Raises
        ----------
        Exception: Error if hwGen contains wrong data type
        """
        if not (isinstance(hwGen, float) or isinstance(hwGen, int)):
            raise Exception(str(hwGen) + " is an invalid hot water generation value.")
        self.hwGen.append(hwGen)
        self.hwGenRate = hwGen

    def getPrimaryVolume(self, i = None):
        """
        Returns a list from the simulation of the volume of the primary tank by timestep
        or, if i is defined, returns index i of that list

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        volume : float
            the primary tank volume in gallons at interval i or the entire list of primary tank volume at every interval if i is undefined
        """
        if i is None:
            return roundList(self.pV, 3)
        return self.pV[i]

    def getHWDemand(self, i = None):
        """
        Returns a list from the simulation of the hot water demand by timestep
        or, if i is defined, returns index i of that list

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        volume : float
            the hot water demand in gallons at interval i or the entire list of hot water demand at every interval if i is undefined
        """
        if i is None:
            return roundList(self.hwDemand, 3)
        return self.hwDemand[i]
    
    def getHWGeneration(self, i = None):
        """
        Returns a list from the simulation of the theoretical hot water generation of the primary tank at supply temperature by timestep
        or, if i is defined, returns index i of that list

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        volume : float
            the theoretical hot water generation of the primary tank at supply temperature in gallons at interval i or the entire list of theoretical hot water generation at every interval if i is undefined
        """
        if len(self.hwGen) == 0:
            self.hwGen = self.hwGenRate * self.loadShiftSchedule
        if i is None:
            return roundList(self.hwGen, 3)
        return self.hwGen[i]
    
    def getPrimaryGeneration(self, i = None):
        """
        Returns a list from the simulation of the actual hot water generation of the primary tank by timestep

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        volume : float
            the actual hot water generation at supply temperature in gallons at interval i or the entire list of actual hot water generation at every interval if i is undefined
        """
        if i is None:
            return roundList(self.pGen,3)
        return self.pGen[i]
    
    def getPrimaryRun(self, i = None):
        """
        Returns a list from the simulation of the amount of time the primary tank is running in minutes per timestep
        or, if i is defined, returns index i of that list

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        minutes : float
            the amount of time the primary tank is running in minutes at interval i or the entire list of 
            amount of time the primary tank is running in minutes at every interval if i is undefined
        """
        if i is None:
            return self.pRun
        return self.pRun[i]
    
    def getTMTemp(self):
        """
        Returns a list from the simulation of the temperature maintenance tank temperature in (F) by timestep

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        temperature : float
            the temperature maintenance tank temperature in (F) at interval i or the entire list of 
            temperature maintenance tank temperature in (F) at every interval if i is undefined
        """
        if hasattr(self, 'tmT_F'):
            return roundList(self.tmT_F, 3)
        else:
            return []
        
    def getTMRun(self, i : int = None):
        """
        Returns a list from the simulation of the amount of time the temperature maintenance tank is running in minutes per timestep
        or, if i is defined, returns index i of that list

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        minutes : float
            the amount of time the temperature maintenance tank is running in minutes at interval i or the entire list of 
            amount of time the temperature maintenance tank is running in minutes at every interval if i is undefined
        """
        if hasattr(self, 'tmRun'):
            if i is None:
                return self.tmRun
            return self.tmRun[i]
        elif i is None:
            return []
        return 0
        
    def gethwOutSwing(self, i : int = None):
        """
        Returns a list from the simulation of the amount of water coming out of the swing tank at tempurature in gallons by timestep
        or, if i is defined, returns index i of that list

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        volume : float
            the amount of water coming out of the swing tank at tempurature in gallons at interval i or the entire list of 
            amount of water coming out of the swing tank at tempurature in gallons at every interval if i is undefined
        """
        if hasattr(self, 'hw_outSwing'):
            if i is None:
                return self.hw_outSwing
            return self.hw_outSwing[i]
        elif i is None:
            return []
        return 0

    def getOAT(self):
        """
        Returns a list from the simulation of the Outdoor Air Temperature in (F) by timestep

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        oat : float
            the Outdoor Air Temperature in (F) at interval i or the entire list of 
            Outdoor Air Temperature in (F) at every interval if i is undefined
        """
        if self.minuteIntervals == 15:
            return hrTo15MinList(self.oat)
        elif self.minuteIntervals == 1:
            return hrToMinList(self.oat)
        else:
            return self.oat
    
    def getkGCO2(self, i : int = None):
        """
        Returns a list from the simulation of the get output of CO2 by timestep in kilograms
        or, if i is defined, returns index i of that list

        Parameters
        ----------
        i : int
            interval of the simulation

        Returns
        -------
        CO2 : float
            the output of CO2 in kilograms at interval i or the entire list of 
            output of CO2 in kilograms at every interval if i is undefined
        """
        if i is None:
            return self.kGCO2
        return self.kGCO2[i]
    
    def getkGCO2Sum(self):
        """
        Returns the sum from the simulation of the output of CO2 in kilograms

        Returns
        -------
        CO2 : float
            the sum from the simulation of the output of CO2 in kilograms
        """
        return sum(self.kGCO2)
    
    def getAnnualCOP(self, boundryMethod = False):
        """
        Returns annual COP for the simulation

        Parameters
        ----------
        boundryMethod : boolean
            set to True to use boundry method to compute COP

        Returns
        -------
        COP : float
            the COP value for the system over the annual simulation
        """
        heatInputTotal = 0
        heatOutputTotal = 0
        if boundryMethod:
            recirc_const = self.building.recirc_loss / (60/self.minuteIntervals)
            for i in range(len(self.hwDemand)):
                heatOutputTotal += (rhoCp*self.hwDemand[i]*(self.building.supplyT_F - self.getIncomingWaterT(i))) + (recirc_const)
                heatInputTotal += ((self.getCapIn(i)*self.getPrimaryRun(i)/60) + (self.getTMCapIn(i)*self.getTMRun(i)/60))*KWH_TO_BTU
        else:
            for i in range(len(self.hwDemand)):
                heatOutputTotal += (self.getCapOut(i)*self.getPrimaryRun(i)/60) + (self.getTMCapOut(i)*self.getTMRun(i)/60)
                heatInputTotal += (self.getCapIn(i)*self.getPrimaryRun(i)/60) + (self.getTMCapIn(i)*self.getTMRun(i)/60)
        return heatOutputTotal/heatInputTotal


    def returnSimResult(self, kWhCalc = False):
        """
        ***LEGACY FUNCTION*** to be depricated.
        """
        retList = [self.getPrimaryVolume(),
            self.getHWGeneration(),
            self.getHWDemand(),
            self.getPrimaryGeneration()]
        
        if hasattr(self, 'tmT_F'):
            retList.append(roundList(self.tmT_F, 3))
        if hasattr(self, 'tmRun'):
            retList.append(roundList(self.tmRun, 3))
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
            retList.append(self.cap_out)
            retList.append(self.kGCO2)
            retList.append(sum(self.kGCO2))
            retList.append(self.getAvgIncomingWaterT())               
        return retList
    
    def plotStorageLoadSim(self, return_as_div=True):
        """
        Returns a plot of the of the simulation for the minimum sized primary
        system as a div or plotly figure. Can plot the minute level simulation

        Parameters
        ----------
        return_as_div : boolean
            A logical on the output, as a div (true) or as a figure (false)

        Returns
        -------
        plot : plotly.Figure -OR- <div> string
            The storage load simulation graph. Return type depends on value of return_as_div parameter.
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
        if hasattr(self, 'tmT_F') and hasattr(self, 'tmRun') and hasattr(self, 'TMCap_kBTUhr') and hasattr(self, 'storageT_F'):
            fig = make_subplots(rows=2, cols=1,
                                specs=[[{"secondary_y": False}],
                                        [{"secondary_y": True}]])


        # Do primary components
        x_data = list(range(len(V)))

        if self.doLoadShift:
            ls_off = [int(not x)* max(V)*2 for x in loadShiftSchedule]
            fig.add_trace(Scatter(x=x_data, y=ls_off, name='Load Shift Shed Period',
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
        if hasattr(self, 'tmT_F') and hasattr(self, 'tmRun') and hasattr(self, 'TMCap_kBTUhr') and hasattr(self, 'storageT_F') and hasattr(self, 'hw_outSwing'):

            # Do Swing Tank components:
            tmT_F = np.array(roundList(self.tmT_F,3)[-(60*hrind_fromback):])
            tmRun = np.array(roundList(self.tmRun,3)[-(60*hrind_fromback):]) * self.TMCap_kBTUhr/W_TO_BTUHR #tmRun is logical so convert to kW

            fig.add_trace(Scatter(x=x_data, y=tmT_F,
                                    name='Swing Tank Temperature',
                                    mode='lines', line_shape='hv',
                                    opacity=0.8, marker_color='purple',yaxis="y2"),
                            row=2,col=1,
                            secondary_y=False )

            fig.add_trace(Scatter(x=x_data, y=tmRun,
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
                                secondary_y=True, range=[0,np.ceil(max(tmRun)/10)*10])

        if return_as_div:
            plot_div = plot(fig, output_type='div', show_link=False, link_text="",
                        include_plotlyjs = False)
            return plot_div
        return fig 
    
    def writeCSV(self, file_path):
        """
        writes all simulation data to a formated csv

        Parameters
        ----------
        file_path : string
            the file path for the output csv file
        """
        
        hours = [(i // (60/self.minuteIntervals)) + 1 for i in range(len(self.getPrimaryVolume()))]
        column_names = ['Hour','Primary Volume (Gallons Storage Temp)', 'Primary Generation (Gallons Storage Temp)', 'HW Demand (Gallons Supply Temp)', 'Recirculation Loss to Primary System (Gallons Supply Temp)','Theoretical HW Generation (Gallons Supply Temp)', 'Primary Run Time (Min)', 'OAT (F)', 'Input Capacity (kW)', 'Output Capacity (kW)']
        columns = [
            hours,
            self.getPrimaryVolume(),
            self.getPrimaryGeneration(),
            self.getHWDemand(),
            self.getRecircLoss(),
            self.getHWGeneration(),
            self.getPrimaryRun(),
            self.getOAT(),
            self.getCapIn(),
            self.getCapOut()
        ]

        if hasattr(self, 'tmRun'):
            column_names.append('TM Temp (F)')
            columns.append(self.getTMTemp())
            column_names.append('TM Runtime (Min)')
            columns.append(self.getTMRun())
            column_names.append('TM Input Capacity (kW)')
            columns.append(self.getTMCapIn())
            column_names.append('TM Output Capacity (kW)')
            columns.append(self.getTMCapOut())
            if hasattr(self, 'hw_outSwing'):
                column_names.append('Water Leaving SwingTank (Gallons at TM Temp)')
                columns.append(self.gethwOutSwing())
        
        column_names.append('C02 Emissions (kG)')
        columns.append(self.getkGCO2())

        transposed_result = zip(*columns)

        # Write the transposed_result to a CSV file
        with open(file_path, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            
            # Write the column headers
            csvwriter.writerow(column_names)
            # Write the data rows
            csvwriter.writerows(transposed_result)

        print("CSV file created successfully.")