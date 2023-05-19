import pytest
from ecoengine.objects.systemConfigUtils import roundList, mixVolume, hrToMinList, getPeakIndices
import ecoengine.engine.EcosizerEngine as EcosizerEngine
import numpy as np
import os, sys
from ecoengine.constants.Constants import *
from plotly.graph_objs import Figure

class QuietPrint:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout

# Fixtures
@pytest.fixture
def swing_sizer(): # Returns the hpwh swing tank
    with QuietPrint():
        hpwh = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            storageT_F      = 150,
            loadUpT_F       = 150,
            percentUseable  = 0.9, 
            aquaFract       = 0.4, 
            aquaFractLoadUp = 0.21,
            aquaFractShed   = 0.8,
            schematic       = 'swingtank', 
            buildingType   = 'multi_family',
            returnT_F       = 0, 
            flowRate       = 0,
            gpdpp           = 25,
            safetyTM        = 1.75,
            defrostFactor   = 1, 
            compRuntime_hr  = 16, 
            nApt            = 100, 
            Wapt            = 100,
            loadShiftSchedule        = [1,1,1,1,1,1,0,0,0,0,0,0,0,1,1,0,0,0,0,1,1,1,1,1],
            loadUpHours     = 3,
            doLoadShift     = True,
            loadShiftPercent       = 0.8
        )
    return hpwh

@pytest.fixture
def parallel_sizer(): # Returns the hpwh swing tank
    with QuietPrint():
        hpwh = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            storageT_F      = 150,
            loadUpT_F       = 150,
            percentUseable  = 0.9, 
            aquaFract       = 0.4, 
            aquaFractLoadUp = 0.21,
            aquaFractShed   = 0.8,
            schematic       = 'paralleltank', 
            buildingType   = 'multi_family',
            returnT_F       = 0, 
            flowRate       = 0,
            gpdpp           = 25,
            safetyTM        = 1.75,
            defrostFactor   = 1, 
            compRuntime_hr  = 16, 
            nApt            = 100, 
            Wapt            = 100,
            loadShiftSchedule        = [1,1,1,1,1,1,0,0,0,0,0,0,0,1,1,0,0,0,0,1,1,1,1,1],
            loadUpHours     = 3,
            doLoadShift     = True,
            loadShiftPercent       = 0.8,
            setpointTM_F    = 130,
            TMonTemp_F      = 120,
            offTime_hr      = 0.333
        )
    return hpwh

@pytest.fixture
def primary_sizer(): # Returns the hpwh swing tank
    with QuietPrint():
        hpwh = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            storageT_F      = 150,
            loadUpT_F       = 150,
            percentUseable  = 0.9, 
            aquaFract       = 0.4, 
            aquaFractLoadUp = 0.21,
            aquaFractShed   = 0.8,
            schematic       = 'primary', 
            buildingType   = 'multi_family',
            returnT_F       = 0, 
            flowRate       = 0,
            gpdpp           = 25,
            safetyTM        = 1.75,
            defrostFactor   = 1, 
            compRuntime_hr  = 16, 
            nApt            = 100, 
            Wapt            = 100,
            loadShiftSchedule        = [1,1,1,1,1,1,0,0,0,0,0,0,0,1,1,0,0,0,0,1,1,1,1,1],
            loadUpHours     = 3,
            #loadShiftSchedule = [1,1,1,1,1,1,0,0,0,0,0,0,0,1,1,0,0,0,0,1,1,1,1,1],
            doLoadShift     = True,
            loadShiftPercent= 0.8
        )
    return hpwh

###############################################################################
###############################################################################
# Unit Tests

@pytest.mark.parametrize("arr, expected", [
    ([1, 2, 1, 1, -3, -4, 7, 8, 9, 10, -2, 1, -3, 5, 6, 7, -10], [4,10,12,16]),
    ([1.3, 100.2, -500.5, 1e9, -1e-9, -5.5, 1,7,8,9,10, -1], [2,4,11]),
    ([-1, 0, 0, -5, 0, 0, 1, 7, 8, 9, 10, -1], [0,3,11])
])
def test_getPeakIndices( arr, expected):
    assert all(getPeakIndices(arr) == np.array(expected))

@pytest.mark.parametrize("hotT, coldT, outT, expected", [
   (125, 50, 120, 93.333),
   (120, 40, 120, 100.0),
   (150, 40, 120, 72.727),
   (100, 40, 120, 133.333)
])
def test_mixVolume(hotT, coldT, outT, expected):
    assert round(mixVolume(100, hotT, coldT, outT), 3) == expected

@pytest.mark.parametrize("sizingResult, magnitude", [
   ([1412.0829378753049, 145.14595864966793, 100, 59.712485, 168], 2500)
])
def test_swingSizingResult(swing_sizer, sizingResult, magnitude):
    assert swing_sizer.getSizingResults() == sizingResult
    assert swing_sizer.getHWMagnitude() == magnitude

@pytest.mark.parametrize("sizingResult, magnitude", [
   ([1141.554372892012, 112.45143269230772], 2500)
])
def test_primarySizingResult(primary_sizer, sizingResult, magnitude):
    assert primary_sizer.getSizingResults() == sizingResult
    assert primary_sizer.getHWMagnitude() == magnitude

@pytest.mark.parametrize("sizingResult, magnitude", [
   ([1141.554372892012, 112.45143269230772, 136.0194559548742, 59.712485], 2500)
])
def test_parallelSizingResult(parallel_sizer, sizingResult, magnitude):
    assert parallel_sizer.getSizingResults() == sizingResult
    assert parallel_sizer.getHWMagnitude() == magnitude

@pytest.mark.parametrize("return_as_div, expected", [
   (True, str),
   (False, Figure)
])
def test_figReturnTypes(parallel_sizer, swing_sizer, primary_sizer, return_as_div, expected):
    assert type(parallel_sizer.plotStorageLoadSim(return_as_div)) is expected
    assert type(swing_sizer.plotStorageLoadSim(return_as_div)) is expected
    assert type(primary_sizer.plotStorageLoadSim(return_as_div)) is expected

def test_primaryCurve(parallel_sizer):
    primaryCurveInfo = parallel_sizer.primaryCurve()
    assert len(primaryCurveInfo) == 4
    assert len(primaryCurveInfo[0]) == len(primaryCurveInfo[1]) == len(primaryCurveInfo[2]) #THIS IS FAILINGG
    assert primaryCurveInfo[3] == 44