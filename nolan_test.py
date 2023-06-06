from ecoengine import EcosizerEngine
import time
import csv

# regular sizing and 3 day simulation

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
            loadShiftSchedule        = [1,1,1,1,1,1,0,0,0,0,0,0,0,1,1,0,0,0,0,1,1,1,1,1],
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

print("starting next section")
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
            loadShiftSchedule        = [1,1,1,1,1,1,0,0,0,0,0,0,0,1,1,0,0,0,0,1,1,1,1,1],
            loadUpHours     = 3,
            doLoadShift     = True,
            loadShiftPercent       = 0.8,
            PVol_G_atStorageT = PVol_G_atStorageT, 
            PCap_kBTUhr = PCap_kBTUhr, 
            TMVol_G = TMVol_G, 
            TMCap_kBTUhr = TMCap_kBTUhr,
            annual = True
        )
start_time = time.time()
simResult_1 = hpwh.getSimResult(initPV=0.4*PVol_G_atStorageT, initST=135, minuteIntervals = 15, nDays = 365, zipCode = 94922)
# simResult_1 = hpwh.getSimResult(initPV=0.4*PVol_G_atStorageT, initST=135)

end_time = time.time()
duration = end_time - start_time
print(len(simResult_1))
print(len(simResult_1[1]))
print(len(simResult_1[1])/4)
print("Program execution time for annual:", duration, "seconds")
print('well hey hey looks like it worked! All done.')
print("PVol_G_atStorageT",PVol_G_atStorageT)
print("PCap_kBTUhr",PCap_kBTUhr)
print("TMVol_G",TMVol_G)
print("TMCap_kBTUhr",TMCap_kBTUhr)
print("building magnitude", hpwh.getHWMagnitude())

hours = [(i // 4) + 1 for i in range(len(simResult_1[0]))]

# Insert the 'hour' column to simResult_1
simResult_1.insert(0, hours)

transposed_result = zip(*simResult_1)

# Define the CSV filename
csv_filename = 'simResult_365_day_resonable_recirc_3.csv'

# Write the transposed_result to a CSV file
# with open(csv_filename, 'w', newline='') as csvfile:
    # csvwriter = csv.writer(csvfile)
    
    # # Write the column headers
    # csvwriter.writerow(['hour_number','pV', 'hwGenRate', 'hwDemand', 'pGen', 'swingT_F', 'sRun', 'hw_outSwing'])
    
    # # Write the data rows
    # csvwriter.writerows(transposed_result)

print("CSV file created successfully.")




