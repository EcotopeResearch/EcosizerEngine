"""
Tests for UtilityCostTracker and the SimulationRun cost integration methods.

Structure mirrors the original EcosizerEngine test_utilityTracker.py but uses
the new snake_case API (from_params, get_energy_charge_at_step, etc.) and
raises ValueError instead of bare Exception.
"""
import os
import pytest
import tempfile

from ecoengine.objects.building.UtilityCostTracker import UtilityCostTracker
from ecoengine.objects.simulation.SimulationRun import SimulationRun


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_uc(
    monthly_base_charge=190.0,
    pk_start_hour=16,
    pk_end_hour=21,
    pk_demand_charge=38.75,
    pk_energy_charge=0.21585,
    off_pk_demand_charge=30.20,
    off_pk_energy_charge=0.14341,
    **kwargs,
) -> UtilityCostTracker:
    """Convenience wrapper around from_params with sensible defaults."""
    return UtilityCostTracker.from_params(
        monthly_base_charge=monthly_base_charge,
        pk_start_hour=pk_start_hour,
        pk_end_hour=pk_end_hour,
        pk_demand_charge=pk_demand_charge,
        pk_energy_charge=pk_energy_charge,
        off_pk_demand_charge=off_pk_demand_charge,
        off_pk_energy_charge=off_pk_energy_charge,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# from_params — basic (scalar) parametrization
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "monthly_base_charge, pk_start_hour, pk_end_hour, "
    "pk_demand_charge, pk_energy_charge, off_pk_demand_charge, off_pk_energy_charge",
    [
        (190.00, 16, 21, 38.75, 0.21585, 30.20, 0.14341),
        (190.00,  0, 24, 38.75, 0.21585, 30.20, 0.14341),   # all-peak
        (190.00, 21, 21, 38.75, 0.21585, 30.20, 0.14341),   # zero-length peak
        (  1.00, 20, 21,  0.75,     4.5,   3.20,    0.1),
    ],
)
def test_from_params_basic(
    monthly_base_charge,
    pk_start_hour, pk_end_hour,
    pk_demand_charge, pk_energy_charge,
    off_pk_demand_charge, off_pk_energy_charge,
):
    uc = _make_uc(
        monthly_base_charge=monthly_base_charge,
        pk_start_hour=pk_start_hour,
        pk_end_hour=pk_end_hour,
        pk_demand_charge=pk_demand_charge,
        pk_energy_charge=pk_energy_charge,
        off_pk_demand_charge=off_pk_demand_charge,
        off_pk_energy_charge=off_pk_energy_charge,
    )

    assert uc.get_yearly_base_charge() == monthly_base_charge * 12

    # Determine expected rates for edge-case peak windows
    if pk_start_hour == pk_end_hour:
        # Zero-length peak → no hour is ever peak
        expected_peak    = off_pk_energy_charge
        expected_off_pk  = off_pk_energy_charge
    elif pk_start_hour == 0 and pk_end_hour == 24:
        # All hours are peak
        expected_peak    = pk_energy_charge
        expected_off_pk  = pk_energy_charge
    else:
        expected_peak    = pk_energy_charge
        expected_off_pk  = off_pk_energy_charge

    # Day 1 — sample the peak start and end hours at three timestep resolutions
    for step, ts in [
        (pk_start_hour,      60),
        (pk_start_hour * 4,  15),
        (pk_start_hour * 60,  1),
    ]:
        assert uc.get_energy_charge_at_step(step, ts) == expected_peak, (
            f"Expected peak rate at pk_start step={step} ts={ts}"
        )

    # One interval before peak start should be off-peak (skip when start=0)
    if pk_start_hour > 0:
        for step, ts in [
            (pk_start_hour - 1,       60),
            (pk_start_hour * 4 - 1,   15),
            (pk_start_hour * 60 - 1,   1),
        ]:
            assert uc.get_energy_charge_at_step(step, ts) == expected_off_pk

    # One interval before peak end should be peak (last peak interval)
    if pk_end_hour > pk_start_hour:
        for step, ts in [
            (pk_end_hour - 1,       60),
            (pk_end_hour * 4 - 1,   15),
            (pk_end_hour * 60 - 1,   1),
        ]:
            assert uc.get_energy_charge_at_step(step, ts) == expected_peak

    # Peak end hour itself should be off-peak (unless all-peak)
    for step, ts in [
        (pk_end_hour,      60),
        (pk_end_hour * 4,  15),
        (pk_end_hour * 60,  1),
    ]:
        assert uc.get_energy_charge_at_step(step, ts) == expected_off_pk

    # Day 2 (same pattern repeats 24 hours later)
    next_pk_hr = pk_start_hour + 24
    for step, ts in [
        (next_pk_hr,      60),
        (next_pk_hr * 4,  15),
        (next_pk_hr * 60,  1),
    ]:
        assert uc.get_energy_charge_at_step(step, ts) == expected_peak


# ---------------------------------------------------------------------------
# from_params — seasonal (list) variation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "monthly_base_charge, pk_start_hour, pk_end_hour, "
    "pk_demand_charge, pk_energy_charge, off_pk_demand_charge, off_pk_energy_charge, "
    "start_month, end_month",
    [
        (5.00, [16, 23], [21, 24], [38.75, 38.77], [0.21585, 0.5],
         [30.20, 35.0], [0.14341, 0.07], [0, 5], [5, 12]),
        (5.00, [16, 23, 13], [21, 24, 14], [38.75, 38.77, 39],
         [0.21585, 0.5, 0.4], [30.20, 35.0, 40], [0.14341, 0.07, 0.8],
         [0, 5, 7], [5, 7, 12]),
        (5.00, [16], [21], [38.75], [0.21585], [30.20], [0.1434], [0], [12]),
    ],
)
def test_from_params_seasonal(
    monthly_base_charge,
    pk_start_hour, pk_end_hour,
    pk_demand_charge, pk_energy_charge,
    off_pk_demand_charge, off_pk_energy_charge,
    start_month, end_month,
):
    uc = UtilityCostTracker.from_params(
        monthly_base_charge=monthly_base_charge,
        pk_start_hour=pk_start_hour,
        pk_end_hour=pk_end_hour,
        pk_demand_charge=pk_demand_charge,
        pk_energy_charge=pk_energy_charge,
        off_pk_demand_charge=off_pk_demand_charge,
        off_pk_energy_charge=off_pk_energy_charge,
        start_month=start_month,
        end_month=end_month,
    )

    assert uc.get_yearly_base_charge() == monthly_base_charge * 12
    # 12 months × 2 periods each = 24 demand period keys
    assert len(uc.get_all_demand_period_keys()) == 24

    # First seasonal block — check pk_start of first block
    assert uc.get_energy_charge_at_step(pk_start_hour[0], 60) == pk_energy_charge[0]
    assert uc.get_energy_charge_at_step(pk_end_hour[0], 60)   == off_pk_energy_charge[0]

    # Last seasonal block — hour near end of year
    assert uc.get_energy_charge_at_step(8760 - 48 + pk_start_hour[-1], 60) == pk_energy_charge[-1]
    assert uc.get_energy_charge_at_step(8760 - 48 + pk_end_hour[-1],   60) == off_pk_energy_charge[-1]


# ---------------------------------------------------------------------------
# Validation errors — monthly_base_charge
# ---------------------------------------------------------------------------

def test_invalid_monthly_base_charge_none():
    with pytest.raises(Exception) as exc:
        _make_uc(monthly_base_charge=None)
    assert "Error: monthly base charge must be a number" in str(exc.value)


def test_invalid_monthly_base_charge_string():
    with pytest.raises(Exception) as exc:
        _make_uc(monthly_base_charge="invalid")
    assert "Error: monthly base charge must be a number" in str(exc.value)


def test_invalid_monthly_base_charge_list():
    with pytest.raises(Exception) as exc:
        _make_uc(monthly_base_charge=[190.0])
    assert "Error: monthly base charge must be a number" in str(exc.value)


# ---------------------------------------------------------------------------
# Validation errors — list length mismatch
# ---------------------------------------------------------------------------

def test_mismatched_list_lengths():
    with pytest.raises(Exception) as exc:
        UtilityCostTracker.from_params(
            190.0, [16, 17], [21], [38.75], [0.21585], [30.20], [0.14341],
        )
    assert "must all be the same length" in str(exc.value)


def test_mismatched_list_lengths_with_months():
    with pytest.raises(Exception) as exc:
        UtilityCostTracker.from_params(
            190.0, [16], [21], [38.75], [0.21585], [30.20], [0.14341],
            start_month=[0, 6], end_month=[6, 12],
        )
    assert "must all be the same length" in str(exc.value)


# ---------------------------------------------------------------------------
# Validation errors — pk_start_hour
# ---------------------------------------------------------------------------

def test_invalid_pk_start_hour_none():
    with pytest.raises(Exception) as exc:
        _make_uc(pk_start_hour=None)
    assert "Error: peak start hour must be a number between 0 and 23" in str(exc.value)


def test_invalid_pk_start_hour_string():
    with pytest.raises(Exception) as exc:
        _make_uc(pk_start_hour="invalid")
    assert "Error: peak start hour must be a number between 0 and 23" in str(exc.value)


def test_invalid_pk_start_hour_negative():
    with pytest.raises(Exception) as exc:
        _make_uc(pk_start_hour=-1)
    assert "Error: peak start hour must be a number between 0 and 23" in str(exc.value)


def test_invalid_pk_start_hour_too_large():
    with pytest.raises(Exception) as exc:
        _make_uc(pk_start_hour=24, pk_end_hour=24)
    assert "Error: peak start hour must be a number between 0 and 23" in str(exc.value)


# ---------------------------------------------------------------------------
# Validation errors — pk_end_hour
# ---------------------------------------------------------------------------

def test_invalid_pk_end_hour_none():
    with pytest.raises(Exception) as exc:
        _make_uc(pk_end_hour=None)
    assert "Error: peak end hour must be a number between peak start hour and 24" in str(exc.value)


def test_invalid_pk_end_hour_string():
    with pytest.raises(Exception) as exc:
        _make_uc(pk_end_hour="invalid")
    assert "Error: peak end hour must be a number between peak start hour and 24" in str(exc.value)


def test_invalid_pk_end_hour_less_than_start():
    with pytest.raises(Exception) as exc:
        _make_uc(pk_start_hour=16, pk_end_hour=15)
    assert "Error: peak end hour must be a number between peak start hour and 24" in str(exc.value)


def test_invalid_pk_end_hour_too_large():
    with pytest.raises(Exception) as exc:
        _make_uc(pk_end_hour=25)
    assert "Error: peak end hour must be a number between peak start hour and 24" in str(exc.value)


# ---------------------------------------------------------------------------
# Validation errors — demand/energy charges
# ---------------------------------------------------------------------------

def test_invalid_pk_demand_charge_none():
    with pytest.raises(Exception) as exc:
        _make_uc(pk_demand_charge=None)
    assert "Error: peak demand charge must be a number" in str(exc.value)


def test_invalid_pk_demand_charge_string():
    with pytest.raises(Exception) as exc:
        _make_uc(pk_demand_charge="invalid")
    assert "Error: peak demand charge must be a number" in str(exc.value)


def test_invalid_off_pk_demand_charge_none():
    with pytest.raises(Exception) as exc:
        _make_uc(off_pk_demand_charge=None)
    assert "Error: off-peak demand charge must be a number" in str(exc.value)


def test_invalid_off_pk_demand_charge_string():
    with pytest.raises(Exception) as exc:
        _make_uc(off_pk_demand_charge="invalid")
    assert "Error: off-peak demand charge must be a number" in str(exc.value)


def test_invalid_pk_energy_charge_none():
    with pytest.raises(Exception) as exc:
        _make_uc(pk_energy_charge=None)
    assert "Error: peak energy charge must be a number" in str(exc.value)


def test_invalid_pk_energy_charge_string():
    with pytest.raises(Exception) as exc:
        _make_uc(pk_energy_charge="invalid")
    assert "Error: peak energy charge must be a number" in str(exc.value)


def test_invalid_off_pk_energy_charge_none():
    with pytest.raises(Exception) as exc:
        _make_uc(off_pk_energy_charge=None)
    assert "Error: off-peak energy charge must be a number" in str(exc.value)


def test_invalid_off_pk_energy_charge_string():
    with pytest.raises(Exception) as exc:
        _make_uc(off_pk_energy_charge="invalid")
    assert "Error: off-peak energy charge must be a number" in str(exc.value)


# ---------------------------------------------------------------------------
# Validation errors — month params
# ---------------------------------------------------------------------------

def test_invalid_start_month_none():
    with pytest.raises(Exception) as exc:
        _make_uc(start_month=None, end_month=12)
    assert "Error: start_month must be a number between 0 and 11" in str(exc.value)


def test_invalid_start_month_string():
    with pytest.raises(Exception) as exc:
        _make_uc(start_month="invalid", end_month=12)
    assert "Error: start_month must be a number between 0 and 11" in str(exc.value)


def test_invalid_start_month_float():
    with pytest.raises(Exception) as exc:
        _make_uc(start_month=0.5, end_month=12)
    assert "Error: start_month must be a number between 0 and 11" in str(exc.value)


def test_invalid_first_start_month_not_zero():
    with pytest.raises(Exception) as exc:
        UtilityCostTracker.from_params(
            190.0, [16], [21], [38.75], [0.21585], [30.20], [0.14341],
            start_month=[1], end_month=[12],
        )
    assert "Error: first start_month must be 0" in str(exc.value)


def test_invalid_start_month_mismatch():
    with pytest.raises(Exception) as exc:
        UtilityCostTracker.from_params(
            190.0, [16, 16], [21, 21], [38.75, 38.75], [0.21585, 0.21585],
            [30.20, 30.20], [0.14341, 0.14341],
            start_month=[0, 7], end_month=[6, 12],
        )
    assert "Error: current start_month must be equal to previous end month" in str(exc.value)


def test_invalid_end_month_none():
    with pytest.raises(Exception) as exc:
        _make_uc(start_month=0, end_month=None)
    assert "Error: end_month must be a number between (start_month+1) - 12" in str(exc.value)


def test_invalid_end_month_string():
    with pytest.raises(Exception) as exc:
        _make_uc(start_month=0, end_month="invalid")
    assert "Error: end_month must be a number between (start_month+1) - 12" in str(exc.value)


def test_invalid_end_month_less_than_start():
    with pytest.raises(Exception) as exc:
        UtilityCostTracker.from_params(
            190.0, [16], [21], [38.75], [0.21585], [30.20], [0.14341],
            start_month=[0], end_month=[0],
        )
    assert "Error: end_month must be a number between (start_month+1) - 12" in str(exc.value)


def test_invalid_end_month_equal_to_start():
    with pytest.raises(Exception) as exc:
        UtilityCostTracker.from_params(
            190.0, [16, 16], [21, 21], [38.75, 38.75], [0.21585, 0.21585],
            [30.20, 30.20], [0.14341, 0.14341],
            start_month=[0, 6], end_month=[6, 6],
        )
    assert "Error: end_month must be a number between (start_month+1) - 12" in str(exc.value)


def test_invalid_final_end_month_not_twelve():
    with pytest.raises(Exception) as exc:
        UtilityCostTracker.from_params(
            190.0, [16], [21], [38.75], [0.21585], [30.20], [0.14341],
            start_month=[0], end_month=[11],
        )
    assert "Error: final end_month must be 12" in str(exc.value)


# ---------------------------------------------------------------------------
# get_demand_charge_for_period
# ---------------------------------------------------------------------------

def test_demand_charge_for_period_basic():
    uc = _make_uc(pk_demand_charge=38.75, off_pk_demand_charge=30.20)
    keys = uc.get_all_demand_period_keys()
    assert len(keys) == 24  # 12 months × 2 periods
    # All period-0 keys are off-peak; period-1 are peak
    for key in keys:
        charge = uc.get_demand_charge_for_period(key, 10.0)
        if key % 2 == 0:
            assert charge == pytest.approx(30.20 * 10.0)
        else:
            assert charge == pytest.approx(38.75 * 10.0)


def test_demand_charge_for_undefined_period():
    uc = _make_uc()
    with pytest.raises(ValueError, match="is not a defined demand period"):
        uc.get_demand_charge_for_period(9999, 5.0)


# ---------------------------------------------------------------------------
# Discount period
# ---------------------------------------------------------------------------

def test_discount_period_keys():
    uc = UtilityCostTracker.from_params(
        monthly_base_charge=50.0,
        pk_start_hour=16,
        pk_end_hour=21,
        pk_demand_charge=38.75,
        pk_energy_charge=0.30,
        off_pk_demand_charge=30.0,
        off_pk_energy_charge=0.15,
        include_discount=True,
        dscnt_start_hour=0,
        dscnt_end_hour=6,
        discnt_demand_charge=5.0,
        discnt_energy_charge=0.05,
    )
    keys = uc.get_all_demand_period_keys()
    assert len(keys) == 36  # 12 months × 3 periods


def test_discount_period_energy_rate():
    uc = UtilityCostTracker.from_params(
        monthly_base_charge=50.0,
        pk_start_hour=16,
        pk_end_hour=21,
        pk_demand_charge=38.75,
        pk_energy_charge=0.30,
        off_pk_demand_charge=30.0,
        off_pk_energy_charge=0.15,
        include_discount=True,
        dscnt_start_hour=0,
        dscnt_end_hour=6,
        discnt_demand_charge=5.0,
        discnt_energy_charge=0.05,
    )
    # Hour 3 (03:00) is in discount window [0, 6)
    assert uc.get_energy_charge_at_step(3, 60) == pytest.approx(0.05)
    # Hour 18 is peak
    assert uc.get_energy_charge_at_step(18, 60) == pytest.approx(0.30)
    # Hour 10 is off-peak (not in peak [16,21) or discount [0,6))
    assert uc.get_energy_charge_at_step(10, 60) == pytest.approx(0.15)


# ---------------------------------------------------------------------------
# from_csv / to_csv roundtrip
# ---------------------------------------------------------------------------

def test_csv_roundtrip():
    uc = _make_uc(
        monthly_base_charge=190.0,
        pk_start_hour=16,
        pk_end_hour=21,
        pk_demand_charge=38.75,
        pk_energy_charge=0.21585,
        off_pk_demand_charge=30.20,
        off_pk_energy_charge=0.14341,
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline=""
    ) as tmp:
        csv_path = tmp.name

    try:
        uc.to_csv(csv_path)
        uc2 = UtilityCostTracker.from_csv(csv_path=csv_path)
    finally:
        os.unlink(csv_path)

    assert uc2.monthly_base_charge == pytest.approx(190.0)
    assert uc2.get_yearly_base_charge() == pytest.approx(190.0 * 12)

    # Energy rate at hour 18 (peak) and hour 10 (off-peak) should survive roundtrip
    assert uc2.get_energy_charge_at_step(18, 60) == pytest.approx(0.21585)
    assert uc2.get_energy_charge_at_step(10, 60) == pytest.approx(0.14341)


def test_csv_wrong_row_count():
    header = "Date,Demand Period,Energy Rate ($/kWh),Demand Rate ($/kW),Monthly Base Charge\n"
    body   = "Jan 1, 00:00,0,0.1,10.0,190.0\n" * 100  # only 100 rows

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline=""
    ) as tmp:
        tmp.write(header + body)
        csv_path = tmp.name

    try:
        with pytest.raises(ValueError, match="8760"):
            UtilityCostTracker.from_csv(csv_path=csv_path)
    finally:
        os.unlink(csv_path)


def test_csv_missing_column():
    # Write a CSV without the 'Demand Period' column
    header = "Date,Energy Rate ($/kWh),Demand Rate ($/kW),Monthly Base Charge\n"
    body   = "Jan 1,0.1,10.0,190.0\n" * 8760

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline=""
    ) as tmp:
        tmp.write(header + body)
        csv_path = tmp.name

    try:
        with pytest.raises(ValueError, match="Missing Columns"):
            UtilityCostTracker.from_csv(csv_path=csv_path)
    finally:
        os.unlink(csv_path)


# ---------------------------------------------------------------------------
# SimulationRun.get_annual_utility_cost
# ---------------------------------------------------------------------------

def _make_sim_run(timestep_min: int, n_steps: int, power_kw: float) -> SimulationRun:
    """Create a minimal SimulationRun with constant power at every step."""
    sr = SimulationRun(
        duration_min=n_steps * timestep_min,
        timestep_min=timestep_min,
    )
    # Populate just the fields get_annual_utility_cost needs
    sr.heater_power_in_kw = [power_kw] * n_steps
    return sr


def test_annual_cost_energy_only():
    """All-off-peak rate, no demand charge → cost = power × hours × energy_rate + base."""
    # 10-min timestep, 365 days, 0.10 $/kWh, 30 $/month base, no demand charge
    steps_per_year = 365 * 24 * 6   # 52560 steps at 10 min
    power_kw       = 2.0
    energy_rate    = 0.10
    base_monthly   = 30.0
    demand_charge  = 0.0

    sr = _make_sim_run(10, steps_per_year, power_kw)
    uc = _make_uc(
        monthly_base_charge=base_monthly,
        pk_start_hour=0,
        pk_end_hour=0,   # zero-length → no peak hours → all off-peak
        pk_demand_charge=0.0,
        pk_energy_charge=0.99,
        off_pk_demand_charge=demand_charge,
        off_pk_energy_charge=energy_rate,
    )

    expected_energy = power_kw * (10 / 60.0) * steps_per_year * energy_rate
    expected_demand = demand_charge * power_kw * 12  # 0 anyway
    expected_base   = base_monthly * 12
    expected_total  = expected_energy + expected_demand + expected_base

    assert sr.get_annual_utility_cost(uc) == pytest.approx(expected_total, rel=1e-6)


def test_annual_cost_includes_demand():
    """Check that the peak-period max-kW demand charge is included."""
    steps_per_year = 365 * 24 * 6
    power_kw       = 5.0
    peak_demand    = 10.0   # $/kW
    off_pk_demand  = 3.0
    peak_energy    = 0.25
    off_pk_energy  = 0.10

    sr = _make_sim_run(10, steps_per_year, power_kw)
    uc = _make_uc(
        monthly_base_charge=100.0,
        pk_start_hour=16,
        pk_end_hour=21,
        pk_demand_charge=peak_demand,
        pk_energy_charge=peak_energy,
        off_pk_demand_charge=off_pk_demand,
        off_pk_energy_charge=off_pk_energy,
    )

    total = sr.get_annual_utility_cost(uc)
    # Must exceed base charge alone
    assert total > 100.0 * 12
    # Must include both peak and off-peak demand charges for all 12 months
    demand_keys = uc.get_all_demand_period_keys()
    peak_months = sum(1 for k in demand_keys if k % 2 == 1)
    assert peak_months == 12


# ---------------------------------------------------------------------------
# SimulationRun.get_monthly_cost_breakdown
# ---------------------------------------------------------------------------

def test_monthly_cost_breakdown_sums_to_annual():
    """Sum of monthly energy+demand+base should equal get_annual_utility_cost."""
    steps_per_year = 365 * 24 * 6
    power_kw       = 3.0

    sr = _make_sim_run(10, steps_per_year, power_kw)
    uc = _make_uc(
        monthly_base_charge=50.0,
        pk_start_hour=16,
        pk_end_hour=21,
        pk_demand_charge=20.0,
        pk_energy_charge=0.20,
        off_pk_demand_charge=10.0,
        off_pk_energy_charge=0.10,
    )

    annual       = sr.get_annual_utility_cost(uc)
    breakdown    = sr.get_monthly_cost_breakdown(uc)
    monthly_sum  = (
        sum(breakdown["energy"])
        + sum(breakdown["demand"])
        + breakdown["base"] * 12
    )
    assert monthly_sum == pytest.approx(annual, rel=1e-6)


def test_monthly_cost_breakdown_structure():
    steps_per_year = 365 * 24 * 6
    sr = _make_sim_run(10, steps_per_year, 2.0)
    uc = _make_uc()
    breakdown = sr.get_monthly_cost_breakdown(uc)

    assert set(breakdown.keys()) == {"energy", "demand", "base"}
    assert len(breakdown["energy"]) == 12
    assert len(breakdown["demand"]) == 12
    assert isinstance(breakdown["base"], float)
    assert breakdown["base"] == pytest.approx(uc.monthly_base_charge)


# ---------------------------------------------------------------------------
# Primary + TM / gas power are combined in every SimulationRun total
# ---------------------------------------------------------------------------

def _make_split_run(primary_kw: float, tm_kw: float) -> SimulationRun:
    """Annual 10-min run whose power is split between primary and TM series."""
    steps_per_year = 365 * 24 * 6
    sr = _make_sim_run(10, steps_per_year, primary_kw)
    sr.tm_heater_input_kw = [tm_kw] * steps_per_year
    return sr


def test_split_power_matches_single_series_in_all_totals():
    """A 1.5 + 0.5 kW split must give the same totals as a single 2.0 kW series."""
    split = _make_split_run(1.5, 0.5)
    whole = _make_sim_run(10, 365 * 24 * 6, 2.0)
    uc = _make_uc()

    assert split.get_total_energy_kwh() == pytest.approx(whole.get_total_energy_kwh())
    assert split.get_peak_demand_kw() == pytest.approx(2.0)
    assert split.get_monthly_energy_kwh() == pytest.approx(whole.get_monthly_energy_kwh())
    assert split.get_annual_utility_cost(uc) == pytest.approx(whole.get_annual_utility_cost(uc))

    split_monthly = split.get_monthly_cost_breakdown(uc)
    whole_monthly = whole.get_monthly_cost_breakdown(uc)
    assert split_monthly["energy"] == pytest.approx(whole_monthly["energy"])
    assert split_monthly["demand"] == pytest.approx(whole_monthly["demand"])

    split_detail = split.get_monthly_cost_breakdown_detailed(uc)
    whole_detail = whole.get_monthly_cost_breakdown_detailed(uc)
    for key in ("energy_peak", "energy_off_peak", "demand_peak", "demand_off_peak"):
        assert split_detail[key] == pytest.approx(whole_detail[key])


def test_peak_demand_sums_series_per_timestep():
    """Peak is the max of the per-step sum, not the max of either series."""
    sr = _make_sim_run(10, 3, 0.0)
    sr.heater_power_in_kw = [5.0, None, 1.0]
    sr.tm_heater_input_kw = [0.0, 4.0, 4.5]
    assert sr.get_peak_demand_kw() == pytest.approx(5.5)


# ---------------------------------------------------------------------------
# Windowed demand: max average kW over demand_interval_min inside one period
# ---------------------------------------------------------------------------

def _one_day_run(timestep_min: int, spikes: dict[int, float]) -> SimulationRun:
    """One-day run, 0 kW except {step: kW} spikes."""
    n_steps = 24 * 60 // timestep_min
    sr = _make_sim_run(timestep_min, n_steps, 0.0)
    for step, kw in spikes.items():
        sr.heater_power_in_kw[step] = kw
    return sr


_JAN_OFF, _JAN_PEAK = 0, 1   # from_params keys: month*2 (off-peak), month*2+1 (peak 16-21)


def test_demand_interval_defaults_to_15_min():
    assert _make_uc().demand_interval_min == 15


def test_single_10min_spike_averaged_over_15min():
    """A 30 kW 10-minute step inside off-peak bills as 30 * 10/15 = 20 kW."""
    sr = _one_day_run(10, {12: 30.0})          # 02:00-02:10, off-peak
    demand = sr.get_max_demand_kw_by_period(_make_uc())
    assert demand[_JAN_OFF] == pytest.approx(20.0)
    assert demand[_JAN_PEAK] == pytest.approx(0.0)


def test_single_1min_spike_averaged_over_15min():
    sr = _one_day_run(1, {17 * 60: 60.0})      # 17:00-17:01, peak
    assert sr.get_max_demand_kw_by_period(_make_uc())[_JAN_PEAK] == pytest.approx(4.0)


def test_two_consecutive_10min_steps_inside_peak_bill_full_kw():
    """
    30 kW for 16:20-16:40 (two 10-min steps, entirely inside peak) contains a
    full 15-minute window at 30 kW (e.g. 16:20-16:35), so peak demand is 30 kW.
    """
    sr = _one_day_run(10, {98: 30.0, 99: 30.0})   # steps 16:20 and 16:30
    demand = sr.get_max_demand_kw_by_period(_make_uc())
    assert demand[_JAN_PEAK] == pytest.approx(30.0)
    assert demand[_JAN_OFF] == pytest.approx(0.0)


def test_window_spanning_two_periods_is_ignored():
    """
    30 kW from 15:50 to 16:10 straddles the off-peak -> peak boundary at 16:00.
    The 15:55-16:10 window (30 kW avg) spans both periods and is ignored, so each
    period only sees 10 of 15 minutes at 30 kW -> 20 kW.
    """
    sr = _one_day_run(10, {95: 30.0, 96: 30.0})   # steps 15:50 and 16:00
    demand = sr.get_max_demand_kw_by_period(_make_uc())
    assert demand[_JAN_OFF] == pytest.approx(20.0)
    assert demand[_JAN_PEAK] == pytest.approx(20.0)


def test_configurable_interval_matching_timestep_gives_step_max():
    """With demand_interval_min == timestep, demand is the single-step max."""
    sr = _one_day_run(10, {12: 30.0, 100: 7.0})
    demand = sr.get_max_demand_kw_by_period(_make_uc(demand_interval_min=10))
    assert demand[_JAN_OFF] == pytest.approx(30.0)
    assert demand[_JAN_PEAK] == pytest.approx(7.0)


def test_windowed_demand_feeds_costs():
    """Peak demand charge uses the 15-min average, in every cost function."""
    sr = _one_day_run(10, {100: 30.0})          # 16:40-16:50, peak
    uc = _make_uc(pk_demand_charge=10.0, off_pk_demand_charge=0.0,
                  pk_energy_charge=0.0, off_pk_energy_charge=0.0, monthly_base_charge=0.0)
    expected = 10.0 * 20.0
    assert sr.get_annual_utility_cost(uc) == pytest.approx(expected)
    assert sum(sr.get_monthly_cost_breakdown(uc)["demand"]) == pytest.approx(expected)
    assert sum(sr.get_monthly_cost_breakdown_detailed(uc)["demand_peak"]) == pytest.approx(expected)


@pytest.mark.parametrize("bad", [0, -15, 7.5, True])
def test_demand_interval_must_be_positive_int(bad):
    with pytest.raises(ValueError, match="demand_interval_min"):
        _make_uc(demand_interval_min=bad)


def test_from_csv_accepts_demand_interval(tmp_path):
    path = str(tmp_path / "rates.csv")
    _make_uc().to_csv(path)
    assert UtilityCostTracker.from_csv(path).demand_interval_min == 15
    assert UtilityCostTracker.from_csv(path, demand_interval_min=30).demand_interval_min == 30
