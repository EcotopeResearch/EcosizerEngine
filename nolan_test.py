from ecoengine import EcosizerEngine

hpwh = EcosizerEngine(  incomingT_F     = 50,
                    magnitudeStat  = 100,
                    supplyT_F       = 120,
                    storageT_F      = 150,
                    percentUseable  = 0.8, 
                    aquaFract       = 0.4, 
                    schematic       = 'paralleltank', 
                    buildingType   = 'multi_family',
                    returnT_F       = 0, 
                    flowRate       = 0,
                    gpdpp           = 25,
                    safetyTM        = 1.75,
                    defrostFactor   = 1, 
                    compRuntime_hr  = 16, 
                    nApt            = 100, 
                    Wapt            = 100,
                    loadShiftSchedule        = [1,1,1,1,1,1,0,0,0,0,0,0,0,1,1,0,0,0,0,1,1,1,1,1], #loadshift schedule
                    doLoadShift     = False,
                    loadShiftPercent       = 0.8
)

outlist = hpwh.getSizingResults()
# [x_data, y_data, hours, recInd] = hpwh.primaryCurve()
# plotSimDiv = hpwh.plotStorageLoadSim()

print("Heating capacity (PCap_kBTUhr)", outlist[1])
print("pl Tank Volume (TMVol_G)", outlist[2])
print("Tank Volume (PVol_G_atStorageT)",outlist[0])
print("Swing Resistance Element (TMCap_kBTUhr)", outlist[3])

# [x_data, y_data, hours, recInd] = swinghpwh.primaryCurve()
# print("x_data",x_data)
# print("y_data",y_data)
# print("hours",hours)
# print("recInd",recInd)

# print("========================================================================================================")

# parallelhpwh = EcosizerEngine(  incomingT_F     = 50,
#                     magnitudeStat  = 100,
#                     supplyT_F       = 120,
#                     storageT_F      = 150,
#                     percentUseable  = 0.8, 
#                     aquaFract       = 0.4, 
#                     schematic       = 'paralleltank', 
#                     buildingType   = 'multi_family',
#                     returnT_F       = 0, 
#                     flowRate       = 0,
#                     gpdpp           = 25,
#                     safetyTM        = 1.75,
#                     defrostFactor   = 1, 
#                     compRuntime_hr  = 16, 
#                     nApt            = 100, 
#                     Wapt            = 100,
#                     loadShiftSchedule        = [1,1,1,1,1,1,0,0,0,0,0,0,0,1,1,0,0,0,0,1,1,1,1,1],
#                     doLoadShift     = True,
#                     loadShiftPercent       = 0.8,
#                     setpointTM_F    = 130,
#                     TMonTemp_F      = 120,
#                     offTime_hr      = 0.333

# )

# outlist = parallelhpwh.getSizingResults()

# print("Heating capacity (PCap_kBTUhr)", outlist[1])
# print("Swing Tank Volume (TMVol_G)", outlist[2])
# print("Tank Volume (PVol_G_atStorageT)",outlist[0])
# print("Swing Resistance Element (TMCap_kBTUhr)", outlist[3])

# [x_data, y_data, hours, recInd] = parallelhpwh.primaryCurve()
# print("x_data",x_data)
# print("y_data",y_data)
# print("hours",hours)
# print("recInd",recInd)



