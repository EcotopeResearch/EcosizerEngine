from objects.Building import *
import numpy as np

def create_building(inputs):


    if not hasattr(inputs, 'building_type'):
            raise Exception("Building Type required.")
    if not hasattr(inputs, 'magnitude'):
            raise Exception("Magnitude required.")
    
    # check custom loadshape or install standard loadshape
    if(not hasattr(inputs, 'loadshape')):
        # TODO inputs for stream vs stream_avg?
        inputs.loadshape = getLoadShape(inputs.building_type)
    else:
        checkLoadShape(inputs.loadshape)

    inputs.loadshape = np.array(inputs.loadshape) # TODO - this changes values a bit, check with scott

    match inputs.building_type:
        case 'apartment':
            return Apartment(inputs)
        case 'elementary_school':
            return ElementarySchool(inputs)
        case 'food_service_a':
            return FoodServiceA(inputs)
        case 'food_service_b':
            return FoodServiceB(inputs)
        case 'junior_high':
            return JuniorHigh(inputs)
        case 'mens_dorm':
            return MensDorm(inputs)
        case 'motel':
            return Motel(inputs)
        case 'nursing_home':
            return NursingHome(inputs)
        case 'office_building':
            return OfficeBuilding(inputs)
        case 'senior_high':
            return SeniorHigh(inputs)
        case 'womens_dorm':
            return WomensDorm(inputs)
        case 'multi_family':
            return MultiFamily(inputs)
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
