from .systemConfigUtils import hrToMinList, roundList, hrTo15MinList
from ecoengine.constants.Constants import *
import math
import csv

class UtilityCostTracker:
    """
    Attributes
    ----------
    monthly_base_charge : float
        monthly base charge for having electricity connected ($/month)
    pk_start_hour : int (in range 0-23) or list of int (in range 0-23)
        start hour of the day which peak demand pricing applies
    pk_end_hour : int (in range pk_start_hour-24) or list of int (in range pk_start_hour-24)
        end hour of the day which peak demand pricing applies
    pk_demand_charge : float or list of float
        peak demand pricing ($/kW)
    pk_energy_charge : float or list of float
        peak energy pricing ($/kWh)
    off_pk_demand_charge : float or list of float
        off-peak demand pricing ($/kW)
    off_pk_energy_charge : float or list of float
        off-peak energy pricing ($/kWh)
    start_month : int (in range 0-11) or list of int (in range 0-11)
        start month for period (defaults to 0)
    end_month : int (in range start_month+1 - 12) or list of int (in range start_month[i]+1 - 12)
        end month for period (defaults to 12)
    csv_path : str
        file path to custom pricing csv. Must have three columns titled "Energy Rate ($/kWh)", "Demand Rate ($/kW)", "Demand Period", and "Monthly Base Charge" 
        with appropriate information in each column. Defaults to None
    """
    def __init__(self, monthly_base_charge = None, pk_start_hour = None, pk_end_hour = None, pk_demand_charge = None, pk_energy_charge = None, 
                 off_pk_demand_charge = None, off_pk_energy_charge = None, start_month = 0, end_month = 12, csv_path = None):
        self.demand_charge_map = {}
        self.energy_charge_map = {}
        self.demand_period_chart = [0]*8760
        self.energy_charge_by_hour = []
        if csv_path is None:
            if not isinstance(pk_start_hour, list):
                pk_start_hour = [pk_start_hour]
            if not isinstance(pk_end_hour, list):
                pk_end_hour = [pk_end_hour]
            if not isinstance(pk_demand_charge, list):
                pk_demand_charge = [pk_demand_charge]
            if not isinstance(pk_energy_charge, list):
                pk_energy_charge = [pk_energy_charge]
            if not isinstance(off_pk_demand_charge, list):
                off_pk_demand_charge = [off_pk_demand_charge]
            if not isinstance(off_pk_energy_charge, list):
                off_pk_energy_charge = [off_pk_energy_charge]
            if not isinstance(start_month, list):
                start_month = [start_month]
            if not isinstance(end_month, list):
                end_month = [end_month]
            self._checkParams(monthly_base_charge, pk_start_hour, pk_end_hour, pk_demand_charge, pk_energy_charge, 
                              off_pk_demand_charge, off_pk_energy_charge, start_month, end_month)
            self.monthly_base_charge= monthly_base_charge
            for i in range(len(pk_start_hour)):
                self.createChargeMaps(off_pk_demand_charge[i], pk_demand_charge[i], off_pk_energy_charge[i], pk_energy_charge[i], 
                                      pk_start_hour[i], pk_end_hour[i], start_month[i], end_month[i])
        else:
            csv_array = []
            header = []
            with open(csv_path, 'r') as utility_file:
                utility_reader = csv.reader(utility_file)
                header = next(utility_reader)
                csv_array = [row for row in utility_reader]
            self._processCSV(csv_array, header)
                

    def _checkParams(self, monthly_base_charge, pk_start_hour, pk_end_hour, pk_demand_charge, pk_energy_charge, off_pk_demand_charge, off_pk_energy_charge,
                     start_month, end_month):
        if monthly_base_charge is None or not (isinstance(monthly_base_charge, int) or isinstance(monthly_base_charge, float)):
            raise Exception("Error: monthly base charge must be a number.")
        if not len(pk_start_hour) == len(pk_end_hour) == len(pk_demand_charge) == len(pk_energy_charge) == len(off_pk_demand_charge) == len(off_pk_energy_charge) == len(start_month) == len(end_month):
            raise Exception("Error: pk_start_hour, pk_end_hour, pk_demand_charge, pk_energy_charge, off_pk_demand_charge, and off_pk_energy_charge must all be the same length.")
        for i in range(len(pk_start_hour)):
            if pk_start_hour[i] is None or not (isinstance(pk_start_hour[i], int) or isinstance(pk_start_hour[i], float)) or pk_start_hour[i] < 0 or pk_start_hour[i] > 23:
                raise Exception("Error: peak start hour must be a number between 0 and 23.")
            if pk_end_hour[i] is None or not (isinstance(pk_end_hour[i], int) or isinstance(pk_end_hour[i], float)) or pk_end_hour[i] < pk_start_hour[i] or pk_end_hour[i] > 24:
                raise Exception("Error: peak end hour must be a number between peak start hour and 23.")
            if pk_demand_charge[i] is None or not (isinstance(pk_demand_charge[i], int) or isinstance(pk_demand_charge[i], float)):
                raise Exception("Error: peak demand charge must be a number.")
            if off_pk_demand_charge[i] is None or not (isinstance(off_pk_demand_charge[i], int) or isinstance(off_pk_demand_charge[i], float)):
                raise Exception("Error: off-peak demand charge must be a number.")
            if pk_energy_charge[i] is None or not (isinstance(pk_energy_charge[i], int) or isinstance(pk_energy_charge[i], float)):
                raise Exception("Error: peak energy charge must be a number.")
            if off_pk_energy_charge[i] is None or not (isinstance(off_pk_energy_charge[i], int) or isinstance(off_pk_energy_charge[i], float)):
                raise Exception("Error: off-peak energy charge must be a number.")
            if start_month[i] is None or not isinstance(start_month[i], int):
                raise Exception("Error: start_month must be a number between 0 and 11.")
            if i == 0:
                if start_month[i] != 0:
                    raise Exception("Error: first start_month must be 0.")
            elif start_month[i] != end_month[i-1]:
                raise Exception("Error: current start_month must be equal to previous end month.")
            if end_month[i] is None or not isinstance(end_month[i], int) or end_month[i] <= start_month[i]:
                raise Exception("Error: end_month must be a number between (start_month+1) - 12.")
            if i == len(end_month) - 1 and end_month[i] != 12:
                raise Exception("Error: final end_month must be 12.")
    
    def _processCSV(self, csv_array : list, header : list):
        if len(csv_array) != 8760:
            raise Exception(f"Error: length of utility calculation csv must be 8760. Instead recieved a length of {len(csv_array)}.")
        result = [item for item in ["Energy Rate ($/kWh)","Demand Rate ($/kW)","Demand Period","Monthly Base Charge"] if item not in header]
        if len(result) != 0:
            raise Exception(f"Missing Columns from utility calculation csv: {result}.")
        try:
            self.monthly_base_charge = float(csv_array[0][header.index("Monthly Base Charge")])
        except ValueError:
                raise Exception(f"Unable to read value in row 0 of csv. Please check values for Monthly Base Charge in this row.")
        
        energy_charge_index = header.index("Energy Rate ($/kWh)")
        demand_charge_index = header.index("Demand Rate ($/kW)")
        demand_period_index = header.index("Demand Period")
        for i, row in enumerate(csv_array):
            try:
                self.energy_charge_by_hour.append(float(row[energy_charge_index]))
                self.demand_period_chart[i] = int(row[demand_period_index])
                if not self.demand_period_chart[i] in self.demand_charge_map:
                    self.demand_charge_map[self.demand_period_chart[i]] = float(row[demand_charge_index])
            except ValueError:
                raise Exception(f"Unable to read value in row {i} of csv. Please check values for Energy Rate ($/kWh), Demand Rate ($/kW), and Demand Period in this row.")


    def createChargeMaps(self, off_pk_demand_charge, pk_demand_charge, off_pk_energy_charge, pk_energy_charge, pk_start_hour, pk_end_hour, start_month, end_month):
        """
        Adds to self.demand_charge_map, self.energy_charge_map, and self.demand_period_chart
        """
        for i in range(start_month * 2, end_month * 2):
            if i % 2 == 0:
                self.demand_charge_map[i] = off_pk_demand_charge
                self.energy_charge_map[i] = off_pk_energy_charge
            else:
                self.demand_charge_map[i] = pk_demand_charge
                self.energy_charge_map[i] = pk_energy_charge
        for i in range(start_month, end_month):
            self.demand_period_chart = [(i*2)+1 if self.isIntervalInPeakPeriod(j, 60, pk_start_hour, pk_end_hour) and j in month_to_hour[i] 
                                        else i*2 if j in month_to_hour[i]
                                        else self.demand_period_chart[j]
                                        for j in range(len(self.demand_period_chart))]
    def getYearlyBaseCharge(self):
        return self.monthly_base_charge * 12.0
    
    def isIntervalInPeakPeriod(self, i, minuteIntervals, pk_start_hour, pk_end_hour):
        hour_of_year = math.floor(i / (60/minuteIntervals))
        hour_of_day = hour_of_year % 24
        if hour_of_day >= pk_start_hour and hour_of_day < pk_end_hour:
            # peak pricing
            return True
        # off-peak
        return False
    
    def getEnergyChargeAtInterval(self, i, minuteIntervals):
        hour_of_year = math.floor(i / (60/minuteIntervals))
        if len(self.energy_charge_by_hour) == 8760:
            # we have a custom energy charge array
            return self.energy_charge_by_hour[hour_of_year]
        demand_period = self.demand_period_chart[hour_of_year]
        return self.energy_charge_map[demand_period]
    
    def getDemandPricingPeriod(self, i, minuteIntervals):
        hour_of_year = math.floor(i / (60/minuteIntervals))
        return self.demand_period_chart[hour_of_year]
    
    def getAllDemandPeriodKeys(self):
        return list(self.demand_charge_map.keys())
    
    def getDemandChargeForPeriod(self, period_key, max_avg_kW):
        if period_key in self.demand_charge_map:
            return self.demand_charge_map[period_key] * max_avg_kW
        else:
            raise Exception(f"{period_key} is not a defined demand period for the utility calculation.")
        
    # def exportAnnualCSV(self, csv_path : str, as_array = False):




   