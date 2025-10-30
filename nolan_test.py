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

check_building = createBuilding(
            incomingT_F     = 55,
            magnitudeStat  = 200,
            supplyT_F       = 125,
            buildingType   = 'multi_family',
            nApt            = 150, 
            returnT_F       = 115,
            flowRate        = 3,
            gpdpp           = 25
        )

print("==========creating nrtp==========")
nortp_system = createSystem(
    schematic   = 'swingtank', 
    building    = check_building, 
    storageT_F  = 150, 
    defrostFactor   = 1, 
    percentUseable  = .8, 
    compRuntime_hr  = 16, 
    onFract   = 0.4,
)
print("==========creating sprtp===========")
rtp_system = createSystem(
    schematic   = 'sprtp', 
    building    = check_building, 
    storageT_F  = 150, 
    defrostFactor   = 1, 
    percentUseable  = .8, 
    compRuntime_hr  = 16, 
    onFract   = 0.4,
)
print("==========created sprtp===========")
print("==========creating mprtp===========")
mprtp_system = createSystem(
    schematic   = 'mprtp', 
    building    = check_building, 
    storageT_F  = 150, 
    defrostFactor   = 1, 
    percentUseable  = .8, 
    compRuntime_hr  = 16, 
    onFract   = 0.25,
)
print("==========created mprtp===========")
print(f"rtp_system.PCap_kBTUhr > nortp_system.PCap_kBTUhr : {rtp_system.PCap_kBTUhr} > {nortp_system.PCap_kBTUhr}")
print(f"rtp_system.getSizingResults() : {rtp_system.getSizingResults()}")
print(f"nortp_system.getSizingResults() : {nortp_system.getSizingResults()}")
print(f"mprtp_system.getSizingResults() : {mprtp_system.getSizingResults()}")

# simRun = simulate(rtp_system, check_building, minuteIntervals = 1, nDays = 3)
# load_sim = simRun.plotStorageLoadSim(True)




def make_oupput_file(system, building, file_name):

    print(f"+++++++++++{file_name}+++++++++++")
    simRun = simulate(system, building, minuteIntervals = 1, nDays = 3)
    load_sim = simRun.plotStorageLoadSim(True)

    [storage_data, capacity_data, hours, startIndex] = system.primaryCurve(building)
    # print("storage_data",storage_data)
    # print("capacity_data",capacity_data)
    # print("hours",hours)
    # print("startIndex",startIndex)
    storage_data = around(flipud(storage_data),2)
    capacity_data = around(flipud(capacity_data),2)
    hours = around(flipud(hours),2)
    startIndex = len(storage_data)-startIndex-1
    curve = system.getPrimaryCurveAndSlider(storage_data, capacity_data, startIndex, hours, returnAsDiv = True)


    title = "sims"

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
        <br><br><br>
        {curve}
    </body>
    </html>"""
    with open(f"{file_name}_output.html", "w", encoding="utf-8") as f:
        f.write(html_content)

make_oupput_file(nortp_system, check_building, "swing_2")
make_oupput_file(rtp_system, check_building, "sprtp_2")
make_oupput_file(mprtp_system, check_building, "mprtp_2")




# @pytest.mark.parametrize("onFractLoadUp, onFractShed, storageT_F, supplyT_F, loadShiftSchedule, hpwhModel, tmModel, simSchematic, PVol_G_atStorageT, PCap_kW, TMVol_G, TMCap_kW, doLoadShift, zipCode, climateZone", [
#    (0.21, 0.8, 140, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_VOLTEX80_R_MP', None, 'multipass_norecirc', 891, 48, None, None, True, 94503,2),
#    (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_ColmacCxA_10_C_MP', None, 'multipass_norecirc', 891, 48, None, None, True, 93901,3),
#    (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_ColmacCxA_10_C_MP', None, 'multipass_rtp', 891, 48, None, None, True, 93254,4),
#    (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_AOSmithCAHP120_C_MP', None, 'multipass_rtp', 891, 48, None, None, True, 93130,5),
#    (0.21, 0.8, 140, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_C_SP', None, 'singlepass_rtp', 891, 48, None, None, True, 90003,8),
#    (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_AOSmithCAHP120_C_MP', None, 'singlepass_rtp', 891, 48, None, None, True, 91902,7),
#    (0.21, 0.8, 150, 120, None, 'MODELS_AOSmithCAHP120_C_MP', None, 'singlepass_rtp', 702, 41, None, None, False, 90003,8),
#    (0.21, 0.8, 140, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_C_SP', None, 'singlepass_norecirc', 891, 48, None, None, True, 91701,10),
#    (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_Mitsubishi_QAHV_C_SP', None, 'singlepass_norecirc', 891, 48, None, None, True, 91701,10),
#    (0.21, 0.8, 145, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_SANCO2_C_SP', None, 'swingtank', 891, 48, 100, 19, True, 95603,11),
#    (0.21, 0.8, 134, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_ColmacCxA_25_C_SP', None, 'swingtank', 891, 48, 100, 19, True, 93620,12),
#    (0.21, 0.8, 140, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_C_SP', 'MODELS_RHEEM_HPHD60HNU_201_C_MP', 'paralleltank', 891, 31, 91, 19, True,91701,10),
#    (0.21, 0.8, 127, 122, [1,1,1,1,1,1,1,1,0,0,0,0,1,1,1,1,0,0,0,0,0,0,1,1], 'MODELS_ColmacCxA_15_C_SP', 'MODELS_ColmacCxA_20_C_MP', 'paralleltank', 891, 31, 91, 19, True, 91916,14),
#    (0.21, 0.8, 140, 122, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_C_SP', 'MODELS_RHEEM_HPHD135HNU_483_C_MP', 'paralleltank', 891, 31, 91, 19, True, 92004,15)
# ])
# def test_annual_simRun_values(onFractLoadUp, onFractShed, storageT_F, supplyT_F, loadShiftSchedule, hpwhModel, tmModel, 
#                               simSchematic, PVol_G_atStorageT, PCap_kW, TMVol_G, TMCap_kW, doLoadShift, zipCode, climateZone):
    
(onFractLoadUp, onFractShed, storageT_F, supplyT_F, loadShiftSchedule, hpwhModel, tmModel, 
                              simSchematic, PVol_G_atStorageT, PCap_kW, TMVol_G, TMCap_kW, doLoadShift, zipCode, climateZone) = (0.21, 0.8, 140, 122, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_C_SP', 'MODELS_RHEEM_HPHD135HNU_483_C_MP', 'paralleltank', 891, 31, 91, 19, True, 92004,15)
hpwh_ls = EcosizerEngine(
        magnitudeStat  = 100,
        supplyT_F       = supplyT_F,
        storageT_F      = storageT_F,
        offLoadUpT       = storageT_F,
        percentUseable  = 0.9, 
        onFract       = 0.4, 
        onFractLoadUp = onFractLoadUp,
        onFractShed   = onFractShed,
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
        loadShiftSchedule  = loadShiftSchedule,
        loadUpHours     = 3,
        doLoadShift     = doLoadShift,
        loadShiftPercent       = 0.8,
        PVol_G_atStorageT = PVol_G_atStorageT, 
        PCap_kW = PCap_kW,
        TMVol_G = TMVol_G,
        TMCap_kW = TMCap_kW,
        annual = True,
        zipCode = zipCode,
        systemModel = hpwhModel,
        tmModel = tmModel
    )

print(f"hpwh_ls L {hpwh_ls.system.getOffTriggerTemp('L')}")
print(f"hpwh_ls S {hpwh_ls.system.getOffTriggerTemp('S')}")
print(f"hpwh_ls N {hpwh_ls.system.getOffTriggerTemp('N')}")

simRun = hpwh_ls.getSimRun(initPV=0.4*PVol_G_atStorageT, initST=135, minuteIntervals = 15, nDays = 365)
supplyToStorageFactor = (supplyT_F - simRun.getIncomingWaterT(0))/(storageT_F - simRun.getIncomingWaterT(0)) # should be same for entire month
# for i in range(2,1000):

#         # assert primaryVolume = generation - demand
#         if simSchematic == 'swingtank':
#             hw_out_at_storage = simRun.gethwOutSwing(i)
#         else:
#             hw_out_at_storage = (simRun.getHWDemand(i)+simRun.getRecircLoss(i)) * supplyToStorageFactor
#         hopefulResult = simRun.getPrimaryVolume(i-1) + simRun.getPrimaryGeneration(i) - hw_out_at_storage
#         print(f"{i}: {simRun.getPrimaryVolume(i)} -> {hopefulResult} = {simRun.getPrimaryVolume(i-1)} + {simRun.getPrimaryGeneration(i)} - {hw_out_at_storage}")
#         print(f"             hw_out_at_storage {hw_out_at_storage} = ({simRun.getHWDemand(i)}+{simRun.getRecircLoss(i)}) * {supplyToStorageFactor}")
#         print(f"             simRun.pOnV[{i}] = {simRun.pOnV[i]}, simRun.pOffV[{i}] = {simRun.pOffV[i]}, simRun.pTAtOff[{i}] = {simRun.pTAtOff[i]}, simRun.pTAtOn[{i}] = {simRun.pTAtOff[i]}")
#         print(f"             simRun.pOnT[{i}] = {simRun.pOnT[i]}, simRun.pOffT[{i}] = {simRun.pOffT[i]}, simRun.getPrimaryGeneration(i) = {simRun.getPrimaryGeneration(i)}")
#         if not simRun.getPrimaryVolume(i) < hopefulResult + 0.01 or not simRun.getPrimaryVolume(i) > hopefulResult - 0.01:
#              break

    # assert hpwh_ls.getClimateZone() == climateZone
    # for i in range(1,1000):

    #     # assert primaryVolume = generation - demand
    #     if simSchematic == 'swingtank':
    #         hw_out_at_storage = simRun.gethwOutSwing(i)
    #     else:
    #         hw_out_at_storage = (simRun.getHWDemand(i)+simRun.getRecircLoss(i)) * supplyToStorageFactor
    #     hopefulResult = simRun.getPrimaryVolume(i-1) + simRun.getPrimaryGeneration(i) - hw_out_at_storage
    #     assert simRun.getPrimaryVolume(i) < hopefulResult + 0.01
    #     assert simRun.getPrimaryVolume(i) > hopefulResult - 0.01

    #     # assert hw generation rate makes sense
    #     calculated_generation = 1000 * (simRun.getCapOut(i)*W_TO_BTUHR) / rhoCp / (supplyT_F - simRun.getIncomingWaterT(i)) / 4 # divide by 4 because there are 4 15 min intervals in an hour
    #     assert simRun.getHWGeneration(i) < calculated_generation + 0.01
    #     assert simRun.getHWGeneration(i) > calculated_generation - 0.01
    #     calculated_generation *= supplyToStorageFactor * (simRun.getPrimaryRun(i)/15)
    #     assert simRun.getPrimaryGeneration(i) < calculated_generation + 0.01
    #     assert simRun.getPrimaryGeneration(i) > calculated_generation - 0.01

    #     # assert kW calculation is correct
    #     calculatedKg = climateZone_1_kg[i//4][climateZone-1] * (simRun.getCapIn(i) * (simRun.getPrimaryRun(i) / 60) + (simRun.getTMCapIn(i)*simRun.getTMRun(i)/60))
    #     assert simRun.getkGCO2(i) < calculatedKg + 0.001
    #     assert simRun.getkGCO2(i) > calculatedKg - 0.001


    # # ensure recirc non-existant for non-recirc-tracking systems
    # if simSchematic != 'singlepass_rtp' and simSchematic != 'multipass_rtp':
    #     assert simRun.getRecircLoss(0) == 0
    #     assert simRun.getRecircLoss(5000) == 0
    #     assert simRun.getRecircLoss(10000) == 0

    # # assert COP calculations are the same (within rounding error of 0.002)
    # equip_method_cop = simRun.getAnnualCOP()
    # boundry_method_cop = simRun.getAnnualCOP(boundryMethod = True)
    # assert equip_method_cop < boundry_method_cop + 0.005
    # assert equip_method_cop > boundry_method_cop - 0.005



# (onFractLoadUp, onFractShed, storageT_F, supplyT_F, hpwhModel, 
#                               PVol_G_atStorageT, PCap_kW, TMVol_G, TMCap_kW, doLoadShift, zipCode, annual, produce_error) = (0.21, 0.8, 145, 120, None, 891, 20, 100, 29, True, None, True, False)

# hpwh = EcosizerEngine(
#             incomingT_F     = 50,
#             magnitudeStat  = 100,
#             supplyT_F       = supplyT_F,
#             storageT_F      = storageT_F,
#             offLoadUpT       = storageT_F,
#             percentUseable  = 0.9, 
#             onFract       = 0.4, 
#             onFractLoadUp = onFractLoadUp,
#             onFractShed   = onFractShed,
#             schematic       = 'swingtank_er', 
#             buildingType   = 'multi_family',
#             returnT_F       = 0, 
#             flowRate       = 0,
#             gpdpp           = 25,
#             safetyTM        = 1.75,
#             defrostFactor   = 1, 
#             compRuntime_hr  = 16, 
#             nApt            = 100, 
#             Wapt            = 60,
#             loadShiftSchedule  = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1],
#             loadUpHours     = 3,
#             doLoadShift     = True,
#             loadShiftPercent       = 0.8,
#             PVol_G_atStorageT = PVol_G_atStorageT, 
#             PCap_kW = PCap_kW,
#             TMVol_G = TMVol_G,
#             TMCap_kW = TMCap_kW,
#             annual = False,
#             zipCode = zipCode,
#             systemModel = hpwhModel,
#             numHeatPumps = 1,
#             sizeAdditionalER = True
#         )

# print(hpwh.getSizingResults())


# hpwh = EcosizerEngine(
#             incomingT_F     = 50,
#             magnitudeStat  = 100,
#             supplyT_F       = supplyT_F,
#             storageT_F      = storageT_F,
#             offLoadUpT       = storageT_F,
#             percentUseable  = 0.9, 
#             onFract       = 0.4, 
#             onFractLoadUp = onFractLoadUp,
#             onFractShed   = onFractShed,
#             schematic       = 'swingtank_er', 
#             buildingType   = 'multi_family',
#             returnT_F       = 0, 
#             flowRate       = 0,
#             gpdpp           = 25,
#             safetyTM        = 1.75,
#             defrostFactor   = 1, 
#             compRuntime_hr  = 16, 
#             nApt            = 100, 
#             Wapt            = 60,
#             loadShiftSchedule  = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1],
#             loadUpHours     = 3,
#             doLoadShift     = doLoadShift,
#             loadShiftPercent       = 0.8,
#             PVol_G_atStorageT = PVol_G_atStorageT, 
#             PCap_kW = PCap_kW,
#             TMVol_G = TMVol_G,
#             TMCap_kW = TMCap_kW,
#             annual = annual,
#             zipCode = zipCode,
#             systemModel = hpwhModel,
#             numHeatPumps = 1,
#             sizeAdditionalER = False
#         )

# simRun = hpwh.getSimRun(initPV=0.4*PVol_G_atStorageT, initST=135, minuteIntervals = 15, nDays = 365)

(zipC, nBR, storageT_F, aqFrac, aqFrac_lu, aqFrac_shed, luT_F, schematic, systemModel, 
    numPumps, pVol, TMCap_kW, tmModel, TMVol_G, tmNumHeatPumps, 
    loadshift_capacity, kGperkWh_saved, annual_kGCO2_saved) = (90023, [5,120,70,9,4,1], 150, .45, .15, .85, 160, 'swingtank', "MODELS_LYNC_AEGIS_500_SIMULATED_C_SP", 
                                                               2, 1700, 17, None, 150, None, 
                                                               279.84, 5.32, 1488.6)
print(f"I am there {aqFrac}, {aqFrac_lu}, {aqFrac_shed}")
nApt = int(sum( nBR ))
rBR = [1.37,1.74,2.57,3.11,4.23,3.77] 
npep = np.dot(nBR, rBR)
building = createBuilding(50, sum(nBR), 150, 'multi_family', loadshape = None, avgLoadshape = None,
    returnT_F = 0, flowRate = 0, gpdpp = 0, nBR = nBR, nApt = 0, Wapt = 0, standardGPD = 'ca')
gpdpp = building.magnitude/sum(nBR)
print('uhhh',gpdpp)
hpwh = EcosizerEngine(
        magnitudeStat = npep,
        supplyT_F = 120,
        storageT_F = storageT_F,
        percentUseable = 0.95,
        onFract = aqFrac,
        onFractLoadUp = aqFrac_lu,
        onLoadUpT= 150,
        onFractShed = aqFrac_shed,
        offLoadUpT = luT_F,
        loadUpHours = 2, # might need to change for future
        schematic = schematic,
        buildingType  = 'multi_family',
        gpdpp = gpdpp,
        compRuntime_hr = 16,
        nApt = nApt,
        Wapt = 60,
        standardGPD = 'ca',
        nBR = nBR,
        loadShiftSchedule = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,1],
        doLoadShift   = True,
        zipCode=zipC,
        annual=True,
        systemModel=systemModel,
        numHeatPumps=numPumps,
        PVol_G_atStorageT=pVol,
        TMCap_kW=TMCap_kW,
        tmModel=tmModel,
        TMVol_G=TMVol_G,
        tmNumHeatPumps = tmNumHeatPumps,                          
)
print("I am here", hpwh.getSizingResults())
outlist = hpwh.getSimRunWithkWCalc(minuteIntervals = 15, nDays = 365)
# outlist[0].writeCSV('ls.csv')
# outlist[1].writeCSV('nls.csv')
print(f"loadshift_capacity =  {round(outlist[2],2)}")
print(f"kGperkWh_saved =  {round(outlist[3],2)}")
print(f"annual_kGCO2_saved =  {round(outlist[4],2)}")
# assert round(outlist[3],2) == kGperkWh_saved
# assert round(outlist[4],2) == annual_kGCO2_saved