import pytest
from ecosizer_engine_package.engine.SystemCreator import createSystem
from ecosizer_engine_package.engine.BuildingCreator import createBuilding
import os, sys
from ecosizer_engine_package.constants.Constants import *

class QuietPrint:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout

default_building = createBuilding(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            buildingType   = 'multi_family',
            nApt            = 100, 
            Wapt            = 100,
            gpdpp           = 25
        )

# Fixtures
@pytest.fixture
def simplePrimary(): # Returns the hpwh swing tank
    with QuietPrint():
        system = createSystem(
            schematic   = 'primary', 
            building    = default_building, 
            storageT_F  = 150, 
            defrostFactor   = 1, 
            percentUseable  = .8, 
            compRuntime_hr  = 16, 
            aquaFract   = 0.4
        )
    return system

@pytest.fixture
def parallellTank(): # Returns the hpwh swing tank
    with QuietPrint():
        system = createSystem(
            schematic   = 'paralleltank', 
            building    = default_building, 
            storageT_F  = 150, 
            defrostFactor   = 1, 
            percentUseable  = .8, 
            compRuntime_hr  = 16, 
            aquaFract   = 0.4
        )
    return system

@pytest.fixture
def swingTank(): # Returns the hpwh swing tank
    with QuietPrint():
        system = createSystem(
            schematic   = 'swingtank', 
            building    = default_building, 
            storageT_F  = 150, 
            defrostFactor   = 1, 
            percentUseable  = .8, 
            compRuntime_hr  = 16, 
            aquaFract   = 0.4
        )
    return system

###############################################################################
###############################################################################
# Unit Tests

@pytest.mark.parametrize("expected", [
   ([467.6418425, 91.3667890625, [1]*24, 16])
])
def test_primaryResults(simplePrimary, expected):
    assert [simplePrimary.PVol_G_atStorageT, simplePrimary.PCap_kBTUhr, simplePrimary.loadShiftSchedule, simplePrimary.maxDayRun_hr] == expected

@pytest.mark.parametrize("expected", [
   ([467.6418425, 91.3667890625, [1]*24, 16, 90.67963730324946, 59.712485])
])
def test_parallelResults(parallellTank, expected):
    assert [parallellTank.PVol_G_atStorageT, parallellTank.PCap_kBTUhr, 
            parallellTank.loadShiftSchedule, parallellTank.maxDayRun_hr,
            parallellTank.TMVol_G, parallellTank.TMCap_kBTUhr] == expected
    
@pytest.mark.parametrize("expected", [
   ([540.4258388420066, 118.11496284632373, [1]*24, 16, 100, 59.712485]) 
])
def test_swingResults(swingTank, expected):
    assert [swingTank.PVol_G_atStorageT, swingTank.PCap_kBTUhr, 
            swingTank.loadShiftSchedule, swingTank.maxDayRun_hr,
            swingTank.TMVol_G, swingTank.TMCap_kBTUhr] == expected


# Check for system initialization errors
def test_invalid_system_parameter_errors():
    with pytest.raises(Exception, match="Invalid input given for Storage temp, it must be between 32 and 212F."):
        createSystem("swingtank", default_building, 15, 1, 0.8, 16, 0.4)
    with pytest.raises(Exception, match="Unknown system schematic type."):
        createSystem("fakesystem", default_building, 150, 1, 0.8, 16, 0.4)
    with pytest.raises(Exception, match="Invalid input given for Defrost Factor, must be a number between 0 and 1."):
        createSystem("swingtank", default_building, 150, 3, 0.8, 16, 0.4)
    with pytest.raises(Exception, match="Invalid input given for percentUseable, must be a number between 0 and 1."):
        createSystem("swingtank", default_building, 150, 1, 1.8, 16, 0.4)
    with pytest.raises(Exception, match="Invalid input given for percentUseable, must be a number between 0 and 1."):
        createSystem("swingtank", default_building, 150, 1, 'zebrah', 16, 0.4)
    with pytest.raises(Exception, match="Invalid input given for compRuntime_hr, must be an integer between 0 and 24."):
        createSystem("swingtank", default_building, 150, 1, 0.8, '16', 0.4)
    with pytest.raises(Exception, match="Invalid input given for compRuntime_hr, must be an integer between 0 and 24."):
        createSystem("swingtank", default_building, 150, 1, 0.8, 25, 0.4)
    with pytest.raises(Exception, match="Invalid input given for aquaFract must, be a number between 0 and 1."):
        createSystem("swingtank", default_building, 150, 1, 0.8, 16, 0.)
    with pytest.raises(Exception, match="Invalid input given for loadShiftPercent, must be a number between 0 and 1."):
        createSystem("swingtank", default_building, 150, 1, 0.8, 16, 0.4, loadShiftPercent = 'eighteen')
    with pytest.raises(Exception, match="Invalid input given for doLoadShift, must be a boolean."):
        createSystem("swingtank", default_building, 150, 1, 0.8, 16, 0.4, doLoadShift = 'eighteen')
    with pytest.raises(Exception, match="The saftey factor for the temperature maintenance system must be greater than 1 or the system will never keep up with the losses."):
        createSystem("swingtank", default_building, 150, 1, 0.8, 16, 0.4, safetyTM = 0.2)
    with pytest.raises(Exception, match="The saftey factor for the temperature maintenance system must be greater than 1 or the system will never keep up with the losses."):
        createSystem("paralleltank", default_building, 150, 1, 0.8, 16, 0.4, safetyTM = 0.2)
    with pytest.raises(Exception, match="The One Cycle Off Time the temperature maintenance system must be a float bigger than zero and less than or equal to one hour."):
        createSystem("paralleltank", default_building, 150, 1, 0.8, 16, 0.4, offTime_hr = 0.)
    with pytest.raises(Exception, match="The expected run time of the parallel tank is less time the minimum runtime for a HPWH of " + str(tmCompMinimumRunTime*60)+ " minutes."):
        createSystem("paralleltank", default_building, 150, 1, 0.8, 16, 0.4, offTime_hr = 0.1, safetyTM = 5)
    with pytest.raises(Exception, match="Invalid input given for setpointTM_F, it must be between 32 and 212F."):
        createSystem("paralleltank", default_building, 150, 1, 0.8, 16, 0.4, setpointTM_F = 5)
    with pytest.raises(Exception, match="Invalid input given for TMonTemp_F, it must be between 32 and 212F."):
        createSystem("paralleltank", default_building, 150, 1, 0.8, 16, 0.4, TMonTemp_F = 5)
    with pytest.raises(Exception, match="The temperature maintenance setpoint temperature must be greater than the turn on temperature"):
        createSystem("paralleltank", default_building, 150, 1, 0.8, 16, 0.4, TMonTemp_F = 135, setpointTM_F = 135)
    with pytest.raises(Exception, match="The temperature maintenance setpoint temperature must be greater than the city cold water temperature"):
        createSystem("paralleltank", default_building, 150, 1, 0.8, 16, 0.4, setpointTM_F = 34, TMonTemp_F = 33)
    with pytest.raises(Exception, match="The temperature maintenance on temperature must be greater than the city cold water temperature"):
        createSystem("paralleltank", default_building, 150, 1, 0.8, 16, 0.4, TMonTemp_F = 34)