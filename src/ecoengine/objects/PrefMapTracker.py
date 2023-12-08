import os
import json
from ecoengine.constants.Constants import KWH_TO_BTU, W_TO_BTUHR
import pickle
from scipy.interpolate import LinearNDInterpolator
import math

class PrefMapTracker:
    """
    An object that uses the preformance map data of varrious models to accuratly predict the kW input and output of 
    HPWH systems under different climates and temperatures.

    Attributes
    ----------
    defaultCapacity_kBTUhr : float
        the default output capacity for the system in kBTUhr
    modelName : String
        The string name for the HPWH model. Must match one of the model names in maps.json. If set to None, this will
        be a default generic HPWH with a COP of 2.5
    kBTUhr : boolean
        Set to True to return input and output capacity in kBTUhr, set to False to return in kW
    numHeatPumps : int
        the Number of heat pumps in the system. If set to None, will be autosized to produce defaultCapacity_kBTUhr output capacity.
        If auto-sizing the number of heat pumps for extreme weather environments outside of available preformance map scope, 
        you will also need to enter parameters for designOAT_F, designIncomingT_F, and designOutT_F to ensure no exceptions occur.
    isMultiPass : boolean
        Set to True for multipass systems, set to False for singlepass
    designOAT_F : float
        The worst-case outdoor air temperature for the climate the preformance map is being tested in. This ensures number of heat pumps is 
        auto-sized appropriatly
    designIncomingT_F : float
        The worst-case inlet water temperature for the climate the preformance map is being tested in. This ensures number of heat pumps is 
        auto-sized appropriatly
    designOutT_F : float
        The worst-case outlet water temperature for the system the preformance map is being tested in. This ensures number of heat pumps is 
        auto-sized appropriatly
    usePkl : boolean
        Default to True. Set to True to use most recent preformance map model. Set to false to use HPWHsim model
    prefMapOnly : boolean
        Set to True when not using preformance map in te larger EcoEngine system. This provides some shortcuts to avoid certain error handling
    erBaseline : boolean
        Set to true to indicate this preformance map is meant to model a ER system with a COP of 1
    """
    def __init__(self, defaultCapacity_kBTUhr = None, modelName = None, kBTUhr = False, numHeatPumps = None, 
                 isMultiPass = False, designOAT_F : float = None, designIncomingT_F : float = None, 
                 designOutT_F : float = None, usePkl = True, prefMapOnly = False, erBaseline = False):
        self.usePkl = usePkl
        self.isQAHV = False
        self.output_cap_interpolator = None
        self.input_cap_interpolator = None
        self.defaultCapacity_kBTUhr = defaultCapacity_kBTUhr
        self.perfMap = None
        self.kBTUhr = kBTUhr
        self.isMultiPass = isMultiPass
        self.twoInputPkl = False
        self.oat_max = None
        self.oat_min = None
        self.inlet_max = None
        self.inlet_min = None
        self.outlet_max = None
        self.outlet_min = None
        self.default_output_high = None
        self.default_input_high = None
        self.default_output_low = None
        self.default_input_low = None
        self.prefMapOnly = prefMapOnly
        self.erBaseline = erBaseline
        if defaultCapacity_kBTUhr is None and numHeatPumps is None:
            raise Exception("Invalid input given for preformance map, requires either defaultCapacity_kBTUhr or numHeatPumps.")
        elif not numHeatPumps is None and not ((isinstance(numHeatPumps, int) or isinstance(numHeatPumps, float)) and numHeatPumps > 0):
            raise Exception("Invalid input given for numHeatPumps, must be a number greater than zero")
        self.numHeatPumps = numHeatPumps
        if not modelName is None: 
            self.setPrefMap(modelName)
            if numHeatPumps is None and not (designOAT_F is None or designIncomingT_F is None or designOutT_F is None):
                if self.usePkl:
                    # Need pkl'd to not return default for sizing number of heat pumps so must set design temp
                    if designOAT_F < self.oat_min:
                        designOAT_F = self.oat_min
                    if designIncomingT_F < self.inlet_min:
                        designIncomingT_F = self.inlet_min
                    if designOutT_F < self.outlet_min:
                        designOutT_F = self.outlet_min
                self.getCapacity(designOAT_F, designIncomingT_F, designOutT_F, sizingNumHP = True) # will set self.numHeatPumps in this function

    def getDefaultCapacity(self):
        """
        Returns default capacity for the system in kBTUhr
        """
        return self.defaultCapacity_kBTUhr

    def getCapacity(self, externalT_F, condenserT_F, outT_F, sizingNumHP = False):
        """
        Returns the current output capacity of of the HPWH model for the simulation given external and condesor temperatures.
        If no HPWH model has been set, returns the default output capacity of the system.
        
        Inputs
        ------
        externalT_F : float
            The external air temperature in fahrenheit
        condenserT_F : float
            The condenser temperature (incoming water temperature) in fahrenheit
        outT_F : float
            The temperature of water leaving the system in fahrenheit
        Returns
        -------
        output_kW
            The output capacity of the primary HPWH in kW (or kBTUhr if the PrefMapTracker object was initialized with kBTUhr=True) as a float
        input_kW
            The input capacity of the primary HPWH in kW (or kBTUhr if the PrefMapTracker object was initialized with kBTUhr=True) as a float
        """
        if self.usePkl:
            # edit incoming values to extrapolate if need be
            extrapolate = False
            if self.isQAHV:
                # TODO check for outT_F, may need to be plus 10 for QAHV///secondary heat exchanger systems
                condenserT_F += 10. # add 10 degrees to incoming water temp for QAHV only

            #use pickled interpolation functions
            input_array = [condenserT_F, outT_F, externalT_F]
            if self.twoInputPkl:
                input_array = [condenserT_F, externalT_F] # MultiPass performance maps do not account for outlet water temp
            output_kW = self.output_cap_interpolator(input_array)[0][0]
            input_kW = self.input_cap_interpolator(input_array)[0][0]
            if math.isnan(output_kW) or math.isnan(input_kW):
                extrapolate = True
                if abs(externalT_F - self.oat_max) > abs(externalT_F - self.oat_min): # if closer to coldest temp than warmest temp in perf map
                    if sizingNumHP:
                        print(f"Error in preformance map for input array of {input_array}. Using default capacity values to size.")
                        output_kW =self.default_output_low
                        input_kW = self.default_input_low
                    else:
                        if self.defaultCapacity_kBTUhr is None:
                            if self.prefMapOnly:
                                return 1.,1. # set for QPL generator electric resistance
                            else:
                                # TODO if we want to put this into ecosizer, we need to size default capacity here and give warning to engineers that ER will be required
                                raise Exception("Climate inputs are colder than available preformance maps for this model. The model will need a default electric resistance capacity to fall back on in order to simulate.")
                        # SEE ABOVE TODO ^^^
                        if self.kBTUhr:
                            return self.defaultCapacity_kBTUhr, self.defaultCapacity_kBTUhr # externalT_F is low so use electric resistance to heat and assume COP of 1
                        else:
                            # return in kW
                            return self.defaultCapacity_kBTUhr/W_TO_BTUHR, self.defaultCapacity_kBTUhr/W_TO_BTUHR
                else:
                    # externalT_F is high so assume same COP for highest temp in performance map
                    output_kW = self.default_output_high
                    input_kW = self.default_input_high

        elif self.perfMap is None or len(self.perfMap) == 0:
            if self.erBaseline:
                if self.kBTUhr:
                    return self.defaultCapacity_kBTUhr, self.defaultCapacity_kBTUhr # ER has COP of 1
                return self.defaultCapacity_kBTUhr/W_TO_BTUHR, self.defaultCapacity_kBTUhr/W_TO_BTUHR
            elif self.kBTUhr:
                return self.defaultCapacity_kBTUhr, self.defaultCapacity_kBTUhr / 2.5 # assume COP of 2.5 for input_capactiy calculation for default HPWH
            return self.defaultCapacity_kBTUhr/W_TO_BTUHR, (self.defaultCapacity_kBTUhr/W_TO_BTUHR)/2.5

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

            inputPower_T1_kW = inputPower_T1_Watts / 1000.0
            inputPower_T2_kW = inputPower_T2_Watts / 1000.0

            cop = self._linearInterp(externalT_F, self.perfMap[i_prev]['T_F'], self.perfMap[i_next]['T_F'], COP_T1, COP_T2)
            input_kW = (self._linearInterp(externalT_F, self.perfMap[i_prev]['T_F'], self.perfMap[i_next]['T_F'], inputPower_T1_kW, inputPower_T2_kW))
            output_kW = cop * input_kW
        else:
            if(externalT_F > self.perfMap[0]['T_F']):
                extrapolate = True
            if self.isMultiPass:
                input_kW = self._regressedMethodMP(externalT_F, condenserT_F, self.perfMap[0]['inputPower_coeffs'])
                cop = self._regressedMethodMP(externalT_F, condenserT_F, self.perfMap[0]['COP_coeffs'])
            else:
                input_kW = self._regressedMethod(externalT_F, outT_F, condenserT_F, self.perfMap[0]['inputPower_coeffs'])
                cop = self._regressedMethod(externalT_F, outT_F, condenserT_F, self.perfMap[0]['COP_coeffs'])
            output_kW = cop * input_kW

        if self.kBTUhr:
            output_kW *= W_TO_BTUHR # convert kW to kBTU
            input_kW *= W_TO_BTUHR
        if self.numHeatPumps is None:
            if self.kBTUhr:
                # output has already been converted to kBTUhr
                self._autoSetNumHeatPumps(output_kW)
            else:
                self._autoSetNumHeatPumps(output_kW*W_TO_BTUHR)
        output_kW *= self.numHeatPumps
        input_kW *= self.numHeatPumps
        return [output_kW, input_kW]

    def _autoSetNumHeatPumps(self, modelCapacity_kBTUhr):
        heatPumps = math.ceil(self.defaultCapacity_kBTUhr/modelCapacity_kBTUhr)
        self.numHeatPumps = max(heatPumps,1.0) + 0.0 # add 0.0 to ensure that it is a float

    def setPrefMap(self, modelName):
        if modelName == "MODELS_Mitsubishi_QAHV":
            self.isQAHV = True
        elif modelName == "MODELS_SANCO2_C_SP" or (modelName[-2:] == 'MP' 
                and not modelName in ["MODELS_RHEEM_HPHD135VNU_483_C_MP","MODELS_RHEEM_HPHD135HNU_483_C_MP",
                "MODELS_RHEEM_HPHD60VNU_201_C_MP","MODELS_RHEEM_HPHD60HNU_201_C_MP"]):
            # The rheems with pkls function like single pass pkls
            self.twoInputPkl = True
        if modelName[-2:] == 'MP':
            self.isMultiPass = True
        try:
            with open(os.path.join(os.path.dirname(__file__), '../data/preformanceMaps/maps.json')) as json_file:
                dataDict = json.load(json_file)
                if self.usePkl or not "perfmap" in dataDict[modelName]:
                    self.usePkl = True
                    filepath = "../data/preformanceMaps/pkls/"
                    with open(os.path.join(os.path.dirname(__file__), f"{filepath}{dataDict[modelName]['cap_out_pkl']}"), 'rb') as f:
                        self.output_cap_interpolator = pickle.load(f)
                    with open(os.path.join(os.path.dirname(__file__), f"{filepath}{dataDict[modelName]['cap_in_pkl']}"), 'rb') as f:
                        self.input_cap_interpolator = pickle.load(f)
                    with open(os.path.join(os.path.dirname(__file__), f"{filepath}{dataDict[modelName]['bounds_pkl']}"), 'rb') as f:
                        bounds = pickle.load(f)
                        # Format: [[max_oat,min_oat],[max_inlet,min_inlet],[max_outlet,min_outlet],[default_output_high, default_input_high],[default_output_low, default_input_low]]
                        self.oat_max = bounds[0][0]
                        self.oat_min = bounds[0][1]
                        self.inlet_max = bounds[1][0]
                        self.inlet_min = bounds[1][1]
                        self.outlet_max = bounds[2][0]
                        self.outlet_min = bounds[2][1]
                        self.default_output_high = bounds[3][0]
                        self.default_input_high = bounds[3][1]
                        self.default_output_low = bounds[4][0]
                        self.default_input_low = bounds[4][1]
                else:
                        self.perfMap = dataDict[modelName]["perfmap"]
        except:
            if self.usePkl and modelName != "MODELS_Mitsubishi_QAHV":
                print("No preformance map pkl file found for " + modelName + ". Attempting to use non-pkl preformance map")
                self.usePkl = False
                self.setPrefMap(modelName)
            else:
                raise Exception("No preformance map found for HPWH model type " + modelName + ".")
    
    def _linearInterp(self, xnew, x0, x1, y0, y1):
        return y0 + (xnew - x0) * (y1 - y0) / (x1 - x0)
    
    def _regressedMethod(self, externalAirT_F, outletWaterT_F, inletWaterT_F, coefficents):
        if len(coefficents) != 11:
            raise Exception('Attempting to use preformance mapping method with invalid system model.')
        ynew = coefficents[0]
        ynew += coefficents[1] * externalAirT_F
        ynew += coefficents[2] * outletWaterT_F
        ynew += coefficents[3] * inletWaterT_F
        ynew += coefficents[4] * externalAirT_F * externalAirT_F
        ynew += coefficents[5] * outletWaterT_F * outletWaterT_F
        ynew += coefficents[6] * inletWaterT_F * inletWaterT_F
        ynew += coefficents[7] * externalAirT_F * outletWaterT_F
        ynew += coefficents[8] * externalAirT_F * inletWaterT_F
        ynew += coefficents[9] * outletWaterT_F * inletWaterT_F
        ynew += coefficents[10] * externalAirT_F * outletWaterT_F * inletWaterT_F
        return ynew
    
    def _regressedMethodMP(self, x1, x2, coefficents):
        if len(coefficents) != 6:
            raise Exception('Attempting to use multi-pass preformance mapping method with non-multi-pass system model.')
        ynew = coefficents[0]
        ynew += coefficents[1] * x1
        ynew += coefficents[2] * x2
        ynew += coefficents[3] * x1 * x1
        ynew += coefficents[4] * x2 * x2
        ynew += coefficents[5] * x1 * x2
        return ynew