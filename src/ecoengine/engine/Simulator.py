from ecoengine.objects.SystemConfig import SystemConfig
from ecoengine.objects.Building import Building
from ecoengine.objects.systemConfigUtils import *
from ecoengine.objects.SimulationRun import *
import os
import json
from ecoengine.constants.Constants import KWH_TO_BTU
import csv

    
def simulate(system : SystemConfig, building : Building, initPV=None, initST=None, minuteIntervals = 1, nDays = 3, hpwhModel = None):
    """
    Implimented seperatly for Swink Tank systems 
    Inputs
    ------
    system : SystemConfig
        the HPWH system object for the annual simulation
    building : Building
        the building object the system configuration is being simulated for.
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
    
    Returns
    -------
    simRun : SimulationRun
        resulting simulation run object containing information from each timestep interval of the simulation for further analysis
    """

    simRun = system.getInitializedSimulation(building, initPV, initST, minuteIntervals, nDays)

    perfMap = PrefMapTracker(system.PCap_kBTUhr/W_TO_BTUHR, modelName = hpwhModel) 

    if nDays == 365:
        # check for climateZone
        if building.climateZone is None:
            raise Exception("Cannot run annual simulation with out setting building climate zone to be a number between 1 and 16.")
        # add city water tempuratures to simRun
        with open(os.path.join(os.path.dirname(__file__), '../data/climate_data/InletWaterTemperatures_ByClimateZone.csv'), 'r') as cw_file:
            csv_reader = csv.reader(cw_file)
            next(csv_reader) # get past header row
            cw_temp_by_month = []
            for i in range(12):
                cw_row = next(csv_reader)
                cw_temp_by_month.append(float(cw_row[building.climateZone - 1]))
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
            if nDays == 365:
                oat_F = float(oat_row[building.climateZone - 1])
                cap = perfMap.getCapacity(oat_F, simRun.getIncomingWaterT(0), system.storageT_F) #TODO use a real condesor temp
                simRun.addOat(oat_F)
                system.setCapacity(cap)
                simRun.addCap(cap)
                kG = (float(kG_row[building.climateZone-1])/(60/minuteIntervals))*(cap/2.5)*(simRun.pRun[0]/minuteIntervals)
                simRun.addKGperkWh(kG)


            # Run the "simulation"
            for i in range(1, len(simRun.hwDemand)):
                if nDays == 365:
                    if i%(60/minuteIntervals) == 0: # we have reached the next hour and should thus take the next OAT
                        oat_row = next(oat_reader)
                        oat_F = float(oat_row[building.climateZone - 1])
                        simRun.addOat(oat_F)
                        kG_row = next(kG_reader)
                        # print("at hour " + str(i/(60/minuteIntervals)) +" oat_F is: "+str(oat_F))
                        cap = perfMap.getCapacity(oat_F, simRun.getIncomingWaterT(i), system.storageT_F) #TODO use a real condesor temp
                        system.setCapacity(cap*W_TO_BTUHR)
                    system.runOneSystemStep(simRun, i, minuteIntervals = minuteIntervals)
                    kG = (cap/2.5)*(simRun.pRun[i]/minuteIntervals) # TODO 2.5 COP placeholder.
                    if(hasattr(simRun, 'sRun')):
                        # we are keeping track of swingtank power as well
                        kG += (system.TMCap_kBTUhr/W_TO_BTUHR)*(simRun.sRun[i]/minuteIntervals) # Assume COP of 1, thus input power = capacity
                    kG *= (float(kG_row[building.climateZone-1])/(60/minuteIntervals))
                    simRun.addKGperkWh(kG)   
                    simRun.addCap(cap)
                else:
                    system.runOneSystemStep(simRun, i, minuteIntervals = minuteIntervals)

    return simRun

class PrefMapTracker:
    def __init__(self, defaultCapacity, modelName = None):
        self.defaultCapacity = defaultCapacity
        self.perfMap = None
        if not modelName is None: 
            self.setPrefMap(modelName)

    def getCapacity(self, externalT_F, condenserT_F, outT_F):
        """
        Returns the current output capacity of of the HPWH model for the simulation given external and condesor temperatures.
        If no HPWH model has been set, returns the default output capacity of the system.
        
        Inputs
        ------
        externalT_F : float
            The external air temperature in fahrenheit
        condenserT_F : float
            The condenser temperature in fahrenheit
        
        Returns
        -------
        The output capacity of the primary HPWH in kW as a float
        """
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

            cop = self._linearInterp(externalT_F, self.perfMap[i_prev].T_F, self.perfMap[i_next].T_F, COP_T1, COP_T2)
            input_kWperHr = (self._linearInterp(externalT_F, self.perfMap[i_prev].T_F, self.perfMap[i_next].T_F, inputPower_T1_Watts, inputPower_T2_Watts))

            return cop * input_kWperHr
        
        else:
            if(externalT_F > self.perfMap[0]['T_F']):
                extrapolate = True
            input_kWperHr = self._regressedMethod(externalT_F, outT_F, condenserT_F, self.perfMap[0]['inputPower_coeffs']) # TODO check for ToutF, may need to be plus 10 for QAHV
            cop = self._regressedMethod(externalT_F, outT_F, condenserT_F, self.perfMap[0]['COP_coeffs'])
            #print("inlet " + str(condenserT_F) + ", storage " + str(outT_F) +", OAT : "+str(externalT_F) + ", capacity " + str(cop * input_kWperHr)+ ", input_kWperHr " + str(input_kWperHr) + ", COP " + str(cop))
            return cop * input_kWperHr 

    def setPrefMap(self, modelName):
        try:
            with open(os.path.join(os.path.dirname(__file__), '../data/preformanceMaps/maps.json')) as json_file:
                dataDict = json.load(json_file)
                self.perfMap = dataDict[modelName]
        except:
            raise Exception("No preformance map found for HPWH model type " + modelName + ".")
    
    def _linearInterp(self, xnew, x0, x1, y0, y1):
        return y0 + (xnew - x0) * (y1 - y0) / (x1 - x0)
    
    def _regressedMethod(self, x1, x2, x3, coefficents):
        ynew = coefficents[0]
        ynew += coefficents[1] * x1
        ynew += coefficents[2] * x2
        ynew += coefficents[3] * x3
        ynew += coefficents[4] * x1 * x1
        ynew += coefficents[5] * x2 * x2
        ynew += coefficents[6] * x3 * x3
        ynew += coefficents[7] * x1 * x2
        ynew += coefficents[8] * x1 * x3
        ynew += coefficents[9] * x2 * x3
        ynew += coefficents[10] * x1 * x2 * x3
        return ynew