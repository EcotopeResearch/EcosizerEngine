import pytest
from ecoengine.objects.PrefMapTracker import *
from ecoengine.engine.EcosizerEngine import getListOfModels
from ecoengine.engine.BuildingCreator import createBuilding
from ecoengine.constants.Constants import *
import os, sys

class QuietPrint:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout

climate_params = []
for climateZone in range (1,17):
    building = createBuilding(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            buildingType   = "multi_family",
            flowRate       = 5,
            returnT_F       = 100,
            climateZone    = climateZone
    )
    for i in range(12):
        climate_params.append([climateZone, building.getLowestOAT(month=i), building.getHighestOAT(month=i), building.getIncomingWaterT(0,0,month=i)])


all_models_and_climates = []
for model_specs in getListOfModels(multiPass = False,sgipModelsOnly=False) + getListOfModels(multiPass = True,sgipModelsOnly=False):
    hpwhModel = model_specs[0]
    for climate_param in climate_params:
       all_models_and_climates.append([hpwhModel]+climate_param) 

@pytest.mark.parametrize("hpwhModel, climateZone, lowest_oat, highest_oat, incomingT_F", [*all_models_and_climates])
def test_perfMaps_for_all_climates(hpwhModel, climateZone, lowest_oat, highest_oat, incomingT_F):
    assert climateZone < 17

    perfMap = PrefMapTracker(None, hpwhModel, False, 1, usePkl= False, prefMapOnly = True)
    

    if perfMap.usePkl == False:
        #test systems with out pkls, then set them to use pkls
        results = perfMap.getCapacity(lowest_oat, incomingT_F, 150)
        assert len(results) == 2
        assert isinstance(results[0], float)
        assert results[0] > 0.0
        assert isinstance(results[1], float)
        assert results[1] > 0.0

        results = perfMap.getCapacity(highest_oat, incomingT_F, 150)
        assert len(results) == 2
        assert isinstance(results[0], float)
        assert results[0] > 0.0
        assert isinstance(results[1], float)
        assert results[1] > 0.0

        perfMap = PrefMapTracker(None, hpwhModel, False, 1, usePkl= True, prefMapOnly = True)

    if perfMap.usePkl:
        results = perfMap.getCapacity(lowest_oat, incomingT_F, 150)
        assert len(results) == 2
        assert isinstance(results[0], float)
        assert results[0] > 0.0
        assert isinstance(results[1], float)
        assert results[1] > 0.0

        results = perfMap.getCapacity(highest_oat, incomingT_F, 150)
        assert len(results) == 2
        assert isinstance(results[0], float)
        assert results[0] > 0.0
        assert isinstance(results[1], float)
        assert results[1] > 0.0
