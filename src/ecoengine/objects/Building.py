import os
import json
import numpy as np

from ecoengine.constants.Constants import *

class Building:
    def __init__(self, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        
        self._checkParams(incomingT_F, supplyT_F, returnT_F, flowRate, ignoreRecirc)
        
        # Does not check loadshape as that is checked in buildingCreator
        self.loadshape = loadshape
        self.avgLoadshape = avgLoadshape
        
        self.incomingT_F = incomingT_F
        self.supplyT_F = supplyT_F
        if ignoreRecirc:
            self.recirc_loss = 0
        else:
            self.recirc_loss = (supplyT_F - returnT_F) * flowRate * rhoCp * 60. #BTU/HR
            if(self.recirc_loss > RECIRC_LOSS_MAX_BTUHR):
                raise Exception("Error: Recirculation losses may not exceed 108 kW, consider using multiple central plants.")
        self.climateZone = climate

    def _checkParams(self, incomingT_F, supplyT_F, returnT_F, flowRate, ignoreRecirc):
        if not (isinstance(supplyT_F, int) or isinstance(supplyT_F, float)):
            raise Exception("Error: Supply temp must be a number.")
        if not ignoreRecirc:
            if not (isinstance(returnT_F, int) or isinstance(returnT_F, float)):
                raise Exception("Error: Return temp must be a number.")
            if supplyT_F <= returnT_F:
                raise Exception("Error: Supply temp must be higher than return temp.")
            if not (isinstance(flowRate, int) or isinstance(flowRate, float)):
                raise Exception("Error: Flow rate must be a number.")
        if not (isinstance(incomingT_F, int) or isinstance(incomingT_F, float)):
            raise Exception("Error: City water temp must be a number.")
        if not hasattr(self, 'magnitude'):
            raise Exception("Magnitude has not been set.")
        
    def setToAnnualLS(self):
        raise Exception("Annual loadshape not available for this building type. This feature is only available for multi-family buildings.")
    def setToDailyLS(self):
        raise Exception("setToDailyLS() feature is not available for this building type. This feature is only available for multi-family buildings.")

class MensDorm(Building):
    def __init__(self, n_students, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        self.magnitude = n_students * 18.9 # ASHREA GPD per student
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class WomensDorm(Building):
    def __init__(self, n_students, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        self.magnitude = n_students * 16.4 # ASHREA GPD per student
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class Motel(Building):
    def __init__(self, n_units, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        self.magnitude = n_units * 28.8 # ASHREA GPD per unit
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class NursingHome(Building):
    def __init__(self, n_beds, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        self.magnitude = n_beds * 20.1 # ASHREA GPD per bed
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class OfficeBuilding(Building):
    def __init__(self, n_people, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        self.magnitude = n_people * 1.11 # ASHREA GPD per person
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class FoodServiceA(Building):
    def __init__(self, n_meals, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        self.magnitude = n_meals * 11.032 # ASHREA GPD per meal
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class FoodServiceB(Building):
    def __init__(self, n_meals, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        self.magnitude = n_meals * 6.288 # ASHREA GPD per meal
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class Apartment(Building):
    def __init__(self, n_units, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        self.magnitude = n_units * 42.8 # ASHREA GPD per unit
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class ElementarySchool(Building):
    def __init__(self, n_students, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        self.magnitude = n_students * 1.081 # ASHREA GPD per student
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class JuniorHigh(Building):
    def __init__(self, n_students, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        self.magnitude = n_students * 3.27 # ASHREA GPD per student
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class SeniorHigh(Building):
    def __init__(self, n_students, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        self.magnitude = n_students * 3.02 # ASHREA GPD per student
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)
    
class MultiFamily(Building):
    def __init__(self, n_people, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc, gpdpp, nBR, nApt, Wapt, standardGPD):
        # check inputs
        if not nApt is None and not (isinstance(nApt, int)):
            raise Exception("Error: Number of apartments must be an integer.")
        if not Wapt is None and not (isinstance(Wapt, int)):
            raise Exception("Error: WATTs per apt must be an integer.")
        if standardGPD is None:
            if not (isinstance(gpdpp, int) or isinstance(gpdpp, float)):
                raise Exception("Error: GPDPP must be a number.")
        else:
            if isinstance(standardGPD, str) and standardGPD in possibleStandardGPDs: # if the input here is a string get the appropriate standard gpdpp
                with open(os.path.join(os.path.dirname(__file__), '../data/load_shapes/multi_family.json')) as json_file:
                    dataDict = json.load(json_file)

                    if standardGPD.lower() == "ca" :
                        if nBR is None or not (isinstance(nBR, list) or isinstance(nBR, np.ndarray))or sum(nBR) == 0 or len(nBR) != 6:
                            raise Exception("Cannot get the gpdpp for the CA data set without knowning the number of units by bedroom size for 0 BR (studios) through 5+ BR, the list must be of length 6 in that order.")

                        # Count up the gpdpp for each bedroom type
                        daily_totals = np.zeros(365)
                        for i in range(0,6):
                            daily_totals += nBR[i] * np.array(dataDict['ca_gpdpp'][str(i) + "br"]) # daily totals is gpdpp * bedroom

                        # Get the 98th percentile day divide by the number of people rounded up to an integer.
                        gpdpp = round(np.percentile(daily_totals,98)/ sum(nBR), 1)

                    # Else look up by normal key function
                    else:
                        gpdpp = dataDict['gpdpp'][standardGPD][0]
            else:
                raise Exception("Error: standardGPD must be a String of one of the following values: " + str(possibleStandardGPDs))
            
        self.magnitude = gpdpp * n_people # gpdpp * number_of_people

        # recalculate recirc_loss with different method if applicable
        if not ignoreRecirc and not nApt is None and not Wapt is None and (nApt > 0 and Wapt > 0):
            # nApt * Wapt will overwrite recirc_loss so it doesn't matter what numbers we put in for returnT_F, flowRate
            super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, None, None, climate, ignoreRecirc = True)
            self.recirc_loss = nApt * Wapt * W_TO_BTUHR
        else:
            super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

    def setToAnnualLS(self):
        with open(os.path.join(os.path.dirname(__file__), '../data/load_shapes/multi_family.json')) as json_file:
            dataDict = json.load(json_file)
            self.loadshape = np.array(dataDict['loadshapes']["Annual_Normalized"])
            self.avgLoadshape = self.loadshape
    
    def setToDailyLS(self):
        with open(os.path.join(os.path.dirname(__file__), '../data/load_shapes/multi_family.json')) as json_file:
            dataDict = json.load(json_file)
            self.loadshape = np.array(dataDict['loadshapes']["Stream"])
            self.avgLoadshape = np.array(dataDict['loadshapes']["Stream_Avg"])

class MultiUse(Building):
    def __init__(self, building_list, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        # Generates building with loadshape that is combination of multiple loadshapes, one for each use section of the building. Each loadshape is multiplied
        # by the magnitude of that use section of the multi-use building, then all added together and divided by the total magnitude for the whole building

        total_magnitude = building_list[0].magnitude
        total_loadshape = [j * building_list[0].magnitude for j in building_list[0].loadshape]
        total_avg_loadshape = [j * building_list[0].magnitude for j in building_list[0].avgLoadshape]

        for i in range(1, len(building_list)):
            total_magnitude += building_list[i].magnitude
            add_loadshape = [j * building_list[i].magnitude for j in building_list[i].loadshape]
            add_avg_loadshape = [j * building_list[i].magnitude for j in building_list[i].avgLoadshape]
            total_loadshape = [total_loadshape[j] + add_loadshape[j] for j in range(len(total_loadshape))]
            total_avg_loadshape = [total_avg_loadshape[j] + add_avg_loadshape[j] for j in range(len(total_avg_loadshape))]

        total_loadshape = [j / total_magnitude for j in total_loadshape]
        total_avg_loadshape = [j / total_magnitude for j in total_avg_loadshape]
        total_loadshape = np.array(total_loadshape)
        total_avg_loadshape = np.array(total_avg_loadshape)

        self.magnitude = total_magnitude

        super().__init__(total_loadshape, total_avg_loadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)