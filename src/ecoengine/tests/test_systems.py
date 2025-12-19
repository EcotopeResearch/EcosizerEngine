import pytest
from ecoengine.engine.SystemCreator import createSystem
from ecoengine.engine.BuildingCreator import createBuilding
import os, sys
from ecoengine.constants.Constants import *
from ecoengine.engine.Simulator import simulate

class QuietPrint:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout

default_building = createBuilding(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            buildingType   = 'multi_family',
            nApt            = 100, 
            Wapt            = 100,
            gpdpp           = 25
        )

# Fixtures
@pytest.fixture
def simplePrimary():
    with QuietPrint():
        system = createSystem(
            schematic   = 'singlepass_norecirc', 
            building    = default_building, 
            storageT_F  = 150, 
            defrostFactor   = 1, 
            percentUseable  = .8, 
            compRuntime_hr  = 16, 
            onFract   = 0.4
        )
    return system

@pytest.fixture
def parallellTank(): 
    with QuietPrint():
        system = createSystem(
            schematic   = 'paralleltank', 
            building    = default_building, 
            storageT_F  = 150, 
            defrostFactor   = 1, 
            percentUseable  = .8, 
            compRuntime_hr  = 16, 
            onFract   = 0.4
        )
    return system

@pytest.fixture
def swingTank():
    with QuietPrint():
        system = createSystem(
            schematic   = 'swingtank', 
            building    = default_building, 
            storageT_F  = 150, 
            defrostFactor   = 1, 
            percentUseable  = .8, 
            compRuntime_hr  = 16, 
            onFract   = 0.4
        )
    return system

@pytest.fixture
def LSprimary():
    with QuietPrint():
       system = createSystem(
            schematic   = 'singlepass_norecirc', 
            building    = default_building, 
            storageT_F  = 150, 
            defrostFactor   = 1, 
            percentUseable  = .8, 
            compRuntime_hr  = 16, 
            onFract   = 0.4,
            onFractLoadUp = 0.25,
            onFractShed = 0.8,
            offLoadUpT = 150,
            loadShiftSchedule = [1,1,1,1,1,1,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
            doLoadShift = True,
            loadUpHours = 2
        )
    return system

@pytest.fixture
def sizedPrimary():
    with QuietPrint():
        system = createSystem(
            schematic   = 'singlepass_norecirc', 
            building    = default_building, 
            storageT_F  = 150, 
            defrostFactor   = 1, 
            percentUseable  = .8, 
            compRuntime_hr  = 16, 
            onFract   = 0.4,
            PVol_G_atStorageT = 500,
            PCap_kBTUhr = 95
        )
    return system

@pytest.fixture
def sizedSwing():
    with QuietPrint():
        system = createSystem(
            schematic   = 'swingtank', 
            storageT_F  = 150, 
            defrostFactor   = 1, 
            percentUseable  = .8, 
            compRuntime_hr  = 16, 
            onFract   = 0.4,
            onT = 120,
            PVol_G_atStorageT = 500,
            PCap_kBTUhr = 95,
            TMVol_G = 100,
            TMCap_kBTUhr = 60
        )
    return system

@pytest.fixture
def sizedParallel():
    with QuietPrint():
        system = createSystem(
            schematic   = 'paralleltank', 
            storageT_F  = 150, 
            defrostFactor   = 1, 
            percentUseable  = .8, 
            compRuntime_hr  = 16, 
            onFract   = 0.4,
            onT = 120,
            PVol_G_atStorageT = 500,
            PCap_kBTUhr = 95,
            TMVol_G = 100,
            TMCap_kBTUhr = 60
        )
    return system


###############################################################################
###############################################################################
# Unit Tests

def test_primaryResults(simplePrimary):
    simRun = simulate(simplePrimary, default_building, minuteIntervals = 1, nDays = 3, exceptOnWaterShortage=False)
    assert simRun.pV[-2] > 0
    # assert [simplePrimary.PVol_G_atStorageT, simplePrimary.PCap_kBTUhr, simplePrimary.loadShiftSchedule, simplePrimary.maxDayRun_hr] == [467.6418425, 91.3667890625, [1]*24, 16]

def test_parallelResults(parallellTank):
    simRun = simulate(parallellTank, default_building, minuteIntervals = 1, nDays = 3, exceptOnWaterShortage=False)
    assert simRun.pV[-2] > 0
    # assert [parallellTank.PVol_G_atStorageT, parallellTank.PCap_kBTUhr, 
    #         parallellTank.loadShiftSchedule, parallellTank.maxDayRun_hr,
    #         parallellTank.TMVol_G, parallellTank.TMCap_kBTUhr] == [467.6418425, 91.3667890625, [1]*24, 16, 90.67963730324946, 59.712485]
    
def test_swingResults(swingTank):
    simRun = simulate(swingTank, default_building, minuteIntervals = 1, nDays = 3, exceptOnWaterShortage=False)
    assert simRun.pV[-2] > 0
    # assert [swingTank.PVol_G_atStorageT, swingTank.PCap_kBTUhr, 
    #         swingTank.loadShiftSchedule, swingTank.maxDayRun_hr,
    #         swingTank.TMVol_G, swingTank.TMCap_kBTUhr] == [540.4258388420066, 118.11496284632376, [1]*24, 16, 100, 59.712485]

def test_LSprimary(LSprimary):
    simRun = simulate(LSprimary, default_building, minuteIntervals = 1, nDays = 3, exceptOnWaterShortage=False)
    assert simRun.pV[-2] > 0
    # assert [LSprimary.PVol_G_atStorageT, LSprimary.PCap_kBTUhr] == [841.0350199999998, 91.3667890625]

def test_sizedPrimaryResults(sizedPrimary):
    # simRun = simulate(sizedPrimary, default_building, minuteIntervals = 1, nDays = 3, exceptOnWaterShortage=False)
    # assert simRun.pV[-2] > 0
    assert [sizedPrimary.PVol_G_atStorageT, sizedPrimary.PCap_kBTUhr, sizedPrimary.loadShiftSchedule, sizedPrimary.maxDayRun_hr] == [500, 95, [1]*24, 16]

def test_sizedSwingResults(sizedSwing):
    # simRun = simulate(sizedSwing, default_building, minuteIntervals = 1, nDays = 3, exceptOnWaterShortage=False)
    # assert simRun.pV[-2] > 0
    assert [sizedSwing.PVol_G_atStorageT, sizedSwing.PCap_kBTUhr, 
            sizedSwing.loadShiftSchedule, sizedSwing.maxDayRun_hr,
            sizedSwing.TMVol_G, sizedSwing.TMCap_kBTUhr, sizedSwing.CA_TMVol_G] == [500, 95, [1]*24, 16, 100, 60, 168]
    
def test_sizedParallelResults(sizedParallel):
    # simRun = simulate(sizedParallel, default_building, minuteIntervals = 1, nDays = 3, exceptOnWaterShortage=False)
    # assert simRun.pV[-2] > 0
    assert [sizedParallel.PVol_G_atStorageT, sizedParallel.PCap_kBTUhr, 
            sizedParallel.loadShiftSchedule, sizedParallel.maxDayRun_hr,
            sizedParallel.TMVol_G, sizedParallel.TMCap_kBTUhr] == [500, 95, [1]*24, 16, 100, 60]

def test_change_capacity(sizedPrimary):
    sizedPrimary.setCapacity(PCap_kBTUhr=100)
    assert sizedPrimary.PCap_kBTUhr == 100
    sizedPrimary.setCapacity(PCap_kBTUhr=95)
    assert sizedPrimary.PCap_kBTUhr == 95

@pytest.mark.parametrize("minuteIntervals, nDays, outputArrayLength, initPV", [
   (1,3,4320, None), (60,365,8760, None), (15,365,35040, None),
   (1,3,4320, 80), (60,365,8760, 300), (15,365,35040, 14) 
])   
def test_initialize_sim(simplePrimary, minuteIntervals, nDays, outputArrayLength, initPV):
    initSim = simplePrimary.getInitializedSimulation(default_building, minuteIntervals=minuteIntervals, nDays=nDays, initPV=initPV)
    assert initSim.hwGenRate == 1000 * simplePrimary.PCap_kBTUhr / rhoCp / (default_building.supplyT_F - default_building.incomingT_F) \
               * simplePrimary.defrostFactor / (60/minuteIntervals)
    assert len(initSim.hwDemand) == outputArrayLength
    if initPV is None:
        assert initSim.pV[-1] == (1-simplePrimary.onFract)*simplePrimary.PVol_G_atStorageT
    else:
        assert initSim.pV[-1] == initPV
    assert len(initSim.pV) == outputArrayLength
    assert len(initSim.pGen) == outputArrayLength
    assert len(initSim.pRun) == outputArrayLength
    assert initSim.pheating == False
    assert len(initSim.oat) == 0
    assert len(initSim.cap_out) == 0
    assert len(initSim.cap_in) == 0
    assert len(initSim.kGCO2) == 0

@pytest.mark.parametrize("minuteIntervals, nDays, outputArrayLength, initPV", [
   (1,3,4320, None), (60,365,8760, None), (15,365,35040, None),
   (1,3,4320, 80), (60,365,8760, 300), (15,365,35040, 14) 
])   
def test_initialize_sim_swing(swingTank, minuteIntervals, nDays, outputArrayLength, initPV):
    initSim = swingTank.getInitializedSimulation(default_building, minuteIntervals=minuteIntervals, nDays=nDays, initPV=initPV)
    assert initSim.hwGenRate == 1000 * swingTank.PCap_kBTUhr / rhoCp / (default_building.supplyT_F - default_building.incomingT_F) \
               * swingTank.defrostFactor / (60/minuteIntervals)
    assert len(initSim.hwDemand) == outputArrayLength
    if initPV is None:
        assert initSim.pV[-1] == (1-swingTank.onFract)*swingTank.PVol_G_atStorageT
    else:
        assert initSim.pV[-1] == initPV
    assert len(initSim.pV) == outputArrayLength
    assert len(initSim.pGen) == outputArrayLength
    assert len(initSim.pRun) == outputArrayLength
    assert initSim.pheating == False
    assert len(initSim.oat) == 0
    assert len(initSim.cap_out) == 0
    assert len(initSim.cap_in) == 0
    assert len(initSim.kGCO2) == 0
    assert len(initSim.tmT_F) == outputArrayLength
    assert len(initSim.tmRun) == outputArrayLength
    assert len(initSim.hw_outSwing) == outputArrayLength
    assert initSim.TM_setpoint == default_building.supplyT_F
    assert initSim.TMCap_kBTUhr == swingTank.TMCap_kBTUhr

# Check for system initialization errors
def test_invalid_building():
    with pytest.raises(Exception, match="Error: Building is not valid."):
        createSystem("swingtank", 150, 1, 0.8, 16, 0.4, building = 5)

def test_invalid_storage_temp():
    with pytest.raises(Exception, match="Invalid input given for Storage temp, it must be between 32 and 212F."):
        createSystem("swingtank", 15, 1, 0.8, 16, 0.4, building = default_building)

def test_invalid_schematic():
    with pytest.raises(Exception, match="Unknown system schematic type."):
        createSystem("fakesystem", 150, 1, 0.8, 16, 0.4, building = default_building)

def test_invalid_defrost():
    with pytest.raises(Exception, match="Invalid input given for Defrost Factor, must be a number between 0 and 1."):
        createSystem("swingtank", 150, 3, 0.8, 16, 0.4, building = default_building)

def test_invalid_percent_usable():
    with pytest.raises(Exception, match="Invalid input given for percentUseable, must be a number between 0 and 1."):
        createSystem("swingtank", 150, 1, 1.8, 16, 0.4, building = default_building)
    with pytest.raises(Exception, match="Invalid input given for percentUseable, must be a number between 0 and 1."):
        createSystem("swingtank", 150, 1, 'zebrah', 16, 0.4, building = default_building)

def test_invalid_compRuntime_hr():
    with pytest.raises(Exception, match="Invalid input given for compRuntime_hr, must be a number between 0 and 24."):
        createSystem("swingtank", 150, 1, 0.8, '16', 0.4, building = default_building)
    with pytest.raises(Exception, match="Invalid input given for compRuntime_hr, must be a number between 0 and 24."):
        createSystem("swingtank", 150, 1, 0.8, 25, 0.4, building = default_building)

def test_invalid_aquaFrac():
    with pytest.raises(Exception, match="Invalid input given for onFract must, be a number between 0 and 1."):
        createSystem("swingtank", 150, 1, 0.8, 16, 0., building = default_building)

def test_invalid_loadShiftPercent():
    with pytest.raises(Exception, match="Invalid input given for loadShiftPercent, must be a number between 0 and 1."):
        createSystem("swingtank", 150, 1, 0.8, 16, 0.4, building = default_building, loadShiftPercent = 'eighteen', doLoadShift= True)
    with pytest.raises(Exception, match="Invalid input given for loadShiftPercent, must be a number between 0 and 1."):
        createSystem("swingtank", 150, 1, 0.8, 16, 0.4, building = default_building, loadShiftPercent = -1., doLoadShift= True)
    with pytest.raises(Exception, match="Invalid input given for loadShiftPercent, must be a number between 0 and 1."):
        createSystem("swingtank", 150, 1, 0.8, 16, 0.4, building = default_building, loadShiftPercent = 1.1, doLoadShift= True)

def test_invalid_doLoadShift():
    with pytest.raises(Exception, match="Invalid input given for doLoadShift, must be a boolean."):
        createSystem("swingtank", 150, 1, 0.8, 16, 0.4, building = default_building, doLoadShift = 'eighteen')

def test_invalid_safteyTM():
    with pytest.raises(Exception, match="The saftey factor for the temperature maintenance system must be greater than 1 or the system will never keep up with the losses."):
        createSystem("swingtank", 150, 1, 0.8, 16, 0.4, building = default_building, safetyTM = 0.2)
    with pytest.raises(Exception, match="The saftey factor for the temperature maintenance system must be greater than 1 or the system will never keep up with the losses."):
        createSystem("paralleltank", 150, 1, 0.8, 16, 0.4, building = default_building, safetyTM = 0.2)

def test_invalid_offTime_hr():
    with pytest.raises(Exception, match="The One Cycle Off Time the temperature maintenance system must be a float bigger than zero and less than or equal to one hour."):
        createSystem("paralleltank", 150, 1, 0.8, 16, 0.4, building = default_building, offTime_hr = 0.)
    with pytest.raises(Exception, match="The expected run time of the parallel tank is less time the minimum runtime for a HPWH of " + str(tmCompMinimumRunTime*60)+ " minutes."):
        createSystem("paralleltank", 150, 1, 0.8, 16, 0.4, building = default_building, offTime_hr = 0.1, safetyTM = 5)

def test_invalid_setpoints():
    with pytest.raises(Exception, match="Invalid input given for setpointTM_F, it must be between 32 and 212F."):
        createSystem("paralleltank", 150, 1, 0.8, 16, 0.4, building = default_building, setpointTM_F = 5)
    with pytest.raises(Exception, match="Invalid input given for setpointTM_F, it must be between 32 and 212F."):
        createSystem("paralleltank", 150, 1, 0.8, 16, 0.4, building = default_building, setpointTM_F = 213)
    with pytest.raises(Exception, match="Invalid input given for TMonTemp_F, it must be between 32 and 212F."):
        createSystem("paralleltank", 150, 1, 0.8, 16, 0.4, building = default_building, TMonTemp_F = 5)
    with pytest.raises(Exception, match="Invalid input given for TMonTemp_F, it must be between 32 and 212F."):
        createSystem("paralleltank", 150, 1, 0.8, 16, 0.4, building = default_building, TMonTemp_F = 213)
    with pytest.raises(Exception, match="The temperature maintenance setpoint temperature must be greater than the turn on temperature"):
        createSystem("paralleltank", 150, 1, 0.8, 16, 0.4, building = default_building, TMonTemp_F = 135, setpointTM_F = 135)
    with pytest.raises(Exception, match="The temperature maintenance setpoint temperature must be greater than the city cold water temperature"):
        createSystem("paralleltank", 150, 1, 0.8, 16, 0.4, building = default_building, setpointTM_F = 34, TMonTemp_F = 33)
    with pytest.raises(Exception, match="The temperature maintenance on temperature must be greater than the city cold water temperature"):
        createSystem("paralleltank", 150, 1, 0.8, 16, 0.4, building = default_building, TMonTemp_F = 34)

def test_invalid_ls_schedule():
    with pytest.raises(Exception, match="Load shift is not of length 24 but instead has length of 0."):
        createSystem('singlepass_norecirc', 150, 1, .8, 16, 0.4, building = default_building, doLoadShift = True, loadShiftPercent = 1, loadShiftSchedule = [])
    with pytest.raises(Exception, match="Load shift is not of length 24 but instead has length of 25."):
        createSystem('singlepass_norecirc', 150, 1, .8, 16, 0.4, building = default_building, doLoadShift = True, loadShiftPercent = 1, loadShiftSchedule = [0]*25)
    with pytest.raises(Exception, match="When using Load shift the HPWH's must run for at least 1 hour each day."):
        createSystem('singlepass_norecirc', 150, 1, .8, 16, 0.4, building = default_building, doLoadShift = True, loadShiftPercent = 1, loadShiftSchedule = [0]*24)
    with pytest.raises(Exception, match="Load shift only available for above 25 percent of days."):
        createSystem('singlepass_norecirc', 150, 1, .8, 16, 0.4, building = default_building, doLoadShift = True, loadShiftPercent = 0.23, loadShiftSchedule = [1]*24)

def test_invalid_loadshift_vars():
    with pytest.raises(Exception, match = "Invalid input given for load up ON fraction, must be a number between 0 and normal ON fraction."):
        createSystem('singlepass_norecirc', 150, 1, .8, 16, 0.4, building = default_building, doLoadShift = True, onFractLoadUp = 0.5, onFractShed = 0.8,
                     loadShiftSchedule = [1]*24, outletLoadUpT = 160, loadUpHours = 0)
    with pytest.raises(Exception, match = "Invalid input given for shed ON fraction, must be a number between normal ON fraction and 1."):
        createSystem('singlepass_norecirc', 150, 1, .8, 16, 0.5, building = default_building, doLoadShift = True, onFractLoadUp = 0.3, onFractShed = 0.4,
                     loadShiftSchedule = [1]*24, outletLoadUpT = 160, loadUpHours = 0)
    with pytest.raises(Exception, match = "Invalid input given for load up storage temp, it must be a number between normal storage temp and 212F."):
        createSystem('singlepass_norecirc', 150, 1, .8, 16, 0.4, building = default_building, doLoadShift = True, onFractLoadUp = 0.3, onFractShed = 0.8,
                     loadShiftSchedule = [1]*24, outletLoadUpT = 140, loadUpHours = 0)
    with pytest.raises(Exception, match = "Invalid input given for load up hours, must be an integer less than or equal to hours in day before first shed period."):
        createSystem('singlepass_norecirc', 150, 1, .8, 16, 0.4, building = default_building, doLoadShift = True, onFractLoadUp = 0.3, onFractShed = 0.8,
                     loadShiftSchedule = [1,0,1,1,1,1,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1], offLoadUpT = 160, loadUpHours = 2)

def test_invalid_sizing():
    with pytest.raises(Exception, match = "Invalid input given for Primary Storage Volume, it must be a number greater than zero."):
        createSystem('singlepass_norecirc', 150, 1, .8, 16, 0.4, building = default_building, PVol_G_atStorageT = 'lol', PCap_kBTUhr = 95)
    with pytest.raises(Exception, match = "Invalid input given for Primary Storage Volume, it must be a number greater than zero."):
        createSystem('singlepass_norecirc', 150, 1, .8, 16, 0.4, building = default_building, PVol_G_atStorageT = 0, PCap_kBTUhr = 95)
    with pytest.raises(Exception, match = "Invalid input given for Primary Storage Volume, it must be a number greater than zero."):
        createSystem('paralleltank', 150, 1, .8, 16, 0.4, building = default_building, PVol_G_atStorageT = 0, PCap_kBTUhr = 95, TMVol_G=12,TMCap_kBTUhr=15)
    with pytest.raises(Exception, match = "Invalid input given for Primary Storage Volume, it must be a number greater than zero."):
        createSystem('swingtank', 150, 1, .8, 16, 0.4, building = default_building, PVol_G_atStorageT = 0, PCap_kBTUhr = 95, TMVol_G=12,TMCap_kBTUhr=15)
    with pytest.raises(Exception, match = "Invalid input given for Primary Output Capacity, must be a number greater than zero."):
        createSystem('swingtank', 150, 1, .8, 16, 0.4, building = default_building, PVol_G_atStorageT = 10, PCap_kBTUhr = 0, TMVol_G=12,TMCap_kBTUhr=15)
    with pytest.raises(Exception, match = "Invalid input given for Temperature Maintenance Storage Volume, it must be a number greater than zero."):
        createSystem('swingtank', 150, 1, .8, 16, 0.4, building = default_building, PVol_G_atStorageT = 10, PCap_kBTUhr = 20, TMVol_G=0,TMCap_kBTUhr=15)
    with pytest.raises(Exception, match = "Invalid input given for Temperature Maintenance Output Capacity, it must be a number greater than zero."):
        createSystem('swingtank', 150, 1, .8, 16, 0.4, building = default_building, PVol_G_atStorageT = 10, PCap_kBTUhr = 20, TMVol_G=10,TMCap_kBTUhr='lol')
    with pytest.raises(Exception, match = "Invalid input given for Temperature Maintenance Storage Volume, it must be a number greater than zero."):
        createSystem('paralleltank', 150, 1, .8, 16, 0.4, building = default_building, PVol_G_atStorageT = 10, PCap_kBTUhr = 20, TMVol_G=0,TMCap_kBTUhr=15)
    with pytest.raises(Exception, match = "Invalid input given for Temperature Maintenance Output Capacity, it must be a number greater than zero."):
        createSystem('paralleltank', 150, 1, .8, 16, 0.4, building = default_building, PVol_G_atStorageT = 10, PCap_kBTUhr = 20, TMVol_G=10,TMCap_kBTUhr='lol')

def test_invalid_prefomance_map():
    with pytest.raises(Exception, match = "Invalid input given for Primary Output Capacity, must be a number greater than zero."):
        createSystem('paralleltank', 150, 1, .8, 16, 0.4, building = default_building, PVol_G_atStorageT = 10, TMVol_G=10, TMCap_kBTUhr=10)
    with pytest.raises(Exception, match = "Invalid input given for numHeatPumps, must be a number greater than zero"):
        createSystem('paralleltank', 150, 1, .8, 16, 0.4, building = default_building, PVol_G_atStorageT = 10, TMVol_G=10, TMCap_kBTUhr=10, systemModel = 'model', numHeatPumps = -3)
    with pytest.raises(Exception, match = "Invalid input given for Primary Output Capacity, must be a number greater than zero."):
        createSystem('paralleltank', 150, 1, .8, 16, 0.4, building = default_building, PVol_G_atStorageT = 10, TMVol_G=10, TMCap_kBTUhr=10, systemModel = 'model')
    with pytest.raises(Exception, match = "No preformance map found for HPWH model type model."):
        createSystem('paralleltank', 150, 1, .8, 16, 0.4, building = default_building, PVol_G_atStorageT = 10, TMVol_G=10, TMCap_kBTUhr=10, systemModel = 'model', numHeatPumps = 4.0)

def test_sp_rtp_sizing():
    check_building = createBuilding(
            incomingT_F     = 50,
            magnitudeStat  = 100,
            supplyT_F       = 120,
            buildingType   = 'multi_family',
            nApt            = 100, 
            returnT_F       = 105,
            flowRate        = 6,
            gpdpp           = 25
        )
    nortp_system = createSystem(
        schematic   = 'singlepass_norecirc', 
        building    = check_building, 
        storageT_F  = 150, 
        defrostFactor   = 1, 
        percentUseable  = .8, 
        compRuntime_hr  = 16, 
        onFract   = 0.4,
    )
    rtp_system = createSystem(
        schematic   = 'sprtp', 
        building    = check_building, 
        storageT_F  = 150, 
        defrostFactor   = 1, 
        percentUseable  = .8, 
        compRuntime_hr  = 16, 
        onFract   = 0.4,
    )
    
    # assert rtp_system.PVol_G_atStorageT > nortp_system.PVol_G_atStorageT
    assert rtp_system.PCap_kBTUhr > nortp_system.PCap_kBTUhr
    rtp_size_results = rtp_system.getSizingResults()
    assert len(rtp_size_results) == 3
    assert rtp_size_results[1] > rtp_size_results[2]
    for i in range(24):
        assert check_building.loadshape[i] == default_building.loadshape[i]
    assert check_building.magnitude == default_building.magnitude
