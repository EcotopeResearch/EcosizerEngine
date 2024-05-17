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
def swing_sizer_er_nls(): 
    with QuietPrint():
        hpwh = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            storageT_F      = 150,
            percentUseable  = 0.9, 
            aquaFract       = 0.4, 
            schematic       = 'swingtank_er', 
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
            PVol_G_atStorageT = 890, 
            PCap_kW = 10,
            TMVol_G = 100,
            TMCap_kW = 19,
            sizeAdditionalER=True
        )
    return hpwh

@pytest.fixture
def annual_swing_sizer(): # Returns the hpwh swing tank
    with QuietPrint():
        hpwh = EcosizerEngine(
            incomingT_F     = None,
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

@pytest.mark.parametrize("hpwhModel, numHP, expectedCap, oat, inlet, outlet, return_as_kW, defrost_derate", 
                         [
                            ("MODELS_Mitsubishi_QAHV_C_SP", 3, 40.0 * 3, 61.0, 53.0, 139.0, True, 0.0),
                            ("MODELS_NyleC125A_C_SP", 5, 34.18 * 5, 60.0, 75.0, 140.0, True, 0.0),
                            ("MODELS_ColmacCxA_20_C_SP", 35, 53.3 * 35, 58.0, 40.0, 120.0, True, 0.0),
                            ("MODELS_Mitsubishi_QAHV_C_SP", 1, 30.0, 61.0, 53.0, 139.0, True, 0.25),
                            ("MODELS_Mitsubishi_QAHV_C_SP", 1, 20.0 * W_TO_BTUHR, 61.0, 53.0, 139.0, False, 0.5),
                        ])
def test_getHPWHOutputCapacity(hpwhModel, numHP, expectedCap, oat, inlet, outlet, return_as_kW, defrost_derate):
    assert getHPWHOutputCapacity(hpwhModel, oat, inlet, outlet, numHP, return_as_kW, defrost_derate) == expectedCap

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

@pytest.mark.parametrize("return_as_div, expected", [
   (True, str),
   (False, Figure)
])
def test_figReturnTypesER(parallel_sizer, swing_sizer, primary_sizer, swing_sizer_er_nls, return_as_div, expected):
    # for system in [parallel_sizer, swing_sizer, primary_sizer]:
    with pytest.raises(Exception, match="erSizedPoints function is only applicable to systems with swing tank electric resistance trade-off capabilities."):
        parallel_sizer.erSizedPointsPlot(return_as_div)
    with pytest.raises(Exception, match="erSizedPoints function is only applicable to systems with swing tank electric resistance trade-off capabilities."):
        swing_sizer.erSizedPointsPlot(return_as_div)
    with pytest.raises(Exception, match="erSizedPoints function is only applicable to systems with swing tank electric resistance trade-off capabilities."):
        primary_sizer.erSizedPointsPlot(return_as_div)
    assert type(swing_sizer_er_nls.erSizedPointsPlot(return_as_div)) is expected

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

@pytest.mark.parametrize(
        "zipC, nBR, storageT_F, aqFrac, aqFrac_lu, aqFrac_shed, luT_F, schematic, systemModel, numPumps, pVol, TMCap_kW, tmModel, TMVol_G, tmNumHeatPumps, loadshift_capacity, kGperkWh_saved, annual_kGCO2_saved", 
        [
            # (zipC, nBR, storageT_F, aqFrac, aqFrac_lu, aqFrac_shed, luT_F, schematic, systemModel, numPumps, pVol, TMCap_kW, tmModel, TMVol_G, tmNumHeatPumps, loadshift_capacity, kGperkWh_saved, annual_kGCO2_saved),
            (90210, [0,100,50,0,0,0], 140, 0.4, 0.2, 0.8, 140, 'swingtank', "MODELS_NyleC125A_C_SP", 4, 1200, 18, None, 150, None, 134.06, 3.58, 479.89),
            (90023, [5,120,70,9,4,1], 150, .45, .15, .85, 160, 'swingtank', "MODELS_LYNC_AEGIS_350_SIMULATED_C_SP", 3, 2000, 20, None, 150, None, 329.22, 5.58, 1838.57),
            (90023, [5,120,70,9,4,1], 150, .45, .15, .85, 160, 'swingtank', "MODELS_LYNC_AEGIS_500_SIMULATED_C_SP", 2, 1700, 17, None, 150, None, 279.84, 5.32, 1488.6),
            (91023, [50,6,50,20,4,1], 140, .45, .15, .85, 140, 'paralleltank', "MODELS_SANCO2_C_SP", 20, 1200, None, "MODELS_AOSmithHPTS50_R_MP", 150, 6, 169.11, 3.89, 658.26),
            (91023, [50,6,50,20,4,1], 140, .45, .15, .85, 140, 'paralleltank', "MODELS_Mitsubishi_QAHV_C_SP", 3, 1800, None, "MODELS_AOSmithHPTS50_R_MP", 150, 6, 253.67, 6.06, 1536.16),
            (91023, [50,0,0,0,0,0], 150, .40, .2, .8, 160, 'singlepass_rtp', "MODELS_Mitsubishi_QAHV_C_SP", 1, 500, None, None, None, None, 75.09, 9.61, 721.48),
            (91023, [50,0,0,0,0,0], 150, .40, .2, .8, 160, 'singlepass_norecirc', "MODELS_Mitsubishi_QAHV_C_SP", 1, 500, None, None, None, None, 75.09, 7.07, 530.93),
            (91023, [50,100,0,0,0,0], 150, .40, .2, .8, 160, 'multipass_norecirc', "MODELS_ColmacCxA_30_C_MP", 1, 1850, None, None, None, None, 69.45, 5.11, 354.67),
            (91023, [50,100,0,0,0,0], 150, .40, .2, .8, 160, 'multipass_rtp', "MODELS_ColmacCxA_30_C_MP", 1, 2200, None, None, None, None, 82.59, 0.4, 33.05)

        ]
)
def test_hard_SGIP_page_results(zipC, nBR, storageT_F, aqFrac, aqFrac_lu, aqFrac_shed, luT_F, schematic, systemModel, 
                                numPumps, pVol, TMCap_kW, tmModel, TMVol_G, tmNumHeatPumps, loadshift_capacity, kGperkWh_saved, annual_kGCO2_saved):
    nApt = int(sum( nBR ))
    rBR = [1.37,1.74,2.57,3.11,4.23,3.77] 
    npep = np.dot(nBR, rBR)
    building = createBuilding(50, sum(nBR), 150, 'multi_family', loadshape = None, avgLoadshape = None,
        returnT_F = 0, flowRate = 0, gpdpp = 0, nBR = nBR, nApt = 0, Wapt = 0, standardGPD = 'ca')
    gpdpp = building.magnitude/sum(nBR)
    
    hpwh = EcosizerEngine(
            magnitudeStat = npep,
            supplyT_F = 120,
            storageT_F = storageT_F,
            percentUseable = 0.95,
            aquaFract = aqFrac,
            aquaFractLoadUp = aqFrac_lu,
            aquaFractShed = aqFrac_shed,
            loadUpT_F = luT_F,
            loadUpHours = 2, # might need to change for future
            schematic = schematic,
            buildingType  = 'multi_family',
            gpdpp = gpdpp,
            compRuntime_hr = 16,
            nApt = nApt,
            Wapt = 60,
            standardGPD = 'ca',
            nBR = nBR,
            loadShiftSchedule = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,1],
            doLoadShift   = True,
            zipCode=zipC,
            annual=True,
            systemModel=systemModel,
            numHeatPumps=numPumps,
            PVol_G_atStorageT=pVol,
            TMCap_kW=TMCap_kW,
            tmModel=tmModel,
            TMVol_G=TMVol_G,
            tmNumHeatPumps = tmNumHeatPumps,                          
    )
    outlist = hpwh.getSimRunWithkWCalc(minuteIntervals = 15, nDays = 365)
    assert round(outlist[2],2) == loadshift_capacity
    assert round(outlist[3],2) == kGperkWh_saved
    assert round(outlist[4],2) == annual_kGCO2_saved

@pytest.mark.parametrize(
        "aquaFractLoadUp, aquaFractShed, storageT_F, supplyT_F, hpwhModel, simSchematic, PVol_G_atStorageT, PCap_kW, TMVol_G, TMCap_kW, doLoadShift, zipCode, usePkl", 
        [
            (0.21, 0.8, 140, 120, 'MODELS_VOLTEX80_R_MP', 'multipass_norecirc', 891, 48, None, None, True, 94503, False),
            (0.21, 0.8, 150, 120, 'MODELS_ColmacCxA_10_C_MP', 'multipass_norecirc', 891, 48, None, None, True, 93901, True),
            (0.21, 0.8, 145, 120, None, 'swingtank_er', 891, 20, 100, 19, True, 95603, False),
            (0.21, 0.8, 145, 120, None, 'swingtank_er', 891, 20, 100, 19, True, None, False),
        ]
)
def test_sizing_for_simRun(aquaFractLoadUp, aquaFractShed, storageT_F, supplyT_F, hpwhModel, 
                              simSchematic, PVol_G_atStorageT, PCap_kW, TMVol_G, TMCap_kW, doLoadShift, zipCode, usePkl):
    hpwh = EcosizerEngine(
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
            loadShiftSchedule  = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1],
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
            sizeAdditionalER= True if simSchematic == 'swingtank_er' else False
        )
    simRun = hpwh.getSimRun(initPV=0.4*PVol_G_atStorageT, initST=135, minuteIntervals = 15, nDays = 365)
    assert len(simRun.getHWGeneration()) == 8760*4
    assert hpwh.system.perfMap.usePkl == usePkl

@pytest.mark.parametrize(
        "aquaFractLoadUp, aquaFractShed, storageT_F, supplyT_F, hpwhModel, PVol_G_atStorageT, PCap_kW, TMVol_G, TMCap_kW, doLoadShift, zipCode, annual, produce_error", 
        [
            (0.21, 0.8, 145, 120, None, 891, 20, 100, 19, True, 95603, True, True),
            (0.21, 0.8, 145, 120, None, 891, 20, 100, 19, True, None, True, True),
            (0.21, 0.8, 145, 120, None, 891, 20, 100, 29, True, None, True, False),
            (0.21, 0.8, 145, 120, None, 891, 20, 100, 29, False, None, False, False),
            (0.21, 0.8, 145, 120, "MODELS_SANCO2_C_SP", 891, None, 100, 67, False, 95603, True, False),
        ]
)
def test_er_undersized_error(aquaFractLoadUp, aquaFractShed, storageT_F, supplyT_F, hpwhModel, 
                              PVol_G_atStorageT, PCap_kW, TMVol_G, TMCap_kW, doLoadShift, zipCode, annual, produce_error):
    hpwh = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = supplyT_F,
            storageT_F      = storageT_F,
            loadUpT_F       = storageT_F,
            percentUseable  = 0.9, 
            aquaFract       = 0.4, 
            aquaFractLoadUp = aquaFractLoadUp,
            aquaFractShed   = aquaFractShed,
            schematic       = 'swingtank_er', 
            buildingType   = 'multi_family',
            returnT_F       = 0, 
            flowRate       = 0,
            gpdpp           = 25,
            safetyTM        = 1.75,
            defrostFactor   = 1, 
            compRuntime_hr  = 16, 
            nApt            = 100, 
            Wapt            = 60,
            loadShiftSchedule  = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1],
            loadUpHours     = 3,
            doLoadShift     = doLoadShift,
            loadShiftPercent       = 0.8,
            PVol_G_atStorageT = PVol_G_atStorageT, 
            PCap_kW = PCap_kW,
            TMVol_G = TMVol_G,
            TMCap_kW = TMCap_kW,
            annual = annual,
            zipCode = zipCode,
            systemModel = hpwhModel,
            numHeatPumps = 1,
            sizeAdditionalER = False
        )
    if produce_error:
        with pytest.raises(Exception, match="The swing tank dropped below the supply temperature! The system is undersized"):
            hpwh.getSimRun(initPV=0.4*PVol_G_atStorageT, initST=135, minuteIntervals = 15, nDays = 365)
        hpwh = EcosizerEngine(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = supplyT_F,
            storageT_F      = storageT_F,
            loadUpT_F       = storageT_F,
            percentUseable  = 0.9, 
            aquaFract       = 0.4, 
            aquaFractLoadUp = aquaFractLoadUp,
            aquaFractShed   = aquaFractShed,
            schematic       = 'swingtank_er', 
            buildingType   = 'multi_family',
            returnT_F       = 0, 
            flowRate       = 0,
            gpdpp           = 25,
            safetyTM        = 1.75,
            defrostFactor   = 1, 
            compRuntime_hr  = 16, 
            nApt            = 100, 
            Wapt            = 60,
            loadShiftSchedule  = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1],
            loadUpHours     = 3,
            doLoadShift     = doLoadShift,
            loadShiftPercent       = 0.8,
            PVol_G_atStorageT = PVol_G_atStorageT, 
            PCap_kW = PCap_kW,
            TMVol_G = TMVol_G,
            TMCap_kW = TMCap_kW,
            annual = annual,
            zipCode = zipCode,
            systemModel = hpwhModel,
            sizeAdditionalER = True
        )
        assert hpwh.system.TMCap_kBTUhr > TMCap_kW * W_TO_BTUHR
    else:
        simRun = hpwh.getSimRun(initPV=0.4*PVol_G_atStorageT, initST=135, minuteIntervals = 15, nDays = 365)
        assert len(simRun.getHWGeneration()) == 8760*4
        assert round(hpwh.system.TMCap_kBTUhr,2) == round(TMCap_kW * W_TO_BTUHR, 2) 

@pytest.mark.parametrize("aquaFractLoadUp, aquaFractShed, storageT_F, supplyT_F, loadShiftSchedule, hpwhModel, tmModel, simSchematic, PVol_G_atStorageT, PCap_kW, TMVol_G, TMCap_kW, doLoadShift, zipCode, climateZone", [
   (0.21, 0.8, 140, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_VOLTEX80_R_MP', None, 'multipass_norecirc', 891, 48, None, None, True, 94503,2),
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
   (0.21, 0.8, 127, 122, [1,1,1,1,1,1,1,1,0,0,0,0,1,1,1,1,0,0,0,0,0,0,1,1], 'MODELS_ColmacCxA_15_C_SP', 'MODELS_ColmacCxA_20_C_MP', 'paralleltank', 891, 31, 91, 19, True, 91916,14),
   (0.21, 0.8, 140, 122, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_C_SP', 'MODELS_RHEEM_HPHD135HNU_483_C_MP', 'paralleltank', 891, 31, 91, 19, True, 92004,15)
])
def test_annual_simRun_values(aquaFractLoadUp, aquaFractShed, storageT_F, supplyT_F, loadShiftSchedule, hpwhModel, tmModel, 
                              simSchematic, PVol_G_atStorageT, PCap_kW, TMVol_G, TMCap_kW, doLoadShift, zipCode, climateZone):
    hpwh_ls = EcosizerEngine(
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
   (0.21, 0.8, 140, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_AOSmithCAHP120_C_MP', None, 'multipass_norecirc', 891, 48, None, None, 94922,1),
   (0.21, 0.8, 150, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_ColmacCxA_10_C_MP', None, 'multipass_rtp', 891, 48, None, None, 90001,8),
   (0.21, 0.8, 140, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_C_SP', None, 'singlepass_rtp', 891, 48, None, None, 90254,6),
   (0.21, 0.8, 140, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_NyleC250A_C_SP', None, 'singlepass_norecirc', 891, 48, None, None, 91730,10),
   (0.21, 0.8, 145, 120, [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1], 'MODELS_SANCO2_C_SP', None, 'swingtank', 891, 48, 100, 19, 90255,8),
   (0.21, 0.8, 148, 122, [1,1,1,1,1,1,1,1,0,0,0,0,1,1,1,1,0,0,0,0,0,0,1,1], 'MODELS_ColmacCxA_15_C_SP', 'MODELS_ColmacCxA_20_C_MP', 'paralleltank', 891, 31, 91, 19, 91730,10),
])

def test_annual_simRun_comparison_values(aquaFractLoadUp, aquaFractShed, storageT_F, supplyT_F, loadShiftSchedule, hpwhModel, 
                                         tmModel, simSchematic, PVol_G_atStorageT, PCap_kW, TMVol_G, TMCap_kW, zipCode, climateZone):
    hpwh_ls = EcosizerEngine(
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
    