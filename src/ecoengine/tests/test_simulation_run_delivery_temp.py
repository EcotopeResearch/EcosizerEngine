"""
Tests for the recorded delivery temperature series.

``SimulationRun.delivery_temp_f`` holds the temperature of the water leaving the
last tank in the series for the mixing valve.  It is populated only for
schematics whose ``simulate_step()`` reports a ``"delivery_temp_f"`` key, and the
CSV column follows the same rule.
"""
import csv
import os
import tempfile

import pytest

from ecoengine import EcosizerEngine
from ecoengine.objects.simulation.SimulationRun import SimulationRun

_SUPPLY_T  = 120.0
_STORAGE_T = 145.0

# CSV header for the recorded series; the attribute itself is delivery_temp_f.
_CSV_COL = "delivery_temp_to_mixing_valve_f"


def _make_run(n_steps: int, delivery_temps: list[float] | None) -> SimulationRun:
    """Build a SimulationRun with n_steps recorded, optionally with delivery temps."""
    run = SimulationRun(duration_min=n_steps, timestep_min=1)
    run.supply_temp_f = _SUPPLY_T
    for i in range(n_steps):
        run.record_timestep(
            dhw_demand_supplyT_gal    = 1.0,
            usable_volume_supplyT_gal = 50.0,
            heater_output_kbtuh       = 10.0,
            heater_power_in_kw        = 1.0,
            oat_f                     = 50.0,
            inlet_water_temp_f        = 55.0,
            tank_temps_f              = [130.0] * 6,
            delivery_temp_f           = None if delivery_temps is None else delivery_temps[i],
        )
    return run


def _read_csv(run: SimulationRun) -> tuple[list[str], list[list[str]]]:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline=""
    ) as tmp:
        path = tmp.name
    try:
        run.to_csv(path)
        with open(path, newline="") as f:
            rows = list(csv.reader(f))
    finally:
        os.unlink(path)
    return rows[0], rows[1:]


# ---------------------------------------------------------------------------
# record_timestep / to_csv
# ---------------------------------------------------------------------------

class TestDeliveryTempRecording:

    def test_not_recorded_when_omitted(self):
        run = _make_run(5, None)
        assert run.delivery_temp_f == []

    def test_recorded_when_supplied(self):
        temps = [121.0, 122.0, 123.0, 124.0, 125.0]
        run = _make_run(5, temps)
        assert run.delivery_temp_f == temps

    def test_column_absent_when_not_recorded(self):
        header, _ = _read_csv(_make_run(5, None))
        assert _CSV_COL not in header

    def test_column_present_and_values_round_trip(self):
        temps = [121.0, 122.0, 123.0, 124.0, 125.0]
        header, rows = _read_csv(_make_run(5, temps))
        assert _CSV_COL in header
        col = header.index(_CSV_COL)
        assert [float(r[col]) for r in rows] == temps

    @pytest.mark.parametrize("temps", [None, [121.0, 122.0, 123.0, 124.0, 125.0]])
    def test_header_and_row_widths_match(self, temps):
        """Guards against a short delivery list silently misaligning the CSV."""
        header, rows = _read_csv(_make_run(5, temps))
        assert all(len(r) == len(header) for r in rows)


# ---------------------------------------------------------------------------
# get_failure_message prefers the recorded delivery temperature
# ---------------------------------------------------------------------------

class TestFailureMessageUsesDeliveryTemp:

    def test_delivery_temp_used_over_tm_tank(self):
        """A cold recorded delivery temp must drive the reported average even when
        the TM tank reads hot."""
        run = SimulationRun(duration_min=3, timestep_min=1)
        run.supply_temp_f  = _SUPPLY_T
        run.show_tm_panel  = True
        for _ in range(3):
            run.record_timestep(
                dhw_demand_supplyT_gal    = 1.0,
                usable_volume_supplyT_gal = 0.0,     # outage: primary empty
                heater_output_kbtuh       = 0.0,
                heater_power_in_kw        = None,
                oat_f                     = 50.0,
                inlet_water_temp_f        = 55.0,
                tank_temps_f              = [100.0] * 6,
                tm_tank_temp_f            = 110.0,   # below supply, so steps count
                delivery_temp_f           = 100.0,   # colder than the TM tank
            )
        run.outage_minutes = 3
        msg = run.get_failure_message()
        assert "100.0" in msg and "110.0" not in msg

    def test_falls_back_to_tm_tank_when_no_delivery_temp(self):
        run = SimulationRun(duration_min=3, timestep_min=1)
        run.supply_temp_f  = _SUPPLY_T
        run.show_tm_panel  = True
        for _ in range(3):
            run.record_timestep(
                dhw_demand_supplyT_gal    = 1.0,
                usable_volume_supplyT_gal = 0.0,
                heater_output_kbtuh       = 0.0,
                heater_power_in_kw        = None,
                oat_f                     = 50.0,
                inlet_water_temp_f        = 55.0,
                tank_temps_f              = [100.0] * 6,
                tm_tank_temp_f            = 110.0,
            )
        run.outage_minutes = 3
        assert "110.0" in run.get_failure_message()


# ---------------------------------------------------------------------------
# End to end through the engine
# ---------------------------------------------------------------------------

_COMMON = dict(
    building_type            = "multi_family",
    magnitude                = 100,
    zip_code_or_climate_zone = "95823",
    supply_temp_f            = _SUPPLY_T,
    storage_temp_f           = _STORAGE_T,
    gpdpp                    = 25,
)
_RECIRC = dict(return_flow_gpm=5.0, return_temp_f=110.0)


class TestDeliveryTempEndToEnd:

    @pytest.mark.parametrize("schematic,extra", [
        ("swing_tank",     _RECIRC),
        ("multi_pass_rtp", _RECIRC),
    ])
    def test_reported_by_emitting_schematics(self, schematic, extra):
        run = EcosizerEngine(schematic=schematic, **_COMMON, **extra).simulate_3day()
        n = len(run.usable_volume_supplyT_gal)
        assert len(run.delivery_temp_f) == n
        header, rows = _read_csv(run)
        assert _CSV_COL in header
        assert len(rows) == n

    @pytest.mark.parametrize("schematic,extra", [
        ("primary_no_recirc", {}),
        ("parallel_loop",     _RECIRC),
    ])
    def test_absent_for_non_emitting_schematics(self, schematic, extra):
        run = EcosizerEngine(schematic=schematic, **_COMMON, **extra).simulate_3day()
        assert run.delivery_temp_f == []
        header, _ = _read_csv(run)
        assert _CSV_COL not in header
