import pytest
from objects.systemConfigUtils import roundList, mixVolume, HRLIST_to_MINLIST, getPeakIndices
import engine.EcosizerEngine as EcosizerEngine
import numpy as np
import os, sys
from constants.Constants import *
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
        hpwh = EcosizerEngine.EcosizerEngine(
            incomingT_F     = 50,
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
    return hpwh

@pytest.fixture
def parallel_sizer(): # Returns the hpwh swing tank
    with QuietPrint():
        hpwh = EcosizerEngine.EcosizerEngine(
            incomingT_F     = 50,
            magnitude_stat  = 100,
            supplyT_F       = 120,
            storageT_F      = 150,
            percentUseable  = 0.8, 
            aquaFract       = 0.4, 
            schematic       = 'paralleltank', 
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
            cdf_shift       = 0.8,
            setpointTM_F    = 130,
            TMonTemp_F      = 120,
            offTime_hr      = 0.333
        )
    return hpwh

@pytest.fixture
def primary_sizer(): # Returns the hpwh swing tank
    with QuietPrint():
        hpwh = EcosizerEngine.EcosizerEngine(
            incomingT_F     = 50,
            magnitude_stat  = 100,
            supplyT_F       = 120,
            storageT_F      = 150,
            percentUseable  = 0.8, 
            aquaFract       = 0.4, 
            schematic       = 'primary', 
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

@pytest.mark.parametrize("expected", [
   ([1507.1634879836542, 151.2139605971942, 300, 59.712485])
])
def test_swingSizingResult(swing_sizer, expected):
    assert swing_sizer.getSizingResults() == expected

@pytest.mark.parametrize("expected", [
   ([1122.528466677145, 112.45143269230772])
])
def test_primarySizingResult(primary_sizer, expected):
    assert primary_sizer.getSizingResults() == expected

@pytest.mark.parametrize("expected", [
   ([1122.528466677145, 112.45143269230772, 136.0194559548742, 59.712485])
])
def test_parallelSizingResult(parallel_sizer, expected):
    assert parallel_sizer.getSizingResults() == expected

@pytest.mark.parametrize("return_as_div, expected", [
   (True, str),
   (False, Figure)
])
def test_figReturnTypes(parallel_sizer, return_as_div, expected):
    assert type(parallel_sizer.plotStorageLoadSim(return_as_div)) is expected

def test_primaryCurve(parallel_sizer):
    primaryCurveInfo = parallel_sizer.primaryCurve()
    assert len(primaryCurveInfo) == 4
    assert len(primaryCurveInfo[0]) == len(primaryCurveInfo[1]) == len(primaryCurveInfo[2])
    assert primaryCurveInfo[3] == 44