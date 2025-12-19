from .BuildingCreator import *
from .SystemCreator import *
from .Simulator import simulate
from ecoengine.objects.SimulationRun import *
from ecoengine.objects.systemConfigUtils import *
from ecoengine.objects.UtilityCostTracker import *
from ecoengine.objects.PrefMapTracker import PrefMapTracker
from ecoengine.constants.Constants import month_to_hour,month_names
import copy
import json
from plotly.graph_objs import Figure, Scatter, Bar
from plotly.offline import plot
from numpy import around, flipud
from io import TextIOWrapper

# TODO need to add a dynamic staged capacity note in front end and get rid of swing tank resistance element output for rtp systems
# Also need to fix other pages

print("EcosizerEngine Copyright (C) 2023  Ecotope Inc.")
print("This program comes with ABSOLUTELY NO WARRANTY. This is free software, and you are welcome to redistribute under certain conditions; details check GNU AFFERO GENERAL PUBLIC LICENSE_08102020.docx.")

class EcosizerEngine:
    """
    Initializes and sizes the HPWH system for a building based on the given parameters.

    Attributes
    ----------
    magnitude_stat : int or list
        a number that will be used to assess the magnitude of the building based on the building type
    supplyT_F : float
        The hot water supply temperature.[°F]
    storageT_F : float 
        The hot water storage temperature. [°F]
    percentUseable : float
        The fraction of the storage volume that can be filled with hot water.
    schematic : String
        Indicates schematic type. Valid values are 'swingtank', 'paralleltank', and 'primary'
    onFract: float
        The fraction of the total height of the primary hot water tanks at which the ON temperature sensor is located.
    offFract : float
        The fraction of the total height of the primary hot water tanks at which the OFF temperature is located (defaults to onFract if not specified)
    onT : float
        The temperature detected at the onFract at which the HPWH system will be triggered to turn on. (defaults to supplyT_F if not specified)
    offT : float
        The temperature detected at the offFract at which the HPWH system will be triggered to turn off. (defaults to storageT_F if not specified)
    incomingT_F : float 
        The incoming city water temperature on the design day. [°F]
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
    outletLoadUpT : float 
        The hot water outlet temperature during load up mode. [°F]
    onFractLoadUp : float
        The fraction of the total height of the primary hot water tanks at which the ON temperature sensor is located during load up periods. (defaults to onFract if not specified)
    offFractLoadUp : float
        The fraction of the total height of the primary hot water tanks at which the OFF temperature sensor is located during load up periods. (defaults to offFract if not specified)
    onLoadUpT : float
        The temperature detected at the onFractLoadUp at which the HPWH system will be triggered to turn on during load up periods. (defaults to onT if not specified)
    offLoadUpT : float
        The temperature detected at the offFractLoadUp at which the HPWH system will be triggered to turn off during load up periods. (defaults to offT if not specified)
    onFractShed : float
        The fraction of the total height of the primary hot water tanks at which the ON temperature sensor is located during shed periods. (defaults to onFract if not specified)
    offFractShed : float
        The fraction of the total height of the primary hot water tanks at which the OFF temperature is located during shed priods (defaults to offFract if not specified)
    onShedT : float
        The temperature detected at the onFractShed at which the HPWH system will be triggered to turn on during shed periods. (defaults to onT if not specified)
    offShedT : float
        The temperature detected at the offFractShed at which the HPWH system will be triggered to turn off during shed periods. (defaults to offT if not specified)
    loadShiftPercent : float
        Percentage of days the load shift will be met
    returnT_F : float 
        The water temperature returning from the recirculation loop. [°F]
    returnFlow_gpm : float 
        The pump flow rate of the recirculation loop. (GPM)
    gpdpp : float
        The volume of water in gallons at DHW supply temperature each person uses per dat.[°F]
    nBR : list
        A list of the number of units by size in the order 0 bedroom units,
        1 bedroom units, 2 bedroom units, 3 bedroom units, 4 bedroom units,
        5 bedroom units.
    safetyTM : float
        The saftey factor for the temperature maintenance system.
    defrostFactor : float 
        A multipier used to account for defrost in the final heating capacity. Default equals 1.
    compRuntime_hr : float
        The number of hours the compressor will run on the design day. [Hr]
    nApt : integer
        The number of apartments. Use with Qdot_apt to determine total recirculation losses. (For multi-falmily buildings)
    Wapt : float
        Watts of heat lost in through recirculation piping system. Used with N_apt to determine total recirculation losses. (For multi-falmily buildings)  
    doLoadShift : boolean
        Set to true if doing loadshift
    setpointTM_F : float
        The setpoint of the temprature maintence tank. Defaults to 135 °F.
    TMonTemp_F : float
        The temperature where parallel loop tank will turn on.
        Defaults to 120 °F.
    offTime_hr : integer
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
    useHPWHsimPrefMap : boolean
        if available for the HPWH model in systemModel and/or tmModel, the system will use the preformance map from HPWHsim if useHPWHsimPrefMap is set to True. 
        Otherwise, it will use the most recent data model.
    designOAT_F : float
        The outdoor air temperature for sizing the number of heat pumps and/or ER capacity in an ER-Trade off system.
    sizeAdditionalER : boolean
        if set to True, swingtank_er will be assummed as schematic and will size for additional ER element. False if there is no need to size additional ER for swingtank_er schematic
    additionalERSaftey : float
        applicable for ER trade off swing tank only. Saftey factor to apply to additional electric resistance sizing
    """

    def __init__(self, supplyT_F, storageT_F, percentUseable, schematic, onFract, offFract = None, onT = None, offT = None, incomingT_F = None,
                            magnitudeStat = None, buildingType = None, loadshape = None, avgLoadshape = None, loadShiftSchedule = None, 
                            loadUpHours = None, outletLoadUpT = None,
                            onFractLoadUp = None, offFractLoadUp = None, onLoadUpT = None, offLoadUpT = None, 
                            onFractShed = None, offFractShed = None, onShedT = None, offShedT = None, 
                            loadShiftPercent = 1, returnT_F = 0, flowRate = 0, gpdpp = 0, nBR = None, safetyTM = 1.75,
                            defrostFactor = 1, compRuntime_hr = 16, nApt = None, Wapt = None, doLoadShift = False,
                            setpointTM_F = 135, TMonTemp_F = 120, offTime_hr = 0.333, standardGPD = None,
                            PVol_G_atStorageT = None, PCap_kW = None, TMVol_G = None, TMCap_kW = None,
                            annual = False, zipCode = None, climateZone = None, systemModel = None, numHeatPumps = None, 
                            tmModel = None, tmNumHeatPumps = None, inletWaterAdjustment = None,
                            useHPWHsimPrefMap = False, designOAT_F = None, sizeAdditionalER = False, additionalERSaftey = 1.0):
        
        if sizeAdditionalER:
            schematic = "swingtank_er"
        # if schematic == "mprtp":
        #     compRuntime_hr = 10
        
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
                                ignoreRecirc    = ignoreRecirc,
                                designOAT_F     = designOAT_F
        )

        self.system = createSystem(  
                                schematic, 
                                storageT_F, 
                                defrostFactor, 
                                percentUseable, 
                                compRuntime_hr, 
                                onFract,
                                building = self.building, 
                                offFract = offFract, 
                                onT = onT, 
                                offT = offT, 
                                outletLoadUpT = outletLoadUpT,
                                onFractLoadUp = onFractLoadUp, 
                                offFractLoadUp = offFractLoadUp, 
                                onLoadUpT = onLoadUpT, 
                                offLoadUpT = offLoadUpT, 
                                onFractShed = onFractShed, 
                                offFractShed = offFractShed, 
                                onShedT = onShedT, 
                                offShedT = offShedT,
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
                                inletWaterAdjustment = inletWaterAdjustment,
                                useHPWHsimPrefMap = useHPWHsimPrefMap,
                                sizeAdditionalER = sizeAdditionalER,
                                additionalERSaftey = additionalERSaftey
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
            # TODO retite this
            print("Warning: getSimResult() is a depricated function. Please use getSimRunWithkWCalc instead")
            if not self.system.doLoadShift:
                raise Exception('Cannot preform kgCO2/kWh calculation on non-loadshifting systems.')
            if nDays != 365 or len(self.building.loadshape) != 8760:
                raise Exception('kgCO2/kWh calculation is only available for annual simulations.')
            
            simRun_ls = simulate(self.system, self.building, initPV=initPV, initST=initST, minuteIntervals = minuteIntervals, nDays = nDays)
            simResult_ls = simRun_ls.returnSimResult(kWhCalc = True)
            
            loadshift_capacity = (8.345*self.system.PVol_G_atStorageT*(self.system.onFractShed-self.system.onFractLoadUp)*(self.system.storageT_F-simResult_ls[-1]))/3412 # stored energy, not input energy
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
    
    def getNumShedHours(self):
        """
        Returns
        -------
        shed_hours : float
            Number of hours the system should be able to shed for during the 4 PM - 9 PM peak
        """
        thermal_cap_remaining = self.getLoadShiftCapacity()
        hour = 16 # 4:00 PM
        hours_met = 0.0
        while thermal_cap_remaining > 0:
            thermal_load = (rhoCp*self.building.getLoadAtHour(hour)*(self.building.supplyT_F-self.building.getAvgIncomingWaterT()))/KWH_TO_BTU # kWh
            hours_met += min(thermal_cap_remaining/thermal_load,1.0)
            thermal_cap_remaining -= thermal_load
            hour += 1
        return hours_met

    def getLoadShiftCapacity(self):
        """
        Returns
        -------
        loadshift_capacity : float
            Thermal storage capacity of the tank volume between the load up and shed aquastat in kWh
        """
        return (rhoCp*self.system.PVol_G_atStorageT*(self.system.onFractShed-self.system.onFractLoadUp)*(self.system.offLoadUpT-self.building.getAvgIncomingWaterT()))/KWH_TO_BTU # stored energy, not input energy

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
        if not self.building.isInCalifornia():
            raise Exception('kgCO2/kWh calculation is only available for California climate zones.')
        
        simRun_ls = simulate(self.system, self.building, initPV=initPV, initST=initST, minuteIntervals = minuteIntervals, nDays = nDays)
        
        loadshift_capacity = (rhoCp*self.system.PVol_G_atStorageT*(self.system.onFractShed-self.system.onFractLoadUp)*(self.system.offLoadUpT-self.building.getAvgIncomingWaterT()))/KWH_TO_BTU # stored energy, not input energy
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
    
    def getMaxCyclingCapacity_kBTUhr(self):
        return self.system.getMaxCyclingCapacity_kBTUhr()

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
    
    def erSizedPointsPlot(self, returnAsDiv = True, returnWithXYPoints = False):
        """
        Returns a plot of sizing Electric Resistance Capacity by the percent of people covered in the appartment building.

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
            It will plot Percent of Coverage vs. Swing Tank Capacity.
        x_values : List
            List of x axis values of points on the sizing curve. Returned only if returnWithXYPoints set to True.
        y_values : List
            List of y axis values of points on the sizing curve. Returned only if returnWithXYPoints set to True.
        startIndex : int
            the index in x_values and y_values to start the slider on the sizing curve. Returned only if returnWithXYPoints set to True.
        """
        if not hasattr(self.system, "original_TMCap_kBTUhr"):
            raise Exception("erSizedPoints function is only applicable to systems with swing tank electric resistance trade-off capabilities.")
        [er_cap_kW, fract_covered, startInd] = self.system.erSizedPoints(self.building)
        if returnWithXYPoints:
            return [
                self.system.getERCurveAndSlider(fract_covered, er_cap_kW, startInd, returnAsDiv = returnAsDiv),
                fract_covered,
                er_cap_kW,
                startInd
            ]
        return self.system.getERCurveAndSlider(fract_covered, er_cap_kW, startInd, returnAsDiv = returnAsDiv)

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
    
    def systemReliedOnEr(self):
        """
        Returns
        -------
        reliedOnER : boolean
            True if the system relied on electric resistance during it's last simulation. False otherwise.
        tmReliedOnER : boolean
            True if the temperature maintenance system relied on electric resistance during it's last simulation. False otherwise.
        """
        return self.system.reliedOnEr(), self.system.tmReliedOnEr()
    
    def systemCapedInlet(self):
        """
        Returns
        -------
        capedInlet : boolean
            Returns True if the model had to reduce the inlet water temperature to stay within the bounds of the available performance map for the model. False otherwise.
        """
        return self.system.capedInlet()
    
    def assumedHighDefaultCap(self):
        """
        Returns
        -------
        assumedHighIO : boolean
            Returns True if the model had to assume default high OAT input and output capacity because the climate's OAT was greater than the values in available performance map. False otherwise.
        """
        return self.system.assumedHighDefaultCap()
    
    def raisedInletTemp(self):
        """
        Returns
        -------
        raisedInlet : boolean
            Returns True if the system at any point needed to raise inlet water temperature if it was less than minimum in performance map. False otherwise.
        """
        return self.system.raisedInletTemp()
    
    def assumedCOP(self):
        """
        Returns
        -------
        assumedCOP : boolean
            Returns True if, at any time, the system has assumed a COP of 1.5 during a simulation due to performance map constraints. False otherwise.
        """
        return self.system.assumedCOP()
    
    def usedHPWHsim(self):
        """
        Returns
        -------
        usedHPWHsim : boolean
            Returns True if the performance map used was from HPWHsim. False otherwise.
        """
        return not self.system.perfMap.usePkl
    
    def utilityCalculation(self, monthly_base_charge, pk_start_hour, pk_end_hour, pk_demand_charge, pk_energy_charge, off_pk_demand_charge, off_pk_energy_charge, 
                           start_month = 0, end_month = 12, csv_path = None, include_dscnt_period = False, dscnt_start_hour = None, dscnt_end_hour = None, 
                           discnt_demand_charge = None, discnt_energy_charge = None, csv_file : TextIOWrapper = None):
        """
        Parameters
        ----------
        monthly_base_charge : float
            monthly base charge for having electricity connected ($/month)
        pk_start_hour : int (in range 0-23) or list of int (in range 0-23)
            start hour of the day which peak demand pricing applies
        pk_end_hour : int (in range pk_start_hour-24) or list of int (in range pk_start_hour-24)
            end hour of the day which peak demand pricing applies
        pk_demand_charge : float or list of float
            peak demand pricing ($/kW)
        pk_energy_charge : float or list of float
            peak energy pricing ($/kWh)
        off_pk_demand_charge : float or list of float
            off-peak demand pricing ($/kW)
        off_pk_energy_charge : float or list of float
            off-peak energy pricing ($/kWh)
        start_month : int (in range 0-11) or list of int (in range 0-11)
            start month for period (defaults to 0)
        end_month : int (in range start_month+1 - 12) or list of int (in range start_month[i]+1 - 12)
            end month for period (defaults to 12)
        csv_path : str
            file path to custom pricing csv. Must have three columns titled "Energy Rate ($/kWh)", "Demand Rate ($/kW)", "Demand Period", and "Monthly Base Charge" 
            with appropriate information in each column. Defaults to None
        include_dscnt_period : bool
            indicates whether or not the utility billing schedule includes a discounted rate period (such as overnight electrical use in British Columbia)
        dscnt_start_hour : int (in range 0-23) or list of int (in range 0-23)
            start hour of the day which discount pricing applies
        dscnt_end_hour : int (in range pk_start_hour-24) or list of int (in range pk_start_hour-24)
            end hour of the day which discount pricing applies
        discnt_demand_charge : float or list of float
            discount pricing ($/kW)
        discnt_energy_charge : float or list of float
            discount pricing ($/kWh)
        csv_file : TextIOWrapper
            an opened csv file (in place of csv_path) to be read

        Returns
        -------
        simRun : SimulationRun
            The object carrying details from the simulation of the system
        utility_cost : float
            The total annual utility cost for the simulation
        simRun_instant : SimulationRun
            The object carrying details from a simulation of the system if it was compossed of instantaneous water heaters for comparison
        utility_cost_instant : float
            The total annual utility cost for the simulation of the system if it was compossed of instantaneous water heaters for comparison
        uc : UtilityCostTracker
            the UtilityCostTracker from the simulation made from user params
        """
        uc = UtilityCostTracker(monthly_base_charge, pk_start_hour, pk_end_hour, pk_demand_charge, pk_energy_charge, off_pk_demand_charge, off_pk_energy_charge,
                                start_month, end_month, csv_path, include_dscnt_period, dscnt_start_hour, dscnt_end_hour, discnt_demand_charge, discnt_energy_charge,
                                csv_file = csv_file)
        simRun = self.getSimRun(minuteIntervals = 15, nDays = 365)
        utility_cost = simRun.getAnnualUtilityCost(uc)
        instant_wh_system = createSystem(  
                                "instant_wh", 
                                self.system.storageT_F, 
                                self.system.defrostFactor, 
                                self.system.percentUseable, 
                                self.system.compRuntime_hr, 
                                self.system.onFract,
                                building = self.building
        )
        instant_wh_simRun = simulate(instant_wh_system, self.building, minuteIntervals = 15, nDays = 365)

        return simRun, utility_cost, instant_wh_simRun, instant_wh_simRun.getAnnualUtilityCost(uc), uc
    
##############################################################
# STATIC FUNCTIONS
##############################################################

def getAnnualUtilityComparisonGraph(simRun_hp : SimulationRun, simRun_iwh : SimulationRun, uc : UtilityCostTracker, return_as_div : bool =True,
                                    return_as_array : bool = False):
    """
    Returns comparison graph of the input power by hour for an annual load shifting and non loadshifting HPWH simulation

    Parameters
    ----------
    simRun_hp : SimulationRun
        The object carrying details from the simulation of the system with a heat pump
    simRun_iwh : SimulationRun
        The object carrying details from the simulation of the system with instantaneous water heaters
    uc : UtilityCostTracker
        The UtilityCostTracker object carrying details for the annual utility cost plan
    return_as_div : boolean
        A logical on the output, as a div string (true) or as a figure (false)
    return_as_array : boolean
        A logical on the output, as a set of comparison arrays (true) or as a figure (false)

    Returns
    -------
    plot : plotly.Figure OR div string
        The annual simulation graph comparing monthly utility costs divided into base costs, demand charges, energy charges.
    """

    if simRun_hp.minuteIntervals != 15 or simRun_iwh.minuteIntervals != 15 or len(simRun_hp.oat) != 8760 or len(simRun_iwh.oat) != 8760:
        raise Exception("Both simulation runs needs to be annual with 15 minute intervals to generate comparison graph.")
        # TODO make useful for non-15 min intervals
    
    simRun_hp.createUtilityCostColumns(uc)
    simRun_iwh.createUtilityCostColumns(uc)
    
    base_charge_per_month_hp = [uc.monthly_base_charge,0] * 12
    base_charge_per_month_iwh = [0,uc.monthly_base_charge] * 12
    categories = ['Base Charges', 'Peak Demand Charges', 'Off-Peak Demand Charges', 'Peak Energy Charges', 'Off-Peak Energy Charges']
    hp_monthly_charges = [base_charge_per_month_hp,[0.]*24,[0.]*24,[0.]*24,[0.]*24]
    iwh_monthly_charges = [base_charge_per_month_iwh,[0.]*24,[0.]*24,[0.]*24,[0.]*24]
    hp_demand_kW_map, hp_demand_last_hour_map = simRun_hp.getDemandChargeMaps(uc)
    iwh_demand_kW_map, iwh_demand_last_hour_map = simRun_iwh.getDemandChargeMaps(uc)

    for month in range(12):
        for hour in month_to_hour[month]:
            demand_period = uc.getDemandPricingPeriod(hour, 60)
            sim_interval_start = hour*(60//simRun_hp.minuteIntervals)
            sim_interval_end = (hour+1)*(60//simRun_hp.minuteIntervals)
            if hp_demand_last_hour_map[demand_period] == hour:
                # should be the end of the demand period for both hp and iwh because they are using the same utility cost tracker
                if uc.is_peak_map[demand_period]:
                    hp_monthly_charges[1][month*2] = hp_monthly_charges[1][month*2] + uc.getDemandChargeForPeriod(demand_period, hp_demand_kW_map[demand_period])
                    iwh_monthly_charges[1][(month*2)+1] = iwh_monthly_charges[1][(month*2)+1] + uc.getDemandChargeForPeriod(demand_period, iwh_demand_kW_map[demand_period])
                else:
                    hp_monthly_charges[2][month*2] = hp_monthly_charges[2][month*2] + uc.getDemandChargeForPeriod(demand_period, hp_demand_kW_map[demand_period])
                    iwh_monthly_charges[2][(month*2)+1] = iwh_monthly_charges[2][(month*2)+1] + uc.getDemandChargeForPeriod(demand_period, iwh_demand_kW_map[demand_period])
            if uc.is_peak_map[demand_period]:
                hp_monthly_charges[3][(month*2)] += sum(simRun_hp.energyCost[sim_interval_start:sim_interval_end])
                iwh_monthly_charges[3][(month*2)+1] += sum(simRun_iwh.energyCost[sim_interval_start:sim_interval_end])
            else:
                hp_monthly_charges[4][(month*2)] += sum(simRun_hp.energyCost[sim_interval_start:sim_interval_end])
                iwh_monthly_charges[4][(month*2)+1] += sum(simRun_iwh.energyCost[sim_interval_start:sim_interval_end])

    if return_as_array:
        for i in range(5):
            for j in range(12):
                hp_monthly_charges[i][j] = hp_monthly_charges[i][j*2]
                iwh_monthly_charges[i][j] = iwh_monthly_charges[i][(j*2)+1]
            hp_monthly_charges[i] = hp_monthly_charges[i][0:12]
            iwh_monthly_charges[i] = iwh_monthly_charges[i][0:12]
        return hp_monthly_charges, iwh_monthly_charges

    fig = Figure()

    offset_month_names = []
    for month_name in month_names:
        offset_month_names.append(f"{month_name}")
        offset_month_names.append(f"{month_name} ")

    for i in range(len(categories)):
        fig.add_trace(Bar(
            x=offset_month_names, 
            y=hp_monthly_charges[i], 
            name=f"{categories[i]} for HP",
            hovertemplate="<br>".join([
                f"{categories[i]} (HP)",
                "%{x}",
                "$%{y}",
            ])
        ))
        fig.add_trace(Bar(
            x=offset_month_names,
            y=iwh_monthly_charges[i],
            name=f"{categories[i]} for UER",
            hovertemplate="<br>".join([
                f"{categories[i]} (UER)",
                "%{x}",
                "$%{y}",
            ])
        ))
    
    # fig.update_xaxes(title_text='Month',)
    fig.update_yaxes(title_text='Cost ($)')
    fig.update_layout(barmode='stack', title='Utility Cost Comparison: Heat Pump (HP) vs. Unitary Electric Resistance (UER)',
                        xaxis=dict(
                            tickvals=month_names,  # Position of the ticks
                            ticktext=month_names,  # Custom tick text
                            title='Month',
                        )
    )
    
    if return_as_div:
        plot_div = plot(fig, output_type='div', show_link=False, link_text="",
                    include_plotlyjs = False)
        return plot_div
    return fig 

def getAnnualUtilityComparisonGraph_Canada(simRun_hp : SimulationRun, simRun_iwh : SimulationRun, uc : UtilityCostTracker, return_as_div : bool =True,
                                    return_as_array : bool = False, monthly_tier_threshold : float = 675.0, tier_cost_increase : float = .0311):
    """
    Custom comparison graph for canadian utility billing structure.

    Parameters
    ----------
    simRun_hp : SimulationRun
        The object carrying details from the simulation of the system with a heat pump
    simRun_iwh : SimulationRun
        The object carrying details from the simulation of the system with instantaneous water heaters
    uc : UtilityCostTracker
        The UtilityCostTracker object carrying details for the annual utility cost plan
    return_as_div : boolean
        A logical on the output, as a div string (true) or as a figure (false)
    return_as_array : boolean
        A logical on the output, as a set of comparison arrays (true) or as a figure (false)
    monthly_tier_threshold : float
        The number of kWh a building must surpass in a month to go to tier 2 billing.
    tier_cost_increase : float
        The increase in Energy Rate from tier 1 to tier 2 in dollars

    Returns
    -------
    plot : plotly.Figure OR div string
        The annual simulation graph comparing monthly utility costs divided into base costs, demand charges, energy charges.
    """

    if simRun_hp.minuteIntervals != 15 or simRun_iwh.minuteIntervals != 15 or len(simRun_hp.oat) != 8760 or len(simRun_iwh.oat) != 8760:
        raise Exception("Both simulation runs needs to be annual with 15 minute intervals to generate comparison graph.")
        # TODO make useful for non-15 min intervals
    
    simRun_hp.createUtilityCostColumns(uc, 675.0, .0311)
    simRun_iwh.createUtilityCostColumns(uc, 675.0, .0311)
    base_charge_per_month_hp = []
    base_charge_per_month_iwh = []
    for month in range(12):
        base_charge_per_month_hp.append(0.2253*month_to_number_days[month])
        base_charge_per_month_hp.append(0)
        base_charge_per_month_iwh.append(0)
        base_charge_per_month_iwh.append(0.2253*month_to_number_days[month])
    categories = ['Base Charges', 'Peak Energy Charges', 'Off-Peak Energy Charges', 'Overnight Energy Charges']
    hp_monthly_charges = [base_charge_per_month_hp,[0.]*24,[0.]*24,[0.]*24]
    iwh_monthly_charges = [base_charge_per_month_iwh,[0.]*24,[0.]*24,[0.]*24]

    for month in range(12):
        for hour in month_to_hour[month]:
            demand_period = uc.getDemandPricingPeriod(hour, 60)
            sim_interval_start = hour*(60//simRun_hp.minuteIntervals)
            sim_interval_end = (hour+1)*(60//simRun_hp.minuteIntervals)
            if uc.is_peak_map[demand_period]:
                hp_monthly_charges[1][(month*2)] += sum(simRun_hp.energyCost[sim_interval_start:sim_interval_end])
                iwh_monthly_charges[1][(month*2)+1] += sum(simRun_iwh.energyCost[sim_interval_start:sim_interval_end])
            elif uc.is_discount_map[demand_period]:
                hp_monthly_charges[3][(month*2)] += sum(simRun_hp.energyCost[sim_interval_start:sim_interval_end])
                iwh_monthly_charges[3][(month*2)+1] += sum(simRun_iwh.energyCost[sim_interval_start:sim_interval_end])
            else:
                hp_monthly_charges[2][(month*2)] += sum(simRun_hp.energyCost[sim_interval_start:sim_interval_end])
                iwh_monthly_charges[2][(month*2)+1] += sum(simRun_iwh.energyCost[sim_interval_start:sim_interval_end])

    if return_as_array:
        for i in range(5):
            for j in range(12):
                hp_monthly_charges[i][j] = hp_monthly_charges[i][j*2]
                iwh_monthly_charges[i][j] = iwh_monthly_charges[i][(j*2)+1]
            hp_monthly_charges[i] = hp_monthly_charges[i][0:12]
            iwh_monthly_charges[i] = iwh_monthly_charges[i][0:12]
        return hp_monthly_charges, iwh_monthly_charges

    fig = Figure()

    offset_month_names = []
    for month_name in month_names:
        offset_month_names.append(f"{month_name}")
        offset_month_names.append(f"{month_name} ")

    for i in range(len(categories)):
        fig.add_trace(Bar(
            x=offset_month_names, 
            y=hp_monthly_charges[i], 
            name=f"{categories[i]} for HP",
            hovertemplate="<br>".join([
                f"{categories[i]} (HP)",
                "%{x}",
                "$%{y}",
            ])
        ))
        fig.add_trace(Bar(
            x=offset_month_names,
            y=iwh_monthly_charges[i],
            name=f"{categories[i]} for UER",
            hovertemplate="<br>".join([
                f"{categories[i]} (UER)",
                "%{x}",
                "$%{y}",
            ])
        ))
    
    # fig.update_xaxes(title_text='Month',)
    fig.update_yaxes(title_text='Cost ($)')
    fig.update_layout(barmode='stack', title='Utility Cost Comparison: Heat Pump (HP) vs. Unitary Electric Resistance (UER)',
                        xaxis=dict(
                            tickvals=month_names,  # Position of the ticks
                            ticktext=month_names,  # Custom tick text
                            title='Month',
                        )
    )
    
    if return_as_div:
        plot_div = plot(fig, output_type='div', show_link=False, link_text="",
                    include_plotlyjs = False)
        return plot_div
    return fig
    
def getListOfModels(multiPass = False, includeResidential = True, excludeModels = [], sgipModelsOnly = True):
    """
    Static Method to Return all Model Names as a list of strings

    Parameters
    ----------
    multiPass : boolean
        return multi-pass models only (True) or single=pass models only (False)
    includeResidential : boolean
        Set to True to include residential HPWH models. Set to False to only include commercial HPWH models.
    excludeModels : List[str]
        A list of models you wish to not include in the model list. Defaults to empty list.
     sgipModelsOnly : boolean
        Defaults to True. If True, excludes all non-SGIP listed models from the model list 

    Returns
    -------
    model_list : List[str]
        a list of tuples containing strings in the form [model_code, display_name] where model_code is the string to set as the systemModel parameter for EcosizerEngine and
        display_name is the corresponding friendly display name for that model.
    """
    returnList = []
    with open(os.path.join(os.path.dirname(__file__), '../data/preformanceMaps/maps.json')) as json_file:
        data = json.load(json_file)
        for model_name, value in data.items():
            if (not model_name in excludeModels) and (sgipModelsOnly == False or value["SGIP_avail"]):
                if includeResidential or model_name[-4] == "C":
                    if multiPass and model_name[-2:] == 'MP':
                        returnList.append([model_name,value["name"]])
                    elif not multiPass and model_name[-2:] != 'MP':
                        returnList.append([model_name,value["name"]])
    return returnList

def getWeatherStations(exclude_stations = [96]):
    """
    Static Method to Return all weather stations as strings with corresponding climate zones as integers

    Parameters
    ----------
    exclude_stations : List[int]
        A list of models you wish to not include in the model list. Defaults to empty list.

    Returns
    -------
    weather_stations : List[str]
        a list of tuples containing a string and integer in the form [weather_station_name, climate_zone] where weather_station_name is the string 
        representing the weather station name and climate_zone is the corresponding ecosizer climate zone.
        Weather data from https://energyplus.net/weather
    """
    data = []
    with open(os.path.join(os.path.dirname(__file__), '../data/climate_data/WeatherStation_ClimateZone_Lookup.csv'), 'r') as csvfile:
        csv_reader = csv.reader(csvfile)
        next(csv_reader) # skip header
        for row in csv_reader:
            # Assuming two columns: string and int
            if len(row) == 2:
                string_value, int_value = row
                # Convert the integer value to int type
                int_value = int(int_value)
                if not int_value in exclude_stations:
                    data.append([string_value, int_value])

    return data

def getHPWHOutputCapacity(model, outdoorAirTemp_F, inletWaterTemp_F, outletWaterTemp_F, num_heatPumps = 1, return_as_kW = True, defrost_derate = 0.0):
    """
    Returns the output capacity of the model at the climate temperatures provided
    
    Parameters
    ----------
    model : String
        string representing the model_code for the model (see getListOfModels() for information on how to aquire this)
    outdoorAirTemp_F : float
        The outdoor air temperature in degrees F
    inletWaterTemp_F : float
        the incoming city water (cold water) temperature in degrees F
    outletWaterTemp_F : float
        The outlet water (hot storage) temperature in degrees F
    num_heatPumps : int
        the number of HPWHs in the system
    return_as_kW : boolean
        Set to True (default) to return output capacity in kW. Set to False to instead return as kBTU/hr
    defrost_derate : float
        defrost derate at design outdoor air temperature for model. Should be a percent in decimal form between 0.0 and 1.0 (e.g. 40% defrost derate would be 0.40)

    Returns
    -------
    output_capacity : float
        the output capacity of the HPWH system at the climate temperatures provided in either kW or kBTU/hr depending on the value of the return_as_kW parameter
    """
    if not (isinstance(defrost_derate, int) or isinstance(defrost_derate, float)) or defrost_derate < 0.0 or defrost_derate > 1.0:
        raise Exception("defrost_derate must be a number between 0.0 and 1.0")
    if not isinstance(num_heatPumps, int) or num_heatPumps < 1:
        raise Exception("num_heatPumps must be an integer equal to or larger than 1")
    
    perfMap = PrefMapTracker(defaultCapacity_kBTUhr = None, 
                             modelName = model,
                             kBTUhr = return_as_kW == False,
                             numHeatPumps = num_heatPumps,
                             usePkl = True)
    output_cap, input_cap = perfMap.getCapacity(outdoorAirTemp_F,inletWaterTemp_F,outletWaterTemp_F)
    return output_cap * (1.0 - defrost_derate)

def get_oat_buckets(zipCode : int, cz : int = None) -> dict:
    """
    returns a dictionary that contains the number of days in which the average OAT falls in each OAT bucket for the given zipCode 

    Parameters
    ----------
    zipCode : int
        the zipcode the building resides in
    cz : int
        the climate zone the building resides in

    Returns
    -------
    oat_buckets : dict
        dict mapping each OAT bucket to the number of days in a year that have an average OAT in that bucket
    """
    return_dict = {}
    cz = getClimateZone(zipCode, cz)
    with open(os.path.join(os.path.dirname(__file__), '../data/climate_data/DryBulbTemperatures_ByClimateZone.csv'), 'r') as oat_file:
        oat_reader = csv.reader(oat_file)
        for i in range(365):
            daily_average_oat = 0
            for j in range(24):
                oat_row = next(oat_reader)
                daily_average_oat += float(oat_row[cz - 1])
            daily_average_oat = daily_average_oat/24
            bucket = (daily_average_oat // 5) * 5
            if bucket in return_dict:
                return_dict[bucket] = return_dict[bucket] + 1
            else:
                return_dict[bucket] = 1
    return return_dict


def getSizingCurvePlot(x, y, startind, loadshifting : bool = False, er_sized : bool = False):
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
    er_sized : boolean
        Indicates whether the resulting plot should be for Electric Resistance trade off sizing

    Returns
    -------
    plot : plotly.Figure
        The sizing curve graph. If loadshifting parameter is set to True, the graph will label the plot as Percent of Load Shift Days Covered vs. Storage Volume.
        Otherwise, it will label the plot as Storage Volume vs. Capacity.
    """
    if er_sized:
        return createERSizingCurvePlot(x, y, startind)
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
    
    ls_off = [max_kw + 10 if i >= 16 and i < 21 else 0 for i in range(24)]
    ls_off.append(ls_off[0])
    fig.add_trace(Scatter(
        x=hour_axis, 
        y=ls_off, 
        name='4-9 PM Peak Pricing',
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
    fig.update_layout(title_text='Annual Average Hourly Energy Use')
    
    if return_as_div:
        plot_div = plot(fig, output_type='div', show_link=False, link_text="",
                    include_plotlyjs = False)
        return plot_div
    return fig 

    
    


