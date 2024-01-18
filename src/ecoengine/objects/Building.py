import os
import json
import numpy as np
import csv
from ecoengine.constants.Constants import *

class Building:
    def __init__(self, magnitude, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        
        self._checkParams(magnitude, incomingT_F, supplyT_F, returnT_F, flowRate, ignoreRecirc, loadshape, avgLoadshape)
        
        # Does not check loadshape as that is checked in buildingCreator
        self.magnitude = magnitude
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
        self.monthlyCityWaterT_F = []
        
        if not self.climateZone is None:
            # add city water tempuratures to simRun
            with open(os.path.join(os.path.dirname(__file__), '../data/climate_data/InletWaterTemperatures_ByClimateZone.csv'), 'r') as cw_file:
                csv_reader = csv.reader(cw_file)
                next(csv_reader) # get past header row
                for i in range(12):
                    cw_row = next(csv_reader)
                    self.monthlyCityWaterT_F.append(float(cw_row[self.climateZone - 1]))

    def _checkParams(self, magnitude, incomingT_F, supplyT_F, returnT_F, flowRate, ignoreRecirc, loadshape, avgLoadshape):
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
        if not (isinstance(magnitude, int) or isinstance(magnitude, float)) or magnitude < 0:
            raise Exception("Magnitude must be a number larger than 0.")
        if max(loadshape) <= 1./16. or max(avgLoadshape) <= 1./16.:
            raise Exception("The Ecosizer was designed to size for systems " +\
                            "with peaking loads. The input load here is too "+\
                            "flat to meet the recommended design conditions. "+\
                            "We recommend sizing to meet the daily load in 16 "+\
                            "hours.")
        
    def setToAnnualLS(self):
        raise Exception("Annual loadshape not available for this building type. This feature is only available for multi-family buildings.")
    def setToDailyLS(self):
        raise Exception("setToDailyLS() feature is not available for this building type. This feature is only available for multi-family buildings.")
    def isAnnualLS(self):
        return False
    def getClimateZone(self):
        return self.climateZone
    
    def getLowestOAT(self, month = None):
        if self.climateZone is None:
            return None
        if month is None:
            with open(os.path.join(os.path.dirname(__file__), '../data/climate_data/DryBulbTemperatures_ByClimateZone.csv'), 'r') as oat_file:
                oat_reader = csv.reader(oat_file)
                next(oat_reader)# Skip the header row
                lowest_oat = float('inf')
                for oat_row in oat_reader:
                    oat_value = float(oat_row[self.climateZone - 1])
                    lowest_oat = min(lowest_oat, oat_value)
                return lowest_oat

        if month not in month_to_hour:
            raise ValueError("Invalid month specified. Please provide a valid month.")

        with open(os.path.join(os.path.dirname(__file__), '../data/climate_data/DryBulbTemperatures_ByClimateZone.csv'), 'r') as oat_file:
            temp_reader = csv.reader(oat_file)
            next(temp_reader)  # Skip the header row

            month_hours = month_to_hour[month]
            lowest_oat = float('inf')

            for row_number, t_row in enumerate(temp_reader, start=1):
                if row_number in month_hours:
                    t_value = float(t_row[self.climateZone - 1])
                    lowest_oat = min(lowest_oat, t_value)

            return lowest_oat
        
    def getHighestOAT(self, month = None):
        if self.climateZone is None:
            return None
        if month is None:
            with open(os.path.join(os.path.dirname(__file__), '../data/climate_data/DryBulbTemperatures_ByClimateZone.csv'), 'r') as oat_file:
                oat_reader = csv.reader(oat_file)
                next(oat_reader)# Skip the header row
                highest_oat = float('-inf')
                for oat_row in oat_reader:
                    oat_value = float(oat_row[self.climateZone - 1])
                    highest_oat = max(highest_oat, oat_value)
                return highest_oat

        if month not in month_to_hour:
            raise ValueError("Invalid month specified. Please provide a valid month.")

        with open(os.path.join(os.path.dirname(__file__), '../data/climate_data/DryBulbTemperatures_ByClimateZone.csv'), 'r') as oat_file:
            temp_reader = csv.reader(oat_file)
            next(temp_reader)  # Skip the header row

            month_hours = month_to_hour[month]
            highest_oat = float('-inf')

            for row_number, t_row in enumerate(temp_reader, start=1):
                if row_number in month_hours:
                    t_value = float(t_row[self.climateZone - 1])
                    highest_oat = max(highest_oat, t_value)

            return highest_oat
        
    def getLowestIncomingT_F(self):
        if self.climateZone is None:
            return self.incomingT_F
        with open(os.path.join(os.path.dirname(__file__), '../data/climate_data/InletWaterTemperatures_ByClimateZone.csv'), 'r') as inlet_file:
            temp_reader = csv.reader(inlet_file)
            next(temp_reader)# Skip the header row
            lowest_t = float('inf')
            for t_row in temp_reader:
                t_value = float(t_row[self.climateZone - 1])
                lowest_t = min(lowest_t, t_value)
            return lowest_t        
        
    def getIncomingWaterT(self, i : int, interval_length : int = 15, month : int = None):
        """
        returns incoming water temperature (F) at interval i of a year for intervals of interval_length minutes

        Parameters
        ----------
        i : int
            interval of the simulation
        interval_length : int
            length of intervals in minutes. Must be 1, 15, or 60
        month : int
            if filled out, ignores interval and just returns incoming water temperature for the specified month (numbered 1-12)

        Returns
        -------
        waterT_F : float
            The incoming water temperature (F) at interval i of the simulation 
        """
        if len(self.monthlyCityWaterT_F) == 0:
            return self.incomingT_F # default city water temp
        elif not month is None:
            return self.monthlyCityWaterT_F[month - 1]
        else:
        #     hourOfYear = i // (60/interval_length)
        #     for max_hour, month in max_hour_to_month.items():
        #         if hourOfYear < max_hour:
        #             return self.monthlyCityWaterT_F[month]
        # raise Exception("Cold water temperature data not available past one year.") 
            dayOfYear = (i // (60/interval_length)) // 24
            if dayOfYear < 31:
                # jan
                return self.monthlyCityWaterT_F[0]
            elif dayOfYear < 59:
                # feb
                return self.monthlyCityWaterT_F[1]
            elif dayOfYear < 90:
                # mar
                return self.monthlyCityWaterT_F[2]
            elif dayOfYear < 120:
                # apr
                return self.monthlyCityWaterT_F[3]
            elif dayOfYear < 151:
                # may
                return self.monthlyCityWaterT_F[4]
            elif dayOfYear < 181:
                # jun
                return self.monthlyCityWaterT_F[5]
            elif dayOfYear < 212:
                # jul
                return self.monthlyCityWaterT_F[6]
            elif dayOfYear < 243:
                # aug
                return self.monthlyCityWaterT_F[7]
            elif dayOfYear < 273:
                # sep
                return self.monthlyCityWaterT_F[8]
            elif dayOfYear < 304:
                # oct
                return self.monthlyCityWaterT_F[9]
            elif dayOfYear < 334:
                # nov
                return self.monthlyCityWaterT_F[10]
            elif dayOfYear < 365:
                # dec
                return self.monthlyCityWaterT_F[11]
            else:
                raise Exception("Cold water temperature data not available past one year.")
            
    def getAvgIncomingWaterT(self):
        """
        Returns the average incoming water temperature for the year in fahrenheit as a float

        Returns
        -------
        waterT_F : float
            The average incoming water temperature (F) of the simulation 
        """
        if len(self.monthlyCityWaterT_F) == 0:
            return self.incomingT_F # default city water temp
        else:
            return ((self.monthlyCityWaterT_F[0]*31) + (self.monthlyCityWaterT_F[1]*28) + (self.monthlyCityWaterT_F[2]*31) + (self.monthlyCityWaterT_F[3]*30) \
                + (self.monthlyCityWaterT_F[4]*31) + (self.monthlyCityWaterT_F[5]*30) + (self.monthlyCityWaterT_F[6]*31) + (self.monthlyCityWaterT_F[7]*31) \
                + (self.monthlyCityWaterT_F[8]*30) + (self.monthlyCityWaterT_F[9]*31) + (self.monthlyCityWaterT_F[10]*30) + (self.monthlyCityWaterT_F[11]*31)) / 365

class MensDorm(Building):
    def __init__(self, n_students, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        magnitude = n_students * 23.6 # ASHREA GPD per student from maximum daily usage
        super().__init__(magnitude, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class WomensDorm(Building):
    def __init__(self, n_students, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        magnitude = n_students * 19.6 # ASHREA GPD per student from maximum daily usage
        super().__init__(magnitude, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class Motel(Building):
    def __init__(self, n_units, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        magnitude = n_units * 21.4 # ASHREA GPD per unit from maximum daily usage
        super().__init__(magnitude, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class NursingHome(Building):
    def __init__(self, n_beds, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        magnitude = n_beds * 23.4 # ASHREA GPD per bed from maximum daily usage
        super().__init__(magnitude, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class OfficeBuilding(Building):
    def __init__(self, n_people, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        magnitude = n_people * 2.1 # ASHREA GPD per person from maximum daily usage
        super().__init__(magnitude, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class FoodServiceA(Building):
    def __init__(self, n_meals, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        magnitude = n_meals * 11.032 # ASHREA GPD per meal per hour
        super().__init__(magnitude, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class FoodServiceB(Building):
    def __init__(self, n_meals, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        magnitude = n_meals * 6.44 # ASHREA GPD per meal per hour from maximum daily usage
        super().__init__(magnitude, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class Apartment(Building):
    def __init__(self, n_units, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        magnitude = n_units * 54.6 # ASHREA GPD per unit from maximum daily usage
        super().__init__(magnitude, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class ElementarySchool(Building):
    def __init__(self, n_students, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        magnitude = n_students * 1.34 # ASHREA GPD per student from maximum daily usage
        super().__init__(magnitude, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class JuniorHigh(Building):
    def __init__(self, n_students, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        magnitude = n_students * 3.75 # ASHREA GPD per student from maximum daily usage
        super().__init__(magnitude, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

class SeniorHigh(Building):
    def __init__(self, n_students, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc):
        magnitude = n_students * 3.26 # ASHREA GPD per student from maximum daily usage
        super().__init__(magnitude, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)
    
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
            
        magnitude = gpdpp * n_people # gpdpp * number_of_people

        # recalculate recirc_loss with different method if applicable
        if not ignoreRecirc and not nApt is None and not Wapt is None and (nApt > 0 and Wapt > 0):
            # nApt * Wapt will overwrite recirc_loss so it doesn't matter what numbers we put in for returnT_F, flowRate
            super().__init__(magnitude, loadshape, avgLoadshape, incomingT_F, supplyT_F, None, None, climate, ignoreRecirc = True)
            self.recirc_loss = nApt * Wapt * W_TO_BTUHR
        else:
            super().__init__(magnitude, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)

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

    def isAnnualLS(self):
        return len(self.loadshape) == 8760

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

        magnitude = total_magnitude

        super().__init__(magnitude, total_loadshape, total_avg_loadshape, incomingT_F, supplyT_F, returnT_F, flowRate, climate, ignoreRecirc)