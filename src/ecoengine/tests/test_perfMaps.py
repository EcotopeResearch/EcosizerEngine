import pytest
from ecoengine.objects.PrefMapTracker import *
from ecoengine.engine.EcosizerEngine import getListOfModels
from ecoengine.constants.Constants import *
import os, sys

class QuietPrint:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout

@pytest.mark.parametrize("hpwhModel, pretty_name", [*getListOfModels(multiPass = False,sgipModelsOnly=False), 
                                                    *getListOfModels(multiPass = True,sgipModelsOnly=False)])
def test_perfMaps(hpwhModel, pretty_name):
    assert isinstance(pretty_name, str)
    perfMap = PrefMapTracker(None, hpwhModel, False, 1, usePkl= False, prefMapOnly = True)
    if perfMap.usePkl == False:
        #test systems with out pkls, then set them to use pkls
        results = perfMap.getCapacity(65, 70, 120)
        assert len(results) == 2
        assert isinstance(results[0], float)
        assert results[0] > 0.0
        assert isinstance(results[1], float)
        assert results[1] > 0.0
        perfMap = PrefMapTracker(None, hpwhModel, False, 1, usePkl= True, prefMapOnly = True)

    results = perfMap.getCapacity(65, 70, 120)
    assert len(results) == 2
    assert isinstance(results[0], float)
    assert results[0] > 0.0
    assert isinstance(results[1], float)
    assert results[1] > 0.0
    # very hot
    hot_results = perfMap.getCapacity(101, 80, 120)
    assert len(hot_results) == 2
    assert isinstance(hot_results[0], float)
    assert isinstance(hot_results[1], float)
    # very cold
    cold_results = perfMap.getCapacity(-1, 34, 120)
    assert len(cold_results) == 2
    assert isinstance(cold_results[0], float)
    assert isinstance(cold_results[1], float)
    if perfMap.usePkl:
        # no guarantees for HPWHsim models, but guarantees for lab data
        assert hot_results[0] > 0.0
        assert hot_results[1] > 0.0
        assert cold_results[0] > 0.0
        assert cold_results[1] > 0.0

@pytest.mark.parametrize("hpwhModel, hxTempIncrease, expectedHXTempIncrease", 
                         [
                            ("MODELS_LYNC_AEGIS_500_C_SP", 15, 15),
                            ("MODELS_LYNC_AEGIS_500_C_SP", None, 10),
                            ("MODELS_Mitsubishi_QAHV_C_SP", 5, 5),
                            ("MODELS_Mitsubishi_QAHV_C_SP", None, 10),
                            ("MODELS_Laars_eTherm_C_SP", 15, 15),
                            ("MODELS_Laars_eTherm_C_SP", None, None)
                        ])
def test_perfMaps_hxTempIncrease(hpwhModel, hxTempIncrease, expectedHXTempIncrease):
    perfMap = PrefMapTracker(None, hpwhModel, False, 1, prefMapOnly = True, hxTempIncrease = hxTempIncrease)
    assert perfMap.hxTempIncrease == expectedHXTempIncrease

@pytest.mark.parametrize("hpwhModel, expectedNumHP, expectedCap, expectedPower, oat, inlet, outlet", 
                         [
                            ("MODELS_Mitsubishi_QAHV_C_SP", 3, 40.0, 10.3, 61.0, 53.0, 139.0),
                            ("MODELS_NyleC125A_C_SP", 5, 34.18, 13.54, 60.0, 75.0, 140.0),
                            ("MODELS_ColmacCxA_20_C_SP", 35, 53.3, 18.8, 58.0, 40.0, 120.0),
                        ])
def test_perfMaps_autosize_and_kW_to_kBTU(hpwhModel, expectedNumHP, expectedCap, expectedPower, oat, inlet, outlet):
    perfMap = PrefMapTracker(expectedCap * expectedNumHP * W_TO_BTUHR, hpwhModel, False)
    results = perfMap.getCapacity(oat, inlet, outlet)
    assert results[0] == expectedCap * expectedNumHP
    assert results[1] == expectedPower * expectedNumHP
    assert perfMap.numHeatPumps == expectedNumHP

    perfMap_kBTU = PrefMapTracker(expectedCap * expectedNumHP * W_TO_BTUHR, hpwhModel, True)
    results_kBTU = perfMap_kBTU.getCapacity(oat, inlet, outlet)
    assert round(results_kBTU[0], 4) == round(expectedCap * expectedNumHP * W_TO_BTUHR, 4) 
    assert round(results_kBTU[1], 4) == round(expectedPower * expectedNumHP * W_TO_BTUHR, 4)
    assert perfMap.numHeatPumps == expectedNumHP

@pytest.mark.parametrize("hpwhModel, expectedCap, expectedPower, oat, inlet, outlet", 
                         [
                            ("MODELS_Mitsubishi_QAHV_C_SP", 6, 4, 103.8, 90.0, 150.0), # this one tests the default return with a COP of 1.5
                            ("MODELS_Mitsubishi_QAHV_C_SP", 40, 12.7, 105.8, 90.0, 150.0), # this one tests the default return when OAT is larger than max OAT
                            ("MODELS_Mitsubishi_QAHV_C_SP", 6, 6, -80, 90.0, 150.0), # this one tests the default return when OAT is smaller than min OAT
                            (None, 15, 6, -80, 90.0, 150.0), # this one tests the default with no perf map
                        ])
def test_perfMaps_outside_perf_map_and_kW_to_kBTU(hpwhModel, expectedCap, expectedPower, oat, inlet, outlet):
    perfMap = PrefMapTracker(expectedCap * W_TO_BTUHR, hpwhModel, False)
    results = perfMap.getCapacity(oat, inlet, outlet)
    assert round(results[0], 4) == round(expectedCap, 4)
    assert round(results[1], 4) == round(expectedPower, 4)

    perfMap_kBTU = PrefMapTracker(expectedCap * W_TO_BTUHR, hpwhModel, True)
    results_kBTU = perfMap_kBTU.getCapacity(oat, inlet, outlet)
    assert round(results_kBTU[0], 4) == round(expectedCap  * W_TO_BTUHR, 4) 
    assert round(results_kBTU[1], 4) == round(expectedPower * W_TO_BTUHR, 4)

@pytest.mark.parametrize("hpwhModel, expectedCap, expectedPower, oat, inlet, outlet, fallbackCapacity", 
                         [
                            ("MODELS_Mitsubishi_QAHV_C_SP", 12, 8, 103.8, 90.0, 150.0, 12), # this one tests the default return with a COP of 1.5
                            ("MODELS_Mitsubishi_QAHV_C_SP", 40, 12.7, 105.8, 90.0, 150.0, 12), # this one tests the default return when OAT is larger than max OAT
                            ("MODELS_Mitsubishi_QAHV_C_SP", 15, 15, -80, 90.0, 150.0, 15), # this one tests the default return when OAT is smaller than min OAT
                            (None, 250, 100, -80, 90.0, 150.0, 250), # this one tests the default with no perf map
                        ])
def test_perfMaps_fallback_and_kW_to_kBTU(hpwhModel, expectedCap, expectedPower, oat, inlet, outlet, fallbackCapacity):
    perfMap = PrefMapTracker(10, hpwhModel, False)
    results = perfMap.getCapacity(oat, inlet, outlet, fallbackCapacity_kW = fallbackCapacity)
    assert round(results[0], 4) == round(expectedCap, 4)
    assert round(results[1], 4) == round(expectedPower, 4)

    perfMap_kBTU = PrefMapTracker(10, hpwhModel, True)
    results_kBTU = perfMap_kBTU.getCapacity(oat, inlet, outlet, fallbackCapacity_kW = fallbackCapacity)
    assert round(results_kBTU[0], 4) == round(expectedCap  * W_TO_BTUHR, 4) 
    assert round(results_kBTU[1], 4) == round(expectedPower * W_TO_BTUHR, 4)

def test_getListOfModels():
    assert len(getListOfModels(multiPass = False,sgipModelsOnly=False)) > len(getListOfModels(multiPass = False,sgipModelsOnly=True))
    assert len(getListOfModels(multiPass = True,sgipModelsOnly=False)) > len(getListOfModels(multiPass = True,sgipModelsOnly=True))
    assert len(getListOfModels(multiPass = True,excludeModels=["MODELS_ColmacCxV_15_VFD_45_Hz_C_MP"])) == len(getListOfModels(multiPass = True))
    assert len(getListOfModels(multiPass = False,excludeModels=["MODELS_LYNC_AEGIS_500_C_SP"])) < len(getListOfModels(multiPass = False))