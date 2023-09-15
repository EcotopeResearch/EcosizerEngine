from .BuildingCreator import *
from .SystemCreator import *
from .Simulator import simulate
from ecoengine.objects.SimulationRun import *
from ecoengine.objects.systemConfigUtils import *
import copy
import json
from plotly.graph_objs import Figure, Scatter
from plotly.offline import plot
from numpy import around, flipud

print("EcosizerEngine Copyright (C) 2023  Ecotope Inc.")
print("This program comes with ABSOLUTELY NO WARRANTY. This is free software, and you are welcome to redistribute under certain conditions; details check GNU AFFERO GENERAL PUBLIC LICENSE_08102020.docx.")

class EcosizerEngine:
    """
    Initializes and sizes the HPWH system for a building based on the given parameters.

    Attributes
    ----------
    incomingT_F : float 
        The incoming city water temperature on the design day. [°F]
    magnitude_stat : int or list
        a number that will be used to assess the magnitude of the building based on the building type
    supplyT_F : float
        The hot water supply temperature.[°F]
    storageT_F : float 
        The hot water storage temperature. [°F]
    percentUseable : float
        The fraction of the storage volume that can be filled with hot water.
    aquaFract: float
        The fraction of the total height of the primary hot water tanks at which the Aquastat is located.
    schematic : String
        Indicates schematic type. Valid values are 'swingtank', 'paralleltank', and 'primary'
    building_type : string or list
        a string indicating the type of building we are sizing for (e.g. "multi_family", "office_building", etc.)
    loadShape : ndarray
        defaults to design load shape for building type.
    avgLoadShape : ndarray
        defaults to average load shape for building type.
    loadShiftSchedule : array_like
        List or array of 0's, 1's used for load shifting, 0 indicates system is off. 
    loadUpHours : float
        Number of hours spent loading up for first shed.
    aquaFractLoadUp : float
        The fraction of the total height of the primary hot water tanks at which the load up aquastat is located.
    aquaFractShed : float
        The fraction of the total height of the primary hot water tanks at which the shed aquastat is located.
    loadUpT_F : float
        The hot water storage temperature between the normal and load up aquastat. [°F]
    loadShiftPercent : float
        Percentage of days the load shift will be met
    returnT_F : float 
        The water temperature returning from the recirculation loop. [°F]
    flow_rate : float 
        The pump flow rate of the recirculation loop. (GPM)
    gpdpp : float
        The volume of water in gallons at 120F each person uses per dat.[°F]
    nBR : array_like
        A list of the number of units by size in the order 0 bedroom units,
        1 bedroom units, 2 bedroom units, 3 bedroom units, 4 bedroom units,
        5 bedroom units.
    safetyTM : float
        The saftey factor for the temperature maintenance system.
    defrostFactor : float 
        A multipier used to account for defrost in the final heating capacity. Default equals 1.
    compRuntime_hr : float
        The number of hours the compressor will run on the design day. [Hr]
    nApt: integer
        The number of apartments. Use with Qdot_apt to determine total recirculation losses. (For multi-falmily buildings)
    Wapt:  float
        Watts of heat lost in through recirculation piping system. Used with N_apt to determine total recirculation losses. (For multi-falmily buildings)  
    doLoadShift : boolean
        Set to true if doing loadshift
    setpointTM_F : float
        The setpoint of the temprature maintence tank. Defaults to 130 °F.
    TMonTemp_F : float
        The temperature where parallel loop tank will turn on.
        Defaults to 120 °F.
    offTime_hr: integer
        Maximum hours per day the temperature maintenance equipment can run.
    standardGPD : string
        indicates whether to use a standard gpdpp specification for multi-family buildings. Set to None if not using a standard gpdpp.
    PVol_G_atStorageT : float
        For pre-sized systems, the total/maximum storage volume for water at storage temperature for the system in gallons
    PCap_kW : float
        For pre-sized systems, the output capacity for the system in kW
    TMVol_G : float
        For applicable pre-sized systems, the temperature maintenance volume for the system in gallons
    TMCap_kW : float
        For applicable pre-sized systems, the output capacity for temperature maintenance for the system in kW
    annual : boolean
        indicates whether to use annual loadshape for multi-family buildings
    zipCode : int
        the CA zipcode the building resides in to determine the climate zone
    climateZone : int
        the CA climate zone the building resides in
    systemModel : String
        The make/model of the HPWH being used for the primary system.
    numHeatPumps : int
        The number of heat pumps on the primary system
    tmModel : String
        The make/model of the HPWH being used for the temperature maintenance system.
    tmNumHeatPumps : int
        The number of heat pumps on the temperature maintenance system
    inletWaterAdjustment : float
        adjustment for inlet water temperature fraction for primary recirculation systems

    """

    def __init__(self, incomingT_F, supplyT_F, storageT_F, percentUseable, aquaFract,
                            schematic, magnitudeStat = None, buildingType = None, loadshape = None, 
                            avgLoadshape = None, loadShiftSchedule = None, loadUpHours = None,
                            aquaFractLoadUp = None, aquaFractShed = None, loadUpT_F = None, loadShiftPercent = 1,
                            returnT_F = 0, flowRate = 0, gpdpp = 0, nBR = None, safetyTM = 1.75,
                            defrostFactor = 1, compRuntime_hr = 16, nApt = None, Wapt = None, doLoadShift = False,
                            setpointTM_F = 135, TMonTemp_F = 120, offTime_hr = 0.333, standardGPD = None,
                            PVol_G_atStorageT = None, PCap_kW = None, TMVol_G = None, TMCap_kW = None,
                            annual = False, zipCode = None, climateZone = None, systemModel = None, numHeatPumps = None, 
                            tmModel = None, tmNumHeatPumps = None, inletWaterAdjustment = None):
        
        ignoreRecirc = False
        if schematic == 'singlepass_norecirc' or schematic == 'primary' or schematic == 'multipass_norecirc' or schematic == 'multipass':
            # recirculation does not matter because there is no temperature maintinence
            ignoreRecirc = True

        # convert kW inputs to kBTUhr
        PCap_kBTUhr = None
        if not PCap_kW is None:
            PCap_kBTUhr = PCap_kW * W_TO_BTUHR
        TMCap_kBTUhr = None
        if not TMCap_kW is None:
            TMCap_kBTUhr = TMCap_kW * W_TO_BTUHR

        self.building = createBuilding( 
                                incomingT_F     = incomingT_F,
                                magnitudeStat   = magnitudeStat, 
                                supplyT_F       = supplyT_F, 
                                buildingType    = buildingType,
                                loadshape       = loadshape,
                                avgLoadshape    = avgLoadshape,
                                returnT_F       = returnT_F, 
                                flowRate        = flowRate,
                                gpdpp           = gpdpp,
                                nBR             = nBR,
                                nApt            = nApt,
                                Wapt            = Wapt,
                                standardGPD     = standardGPD,
                                annual          = annual,
                                zipCode         = zipCode, 
                                climateZone     = climateZone,
                                ignoreRecirc    = ignoreRecirc
        )

        self.system = createSystem(  
                                schematic, 
                                storageT_F, 
                                defrostFactor, 
                                percentUseable, 
                                compRuntime_hr, 
                                aquaFract,
                                building = self.building if PVol_G_atStorageT is None else None, 
                                aquaFractLoadUp = aquaFractLoadUp,
                                aquaFractShed = aquaFractShed,
                                loadUpT_F = loadUpT_F,
                                doLoadShift = doLoadShift, 
                                loadShiftPercent = loadShiftPercent, 
                                loadShiftSchedule = loadShiftSchedule, 
                                loadUpHours = loadUpHours,
                                safetyTM = safetyTM, 
                                setpointTM_F = setpointTM_F, 
                                TMonTemp_F = TMonTemp_F, 
                                offTime_hr = offTime_hr,
                                PVol_G_atStorageT = PVol_G_atStorageT, 
                                PCap_kBTUhr = PCap_kBTUhr, 
                                TMVol_G = TMVol_G, 
                                TMCap_kBTUhr = TMCap_kBTUhr,
                                systemModel = systemModel,
                                numHeatPumps = numHeatPumps,
                                tmModel = tmModel,
                                tmNumHeatPumps = tmNumHeatPumps,
                                inletWaterAdjustment = inletWaterAdjustment
        )
    
    def getSimResult(self, initPV=None, initST=None, minuteIntervals = 1, nDays = 3, kWhCalc = False, kGDiff = False, optimizeNLS = False):
        """
        ***LEGACY FUNCTION*** to be depricated.
        Returns the result of a simulation of a HPWH system in a building

        Parameters
        ----------
        initPV : float
            Primary volume at start of the simulation
        initST : float
            Swing tank temperature at start of the simulation.
        minuteIntervals : int
            the number of minutes the duration each interval timestep for the simulation will be
        nDays : int
            the number of days the for duration of the entire simulation will be
        kWhCalc : boolean
            set to true to add the kgCO2/kWh calculation to the result.
        kGDiff : boolean
            set to True if you want to include the kGCO2/kWh saved in the result. Will also include loadshift capacity. Only available for loadshifting systems with annual loadshapes
        optimizeNLS : boolean
            set to True to optimize non-loadshift sizing. Only applies if kGDiff = True
            
        Returns
        -------
        simResult : List
            contains the following items in this order:
                pV : List 
                    Volume of HW in the tank at the storage temperature at every simulation interval. (Gallons)
                hwGen : List
                    The theoretical amount of HW at storage tempurature that can be generated at every simulation interval. (Gallons)
                hwDemand : List
                    The amount of HW used by the building (loadshape) at every simulation interval. (Gallons)
                pGen : List
                    The actual amount of HW at storage tempurature generated by the primary system at every simulation interval. (Gallons)
            If the system is a swing tank, the following fields will appear in the result in this order:
                swingT_F : List
                    Tempurature of water in the swing tank at every simulation interval. (F)
                tmRun : List
                    Amount of time the temperature maintenance is on during every simulation interval. (Minutes)
                hw_outSwing : List
                    Hot water exiting swing tank at swing tank temperature at every simulation interval. (Gallons)
            If kWhCalc == True, the following fields will appear in the result in this order:
                pRun : List
                    Amount of time the primary tank is on during every simulation interval. (Minutes)
                oat : List
                    Tempurature of outdoor air at every simulation interval. (F)
                cap : List
                    The capacity of the primary system at every simulation interval. (kW)
                kGperkWh : List
                    The kGCO2 used in every simulation interval. (kGCO2)
                sum_of_kGperkWh : Float
                    Sum of kGCO2 used in the simulation. (kGCO2)
                avgIncomingWaterT_F : Float
                    Average incoming water temperature for the entire simulation. (F)
            If kGDiff == True, the following fields will appear in the result in this order:
                loadshift_capacity : Float
                    The loadshift capacity for the entire simulation (kWh)
                kGperKwH_saved : Float
                    The kGCO2 saved by using load shifting in the simulation. (kGCO2/kWh)
                ***NOTE*** If kGDiff == True, the return value will be an array of size [2][x], where x is the length
                return values for one simulation result and array[0] will be the simulation result with load shifting
                and array[1] will be the result without load shifting.
        """
        if kGDiff:
            # TODO unit tests
            if not self.system.doLoadShift:
                raise Exception('Cannot preform kgCO2/kWh calculation on non-loadshifting systems.')
            if nDays != 365 or len(self.building.loadshape) != 8760:
                raise Exception('kgCO2/kWh calculation is only available for annual simulations.')
            
            simRun_ls = simulate(self.system, self.building, initPV=initPV, initST=initST, minuteIntervals = minuteIntervals, nDays = nDays)
            simResult_ls = simRun_ls.returnSimResult(kWhCalc = True)
            
            loadshift_capacity = (8.345*self.system.PVol_G_atStorageT*(self.system.aquaFractShed-self.system.aquaFractLoadUp)*(self.system.storageT_F-simResult_ls[-1]))/3412 # stored energy, not input energy
            kGperkWh_ls = simResult_ls[-2]/loadshift_capacity

            nls_system = copy.copy(self.system)

            nls_system.setDoLoadShift(False)
            if optimizeNLS:
                # resize system for most optimized system without loadshifting
                self.building.setToDailyLS()
                nls_system.sizeSystem(self.building)
                self.building.setToAnnualLS()

            simRun_nls = simulate(nls_system, self.building, initPV=initPV, initST=initST, minuteIntervals = minuteIntervals, nDays = nDays)
            simResult_nls = simRun_nls.returnSimResult(kWhCalc = True)
            kGperkWh_nls = simResult_nls[-2]/loadshift_capacity

            kGperkWh_saved = kGperkWh_nls - kGperkWh_ls
            simResult_ls.append(loadshift_capacity)
            simResult_ls.append(kGperkWh_saved)
            bothResults = [simResult_ls, simResult_nls]
            return bothResults
        else:
            simRun = simulate(self.system, self.building, initPV=initPV, initST=initST, minuteIntervals = minuteIntervals, nDays = nDays)
            return simRun.returnSimResult(kWhCalc = kWhCalc)
        
    def getSimRun(self, initPV=None, initST=None, minuteIntervals = 1, nDays = 3, exceptOnWaterShortage = True) -> SimulationRun:
        """
        Returns a simulationRun object for a simulation of the Ecosizer's building and system object

        Parameters
        ----------
        initPV : float
            Primary volume at start of the simulation
        initST : float
            Swing tank temperature at start of the simulation. Not used in this instance of the function
        minuteIntervals : int
            the number of minutes the duration each interval timestep for the simulation will be
        nDays : int
            the number of days the for duration of the entire simulation will be
        exceptOnWaterShortage : boolean
            Throws an exception if Primary Storage runs out of water. Otherwise returns failed simulation run

        Returns
        -------
        simRun : SimulationRun
            The object carrying details from the simulation of the system
        """
        return simulate(self.system, self.building, initPV=initPV, initST=initST, minuteIntervals = minuteIntervals, nDays = nDays, exceptOnWaterShortage = exceptOnWaterShortage)
    
    def getSimRunWithkWCalc(self, initPV=None, initST=None, minuteIntervals = 15, nDays = 365, optimizeNLS = False):
        """
        Returns a list that includes a simulationRun object for a simulation of the Ecosizer's building and system object with load shifting and without load shifting,
        also includes the loadshift_capacity and the kGperkWh_saved

        Parameters
        ----------
        initPV : float
            Primary volume at start of the simulation
        initST : float
            Swing tank temperature at start of the simulation. Not used in this instance of the function
        minuteIntervals : int
            the number of minutes the duration each interval timestep for the simulation will be
        nDays : int
            the number of days the for duration of the entire simulation will be
        optimizeNLS : boolean
            set to True to optimize non-loadshift sizing. Only applies if kGDiff = True

        Returns
        -------
        simRun_ls : SimulationRun
            The object carrying details from the simulation of the system with load shifting activated
        simRun_nls : SimulationRun
            The object carrying details from the simulation of the system with load shifting deactivated
        loadshift_capacity : float
            Thermal storage capacity of the tank volume between the load up and shed aquastat in kWh
        kGperkWh_saved : float
            Annual reduction in CO2 emissions per kWh of load shift capacity
        annual_kGCO2_saved : float
            Annual CO2 emissions saved by scheduling heat pump to load shift in kg CO2-e

        Raises
        ----------
        Exception: Error if system has not been set up for load shifting.
        """
        if not self.system.doLoadShift:
            raise Exception('Cannot preform kgCO2/kWh calculation on non-loadshifting systems.')
        if nDays != 365 or len(self.building.loadshape) != 8760:
            raise Exception('kgCO2/kWh calculation is only available for annual simulations.')
        
        simRun_ls = simulate(self.system, self.building, initPV=initPV, initST=initST, minuteIntervals = minuteIntervals, nDays = nDays)
        
        loadshift_capacity = (rhoCp*self.system.PVol_G_atStorageT*(self.system.aquaFractShed-self.system.aquaFractLoadUp)*(self.system.storageT_F-simRun_ls.getAvgIncomingWaterT()))/KWH_TO_BTU # stored energy, not input energy
        kG_sum_ls = simRun_ls.getkGCO2Sum()
        kGperkWh_ls = kG_sum_ls/loadshift_capacity

        nls_system = copy.copy(self.system)

        nls_system.setDoLoadShift(False)
        if optimizeNLS:
            # resize system for most optimized system without loadshifting
            self.building.setToDailyLS()
            nls_system.sizeSystem(self.building)
            self.building.setToAnnualLS()

        simRun_nls = simulate(nls_system, self.building, initPV=initPV, initST=initST, minuteIntervals = minuteIntervals, nDays = nDays)
        kG_sum_nls = simRun_nls.getkGCO2Sum()
        kGperkWh_nls = kG_sum_nls/loadshift_capacity

        annual_kGCO2_saved = kG_sum_nls - kG_sum_ls
        kGperkWh_saved = kGperkWh_nls - kGperkWh_ls
        return [simRun_ls, simRun_nls, loadshift_capacity, kGperkWh_saved, annual_kGCO2_saved]

    def getSizingResults(self):
        """
        Returns the minimum primary volume and heating capacity sizing results

        Returns
        -------
        PVol_G_atStorageT : float
            The volume of the primary storage tank storing DHW at storage tempurature in gallons.
        PCap_kBTUhr : float
            The heating capacity of the primary HPWH in kBTUhr
        TMVol_G : float
            Available only in systems with a tempurature maintenence system. The volume of the tempurature maintenence system in gallons.
        TMCap_kBTUhr : float 
            Available only in systems with a tempurature maintenence system. The heating capacity of the tempurature maintenence system in kBTUhr
        CA_TMVol_G : float 
            Available only in systems with a swing tank. The volume of the swing in gallons as specified by California sizing methods.
        """
        return self.system.getSizingResults()

    def primaryCurve(self):
        """
        Sizes the primary system curve. Will catch the point at which the aquatstat
        fraction is too small for system and cuts the return arrays to match cutoff point.

        Returns
        -------
        volN : array
            Array of volume in the tank at each hour.

        sHrs2kBTUHR : array
            Array of heating capacity in kBTU/hr
            
        heatHours : array
            Array of running hours per day corresponding to primaryHeatHrs2kBTUHR
            
        recIndex : int
            The index of the recommended heating rate. 
        """
        return self.system.primaryCurve(self.building)
    
    def plotStorageLoadSim(self, return_as_div=True, initPV=None, initST=None, minuteIntervals = 1, nDays = 3):
        """
        Returns a plot of the of the simulation for the minimum sized primary
        system as a div or plotly figure. Can plot the minute level simulation

        Parameters
        ----------
        return_as_div
            A logical on the output, as a div string (true) or as a figure (false)
        initPV : float
            Primary volume at start of the simulation
        initST : float
            Swing tank temperature at start of the simulation. Not used in this instance of the function
        minuteIntervals : int
            the number of minutes the duration each interval timestep for the simulation will be
        nDays : int
            the number of days the for duration of the entire simulation will be

        Returns
        -------
        plot : plotly.Figure -OR- <div> string
            The storage load simulation graph. Return type depends on value of return_as_div parameter.
        """
        simRun = simulate(self.system, self.building, initPV=initPV, initST=initST, minuteIntervals = minuteIntervals, nDays = nDays)
        return simRun.plotStorageLoadSim(return_as_div)
    
    def plotSizingCurve(self, returnAsDiv = False, returnWithXYPoints = False):
        """
        Returns a plot of the valid storage and capacity combinations.

        Parameters
        ----------
        return_as_div : boolean
            A logical on the output, as a div string (true) or as a figure (false)
        returnWithXYPoints : boolean
            set to true to return the plot in addition to arrays of x and y coordinates for the sizing curve

        Returns
        -------
        plot : plotly.Figure -OR- <div> string
            The sizing curve graph with slider. Return type depends on value of return_as_div parameter.
            If the system has a load shifting element, the graph will plot Percent of Load Shift Days Covered vs. Storage Volume.
            Otherwise, it will plot Storage Volume vs. Capacity.
        x_values : List
            List of x axis values of points on the sizing curve. Returned only if returnWithXYPoints set to True.
        y_values : List
            List of y axis values of points on the sizing curve. Returned only if returnWithXYPoints set to True.
        startIndex : int
            the index in x_values and y_values to start the slider on the sizing curve. Returned only if returnWithXYPoints set to True.
        """
        if self.system.doLoadShift:
            [storage_data, capacity_data, percents, startIndex] = self.lsSizedPoints()
            storage_data = around(flipud(storage_data),2)
            percents = around(flipud(percents),2)
            if returnWithXYPoints:
                return [
                    self.system.getPrimaryCurveAndSlider(percents, storage_data, startIndex, percents, returnAsDiv = returnAsDiv),
                    percents,
                    storage_data,
                    startIndex
                ]
            return self.system.getPrimaryCurveAndSlider(percents, storage_data, startIndex, percents, returnAsDiv = returnAsDiv)
        else:
            [storage_data, capacity_data, hours, startIndex] = self.primaryCurve()
            storage_data = around(flipud(storage_data),2)
            capacity_data = around(flipud(capacity_data),2)
            hours = around(flipud(hours),2)
            startIndex = len(storage_data)-startIndex-1
            if returnWithXYPoints:
                return [
                    self.system.getPrimaryCurveAndSlider(storage_data, capacity_data, startIndex, hours, returnAsDiv = returnAsDiv),
                    storage_data,
                    capacity_data,
                    startIndex
                ]
            return self.system.getPrimaryCurveAndSlider(storage_data, capacity_data, startIndex, hours, returnAsDiv = returnAsDiv)
    
    def lsSizedPoints(self):
        """
        Returns combinations of storage and percent of load shift days covered

        Raises
        ----------
        Exception: Error if system has not been set up for load shifting.

        Returns 
        -------
        volN : array
            Array of storage volume for each number of load up hours.
        CapN : array
            Array of heating capacity for each number of load up hours.
        N : array
            Array of load up hours tested. Goes from 1 to hour before first shed.
        startIndex : int
            The position the slider on the graph should start, reflecting the user defined load shift percent
        """
        return self.system.lsSizedPoints(self.building)

    def getHWMagnitude(self):
        """
        Returns the total daily DHW usage for the building the HPWH is being sized or simulated for.
        
        Returns
        -------
        magnitude : Float
            The total daily DHW usage for the building in gallons.
        """
        return self.building.magnitude
    
    def getClimateZone(self):
        """
        Returns climate zone of the simulation building as an int or None if it has not been set.
        
        Returns
        -------
        climateZone : int
            A number between 1 and 16 that represents the coorespondiong California climate zone. Returns None if this value has not been set.
        """
        return self.building.getClimateZone()
    
##############################################################
# STATIC FUNCTIONS
##############################################################
    
def getListOfModels(multiPass = False):
    """
    Static Method to Return all Model Names as a list of strings

    Parameters
    ----------
    multiPass : boolean
        return multi-pass models only (True) or single=pass models only (False)

    Returns
    -------
    model_list : List
        a list of tuples containing strings in the form [model_code, display_name] where model_code is the string to set as the systemModel parameter for EcosizerEngine and
        display_name is the corresponding friendly display name for that model.
    """
    returnList = []
    with open(os.path.join(os.path.dirname(__file__), '../data/preformanceMaps/maps.json')) as json_file:
        data = json.load(json_file)
        for model_name, value in data.items():
            if multiPass and model_name[-2:] == 'MP':
                returnList.append([model_name,value["name"]])
            elif not multiPass and model_name[-2:] != 'MP':
                returnList.append([model_name,value["name"]])
    return returnList

def getSizingCurvePlot(x, y, startind, loadshifting = False):
    """
    creates a plotly figure from a list of x and y points and starts the slider at the start index.

    Parameters
    ----------
    x : List
        List of x axis values of points on the sizing curve.
    y : List
        List of y axis values of points on the sizing curve.
    startind : int
        the index in x_values and y_values to start the slider on the sizing curve.
    loadshifting : boolean
        Indicates whether the resulting plot should be for a load shifting system (plotting Percent of Load Shift Days Covered vs. Storage Volume)
        or non-load shifting system (plotting Storage Volume vs. Capacity)

    Returns
    -------
    plot : plotly.Figure
        The sizing curve graph. If loadshifting parameter is set to True, the graph will label the plot as Percent of Load Shift Days Covered vs. Storage Volume.
        Otherwise, it will label the plot as Storage Volume vs. Capacity.
    """
    return createSizingCurvePlot(x, y, startind, loadshifting)

def getAnnualSimLSComparison(simRun_ls : SimulationRun, simRun_nls : SimulationRun, return_as_div=True):
    """
    Returns comparison graph of the input power by hour for an annual load shifting and non loadshifting HPWH simulation

    Parameters
    ----------
    simRun_ls : SimulationRun
        The object carrying details from the simulation of the system with load shifting activated
    simRun_nls : SimulationRun
        The object carrying details from the simulation of the system with load shifting deactivated
    return_as_div : boolean
            A logical on the output, as a div string (true) or as a figure (false)

    Returns
    -------
    plot : plotly.Figure OR div string
        The annual simulation graph comparing average daily input capacity of the system with load shifting activated and the system with load shifting deactivated.
    """
    if simRun_ls.minuteIntervals != 15 or simRun_nls.minuteIntervals != 15 or len(simRun_ls.oat) != 8760 or len(simRun_nls.oat) != 8760:
        raise Exception("Both simulation runs needs to be annual with 15 minute intervals to generate comparison graph.")
        # TODO make useful for non-15 min intervals

    energy_ls = [0] * 25
    energy_nls = [0] * 25
    hour_axis = [0] * 25
    
    for i in range(8760*4):
        energy_ls[(i % 96) // 4] += ((simRun_ls.getCapIn(i) * simRun_ls.getPrimaryRun(i)) + (simRun_ls.getTMCapIn(i) * simRun_ls.getTMRun(i)))/60
        energy_nls[(i % 96) // 4] += ((simRun_nls.getCapIn(i) * simRun_nls.getPrimaryRun(i)) + (simRun_nls.getTMCapIn(i) * simRun_nls.getTMRun(i)))/60

    for i in range(24):
        hour_axis[i] = i
        energy_ls[i] = energy_ls[i]/365
        energy_nls[i] = energy_nls[i]/365

    hour_axis[24] = 24
    energy_ls[24] = energy_ls[0]
    energy_nls[24] = energy_nls[0]

    fig = Figure()
    
    max_kw = max(max(energy_nls),max(energy_ls))
    
    ls_off = [max_kw + 10 if simRun_ls.LS_sched[i] == 'S' else 0 for i in range(24)]
    ls_off.append(ls_off[0])
    fig.add_trace(Scatter(
        x=hour_axis, 
        y=ls_off, 
        name='Load Shift Shed Period',
        mode='lines', 
        line_shape='hv',
        opacity=0.5, marker_color='grey',
        fill='tonexty'))

    fig.add_trace(Scatter(
        x = hour_axis,
        y = energy_ls,
        marker_color='blue',
        name = 'Load Shift'))
    fig.add_trace(Scatter(
        x = hour_axis,
        y = energy_nls,
        marker_color='red',
        name = 'Baseline'))
    
    fig.update_xaxes(title_text='Hour')
    fig.update_yaxes(title_text='Energy Use (kWh)',
                     range=[0, max_kw + 5])
    fig.update_layout(title_text='Annual Average Hourly Thermal Energy Use')
    
    if return_as_div:
        plot_div = plot(fig, output_type='div', show_link=False, link_text="",
                    include_plotlyjs = False)
        return plot_div
    return fig 

    
    


