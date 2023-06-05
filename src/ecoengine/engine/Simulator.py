from ecoengine.objects.SystemConfig import SystemConfig
from ecoengine.objects.Building import Building
from ecoengine.objects.systemConfigUtils import *
from ecoengine.objects.SimulationRun import *
import os
import json
from ecoengine.constants.Constants import KWH_TO_BTU

    
def simulate(system : SystemConfig, building : Building, initPV=None, initST=None, Pcapacity=None, Pvolume=None, minuteIntervals = 1, nDays = 3,
             climateZone = None, hpwhModel = None):
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

    simRun = system.getInitializedSimulation(building, Pcapacity, Pvolume, initPV, initST, minuteIntervals, nDays)

    perfMap = PrefMapTracker(system.PCap_kBTUhr)
    if not hpwhModel is None:
        perfMap.setPrefMap(hpwhModel)
        

    # Run the "simulation"
    for i in range(1, len(simRun.D_hw)):
        # TODO change capacity based on weather here
        system.runOneSystemStep(simRun, i, minuteIntervals = minuteIntervals)

    return simRun

class PrefMapTracker:
    def __init__(self, defaultCapacity, modelName = None):
        self.defaultCapacity = defaultCapacity
        if modelName is None: 
            self.perfMap = None
        else:
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
                        extrapolate = True
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
    
    def linearInterp(self, xnew, x0, x1, y0, y1):
        return y0 + (xnew - x0) * (y1 - y0) / (x1 - x0)