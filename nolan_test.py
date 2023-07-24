from ecoengine import EcosizerEngine, getListOfModels, SimulationRun
import time

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
hpwhModel ='MODELS_AWHSTier3Generic65'
tmModel ='MODELS_AWHSTier3Generic65'
minuteIntervals = 15
sizingSchematic = 'primary'
simSchematic = 'multipass'

def createCSV(simRun : SimulationRun, simSchematic, kGperkWh, loadshift_title, start_vol):
    csv_filename = simSchematic+'_LS_simResult_5.csv'
    if loadshift_title == False:
        csv_filename = simSchematic+'_NON_LS_simResult_3.csv'
    simRun.writeCSV(csv_filename)

hpwh_for_sizing = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
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
            nApt            = 100, 
            Wapt            = 100,
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
TMCap_kBTUhr = None
if sizingSchematic == 'swingtank' or sizingSchematic == 'paralleltank':
    TMVol_G = hpwh_for_sizing.getSizingResults()[2] 
    TMCap_kBTUhr = hpwh_for_sizing.getSizingResults()[3]
    print('TMVol_G = ',TMVol_G)
    print('TMCap_kBTUhr = ',TMCap_kBTUhr)
print('+++++++++++++++++++++++++++++++++++++++')

# Annual simulation based on sizing from last:

print("starting LS section using sizes")
hpwh_ls = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
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
            nApt            = 100, 
            Wapt            = 60,
            nBR             = [0,50,30,20,0,0],
            loadShiftSchedule        = loadShiftSchedule,
            loadUpHours     = 3,
            doLoadShift     = True,
            loadShiftPercent       = 0.8,
            PVol_G_atStorageT = PVol_G_atStorageT, 
            PCap_kBTUhr = PCap_kBTUhr, 
            TMVol_G = TMVol_G, 
            TMCap_kBTUhr = TMCap_kBTUhr,
            annual = True,
            climateZone = 1,
            systemModel = hpwhModel,
            tmModel = tmModel
        )

start_vol = 0.4*PVol_G_atStorageT
start_time = time.time()

simResultArray = hpwh_ls.getSimRunWithkWCalc(initPV=0.4*PVol_G_atStorageT, initST=135, minuteIntervals = minuteIntervals, nDays = 365, optimizeNLS = False)

end_time = time.time()
duration = end_time - start_time
print("Program execution time for annual simulation:", duration, "seconds")

simRun_ls = simResultArray[0]

hours = [(i // (60/minuteIntervals)) + 1 for i in range(len(simRun_ls.getPrimaryVolume()))]

print('=========================================================')
print('average city watertemp is', simRun_ls.getAvgIncomingWaterT())
print('=======================FOR LS============================')
loadshift_capacity = simResultArray[2]
kGperkWh = simRun_ls.getkGCO2Sum()/loadshift_capacity
print('ls kg_sum is', simRun_ls.getkGCO2Sum())
print('ls kGperkWh is', kGperkWh)
print('annual COP:', simRun_ls.getAnnualCOP())
print('annual COP (boundry):', simRun_ls.getAnnualCOP(True))

if csvCreate:
    createCSV(simRun_ls, simSchematic, kGperkWh, True, start_vol)

print('=====================FOR NON LS==========================')
simRun_nls = simResultArray[1]

kGperkWh_nonLS = simRun_nls.getkGCO2Sum()/loadshift_capacity
print('non-ls kg_sum is', simRun_nls.getkGCO2Sum())
print('non-ls kGperkWh is', kGperkWh_nonLS)
print('annual COP:', simRun_nls.getAnnualCOP())
print('annual COP (boundry):', simRun_nls.getAnnualCOP(True))

if csvCreate:
    createCSV(simRun_nls, simSchematic, kGperkWh_nonLS, False, start_vol)
print('=========================================================')
print("LS to non-LS diff:", kGperkWh_nonLS - kGperkWh, "=", simResultArray[3])

# print(getListOfModels())
# parallel_sizer = EcosizerEngine(
#             incomingT_F     = 50,
#             magnitudeStat  = 100,
#             supplyT_F       = 120,
#             storageT_F      = 150,
#             loadUpT_F       = 150,
#             percentUseable  = 0.9, 
#             aquaFract       = 0.4, 
#             aquaFractLoadUp = 0.21,
#             aquaFractShed   = 0.8,
#             schematic       = 'swingtank', 
#             buildingType   = 'multi_family',
#             returnT_F       = 0, 
#             flowRate       = 0,
#             gpdpp           = 25,
#             safetyTM        = 1.75,
#             defrostFactor   = 1, 
#             compRuntime_hr  = 16, 
#             nApt            = 100, 
#             Wapt            = 60,
#             nBR             = [0,50,30,20,0,0],
#             loadShiftSchedule        = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,1,1],
#             loadUpHours     = 3,
#             doLoadShift     = True,
#             loadShiftPercent       = 0.8,
#             PVol_G_atStorageT = 944.972083230641, 
#             PCap_kBTUhr = 122.61152083930925, 
#             TMVol_G = 100, 
#             TMCap_kBTUhr = 59.712485,
#             annual = True,
#             climateZone = 1
#         )
# simResult = parallel_sizer.getSimResult(initPV=0.4*944.972083230641, initST=135, minuteIntervals = 15, nDays = 365)
# print(simResult[0][:10])
# print(simResult[1][-10:])
# print(simResult[2][-65:-55])
# print(simResult[3][800:810])
# print(simResult[4][-10:-4])
# print(simResult[5][-200:-190])
# print(simResult[6][800:803])
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




