from BuildingCreator import *
from SystemCreator import *

print("HPWHulator 2.0 Copyright (C) 2023  Ecotope Inc. ")
print("This program comes with ABSOLUTELY NO WARRANTY. This is free software, and you are welcome to redistribute under certain conditions; details check GNU AFFERO GENERAL PUBLIC LICENSE_08102020.docx.")

class HPWHulator:

    def __init__(self, incomingT_F, magnitude_stat, supplyT_F, storageT_F, percentUseable, aquaFract, 
                            schematic, building_type, loadshape = None, schedule = None, cdf_shift = 1,
                            returnT_F = 0, flow_rate = 0, gpdpp = 0, nBR = None, safetyTM = 1.75,
                            defrostFactor = 1, compRuntime_hr = 16, nApt = 0, Wapt = 0, doLoadShift = False,
                            setpointTM_F = 0, TMonTemp_F = 0, offTime_hr = 0, CA = False):
        
        building = createBuilding( incomingT_F     = incomingT_F,
                                    magnitude_stat  = magnitude_stat, 
                                    supplyT_F       = supplyT_F, 
                                    building_type   = building_type,
                                    loadshape       = loadshape,
                                    returnT_F       = returnT_F, 
                                    flow_rate       = flow_rate,
                                    gpdpp           = gpdpp,
                                    nBR             = nBR,
                                    nApt            = nApt,
                                    Wapt            = Wapt
        )

        print("======= "+building_type+" =======")
        print(building.magnitude)
        print(building.recirc_loss)
        print(building.incomingT_F)

        system = createSystem(  schematic, 
                                building, 
                                storageT_F, 
                                defrostFactor, 
                                percentUseable, 
                                compRuntime_hr, 
                                aquaFract, 
                                doLoadShift = doLoadShift, 
                                cdf_shift = cdf_shift, 
                                schedule = schedule, 
                                safetyTM = safetyTM, 
                                setpointTM_F = setpointTM_F, 
                                TMonTemp_F = TMonTemp_F, 
                                offTime_hr = offTime_hr, 
                                CA = CA
        )
 
        self.system = system
    
    def getSizingResults(self):
        return self.system.getSizingResults()

    def primaryCurve(self):
        return self.system.primaryCurve()
    
    def plotStorageLoadSim(self):
        return self.system.plotStorageLoadSim()