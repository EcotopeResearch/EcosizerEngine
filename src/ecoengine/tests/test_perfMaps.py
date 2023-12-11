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
    # No pkl
    perfMap = PrefMapTracker(None, hpwhModel, False, 1, usePkl= False, prefMapOnly = True)
    results = perfMap.getCapacity(65, 70, 120)
    assert len(results) == 2
    assert isinstance(results[0], float)
    assert isinstance(results[1], float)
    # with pkl
    perfMap = PrefMapTracker(None, hpwhModel, False, 1, usePkl= True, prefMapOnly = True)
    results = perfMap.getCapacity(65, 70, 120)
    assert len(results) == 2
    assert isinstance(results[0], float)
    assert isinstance(results[1], float)
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