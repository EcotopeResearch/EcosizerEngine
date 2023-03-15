import pytest
from utils import roundList, mixVolume, HRLIST_to_MINLIST, getPeakIndices
import EcosizerEngine
import numpy as np
import os, sys

class QuietPrint:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout

# Fixtures
@pytest.fixture
def swing_sizer(): # Returns the hpwh sizer object designed for Cali options
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
   ([1507.1634879836542, 151.2139605971942, 300, 59.712485]),
])
def test_sizingResult(swing_sizer, expected):
    assert swing_sizer.getSizingResults() == expected
