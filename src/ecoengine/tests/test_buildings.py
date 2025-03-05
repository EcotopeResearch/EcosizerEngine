import pytest
from ecoengine.engine.BuildingCreator import createBuilding
import numpy as np
import os, sys
from ecoengine.constants.Constants import *
import re

class QuietPrint:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout

# Fixtures
@pytest.fixture
def multiFamily(): # Returns the hpwh swing tank
    with QuietPrint():
        building = createBuilding(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            buildingType   = 'multi_family',
            nApt            = 100, 
            Wapt            = 100,
            gpdpp           = 25
        )
    return building

@pytest.fixture
def multiFamilyWithBedrooms(): # Returns the hpwh swing tank
    with QuietPrint():
        building = createBuilding(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            buildingType   = 'multi_family',
            nApt            = 100, 
            Wapt            = 100,
            gpdpp           = 100,
            nBR             = [0,1,5,3,2,0],
            standardGPD     = 'ca'
        )
    return building

@pytest.fixture
def nursingHomeAndOffice(): # Returns the hpwh swing tank
    with QuietPrint():
        building = createBuilding(
            incomingT_F     = 50,
            magnitudeStat  = [100, 75],
            supplyT_F       = 120,
            buildingType   = ['nursing_home','office_building'],
            returnT_F       = 100, 
            flowRate       = 5
        )
    return building

###############################################################################
###############################################################################
# Unit Tests

@pytest.mark.parametrize("expected", [
   ([50, 120, 34121.42, 2500])
])
def test_multiFamilyResults(multiFamily, expected):
    assert [multiFamily.incomingT_F, multiFamily.supplyT_F, multiFamily.recirc_loss, multiFamily.magnitude] == expected

@pytest.mark.parametrize("expected", [
   ([34121.42, 50, 120, 2350.0])
])
def test_multiFamilyWithBedroomsResults(multiFamilyWithBedrooms, expected):
    assert [multiFamilyWithBedrooms.recirc_loss, multiFamilyWithBedrooms.incomingT_F, multiFamilyWithBedrooms.supplyT_F, multiFamilyWithBedrooms.magnitude] == expected

@pytest.mark.parametrize("expected", [
   ([50, 120, 50121.21, 2497.5])
])
def test_multiUseResults(nursingHomeAndOffice, expected):
    assert [nursingHomeAndOffice.incomingT_F, nursingHomeAndOffice.supplyT_F, round(nursingHomeAndOffice.recirc_loss, 2), round(nursingHomeAndOffice.magnitude, 2)] == expected

@pytest.mark.parametrize("buildingType, loadshape, magnitude, expected", [
   ("apartment",None,100,5460.0),
   (["elementary_school"],None,100,134.0),
   ("food_service_a",None,100,1103.2),
   ("food_service_b",None,100,644.0),
   ("junior_high",None,100,375.0),
   ("mens_dorm",None,[100],2360.0),
   (None,[0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[100],100),
   (None,[0,0,0,0,0,0,0,0,100,50,0,0,0,0,0,0,0,0,0,0,0,0,0,0],None,150),
   (["office_building",None],[None, [0,0,0,0,0,0,0,0,100,50,0,0,0,0,0,0,0,0,0,0,0,0,0,0]],[100,None],360.0),
   ("motel",None,100,2140.0),
   (["nursing_home"],None,[100],2340.0),
   ("office_building",None,100,210.0),
   ("senior_high",None,100,326.0),
   ("womens_dorm",None,100,1960.0),
   (["womens_dorm", "junior_high"],None,[100,5],1978.8)
])
def test_magnitudes(buildingType, loadshape, magnitude, expected):
    building = createBuilding(
            incomingT_F     = 50,
            magnitudeStat  = magnitude,
            supplyT_F       = 120,
            buildingType   = buildingType,
            flowRate       = 5,
            returnT_F       = 100,
            loadshape       = loadshape
    )
    assert round(building.magnitude,1) == expected

@pytest.mark.parametrize("buildingType, magnitude, expected", [
   ("apartment",100,np.array([0.046728972, 0.044392523, 0.037383178])),
   (["food_service_a", "nursing_home"],[100,50],np.array([0., 0.00256, 0.00256])),
   (["womens_dorm", "junior_high"],[100,5],np.array([0.30202, 0.12085, 0.0363])),
   (["womens_dorm", "junior_high"],[5,100],np.array([0.06559, 0.03012, 0.01243])),
   (["womens_dorm", "junior_high", "food_service_a", "nursing_home", "apartment"],[5,100, 50, 200, 500],np.array([0.03959, 0.03786, 0.03181]))
])
def test_default_loadshapes(buildingType, magnitude, expected):
    building = createBuilding(
            incomingT_F     = 50,
            magnitudeStat  = magnitude,
            supplyT_F       = 120,
            buildingType   = buildingType,
            flowRate       = 5,
            returnT_F       = 100,
    )
    assert np.array_equal(np.round(building.loadshape[:3], decimals=5), np.round(expected, decimals=5))
    
@pytest.mark.parametrize("loadShape, buildingType, magnitude, expected", [
   ([1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],"apartment",100,np.array([1, 0, 0])),
   ([1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],None,100,np.array([1, 0, 0])),
   ([[1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]],["womens_dorm", "junior_high"],[5,100],np.array([0.20719, 0.79281, 0.]))
])
def test_custom_loadshapes(loadShape, buildingType, magnitude, expected):
    building = createBuilding(
            incomingT_F     = 50,
            magnitudeStat  = magnitude,
            supplyT_F       = 120,
            buildingType   = buildingType,
            flowRate       = 5,
            returnT_F       = 100,
            loadshape       = loadShape
    )
    assert np.array_equal(np.round(building.loadshape[:3], decimals=5), np.round(expected, decimals=5))

def test_annualLS_for_multi_family(multiFamilyWithBedrooms):
    assert len(multiFamilyWithBedrooms.loadshape) == 24
    assert len(multiFamilyWithBedrooms.avgLoadshape) == 24
    assert not multiFamilyWithBedrooms.isAnnualLS()
    multiFamilyWithBedrooms.setToAnnualLS()
    assert len(multiFamilyWithBedrooms.loadshape) == 8760
    assert len(multiFamilyWithBedrooms.avgLoadshape) == 8760
    assert multiFamilyWithBedrooms.isAnnualLS()

def test_annualLS_for_non_multi_family(nursingHomeAndOffice):
    assert len(nursingHomeAndOffice.loadshape) == 24
    assert len(nursingHomeAndOffice.avgLoadshape) == 24
    assert not nursingHomeAndOffice.isAnnualLS()
    with pytest.raises(Exception, match="Annual loadshape not available for this building type. This feature is only available for multi-family buildings."):
        nursingHomeAndOffice.setToAnnualLS()
    assert len(nursingHomeAndOffice.loadshape) == 24
    assert len(nursingHomeAndOffice.avgLoadshape) == 24
    assert not nursingHomeAndOffice.isAnnualLS()

def test_annualLS_from_instantiation(nursingHomeAndOffice):
    building = createBuilding(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            buildingType   = 'multi_family',
            nApt            = 100, 
            Wapt            = 100,
            gpdpp           = 25,
            annual          = True
        )
    assert len(building.loadshape) == 8760
    assert len(building.avgLoadshape) == 8760

@pytest.mark.parametrize("zipCode, climateZone, buildingType, magnitude", [
   (94922,1,"apartment", 100),
   (94565,12,["womens_dorm", "junior_high"], [100,50]),
   (None,None,"multi_family", 100)
])
def test_zipCodes_to_climateZones(zipCode, climateZone, buildingType, magnitude):
    building = createBuilding(
            incomingT_F     = 50,
            magnitudeStat  = magnitude,
            supplyT_F       = 120,
            buildingType   = buildingType,
            flowRate       = 5,
            returnT_F       = 100,
            zipCode         = zipCode
    )
    assert building.climateZone == climateZone

@pytest.mark.parametrize("zipCode, design_oat, buildingType, magnitude, expected_design_oat", [
   (94565,1,"apartment", 100, 1),
   (94565,None,["womens_dorm", "junior_high"], [100,50], 26.96),
   (None,None,"multi_family", 100, None)
])
def test_design_oat(zipCode, design_oat, buildingType, magnitude, expected_design_oat):
    building = createBuilding(
            incomingT_F     = 50,
            magnitudeStat  = magnitude,
            supplyT_F       = 120,
            buildingType   = buildingType,
            flowRate       = 5,
            returnT_F       = 100,
            zipCode         = zipCode,
            designOAT_F= design_oat
    )
    assert building.getDesignOAT() == expected_design_oat

@pytest.mark.parametrize("climateZone, jan_in_T, sep_in_t, oct_in_T", [
   (1, 50.108, 54.734, 54.59),
   (6, 59.306, 65.876, 64.742),
   (18, 46.9, 61.0, 58.6)
])
def test_climateZone_temps(climateZone, jan_in_T, sep_in_t, oct_in_T):
    building = createBuilding(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            buildingType   = "multi_family",
            flowRate       = 5,
            returnT_F       = 100,
            climateZone    = climateZone
    )
    assert building.getIncomingWaterT(0, 60) == jan_in_T
    assert building.getIncomingWaterT(100, 15) == jan_in_T
    assert building.getIncomingWaterT(80000, 16, month=1) == jan_in_T

    assert building.getIncomingWaterT(6551, 60) == sep_in_t
    assert building.getIncomingWaterT((6551*4)+3, 15) == sep_in_t
    assert building.getIncomingWaterT((6551*60)+45, 1) == sep_in_t

    assert building.getIncomingWaterT(6552, 60) == oct_in_T
    assert building.getIncomingWaterT(26242, 15) == oct_in_T
    assert building.getIncomingWaterT(80000, 16, month=10) == oct_in_T

# Check for building initialization errors
def test_invalid_building_parameter_errors():
    with pytest.raises(Exception, match="Error: Number of apartments must be an integer."):
        createBuilding(35, 4, 120, "multi_family", nApt='blah')
    with pytest.raises(Exception, match="Error: WATTs per apt must be an integer."):
        createBuilding(35, 4, 120, "multi_family", Wapt='blah')
    with pytest.raises(Exception, match="Error: GPDPP must be a number."):
        createBuilding(35, 4, 120, "multi_family", gpdpp=None)
    with pytest.raises(Exception, match=re.escape("Error: standardGPD must be a String of one of the following values: ['ca', 'ashLow', 'ashMed', 'ecoMark']")):
        createBuilding(35, 4, 120, "multi_family", gpdpp=25, standardGPD=5)
    with pytest.raises(Exception, match=re.escape("Error: standardGPD must be a String of one of the following values: ['ca', 'ashLow', 'ashMed', 'ecoMark']")):
        createBuilding(35, 4, 120, "multi_family", gpdpp=25, standardGPD='yabadabado')
    with pytest.raises(Exception, match="No default loadshape found for building type climbing_gym."):
        createBuilding(35, 4, 120, "climbing_gym")
    with pytest.raises(Exception, match="Loadshape must be of length 24 but instead has length of 5."):
        createBuilding(35, 4, 120, "mens_dorm", loadshape=[1,2,3,4,5])
    with pytest.raises(Exception, match="Sum of the loadshape does not equal 1. Loadshape needs to be normalized."):
        createBuilding(35, 4, 120, "mens_dorm", loadshape=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24])
    with pytest.raises(Exception, match="Can not have negative values in loadshape."):
        createBuilding(35, 4, 120, "mens_dorm", loadshape=[1,2,-3,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
    with pytest.raises(Exception, match="Average loadshape must be of length 24 but instead has length of 5."):
        createBuilding(35, 4, 120, "mens_dorm", avgLoadshape=[1,2,3,4,5])
    with pytest.raises(Exception, match="Sum of the average loadshape does not equal 1. Loadshape needs to be normalized."):
        createBuilding(35, 4, 120, "mens_dorm", avgLoadshape=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24])
    with pytest.raises(Exception, match="Can not have negative values in average loadshape."):
        createBuilding(35, 4, 120, "mens_dorm", avgLoadshape=[1,2,-3,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
    with pytest.raises(Exception, match="Missing values for multi-use building. Collected 2 building types but collected 24 avgLoadshape values"):
        createBuilding(35, [4,8], 120, ["mens_dorm", None], avgLoadshape=[0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
    with pytest.raises(Exception, match="Both buildingType and loadshape are undefined. Must define at least one to construct building object."):
        createBuilding(35, [4,8], 120, ["mens_dorm", None], avgLoadshape=[None,None])
    with pytest.raises(Exception, match="Error: Supply temp must be a number."):
        createBuilding(35, 4, "whoops", "mens_dorm")
    with pytest.raises(Exception, match="Error: Return temp must be a number."):
        createBuilding(35, 4, 120, "mens_dorm", returnT_F="uh oh")
    with pytest.raises(Exception, match="Error: Supply temp must be higher than return temp."):
        createBuilding(35, 4, 120, "mens_dorm", returnT_F=150)
    with pytest.raises(Exception, match="Error: City water temp must be a number."):
        createBuilding("not a number", 4, 120, "mens_dorm")
    with pytest.raises(Exception, match="Error: Flow rate must be a number."):
        createBuilding(35, 4, 120, "mens_dorm", flowRate = "problem")
    with pytest.raises(Exception, match="Error: designOAT_F must be a number or None."):
        createBuilding(35, 4, 120, "mens_dorm", designOAT_F = "problem")
    with pytest.raises(Exception, match="Missing values for multi-use building. Collected 2 building types but collected 1 magnitude varriables"):
        createBuilding(35, 4, 120, ["mens_dorm","yep"])
    with pytest.raises(Exception, match="Missing values for multi-use building. Collected 2 building types but collected 4 magnitude varriables"):
        createBuilding(35, [1,2,3,4], 120, ["mens_dorm","yep"])
    with pytest.raises(Exception, match="Missing values for multi-use building. Collected 1 building type but collected 3 magnitude varriables"):
        createBuilding(35, [4,7,8] , 120, ["mens_dorm"])
    with pytest.raises(Exception, match="No default loadshape found for building type yep."):
        createBuilding(35, [1,2], 120, ["mens_dorm","yep"])
    with pytest.raises(Exception, match="Climate Zone must be a number between 1 and 19, or between 1 and 16 if making a kWh calculation."):
        createBuilding(35, 4, 120, "mens_dorm", climateZone = 100)
    with pytest.raises(Exception, match="Both buildingType and loadshape are undefined. Must define at least one to construct building object."):
        createBuilding(35, 4, 120, None)
    with pytest.raises(Exception, match="Climate Zone must be a number between 1 and 19, or between 1 and 16 if making a kWh calculation."):
        createBuilding(35, 4, 120, "mens_dorm", climateZone = 'yes')
    with pytest.raises(Exception, match="Climate Zone must be a number between 1 and 19, or between 1 and 16 if making a kWh calculation."):
        createBuilding(35, 4, 120, "mens_dorm", climateZone = 0)
    with pytest.raises(Exception, match="18 is not a California zip code."):
        createBuilding(35, 4, 120, "mens_dorm", zipCode = 18)
    with pytest.raises(Exception, match="98028 is not a California zip code."):
        createBuilding(35, 4, 120, "mens_dorm", zipCode = 98122)
    with pytest.raises(Exception, match="the surf spot is not a California zip code."):
        createBuilding(35, 4, 120, "mens_dorm", zipCode = 'the surf spot')
    with pytest.raises(Exception, match="Annual simulation for non-multifamily buildings is not yet available."):
        createBuilding(35, 4, 120, "mens_dorm", annual=True)