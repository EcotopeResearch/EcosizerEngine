from ecoengine.objects.SystemConfig import SystemConfig
from ecoengine.objects.Building import Building
from ecoengine.objects.systemConfigUtils import *
from ecoengine.objects.SimulationRun import *
import os
import json
from ecoengine.constants.Constants import KWH_TO_BTU
import csv

    
def simulate(system : SystemConfig, building : Building, initPV=None, initST=None, Pcapacity=None, Pvolume=None, minuteIntervals = 1, nDays = 3,
             zipCode = None, climateZone = None, hpwhModel = None):
    """
    Implimented seperatly for Swink Tank systems 
    Inputs
    ------
    building : Building
        the building object the system configuration is being simulated for.
    initPV : float
        Primary volume at start of the simulation
    initST : float
        Swing tank temperature at start of the simulation. Not used in this instance of the function
    Pcapacity : float
        The primary heating capacity in kBTUhr to use for the simulation,
        default is the sized system
    Pvolume : float
        The primary storage volume in gallons to  to use for the simulation,
        default is the sized system
    
    Returns
    -------
    list [ pV, hwGenRate, hwDemand, pGen ]
    pV : list 
        Volume of HW in the tank with time at the strorage temperature.
    hwGenRate : list 
        The generation of HW with time at the supply temperature
    hwDemand : list 
        The hot water demand with time at the tsupply temperature
    pGen : list 
        The actual hot water generation in gallons of the HPWH with time
    """

    simRun = system.getInitializedSimulation(building, Pcapacity, Pvolume, initPV, initST, minuteIntervals, nDays)

    perfMap = PrefMapTracker(system.PCap_kBTUhr, zipCode = zipCode, climateZone = climateZone, modelName = hpwhModel) 

    # add city water tempuratures to simRun
    if not perfMap.climateZone is None:
        with open(os.path.join(os.path.dirname(__file__), '../data/climate_data/InletWaterTemperatures_ByClimateZone.csv'), 'r') as cw_file:
            csv_reader = csv.reader(cw_file)
            next(csv_reader) # get past header row
            cw_temp_by_month = []
            for i in range(12):
                cw_row = next(csv_reader)
                cw_temp_by_month.append(float(cw_row[perfMap.climateZone - 1]))
            simRun.setMonthlyCityWaterT_F(cw_temp_by_month)
            
    with open(os.path.join(os.path.dirname(__file__), '../data/climate_data/DryBulbTemperatures_ByClimateZone.csv'), 'r') as oat_file:
        with open(os.path.join(os.path.dirname(__file__), '../data/climate_data/kGperkWh_ByClimateZone.csv'), 'r') as kG_file:
            oat_reader = csv.reader(oat_file)
            kG_reader = csv.reader(kG_file)
            next(oat_reader)
            next(kG_reader)
            oat_row = next(oat_reader) # now on first hour
            kG_row = next(kG_reader) # now on first hour
            cap = 0 # initialize cap
            if not perfMap.climateZone is None: # TODO need better check for annual
                oat_F = float(oat_row[perfMap.climateZone - 1])
                cap = perfMap.getCapacity(oat_F, 120) #TODO use a real condesor temp
                simRun.addOat(oat_F)
                system.setCapacity(cap)
                simRun.addCap(cap)
                kG = (float(kG_row[perfMap.climateZone-1])/(60/minuteIntervals))*(cap/2.5)*(simRun.pRun[0]/minuteIntervals)
                simRun.addKGperkWh(kG)


            # Run the "simulation"
            for i in range(1, len(simRun.hwDemand)):
                # TODO change capacity based on weather here
                if not perfMap.climateZone is None: # TODO find more elegant way to determine if this is annual sim?
                    if i%(60/minuteIntervals) == 0: # we have reached the next hour and should thus take the next OAT
                        oat_row = next(oat_reader)
                        oat_F = float(oat_row[perfMap.climateZone - 1])
                        simRun.addOat(oat_F)
                        kG_row = next(kG_reader)
                        # print("at hour " + str(i/(60/minuteIntervals)) +" oat_F is: "+str(oat_F))
                        cap = perfMap.getCapacity(oat_F, 120) #TODO use a real condesor temp
                        system.setCapacity(cap)
                    system.runOneSystemStep(simRun, i, minuteIntervals = minuteIntervals)
                    kG = (float(kG_row[perfMap.climateZone-1])/(60/minuteIntervals))*(cap/2.5)*(simRun.pRun[i]/minuteIntervals) # TODO 2.5 COP placeholder.
                    simRun.addKGperkWh(kG)   
                    simRun.addCap(cap)
                else:
                    system.runOneSystemStep(simRun, i, minuteIntervals = minuteIntervals)

    return simRun

class PrefMapTracker:
    def __init__(self, defaultCapacity, zipCode = None, climateZone = None, modelName = None):
        self.defaultCapacity = defaultCapacity
        self.climateZone = None
        self.perfMap = None
        self.setClimateZone(zipCode = zipCode, climateZone = climateZone)
        if not modelName is None: 
            self.setPrefMap(modelName)

    def getCapacity(self, externalT_F, condenserT_F):
        if self.perfMap is None or len(self.perfMap) == 0:
            return self.defaultCapacity
        elif len(self.perfMap) > 1:
            # cop at ambient temperatures T1 and T2
            COP_T1 = 0 
            COP_T2 = 0
            # input power at ambient temperatures T1 and T2
            inputPower_T1_Watts = 0
            inputPower_T2_Watts = 0

            i_prev = 0
            i_next = 1
            extrapolate = False
            for i in range(0, len(self.perfMap)):
                if externalT_F < self.perfMap[i]['T_F']:
                    if i == 0:
                        extrapolate = True # TODO warning message
                    else:
                       i_prev = i - 1
                       i_next = i
                    break
                else:
                    if i >= len(self.perfMap) - 1:
                        extrapolate = True  # TODO warning message
                        i_prev = i-1
                        i_next = i
                        break
            
            COP_T1 = self.perfMap[i_prev]['COP_coeffs'][0]
            COP_T1 += self.perfMap[i_prev]['COP_coeffs'][1] * condenserT_F
            COP_T1 += self.perfMap[i_prev]['COP_coeffs'][2] * condenserT_F * condenserT_F

            COP_T2 = self.perfMap[i_next]['COP_coeffs'][0]
            COP_T2 += self.perfMap[i_next]['COP_coeffs'][1] * condenserT_F
            COP_T2 += self.perfMap[i_next]['COP_coeffs'][2] * condenserT_F * condenserT_F

            inputPower_T1_Watts = self.perfMap[i_prev]['inputPower_coeffs'][0]
            inputPower_T1_Watts += self.perfMap[i_prev]['inputPower_coeffs'][1] * condenserT_F
            inputPower_T1_Watts += self.perfMap[i_prev]['inputPower_coeffs'][2] * condenserT_F * condenserT_F

            inputPower_T2_Watts = self.perfMap[i_next]['inputPower_coeffs'][0]
            inputPower_T2_Watts += self.perfMap[i_next]['inputPower_coeffs'][1] * condenserT_F
            inputPower_T2_Watts += self.perfMap[i_next]['inputPower_coeffs'][2] * condenserT_F * condenserT_F

            cop = self.linearInterp(externalT_F, self.perfMap[i_prev].T_F, self.perfMap[i_next].T_F, COP_T1, COP_T2)
            input_BTUperHr = (self.linearInterp(externalT_F, self.perfMap[i_prev].T_F, self.perfMap[i_next].T_F, inputPower_T1_Watts, inputPower_T2_Watts) / 1000.0) * KWH_TO_BTU

            return cop * input_BTUperHr


    def setPrefMap(self, modelName):
        try:
            with open(os.path.join(os.path.dirname(__file__), '../data/preformanceMaps/maps.json')) as json_file:
                dataDict = json.load(json_file)
                self.perfMap = dataDict[modelName]
        except:
            raise Exception("No preformance map found for HPWH model type " + modelName + ".")
    
    def setClimateZone(self, zipCode = None, climateZone = None):
        if not climateZone is None:
            if not isinstance(climateZone, int) or climateZone < 1 or climateZone > 16:
                raise Exception("Climate Zone must be a number between 1 and 16.")
            self.climateZone = climateZone
        elif not zipCode is None:
            with open(os.path.join(os.path.dirname(__file__), '../data/climate_data/ZipCode_ClimateZone_Lookup.csv'), 'r') as file:
                csv_reader = csv.reader(file)                
                for row in csv_reader:
                    if str(zipCode) == row[0]:
                        self.climateZone = int(row[1])
                        break
                if self.climateZone is None:
                    raise Exception(str(zipCode) + " is not a California zip code.")
    
    def linearInterp(self, xnew, x0, x1, y0, y1):
        return y0 + (xnew - x0) * (y1 - y0) / (x1 - x0)