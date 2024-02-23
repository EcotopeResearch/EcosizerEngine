import pytest
from ecoengine.constants.Constants import *
from ecoengine.objects.UtilityCostTracker import *
import os, sys

class QuietPrint:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout

@pytest.mark.parametrize("monthly_base_charge, pk_start_hour, pk_end_hour, pk_demand_charge, pk_energy_charge, off_pk_demand_charge, off_pk_energy_charge", 
                         [(190.00, 16, 21, 38.75, 0.21585, 30.20, 0.14341),
                          (190.00, 0, 24, 38.75, 0.21585, 30.20, 0.14341),
                          (190.00, 21, 21, 38.75, 0.21585, 30.20, 0.14341),
                          (1.00, 20, 21, 0.75, 4.5, 3.20, 0.1)])
def test_uc_from_standard(monthly_base_charge, pk_start_hour, pk_end_hour, pk_demand_charge, pk_energy_charge, off_pk_demand_charge, off_pk_energy_charge):
    uc = UtilityCostTracker(monthly_base_charge, pk_start_hour, pk_end_hour, pk_demand_charge, pk_energy_charge, off_pk_demand_charge, off_pk_energy_charge)
    assert uc.getYearlyBaseCharge() == monthly_base_charge * 12
    next_pk_hr = pk_start_hour + 24
    next_off_pk = pk_end_hour + 24
    expected_start_energy = pk_energy_charge
    expected_end_energy = off_pk_energy_charge
    if pk_start_hour == pk_end_hour:
        # should never have pk_energy_charge
        expected_start_energy = off_pk_energy_charge
    elif pk_start_hour == 0 and pk_end_hour == 24:
        # should never have off_pk_energy_charge
        expected_end_energy = pk_energy_charge
    assert uc.getEnergyChargeAtInterval(pk_start_hour, 60) == expected_start_energy
    assert uc.getEnergyChargeAtInterval(pk_start_hour * 4, 15) == expected_start_energy
    assert uc.getEnergyChargeAtInterval(pk_start_hour * 60, 1) == expected_start_energy
    assert uc.getEnergyChargeAtInterval(next_pk_hr, 60) == expected_start_energy
    assert uc.getEnergyChargeAtInterval(next_pk_hr * 4, 15) == expected_start_energy
    assert uc.getEnergyChargeAtInterval(next_pk_hr * 60, 1) == expected_start_energy

    assert uc.getEnergyChargeAtInterval(pk_start_hour - 1, 60) == expected_end_energy
    assert uc.getEnergyChargeAtInterval((pk_start_hour * 4) - 1, 15) == expected_end_energy
    assert uc.getEnergyChargeAtInterval((pk_start_hour * 60) - 1, 1) == expected_end_energy
    assert uc.getEnergyChargeAtInterval(next_pk_hr - 1, 60) == expected_end_energy
    assert uc.getEnergyChargeAtInterval((next_pk_hr * 4) - 1, 15) == expected_end_energy
    assert uc.getEnergyChargeAtInterval((next_pk_hr * 60) - 1, 1) == expected_end_energy

    assert uc.getEnergyChargeAtInterval(pk_end_hour, 60) == expected_end_energy
    assert uc.getEnergyChargeAtInterval(pk_end_hour * 4, 15) == expected_end_energy
    assert uc.getEnergyChargeAtInterval(pk_end_hour * 60, 1) == expected_end_energy
    assert uc.getEnergyChargeAtInterval(next_off_pk, 60) == expected_end_energy
    assert uc.getEnergyChargeAtInterval(next_off_pk * 4, 15) == expected_end_energy
    assert uc.getEnergyChargeAtInterval(next_off_pk * 60, 1) == expected_end_energy

    assert uc.getEnergyChargeAtInterval(pk_end_hour - 1, 60) == expected_start_energy
    assert uc.getEnergyChargeAtInterval((pk_end_hour * 4) - 1, 15) == expected_start_energy
    assert uc.getEnergyChargeAtInterval((pk_end_hour * 60) - 1, 1) == expected_start_energy
    assert uc.getEnergyChargeAtInterval(next_off_pk - 1, 60) == expected_start_energy
    assert uc.getEnergyChargeAtInterval((next_off_pk * 4) - 1, 15) == expected_start_energy
    assert uc.getEnergyChargeAtInterval((next_off_pk * 60) - 1, 1) == expected_start_energy


