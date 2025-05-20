from ecoengine import getWeatherStations, EcosizerEngine, getListOfModels, SimulationRun, getAnnualSimLSComparison, PrefMapTracker, UtilityCostTracker, get_oat_buckets
import time
import math
from plotly.offline import plot
from plotly.graph_objs import Figure, Scatter
import os

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

print(get_oat_buckets(None, 19)[65])
print(get_oat_buckets(None, 19)[65.0])
print((-12 // 5) * 5)
print(get_oat_buckets(90210))


