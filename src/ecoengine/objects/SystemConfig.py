from ecoengine.constants.Constants import *
from .Building import Building
from .SimulationRun import SimulationRun
from .PrefMapTracker import PrefMapTracker
import numpy as np
from scipy.stats import norm #lognorm
from .systemConfigUtils import *
from plotly.offline import plot
from plotly.graph_objs import Figure, Scatter

class SystemConfig:
    def __init__(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building : Building = None,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, aquaFractLoadUp = None, 
                 aquaFractShed = None, loadUpT_F = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, 
                 PCap_kBTUhr = None, ignoreShortCycleEr = False):
        # check inputs. Schedule not checked because it is checked elsewhere
        self._checkInputs(storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, doLoadShift, loadShiftPercent)
        self.doLoadShift = doLoadShift
        self.storageT_F = storageT_F
        self.defrostFactor = defrostFactor
        self.percentUseable = percentUseable
        self.compRuntime_hr = compRuntime_hr
        self.aquaFract = aquaFract
        self.loadUpHours = None
        self.ignoreShortCycleEr = ignoreShortCycleEr

        if doLoadShift:
            self._setLoadShift(loadShiftSchedule, loadUpHours, aquaFract, aquaFractLoadUp, aquaFractShed, storageT_F, loadUpT_F, loadShiftPercent)
        
        else:
            self.loadShiftSchedule = [1] * 24
            self.fract_total_vol = 1 # fraction of total volume for for load shifting, or 1 if no load shifting

        #Check if need to increase sizing to meet lower runtimes for load shift
        self.maxDayRun_hr = min(self.compRuntime_hr, sum(self.loadShiftSchedule))

        #size system
        if not PVol_G_atStorageT is None:
            if not (isinstance(PVol_G_atStorageT, int) or isinstance(PVol_G_atStorageT, float)) or PVol_G_atStorageT <= 0: 
                raise Exception('Invalid input given for Primary Storage Volume, it must be a number greater than zero.')
            if not (isinstance(PCap_kBTUhr, int) or isinstance(PCap_kBTUhr, float)) or PCap_kBTUhr <= 0:
                # if systemModel and numHeatPumps are defined we do not nessesarily need PCap_kBTUhr
                if systemModel is None or numHeatPumps is None:
                    raise Exception('Invalid input given for Primary Output Capacity, must be a number greater than zero.')
            self.PVol_G_atStorageT = PVol_G_atStorageT
            self.PCap_kBTUhr = PCap_kBTUhr
        else: 
            #size system based off of building
            self.sizeSystem(building)
            if self.doLoadShift:
                self.PConvertedLoadUPV_G_atStorageT = convertVolume(self.PVol_G_atStorageT, self.storageT_F, building.incomingT_F, self.loadUpT_F)
                self.adjustedPConvertedLoadUPV_G_atStorageT = np.ceil(self.PConvertedLoadUPV_G_atStorageT * self.percentUseable)
                self.Vtrig_loadUp = self.PConvertedLoadUPV_G_atStorageT * (1 - self.aquaFractLoadUp)

        self.adjustedPVol_G_atStorageT = np.ceil(self.PVol_G_atStorageT * self.percentUseable)
        self.Vtrig_normal = self.PVol_G_atStorageT * (1 - self.aquaFract)
        if self.doLoadShift:
            self.Vtrig_shed = self.PVol_G_atStorageT * (1 - self.aquaFractShed)
        if numHeatPumps is None and not systemModel is None and not building is None and not building.getClimateZone() is None:
            # size number of heatpumps based on the coldest day
            self.perfMap = PrefMapTracker(self.PCap_kBTUhr, modelName = systemModel, numHeatPumps = numHeatPumps, kBTUhr = True,
                                          designOAT_F=building.getLowestOAT(), designIncomingT_F=building.getLowestIncomingT_F(),
                                          designOutT_F=self.storageT_F) 
        else:
            self.perfMap = PrefMapTracker(self.PCap_kBTUhr, modelName = systemModel, numHeatPumps = numHeatPumps, kBTUhr = True)

    def _checkInputs(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, doLoadShift, loadShiftPercent):
        if not (isinstance(storageT_F, int) or isinstance(storageT_F, float)) or not checkLiqudWater(storageT_F): 
            raise Exception('Invalid input given for Storage temp, it must be between 32 and 212F.')
        if not (isinstance(defrostFactor, int) or isinstance(defrostFactor, float)) or defrostFactor < 0 or defrostFactor > 1:
            raise Exception("Invalid input given for Defrost Factor, must be a number between 0 and 1.")
        if not (isinstance(percentUseable, int) or isinstance(percentUseable, float)) or percentUseable > 1 or percentUseable < 0:
            raise Exception("Invalid input given for percentUseable, must be a number between 0 and 1.")
        if not isinstance(compRuntime_hr, int) or compRuntime_hr <= 0 or compRuntime_hr > 24:
            raise Exception("Invalid input given for compRuntime_hr, must be an integer between 0 and 24.")
        if not (isinstance(aquaFract, int) or isinstance(aquaFract, float)) or aquaFract > 1 or aquaFract <= 0:
            raise Exception("Invalid input given for aquaFract must, be a number between 0 and 1.")
        if not isinstance(doLoadShift, bool):
            raise Exception("Invalid input given for doLoadShift, must be a boolean.")
        if doLoadShift and (not (isinstance(loadShiftPercent, int) or isinstance(loadShiftPercent, float)) or loadShiftPercent > 1 or loadShiftPercent < 0):
            raise Exception("Invalid input given for loadShiftPercent, must be a number between 0 and 1.")

    def setCapacity(self, PCap_kBTUhr = None, oat = None, incomingWater_T = None):
        if not PCap_kBTUhr is None:
            self.PCap_kBTUhr = PCap_kBTUhr
            self.PCap_input_kBTUhr = self.PCap_kBTUhr / 2.5 # Assume COP of 2.5
        elif not (oat is None or incomingWater_T is None or self.perfMap is None):
            self.PCap_kBTUhr, self.PCap_input_kBTUhr = self.perfMap.getCapacity(oat, incomingWater_T, self.storageT_F)
        else:
           raise Exception("No capacity given or preformance map has not been set.")
        
    def setLoadUPVolumeAndTrigger(self, incomingWater_T):
        # if not doing load shift, this is not applicable
        if self.doLoadShift:
            self.PConvertedLoadUPV_G_atStorageT = convertVolume(self.PVol_G_atStorageT, self.storageT_F, incomingWater_T, self.loadUpT_F)
            self.Vtrig_loadUp = self.PConvertedLoadUPV_G_atStorageT * (1 - self.aquaFractLoadUp)
            self.adjustedPConvertedLoadUPV_G_atStorageT = np.ceil(self.PConvertedLoadUPV_G_atStorageT * self.percentUseable)

    def resetToDefaultCapacity(self):
        self.PCap_kBTUhr = self.perfMap.getDefaultCapacity()

    def getOutputCapacity(self, kW = False):
        if kW:
            return self.PCap_kBTUhr/W_TO_BTUHR
        return self.PCap_kBTUhr
    
    def getInputCapacity(self, kW = False):
        if hasattr(self, 'PCap_input_kBTUhr'):
            if kW:
                return self.PCap_input_kBTUhr / W_TO_BTUHR
            return self.PCap_input_kBTUhr
        
        # else assume COP of 2.5
        if kW:
            return (self.PCap_kBTUhr / 2.5) / W_TO_BTUHR
        return self.PCap_kBTUhr / 2.5

    def setDoLoadShift(self, doLoadShift):
        if not isinstance(doLoadShift, bool):
            raise Exception("Invalid input given for doLoadShift, must be a boolean.")

        self.doLoadShift = doLoadShift

    def sizeSystem(self, building : Building):
        """
        Resizes the system with a new building.
        Also used for resizing the system after it has changed its loadshift settings using the original building the system was sized for

        Parameters
        ----------
        building : Building
            The building to size with
        """
        if not isinstance(building, Building):
                raise Exception("Error: Building is not valid.")
        self.PVol_G_atStorageT, self.effSwingFract = self.sizePrimaryTankVolume(self.maxDayRun_hr, self.loadUpHours, building, lsFractTotalVol = self.fract_total_vol)
        self.PCap_kBTUhr = self._primaryHeatHrs2kBTUHR(self.maxDayRun_hr, self.loadUpHours, building, 
            effSwingVolFract = self.effSwingFract, primaryCurve = False, lsFractTotalVol = self.fract_total_vol)[0]
        
    def getSizingResults(self):
        """
        Returns the minimum primary volume and heating capacity sizing results. Implimented seperatly in Temp Maintenence systems.

        Returns
        -------
        list
            self.PVol_G_atStorageT, self.PCap_kBTUhr
        """
        return [self.PVol_G_atStorageT, self.PCap_kBTUhr]
    
    def getInitializedSimulation(self, building : Building, initPV=None, initST=None, minuteIntervals = 1, nDays = 3):
        """
        Returns initialized arrays needed for nDay simulation

        Parameters
        ----------
        building : Building
            The building for the simulation
        initPV : float
            the initial primary tank volume at the start of the simulation
        initST : float
            Not used in this instance of the function
        minuteIntervals : int
            the number of minutes per time interval for the simulation
        nDays : int
            the number of days that will be simulated 

        Returns
        -------
        a SimulationRun object with all necessary components for running the simulation
        """
        
        loadShapeN = building.loadshape
        if self.doLoadShift and nDays < 365: #Only for non-annual simulations
            loadShapeN = building.avgLoadshape
        
        # Get the generation rate from the primary capacity
        hwGenRate = None
        if self.PCap_kBTUhr is None:
            if building.climateZone is None:
                raise Exception("Cannot run a simulation of this kind without either a climate zone or a default output capacity")
        else:
            hwGenRate = 1000 * self.PCap_kBTUhr / rhoCp / (building.supplyT_F - building.incomingT_F) \
                * self.defrostFactor
        loadshiftSched = np.tile(self.loadShiftSchedule, nDays) # TODO can we get rid of it?
        
        # Define the use of DHW with the normalized load shape
        hwDemand = building.magnitude * loadShapeN
        if (len(hwDemand) == 24):
            hwDemand = np.tile(hwDemand, nDays)
        if nDays < 365:
            hwDemand = hwDemand * self.fract_total_vol
        elif nDays == 365:
            hwDemand = hwDemand
        else:
            raise Exception("Invalid input given for number of days. Must be <= 365.")

        # Init the "simulation"
        V0_normal = self.adjustedPVol_G_atStorageT
        
        # set load shift schedule for the simulation
        LS_sched = ['N'] * 24
        if self.doLoadShift:
            LS_sched = ['S' if x == 0 else 'N' for x in self.loadShiftSchedule]
            #set load up hours pre-shed 1
            shedHours = [i for i in range(len(self.loadShiftSchedule)) if self.loadShiftSchedule[i] == 0] 
            LS_sched = ['L' if shedHours[0] - self.loadUpHours <= i <= shedHours[0] - 1 else LS_sched[i] for i, x in enumerate(LS_sched)]
            #check if there are two sheds, if so set all hours inbetween to load up
            try:
                secondShed = [[shedHours[i-1], shedHours[i]] for i in range(1, len(shedHours)) if shedHours[i] - shedHours[i-1] > 1][0]
                LS_sched = ['L' if secondShed[0] < i <= secondShed[1] - 1 else LS_sched[i] for i, x in enumerate(LS_sched)]
            except IndexError:
                pass

        if minuteIntervals == 1:
            # To per minute from per hour
            if not hwGenRate is None:
                hwGenRate = hwGenRate / 60
            hwDemand = np.array(hrToMinList(hwDemand)) / 60
            loadshiftSched = np.array(hrToMinList(loadshiftSched))
        elif minuteIntervals == 15:
            # To per 15 minute from per hour
            if not hwGenRate is None:
                hwGenRate = hwGenRate / 4
            hwDemand = np.array(hrTo15MinList(hwDemand)) / 4
            loadshiftSched = np.array(hrTo15MinList(loadshiftSched))
        elif minuteIntervals != 60:
            raise Exception("Invalid input given for granularity. Must be 1, 15, or 60.")

        pV = [0] * (len(hwDemand) - 1) + [V0_normal]

        if initPV:
            pV[-1] = initPV

        return SimulationRun(hwGenRate, hwDemand, V0_normal, pV, building, loadshiftSched, minuteIntervals, self.doLoadShift, LS_sched)
    
    def runOneSystemStep(self, simRun : SimulationRun, i, minuteIntervals = 1, oat = None):
        incomingWater_T = simRun.getIncomingWaterT(i)
        if i > 0 and incomingWater_T != simRun.getIncomingWaterT(i-1):
            self.setLoadUPVolumeAndTrigger(incomingWater_T) #adjust load up volume to reflect usefull energy
        if not (oat is None or self.perfMap is None):
            # set primary system capacity based on outdoor ait temp and incoming water temp 
            self.setCapacity(oat = oat, incomingWater_T = incomingWater_T)
            simRun.addHWGen((1000 * self.PCap_kBTUhr / rhoCp / (simRun.building.supplyT_F - incomingWater_T) \
               * self.defrostFactor)/(60/minuteIntervals))
        
        # Get exiting and generating water volumes at storage temp
        mixedDHW = convertVolume(simRun.hwDemand[i], self.storageT_F, incomingWater_T, simRun.building.supplyT_F)
        mixedGHW = convertVolume(simRun.hwGenRate, self.storageT_F, incomingWater_T, simRun.building.supplyT_F)

        simRun.pheating, simRun.pV[i], simRun.pGen[i], simRun.pRun[i] = self.runOnePrimaryStep(pheating = simRun.pheating,
                                                                                            Vcurr = simRun.pV[i-1], 
                                                                                            hw_out = mixedDHW, 
                                                                                            hw_in = mixedGHW, 
                                                                                            mode = simRun.getLoadShiftMode(i),
                                                                                            modeChanged = (simRun.getLoadShiftMode(i) != simRun.getLoadShiftMode(i-1)),
                                                                                            minuteIntervals = minuteIntervals) 
    
    def _setLoadShift(self, loadShiftSchedule, loadUpHours, aquaFract, aquaFractLoadUp, aquaFractShed, storageT_F, loadUpT_F, loadShiftPercent=1):
        """
        Sets the load shifting schedule from input loadShiftSchedule

        Parameters
        ----------
        loadShiftSchedule : array_like
            List or array of 0's, 1's used for load shifting, 0 indicates system is off. 
        loadUpHours : float
            Number of hours spent loading up for first shed.
        aquaFract: float
            The fraction of the total height of the primary hot water tanks at which the Aquastat is located.
        aquaFractLoadUp : float
            The fraction of the total height of the primary hot water tanks at which the load up aquastat is located.
        aquaFractShed : float
            The fraction of the total height of the primary hot water tanks at which the shed aquastat is located.
        storageT_F : float 
            The hot water storage temperature. [°F]
        loadUpT_F : float
            The hot water storage temperature between the normal and load up aquastat. [°F]
        loadShiftPercent : float
            Percentile of days which need to be covered by load shifting

        """
        # Check
        if not(isinstance(loadShiftSchedule, list)):
            raise Exception("Invalid input given for schedule, must be an array of length 24.")
        if len(loadShiftSchedule) != 24: 
            raise Exception("Load shift is not of length 24 but instead has length of "+str(len(loadShiftSchedule))+".")
        if not all(i in [0,1] for i in loadShiftSchedule):
            raise Exception("Loadshift schedule must be comprised of 0s, 1s, and 2s for shed, normal, and load up operation.")
        if sum(loadShiftSchedule) == 0 :
            raise Exception("When using Load shift the HPWH's must run for at least 1 hour each day.")
        if loadShiftPercent < 0.25 :
            raise Exception("Load shift only available for above 25 percent of days.")
        if loadShiftPercent > 1 :
            raise Exception("Cannot load shift for more than 100 percent of days")
        if not (isinstance(aquaFractLoadUp, int) or isinstance(aquaFractLoadUp, float)) or aquaFractLoadUp > aquaFract or aquaFractLoadUp <= 0:
            raise Exception("Invalid input given for load up aquastat fraction, must be a number between 0 and normal aquastat fraction.")
        if not (isinstance(aquaFractShed, int) or isinstance(aquaFractShed, float)) or aquaFractShed >= 1 or aquaFractShed < aquaFract:
            raise Exception("Invalid input given for shed aquastat fraction, must be a number between normal aquastat fraction and 1.")
        if not (isinstance(loadUpT_F, int) or isinstance(loadUpT_F, float)) or loadUpT_F < storageT_F or not checkLiqudWater(loadUpT_F):
            raise Exception("Invalid input given for load up storage temp, it must be a number between normal storage temp and 212F.")
        if not (isinstance(loadUpHours, int)) or loadUpHours > loadShiftSchedule.index(0): #make sure there are not more load up hours than nhours before first shed
            raise Exception("Invalid input given for load up hours, must be an integer less than or equal to hours in day before first shed period.") 

        self.loadShiftSchedule = loadShiftSchedule
        self.loadUpHours = loadUpHours
        self.aquaFractLoadUp = aquaFractLoadUp
        self.aquaFractShed = aquaFractShed
        self.loadUpT_F = loadUpT_F
        
        # adjust for cdf_shift
        if loadShiftPercent == 1: # meaing 100% of days covered by load shift
            self.fract_total_vol = 1
            
        else:
            # calculate fraction total hot water required to meet load shift days
            fract = norm_mean + norm_std * norm.ppf(loadShiftPercent) #TODO norm_mean and std are currently from multi-family, need other types eventually. For now, loadshifting will only be available for multi-family
            self.fract_total_vol = fract if fract <= 1. else 1.
        
        self.loadShiftPercent = loadShiftPercent
        self.doLoadShift = True

    def _primaryHeatHrs2kBTUHR(self, heathours, loadUpHours, building : Building, primaryCurve = False, effSwingVolFract=1, lsFractTotalVol = 1):
        """
        Converts from hours of heating in a day to heating capacity. If loadshifting compares this method to capacity needed to load up
        and takes maximum.

        Implimented seperatly in Swing Tank systems

        Parameters
        ----------
        heathours : float or numpy.ndarray
            The number of hours primary heating equipment can run.
        loadUpHours : float
            Number of hours spent loading up for first shed.
        building : Building
            The building the system being sized for
        primaryCurve : Bool
            Indicates that function is being called to generate the priamry
            sizing curve. This overrides LS sizing and sizes with "normal"
            sizing (default = False)
        effSwingVolFract : float or numpy.ndarray
            The fractional adjustment to the total hot water load for the
            primary system. Only used in a swing tank system.

        Returns
        -------
        heatCap
            The heating capacity in [btu/hr].
        genRate
            The generation rate in [gal/hr] when the heat pump is on. 
            If loadshifting this is the maximum between normal calculation
            and what is necessary to complete first load up.
        """
        checkHeatHours(heathours)
        genRate = building.magnitude * effSwingVolFract / heathours
        
        if self.doLoadShift and not primaryCurve:
            Vshift, VconsumedLU = self._calcPrelimVol(loadUpHours, building.avgLoadshape, building, lsFractTotalVol)
            Vload = Vshift * (self.aquaFract - self.aquaFractLoadUp) / (self.aquaFractShed - self.aquaFractLoadUp) #volume in 'load up' portion of tank
            LUgenRate = (Vload + VconsumedLU) / loadUpHours #rate needed to load up tank and offset use during load up period
            
            #compare with original genRate
            genRate = max(LUgenRate, genRate)
            
        heatCap = genRate * rhoCp * \
            (building.supplyT_F - building.incomingT_F) / self.defrostFactor / 1000
       
        return heatCap, genRate
    

    def sizePrimaryTankVolume(self, heatHrs, loadUpHours, building : Building, primaryCurve = False, lsFractTotalVol = 1.):
        """
        Calculates the primary storage using the Ecotope sizing methodology. Function is also used
        to generate primary sizing curve, which creates a curve with no load shifting and points
        with varying numbers of load up hours.

        Parameters
        ----------
        heatHrs : float
            The number of hours primary heating equipment can run in a day.
        loadUpHours : float
            Number of hours spent loading up for first shed.
        building : Building
            the building object the primary tank is being sized for.
        primaryCurve : Bool
            Indicates that function is being called to generate the priamry
            sizing curve. This overrides LS sizing and sizes with "normal"
            sizing (default = False)
        
        Raises
        ------
        ValueError: aquastat fraction is too low.
        ValueError: The minimum aquastat fraction is greater than 1.

        Returns
        -------
        totalVolMax : float
            The total storage volume in gallons adjusted to the storage tempreature
        effMixFract : float
            The fractional adjustment to the total hot water load for the
            primary system. Only used in a swing tank system.
        
        """
       

        if heatHrs <= 0 or heatHrs > 24:
            raise Exception("Heat hours is not within 1 - 24 hours")
        # Fraction used for adjusting swing tank volume.
        effMixFract = 1.

        # Running vol
        runningVol_G, effMixFract = self._calcRunningVol(heatHrs, np.ones(24), building.loadshape, building, effMixFract)
        totalVolAtStorage = self._getTotalVolAtStorage(runningVol_G, building.incomingT_F, building.supplyT_F)
        totalVolAtStorage *=  thermalStorageSF

        if self.doLoadShift and not primaryCurve:
            LSrunningVol_G, LSeffMixFract = self._calcRunningVolLS(loadUpHours, building.avgLoadshape, building, effMixFract, lsFractTotalVol = lsFractTotalVol)

            # Get total volume from max of primary method or load shift method
            if LSrunningVol_G > runningVol_G:
                runningVol_G = LSrunningVol_G
                effMixFract = LSeffMixFract
                
                #get the average tank volume
                totalVolAtStorage_ls = convertVolume(runningVol_G, self.storageT_F, building.incomingT_F, building.supplyT_F) / (self.aquaFractShed - self.aquaFractLoadUp)
                
                #multiply computed storage by efficiency safety factor (currently set to 1)
                totalVolAtStorage_ls *=  thermalStorageSF 

                if totalVolAtStorage_ls > totalVolAtStorage:
                    totalVolAtStorage = totalVolAtStorage_ls

            # Check the Cycling Volume 
            LUcyclingVol_G = totalVolAtStorage * (self.aquaFractLoadUp - (1 - self.percentUseable))
            minRunVol_G = pCompMinimumRunTime * (building.magnitude / heatHrs) # (generation rate - no usage) #REMOVED EFFMIXFRACT
            
            if minRunVol_G > LUcyclingVol_G:
                min_AF = minRunVol_G / totalVolAtStorage + (1 - self.percentUseable)
                if min_AF >= 1:
                    raise Exception("The minimum load up aquastat fraction is greater than 1. This is due to the storage efficency and/or the maximum run hours in the day may be too low. Try increasing these values, we reccomend 0.8 and 16 hours for these variables respectively." )                
                # raise Exception("The load up aquastat fraction is too low in the storge system recommend increasing the maximum run hours in the day or increasing to a minimum of: " + str(round(min_AF,3)) + " or increase your drawdown factor.")


        cyclingVol_G = totalVolAtStorage * (self.aquaFract - (1 - self.percentUseable))
        minRunVol_G = pCompMinimumRunTime * (building.magnitude / heatHrs) # (generation rate - no usage)  #REMOVED EFFMIXFRACT

        if minRunVol_G > cyclingVol_G:
            min_AF = minRunVol_G / totalVolAtStorage + (1 - self.percentUseable)
            if min_AF < 1 and not self.ignoreShortCycleEr:
                raise ValueError("01", "The aquastat fraction is too low in the storge system recommend increasing the maximum run hours in the day or increasing to a minimum of: ", round(min_AF,3))
            elif min_AF >= 1:
                raise ValueError("02", "The minimum aquastat fraction is greater than 1. This is due to the storage efficency and/or the maximum run hours in the day may be too low. Try increasing these values, we reccomend 0.8 and 16 hours for these variables respectively." )

        
        # Return the temperature adjusted total volume ########################
        
        return totalVolAtStorage, effMixFract
    
    def _calcRunningVol(self, heatHrs, onOffArr, loadshape, building : Building, effMixFract = 0):
        """
        Function to find the running volume for the hot water storage tank, which
        is needed for calculating the total volume for primary sizing and in the event of load shift sizing
        represents the entire volume.

        Implimented seperatly for Swing Tank systems

        Parameters
        ----------
        heatHrs : float
            The number of hours primary heating equipment can run in a day.
        onOffArr : ndarray
            array of 1/0's where 1's allow heat pump to run and 0's dissallow. of length 24.
        loadshape : ndarray
            normalized array of length 24 representing the daily loadshape for this calculation.
        building : Building
            The building the system is being sized for
        effMixFract: Int
            unused value in this instance of the function. Used in Swing Tank implimentation

        Raises
        ------
        Exception: Error if oversizing system.

        Returns
        -------
        runV_G : float
            The running volume in gallons at supply temp.
        effMixFract: int
            Needed for swing tank implementation.
        """          
        genRate = np.tile(onOffArr,2) / heatHrs #hourly
        diffN = genRate - np.tile(loadshape,2) #hourly
        diffInd = getPeakIndices(diffN[0:24]) #Days repeat so just get first day!
        diffN *= building.magnitude
        
        # Get the running volume ##############################################
        if len(diffInd) == 0:
            raise Exception("ERROR ID 03","The heating rate is greater than the peak volume the system is oversized! Try increasing the hours the heat pump runs in a day",)
        runV_G = 0
        for peakInd in diffInd:
            #Get the rest of the day from the start of the peak
            diffCum = np.cumsum(diffN[peakInd:])  #hourly
            runV_G = max(runV_G, -min(diffCum[diffCum<0.])) #Minimum value less than 0 or 0.
        return runV_G, effMixFract
    
    def _calcRunningVolLS(self, loadUpHours, loadshape, building : Building, effMixFract = 1, lsFractTotalVol = 1):
        """
        Function to calculate the running volume if load shifting. Using the max generation rate between normal sizing
        and preliminary volume, the deficit between generation and hot water use is then added to the preliminary volume.

        Implemented separately for swing tank system.

        Parameters
        ------   
        loadUpHours : float
            Number of hours of scheduled load up before first shed. If sizing, this is set by user. If creating sizing
            plot, number may vary.  
        loadshape : ndarray
            normalized array of length 24 representing the daily loadshape for this calculation.
        building : Building
            The building the system is being sized for
        effMixFract : float
            Only used in swing tank implementation.

        Returns
        ------
        LSrunV_G : float
            Volume needed between primary shed aquastat and load up aquastat at supply temp.
        effMixFract : float
            Used for swing tank implementation.
        """
        Vshift = self._calcPrelimVol(loadUpHours, loadshape, building, lsFractTotalVol = lsFractTotalVol)[0] #volume to make it through first shed
        
        genRateON = self._primaryHeatHrs2kBTUHR(self.maxDayRun_hr, loadUpHours, building, effSwingVolFract = effMixFract, primaryCurve = False, lsFractTotalVol = lsFractTotalVol)[1] #max generation rate from both methods
        genRate = [genRateON if x != 0 else 0 for x in self.loadShiftSchedule] #set generation rate during shed to 0
        genRate = np.tile(genRate, 2)
        
        diffN = genRate - np.tile(loadshape,2) * building.magnitude
        
        #get first index after shed
        shedEnd = [i for i,x in enumerate(genRate[1:],1) if x > genRate[i-1]][0] #start at beginning of first shed, fully loaded up equivalent to starting at the end of shed completely "empty"
        diffCum = np.cumsum(diffN[shedEnd:]) 
        LSrunV_G = -min(diffCum[diffCum<0.], default = 0) * lsFractTotalVol #numbers less than 0 are a hot water deficit, find the biggest deficit. if no deficit then 0.
        # TODO do we want to multiply LSrunV_G by lsFractTotalVol? that isn't really affected by cdf

        #add running volume to preliminary shifted volume
        LSrunV_G += Vshift
        
        return LSrunV_G, effMixFract 

    def _getTotalVolAtStorage(self, runningVol_G, incomingT_F, supplyT_F):
        """
        Calculates the maximum primary storage using the Ecotope sizing methodology. Swing Tanks implement sperately.

        Parameters
        ----------
        runningVol_G : float
            The running volume in gallons
        incomingT_F : float
            Incoming temp (in Fahrenhiet) of city water
        supplyT_F : float
            Supply temp (in Fahrenhiet) of water distributed to those in the building

        Returns
        -------
        totalVolMax : float
            The total storage volume in gallons adjusted to the storage tempreature.
        
        """
        
        return convertVolume(runningVol_G, self.storageT_F, incomingT_F, supplyT_F) / (1 - self.aquaFract)
    
    def primaryCurve(self, building : Building):
        """
        Sizes the primary system curve. Will catch the point at which the aquatstat
        fraction is too small for system and cuts the return arrays to match cutoff point.

        Parameters
        ----------
        building : Building
            the building this primary system curve is being sized for

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
        maxHeatHours = 1/(max(building.loadshape))*1.001   
        arr1 = np.arange(24, self.maxDayRun_hr, delta) #TODO why are we going all the way to 24 hours ???
        recIndex = len(arr1)
        heatHours = np.concatenate((arr1, np.arange(self.maxDayRun_hr, maxHeatHours, delta)))
        
        volN = np.zeros(len(heatHours))
        effMixFract = np.ones(len(heatHours))
        for i in range(0,len(heatHours)):
            try:
                volN[i], effMixFract[i] = self.sizePrimaryTankVolume(heatHours[i], self.loadUpHours, building, primaryCurve = True, lsFractTotalVol = self.fract_total_vol)
                
            except ValueError:
                break
        # Cut to the point the aquastat fraction was too small
        volN        = volN[:i]
        heatHours   = heatHours[:i]
        effMixFract = effMixFract[:i]

        return [volN, self._primaryHeatHrs2kBTUHR(heatHours, self.loadUpHours, building, 
            effSwingVolFract = effMixFract, primaryCurve = True, lsFractTotalVol = self.fract_total_vol)[0], heatHours, recIndex]

    def lsSizedPoints(self, building : Building):
        """
        Creates points for sizing curve plot based on number of hours in first load up period. If "regular" sizing 
        drives algorithmn, regular sizing will be used. This prevents user from oversizing system by putting 
        ill-informed number of load up hours.

        Parameters
        ----------
        building : Building
            The building the system being sized for

        Returns
        lsSizingCombos : array
            Array of volume and capacity combinations sized based on the number of load up hours.
        """
        if not self.doLoadShift:
            raise Exception("lsSizedPoints() only applicable to systems with load shifting.")
        
        volN = []
        capN = []
        effMixN = []
        N = []

        #load up hours to loop through
        i = 100
        # try:
        while i >= 25: #arbitrary stopping point, anything more than this will not result in different sizing
            #size the primary system based on the number of load up hours
            fract = norm_mean + norm_std * norm.ppf(i/100) #TODO norm_mean and std are currently from multi-family, need other types eventually. For now, loadshifting will only be available for multi-family
            fract = fract if fract <= 1. else 1.
            volN_i, effMixN_i = self.sizePrimaryTankVolume(heatHrs = self.maxDayRun_hr, loadUpHours = self.loadUpHours, building = building, primaryCurve = False, lsFractTotalVol = fract)
            volN.append(volN_i)
            effMixN.append(effMixN_i)
            capN.append(self._primaryHeatHrs2kBTUHR(self.maxDayRun_hr, self.loadUpHours, building, effSwingVolFract = effMixN_i, primaryCurve = False, lsFractTotalVol = fract)[0])
            N.append(i)
            i -= 1

        # except Exception:
    
        return [volN, capN, N, int(np.ceil((self.loadShiftPercent * 100)-25))]
    

    def getPrimaryCurveAndSlider(self, x, y, startind, y2 = None, returnAsDiv = True, lsPoints = None): #getPrimaryCurveAndSlider
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
        
        Returns
        --------
        plotdiv : a plotly div of the graph
        
        
        """
        fig = createSizingCurvePlot(x, y, startind, loadshifting = self.doLoadShift)
    
        # Create and add sliderbar steps
        steps = []
        for i in range(1,len(fig.data)):
        
            labelText = "Storage: "+("<b id='point_y'>" if self.doLoadShift else "<b id='point_x'>") + str(float(x[i-1] if not self.doLoadShift else y[i-1])) + "</b> Gal, Capacity: "+ \
                ("<b>" if self.doLoadShift else "<b id='point_y'>") + \
                str(round(y[i-1],1) if not self.doLoadShift else round(self.PCap_kBTUhr,2)) + "</b> kBTU/hr" 
            if y2 is not None:
                if self.doLoadShift:
                    labelText += ", Percent Load Shift Days Covered: <b id='point_x'>" + str(float(y2[i-1])) + "</b> %"
                else:
                    labelText += ", Compressor Runtime: <b>" + str(float(y2[i-1])) + "</b> hr" 
        
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
                'prefix': '<b>Primary System Size</b>, ',
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

    
    def runOnePrimaryStep(self, pheating, Vcurr, hw_out, hw_in, mode, modeChanged, minuteIntervals = 1):
        """
        Runs one step on the primary system. This changes the volume of the primary system
        by assuming there is hot water removed at a volume of hw_out and hot water
        generated or added at a volume of hw_in. This is assuming the system is perfectly
        stratified and all of the hot water above the cold temperature is at the storage temperature.

        Parameters
        ----------
        pheating : boolean
            indicates whether system is heating at the beginning of this step
        Vfull : float
            The maximum volume of the primary system at the storage temperature
        Vtrig : float
            The remaining volume of the primary storage volume when heating is
            triggered, note this equals V0*(1 - aquaFract) 
        Vcurr : float
            The primary volume at the beginning of the interval.
        hw_out : float
            The volume of DHW removed from the primary system at storage temp, assumed that
            100% of what of what is removed is replaced
        hw_in : float
            The volume of hot water that could be generated in a time step at storage temp if the primary tank was running the entire time
        Vtrig_previous : float
            Trigger from last time step to see if we missed any heating (may have changed if doing load shifting)

        Returns
        -------
        pheating : boolean
            Boolean indicating if the primary system is heating at the end of this step in the simulation 
        Vnew : float
            The new primary volume at the timestep.
        hw_generated : float
            The volume of hot water generated during the time step.
        time_ran : 
            The amount of time the primary tank ran

        """
        Vtrig = self.Vtrig_normal
        if mode == 'S':
            Vtrig = self.Vtrig_shed
        elif mode == 'L':
            Vtrig = self.Vtrig_loadUp

        if Vcurr > Vtrig and modeChanged:
            # ensure we stop heating if we start the interval above the aquastat after the aquastat changes
            pheating = False

        Vnew = Vcurr - hw_out
        time_ran = 0

        # figure out if we needed to start heating in the interval
        if pheating:
            time_ran = 1
        elif Vnew < Vtrig: # If should heat
            pheating = True
            if hw_out == 0:
                time_ran = 1
            else:    
                time_ran = min((Vtrig - Vnew)/hw_out, 1) # Volume below turn on / rate of draw gives time below tigger (aquastat)

        # calculate hw water generated and add to tank
        hw_generated = hw_in * time_ran
        Vnew_potential = Vnew + hw_generated

        # figure out if we need to stop heating in the interval if we are heating
        if pheating:
            if mode == 'S' and Vnew_potential > self.Vtrig_normal:
                # stop heating if hw has met the normal aquastat fraction during a shed period
                time_over = min((Vnew_potential - self.Vtrig_normal)/hw_in, 1) # Volume over trigger / hot water generation rate gives percent of interval it takes to generate that much water
                time_ran -= time_over
                pheating = False # Stop heating
            elif mode == 'N' and Vnew_potential > self.adjustedPVol_G_atStorageT: # If overflow
                time_over = min((Vnew_potential - self.adjustedPVol_G_atStorageT)/hw_in, 1) # Volume over trigger / hot water generation rate gives percent of interval it takes to generate that much water
                time_ran -= time_over
                pheating = False # Stop heating
            elif mode == 'L' and Vnew_potential > self.adjustedPConvertedLoadUPV_G_atStorageT: # If overflow
                time_over = min((Vnew_potential - self.adjustedPConvertedLoadUPV_G_atStorageT)/hw_in, 1) # Volume over trigger / hot water generation rate gives percent of interval it takes to generate that much water
                time_ran -= time_over
                pheating = False # Stop heating

        hw_generated = hw_in * time_ran
        Vnew += hw_generated
        
        if Vnew < 0:
           raise Exception("Primary storage ran out of Volume!")
        if time_ran < 0:
           raise Exception("Internal system error. time_ran was negative")

        return pheating, Vnew, hw_generated, time_ran * minuteIntervals
    
    def _calcPrelimVol(self, loadUpHours, loadshape, building : Building, lsFractTotalVol = 1):
        '''
        Function to calculate volume shifted during first shed period, which is used to calculated generation rate
        needed for load up.

        Parameters
        ----------
        loadUpHours : float
            Number of hours of scheduled load up before first shed. If sizing, this is set by user. If creating sizing
            plot, number may vary. 
        loadshape : ndarray
            normalized array of length 24 representing the daily loadshape for this calculation.
        building : Building
            The building object being sized for 

        Returns 
        ----------
        Vshift : float
            Volume at supply temp between normal and load up AQ fract needed to make it through first shed period.
        VconsumedLU : float
            Volume at supply temp consumed during first load up period.
        '''
        shedHours = [i for i in range(len(self.loadShiftSchedule)) if self.loadShiftSchedule[i] == 0] #get all scheduled shed hours
        firstShed = [x for i,x in enumerate(shedHours) if x == shedHours[0] + i] #get first shed
        Vshift = sum([loadshape[i]*building.magnitude for i in firstShed]) * lsFractTotalVol #calculate vol used during first shed multiplied by cdf
        VconsumedLU = sum(loadshape[firstShed[0] - loadUpHours : firstShed[0]]) * building.magnitude
        
        return Vshift, VconsumedLU
    
class Primary(SystemConfig):
    def __init__(self, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building,
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, aquaFractLoadUp = None, 
                 aquaFractShed = None, loadUpT_F = None, systemModel = None, numHeatPumps = None, PVol_G_atStorageT = None, PCap_kBTUhr = None, ignoreShortCycleEr = False):
        super().__init__(storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, building, doLoadShift, 
                loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, aquaFractShed, loadUpT_F, systemModel, 
                numHeatPumps, PVol_G_atStorageT, PCap_kBTUhr, ignoreShortCycleEr)


