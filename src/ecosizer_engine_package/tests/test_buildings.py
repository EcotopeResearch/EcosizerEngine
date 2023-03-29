import pytest
from ecosizer_engine_package.engine.BuildingCreator import createBuilding
import numpy as np
import os, sys
from ecosizer_engine_package.constants.Constants import *

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
            magnitude_stat  = 100,
            supplyT_F       = 120,
            building_type   = 'multi_family',
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
            magnitude_stat  = 100,
            supplyT_F       = 120,
            building_type   = 'multi_family',
            nApt            = 100, 
            Wapt            = 100,
            gpdpp           = 'ca',
            nBR             = [0,1,5,3,2,0]
        )
    return building

@pytest.fixture
def nursingHomeAndOffice(): # Returns the hpwh swing tank
    with QuietPrint():
        building = createBuilding(
            incomingT_F     = 50,
            magnitude_stat  = [100, 75],
            supplyT_F       = 120,
            building_type   = ['nursing_home','office_building'],
            returnT_F       = 100, 
            flow_rate       = 5
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
            magnitude_stat  = magnitude,
            supplyT_F       = 120,
            building_type   = buildingType,
            flow_rate       = 5,
            returnT_F       = 100,
    )
    assert round(building.magnitude,1) == expected

@pytest.mark.parametrize("buildingType, magnitude, expected", [
   ("apartment",100,np.array([0.046728972, 0.044392523, 0.037383178])),
   (["food_service_a", "nursing_home"],[100,50],np.array([0.0, 0.00237169, 0.00237169])),
   (["womens_dorm", "junior_high"],[100,5],np.array([0.30189875, 0.1208078 , 0.0362846])),
   (["womens_dorm", "junior_high"],[5,100],np.array([0.06356968, 0.02933985, 0.01222494]))
])
def test_default_loadshapes(buildingType, magnitude, expected):
    building = createBuilding(
            incomingT_F     = 50,
            magnitude_stat  = magnitude,
            supplyT_F       = 120,
            building_type   = buildingType,
            flow_rate       = 5,
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
            magnitude_stat  = magnitude,
            supplyT_F       = 120,
            building_type   = buildingType,
            flow_rate       = 5,
            returnT_F       = 100,
            loadshape       = loadShape
    )
    assert np.array_equal(np.round(building.loadshape[:3], decimals=5), np.round(expected, decimals=5))

# Check for building initialization errors
def test_invalid_building_parameter_errors():
    with pytest.raises(Exception, match="No default loadshape found for building type climbing_gym."):
        createBuilding(35, 4, 120, "climbing_gym")
    with pytest.raises(Exception, match="Loadshape must be of length 24 but instead has length of 5."):
        createBuilding(35, 4, 120, "mens_dorm", loadshape=[1,2,3,4,5])
    with pytest.raises(Exception, match="Sum of the loadshape does not equal 1. Loadshape needs to be normalized."):
        createBuilding(35, 4, 120, "mens_dorm", loadshape=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24])
    with pytest.raises(Exception, match="Can not have negative load shape values in loadshape."):
        createBuilding(35, 4, 120, "mens_dorm", loadshape=[1,2,-3,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
    with pytest.raises(Exception, match="Error: Supply temp must be a number."):
        createBuilding(35, 4, "whoops", "mens_dorm")
    with pytest.raises(Exception, match="Error: Return temp must be a number."):
        createBuilding(35, 4, 120, "mens_dorm", returnT_F="uh oh")
    with pytest.raises(Exception, match="Error: Supply temp must be higher than return temp."):
        createBuilding(35, 4, 120, "mens_dorm", returnT_F=150)
    with pytest.raises(Exception, match="Error: City water temp must be a number."):
        createBuilding("not a number", 4, 120, "mens_dorm")
    with pytest.raises(Exception, match="Error: Flow rate must be a number."):
        createBuilding(35, 4, 120, "mens_dorm", flow_rate = "problem")
    with pytest.raises(Exception, match="Missing values for multi-use building. Collected 2 building types but collected 1 magnitude varriables"):
        createBuilding(35, 4, 120, ["mens_dorm","yep"])
    with pytest.raises(Exception, match="Missing values for multi-use building. Collected 2 building types but collected 4 magnitude varriables"):
        createBuilding(35, [1,2,3,4], 120, ["mens_dorm","yep"])
    with pytest.raises(Exception, match="Missing values for multi-use building. Collected 1 building type but collected 3 magnitude varriables"):
        createBuilding(35, [4,7,8] , 120, ["mens_dorm"])
    with pytest.raises(Exception, match="No default loadshape found for building type yep."):
        createBuilding(35, [1,2], 120, ["mens_dorm","yep"])