from ecoengine import EcosizerEngine, getListOfModels, SimulationRun, getAnnualSimLSComparison
import time


#########################################################################################################
rhoCp = 8.353535 
W_TO_BTUHR = 3.412142
W_TO_BTUMIN = W_TO_BTUHR/60.
W_TO_TONS = 0.000284345
TONS_TO_KBTUHR = 12.
watt_per_gal_recirc_factor = 100 
KWH_TO_BTU = 3412.14
RECIRC_LOSS_MAX_BTUHR = 1080 * (watt_per_gal_recirc_factor * W_TO_BTUHR)


# regular sizing and 3 day simulation
aquaFractLoadUp = 0.21
aquaFractShed   = 0.8
storageT_F = 150
loadShiftSchedule        = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1] #assume this loadshape for annual simulation every day
csvCreate = False
hpwhModel ='MODELS_NyleC90A_SP'
tmModel ='MODELS_ColmacCxA_10_MP'
minuteIntervals = 15
sizingSchematic = 'paralleltank'
simSchematic = 'paralleltank'

def createCSV(simRun : SimulationRun, simSchematic, kGperkWh, loadshift_title, start_vol):
    csv_filename = f'{simSchematic}_LS_simResult_{hpwhModel}.csv'
    if loadshift_title == False:
        csv_filename = f'{simSchematic}_NON_LS_simResult_{hpwhModel}.csv'
    simRun.writeCSV(csv_filename)

hpwh_for_sizing = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 150,
            supplyT_F       = 120,
            storageT_F      = storageT_F,
            loadUpT_F       = 150,
            percentUseable  = 0.9, 
            aquaFract       = 0.4, 
            aquaFractLoadUp = aquaFractLoadUp,
            aquaFractShed   = aquaFractShed,
            schematic       = sizingSchematic, 
            buildingType   = 'multi_family',
            returnT_F       = 0, 
            flowRate       = 0,
            gpdpp           = 25,
            safetyTM        = 1.75,
            defrostFactor   = 1, 
            compRuntime_hr  = 16, 
            nApt            = 110, 
            Wapt            = 60,
            loadShiftSchedule        = loadShiftSchedule,
            loadUpHours     = 3,
            doLoadShift     = True,
            loadShiftPercent       = 0.8
        )

start_time = time.time()
simRun_from_sized = hpwh_for_sizing.getSimRun()

end_time = time.time()
duration = end_time - start_time
print("Execution time for simple simulation run:", duration, "seconds")

print('+++++++++++++++++++++++++++++++++++++++')
print('SIZING RESULTS')
print('+++++++++++++++++++++++++++++++++++++++')
print('recirc loss', hpwh_for_sizing.building.recirc_loss)
PVol_G_atStorageT = hpwh_for_sizing.getSizingResults()[0] 
PCap_kBTUhr = hpwh_for_sizing.getSizingResults()[1] 
if simSchematic == 'multipass' or simSchematic == 'primaryrecirc':
    PCap_kBTUhr += (hpwh_for_sizing.building.recirc_loss * 1.75 / 1000)
print('PVol_G_atStorageT = ',PVol_G_atStorageT)
print('PCap_kBTUhr = ',PCap_kBTUhr)

TMVol_G = None
TMCap_kW = None
if sizingSchematic == 'swingtank' or sizingSchematic == 'paralleltank':
    TMVol_G = hpwh_for_sizing.getSizingResults()[2] 
    TMCap_kW = hpwh_for_sizing.getSizingResults()[3]/W_TO_BTUHR
    print('TMVol_G = ',TMVol_G)
    print('TMCap_kW = ',TMCap_kW)
print('+++++++++++++++++++++++++++++++++++++++')

# Annual simulation based on sizing from last:

# print("starting LS section using sizes")
# hpwh_ls = EcosizerEngine(
#             incomingT_F     = 50,
#             magnitudeStat  = 150,
#             supplyT_F       = 120,
#             storageT_F      = storageT_F,
#             loadUpT_F       = 150,
#             percentUseable  = 0.9, 
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

# if csvCreate:
#     createCSV(simRun_nls, simSchematic, kGperkWh_nonLS, False, start_vol)
# print('=========================================================')
# print("LS to non-LS diff:", kGperkWh_nonLS - kGperkWh, "=", simResultArray[3])

# # print(getListOfModels())

# if csvCreate:
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

print("starting LS section using sizes")
hpwh_ls = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 1500,
            supplyT_F       = 120,
            storageT_F      = storageT_F,
            loadUpT_F       = 150,
            percentUseable  = 0.9, 
            aquaFract       = 0.4, 
            aquaFractLoadUp = aquaFractLoadUp,
            aquaFractShed   = aquaFractShed,
            schematic       = simSchematic, 
            buildingType   = 'multi_family',
            returnT_F       = 0, 
            flowRate       = 0,
            gpdpp           = 25,
            safetyTM        = 1.75,
            defrostFactor   = 1, 
            compRuntime_hr  = 16, 
            nApt            = 110, 
            Wapt            = 60,
            nBR             = [0,50,30,20,0,0],
            loadShiftSchedule        = loadShiftSchedule,
            loadUpHours     = 3,
            doLoadShift     = True,
            loadShiftPercent       = 0.8,
            PVol_G_atStorageT = PVol_G_atStorageT, 
            PCap_kW = PCap_kBTUhr/W_TO_BTUHR, 
            TMVol_G = TMVol_G, 
            TMCap_kW = TMCap_kW,
            annual = True,
            climateZone = 1,
            systemModel = hpwhModel,
            tmModel = tmModel
        )

start_vol = 0.4*PVol_G_atStorageT
start_time = time.time()

simRun_ls = hpwh_ls.getSimRun(initPV=0.4*PVol_G_atStorageT, initST=135, minuteIntervals = minuteIntervals, nDays = 365, exceptOnWaterShortage = False)
# simResultArray = hpwh_ls.getSimRun(minuteIntervals = 1, nDays = 3, optimizeNLS = False)


end_time = time.time()
duration = end_time - start_time
print("Program execution time for annual simulation:", duration, "seconds")

if csvCreate:
    csv_filename = f'{simSchematic}_LS_simResult_{hpwhModel}.csv'
    simRun_ls.writeCSV(csv_filename)

# swing_sizer = EcosizerEngine(
#             incomingT_F     = 50,
#             magnitudeStat  = 90,
#             supplyT_F       = 120,
#             storageT_F      = 149,
#             loadUpT_F       = 149,
#             percentUseable  = 0.95, 
#             aquaFract       = 0.4, 
#             aquaFractLoadUp = 0.2,
#             aquaFractShed   = 0.8,
#             schematic       = 'swingtank', 
#             buildingType   = 'multi_family',
#             gpdpp           = 25,
#             safetyTM        = 1.75,
#             defrostFactor   = 1,
#             compRuntime_hr  = 16, 
#             nApt            = 85, 
#             Wapt            = 100,
#             loadShiftSchedule        = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
#             loadUpHours     = 3,
#             doLoadShift     = True,
#             loadShiftPercent       = 0.95
#         )
# simResult = swing_sizer.getSimRun()
# # print(simResult[0][:10])
# # print(simResult[1][-10:])
# # print(simResult[2][-65:-55])
# # print(simResult[3][800:810])
# # print(simResult[4][-10:-4])
# # print(simResult[5][-200:-190])
# # print(simResult[6][800:803])
# print("===============================================")
# #print(hpwh.plotStorageLoadSim(minuteIntervals = 15, nDays = 365, return_as_div = False))
# # parallel_sizer = EcosizerEngine(
# #             incomingT_F     = 50,
# #             magnitudeStat  = 500,
# #             supplyT_F       = 120,
# #             storageT_F      = 150,
# #             percentUseable  = 0.9, 
# #             aquaFract       = 0.4, 
# #             schematic       = 'swingtank', 
# #             buildingType   = 'multi_family',
# #             returnT_F       = 0, 
# #             flowRate       = 0,
# #             gpdpp           = 25,
# #             safetyTM        = 1.75,
# #             defrostFactor   = 1, 
# #             compRuntime_hr  = 16, 
# #             nApt            = 351, 
# #             Wapt            = 100,
# #             doLoadShift     = False,
# #         )




