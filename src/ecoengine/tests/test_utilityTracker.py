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
    
@pytest.mark.parametrize("monthly_base_charge, pk_start_hour, pk_end_hour, pk_demand_charge, pk_energy_charge, off_pk_demand_charge, off_pk_energy_charge, start_month, end_month",
                         [(5.00, [16,23], [21,24], [38.75,38.77], [0.21585,0.5], [30.20,35.0], [0.14341,0.07],[0,5],[5,12]),
                          (5.00, [16,23,13], [21,24,14], [38.75,38.77,39], [0.21585,0.5,0.4], [30.20,35.0,40], [0.14341,0.07,0.8],[0,5,7],[5,7,12]),
                          (5.00, [16], [21], [38.75], [0.21585], [30.20], [0.1434],[0],[12])])
def test_uc_from_standard_list(monthly_base_charge, pk_start_hour, pk_end_hour, pk_demand_charge, pk_energy_charge, off_pk_demand_charge, off_pk_energy_charge, start_month, end_month):
    uc = UtilityCostTracker(monthly_base_charge, pk_start_hour, pk_end_hour, pk_demand_charge, pk_energy_charge, off_pk_demand_charge, off_pk_energy_charge, start_month, end_month)
    assert uc.getYearlyBaseCharge() == monthly_base_charge * 12
    assert len(uc.getAllDemandPeriodKeys()) == 24
    assert uc.getEnergyChargeAtInterval(pk_start_hour[0], 60) == pk_energy_charge[0]
    assert uc.getEnergyChargeAtInterval(pk_end_hour[0], 60) == off_pk_energy_charge[0]
    assert uc.getEnergyChargeAtInterval(8760 - 48 + pk_start_hour[-1], 60) == pk_energy_charge[-1]
    assert uc.getEnergyChargeAtInterval(8760 - 48 + pk_end_hour[-1], 60) == off_pk_energy_charge[-1]

def test_invalid_monthly_base_charge_none():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(None, 16, 21, 38.75, 0.21585, 30.20, 0.14341)
    assert "Error: monthly base charge must be a number" in str(excinfo.value)

def test_invalid_monthly_base_charge_string():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker("invalid", 16, 21, 38.75, 0.21585, 30.20, 0.14341)
    assert "Error: monthly base charge must be a number" in str(excinfo.value)

def test_invalid_monthly_base_charge_list():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker([190.0], 16, 21, 38.75, 0.21585, 30.20, 0.14341)
    assert "Error: monthly base charge must be a number" in str(excinfo.value)

def test_mismatched_list_lengths():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, [16, 17], [21], [38.75], [0.21585], [30.20], [0.14341])
    assert "must all be the same length" in str(excinfo.value)

def test_mismatched_list_lengths_with_months():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, [16], [21], [38.75], [0.21585], [30.20], [0.14341], [0, 6], [6, 12])
    assert "must all be the same length" in str(excinfo.value)

def test_invalid_pk_start_hour_none():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, None, 21, 38.75, 0.21585, 30.20, 0.14341)
    assert "Error: peak start hour must be a number between 0 and 23" in str(excinfo.value)

def test_invalid_pk_start_hour_string():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, "invalid", 21, 38.75, 0.21585, 30.20, 0.14341)
    assert "Error: peak start hour must be a number between 0 and 23" in str(excinfo.value)

def test_invalid_pk_start_hour_negative():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, -1, 21, 38.75, 0.21585, 30.20, 0.14341)
    assert "Error: peak start hour must be a number between 0 and 23" in str(excinfo.value)

def test_invalid_pk_start_hour_too_large():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 24, 24, 38.75, 0.21585, 30.20, 0.14341)
    assert "Error: peak start hour must be a number between 0 and 23" in str(excinfo.value)

def test_invalid_pk_end_hour_none():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 16, None, 38.75, 0.21585, 30.20, 0.14341)
    assert "Error: peak end hour must be a number between peak start hour and 24" in str(excinfo.value)

def test_invalid_pk_end_hour_string():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 16, "invalid", 38.75, 0.21585, 30.20, 0.14341)
    assert "Error: peak end hour must be a number between peak start hour and 24" in str(excinfo.value)

def test_invalid_pk_end_hour_less_than_start():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 16, 15, 38.75, 0.21585, 30.20, 0.14341)
    assert "Error: peak end hour must be a number between peak start hour and 24" in str(excinfo.value)

def test_invalid_pk_end_hour_too_large():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 16, 25, 38.75, 0.21585, 30.20, 0.14341)
    assert "Error: peak end hour must be a number between peak start hour and 24" in str(excinfo.value)

def test_invalid_pk_demand_charge_none():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 16, 21, None, 0.21585, 30.20, 0.14341)
    assert "Error: peak demand charge must be a number" in str(excinfo.value)

def test_invalid_pk_demand_charge_string():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 16, 21, "invalid", 0.21585, 30.20, 0.14341)
    assert "Error: peak demand charge must be a number" in str(excinfo.value)

def test_invalid_off_pk_demand_charge_none():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 16, 21, 38.75, 0.21585, None, 0.14341)
    assert "Error: off-peak demand charge must be a number" in str(excinfo.value)

def test_invalid_off_pk_demand_charge_string():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 16, 21, 38.75, 0.21585, "invalid", 0.14341)
    assert "Error: off-peak demand charge must be a number" in str(excinfo.value)

def test_invalid_pk_energy_charge_none():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 16, 21, 38.75, None, 30.20, 0.14341)
    assert "Error: peak energy charge must be a number" in str(excinfo.value)

def test_invalid_pk_energy_charge_string():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 16, 21, 38.75, "invalid", 30.20, 0.14341)
    assert "Error: peak energy charge must be a number" in str(excinfo.value)

def test_invalid_off_pk_energy_charge_none():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 16, 21, 38.75, 0.21585, 30.20, None)
    assert "Error: off-peak energy charge must be a number" in str(excinfo.value)

def test_invalid_off_pk_energy_charge_string():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 16, 21, 38.75, 0.21585, 30.20, "invalid")
    assert "Error: off-peak energy charge must be a number" in str(excinfo.value)

def test_invalid_start_month_none():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 16, 21, 38.75, 0.21585, 30.20, 0.14341, None, 12)
    assert "Error: start_month must be a number between 0 and 11" in str(excinfo.value)

def test_invalid_start_month_string():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 16, 21, 38.75, 0.21585, 30.20, 0.14341, "invalid", 12)
    assert "Error: start_month must be a number between 0 and 11" in str(excinfo.value)

def test_invalid_start_month_float():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 16, 21, 38.75, 0.21585, 30.20, 0.14341, 0.5, 12)
    assert "Error: start_month must be a number between 0 and 11" in str(excinfo.value)

def test_invalid_first_start_month_not_zero():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, [16], [21], [38.75], [0.21585], [30.20], [0.14341], [1], [12])
    assert "Error: first start_month must be 0" in str(excinfo.value)

def test_invalid_start_month_mismatch():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, [16, 16], [21, 21], [38.75, 38.75], [0.21585, 0.21585],
                         [30.20, 30.20], [0.14341, 0.14341], [0, 7], [6, 12])
    assert "Error: current start_month must be equal to previous end month" in str(excinfo.value)

def test_invalid_end_month_none():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 16, 21, 38.75, 0.21585, 30.20, 0.14341, 0, None)
    assert "Error: end_month must be a number between (start_month+1) - 12" in str(excinfo.value)

def test_invalid_end_month_string():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, 16, 21, 38.75, 0.21585, 30.20, 0.14341, 0, "invalid")
    assert "Error: end_month must be a number between (start_month+1) - 12" in str(excinfo.value)

def test_invalid_end_month_less_than_start():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, [16], [21], [38.75], [0.21585], [30.20], [0.14341], [0], [0])
    assert "Error: end_month must be a number between (start_month+1) - 12" in str(excinfo.value)

def test_invalid_end_month_equal_to_start():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, [16, 16], [21, 21], [38.75, 38.75], [0.21585, 0.21585],
                         [30.20, 30.20], [0.14341, 0.14341], [0, 6], [6, 6])
    assert "Error: end_month must be a number between (start_month+1) - 12" in str(excinfo.value)

def test_invalid_final_end_month_not_twelve():
    with pytest.raises(Exception) as excinfo:
        UtilityCostTracker(190.0, [16], [21], [38.75], [0.21585], [30.20], [0.14341], [0], [11])
    assert "Error: final end_month must be 12" in str(excinfo.value)

    

