from .systemConfigUtils import hrToMinList, roundList, hrTo15MinList
from ecoengine.constants.Constants import *
import math
import csv
import os

class UtilityCostTracker:
    """
    Attributes
    ----------
    monthly_base_charge : float
        monthly base charge for having electricity connected ($/month)
    pk_start_hour : int (in range 0-23)
        start hour of the day which peak demand pricing applies
    pk_end_hour : int (in range pk_start_hour-24)
        end hour of the day which peak demand pricing applies
    pk_demand_charge : float
        peak demand pricing ($/kW)
    pk_energy_charge : float
        peak energy pricing ($/kWh)
    off_pk_demand_charge : float
        off-peak demand pricing ($/kW)
    off_pk_energy_charge : float
        off-peak energy pricing ($/kWh)
    """
    def __init__(self, monthly_base_charge, pk_start_hour, pk_end_hour, pk_demand_charge, pk_energy_charge, off_pk_demand_charge, off_pk_energy_charge, csv_path = None):
        self.demand_charge_map = {}
        self.demand_period_chart = [0]*8760
        self.energy_charge_by_hour = []
        if csv_path is None:
            self._checkParams(monthly_base_charge, pk_start_hour, pk_end_hour, pk_demand_charge, pk_energy_charge, off_pk_demand_charge, off_pk_energy_charge)
            self.monthly_base_charge= monthly_base_charge
            self.pk_start_hour = pk_start_hour
            self.pk_end_hour = pk_end_hour
            self.pk_energy_charge = pk_energy_charge
            self.off_pk_energy_charge = off_pk_energy_charge
            self.createDemandChargeMap(off_pk_demand_charge, pk_demand_charge)
            # print(self.demand_period_chart)
        else:
            csv_array = []
            header = []
            with open(csv_path, 'r') as utility_file:
                utility_reader = csv.reader(utility_file)
                header = next(utility_reader)
                csv_array = [row for row in utility_reader]
            self._processCSV(csv_array, header)
        print(self.demand_charge_map)
        print(self.getAllDemandPeriodKeys())
                

    def _checkParams(self, monthly_base_charge, pk_start_hour, pk_end_hour, pk_demand_charge, pk_energy_charge, off_pk_demand_charge, off_pk_energy_charge):
        if not (isinstance(monthly_base_charge, int) or isinstance(monthly_base_charge, float)):
            raise Exception("Error: monthly base charge must be a number.")
        if not (isinstance(pk_start_hour, int) or isinstance(pk_start_hour, float)) or pk_start_hour < 0 or pk_start_hour > 23:
            raise Exception("Error: peak start hour must be a number between 0 and 23.")
        if not (isinstance(pk_end_hour, int) or isinstance(pk_end_hour, float)) or pk_end_hour < pk_start_hour or pk_end_hour > 24:
            raise Exception("Error: peak end hour must be a number between peak start hour and 23.")
        if not (isinstance(pk_demand_charge, int) or isinstance(pk_demand_charge, float)):
            raise Exception("Error: peak demand charge must be a number.")
        if not (isinstance(off_pk_demand_charge, int) or isinstance(off_pk_demand_charge, float)):
            raise Exception("Error: off-peak demand charge must be a number.")
        if not (isinstance(pk_energy_charge, int) or isinstance(pk_energy_charge, float)):
            raise Exception("Error: peak energy charge must be a number.")
        if not (isinstance(off_pk_energy_charge, int) or isinstance(off_pk_energy_charge, float)):
            raise Exception("Error: off-peak energy charge must be a number.")
    
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


    def createDemandChargeMap(self, off_pk_demand_charge, pk_demand_charge):
        for i in range(24):
            if i % 2 == 0:
                self.demand_charge_map[i] = off_pk_demand_charge
            else:
                self.demand_charge_map[i] = pk_demand_charge
        for i in range(12):
            self.demand_period_chart = [(i*2)+1 if self.isIntervalInPeakPeriod(j, 60) and j in month_to_hour[i] 
                                        else i*2 if j in month_to_hour[i]
                                        else self.demand_period_chart[j]
                                        for j in range(len(self.demand_period_chart))]
            
    def getYearlyBaseCharge(self):
        return self.monthly_base_charge * 12.0
    
    def isIntervalInPeakPeriod(self, i, minuteIntervals):
        hour_of_year = math.floor(i / (60/minuteIntervals))
        hour_of_day = hour_of_year % 24
        if hour_of_day >= self.pk_start_hour and hour_of_day < self.pk_end_hour:
            # peak pricing
            return True
        # off-peak
        return False
    
    def getEnergyChargeAtInterval(self, i, minuteIntervals):
        if len(self.energy_charge_by_hour) == 8760:
            # we have a custom energy charge array
            hour_of_year = math.floor(i / (60/minuteIntervals))
            return self.energy_charge_by_hour[hour_of_year]
        if self.isIntervalInPeakPeriod(i, minuteIntervals):
            # peak pricing
            return self.pk_energy_charge
        # off-peak
        return self.off_pk_energy_charge
    
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




   