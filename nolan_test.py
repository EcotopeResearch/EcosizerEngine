from ecoengine import EcosizerEngine
import time
import csv

# regular sizing and 3 day simulation
aquaFractLoadUp = 0.21
aquaFractShed   = 0.8
storageT_F = 150
loadShiftSchedule        = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,1,1] #assume this loadshape for annual simulation every day
csvCreate = False
hpwhModel ='MODELS_NyleC250A_SP'

hpwh = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            storageT_F      = storageT_F,
            loadUpT_F       = 150,
            percentUseable  = 0.9, 
            aquaFract       = 0.4, 
            aquaFractLoadUp = aquaFractLoadUp,
            aquaFractShed   = aquaFractShed,
            schematic       = 'swingtank', 
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
simResult_1 = hpwh.getSimResult()

end_time = time.time()
duration = end_time - start_time
print("Program execution time:", duration, "seconds")

PVol_G_atStorageT = hpwh.getSizingResults()[0] 
PCap_kBTUhr = hpwh.getSizingResults()[1]  
TMVol_G = hpwh.getSizingResults()[2] 
TMCap_kBTUhr = hpwh.getSizingResults()[3] 

# Annual simulation based on sizing from last:

print("starting LS section")
hpwh = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            storageT_F      = storageT_F,
            loadUpT_F       = 150,
            percentUseable  = 0.9, 
            aquaFract       = 0.4, 
            aquaFractLoadUp = aquaFractLoadUp,
            aquaFractShed   = aquaFractShed,
            schematic       = 'swingtank', 
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
            systemModel = hpwhModel
        )
start_time = time.time()
simResult_1 = hpwh.getSimResult(initPV=0.4*PVol_G_atStorageT, initST=135, minuteIntervals = 15, nDays = 365, kWhCalc = True)
# simResult_1 = hpwh.getSimResult(initPV=0.4*PVol_G_atStorageT, initST=135)

end_time = time.time()
duration = end_time - start_time
print("Program execution time for annual:", duration, "seconds")
print('well hey hey looks like it worked! All done.')
print("PVol_G_atStorageT",PVol_G_atStorageT)
print("PCap_kBTUhr",PCap_kBTUhr)
print("TMVol_G",TMVol_G)
print("TMCap_kBTUhr",TMCap_kBTUhr)
print("building magnitude", hpwh.getHWMagnitude())
print('==========================================')
print(simResult_1[0][:10])
print(simResult_1[1][-10:])
print(simResult_1[2][-65:-55])
print(simResult_1[3][800:810])
print('==========================================')

hours = [(i // 4) + 1 for i in range(len(simResult_1[0]))]

# Insert the 'hour' column to simResult_1
simResult_1.insert(0, hours)
print('kg_sum is', simResult_1[-2])
print('average temp is', simResult_1[-1])

#finishing kGperkWh calc
denom = (8.345*PVol_G_atStorageT*(aquaFractShed-aquaFractLoadUp)*(storageT_F-simResult_1[-1]))/3412 # stored energy, not input energy
print('denom',denom)
kGperkWh = simResult_1[-2]/denom

simResult_1.append(kGperkWh)

transposed_result = zip(*simResult_1[:-3])

if csvCreate:
    # Define the CSV filename
    csv_filename = 'simResult_365_day_with_ls_2.csv'
    # Write the transposed_result to a CSV file
    with open(csv_filename, 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        
        # Write the column headers
        csvwriter.writerow(['hour_number','pV', 'hwGenRate', 'hwDemand', 'pGen', 'swingT_F', 'sRun', 'hw_outSwing', 'time_primary_ran', 'OAT', 'Capacity_out', 'KgC02', 'avg_cw_temp','kGperkWh'])
        csvwriter.writerow(['','', '', '', '', '', '', '', '', '', 'total->', simResult_1[-3], simResult_1[-2],simResult_1[-1]])
        # Write the data rows
        csvwriter.writerows(transposed_result)

    print("LS CSV file created successfully.")

print("starting non-LS section")
hpwh = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            storageT_F      = storageT_F,
            loadUpT_F       = 150,
            percentUseable  = 0.9, 
            aquaFract       = 0.4, 
            aquaFractLoadUp = aquaFractLoadUp,
            aquaFractShed   = aquaFractShed,
            schematic       = 'swingtank', 
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
            loadUpHours     = 3,
            doLoadShift     = False,
            loadShiftPercent       = 0.8,
            PVol_G_atStorageT = PVol_G_atStorageT, 
            PCap_kBTUhr = PCap_kBTUhr, 
            TMVol_G = TMVol_G, 
            TMCap_kBTUhr = TMCap_kBTUhr,
            annual = True,
            climateZone = 1,
            systemModel = hpwhModel
        )
start_time = time.time()
simResult_1 = hpwh.getSimResult(initPV=0.4*PVol_G_atStorageT, initST=135, minuteIntervals = 15, nDays = 365, kWhCalc = True)
# simResult_1 = hpwh.getSimResult(initPV=0.4*PVol_G_atStorageT, initST=135)

end_time = time.time()
duration = end_time - start_time
print("Program execution time for annual:", duration, "seconds")

simResult_1.insert(0, hours)
print('kg_sum is', simResult_1[-2])
print('average temp is', simResult_1[-1])

kGperkWh_nonLS = simResult_1[-2]/denom

simResult_1.append(kGperkWh_nonLS)

transposed_result = zip(*simResult_1[:-3])

if csvCreate:
    # Define the CSV filename
    csv_filename = 'simResult_365_day_without_ls_2.csv'
    # Write the transposed_result to a CSV file
    with open(csv_filename, 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        
        # Write the column headers
        csvwriter.writerow(['hour_number','pV', 'hwGenRate', 'hwDemand', 'pGen', 'swingT_F', 'sRun', 'hw_outSwing', 'time_primary_ran', 'OAT', 'Capacity_out', 'KgC02', 'avg_cw_temp','kGperkWh'])
        csvwriter.writerow(['','', '', '', '', '', '', '', '', '', 'total->', simResult_1[-3], simResult_1[-2],simResult_1[-1]])
        # Write the data rows
        csvwriter.writerows(transposed_result)

    print("CSV file created successfully.")
print("LS kGperkWh", kGperkWh)
print("non-LS kGperkWh", kGperkWh_nonLS)
print("LS to non-LS diff:", kGperkWh - kGperkWh_nonLS)
print("dafault cap", PCap_kBTUhr / 3.412142)
print('starting v',0.4*PVol_G_atStorageT)

parallel_sizer = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            storageT_F      = 150,
            percentUseable  = 0.9, 
            aquaFract       = 0.4, 
            schematic       = 'swingtank', 
            buildingType   = 'multi_family',
            returnT_F       = 0, 
            flowRate       = 0,
            gpdpp           = 25,
            safetyTM        = 1.75,
            defrostFactor   = 1, 
            compRuntime_hr  = 16, 
            nApt            = 100, 
            Wapt            = 100,
            doLoadShift     = False,
        )
simResult = parallel_sizer.getSimResult()
print(simResult[0][:2])
print(simResult[1][-10:-8])
print(simResult[2][-65:-55])
print(simResult[3][800:810])
print(simResult[4][-10:-4])
print(simResult[5][-200:-190])
print(simResult[6][800:803])
print("===============================================")
#print(hpwh.plotStorageLoadSim(minuteIntervals = 15, nDays = 365, return_as_div = False))




