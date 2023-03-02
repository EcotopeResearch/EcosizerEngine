from abc import ABC, abstractmethod
# Functions to gather data from JSON
import os
import json
import numpy as np

from constants.Constants import *

class Building(ABC):
    def __init__(self, hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude):
        self.city_water_temp = city_water_temp
        self.magnitude = magnitude
        self.recirc_loss = (hot_water_temp - return_water_temp) * flow_rate * rhoCp * 60. #BTU/HR

    def getLoadShape(self, file_name, shape):
        with open(os.path.join(os.path.dirname(__file__), '../data/load_shapes/' + file_name + '.json')) as json_file:
            dataDict = json.load(json_file)
            try: 
                return dataDict['loadshapes'][shape]
            except KeyError:
                raise KeyError("Mapping key not found for loadshapes, valid keys are: 'Stream', or 'Stream_Avg'")

class MensDorm(Building):
    def __init__(self, hot_water_temp, city_water_temp, return_water_temp, flow_rate, n_students):
        magnitude = n_students * 18.9
        super().__init__(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude)

    def getLoadShape(self, shape = 'Stream'):
        return super().getLoadShape('mens_dorm', shape)

class WomensDorm(Building):
    def __init__(self, hot_water_temp, city_water_temp, return_water_temp, flow_rate, n_students):
        magnitude = n_students * 16.4
        super().__init__(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude)

    def getLoadShape(self, shape = 'Stream'):
        return super().getLoadShape('womens_dorm', shape)

class Motel(Building):
    def __init__(self, hot_water_temp, city_water_temp, return_water_temp, flow_rate, n_units):
        magnitude = n_units * 28.8
        super().__init__(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude)

    def getLoadShape(self, shape = 'Stream'):
        return super().getLoadShape('motel', shape)

class NursingHome(Building):
    def __init__(self, hot_water_temp, city_water_temp, return_water_temp, flow_rate, n_beds):
        magnitude = n_beds * 20.1
        super().__init__(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude)

    def getLoadShape(self, shape = 'Stream'):
        return super().getLoadShape('nursing_home', shape)

class OfficeBuilding(Building):
    def __init__(self, hot_water_temp, city_water_temp, return_water_temp, flow_rate, n_people):
        magnitude = n_people * 1.11
        super().__init__(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude)

    def getLoadShape(self, shape = 'Stream'):
        return super().getLoadShape('office_building', shape)

class FoodServiceA(Building):
    def __init__(self, hot_water_temp, city_water_temp, return_water_temp, flow_rate, n_meals):
        magnitude = n_meals * 11.032
        super().__init__(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude)

    def getLoadShape(self, shape = 'Stream'):
        return super().getLoadShape('food_service_a', shape)

class FoodServiceB(Building):
    def __init__(self, hot_water_temp, city_water_temp, return_water_temp, flow_rate, n_meals):
        magnitude = n_meals * 11.032
        super().__init__(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude)

    def getLoadShape(self, shape = 'Stream'):
        return super().getLoadShape('food_service_b', shape)

class Apartment(Building):
    def __init__(self, hot_water_temp, city_water_temp, return_water_temp, flow_rate, n_units):
        magnitude = n_units * 42.8
        super().__init__(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude)

    def getLoadShape(self, shape = 'Stream'):
        return super().getLoadShape('apartment', shape)

class ElementarySchool(Building):
    def __init__(self, hot_water_temp, city_water_temp, return_water_temp, flow_rate, n_students):
        magnitude = n_students * 1.081
        super().__init__(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude)

    def getLoadShape(self, shape = 'Stream'):
        return super().getLoadShape('elementary_school', shape)

class JuniorHigh(Building):
    def __init__(self, hot_water_temp, city_water_temp, return_water_temp, flow_rate, n_students):
        magnitude = n_students * 3.27
        super().__init__(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude)

    def getLoadShape(self, shape = 'Stream'):
        return super().getLoadShape('junior_high', shape)

class SeniorHigh(Building):
    def __init__(self, hot_water_temp, city_water_temp, return_water_temp, flow_rate, n_students):
        magnitude = n_students * 3.02
        super().__init__(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude)

    def getLoadShape(self, shape = 'Stream'):
        return super().getLoadShape('senior_high', shape)
    
class MultiFamily(Building):
    def __init__(self, hot_water_temp, city_water_temp, return_water_temp, flow_rate, n_people, gpdpp, nApt, Wapt, nBR = None): #todo add nApts?
        with open(os.path.join(os.path.dirname(__file__), '../data/load_shapes/multi_family.json')) as json_file:
            dataDict = json.load(json_file)
            # Check if gpdpp is a string and look up by key
            if isinstance(gpdpp, str): # if the input here is a string get the get the gpdpp

                if gpdpp.lower() == "ca" :
                    if nBR is None or sum(nBR) == 0:
                        raise Exception("Cannot get the gpdpp for the CA data set without knowning the number of units by bedroom size for 0 BR (studios) through 5+ BR, the list must be of length 6 in that order.")
                    if len(nBR) != 6:
                        raise Exception("Cannot get the gpdpp for the CA data set without knowning the number of units by bedroom size for 0 BR (studios) through 5+ BR, the list must be of length 6 in that order.")

                    # Count up the gpdpp for each bedroom type
                    daily_totals = np.zeros(365)
                    for ii in range(0,6):
                        daily_totals += nBR[ii] * np.array(dataDict['ca_gpdpp'][str(ii) + "br"]) # daily totals is gpdpp * bedroom

                    # Get the 98th percentile day divide by the number of people rounded up to an integer.
                    gpdpp = np.ceil(np.percentile(daily_totals,98)/ sum(nBR))

                # Else look up by normal key function
                else:
                    gpdpp = dataDict['gpdpp'][gpdpp][0] # TODO error handle
            
            magnitude = gpdpp * n_people

        super().__init__(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude)
        if(nApt > 0 and Wapt > 0):
            self.recirc_loss = nApt * Wapt * W_TO_BTUHR

    def getLoadShape(self, shape = 'Stream'):
        return super().getLoadShape('multi_family', shape)
    