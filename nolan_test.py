from ecoengine import EcosizerEngine
# # import numpy as np
hpwh = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            storageT_F      = 150,
            loadUpT_F       = 150,
            percentUseable  = 0.9, 
            aquaFract       = 0.4, 
            aquaFractLoadUp = 0.21,
            aquaFractShed   = 0.8,
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
            loadShiftSchedule        = [1,1,1,1,1,1,0,0,0,0,0,0,0,1,1,0,0,0,0,1,1,1,1,1],
            loadUpHours     = 3,
            doLoadShift     = True,
            loadShiftPercent       = 0.8,
            setpointTM_F    = 130,
            TMonTemp_F      = 120,
            offTime_hr      = 0.333
        )

# print(hpwh.getSizingResults())
# # hpwh = EcosizerEngine(  incomingT_F     = 50,
# #                     magnitudeStat  = 1,
# #                     supplyT_F       = 120,
# #                     storageT_F      = 180,
# #                     percentUseable  = .8, 
# #                     aquaFract       = .4,
# #                     loadshape= np.array([0,40,0,0,0,0,300,0,0,0,0,0,0,0,0,82,0,0,0,17,0,0,0,0])/439,
# #                     schematic       = 'swingtank', 
# #                     buildingType   = 'multi_family',
# #                     returnT_F       = 100, 
# #                     flowRate       = 3,
# #                     gpdpp           = 439,
# #                     standardGPD = None,
# #                     safetyTM        = 1.75,
# #                     defrostFactor   = 1, 
# #                     compRuntime_hr  = 16, 
# #                     nApt            = 1, 
# #                     # Wapt            = 100,
# #                     # loadShiftSchedule        = [1,1,1,1,1,1,0,0,0,0,0,0,0,1,1,0,0,0,0,1,1,1,1,1], #loadshift schedule
# #                     doLoadShift     = False,
# #                     # loadShiftPercent       = 0.8,
# #                     offTime_hr = 0.5,
# #                     TMonTemp_F = 125
# # )

# # outlist = hpwh.getSizingResults()
# # hpwh.plotStorageLoadSim()
# # # [x_data, y_data, hours, recInd] = hpwh.primaryCurve()
# # # plotSimDiv = hpwh.plotStorageLoadSim()

# # print("Heating capacity (PCap_kBTUhr)", outlist[1])
# # print("pl Tank Volume (TMVol_G)", outlist[2])
# # print("Tank Volume (PVol_G_atStorageT)",outlist[0])
# # print("Swing Resistance Element (TMCap_kBTUhr)", outlist[3])
# # print("Swing Tank Volume (TMVol_G) CA", outlist[4])

# # # [x_data, y_data, hours, recInd] = swinghpwh.primaryCurve()
# # # print("x_data",x_data)
# # # print("y_data",y_data)
# # # print("hours",hours)
# # # print("recInd",recInd)

# # # print("========================================================================================================")

# # # parallelhpwh = EcosizerEngine(  incomingT_F     = 50,
# # #                     magnitudeStat  = 100,
# # #                     supplyT_F       = 120,
# # #                     storageT_F      = 150,
# # #                     percentUseable  = 0.8, 
# # #                     aquaFract       = 0.4, 
# # #                     schematic       = 'paralleltank', 
# # #                     buildingType   = 'multi_family',
# # #                     returnT_F       = 0, 
# # #                     flowRate       = 0,
# # #                     gpdpp           = 25,
# # #                     safetyTM        = 1.75,
# # #                     defrostFactor   = 1, 
# # #                     compRuntime_hr  = 16, 
# # #                     nApt            = 100, 
# # #                     Wapt            = 100,
# # #                     loadShiftSchedule        = [1,1,1,1,1,1,0,0,0,0,0,0,0,1,1,0,0,0,0,1,1,1,1,1],
# # #                     doLoadShift     = True,
# # #                     loadShiftPercent       = 0.8,
# # #                     setpointTM_F    = 130,
# # #                     TMonTemp_F      = 120,
# # #                     offTime_hr      = 0.333

# # # )

# # # outlist = parallelhpwh.getSizingResults()

# # # print("Heating capacity (PCap_kBTUhr)", outlist[1])
# # # print("Swing Tank Volume (TMVol_G)", outlist[2])
# # # print("Tank Volume (PVol_G_atStorageT)",outlist[0])
# # # print("Swing Resistance Element (TMCap_kBTUhr)", outlist[3])

# # # [x_data, y_data, hours, recInd] = parallelhpwh.primaryCurve()
# # # print("x_data",x_data)
# # # print("y_data",y_data)
# # # print("hours",hours)
# # # print("recInd",recInd)



