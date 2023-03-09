from abc import ABC, abstractmethod
# Functions to gather data from JSON
import os
import json
import numpy as np

from constants.Constants import *

class Building(ABC):
    def __init__(self, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate):
        # if not hasattr(inputs, 'loadshape'):
        #     raise Exception("Loadshape required.")
        # if len(inputs.loadshape) != 24:
        #     raise Exception("Loadshape must be of length 24 but instead has length of "+str(len(inputs.loadshape))+".")
        # if sum(inputs.loadshape) > 1 + 1e-3 or sum(inputs.loadshape) < 1 - 1e-3:
        #     raise Exception("Sum of the loadshape does not equal 1 but "+str(sum(inputs.loadshape))+".")
        # if any(x < 0 for x in inputs.loadshape):
        #     raise Exception("Can not have negative load shape values in loadshape.")
        # if any(supplyT_F <= returnT_F):
        #     raise Exception("Supply temp must be higher than return temp.")
        # if not hasattr(inputs, 'incomingT_F'):
        #     raise Exception("City water temp required.")
        # if not hasattr(inputs, 'supplyT_F'):
        #     raise Exception("Supply Temp required.")
        # if not hasattr(inputs, 'returnT_F'):
        #     raise Exception("Return Temp required.")
        # if not hasattr(inputs, 'flow_rate'):
        #     raise Exception("Flow rate required.")
        # if not hasattr(self, 'magnitude'):
        #     raise Exception("Magnitude has not been set.")
        self.loadshape = loadshape
        self.avgLoadshape = avgLoadshape
        self.incomingT_F = incomingT_F
        self.supplyT_F = supplyT_F
        self.recirc_loss = (supplyT_F - returnT_F) * flow_rate * rhoCp * 60. #BTU/HR

class MensDorm(Building):
    def __init__(self, n_students, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate):
        self.magnitude = n_students * 18.9 # ASHREA GPD per student
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)

class WomensDorm(Building):
    def __init__(self, n_students, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate):
        self.magnitude = n_students * 16.4 # ASHREA GPD per student
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)

class Motel(Building):
    def __init__(self, n_units, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate):
        self.magnitude = n_units * 28.8 # ASHREA GPD per unit
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)

class NursingHome(Building):
    def __init__(self, n_beds, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate):
        self.magnitude = n_beds * 20.1 # ASHREA GPD per bed
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)

class OfficeBuilding(Building):
    def __init__(self, n_people, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate):
        self.magnitude = n_people * 1.11 # ASHREA GPD per person
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)

class FoodServiceA(Building):
    def __init__(self, n_meals, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate):
        self.magnitude = n_meals * 11.032 # ASHREA GPD per meal
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)

class FoodServiceB(Building):
    def __init__(self, n_meals, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate):
        self.magnitude = n_meals * 6.288 # ASHREA GPD per meal
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)

class Apartment(Building):
    def __init__(self, n_units, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate):
        self.magnitude = n_units * 42.8 # ASHREA GPD per unit
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)

class ElementarySchool(Building):
    def __init__(self, n_students, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate):
        self.magnitude = n_students * 1.081 # ASHREA GPD per student
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)

class JuniorHigh(Building):
    def __init__(self, n_students, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate):
        self.magnitude = n_students * 3.27 # ASHREA GPD per student
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)

class SeniorHigh(Building):
    def __init__(self, n_students, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate):
        self.magnitude = n_students * 3.02 # ASHREA GPD per student
        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)
    
class MultiFamily(Building):
    def __init__(self, n_people, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate, gpdpp, nBR, nApt, Wapt):
        # supplyT_F, incomingT_F, returnT_F, flow_rate, loadshape, avgLoadshape, n_people, gpdpp, nApt, Wapt, nBR = None
        # if not hasattr(inputs, 'gpdpp'):
        #     raise Exception("GPDPP required.")
        with open(os.path.join(os.path.dirname(__file__), '../data/load_shapes/multi_family.json')) as json_file:
            dataDict = json.load(json_file)
            # Check if gpdpp is a string and look up by key
            if isinstance(gpdpp, str): # if the inputs here is a string get the get the gpdpp

                if gpdpp.lower() == "ca" :
                    if nBR is None or sum(nBR) == 0 or len(nBR) != 6:
                        raise Exception("Cannot get the gpdpp for the CA data set without knowning the number of units by bedroom size for 0 BR (studios) through 5+ BR, the list must be of length 6 in that order.")

                    # Count up the gpdpp for each bedroom type
                    daily_totals = np.zeros(365)
                    for ii in range(0,6):
                        daily_totals += nBR[ii] * np.array(dataDict['ca_gpdpp'][str(ii) + "br"]) # daily totals is gpdpp * bedroom

                    # Get the 98th percentile day divide by the number of people rounded up to an integer.
                    gpdpp = round(np.percentile(daily_totals,98)/ sum(nBR), 1)

                # Else look up by normal key function
                else:
                    gpdpp = dataDict['gpdpp'][gpdpp][0] # TODO error handle
            
            self.magnitude = gpdpp * n_people # gpdpp * number_of_people

        super().__init__(loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)
        # recalculate recirc_loss with different method if applicable
        if(nApt > 0 and Wapt > 0):
            self.recirc_loss = nApt * Wapt * W_TO_BTUHR
    