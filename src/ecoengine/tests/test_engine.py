import pytest
from ecoengine.objects.systemConfigUtils import roundList, convertVolume, hrToMinList, getPeakIndices
from ecoengine.engine.EcosizerEngine import *
from ecoengine.objects.SimulationRun import *
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
            schematic       = 'singlepass_norecirc', 
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
            schematic       = 'singlepass_norecirc', 
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
            PCap_kW = 122.61152083930925/W_TO_BTUHR, 
            TMVol_G = 100, 
            TMCap_kW = 59.712485/W_TO_BTUHR,
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
        climateZone_1_kg.append([float(kG_row[0]),
                                 float(kG_row[1]),
                                 float(kG_row[2]),
                                 float(kG_row[3]),
                                 float(kG_row[4]),
                                 float(kG_row[5]),
                                 float(kG_row[6]),
                                 float(kG_row[7]),
                                 float(kG_row[8]),
                                 float(kG_row[9]),
                                 float(kG_row[10]),
                                 float(kG_row[11]),
                                 float(kG_row[12]),
                                 float(kG_row[13]),
                                 float(kG_row[14]),
                                 float(kG_row[15])])
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

@pytest.mark.parametrize("convertToT_F, referenceT_F, convertFromT_F, expected", [
   (125, 50, 120, 93.333),
   (120, 40, 120, 100.0),
   (150, 40, 120, 72.727),
   (100, 40, 120, 133.333)
])
def test_convertVolume(convertToT_F, referenceT_F, convertFromT_F, expected):
    assert round(convertVolume(100, convertToT_F, referenceT_F, convertFromT_F), 3) == expected

@pytest.mark.parametrize("sizingResult, magnitude", [
   ([1579.8153948651493, 150.75919907543388, 100, 59.712485, 168], 2500)
])
def test_swingSizingResult(swing_sizer, sizingResult, magnitude):
    assert swing_sizer.getSizingResults() == sizingResult
    assert swing_sizer.getHWMagnitude() == magnitude

def test_plotSizingCurve_len(swing_sizer):
    assert len(swing_sizer.plotSizingCurve(returnAsDiv = True, returnWithXYPoints = True)) == 4

@pytest.mark.parametrize("sizingResult", [
    ([540.4258388420066, 118.11496284632376, 100, 59.712485, 168])
])
def test_swingSizingNLSResult(swing_sizer_nls, sizingResult):
    assert swing_sizer_nls.getSizingResults() == sizingResult

@pytest.mark.parametrize("sizingResult, magnitude", [
   ([1141.5543728920115, 112.45143269230772], 2500)
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
   ([1141.5543728920115, 112.45143269230772, 136.0194559548742, 59.712485], 2500)
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
    simRun = parallel_sizer.getSimRun()
    assert len(simRun.getPrimaryVolume()) == len(simRun.getHWGeneration()) == len(simRun.getHWDemand()) == len(simRun.getPrimaryGeneration()) == 4320
    assert simRun.getPrimaryVolume()[:10] == [1027.528, 1027.057, 1026.585, 1026.114, 1025.642, 1025.171, 1024.699, 1024.228, 1023.756, 1023.284]
    assert simRun.getHWGeneration()[-10:] == [3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205]
    assert simRun.getHWDemand()[-65:-55] == [1.86, 1.86, 1.86, 1.86, 1.86, 1.193, 1.193, 1.193, 1.193, 1.193]
    assert simRun.getPrimaryGeneration()[800:810] == [2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244]

def test__parallel_simRun(parallel_sizer):
    simRun = parallel_sizer.getSimRun()
    supplyToStorageFactor = 0.7
    for i in range(1,100):
        hopefulResult = simRun.getPrimaryVolume(i-1) + simRun.getPrimaryGeneration(i) - (simRun.getHWDemand(i) * supplyToStorageFactor)
        assert simRun.getPrimaryVolume(i) < hopefulResult + 0.01
        assert simRun.getPrimaryVolume(i) > hopefulResult - 0.01

def test__primary_simulationResults(primary_sizer):
    simRun = primary_sizer.getSimRun()
    assert len(simRun.getPrimaryVolume()) == len(simRun.getHWGeneration()) == len(simRun.getHWDemand()) == len(simRun.getPrimaryGeneration()) == 4320
    assert simRun.getPrimaryVolume()[:10] == [1027.528, 1027.057, 1026.585, 1026.114, 1025.642, 1025.171, 1024.699, 1024.228, 1023.756, 1023.284]
    assert simRun.getHWGeneration()[-10:] == [3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205, 3.205]
    assert simRun.getHWDemand()[-65:-55] == [1.86, 1.86, 1.86, 1.86, 1.86, 1.193, 1.193, 1.193, 1.193, 1.193]
    assert simRun.getPrimaryGeneration()[800:810] == [2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244, 2.244]

def test__swing_simulationResults(swing_sizer):
    simRun = swing_sizer.getSimRun()
    assert len(simRun.getPrimaryVolume()) == len(simRun.getHWGeneration()) == len(simRun.getTMRun()) == len(simRun.getTMTemp()) == 4320
    assert len(simRun.getHWDemand()) == len(simRun.getPrimaryGeneration()) == 4320

def test__primary_nls_simulationResults(primary_sizer_nls):
    simRun = primary_sizer_nls.getSimRun()
    assert len(simRun.getPrimaryVolume()) == len(simRun.getHWGeneration()) == len(simRun.getHWDemand()) == len(simRun.getPrimaryGeneration()) == 4320
    assert simRun.getPrimaryVolume()[:10] == [420.557, 420.113, 419.67, 419.227, 418.784, 418.34, 417.897, 417.454, 417.011, 416.567]
    assert simRun.getHWGeneration()[-10:] == [2.604, 2.604, 2.604, 2.604, 2.604, 2.604, 2.604, 2.604, 2.604, 2.604]
    assert simRun.getHWDemand()[-65:-55] == [2.66, 2.66, 2.66, 2.66, 2.66, 1.013, 1.013, 1.013, 1.013, 1.013]
    assert simRun.getPrimaryGeneration()[800:810] == [1.823, 1.823, 1.823, 1.823, 1.823, 1.823, 1.823, 1.823, 1.823, 1.823]

# annual simulations
def test__annual_swing_simulationResults_size(annual_swing_sizer):
    simRun = annual_swing_sizer.getSimRun(initPV=0.4*944.972083230641, initST=135, minuteIntervals = 15, nDays = 365)
    assert len(simRun.getPrimaryVolume()) == len(simRun.getHWGeneration()) == len(simRun.getHWDemand()) == len(simRun.getPrimaryGeneration()) == 35040

@pytest.mark.parametrize("aquaFractLoadUp, aquaFractShed, storageT_F, supplyT_F, loadShiftSchedule, hpwhModel, tmModel, simSchematic, PVol_G_atStorageT, PCap_kW, TMVol_G, TMCap_kW, doLoadShift, zipCode, climateZone", [
   (0.21, 0.8, 140, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_C_SP', None, 'multipass_norecirc', 891, 48, None, None, True, 94503,2),
   (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_ColmacCxA_10_C_MP', None, 'multipass_norecirc', 891, 48, None, None, True, 93901,3),
   (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_ColmacCxA_10_C_MP', None, 'multipass_rtp', 891, 48, None, None, True, 93254,4),
   (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_AOSmithCAHP120_C_MP', None, 'multipass_rtp', 891, 48, None, None, True, 93130,5),
   (0.21, 0.8, 140, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_C_SP', None, 'singlepass_rtp', 891, 48, None, None, True, 90003,8),
   (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_AOSmithCAHP120_C_MP', None, 'singlepass_rtp', 891, 48, None, None, True, 91902,7),
   (0.21, 0.8, 150, 120, None, 'MODELS_AOSmithCAHP120_C_MP', None, 'singlepass_rtp', 702, 41, None, None, False, 90003,8),
   (0.21, 0.8, 140, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_C_SP', None, 'singlepass_norecirc', 891, 48, None, None, True, 91701,10),
   (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_Mitsubishi_QAHV_C_SP', None, 'singlepass_norecirc', 891, 48, None, None, True, 91701,10),
   (0.21, 0.8, 145, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_SANCO2_C_SP', None, 'swingtank', 891, 48, 100, 19, True, 95603,11),
   (0.21, 0.8, 134, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_ColmacCxA_25_C_SP', None, 'swingtank', 891, 48, 100, 19, True, 93620,12),
   (0.21, 0.8, 140, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_C_SP', 'MODELS_RHEEM_HPHD60HNU_201_C_MP', 'paralleltank', 891, 31, 91, 19, True,91701,10),
   (0.21, 0.8, 141, 122, [1,1,1,1,1,1,1,1,0,0,0,0,1,1,1,1,0,0,0,0,0,0,1,1], 'MODELS_ColmacCxA_15_C_SP', 'MODELS_ColmacCxA_20_C_MP', 'paralleltank', 891, 31, 91, 19, True, 91916,14),
   (0.21, 0.8, 140, 122, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_C_SP', 'MODELS_RHEEM_HPHD135HNU_483_C_MP', 'paralleltank', 891, 31, 91, 19, True, 92004,15)
])
def test_annual_simRun_values(aquaFractLoadUp, aquaFractShed, storageT_F, supplyT_F, loadShiftSchedule, hpwhModel, tmModel, 
                              simSchematic, PVol_G_atStorageT, PCap_kW, TMVol_G, TMCap_kW, doLoadShift, zipCode, climateZone):
    hpwh_ls = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = supplyT_F,
            storageT_F      = storageT_F,
            loadUpT_F       = storageT_F,
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
            doLoadShift     = doLoadShift,
            loadShiftPercent       = 0.8,
            PVol_G_atStorageT = PVol_G_atStorageT, 
            PCap_kW = PCap_kW,
            TMVol_G = TMVol_G,
            TMCap_kW = TMCap_kW,
            annual = True,
            zipCode = zipCode,
            systemModel = hpwhModel,
            tmModel = tmModel
        )
    simRun = hpwh_ls.getSimRun(initPV=0.4*PVol_G_atStorageT, initST=135, minuteIntervals = 15, nDays = 365)
    supplyToStorageFactor = (supplyT_F - simRun.getIncomingWaterT(0))/(storageT_F - simRun.getIncomingWaterT(0)) # should be same for entire month

    assert hpwh_ls.getClimateZone() == climateZone
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
        calculated_generation = 1000 * (simRun.getCapOut(i)*W_TO_BTUHR) / rhoCp / (supplyT_F - simRun.getIncomingWaterT(i)) / 4 # divide by 4 because there are 4 15 min intervals in an hour
        assert simRun.getHWGeneration(i) < calculated_generation + 0.01
        assert simRun.getHWGeneration(i) > calculated_generation - 0.01
        calculated_generation *= supplyToStorageFactor * (simRun.getPrimaryRun(i)/15)
        assert simRun.getPrimaryGeneration(i) < calculated_generation + 0.01
        assert simRun.getPrimaryGeneration(i) > calculated_generation - 0.01

        # assert kW calculation is correct
        calculatedKg = climateZone_1_kg[i//4][climateZone-1] * (simRun.getCapIn(i) * (simRun.getPrimaryRun(i) / 60) + (simRun.getTMCapIn(i)*simRun.getTMRun(i)/60))
        assert simRun.getkGCO2(i) < calculatedKg + 0.001
        assert simRun.getkGCO2(i) > calculatedKg - 0.001


    # ensure recirc non-existant for non-recirc-tracking systems
    if simSchematic != 'singlepass_rtp' and simSchematic != 'multipass_rtp':
        assert simRun.getRecircLoss(0) == 0
        assert simRun.getRecircLoss(5000) == 0
        assert simRun.getRecircLoss(10000) == 0

    # assert COP calculations are the same (within rounding error of 0.002)
    equip_method_cop = simRun.getAnnualCOP()
    boundry_method_cop = simRun.getAnnualCOP(boundryMethod = True)
    assert equip_method_cop < boundry_method_cop + 0.005
    assert equip_method_cop > boundry_method_cop - 0.005

@pytest.mark.parametrize("aquaFractLoadUp, aquaFractShed, storageT_F, supplyT_F, loadShiftSchedule, hpwhModel, tmModel, simSchematic, PVol_G_atStorageT, PCap_kW, TMVol_G, TMCap_kW, zipCode, climateZone", [
   (0.21, 0.8, 140, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_C_SP', None, 'multipass_norecirc', 891, 48, None, None, 94922,1),
   (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_ColmacCxA_10_C_MP', None, 'multipass_rtp', 891, 48, None, None, 90001,8),
   (0.21, 0.8, 140, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_C_SP', None, 'singlepass_rtp', 891, 48, None, None, 90254,6),
   (0.21, 0.8, 140, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_C_SP', None, 'singlepass_norecirc', 891, 48, None, None, 91730,10),
   (0.21, 0.8, 145, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_SANCO2_C_SP', None, 'swingtank', 891, 48, 100, 19, 90255,8),
   (0.21, 0.8, 150, 122, [1,1,1,1,1,1,1,1,0,0,0,0,1,1,1,1,0,0,0,0,0,0,1,1], 'MODELS_ColmacCxA_15_C_SP', 'MODELS_ColmacCxA_20_C_MP', 'paralleltank', 891, 31, 91, 19, 91730,10),
])

def test_annual_simRun_comparison_values(aquaFractLoadUp, aquaFractShed, storageT_F, supplyT_F, loadShiftSchedule, hpwhModel, 
                                         tmModel, simSchematic, PVol_G_atStorageT, PCap_kW, TMVol_G, TMCap_kW, zipCode, climateZone):
    hpwh_ls = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = supplyT_F,
            storageT_F      = storageT_F,
            loadUpT_F       = storageT_F,
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
            PCap_kW = PCap_kW,
            TMVol_G = TMVol_G,
            TMCap_kW = TMCap_kW,
            annual = True,
            zipCode = zipCode,
            systemModel = hpwhModel,
            tmModel = tmModel
        )
    simRunsAndCalcs = hpwh_ls.getSimRunWithkWCalc(initPV=0.4*PVol_G_atStorageT, initST=135)
    assert len(simRunsAndCalcs) == 5
    assert hpwh_ls.getClimateZone() == climateZone
    simRun_ls = simRunsAndCalcs[0]
    simRun_nls = simRunsAndCalcs[1]
    for i in range(1,1000):
        # these always be the same because they are the same system model in the same building
        assert simRun_ls.getCapOut(i) == simRun_nls.getCapOut(i)
        assert simRun_ls.getCapIn(i) == simRun_nls.getCapIn(i)
        assert simRun_ls.getTMCapOut(i) == simRun_nls.getTMCapOut(i)
        assert simRun_ls.getTMCapIn(i) == simRun_nls.getTMCapIn(i)
        assert simRun_ls.getHWDemand(i) == simRun_nls.getHWDemand(i)
        assert simRun_ls.getRecircLoss(i) == simRun_nls.getRecircLoss(i)
        assert simRun_ls.getIncomingWaterT(i) == simRun_nls.getIncomingWaterT(i)

def test_invalid_getSimRunWithkWCalc(swing_sizer, primary_sizer_nls):
    with pytest.raises(Exception, match = "kgCO2/kWh calculation is only available for annual simulations."):
        swing_sizer.getSimRunWithkWCalc()
    with pytest.raises(Exception, match = "Cannot preform kgCO2/kWh calculation on non-loadshifting systems."):
        primary_sizer_nls.getSimRunWithkWCalc()

@pytest.mark.parametrize("climateZone", [
   (1),(2),(3),(4),(5),(6),(7),(8),(9),(10),(11),(12),(13),(14),(15),(16)
])
def test_annual_QAVH_for_all_climates(climateZone):
    hpwh = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            storageT_F      = 150,
            percentUseable  = 0.9, 
            aquaFract       = 0.4,
            schematic       = "singlepass_norecirc", 
            buildingType   = 'multi_family',
            gpdpp           = 25,
            defrostFactor   = 1, 
            compRuntime_hr  = 16, 
            nApt            = 100, 
            Wapt            = 60,
            doLoadShift     = False,
            PVol_G_atStorageT = 891,
            # PCap_kW = 48,
            numHeatPumps=1,
            annual = True,
            climateZone = climateZone,
            systemModel = "MODELS_Mitsubishi_QAHV_C_SP"
        )
    simRun = hpwh.getSimRun(minuteIntervals = 15, nDays = 365)

    assert hpwh.getClimateZone() == climateZone

    # assert COP calculations are the same (within rounding error of 0.002)
    equip_method_cop = simRun.getAnnualCOP()
    boundry_method_cop = simRun.getAnnualCOP(boundryMethod = True)
    assert equip_method_cop < boundry_method_cop + 0.003
    assert equip_method_cop > boundry_method_cop - 0.003

def test_short_cycle_override():
    with pytest.raises(ValueError, 
                       match="('01', 'The aquastat fraction is too low in the storge system recommend increasing the maximum run hours in the day or increasing to a minimum of: ', 0.517)"):
        hpwh = EcosizerEngine(incomingT_F = 50.0,magnitudeStat = 1,supplyT_F = 110.0,storageT_F = 165.0, percentUseable = 0.85,aquaFract = 0.45,aquaFractLoadUp = None,
            aquaFractShed = None,loadUpT_F = None,loadUpHours = None,schematic = "swingtank",buildingType  = "multi_family",returnT_F = 100,flowRate = 8.0,
            loadshape = [0.07272037, 0.03588551, 0.01756301, 0.02060094, 0.00778469, 0.00830683,
            0.00028481, 0.01571178, 0.03484122, 0.08401766, 0.06925523, 0.05135995
            , 0.03213557, 0.03137609, 0.05957184, 0.05197703, 0.06223003, 0.05150235
            , 0.08112213, 0.05207196, 0.04452461, 0.02829069, 0.04480942, 0.0420563],
            gpdpp = 21067.0,nBR = None,safetyTM = 1.75,defrostFactor  = 1.0,compRuntime_hr = 16,nApt = 1,Wapt = None,setpointTM_F = 135.0,TMonTemp_F = 125.0,
            offTime_hr = 0.33,standardGPD = None,loadShiftSchedule = [],doLoadShift   = False,loadShiftPercent = None
        )
    hpwh = EcosizerEngine(incomingT_F = 50.0,magnitudeStat = 1,supplyT_F = 110.0,storageT_F = 165.0, percentUseable = 0.85,aquaFract = 0.45,aquaFractLoadUp = None,
            aquaFractShed = None,loadUpT_F = None,loadUpHours = None,schematic = "swingtank",buildingType  = "multi_family",returnT_F = 100,flowRate = 8.0,
            loadshape = [0.07272037, 0.03588551, 0.01756301, 0.02060094, 0.00778469, 0.00830683,
            0.00028481, 0.01571178, 0.03484122, 0.08401766, 0.06925523, 0.05135995
            , 0.03213557, 0.03137609, 0.05957184, 0.05197703, 0.06223003, 0.05150235
            , 0.08112213, 0.05207196, 0.04452461, 0.02829069, 0.04480942, 0.0420563],
            gpdpp = 21067.0,nBR = None,safetyTM = 1.75,defrostFactor  = 1.0,compRuntime_hr = 16,nApt = 1,Wapt = None,setpointTM_F = 135.0,TMonTemp_F = 125.0,
            offTime_hr = 0.33,standardGPD = None,loadShiftSchedule = [],doLoadShift   = False,loadShiftPercent = None, ignoreShortCycleEr = True
    )
    assert 598.0958941412142 == hpwh.getSizingResults()[0] 
    assert 722.2618842984205 == hpwh.getSizingResults()[1] 
    