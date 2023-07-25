import pytest
from ecoengine.objects.systemConfigUtils import roundList, mixVolume, hrToMinList, getPeakIndices
import ecoengine.engine.EcosizerEngine as EcosizerEngine
import ecoengine.objects.SimulationRun as SimulationRun
import numpy as np
import os, sys, csv
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
            returnT_F       = None, 
            flowRate       = None,
            gpdpp           = 25,
            safetyTM        = 1.75,
            defrostFactor   = 1, 
            compRuntime_hr  = 16, 
            nApt            = 100, 
            Wapt            = None,
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
            returnT_F       = None, 
            flowRate       = None,
            gpdpp           = 25,
            safetyTM        = 1.75,
            defrostFactor   = 1, 
            compRuntime_hr  = 16, 
            nApt            = 100, 
            Wapt            = None,
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

@pytest.fixture
def annual_swing_sizer(): # Returns the hpwh swing tank
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
            Wapt            = 60,
            nBR             = [0,50,30,20,0,0],
            loadShiftSchedule        = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,1,1],
            loadUpHours     = 3,
            doLoadShift     = True,
            loadShiftPercent       = 0.8,
            PVol_G_atStorageT = 944.972083230641, 
            PCap_kBTUhr = 122.61152083930925, 
            TMVol_G = 100, 
            TMCap_kBTUhr = 59.712485,
            annual = True,
            climateZone = 1
        )
    return hpwh

climateZone_1_kg = [] # will contain first 1000 kGperkWh rows
with open(os.path.join(os.path.dirname(__file__), '../data/climate_data/kGperkWh_ByClimateZone.csv'), 'r') as kG_file:
    kG_reader = csv.reader(kG_file)
    next(kG_reader)
    for i in range(1000):
        kG_row = next(kG_reader)
        climateZone_1_kg.append(float(kG_row[0]))
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
    assert len(primaryCurveInfo[0]) == len(primaryCurveInfo[1]) == len(primaryCurveInfo[2])
    assert primaryCurveInfo[3] == 44

def test__parallel_simulationResults(parallel_sizer):
    simResult = parallel_sizer.getSimResult()
    assert len(simResult) == 6
    assert len(simResult[0]) == len(simResult[1]) == len(simResult[2]) == len(simResult[3]) == 4320
    assert simResult[0][:10] == [1027.528, 1027.057, 1026.585, 1026.114, 1025.642, 1025.171, 1024.699, 1024.228, 1023.756, 1023.284]
    assert simResult[1][-10:] == [3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205]
    assert simResult[2][-65:-55] == [1.86, 1.86, 1.86, 1.86, 1.86, 1.193, 1.193, 1.193, 1.193, 1.193]
    assert simResult[3][800:810] == [2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244]

def test__parallel_simRun(parallel_sizer):
    simRun = parallel_sizer.getSimRun()
    supplyToStorageFactor = 0.7
    for i in range(1,100):
        hopefulResult = simRun.getPrimaryVolume(i-1) + simRun.getPrimaryGeneration(i) - (simRun.getHWDemand(i) * supplyToStorageFactor)
        assert simRun.getPrimaryVolume(i) < hopefulResult + 0.01
        assert simRun.getPrimaryVolume(i) > hopefulResult - 0.01

def test__primary_simulationResults(primary_sizer):
    simResult = primary_sizer.getSimResult()
    assert len(simResult) == 4
    assert len(simResult[0]) == len(simResult[1]) == len(simResult[2]) == len(simResult[3]) == 4320
    assert simResult[0][:10] == [1027.528, 1027.057, 1026.585, 1026.114, 1025.642, 1025.171, 1024.699, 1024.228, 1023.756, 1023.284]
    assert simResult[1][-10:] == [3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205]
    assert simResult[2][-65:-55] == [1.86, 1.86, 1.86, 1.86, 1.86, 1.193, 1.193, 1.193, 1.193, 1.193]
    assert simResult[3][800:810] == [2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244]

def test__swing_simulationResults(swing_sizer):
    simResult = swing_sizer.getSimResult()
    assert len(simResult) == 7
    assert len(simResult[0]) == len(simResult[1]) == len(simResult[2]) == len(simResult[3]) == len(simResult[4]) == len(simResult[5]) == len(simResult[6]) == 4320
    assert simResult[0][:10] == [1375.528, 1375.054, 1374.576, 1374.094, 1373.61, 1373.122, 1372.63, 1372.135, 1371.637, 1371.135]
    assert simResult[1][-10:] == [4.297, 4.297, 4.297, 4.297, 4.297, 4.297, 4.297, 4.297, 4.297, 4.297]
    assert simResult[2][-65:-55] == [1.86, 1.86, 1.86, 1.86, 1.86, 1.193, 1.193, 1.193, 1.193, 1.193]
    assert simResult[3][800:810] == [3.008, 3.008, 3.008, 3.008, 3.008, 3.008, 3.008, 3.008, 3.008, 3.008]
    assert simResult[4][-10:] == [124.201, 125.002, 125.791, 126.568, 127.334, 128.0, 127.555, 127.115, 126.682, 126.256]
    assert simResult[5][-200:-190] == [0, 0, 0, 0, 0.013, 1, 1, 1, 1, 1]
    assert simResult[6][800:803] == [0.9489206357019205, 0.9384794009334938, 0.9283993792885612]

def test__primary_nls_simulationResults(primary_sizer_nls):
    simResult = primary_sizer_nls.getSimResult()
    assert len(simResult) == 4
    assert len(simResult[0]) == len(simResult[1]) == len(simResult[2]) == len(simResult[3]) == 4320
    assert simResult[0][:10] == [420.557, 420.113, 419.67, 419.227, 418.784, 418.34, 417.897, 417.454, 417.011, 416.567]
    assert simResult[1][-10:] == [2.604, 2.604, 2.604, 2.604, 2.604, 2.604, 2.604, 2.604, 2.604, 2.604]
    assert simResult[2][-65:-55] == [2.66, 2.66, 2.66, 2.66, 2.66, 1.013, 1.013, 1.013, 1.013, 1.013]
    assert simResult[3][800:810] == [1.823, 1.823, 1.823, 1.823, 1.823, 1.823, 1.823, 1.823, 1.823, 1.823]

# annual simulations
def test__annual_swing_simulationResults_size(annual_swing_sizer):
    simResult = annual_swing_sizer.getSimResult(initPV=0.4*944.972083230641, initST=135, minuteIntervals = 15, nDays = 365)
    assert len(simResult) == 7
    assert len(simResult[0]) == len(simResult[1]) == len(simResult[2]) == len(simResult[3]) == 35040

@pytest.mark.parametrize("aquaFractLoadUp, aquaFractShed, storageT_F, supplyT_F, loadShiftSchedule, hpwhModel, tmModel, simSchematic, PVol_G_atStorageT, PCap_kBTUhr, TMVol_G, TMCap_kBTUhr", [
   (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_SP', None, 'multipass', 891, 166, None, None),
   (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_ColmacCxA_10_MP', None, 'multipass', 891, 166, None, None),
   (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_C_SP', None, 'primaryrecirc', 891, 166, None, None),
   (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_SP', None, 'primary', 891, 166, None, None),
   (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_SANCO2_GS3_45HPA_US_SP', None, 'swingtank', 891, 166, 100, 60),
   (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_ColmacCxA_25_SP', None, 'swingtank', 891, 166, 100, 60),
   (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_SP', 'MODELS_NyleC185A_SP', 'paralleltank', 891, 106, 91, 60),
   (0.21, 0.8, 150, 122, [1,1,1,1,1,1,1,1,0,0,0,0,1,1,1,1,0,0,0,0,0,0,1,1], 'MODELS_ColmacCxA_15_SP', 'MODELS_ColmacCxA_20_SP', 'paralleltank', 891, 106, 91, 60),
   (0.21, 0.8, 150, 122, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_SP', 'MODELS_NyleC250A_C_SP', 'paralleltank', 891, 106, 91, 60)
])
def test_annual_simRun_values(aquaFractLoadUp, aquaFractShed, storageT_F, supplyT_F, loadShiftSchedule, hpwhModel, tmModel, simSchematic, PVol_G_atStorageT, PCap_kBTUhr, TMVol_G, TMCap_kBTUhr):
    hpwh_ls = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = supplyT_F,
            storageT_F      = storageT_F,
            loadUpT_F       = 150,
            percentUseable  = 0.9, 
            aquaFract       = 0.4, 
            aquaFractLoadUp = aquaFractLoadUp,
            aquaFractShed   = aquaFractShed,
            schematic       = simSchematic, 
            buildingType   = 'multi_family',
            returnT_F       = 0, 
            flowRate       = 0,
            gpdpp           = 25,
            safetyTM        = 1.75,
            defrostFactor   = 1, 
            compRuntime_hr  = 16, 
            nApt            = 100, 
            Wapt            = 60,
            loadShiftSchedule  = loadShiftSchedule,
            loadUpHours     = 3,
            doLoadShift     = True,
            loadShiftPercent       = 0.8,
            PVol_G_atStorageT = PVol_G_atStorageT, 
            PCap_kBTUhr = PCap_kBTUhr,
            TMVol_G = TMVol_G,
            TMCap_kBTUhr = TMCap_kBTUhr,
            annual = True,
            climateZone = 1,
            systemModel = hpwhModel,
            tmModel = tmModel
        )
    simRun = hpwh_ls.getSimRun(initPV=0.4*PVol_G_atStorageT, initST=135, minuteIntervals = 15, nDays = 365)
    supplyToStorageFactor = (supplyT_F - simRun.getIncomingWaterT(0))/(storageT_F - simRun.getIncomingWaterT(0)) # should be same for entire month
    TMcap = TMCap_kBTUhr
    if TMcap is None:
        TMcap = 0

    assert 1 == 1
    for i in range(1,1000):

        # assert primaryVolume = generation - demand
        if simSchematic == 'swingtank':
            hw_out_at_storage = simRun.gethwOutSwing(i)
        else:
            hw_out_at_storage = (simRun.getHWDemand(i)+simRun.getRecircLoss(i)) * supplyToStorageFactor
        hopefulResult = simRun.getPrimaryVolume(i-1) + simRun.getPrimaryGeneration(i) - hw_out_at_storage
        assert simRun.getPrimaryVolume(i) < hopefulResult + 0.01
        assert simRun.getPrimaryVolume(i) > hopefulResult - 0.01

        # assert hw generation rate makes sense
        calculated_generation = 1000 * (simRun.getCapOut(i)*W_TO_BTUHR) / rhoCp / (supplyT_F - simRun.getIncomingWaterT(i))
        assert simRun.getHWGeneration(i) < calculated_generation + 0.01
        assert simRun.getHWGeneration(i) > calculated_generation - 0.01
        calculated_generation *= supplyToStorageFactor * (simRun.getPrimaryRun(i)/15)
        assert simRun.getPrimaryGeneration(i) < calculated_generation + 0.01
        assert simRun.getPrimaryGeneration(i) > calculated_generation - 0.01

        # assert kW calculation is correct
        calculatedKg = climateZone_1_kg[i//4] * (simRun.getCapIn(i) * (simRun.getPrimaryRun(i) / 15) + (simRun.getTMCapIn(i)*simRun.getTMRun(i)/15))
        assert simRun.getkGCO2(i) < calculatedKg + 0.001
        assert simRun.getkGCO2(i) > calculatedKg - 0.001


    # ensure recirc non-existant for non-recirc-tracking systems
    if simSchematic != 'primaryrecirc' and simSchematic != 'multipass':
        assert simRun.getRecircLoss(0) == 0
        assert simRun.getRecircLoss(5000) == 0
        assert simRun.getRecircLoss(10000) == 0

    # assert COP calculations are the same (within rounding error of 0.002)
    equip_method_cop = simRun.getAnnualCOP()
    boundry_method_cop = simRun.getAnnualCOP(boundryMethod = True)
    assert equip_method_cop < boundry_method_cop + 0.002
    assert equip_method_cop > boundry_method_cop - 0.002