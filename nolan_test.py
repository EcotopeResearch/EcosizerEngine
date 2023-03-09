from HPWHulator import *
from SystemCreator import *

class Input:
    def __init__(self):
        self.incomingT_F = 50
        self.magnitude = 100
        self.supplyT_F = 120
        self.returnT_F = 1
        self.flow_rate = 1
        self.gpdpp = 25
        self.nBR = [0,40,1,7,0,0]
        self.safetyTM = 1.75
        self.storageT_F = 150
        self.defrostFactor = 1
        self.percentUseable = 0.8
        self.compRuntime_hr = 16
        self.aquaFract = 0.4
        self.schematic = "swingtank"

inputs = Input()

# inputs.building_type = 'apartment'
# building = create_building(inputs)
# print(building.loadshape)
# inputs.building_type = 'elementary_school'
# building = create_building(inputs)
# print(building.loadshape)
# inputs.building_type = 'food_service_a'
# building = create_building(inputs)
# print(building.loadshape)
# inputs.building_type = 'food_service_b'
# building = create_building(inputs)
# print(building.loadshape)
# inputs.building_type = 'junior_high'
# building = create_building(inputs)
# print(building.loadshape)
# inputs.building_type = 'mens_dorm'
# building = create_building(inputs)
# print(building.loadshape)
# inputs.building_type = 'motel'
# building = create_building(inputs)
# print(building.loadshape)
# inputs.building_type = 'nursing_home'
# building = create_building(inputs)
# print(building.loadshape)
# inputs.building_type = 'senior_high'
# building = create_building(inputs)
# print(building.loadshape)
# inputs.building_type = 'womens_dorm'
# building = create_building(inputs)
# print(building.loadshape)
# inputs.nApt = 1
# inputs.Wapt = 1
# inputs.building_type = 'multi_family'
# building = create_building(inputs)
# print(building.loadshape)
# print(building.recirc_loss)
# inputs = Input()
# inputs.building_type = 'multi_family'
# inputs.gpdpp = 'ca'
# building = create_building(inputs)
# print(building.loadshape)
# print(building.recirc_loss)
# print(building.magnitude)

hpwh = HPWHulator()
swingTank = hpwh.createAndSizeSystem(incomingT_F     = 50,
                                    magnitude_stat  = 100,
                                    supplyT_F       = 120,
                                    storageT_F      = 150,
                                    percentUseable  = 0.8, 
                                    aquaFract       = 0.4, 
                                    schematic       = 'swingtank', 
                                    building_type   = 'multi_family',
                                    returnT_F       = 0, 
                                    flow_rate       = 0,
                                    gpdpp           = 25,
                                    safetyTM        = 1.75,
                                    defrostFactor   = 1, 
                                    compRuntime_hr  = 16, 
                                    nApt            = 100, 
                                    Wapt            = 100,
                                    schedule        = [1,1,1,1,1,1,0,0,0,0,0,0,0,1,1,0,0,0,0,1,1,1,1,1],
                                    doLoadShift     = True,
                                    cdf_shift       = 0.8
)

# swingTank = createSystem(building, inputs)
swingTank.simulate()
[x_data, y_data, hours, recInd] = swingTank.primaryCurve()
print("x_data",x_data)
print("y_data",y_data)
print("hours",hours)
print("recInd",recInd)

fig = swingTank.plotStorageLoadSim()


#building = create_building(3,1,1,1,1,'multi_family', None, ["ca",0,0, [0,40,1,7,0,0]])
# p = ParallelLoopTank(building, 1, 4, 1, 1)
# p.simulate()


