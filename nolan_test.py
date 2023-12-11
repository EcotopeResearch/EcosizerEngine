from ecoengine import EcosizerEngine, getListOfModels, SimulationRun, getAnnualSimLSComparison, PrefMapTracker
import time
import math

pm = PrefMapTracker(None, 'MODELS_ColmacCxA_20_C_SP', numHeatPumps=1, usePkl=True, prefMapOnly = True)

print(pm.default_input_low)
print(pm.default_output_low)
for i in range(10):
    print(f"pm.getCapacity({25},{63+i},{140}) {pm.getCapacity(25,63+i,140)}")

print(f"pm.getCapacity({25},{40},{148}) {pm.getCapacity(25,40,148)}")
print(f"pm.getCapacity({25},{83},{134}) {pm.getCapacity(25,83,134)}")
# W_TO_BTUHR = 3.412142
# hpwh_for_sizing = EcosizerEngine(
#             incomingT_F     = 33.5,
#             magnitudeStat  = 222.95,
#             supplyT_F       = 120,
#             storageT_F      = 150,
#             percentUseable  = 0.85, 
#             aquaFract       = 0.4,
#             schematic       = 'paralleltank', 
#             buildingType   = 'multi_family',
#             safetyTM        = 1.75,
#             defrostFactor   = 1, 
#             compRuntime_hr  = 16, 
#             nBR             = [20, 30, 25, 15, 10, 0],
#             standardGPD     = 'ecoMark',
#             nApt            = 100, 
#             Wapt            = 100,
#             loadUpHours     = 3,
#             doLoadShift     = False
#         )

# # print('+++++++++++++++++++++++++++++++++++++++')
# # print('SIZING RESULTS')
# # print('+++++++++++++++++++++++++++++++++++++++')
# TMVol_G = None 
# TMCap_kW = None
# # print('recirc loss', hpwh_for_sizing.building.recirc_loss)
# sizing_result = hpwh_for_sizing.getSizingResults()
# PVol_G_atStorageT = sizing_result[0] 
# PCap_kBTUhr = sizing_result[1] 
# if len(sizing_result) > 2:
#     TMVol_G = sizing_result[2] 
#     TMCap_kW = sizing_result[3]/W_TO_BTUHR
# # print('PVol_G_atStorageT = ',PVol_G_atStorageT)
# # print('PCap_kBTUhr = ',PCap_kBTUhr)
# # print('TMVol_G = ',TMVol_G)
# # print('TMCap_kW = ',TMCap_kW)

# hpwh = EcosizerEngine(
#             incomingT_F     = 33.5,
#             magnitudeStat  = 222.95,
#             supplyT_F       = 120,
#             storageT_F      = 150,
#             percentUseable  = 0.85, 
#             aquaFract       = 0.4,
#             schematic       = 'paralleltank', 
#             buildingType   = 'multi_family',
#             defrostFactor   = 1, 
#             compRuntime_hr  = 16, 
#             nBR             = [20, 30, 25, 15, 10, 0],
#             standardGPD     = 'ecoMark',
#             nApt            = 100, 
#             Wapt            = 100,
#             doLoadShift     = False,
#             PVol_G_atStorageT = PVol_G_atStorageT, 
#             PCap_kW = PCap_kBTUhr/W_TO_BTUHR, 
#             TMVol_G = TMVol_G, 
#             TMCap_kW = TMCap_kW,
#             annual = True,
#             climateZone = 17,
#             systemModel = "MODELS_Mitsubishi_QAHV"
#         )
# simRun = hpwh.getSimRun(minuteIntervals = 60, nDays = 365, exceptOnWaterShortage=False)
# simRun.writeCSV("here.csv")

#########################################################################################################
# rhoCp = 8.353535 
# W_TO_BTUHR = 3.412142
# W_TO_BTUMIN = W_TO_BTUHR/60.
# W_TO_TONS = 0.000284345
# TONS_TO_KBTUHR = 12.
# watt_per_gal_recirc_factor = 100 
# KWH_TO_BTU = 3412.14
# RECIRC_LOSS_MAX_BTUHR = 1080 * (watt_per_gal_recirc_factor * W_TO_BTUHR)


# # regular sizing and 3 day simulation
# aquaFractLoadUp = 0.2
# aquaFractShed   = 0.8
# storageT_F = 150
# loadShiftSchedule        = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,1,1,1] #assume this loadshape for annual simulation every day
# csvCreate = False
# hpwhModel ='MODELS_Mitsubishi_QAHV'
# tmModel ='MODELS_Mitsubishi_QAHV'
# minuteIntervals = 15
# sizingSchematic = 'singlepass_norecirc'
# simSchematic = 'singlepass_rtp'

# def createCSV(simRun : SimulationRun, simSchematic, kGperkWh, loadshift_title, start_vol):
#     csv_filename = f'{simSchematic}_LS_simResult_{hpwhModel}.csv'
#     if loadshift_title == False:
#         csv_filename = f'{simSchematic}_NON_LS_simResult_{hpwhModel}.csv'
#     simRun.writeCSV(csv_filename)

# hpwh_for_sizing = EcosizerEngine(
#             incomingT_F     = 50,
#             magnitudeStat  = 150,
#             supplyT_F       = 120,
#             storageT_F      = storageT_F,
#             loadUpT_F       = storageT_F + 10,
#             percentUseable  = 0.85, 
#             aquaFract       = 0.4, 
#             aquaFractLoadUp = aquaFractLoadUp,
#             aquaFractShed   = aquaFractShed,
#             schematic       = sizingSchematic, 
#             buildingType   = 'multi_family',
#             returnT_F       = 0, 
#             flowRate       = 0,
#             gpdpp           = 25,
#             safetyTM        = 1.75,
#             defrostFactor   = 1, 
#             compRuntime_hr  = 16, 
#             nApt            = 110, 
#             Wapt            = 60,
#             loadShiftSchedule        = loadShiftSchedule,
#             loadUpHours     = 3,
#             doLoadShift     = True,
#             loadShiftPercent       = 1
#         )

# print('+++++++++++++++++++++++++++++++++++++++')
# print('SIZING RESULTS')
# print('+++++++++++++++++++++++++++++++++++++++')
# print('recirc loss', hpwh_for_sizing.building.recirc_loss)
# PVol_G_atStorageT = hpwh_for_sizing.getSizingResults()[0] 
# PCap_kBTUhr = hpwh_for_sizing.getSizingResults()[1] 
# if simSchematic == 'multipass' or simSchematic == 'primaryrecirc':
#     PCap_kBTUhr += (hpwh_for_sizing.building.recirc_loss * 1.75 / 1000)
# print('PVol_G_atStorageT = ',PVol_G_atStorageT)
# print('PCap_kBTUhr = ',PCap_kBTUhr)

# if csvCreate:
#     #test plot output
#     fig = hpwh_for_sizing.plotSizingCurve()
#     fig.write_html('Z:\\sizingplotTEST.html')
# ##########################################################################################
# start_time = time.time()
# simRun_from_sized = hpwh_for_sizing.getSimRun()

# end_time = time.time()
# duration = end_time - start_time
# print("Execution time for simple simulation run:", duration, "seconds")

# print('+++++++++++++++++++++++++++++++++++++++')
# print('SIZING RESULTS')
# print('+++++++++++++++++++++++++++++++++++++++')
# print('recirc loss', hpwh_for_sizing.building.recirc_loss)
# PVol_G_atStorageT = hpwh_for_sizing.getSizingResults()[0] 
# PCap_kBTUhr = hpwh_for_sizing.getSizingResults()[1] 
# if simSchematic == 'multipass' or simSchematic == 'primaryrecirc':
#     PCap_kBTUhr += (hpwh_for_sizing.building.recirc_loss * 1.75 / 1000)
# print('PVol_G_atStorageT = ',PVol_G_atStorageT)
# print('PCap_kBTUhr = ',PCap_kBTUhr)
# print('Vtrig_normal = ',hpwh_for_sizing.system.Vtrig_normal)
# print('Vtrig_shed = ',hpwh_for_sizing.system.Vtrig_shed)
# print('Vtrig_loadUp = ',hpwh_for_sizing.system.Vtrig_loadUp)

# TMVol_G = None
# TMCap_kW = None
# if sizingSchematic == 'swingtank' or sizingSchematic == 'paralleltank':
#     TMVol_G = hpwh_for_sizing.getSizingResults()[2] 
#     TMCap_kW = hpwh_for_sizing.getSizingResults()[3]/W_TO_BTUHR
#     print('TMVol_G = ',TMVol_G)
#     print('TMCap_kW = ',TMCap_kW)
# print('+++++++++++++++++++++++++++++++++++++++')

# # Annual simulation based on sizing from last:

# print("starting LS section using sizes")
# hpwh_ls = EcosizerEngine(
#             incomingT_F     = 50,
#             magnitudeStat  = 150,
#             supplyT_F       = 120,
#             storageT_F      = storageT_F,
#             loadUpT_F       = storageT_F + 10,
#             percentUseable  = 1, 
#             aquaFract       = 0.4, 
#             aquaFractLoadUp = aquaFractLoadUp,
#             aquaFractShed   = aquaFractShed,
#             schematic       = simSchematic, 
#             buildingType   = 'multi_family',
#             returnT_F       = 0, 
#             flowRate       = 0,
#             gpdpp           = 25,
#             safetyTM        = 1.75,
#             defrostFactor   = 1, 
#             compRuntime_hr  = 16, 
#             nApt            = 110, 
#             Wapt            = 60,
#             nBR             = [0,50,30,20,0,0],
#             loadShiftSchedule        = loadShiftSchedule,
#             loadUpHours     = 3,
#             doLoadShift     = True,
#             loadShiftPercent       = 0.8,
#             PVol_G_atStorageT = PVol_G_atStorageT, 
#             PCap_kW = PCap_kBTUhr/W_TO_BTUHR, 
#             TMVol_G = TMVol_G, 
#             TMCap_kW = TMCap_kW,
#             annual = True,
#             climateZone = 1,
#             systemModel = hpwhModel,
#             tmModel = tmModel
#         )

# start_vol = 0.4*PVol_G_atStorageT
# start_time = time.time()

# simResultArray = hpwh_ls.getSimRunWithkWCalc(initPV=0.4*PVol_G_atStorageT, initST=135, minuteIntervals = minuteIntervals, nDays = 365, optimizeNLS = False)
# lsCap = simResultArray[2]
# print(lsCap)

# # simResultArray = hpwh_ls.getSimRun(minuteIntervals = 1, nDays = 3, optimizeNLS = False)


# end_time = time.time()
# duration = end_time - start_time
# print("Program execution time for annual simulation:", duration, "seconds")

# simRun_ls = simResultArray[0]


# print('=========================================================')
# print('average city watertemp is', simRun_ls.getAvgIncomingWaterT())
# print('=======================FOR LS============================')
# loadshift_capacity = simResultArray[2]
# kGperkWh = simRun_ls.getkGCO2Sum()/loadshift_capacity
# print('ls kg_sum is', simRun_ls.getkGCO2Sum())
# print('ls kGperkWh is', kGperkWh)
# print('annual COP:', simRun_ls.getAnnualCOP())
# print('annual COP (boundry):', simRun_ls.getAnnualCOP(True))

# if csvCreate:
#     createCSV(simRun_ls, simSchematic, kGperkWh, True, start_vol)

# print('=====================FOR NON LS==========================')
# simRun_nls = simResultArray[1]

# kGperkWh_nonLS = simRun_nls.getkGCO2Sum()/loadshift_capacity
# print('non-ls kg_sum is', simRun_nls.getkGCO2Sum())
# print('non-ls kGperkWh is', kGperkWh_nonLS)
# print('annual COP:', simRun_nls.getAnnualCOP())
# print('annual COP (boundry):', simRun_nls.getAnnualCOP(True))

# # if csvCreate:
# #     createCSV(simRun_nls, simSchematic, kGperkWh_nonLS, False, start_vol)
# print('=========================================================')
# print("LS to non-LS diff:", kGperkWh_nonLS - kGperkWh, "=", simResultArray[3])

# # print(getListOfModels())
# if False:
# # Generate the content for the HTML div
#     content = getAnnualSimLSComparison(simRun_ls, simRun_nls)

#     # Create the HTML content
#     html_content = f"""<!DOCTYPE html>
# <html>
# <head>
#     <title>My Webpage</title>
#     <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
# </head>
# <body>
# <div>
# {content}
# </div>
# </body>
# </html>
# """

#     # Write the HTML content to the file
#     file_name = f'{simSchematic}_simResult_{hpwhModel}.html'
#     with open(file_name, 'w') as file:
#         file.write(html_content)

##############################################################################################
# # PVol_G_atStorageT = 400
# print("starting LS section using sizes")
# loadshape = [18.52, 32.27, 11.51, 9.96, 19.01, 51.56, 324.4, 339.9, 308.27, 198.04, 373.78, 259.31, 195.34, 294.24, 345.65, 441.84, 310.58, 417.3, 330.08, 96.58, 10.62, 12.03, 14.5, 27.32]
# loadshape = [math.ceil(x) for x in loadshape]
# totalDemand = sum(loadshape)
# print('total HW demand', totalDemand)
# normalizedLoad = [x / sum(loadshape) for x in loadshape]
# print('normalized Load', normalizedLoad)
# nPep = 200
# vol = nPep * 6
# kbtu = nPep * 0.8
# hpwh = EcosizerEngine(
#                      incomingT_F     = 50,
#                      magnitudeStat  = nPep,
#                      supplyT_F       = 120,
#                      storageT_F      = 150,
#                      percentUseable  = 0.9,
#                      aquaFract       = 0.4,
#                      schematic       = "singlepass_rtp",
#                      buildingType   = 'multi_family',
#                      flowRate       = 0,
#                      gpdpp           = 25,
#                      safetyTM        = 1.75,
#                      defrostFactor   = 1,
#                      compRuntime_hr  = 16,
#                      nApt            = int(100),
#                      Wapt            = int(60),
#                      loadShiftSchedule = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,1],
#                      loadUpHours     = int(3),
#                      doLoadShift     = True,
#                      loadShiftPercent= 0.95,
#                      aquaFractLoadUp = 0.2,
#                      aquaFractShed   = 0.8,
#                      loadUpT_F       = 160,
#                      PVol_G_atStorageT = vol,
#                      PCap_kW =  kbtu / 3.41,
#                      TMVol_G = TMVol_G,
#                      TMCap_kW = TMCap_kW,
#                      annual = True,
#                      climateZone = 1,
#                      systemModel = "MODELS_Mitsubishi_QAHV")

# start_vol = vol
# start_time = time.time()

# simRun_ls = hpwh.getSimRun(initPV=start_vol, initST=135, minuteIntervals = minuteIntervals, nDays = 365, exceptOnWaterShortage = False)

# end_time = time.time()
# duration = end_time - start_time
# print("Program execution time for annual simulation:", duration, "seconds")

# if csvCreate:
#     csv_filename = f'{simSchematic}_thing_simResult_{hpwhModel}.csv'
#     simRun_ls.writeCSV(csv_filename)

###################################################################################################################################################

# swing_sizer = EcosizerEngine(
#             incomingT_F     = 50,
#             magnitudeStat  = 90,
#             supplyT_F       = 120,
#             storageT_F      = 149,
#             loadUpT_F       = 159,
#             percentUseable  = 0.95, 
#             aquaFract       = 0.4, 
#             aquaFractLoadUp = 0.2,
#             aquaFractShed   = 0.8,
#             schematic       = 'multipass_norecirc', 
#             buildingType   = 'multi_family',
#             gpdpp           = 25,
#             safetyTM        = 1.75,
#             defrostFactor   = 1,
#             compRuntime_hr  = 16, 
#             nApt            = 85, 
#             Wapt            = 60,
#             loadShiftSchedule        = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
#             loadUpHours     = 3,
#             doLoadShift     = True,
#             loadShiftPercent       = 0.95,
#             PVol_G_atStorageT= 2000,
#             numHeatPumps= 4,
#             systemModel="MODELS_ColmacCxA_20_MP",
#             annual=True,
#             zipCode=90001
#         )
# simResult = swing_sizer.getSimRun(minuteIntervals=15,nDays=365)
# print(simResult.LS_sched)
# # print(simResult[0][:10])
# # print(simResult[1][-10:])
# # print(simResult[2][-65:-55])
# # print(simResult[3][800:810])
# # print(simResult[4][-10:-4])
# # print(simResult[5][-200:-190])
# # print(simResult[6][800:803])
# print("===============================================")
#print(hpwh.plotStorageLoadSim(minuteIntervals = 15, nDays = 365, return_as_div = False))
# parallel_sizer = EcosizerEngine(
#             incomingT_F     = 50,
#             magnitudeStat  = 500,
#             supplyT_F       = 120,
#             storageT_F      = 150,
#             percentUseable  = 0.9, 
#             aquaFract       = 0.4, 
#             schematic       = 'swingtank', 
#             buildingType   = 'multi_family',
#             returnT_F       = 0, 
#             flowRate       = 0,
#             gpdpp           = 25,
#             safetyTM        = 1.75,
#             defrostFactor   = 1, 
#             compRuntime_hr  = 16, 
#             nApt            = 351, 
#             Wapt            = 100,
#             doLoadShift     = False,
#         )




