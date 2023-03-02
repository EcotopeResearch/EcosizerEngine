from abc import ABC, abstractmethod
from constants.Constants import *
from objects.Building import Building
# Functions to gather data from JSON
import os
import json
import numpy as np

class SystemConfig(ABC):
    def __init__(self, building):
        if(isinstance(building, Building)):
            self.building = building
        # else TODO error

    # @abstractmethod
    def simulate(self):
        pass

class ParallelLoopTank(SystemConfig):
    def __init__(self, building, safetyTM, setpointTM_F, TMonTemp_F, offTime_hr):
        super().__init__(building)
        self.setpointTM_F = setpointTM_F
        self.TMonTemp_F = TMonTemp_F
        self.offTime_hr = offTime_hr # Hour
        self.safetyTM = safetyTM # Safety factor

        self.TMVol_G  =  self.building.recirc_loss / rhoCp * self.offTime_hr / (self.setpointTM_F - self.TMonTemp_F)
        self.TMCap_kBTUhr = self.safetyTM * self.building.recirc_loss/1000

    def simulate(self):
        print(self.TMonTemp_F)
        print(self.TMVol_G)

