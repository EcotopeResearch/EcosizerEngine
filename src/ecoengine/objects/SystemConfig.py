from ecoengine.constants.Constants import *
from .Building import Building
import numpy as np
from scipy.stats import norm #lognorm
from plotly.graph_objs import Figure, Scatter
from plotly.offline import plot
from .systemConfigUtils import roundList, mixVolume, hrToMinList, getPeakIndices, checkLiqudWater, checkHeatHours

class SystemConfig:
    def __init__(self, building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, 
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, aquaFractLoadUp = None, 
                 aquaFractShed = None, loadUpT_F = None):
        # check inputs. Schedule not checked because it is checked elsewhere
        self._checkInputs(building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, doLoadShift, loadShiftPercent)
        self.doLoadShift = doLoadShift
        self.building = building        
        self.storageT_F = storageT_F
        self.defrostFactor = defrostFactor
        self.percentUseable = percentUseable
        self.compRuntime_hr = compRuntime_hr
        self.aquaFract = aquaFract
        self.loadUpHours = None

        if doLoadShift and not loadShiftSchedule is None:
            self._setLoadShift(loadShiftSchedule, loadUpHours, aquaFract, aquaFractLoadUp, aquaFractShed, storageT_F, loadUpT_F, loadShiftPercent)
        
        else:
            self.loadShiftSchedule = [1] * 24
            self.fract_total_vol = 1 # fraction of total volume for for load shifting, or 1 if no load shifting

        #Check if need to increase sizing to meet lower runtimes for load shift
        self.maxDayRun_hr = min(self.compRuntime_hr, sum(self.loadShiftSchedule))

        #size system
        self.PVol_G_atStorageT, self.effSwingFract = self.sizePrimaryTankVolume(self.maxDayRun_hr, self.loadUpHours)
        self.PCap_kBTUhr = self._primaryHeatHrs2kBTUHR(heathours = self.maxDayRun_hr, loadUpHours = self.loadUpHours, effSwingVolFract = self.effSwingFract, primaryCurve = False)[0]

    def _checkInputs(self, building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, doLoadShift, loadShiftPercent):
        if not isinstance(building, Building):
            raise Exception("Error: Building is not valid.")
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
        if not (isinstance(loadShiftPercent, int) or isinstance(loadShiftPercent, float)) or loadShiftPercent > 1 or loadShiftPercent < 0:
            raise Exception("Invalid input given for loadShiftPercent, must be a number between 0 and 1.")
        if not isinstance(doLoadShift, bool):
            raise Exception("Invalid input given for doLoadShift, must be a boolean.")
              
    def getSizingResults(self):
        """
        Returns the minimum primary volume and heating capacity sizing results. Implimented seperatly in Temp Maintenence systems.

        Returns
        -------
        list
            self.PVol_G_atStorageT, self.PCap_kBTUhr
        """
        return [self.PVol_G_atStorageT, self.PCap_kBTUhr]

    def simulate(self, initPV=None, initST=None, Pcapacity=None, Pvolume=None):
        """
        Implimented seperatly for Swink Tank systems 
        Inputs
        ------
        initPV : float
            Primary volume at start of the simulation
        initST : float
            Primary Swing tank at start of the simulation. Not used in this instance of the function
        Pcapacity : float
            The primary heating capacity in kBTUhr to use for the simulation,
            default is the sized system
        Pvolume : float
            The primary storage volume in gallons to  to use for the simulation,
            default is the sized system
        
        Returns
        -------
        list [ pV, G_hw, D_hw, prun ]
        pV : list 
            Volume of HW in the tank with time at the strorage temperature.
        G_hw : list 
            The generation of HW with time at the supply temperature
        D_hw : list 
            The hot water demand with time at the tsupply temperature
        prun : list 
            The actual output in gallons of the HPWH with time
        """

        G_hw, D_hw, V0, Vtrig, pV, pheating = self._getInitialSimulationValues(Pcapacity, Pvolume)
       
        hw_outSwing = [0] * (len(G_hw))
        hw_outSwing[0] = D_hw[0]
        prun = [0] * (len(G_hw))

        if initPV:
            pV[0] = initPV

        #get mixed storage temp
        mixedStorT_F = self._mixStorageTemps(pV[0])[0]

        # Run the "simulation"
        for i in range(1, len(G_hw)):
            mixedDHW = mixVolume(D_hw[i], mixedStorT_F, self.building.incomingT_F, self.building.supplyT_F) 
            mixedGHW = mixVolume(G_hw[i], mixedStorT_F, self.building.incomingT_F, self.building.supplyT_F)
            pheating, pV[i], prun[i] = self.runOnePrimaryStep(pheating, V0, Vtrig[i], pV[i-1], mixedDHW, mixedGHW) 
            
        return [roundList(pV, 3),
                roundList(G_hw, 3),
                roundList(D_hw, 3),
                roundList(prun, 3)]

    def _getInitialSimulationValues(self, Pcapacity=None, Pvolume=None):
        """
        Returns initialized arrays needed for 3-day simulation

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
        list [ G_hw, D_hw, V0, V, run, pheating ]
        G_hw : list
            The generation of HW with time at the supply temperature
        D_hw : list
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
               * self.defrostFactor * np.tile(self.loadShiftSchedule, 3)

        
        # Define the use of DHW with the normalized load shape
        D_hw = self.building.magnitude * self.fract_total_vol * np.tile(loadShapeN, 3)

        # Init the "simulation"
        V0 = np.ceil(Pvolume * self.percentUseable) 
        
        Vtrig = np.tile(np.ceil(Pvolume * (1 - self.aquaFract)) + 1, 24) # To prevent negatives with any of that rounding math. TODO Nolan and I don't think we need this mysterious + 1
        
        if self.doLoadShift:
            
            Vtrig = [Pvolume * (1 - self.aquaFractShed) if x == 0 else Pvolume * (1 - self.aquaFract) for x in self.loadShiftSchedule]
            
            #set load up hours pre-shed 1
            shedHours = [i for i in range(len(self.loadShiftSchedule)) if self.loadShiftSchedule[i] == 0] 
            Vtrig = [Pvolume * (1 - self.aquaFractLoadUp) if shedHours[0] - self.loadUpHours <= i <= shedHours[0] - 1 else Vtrig[i] for i, x in enumerate(Vtrig)]
            
            #check if there are two sheds, if so set all hours inbetween to load up
            try:
                secondShed = [[shedHours[i-1], shedHours[i]] for i in range(1, len(shedHours)) if shedHours[i] - shedHours[i-1] > 1][0]
                Vtrig = [Pvolume * (1 - self.aquaFractLoadUp) if secondShed[0] <= i <= secondShed[1] - 1 else Vtrig[i] for i, x in enumerate(Vtrig)]
            
            except IndexError:
                pass
        
        # To per minute from per hour
        G_hw = np.array(hrToMinList(G_hw)) / 60
        D_hw = np.array(hrToMinList(D_hw)) / 60
        Vtrig = np.array(hrToMinList(np.tile(Vtrig, 3))) 

        pV = [V0] + [0] * (len(G_hw) - 1)

        pheating = False
    
        return G_hw, D_hw, V0, Vtrig, pV, pheating
    
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
        self.loadshift = np.array(loadShiftSchedule, dtype = float) # Coerce to numpy array of data type float
        
        # adjust for cdf_shift
        if loadShiftPercent == 1: # meaing 100% of days covered by load shift
            self.fract_total_vol = 1
            
        else:
            # calculate fraction total hot water required to meet load shift days
            fract = norm_mean + norm_std * norm.ppf(loadShiftPercent) #TODO norm_mean and std are currently from multi-family, need other types eventually. For now, loadshifting will only be available for multi-family
            self.fract_total_vol = fract if fract <= 1. else 1.
        
        self.doLoadShift = True

    def _primaryHeatHrs2kBTUHR(self, heathours, loadUpHours, primaryCurve = False, effSwingVolFract=1):
        """
        Converts from hours of heating in a day to heating capacity. If loadshifting compares this method to capacity needed to load up
        and takes maximum.

        Implimented seperatly in Swing Tank systems

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
        genRate
            The generation rate in [gal/hr] when the heat pump is on. 
            If loadshifting this is the maximum between normal calculation
            and what is necessary to complete first load up.
        """
        checkHeatHours(heathours)
        genRate = self.building.magnitude * effSwingVolFract / heathours
        
        if self.doLoadShift and not primaryCurve:
            Vshift, VconsumedLU = self._calcPrelimVol(loadUpHours) 
            Vload = Vshift * (self.aquaFract - self.aquaFractLoadUp) / (self.aquaFractShed - self.aquaFractLoadUp) #volume in 'load up' portion of tank
            LUgenRate = (Vload + VconsumedLU) / loadUpHours #rate needed to load up tank and offset use during load up period
            
            #compare with original genRate
            genRate = max(LUgenRate, genRate)
            
        heatCap = genRate * rhoCp * \
            (self.building.supplyT_F - self.building.incomingT_F) / self.defrostFactor / 1000
       
        return heatCap, genRate
    

    def sizePrimaryTankVolume(self, heatHrs, loadUpHours, primaryCurve = False):
        """
        Calculates the primary storage using the Ecotope sizing methodology. Function is also used
        to generate primary sizing curve, which creates a curve with no load shifting and points
        with varying numbers of load up hours.

        Parameters
        ----------
        heatHrs : float
            The number of hours primary heating equipment can run in a day.
        primaryCurve : 
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
        runningVol_G, effMixFract = self._calcRunningVol(heatHrs, np.ones(24), self.building.loadshape, effMixFract)
        totalVolAtStorage = self._getTotalVolAtStorage(runningVol_G)
        totalVolAtStorage *=  thermalStorageSF

        if self.doLoadShift and not primaryCurve:
            LSrunningVol_G, LSeffMixFract = self._calcRunningVolLS(loadUpHours, effMixFract)
            LSrunningVol_G *= self.fract_total_vol 

            # Get total volume from max of primary method or load shift method
            if LSrunningVol_G > runningVol_G:
                runningVol_G = LSrunningVol_G
                effMixFract = LSeffMixFract
                
                #get the average tank volume
                totalVolAtStorage = self._mixStorageTemps(runningVol_G)[1]
                
                #multiply computed storage by efficiency safety factor (currently set to 1)
                totalVolAtStorage *=  thermalStorageSF 
        
            # Check the Cycling Volume 
            LUcyclingVol_G = totalVolAtStorage * (self.aquaFractLoadUp - (1 - self.percentUseable))
            minRunVol_G = pCompMinimumRunTime * (self.building.magnitude / heatHrs) # (generation rate - no usage) #REMOVED EFFMIXFRACT
            
            if minRunVol_G > LUcyclingVol_G:
                min_AF = minRunVol_G / totalVolAtStorage + (1 - self.percentUseable)
                if min_AF < 1:
                    raise ValueError("01", "The load up aquastat fraction is too low in the storge system recommend increasing the maximum run hours in the day or increasing to a minimum of: ", round(min_AF,3))
                raise ValueError("02", "The minimum aquastat fraction is greater than 1. This is due to the storage efficency and/or the maximum run hours in the day may be too low. Try increasing these values, we reccomend 0.8 and 16 hours for these variables respectively." )

        cyclingVol_G = totalVolAtStorage * (self.aquaFract - (1 - self.percentUseable))
        minRunVol_G = pCompMinimumRunTime * (self.building.magnitude / heatHrs) # (generation rate - no usage)  #REMOVED EFFMIXFRACT

        if minRunVol_G > cyclingVol_G:
            min_AF = minRunVol_G / totalVolAtStorage + (1 - self.percentUseable)
            if min_AF < 1:
                raise ValueError("01", "The aquastat fraction is too low in the storge system recommend increasing the maximum run hours in the day or increasing to a minimum of: ", round(min_AF,3))
            raise ValueError("02", "The minimum aquastat fraction is greater than 1. This is due to the storage efficency and/or the maximum run hours in the day may be too low. Try increasing these values, we reccomend 0.8 and 16 hours for these variables respectively." )

        
        # Return the temperature adjusted total volume ########################
        
        return totalVolAtStorage, effMixFract
    
    def _calcRunningVol(self, heatHrs, onOffArr, loadshape, effMixFract = 0):
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
        diffN *= self.building.magnitude
        
        # Get the running volume ##############################################
        if len(diffInd) == 0:
            #TODO but what if it is undersized? Also can this ever be hit? users currently do not have power to change num hours from interface
            raise Exception("ERROR ID 03","The heating rate is greater than the peak volume the system is oversized! Try increasing the hours the heat pump runs in a day",)
        runV_G = 0
        for peakInd in diffInd:
            #Get the rest of the day from the start of the peak
            diffCum = np.cumsum(diffN[peakInd:])  #hourly
            runV_G = max(runV_G, -min(diffCum[diffCum<0.])) #Minimum value less than 0 or 0.
        return runV_G, effMixFract
    
    def _calcRunningVolLS(self, loadUpHours, effMixFract = 1):
        """
        Function to calculate the running volume if load shifting. Using the max generation rate between normal sizing
        and preliminary volume, the deficit between generation and hot water use is then added to the preliminary volume.

        Implemented separately for swing tank system.

        Parameters
        ------   
        loadUpHours : float
            Number of hours of scheduled load up before first shed. If sizing, this is set by user. If creating sizing
            plot, number may vary.   
        effMixFract : float
            Only used in swing tank implementation.

        Returns
        ------
        LSrunV_G : float
            Volume needed between primary shed aquastat and load up aquastat at supply temp.
        effMixFract : float
            Used for swing tank implementation.
        """
        Vshift = self._calcPrelimVol(loadUpHours)[0] #volume to make it through first shed
        
        genRateON = self._primaryHeatHrs2kBTUHR(self.maxDayRun_hr, loadUpHours, effSwingVolFract = effMixFract, primaryCurve = False)[1] #max generation rate from both methods
        genRate = [genRateON if x != 0 else 0 for x in self.loadShiftSchedule] #set generation rate during shed to 0
        
        diffN = np.tile(genRate, 2) - np.tile(self.building.avgLoadshape,2) * self.building.magnitude
        
        #get first index after shed
        shedEnd = [i for i,x in enumerate(genRate[1:],1) if x > genRate[i-1]][0] #start at beginning of first shed, fully loaded up equivalent to starting at the end of shed completely "empty"
        diffCum = np.cumsum(diffN[shedEnd:]) 
        LSrunV_G = -min(diffCum[diffCum<0.], default = 0) #numbers less than 0 are a hot water deficit, find the biggest deficit. if no deficit then 0.
        
        #add running volume to preliminary shifted volume
        LSrunV_G += Vshift
        
        return LSrunV_G, effMixFract 

    def _getTotalVolAtStorage(self, runningVol_G):
        """
        Calculates the maximum primary storage using the Ecotope sizing methodology. Swing Tanks implement sperately.

        Parameters
        ----------
        runningVol_G : float
            The running volume in gallons
        avgStorageT_F : float
            Average storage temperature. If not load shifting this is the storage temp. If load shifting this is the 
            average between load up and normal setpoint based on aquastat locations.

        Returns
        -------
        totalVolMax : float
            The total storage volume in gallons adjusted to the storage tempreature.
        
        """
        
        return mixVolume(runningVol_G, self.storageT_F, self.building.incomingT_F, self.building.supplyT_F) / (1 - self.aquaFract)
    
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
        arr1 = np.arange(24, self.maxDayRun_hr, delta) #TODO why are we going all the way to 24 hours ???
        recIndex = len(arr1)
        heatHours = np.concatenate((arr1, np.arange(self.maxDayRun_hr, maxHeatHours, delta)))
        
        volN = np.zeros(len(heatHours))
        effMixFract = np.ones(len(heatHours))
        for i in range(0,len(heatHours)):
            try:
                volN[i], effMixFract[i] = self.sizePrimaryTankVolume(heatHours[i], self.loadUpHours, primaryCurve = True)
                
            except ValueError:
                break
        # Cut to the point the aquastat fraction was too small
        volN        = volN[:i]
        heatHours   = heatHours[:i]
        effMixFract = effMixFract[:i]

        return [volN, self._primaryHeatHrs2kBTUHR(heatHours, self.loadUpHours, effSwingVolFract = effMixFract, primaryCurve = True)[0], heatHours, recIndex]

    def lsSizedPoints(self):
        """
        Creates points for sizing curve plot based on number of hours in first load up period. If "regular" sizing 
        drives algorithmn, regular sizing will be used. This prevents user from oversizing system by putting 
        ill-informed number of load up hours.

        Returns
        lsSizingCombos : array
            Array of volume and capacity combinations sized based on the number of load up hours.
        """
        
        volN = np.zeros(5)
        capN = np.zeros(5)
        effMixN = np.zeros(5)
        N = np.zeros(5)

        #load up hours to loop through
        for i in range(1, 6): #arbitrary stopping point, anything more than this will not result in different sizing
            #size the primary system based on the number of load up hours
            volN[i-1], effMixN[i-1] = self.sizePrimaryTankVolume(heatHrs = self.maxDayRun_hr, loadUpHours = i, primaryCurve = False)
            capN[i-1] = self._primaryHeatHrs2kBTUHR(heathours = self.maxDayRun_hr, loadUpHours = i, effSwingVolFract = effMixN[i-1], primaryCurve = False)[0]
            N[i-1] = i

        volN, capN = zip(*set(zip(volN, capN)))
        N = N[:len(volN)]
    
        return [volN, capN, N]

    
    def runOnePrimaryStep(self, pheating, V0, Vtrig, Vcurr, hw_out, hw_in):
        """
        Runs one step on the primary system. This changes the volume of the primary system
        by assuming there is hot water removed at a volume of hw_out and hot water
        generated or added at a volume of hw_in. This is assuming the system is perfectly
        stratified and all of the hot water above the cold temperature is at the storage temperature.

        Parameters
        ----------
        pheating : boolean
            indicates whether system is heating at the beginning of this step
        V0 : float
            The storage volume of the primary system at the storage temperature
        Vtrig : float
            The remaining volume of the primary storage volume when heating is
            triggered, note this equals V0*(1 - aquaFract) TODO is that true tho? 
        Vcurr : float
            The primary volume at the timestep.
        hw_out : float
            The volume of DHW removed from the primary system, assumed that
            100% of what of what is removed is replaced
        hw_in : float
            The volume of hot water generated in a time step

        Returns
        -------
        pheating : boolean
            Boolean indicating if the primary system is heating at the end of this step in the simulation 
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

        else:  # Else not heating, REMOVED TIME MISSED HERE
            Vnew = Vcurr - hw_out # So lose HW
            if Vnew < Vtrig: # If should heat
                Vnew += hw_in # # Start heating
                did_run = hw_in 
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

        Implimented seperatly for Swing Tank systems

        Parameters
        ----------
        return_as_div
            A logical on the output, as a div (true) or as a figure (false)

        Returns
        -------
        div/fig
            plot_div
        """
        [V, G_hw, D_hw, run] = self.simulate()
        
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
    
    def _calcPrelimVol(self, loadUpHours):
        '''
        Function to calculate volume shifted during first shed period, which is used to calculated generation rate
        needed for load up.

        Parameters
        ----------
        loadUpHours : float
            Number of hours of scheduled load up before first shed. If sizing, this is set by user. If creating sizing
            plot, number may vary. 

        Returns 
        ----------
        Vshift : float
            Volume at supply temp between normal and load up AQ fract needed to make it through first shed period.
        VconsumedLU : float
            Volume at supply temp consumed during first load up period.
        '''
        shedHours = [i for i in range(len(self.loadShiftSchedule)) if self.loadShiftSchedule[i] == 0] #get all scheduled shed hours
        firstShed = [x for i,x in enumerate(shedHours) if x == shedHours[0] + i] #get first shed
        Vshift = sum([self.building.avgLoadshape[i]*self.building.magnitude for i in firstShed])#calculate vol used during first shed
        VconsumedLU = sum(self.building.avgLoadshape[firstShed[0] - loadUpHours : firstShed[0]]) * self.building.magnitude
        
        return Vshift, VconsumedLU 
        
        

    def _mixStorageTemps(self, runningVol_G):
        """
        Calculates average tank temperature using load up and normal setpoints according to locations of aquastats. 
        Used for load shifting when there are two setpoints. Returns normal storage setpoint if load up and normal
        setpoint are equal or if not loadshifting.

        Parameters
        ----------
        runningVol_G : float
            Volume of water to be mixed. 

        Returns
        ----------
        mixStorageT_F: float
            Average storage temperature calcuated with normal setpoint and load up setpoint.
        totalVolMax : float
            The total storage volume in gallons adjusted to the average storage temperature.
        """
        mixStorageT_F = self.storageT_F

        if self.doLoadShift:
            f = (self.aquaFract - self.aquaFractLoadUp) / (self.aquaFractShed - self.aquaFractLoadUp) 
            normV = (1 - f) * runningVol_G
            loadV = f * runningVol_G

            mixStorageT_F = (self.storageT_F * normV + self.loadUpT_F * loadV) / (normV + loadV)

            return mixStorageT_F, mixVolume(runningVol_G, mixStorageT_F, self.building.incomingT_F, self.building.supplyT_F) / (self.aquaFractShed - self.aquaFractLoadUp)
        
        return [mixStorageT_F]

    
class Primary(SystemConfig):
    def __init__(self, building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, 
                 doLoadShift = False, loadShiftPercent = 1, loadShiftSchedule = None, loadUpHours = None, aquaFractLoadUp = None, 
                 aquaFractShed = None, loadUpT_F = None):
        super().__init__(building, storageT_F, defrostFactor, percentUseable, compRuntime_hr, aquaFract, 
                 doLoadShift, loadShiftPercent, loadShiftSchedule, loadUpHours, aquaFractLoadUp, aquaFractShed, loadUpT_F)


