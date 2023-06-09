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
            doLoadShift     = True,
            loadShiftPercent= 0.8
        )
    return hpwh

@pytest.fixture
def primary_sizer_nls(): 
    with QuietPrint():
        hpwh = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            storageT_F      = 150,
            percentUseable  = 0.9, 
            aquaFract       = 0.4, 
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
            doLoadShift     = False,
        )
    return hpwh

@pytest.fixture
def swing_sizer_nls(): 
    with QuietPrint():
        hpwh = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            storageT_F      = 150,
            percentUseable  = 0.9, 
            aquaFract       = 0.4, 
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
            doLoadShift     = False,
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
   ([1528.0027969823054, 150.75919907543388, 100, 59.712485, 168], 2500)
])
def test_swingSizingResult(swing_sizer, sizingResult, magnitude):
    assert swing_sizer.getSizingResults() == sizingResult
    assert swing_sizer.getHWMagnitude() == magnitude

@pytest.mark.parametrize("sizingResult", [
    ([540.4258388420066, 118.11496284632373, 100, 59.712485, 168])
])
def test_swingSizingNLSResult(swing_sizer_nls, sizingResult):
    assert swing_sizer_nls.getSizingResults() == sizingResult

@pytest.mark.parametrize("sizingResult, magnitude", [
   ([1141.554372892012, 112.45143269230772], 2500)
])
def test_primarySizingResult(primary_sizer, sizingResult, magnitude):
    assert primary_sizer.getSizingResults() == sizingResult
    assert primary_sizer.getHWMagnitude() == magnitude

@pytest.mark.parametrize("sizingResult", [
    ([467.6418425, 91.3667890625])
])
def test_primarySizingNLSResults(primary_sizer_nls, sizingResult):
    assert primary_sizer_nls.getSizingResults() == sizingResult

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

def test__parallel_simulationResults(parallel_sizer):
    simResult = parallel_sizer.getSimResult()
    assert len(simResult) == 4
    assert len(simResult[0]) == len(simResult[1]) == len(simResult[2]) == len(simResult[3]) == 4320
    assert simResult[0][:10] == [1028.0, 1027.528, 1027.057, 1026.585, 1026.114, 1025.642, 1025.171, 1024.699, 1024.228, 1023.756]
    assert simResult[1][-10:] == [3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205]
    assert simResult[2][-65:-55] == [1.86, 1.86, 1.86, 1.86, 1.86, 1.193, 1.193, 1.193, 1.193, 1.193]
    assert simResult[3][800:810] == [2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244]

def test__primary_simulationResults(primary_sizer):
    simResult = primary_sizer.getSimResult()
    assert len(simResult) == 4
    assert len(simResult[0]) == len(simResult[1]) == len(simResult[2]) == len(simResult[3]) == 4320
    assert simResult[0][:10] == [1028.0, 1027.528, 1027.057, 1026.585, 1026.114, 1025.642, 1025.171, 1024.699, 1024.228, 1023.756]
    assert simResult[1][-10:] == [3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205]
    assert simResult[2][-65:-55] == [1.86, 1.86, 1.86, 1.86, 1.86, 1.193, 1.193, 1.193, 1.193, 1.193]
    assert simResult[3][800:810] == [2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244]

def test__swing_simulationResults(swing_sizer):
    simResult = swing_sizer.getSimResult()
    assert len(simResult) == 7
    assert len(simResult[0]) == len(simResult[1]) == len(simResult[2]) == len(simResult[3]) == len(simResult[4]) == len(simResult[5]) == len(simResult[6]) == 4320
    assert simResult[0][:10] == [1376.0, 1375.528, 1375.054, 1374.576, 1374.094, 1373.61, 1373.122, 1372.63, 1372.135, 1371.637]
    assert simResult[1][-10:] == [4.297, 4.297, 4.297, 4.297, 4.297, 4.297, 4.297, 4.297, 4.297, 4.297]
    assert simResult[2][-65:-55] == [1.86, 1.86, 1.86, 1.86, 1.86, 1.193, 1.193, 1.193, 1.193, 1.193]
    assert simResult[3][800:810] == [3.008, 3.008, 3.008, 3.008, 3.008, 3.008, 3.008, 3.008, 3.008, 3.008]
    assert simResult[4][-10:] == [124.201, 125.002, 125.791, 126.568, 127.334, 128.0, 127.555, 127.115, 126.682, 126.256]
    assert simResult[5][-200:-190] == [0, 0, 0, 0, 0.013, 1, 1, 1, 1, 1]
    assert simResult[6][800:803] == [0.9489206357019205, 0.9384794009334938, 0.9283993792885612]

def test__swing_nls_simulationResults(swing_sizer_nls):
    simResult = swing_sizer_nls.getSimResult()
    assert len(simResult) == 7
    assert len(simResult[0]) == len(simResult[1]) == len(simResult[2]) == len(simResult[3]) == len(simResult[4]) == len(simResult[5]) == len(simResult[6]) == 4320
    assert simResult[0][:2] == [487.0, 486.557]
    assert simResult[1][-10:-8] == [3.367, 3.367]
    assert simResult[2][-65:-55] == [2.66, 2.66, 2.66, 2.66, 2.66, 1.013, 1.013, 1.013, 1.013, 1.013]
    assert simResult[3][800:810] == [2.357, 2.357, 2.357, 2.357, 2.357, 2.357, 2.357, 2.357, 2.357, 2.357]
    assert simResult[4][-10:-4] == [128.0, 127.519, 127.044, 126.575, 126.111, 125.653]
    assert simResult[5][-200:-190] == [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    assert simResult[6][800:803] == [0.9589199980931171, 0.9491629610090546, 0.9397239536905911]

def test__primary_nls_simulationResults(primary_sizer_nls):
    simResult = primary_sizer_nls.getSimResult()
    assert len(simResult) == 4
    assert len(simResult[0]) == len(simResult[1]) == len(simResult[2]) == len(simResult[3]) == 4320
    assert simResult[0][:10] == [421.0, 420.557, 420.113, 419.67, 419.227, 418.784, 418.34, 417.897, 417.454, 417.011]
    assert simResult[1][-10:] == [2.604, 2.604, 2.604, 2.604, 2.604, 2.604, 2.604, 2.604, 2.604, 2.604]
    assert simResult[2][-65:-55] == [2.66, 2.66, 2.66, 2.66, 2.66, 1.013, 1.013, 1.013, 1.013, 1.013]
    assert simResult[3][800:810] == [1.823, 1.823, 1.823, 1.823, 1.823, 1.823, 1.823, 1.823, 1.823, 1.823]

    # TODO add simulation tests for non load shifting