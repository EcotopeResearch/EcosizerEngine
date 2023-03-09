from objects.Building import *
import numpy as np

def create_building(incomingT_F, magnitude_stat, supplyT_F, building_type, loadshape = None, avgLoadshape = None,
                    returnT_F = 0, flow_rate = 0, gpdpp = 0, nBR = None, nApt = 0, Wapt = 0):


    if not isinstance(building_type, str):
            raise Exception("building_type must be a string.")
    
    # check custom loadshape or install standard loadshape
    if(loadshape is None):
        loadshape = getLoadShape(building_type)
    else:
        checkLoadShape(loadshape)
    if(avgLoadshape is None):
        avgLoadshape = getLoadShape(building_type, 'Stream_Avg')
    else:
        checkLoadShape(avgLoadshape)

    loadshape = np.array(loadshape) # TODO - this changes values of loadshape a bit, show this to scott
    avgLoadshape = np.array(avgLoadshape) # TODO - this changes values of loadshape a bit, show this to scott

    match building_type:
        case 'apartment':
            return Apartment(magnitude_stat, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)
        case 'elementary_school':
            return ElementarySchool(magnitude_stat, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)
        case 'food_service_a':
            return FoodServiceA(magnitude_stat, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)
        case 'food_service_b':
            return FoodServiceB(magnitude_stat, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)
        case 'junior_high':
            return JuniorHigh(magnitude_stat, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)
        case 'mens_dorm':
            return MensDorm(magnitude_stat, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)
        case 'motel':
            return Motel(magnitude_stat, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)
        case 'nursing_home':
            return NursingHome(magnitude_stat, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)
        case 'office_building':
            return OfficeBuilding(magnitude_stat, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)
        case 'senior_high':
            return SeniorHigh(magnitude_stat, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)
        case 'womens_dorm':
            return WomensDorm(magnitude_stat, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate)
        case 'multi_family':
            return MultiFamily(magnitude_stat, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate, gpdpp, nBR, nApt, Wapt)
        case _:
            raise Exception("Unrecognized building type.")
        
def getLoadShape(file_name, shape = 'Stream'):
    with open(os.path.join(os.path.dirname(__file__), 'data/load_shapes/' + file_name + '.json')) as json_file:
        dataDict = json.load(json_file)
        try: 
            return dataDict['loadshapes'][shape]
        except KeyError:
            raise KeyError("Mapping key not found for loadshapes, valid keys are: 'Stream', or 'Stream_Avg'")
        
def checkLoadShape(loadshape):
    if len(loadshape) != 24:
        raise Exception("Loadshape must be of length 24 but instead has length of "+str(len(loadshape))+".")
    if sum(loadshape) > 1 + 1e-3 or sum(loadshape) < 1 - 1e-3:
        raise Exception("Sum of the loadshape does not equal 1 but "+str(sum(loadshape))+".")
    if any(x < 0 for x in loadshape):
        raise Exception("Can not have negative load shape values in loadshape.")
