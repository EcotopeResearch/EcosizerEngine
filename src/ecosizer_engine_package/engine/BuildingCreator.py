from ecosizer_engine_package.objects.Building import *
import numpy as np

def createBuilding(incomingT_F, magnitude_stat, supplyT_F, building_type, loadshape = None, avgLoadshape = None,
                    returnT_F = 0, flow_rate = 0, gpdpp = 0, nBR = None, nApt = 0, Wapt = 0, standardGPD = None):
    
    """
    Initializes the building in which the HPWH system will be sized for

    Attributes
    ----------
    incomingT_F : float 
        The incoming city water temperature on the design day. [°F]
    magnitude_stat : int or list
        a number that will be used to assess the magnitude of the building based on the building type
    supplyT_F : float
        The hot water supply temperature.[°F]
    building_type : string or list
        a string indicating the type of building we are sizing for (e.g. "multi_family", "office_building", etc.)
    loadShape : ndarray
        defaults to design load shape for building type.
    avgLoadShape : ndarray
        defaults to average load shape for building type.
    returnT_F : float 
        The water temperature returning from the recirculation loop. [°F]
    flow_rate : float 
        The pump flow rate of the recirculation loop. (GPM)
    gpdpp : float
        The volume of water in gallons at 120F each person uses per dat.[°F]
    nBR : array_like
        A list of the number of units by size in the order 0 bedroom units,
        1 bedroom units, 2 bedroom units, 3 bedroom units, 4 bedroom units,
        5 bedroom units.
    nApt: integer
        The number of apartments. Use with Qdot_apt to determine total recirculation losses. (For multi-falmily buildings)
    Wapt:  float
        Watts of heat lost in through recirculation piping system. Used with N_apt to determine total recirculation losses. (For multi-falmily buildings)
    standardGPD : string
        indicates whether to use a standard gpdpp specification for multi-family buildings. Set to None if not using a standard gpdpp.

    Raises
    ----------
    Exception: Error if building_type is not in list of valid building_type names.

    """

    # handle multiuse buildings
    if isinstance(building_type, list):
        if len(building_type) == 1:
            building_type = building_type[0]
        else:
            if not isinstance(magnitude_stat, list) or len(building_type) != len(magnitude_stat):
                raise Exception("Missing values for multi-use building. Collected " + str(len(building_type)) + " building types but collected " + 
                                ("1" if not isinstance(magnitude_stat, list) else str(len(magnitude_stat)))+ " magnitude varriables")
            building_list = []
            for i in range(len(building_type)):
                building_list.append(createBuilding(incomingT_F, magnitude_stat[i], supplyT_F, building_type[i], loadshape, avgLoadshape,
                        returnT_F, flow_rate, gpdpp, nBR, nApt, Wapt))
            return MultiUse(building_list, incomingT_F, supplyT_F, returnT_F, flow_rate)
    
    #only one building type so there should only be one magnitude statistic 
    if isinstance(magnitude_stat, list):
        if len(magnitude_stat) == 1:
            magnitude_stat = magnitude_stat[0]
        else:
            raise Exception("Missing values for multi-use building. Collected 1 building type but collected " + str(len(magnitude_stat)) + " magnitude varriables")
    
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
            return MultiFamily(magnitude_stat, loadshape, avgLoadshape, incomingT_F, supplyT_F, returnT_F, flow_rate, gpdpp, nBR, nApt, Wapt, standardGPD)
        case _:
            raise Exception("Unrecognized building type.")
        
def getLoadShape(file_name, shape = 'Stream'):
    if shape != 'Stream' and shape != 'Stream_Avg':
        raise Exception("Mapping key not found for loadshapes, valid keys are: 'Stream', or 'Stream_Avg'")
    try:
        with open(os.path.join(os.path.dirname(__file__), '../data/load_shapes/' + file_name + '.json')) as json_file:
            dataDict = json.load(json_file)
            return dataDict['loadshapes'][shape]
    except:
        raise Exception("No default loadshape found for building type " +file_name + ".")
        
def checkLoadShape(loadshape):
    if len(loadshape) != 24:
        raise Exception("Loadshape must be of length 24 but instead has length of "+str(len(loadshape))+".")
    if sum(loadshape) > 1 + 1e-3 or sum(loadshape) < 1 - 1e-3:
        raise Exception("Sum of the loadshape does not equal 1. Loadshape needs to be normalized.")
    if any(x < 0 for x in loadshape):
        raise Exception("Can not have negative load shape values in loadshape.")
