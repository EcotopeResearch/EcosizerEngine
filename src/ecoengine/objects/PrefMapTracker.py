import os
import json
from ecoengine.constants.Constants import KWH_TO_BTU, W_TO_BTUHR
import pickle
from scipy.interpolate import LinearNDInterpolator
import math

class PrefMapTracker:
    def __init__(self, defaultCapacity = None, modelName = None, kBTUhr = False, numHeatPumps = None, isMultiPass = False):
        self.isQAHV = False
        self.output_cap_interpolator = None
        self.cop_interpolator = None
        self.input_cap_interpolator = None
        self.defaultCapacity = defaultCapacity
        self.perfMap = None
        self.kBTUhr = kBTUhr
        self.isMultiPass = isMultiPass
        if defaultCapacity is None and numHeatPumps is None:
            raise Exception("Invalid input given for preformance map, requires either defaultCapacity or numHeatPumps.")
        elif not numHeatPumps is None and not ((isinstance(numHeatPumps, int) or isinstance(numHeatPumps, float)) and numHeatPumps > 0):
            raise Exception("Invalid input given for numHeatPumps, must be a number greater than zero")
        self.numHeatPumps = numHeatPumps
        if not modelName is None: 
            self.setPrefMap(modelName)

    def getDefaultCapacity(self):
        return self.defaultCapacity

    def getCapacity(self, externalT_F, condenserT_F, outT_F):
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
            The output capacity of the primary HPWH in kW as a float
        input_kW
            The input capacity of the primary HPWH in kW as a float
        """
        if self.isQAHV:
            # edit incoming values to extrapolate if need be
            extrapolate = False
            condenserT_F += 10 # add 10 degrees to incoming water temp for QAHV only
            
            if condenserT_F > 120:
                condenserT_F = 120
                extrapolate = True
            elif condenserT_F < 41:
                condenserT_F = 120
                extrapolate = True
            
            if outT_F > 170:
                outT_F = 170
                extrapolate = True
            elif outT_F < 149:
                outT_F = 149
                extrapolate = True
            
            if externalT_F > 100.0:
                externalT_F = 100.0
                extrapolate = True
            elif externalT_F < -13.0:
                externalT_F = -13.0
                extrapolate = True

            #use pickled interpolation functions
            input_array = [condenserT_F, outT_F, externalT_F] # add 10 degrees to inlet water temp for QAHV
            output_kW = self.output_cap_interpolator(input_array)[0][0]
            input_kW = self.input_cap_interpolator(input_array)[0][0]

        elif self.perfMap is None or len(self.perfMap) == 0:
            return self.defaultCapacity, self.defaultCapacity / 2.5 # assume COP of 2.5 for input_capactiy calculation
        
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
                input_kW = self._regressedMethod(externalT_F, outT_F, condenserT_F, self.perfMap[0]['inputPower_coeffs']) # TODO check for outT_F, may need to be plus 10 for QAHV
                cop = self._regressedMethod(externalT_F, outT_F, condenserT_F, self.perfMap[0]['COP_coeffs'])
            output_kW = cop * input_kW

        if self.kBTUhr:
            output_kW *= W_TO_BTUHR # convert kW to kBTU
            input_kW *= W_TO_BTUHR
        if self.numHeatPumps is None:
            self._autoSetNumHeatPumps(output_kW)
        output_kW *= self.numHeatPumps
        input_kW *= self.numHeatPumps
        return [output_kW, input_kW]

    def _autoSetNumHeatPumps(self, modelCapacity):
        heatPumps = round(self.defaultCapacity/modelCapacity)
        self.numHeatPumps = max(heatPumps,1.0) + 0.0 # add 0.0 to ensure that it is a float

    def setPrefMap(self, modelName):
        if modelName == "MODELS_Mitsubishi_QAHV":
            self.isQAHV = True
            filepath = "../data/preformanceMaps/pkls/"
            with open(os.path.join(os.path.dirname(__file__), f"{filepath}QAHV_capacity_interpolator.pkl"), 'rb') as f:
                self.output_cap_interpolator = pickle.load(f)
            with open(os.path.join(os.path.dirname(__file__), f"{filepath}QAHV_cop_interpolator.pkl"), 'rb') as f:
                self.cop_interpolator = pickle.load(f)
            with open(os.path.join(os.path.dirname(__file__), f"{filepath}QAHV_power_in_interpolator.pkl"), 'rb') as f:
                self.input_cap_interpolator = pickle.load(f)
        else:
            try:
                with open(os.path.join(os.path.dirname(__file__), '../data/preformanceMaps/maps.json')) as json_file:
                    dataDict = json.load(json_file)
                    self.perfMap = dataDict[modelName]["perfmap"]
                    if modelName[-2:] == 'MP':
                        self.isMultiPass = True
            except:
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