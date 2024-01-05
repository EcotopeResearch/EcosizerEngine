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

@pytest.mark.parametrize("hpwhModel, pretty_name", [*getListOfModels(multiPass = False), *getListOfModels(multiPass = True)])
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