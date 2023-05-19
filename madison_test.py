from ecoengine import *

# #can create object with EcosizerEngine (wrapper) or can use createBuilding with createSystem
# #hpwh = EcosizerEngine(
# #                     incomingT_F     = 50,
# #                     magnitude_stat  = 100,
# #                     supplyT_F       = 120,
# #                     storageT_F      = 150,
# #                     percentUseable  = 0.8, 
# #                     aquaFract       = 0.4, 
# #                     schematic       = 'primary', 
# #                     building_type   = 'multi_family',
# #                     flow_rate       = 0,
# #                     gpdpp           = 25,
# #                     safetyTM        = 1.75,
# #                     defrostFactor   = 1, 
# #                     compRuntime_hr  = 16, 
# #                     nApt            = 100, 
# #                     Wapt            = 300,
#                      #schedule        = [1,1,1,1,1,1,0,0,0,0,0,0,0,1,1,0,0,0,0,1,1,1,1,1],
#                      #loadUpHours     = 2,
# #                     doLoadShift     = False,
# #                     cdf_shift       = 1,
# #                     aquaFractLoadUp = 0.31,
# #                     aquaFractShed   = 0.8,
# #                     loadUpT_F       = 150)

# #print('hpwh', hpwh.getSizingResults())

hpwhSHIFT = EcosizerEngine(
                      incomingT_F     = 50,
                      magnitudeStat  = 100,
                      supplyT_F       = 120,
                      storageT_F      = 150,
                      percentUseable  = 0.8, 
                      aquaFract       = 0.4, 
                      schematic       = 'swingtank', 
                      buildingType   = 'multi_family',
                      #flow_rate       = 0,
                      gpdpp           = 25,
                      safetyTM        = 1.75,
                      defrostFactor   = 1, 
                      compRuntime_hr  = 16, 
                      nApt            = 100, 
                      Wapt            = 100,
                      loadShiftSchedule        =  [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,1,1,1],
                      #schedule        = [1,1,1,1,1,1,0,0,0,1,1,1,1,1,1,1,1,1,0,0,0,0,1,1],
                      loadUpHours     = 2,
                      doLoadShift     = True,
                      loadShiftPercent      = 0.95,
                      aquaFractLoadUp = 0.31,
                      aquaFractShed   = 0.8,
                      loadUpT_F       = 160)

print('hpwhSHIFT', hpwhSHIFT.getSizingResults())

curve = hpwhSHIFT.primaryCurve()

print(hpwhSHIFT.lsSizedPoints())
plot = hpwhSHIFT.plotStorageLoadSim(False)
plot.write_html('Z:\\Ecosizer Updates\\newswingsizing.html')






