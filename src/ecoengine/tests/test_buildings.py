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
   ([50, 120, 50121.21, 2093.25])
])
def test_multiUseResults(nursingHomeAndOffice, expected):
    assert [nursingHomeAndOffice.incomingT_F, nursingHomeAndOffice.supplyT_F, round(nursingHomeAndOffice.recirc_loss, 2), round(nursingHomeAndOffice.magnitude, 2)] == expected

@pytest.mark.parametrize("buildingType, magnitude, expected", [
   ("apartment",100,4280.0),
   (["elementary_school"],100,108.1),
   ("food_service_a",100,1103.2),
   ("food_service_b",100,628.8),
   ("junior_high",100,327.0),
   ("mens_dorm",[100],1890.),
   ("motel",100,2880.0),
   (["nursing_home"],[100],2010),
   ("office_building",100,111.0),
   ("senior_high",100,302.),
   ("womens_dorm",100,1640.),
   (["womens_dorm", "junior_high"],[100,5],1656.3)
])
def test_magnitudes(buildingType, magnitude, expected):
    building = createBuilding(
            incomingT_F     = 50,
            magnitudeStat  = magnitude,
            supplyT_F       = 120,
            buildingType   = buildingType,
            flowRate       = 5,
            returnT_F       = 100,
    )
    assert round(building.magnitude,1) == expected

@pytest.mark.parametrize("buildingType, magnitude, expected", [
   ("apartment",100,np.array([0.046728972, 0.044392523, 0.037383178])),
   (["food_service_a", "nursing_home"],[100,50],np.array([0.0, 0.00237169, 0.00237169])),
   (["womens_dorm", "junior_high"],[100,5],np.array([0.30189875, 0.1208078 , 0.0362846])),
   (["womens_dorm", "junior_high"],[5,100],np.array([0.06356968, 0.02933985, 0.01222494])),
   (["womens_dorm", "junior_high", "food_service_a", "nursing_home", "apartment"],[5,100, 50, 200, 500],np.array([0.03889, 0.03722, 0.03127]))
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
   ([1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],["womens_dorm", "junior_high"],[5,100],np.array([1, 0, 0]))
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
    multiFamilyWithBedrooms.setToAnnualLS()
    assert len(multiFamilyWithBedrooms.loadshape) == 8760
    assert len(multiFamilyWithBedrooms.avgLoadshape) == 8760

def test_annualLS_for_non_multi_family(nursingHomeAndOffice):
    assert len(nursingHomeAndOffice.loadshape) == 24
    assert len(nursingHomeAndOffice.avgLoadshape) == 24
    with pytest.raises(Exception, match="Annual loadshape not available for this building type. This feature is only available for multi-family buildings."):
        nursingHomeAndOffice.setToAnnualLS()
    assert len(nursingHomeAndOffice.loadshape) == 24
    assert len(nursingHomeAndOffice.avgLoadshape) == 24

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
    with pytest.raises(Exception, match="Missing values for multi-use building. Collected 2 building types but collected 1 magnitude varriables"):
        createBuilding(35, 4, 120, ["mens_dorm","yep"])
    with pytest.raises(Exception, match="Missing values for multi-use building. Collected 2 building types but collected 4 magnitude varriables"):
        createBuilding(35, [1,2,3,4], 120, ["mens_dorm","yep"])
    with pytest.raises(Exception, match="Missing values for multi-use building. Collected 1 building type but collected 3 magnitude varriables"):
        createBuilding(35, [4,7,8] , 120, ["mens_dorm"])
    with pytest.raises(Exception, match="No default loadshape found for building type yep."):
        createBuilding(35, [1,2], 120, ["mens_dorm","yep"])
    with pytest.raises(Exception, match="Climate Zone must be a number between 1 and 16."):
        createBuilding(35, 4, 120, "mens_dorm", climateZone = 18)
    with pytest.raises(Exception, match="Climate Zone must be a number between 1 and 16."):
        createBuilding(35, 4, 120, "mens_dorm", climateZone = 'yes')
    with pytest.raises(Exception, match="Climate Zone must be a number between 1 and 16."):
        createBuilding(35, 4, 120, "mens_dorm", climateZone = 0)
    with pytest.raises(Exception, match="18 is not a California zip code."):
        createBuilding(35, 4, 120, "mens_dorm", zipCode = 18)
    with pytest.raises(Exception, match="98122 is not a California zip code."):
        createBuilding(35, 4, 120, "mens_dorm", zipCode = 98122)
    with pytest.raises(Exception, match="the surf spot is not a California zip code."):
        createBuilding(35, 4, 120, "mens_dorm", zipCode = 'the surf spot')
    with pytest.raises(Exception, match="Annual simulation for non-multifamily buildings is not yet available."):
        createBuilding(35, 4, 120, "mens_dorm", annual=True)