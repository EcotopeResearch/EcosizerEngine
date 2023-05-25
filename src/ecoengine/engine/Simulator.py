from ecoengine.objects.SystemConfig import SystemConfig
from ecoengine.objects.Building import Building
from ecoengine.objects.systemConfigUtils import *
from ecoengine.objects.SimulationRun import *

    
def simulate(system : SystemConfig, building : Building, initPV=None, initST=None, Pcapacity=None, Pvolume=None):
    """
    Implimented seperatly for Swink Tank systems 
    Inputs
    ------
    building : Building
        the building object the system configuration is being simulated for.
    initPV : float
        Primary volume at start of the simulation
    initST : float
        Primary Swing tank at start of the simulation. Not used in this instance of the function
    Pcapacity : float
        The primary heating capacity in kBTUhr to use for the simulation,
        default is the sized system
    Pvolume : float
        The primary storage volume in gallons to  to use for the simulation,
        default is the sized system
    
    Returns
    -------
    list [ pV, G_hw, D_hw, prun ]
    pV : list 
        Volume of HW in the tank with time at the strorage temperature.
    G_hw : list 
        The generation of HW with time at the supply temperature
    D_hw : list 
        The hot water demand with time at the tsupply temperature
    prun : list 
        The actual output in gallons of the HPWH with time
    """

    simRun = system.getInitializedSimulation(building, Pcapacity, Pvolume, initPV, initST)

    # Run the "simulation"
    for i in range(1, len(simRun.G_hw)):
        # change capacity based weather
        system.runOneSystemStep(simRun, i)

    return simRun
