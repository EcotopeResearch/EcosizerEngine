from .BuildingCreator import *
from .SystemCreator import *
from .Simulator import simulate
from ecoengine.objects.SimulationRun import *

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
    loadShiftPercent: float
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

    """

    def __init__(self, incomingT_F, magnitudeStat, supplyT_F, storageT_F, percentUseable, aquaFract,
                            schematic, buildingType, loadshape = None, avgLoadshape = None, loadShiftSchedule = None, loadUpHours = None,
                            aquaFractLoadUp = None, aquaFractShed = None, loadUpT_F = None, loadShiftPercent = 1,
                            returnT_F = 0, flowRate = 0, gpdpp = 0, nBR = None, safetyTM = 1.75,
                            defrostFactor = 1, compRuntime_hr = 16, nApt = None, Wapt = None, doLoadShift = False,
                            setpointTM_F = 135, TMonTemp_F = 120, offTime_hr = 0.333, standardGPD = None,
                            PVol_G_atStorageT = None, PCap_kBTUhr = None, TMVol_G = None, TMCap_kBTUhr = None,
                            annual = False, zipCode = None, climateZone = None, systemModel = None):
        
        ignoreRecirc = False
        if schematic == 'primary':
            # recirculation does not matter because there is no temperature maintinence
            ignoreRecirc = True

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
                                systemModel = systemModel
        )
    
    def getSimResult(self, initPV=None, initST=None, minuteIntervals = 1, nDays = 3, kWhCalc = False, kGDiff = False):
        """
        Returns the result of a simulation of a HPWH system in a building

        Inputs
        ------
        initPV : float
            Primary volume at start of the simulation
        initST : float
            Swing tank temperature at start of the simulation. Not used in this instance of the function
        minuteIntervals : int
            the number of minutes the duration each interval timestep for the simulation will be
        nDays : int
            the number of days the for duration of the entire simulation will be
        hpwhModel : string
            the real world HPWH model used in the simulation. Used to determina capacity and input power for varrious air temperaturess
        kWhCalc : boolean
            set to true to add the kgCO2/kWh calculation to the result.
        kGDiff : boolean
            set to True if you want to include the kGCO2/kWh saved in the result. Will also include loadshift capacity. Only available for loadshifting systems with annual loadshapes

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
                sRun : List
                    Amount of time the swing tank is on during every simulation interval. (Minutes)
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
        """
        if kGDiff:
            if not self.system.doLoadShift:
                raise Exception('Cannot preform kgCO2/kWh calculation on non-loadshifting systems.')
            if nDays != 365 or len(self.building.loadshape) != 8760:
                raise Exception('kgCO2/kWh calculation is only available for annual simulations.')
            
            simRun_ls = simulate(self.system, self.building, initPV=initPV, initST=initST, minuteIntervals = minuteIntervals, nDays = nDays)
            simResult_ls = simRun_ls.returnSimResult(kWhCalc = kWhCalc)
            
            loadshift_capacity = (8.345*self.system.PVol_G_atStorageT*(self.system.aquaFractShed-self.system.aquaFractLoadUp)*(self.system.storageT_F-simResult_ls[-1]))/3412 # stored energy, not input energy
            kGperkWh_ls = simResult_ls[-2]/loadshift_capacity

            self.system.setDoLoadShift(False)
            simRun_nls = simulate(self.system, self.building, initPV=initPV, initST=initST, minuteIntervals = minuteIntervals, nDays = nDays)
            simResult_nls = simRun_nls.returnSimResult(kWhCalc = kWhCalc)
            kGperkWh_nls = simResult_nls[-2]/loadshift_capacity

            kGperkWh_saved = kGperkWh_nls - kGperkWh_ls
            self.system.setDoLoadShift(True)
            simResult_ls.append(loadshift_capacity)
            simResult_ls.append(kGperkWh_saved)
            return simResult_ls
        else:
            simRun = simulate(self.system, self.building, initPV=initPV, initST=initST, minuteIntervals = minuteIntervals, nDays = nDays)
            return simRun.returnSimResult(kWhCalc = kWhCalc)

    def getSizingResults(self):
        """
        Returns the minimum primary volume and heating capacity sizing results

        Returns
        -------
        list
            self.PVol_G_atStorageT, self.PCap_kBTUhr (also self.TMVol_G, self.TMCap_kBTUhr if there is a TM system and self.CA_TMVol_G if SwingTank)
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
    
    def plotStorageLoadSim(self, return_as_div=True, initPV=None, initST=None, minuteIntervals = 1, nDays = 3, kWhCalc = False):
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
        simRun = simulate(self.system, self.building, initPV=initPV, initST=initST, minuteIntervals = minuteIntervals, nDays = nDays)
        return simRun.plotStorageLoadSim(return_as_div)
    
    def lsSizedPoints(self):
        """
        Returns combinations of storage and capacity based on number of 
        load up hours

        Returns 
        -------
        volN : array
            Array of storage volume for each number of load up hours.
        CapN : array
            Array of heating capacity for each number of load up hours.
        N : array
            Array of load up hours tested. Goes from 1 to hour before first shed.
        """
        return self.system.lsSizedPoints(self.building)

    def getHWMagnitude(self):
        """
        Returns the total daily hot water for the building the HPWH is being sized for.
        
        Returns
        -------
        magnitude : Float
            The total daily hot water for the building the HPWH is being sized for.
        """
        return self.building.magnitude