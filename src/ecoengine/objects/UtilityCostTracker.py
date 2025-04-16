from .systemConfigUtils import hrToMinList, roundList, hrTo15MinList
from ecoengine.constants.Constants import *
import math
import csv
from io import TextIOWrapper

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
        with appropriate information in each column. Defaults to None. Note that Demand Periods with odd numbered labels will be assumed to be peak periods while
        even-numbered periods will be assumed as off-peak
    include_dscnt_period : bool
        indicates whether or not the utility billing schedule includes a discounted rate period (such as overnight electrical use in British Columbia)
    dscnt_start_hour : int (in range 0-23) or list of int (in range 0-23)
        start hour of the day which discount pricing applies
    dscnt_end_hour : int (in range pk_start_hour-24) or list of int (in range pk_start_hour-24)
        end hour of the day which discount pricing applies
    discnt_demand_charge : float or list of float
        discount pricing ($/kW)
    discnt_energy_charge : float or list of float
        discount pricing ($/kWh)
    csv_file : TextIOWrapper
        an opened csv file (in place of csv_path) to be read
    """
    def __init__(self, monthly_base_charge = None, pk_start_hour = None, pk_end_hour = None, pk_demand_charge = None, pk_energy_charge = None, 
                 off_pk_demand_charge = None, off_pk_energy_charge = None, start_month = 0, end_month = 12, csv_path = None, include_dscnt_period = False,
                 dscnt_start_hour = None, dscnt_end_hour = None, discnt_demand_charge = None, discnt_energy_charge = None, csv_file : TextIOWrapper = None):
        self.demand_charge_map = {}
        self.energy_charge_map = {}
        self.is_peak_map = {}
        self.is_discount_map = {}
        self.demand_period_chart = [0]*8760
        self.energy_charge_by_hour = []
        self.include_dscnt_period = include_dscnt_period
        if csv_path is None and csv_file is None:
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
            if discnt_energy_charge is None or not isinstance(discnt_energy_charge, list):
                discnt_energy_charge = [discnt_energy_charge] * len(pk_start_hour)
            if discnt_demand_charge is None or not isinstance(discnt_demand_charge, list):
                discnt_demand_charge = [discnt_demand_charge] * len(pk_start_hour)
            if dscnt_start_hour is None or not isinstance(dscnt_start_hour, list):
                dscnt_start_hour = [dscnt_start_hour] * len(pk_start_hour)
            if dscnt_end_hour is None or not isinstance(dscnt_end_hour, list):
                dscnt_end_hour = [dscnt_end_hour] * len(pk_start_hour)
            self._checkParams(monthly_base_charge, pk_start_hour, pk_end_hour, pk_demand_charge, pk_energy_charge, 
                              off_pk_demand_charge, off_pk_energy_charge, start_month, end_month)
            self.monthly_base_charge= monthly_base_charge
            for i in range(len(pk_start_hour)):
                self._createChargeMaps(off_pk_demand_charge[i], pk_demand_charge[i], off_pk_energy_charge[i], pk_energy_charge[i], 
                                      pk_start_hour[i], pk_end_hour[i], start_month[i], end_month[i],
                                      discnt_energy_charge[i], discnt_demand_charge[i], dscnt_start_hour[i], dscnt_end_hour[i])
        else:
            csv_array = []
            header = []
            if csv_file is None:
                csv_file = open(csv_path, 'r')
            utility_reader = csv.reader(csv_file)
            header = next(utility_reader)
            csv_array = [row for row in utility_reader]
            self._processCSV(csv_array, header) # TODO make process CSV work with discount periods
                

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
                raise Exception("Error: peak end hour must be a number between peak start hour and 24.")
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
                self.demand_period_chart[i] = int(row[demand_period_index])
                if row[energy_charge_index] is None or row[energy_charge_index] == "":
                    if not self.demand_period_chart[i] in self.demand_charge_map:
                        raise Exception(f"Missing 'Energy Rate ($/kWh)' in row {i} of csv.")
                    self.energy_charge_by_hour.append(self.energy_charge_map[self.demand_period_chart[i]])
                else:
                    self.energy_charge_by_hour.append(float(row[energy_charge_index]))
                if not self.demand_period_chart[i] in self.demand_charge_map:
                    self.demand_charge_map[self.demand_period_chart[i]] = float(row[demand_charge_index])
                    self.energy_charge_map[self.demand_period_chart[i]] = float(row[energy_charge_index])
                    self.is_peak_map[self.demand_period_chart[i]] = True if self.demand_period_chart[i] % 2 == 1 else False
                    self.is_discount_map[self.demand_period_chart[i]] = False
            except ValueError:
                raise Exception(f"Unable to read value in row {i} of csv. Please check values for Energy Rate ($/kWh), Demand Rate ($/kW), and Demand Period in this row.")


    def _createChargeMaps(self, off_pk_demand_charge, pk_demand_charge, off_pk_energy_charge, pk_energy_charge, pk_start_hour, pk_end_hour, start_month, end_month,
                          discnt_energy_charge, discnt_demand_charge, dscnt_start_hour, dscnt_end_hour):
        """
        Adds to self.demand_charge_map, self.energy_charge_map, and self.demand_period_chart
        """
        num_periods_per_day = 3 if self.include_dscnt_period else 2
        for i in range(start_month * num_periods_per_day, end_month * num_periods_per_day):
            if i % num_periods_per_day == 0:
                # Off-Peak Charges
                self.demand_charge_map[i] = off_pk_demand_charge
                self.energy_charge_map[i] = off_pk_energy_charge
                self.is_peak_map[i] = False
                self.is_discount_map[i] = False
            elif self.include_dscnt_period and i % num_periods_per_day == 2:
                # Discount Charges
                self.demand_charge_map[i] = discnt_demand_charge
                self.energy_charge_map[i] = discnt_energy_charge
                self.is_peak_map[i] = False
                self.is_discount_map[i] = True
            else:
                # Peak Charges
                self.demand_charge_map[i] = pk_demand_charge
                self.energy_charge_map[i] = pk_energy_charge
                self.is_peak_map[i] = True
                self.is_discount_map[i] = False
        for i in range(start_month, end_month):
            self.demand_period_chart = [(i*num_periods_per_day)+1 if self.isIntervalInPeriod(j, 60, pk_start_hour, pk_end_hour) and j in month_to_hour[i] 
                                        else (i*num_periods_per_day)+2 if self.isIntervalInPeriod(j, 60, dscnt_start_hour, dscnt_end_hour) and j in month_to_hour[i]
                                        else i*num_periods_per_day if j in month_to_hour[i]
                                        else self.demand_period_chart[j]
                                        for j in range(len(self.demand_period_chart))]
            
    def getYearlyBaseCharge(self):
        """
        Returns
        -------
        charge : float
            The anual base energy charge in dollars
        """
        return self.monthly_base_charge * 12.0
    
    def isIntervalInPeriod(self, i, minuteIntervals, start_hour, end_hour):
        if start_hour is None or end_hour is None:
            return False 
        hour_of_year = math.floor(i / (60/minuteIntervals))
        hour_of_day = hour_of_year % 24
        if end_hour < start_hour:
            # period is split between days
            if hour_of_day >= start_hour or hour_of_day < end_hour:
                return True
        elif hour_of_day >= start_hour and hour_of_day < end_hour:
            # peak pricing
            return True
        # off-peak
        return False
    
    def getEnergyChargeAtInterval(self, i, minuteIntervals):
        """
        Parameters
        ----------
        i : int
            The interval number from a simulation
        minuteIntervals : int
            the minutes per time interval for the simulation.

        Returns
        -------
        energy_charge : float
            The energy charge rate for the interval in dollars per kWh
        """
        hour_of_year = math.floor(i / (60/minuteIntervals))
        if len(self.energy_charge_by_hour) == 8760:
            # we have a custom energy charge array
            return self.energy_charge_by_hour[hour_of_year]
        demand_period = self.demand_period_chart[hour_of_year]
        return self.energy_charge_map[demand_period]
    
    def getDemandPricingPeriod(self, i, minuteIntervals):
        """
        Parameters
        ----------
        i : int
            The interval number from a simulation
        minuteIntervals : int
            the minutes per time interval for the simulation.

        Returns
        -------
        demand_period_key : int
            The demand period key for the interval. Use this key in the getDemandChargeForPeriod() function to get demand period cost.
        """
        hour_of_year = math.floor(i / (60/minuteIntervals))
        return self.demand_period_chart[hour_of_year]
    
    def getAllDemandPeriodKeys(self):
        return list(self.demand_charge_map.keys())
    
    def getDemandChargeForPeriod(self, period_key, max_avg_kW):
        """
        Parameters
        ----------
        period_key : int
            The key for the demand period in the UtilityCostTracker
        max_avg_kW : float
            the maximum average kW draw durring the demand period

        Returns
        -------
        cost : float
            The total dollar amount that will be charged for the demand period
        """
        if period_key in self.demand_charge_map:
            return self.demand_charge_map[period_key] * max_avg_kW
        else:
            raise Exception(f"{period_key} is not a defined demand period for the utility calculation.")
        
    def exportAnnualCSV(self, csv_path : str, return_as_array : bool = False):
        """
        Parameters
        ----------
        csv_path : str
            the file path for the output csv file
        return_as_array : bool
            returns as an array representation of the Utility Cost Tracker instead of outputting a csv

        Returns
        -------
        output_array : list
            a csv list form of the annual CSV if return_as_array is set to True.
            This is a list of lists length 8760x5 where for every hour i in range(0,8760)...
            output_array[i+1][0] is a string representation of the date,
            output_array[i+1][1] is the demand period,
            output_array[i+1][2] is the Energy Rate ($/kWh) of the demand period if i is the first hour in the demand period,
            output_array[i+1][3] is the Demand Rate ($/kW) of the demand period if i is the first hour in the demand period,
            output_array[1][4] is the monthly base charge applicable to the entire year
        """
        header = [["Date","Demand Period","Energy Rate ($/kWh)","Demand Rate ($/kW)","Monthly Base Charge"]]
        body = [[None,None,None,None,self.monthly_base_charge]]
        for i in range(8759):
            body.append([None,None,None,None,None])
        seen_demand_periods = []
        month = 0
        day_of_month = 1
        for i in range(8760):
            if i == month_to_hour[month].stop:
                month += 1
                day_of_month = 1
            elif i != 0 and i % 24 == 0:
                day_of_month += 1
            body[i][0] = f"{month_names[month]} {day_of_month}, {i % 24}:00"
            demand_period_at_hour = self.getDemandPricingPeriod(i, 60)
            body[i][1] = demand_period_at_hour
            if not demand_period_at_hour in seen_demand_periods:
                body[i][2] = self.energy_charge_map[demand_period_at_hour]
                body[i][3] = self.demand_charge_map[demand_period_at_hour]
                seen_demand_periods.append(demand_period_at_hour)
        full_csv_array = header + body
        if return_as_array:
            return full_csv_array
        
        # Write the transposed_result to a CSV file
        with open(csv_path, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)  
            csvwriter.writerow(["Note: Demand Periods with odd-numbered labels will be assumed to be peak periods while even-numbered periods will be assumed as off-peak. Delete this line before importing CSV to Ecosizer Utiliy Calculation"])
            for row in full_csv_array:
                csvwriter.writerow(row)
            print("successfully exported to csv")