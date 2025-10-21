from ecoengine import getWeatherStations, EcosizerEngine, getListOfModels, SimulationRun, getAnnualSimLSComparison, PrefMapTracker, UtilityCostTracker, get_oat_buckets
import time
import math
from plotly.offline import plot
from plotly.graph_objs import Figure, Scatter
import os
from ecoengine.engine.SystemCreator import createSystem
from ecoengine.engine.BuildingCreator import createBuilding
from ecoengine.engine.Simulator import simulate

check_building = createBuilding(
            incomingT_F     = 50,
            magnitudeStat  = 200,
            supplyT_F       = 120,
            buildingType   = 'multi_family',
            nApt            = 150, 
            returnT_F       = 115,
            flowRate        = 6,
            gpdpp           = 25
        )

print("==========creating nrtp==========")
nortp_system = createSystem(
    schematic   = 'singlepass_norecirc', 
    building    = check_building, 
    storageT_F  = 150, 
    defrostFactor   = 1, 
    percentUseable  = .8, 
    compRuntime_hr  = 16, 
    aquaFract   = 0.4,
)
print("==========creating rtp===========")
rtp_system = createSystem(
    schematic   = 'sprtp', 
    building    = check_building, 
    storageT_F  = 150, 
    defrostFactor   = 1, 
    percentUseable  = .8, 
    compRuntime_hr  = 16, 
    aquaFract   = 0.4,
)
print("==========created rtp===========")
print(f"rtp_system.PCap_kBTUhr > nortp_system.PCap_kBTUhr : {rtp_system.PCap_kBTUhr} > {nortp_system.PCap_kBTUhr}")
print(f"rtp_system.getSizingResults() : {rtp_system.getSizingResults()}")
print(f"nortp_system.getSizingResults() : {nortp_system.getSizingResults()}")

simRun = simulate(rtp_system, check_building, minuteIntervals = 1, nDays = 3)
load_sim = simRun.plotStorageLoadSim(True)



title = "My Page"

html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
    {load_sim}
</body>
</html>"""
with open("output.html", "w", encoding="utf-8") as f:
      f.write(html_content)
print(rtp_system.primaryCurve(check_building))
# hpwh = EcosizerEngine(
#             incomingT_F = 0, #not needed, weather weather file inlet temp is used
#             magnitudeStat = 438,
#             supplyT_F = 120,
#             storageT_F = 140, #150
#             percentUseable = 0.95, #NEED
#             aquaFract = 0.29,
#             aquaFractLoadUp = 0.04,
#             aquaFractShed = 0.79,
#             loadUpT_F = 140, #150
#             loadUpHours = 2,
#             schematic = "swingtank",
#             buildingType  = "multi_family",
#             gpdpp = 25,
#             nApt = 219,
#             Wapt = 90,
#             #loadShiftSchedule = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,1],
#             doLoadShift=False,
#             #doLoadShift   = True,
#             climateZone=61,
#             annual=False,
#             systemModel='MODELS_NyleE360_LT_C_SP',
#             PVol_G_atStorageT=3000,
#             numHeatPumps=3,
#             TMCap_kW=48, #IS THIS TRUE?
#             TMVol_G=120,  
#         )

# print(f"loadshift_capacity {round(hpwh.getLoadShiftCapacity(),2)}")
# print(f"shed_hours {round(hpwh.getNumShedHours(),2)}")

# print(get_oat_buckets(None, 19)[65])
# print(get_oat_buckets(None, 19)[65.0])
# print((-12 // 5) * 5)
# print(get_oat_buckets(90210))


