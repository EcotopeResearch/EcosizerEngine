from ecoengine import getWeatherStations, EcosizerEngine, getListOfModels, SimulationRun, getAnnualSimLSComparison, PrefMapTracker, UtilityCostTracker, get_oat_buckets
import time
import math
from plotly.offline import plot
from plotly.graph_objs import Figure, Scatter
import os
from ecoengine.engine.SystemCreator import createSystem
from ecoengine.engine.BuildingCreator import createBuilding
from ecoengine.engine.Simulator import simulate
from numpy import around, flipud
import numpy as np
import pandas as pd


def make_oupput_file(hpwh : EcosizerEngine, file_name, schem : str, npep: int):

    print(f"+++++++++++{file_name}+++++++++++")
    print(hpwh.system.getOutputCapacity(kW = True))
    simRun = simulate(hpwh.system, hpwh.building, minuteIntervals = 1, nDays = 3, exceptOnWaterShortage=False)
    # try:
    #     load_sim = simRun.plotStorageLoadSim(True, include_tank_temps = True)

    #     # [storage_data, capacity_data, hours, startIndex] = system.primaryCurve(building)
    #     # storage_data = around(flipud(storage_data),2)
    #     # capacity_data = around(flipud(capacity_data),2)
    #     # hours = around(flipud(hours),2)
    #     # startIndex = len(storage_data)-startIndex-1
    #     curve = hpwh.plotSizingCurve(True)
    #     # curve = system.getPrimaryCurveAndSlider(storage_data, capacity_data, startIndex, hours, returnAsDiv = True)

    #     title = "sims"

    #     html_content = f"""<!DOCTYPE html>
    #     <html>
    #     <head>
    #         <meta charset="UTF-8">
    #         <meta name="viewport" content="width=device-width, initial-scale=1.0">
    #         <title>{title}</title>
    #         <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    #     </head>
    #     <body>
    #         <br>
    #         Sized for {schem} for {npep} people building and {hpwh.system.compRuntime_hr} hr run time.
    #         <br><br><br>
    #         {load_sim}
    #         <br><br><br>
    #         {curve}
    #     </body>
    #     </html>"""
    # except Exception as e:
    #     html_content = f"""<!DOCTYPE html>
    #     <html>
    #     <head>
    #         <meta charset="UTF-8">
    #         <meta name="viewport" content="width=device-width, initial-scale=1.0">
    #         <title>{title}</title>
    #         <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    #     </head>
    #     <body>
    #         Simulation and sizing failed! {e}
    #     </body>
    #     </html>"""
    # with open(f"outputs/{file_name}_output.html", "w", encoding="utf-8") as f:
    #     f.write(html_content)
    # simRun.writeCSV(f"outputs/{file_name}.csv")

# Read input CSV and process each row
df = pd.read_csv('input.csv')

for index, row in df.iterrows():
    # Extract parameters from the row
    row_id = row['id']
    npep = row['npep']
    supplyT_F = row['supplyT_F']
    storageT_F = row['storageT_F']
    onFrac = row['onFrac']
    offFract = row['offFract']
    onT = row['onT']
    offT = row['offT']
    outletLoadUpT = row['outletLoadUpT']
    onFractLoadUp = row['onFractLoadUp']
    offFractLoadUp = row['offFractLoadUp']
    onLoadUpT = row['onLoadUpT']
    offLoadUpT = row['offLoadUpT']
    onFracShed = row['onFracShed']
    offFractShed = row['offFractShed']
    onShedT = row['onShedT']
    offShedT = row['offShedT']
    schematic = row['schematic']
    recirc_flow_gpm = row['recirc_flow_gpm']
    recirc_return_temp = row['recirc_return_temp']
    doLoadShift = row['doLoadShift']
    compRuntime_hr = row['compRuntime_hr']


    # Create EcosizerEngine with parameters from this row
    hpwh = EcosizerEngine(
            magnitudeStat = npep,
            gpdpp = 25,
            supplyT_F = supplyT_F,
            storageT_F = storageT_F,
            incomingT_F=50,
            percentUseable = 0.95,
            onFract = onFrac,
            offFract= offFract,
            onT = onT,
            offT= offT,
            onFractLoadUp = onFractLoadUp,
            offFractLoadUp= offFractLoadUp,
            outletLoadUpT=outletLoadUpT,
            onLoadUpT= onLoadUpT,
            offLoadUpT = offLoadUpT,
            onFractShed = onFracShed,
            offFractShed= offFractShed,
            onShedT = onShedT,
            offShedT= offShedT,
            loadUpHours = 2, # might need to change for future
            schematic = schematic,
            buildingType  = 'multi_family',
            loadShiftSchedule = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,1,1],
            doLoadShift   = doLoadShift,
            flowRate=recirc_flow_gpm,
            returnT_F=recirc_return_temp,
            compRuntime_hr=compRuntime_hr
    )

    # print(hpwh.getSizingResults())

    # Create filename based on row data
    ls_suffix = 'ls' if doLoadShift else 'notls'
    file_name = f"{row_id}_{schematic}_{ls_suffix}_new"

    make_oupput_file(hpwh, file_name, schematic, npep)