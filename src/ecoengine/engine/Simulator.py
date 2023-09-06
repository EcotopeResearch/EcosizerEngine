from ecoengine.objects.SystemConfig import SystemConfig
from ecoengine.objects.Building import Building
from ecoengine.objects.systemConfigUtils import *
from ecoengine.objects.SimulationRun import *
from ecoengine.objects.PrefMapTracker import *
import os
import json
from ecoengine.constants.Constants import KWH_TO_BTU, W_TO_BTUHR
import csv

    
def simulate(system : SystemConfig, building : Building, initPV=None, initST=None, minuteIntervals = 1, nDays = 3, exceptOnWaterShortage = True):
    """
    Implimented seperatly for Swink Tank systems 
    Inputs
    ------
    system : SystemConfig
        the HPWH system object for the annual simulation
    building : Building
        the building object the system configuration is being simulated for.
    initPV : float
        Primary volume at start of the simulation
    initST : float
        Swing tank temperature at start of the simulation. Not used in this instance of the function
    minuteIntervals : int
        the number of minutes the duration each interval timestep for the simulation will be
    nDays : int
        the number of days the for duration of the entire simulation will be
    exceptOnWaterShortage : boolean
        Throws an exception if Primary Storage runs out of water. Otherwise returns failed simulation run
    
    Returns
    -------
    simRun : SimulationRun
        resulting simulation run object containing information from each timestep interval of the simulation for further analysis
    """

    simRun = system.getInitializedSimulation(building, initPV, initST, minuteIntervals, nDays)

    # do preliminary work for annual simulation
    if nDays == 365:
        
        # check for climateZone
        if building.climateZone is None:
            raise Exception("Cannot run annual simulation with out setting building climate zone to be a number between 1 and 16.")
        
        # add city water tempuratures to simRun
        with open(os.path.join(os.path.dirname(__file__), '../data/climate_data/InletWaterTemperatures_ByClimateZone.csv'), 'r') as cw_file:
            csv_reader = csv.reader(cw_file)
            next(csv_reader) # get past header row
            cw_temp_by_month = []
            for i in range(12):
                cw_row = next(csv_reader)
                cw_temp_by_month.append(float(cw_row[building.climateZone - 1]))
            simRun.setMonthlyCityWaterT_F(cw_temp_by_month)

        system.setLoadUPVolumeAndTrigger(simRun.getIncomingWaterT(0)) # set initial load up volume and aquafraction adjusted for useful energy

    with open(os.path.join(os.path.dirname(__file__), '../data/climate_data/DryBulbTemperatures_ByClimateZone.csv'), 'r') as oat_file:
        with open(os.path.join(os.path.dirname(__file__), '../data/climate_data/kGperkWh_ByClimateZone.csv'), 'r') as kG_file:
            oat_reader = csv.reader(oat_file)
            kG_reader = csv.reader(kG_file)
            next(oat_reader)
            next(kG_reader)
            oat_F = None

            # Run the "simulation"
            try:
                for i in range(len(simRun.hwDemand)):
                    if nDays == 365:
                        if i%(60/minuteIntervals) == 0: # we have reached the next hour and should thus take the next OAT
                            oat_row = next(oat_reader)
                            oat_F = float(oat_row[building.climateZone - 1])
                            simRun.addOat(oat_F)
                            kG_row = next(kG_reader)
                        system.runOneSystemStep(simRun, i, minuteIntervals = minuteIntervals, oat = oat_F)
                        simRun.addCap(system.getOutputCapacity(kW=True), system.getInputCapacity(kW=True))
                        kGofCO2 = simRun.getCapIn(i)*(simRun.pRun[i]/60)
                        if(hasattr(simRun, 'tmRun')):
                            # we are keeping track of temperature maintenance power as well
                            simRun.addTMCap(system.getTMOutputCapacity(kW=True), system.getTMInputCapacity(kW=True))
                            kGofCO2 += simRun.getTMCapIn(i)*(simRun.tmRun[i]/60)
                        kGofCO2 *= float(kG_row[building.climateZone-1])
                        simRun.addKGCO2(kGofCO2)   
                    else:
                        system.runOneSystemStep(simRun, i, minuteIntervals = minuteIntervals)
            
            except Exception as e:
                if not exceptOnWaterShortage and str(e) == "Primary storage ran out of Volume!":
                    print(f"{str(e)} Returning simulation result for analysis.")
                else:
                    raise

    system.resetToDefaultCapacity()
    return simRun