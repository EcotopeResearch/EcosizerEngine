"""
Sizing comparison: EcosizerEngine (original) vs EcosizerEngine2 (new).

Runs several sizing scenarios both with and without load shifting, then
writes results side-by-side to compare_sizing_output.csv.

Usage:
    python compare_sizing.py
"""

import sys
import json
import csv
import subprocess
import os

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------
# Each scenario is a dict consumed by both the original and new sizing code.
# Fields:
#   label           : human-readable name for the row
#   building_type   : 'multi_family', 'mens_dorm', etc.
#   magnitude       : number of units / people
#   gpdpp           : gallons per person per day (0 if not applicable)
#   supply_t_f      : DHW delivery temperature [°F]
#   storage_t_f     : storage setpoint [°F]
#   inlet_t_f       : design cold-water inlet [°F]
#   design_oat_f    : design outdoor air temperature [°F]
#   max_run_hr      : max heater run hours per day
#   defrost_factor  : defrost derating (1.0 = no derating)
#   on_fract        : normal ON aquastat fractional height (must be > 0 for original)
#   off_fract       : normal OFF aquastat fractional height
#   load_shift      : True / False
#   shed_hours      : list of 0-23 hour indices that are shed (only if load_shift=True)
#   lu_hours        : number of load-up hours before first shed (0 = no load-up)
#   lu_on_fract     : load-up ON aquastat (must be <= on_fract for original)
#   shed_on_fract   : shed ON aquastat (must be >= on_fract for original)

SCENARIOS = [
    dict(
        label="100-unit MF, 24hr run, no controls",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=24.0, defrost_factor=1.0,
        on_fract=0.1, off_fract=0.1,
        load_shift=False, shed_hours=[], lu_hours=0,
        lu_on_fract=None, shed_on_fract=None,
    ),
    dict(
        label="100-unit MF, 16hr run, no controls",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.1, off_fract=0.1,
        load_shift=False, shed_hours=[], lu_hours=0,
        lu_on_fract=None, shed_on_fract=None,
    ),
    dict(
        label="100-unit MF, 24hr run, high aquastat (on=0.5)",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=24.0, defrost_factor=1.0,
        on_fract=0.5, off_fract=0.1,
        load_shift=False, shed_hours=[], lu_hours=0,
        lu_on_fract=None, shed_on_fract=None,
    ),
    dict(
        label="50-unit MF, 16hr run, gpdpp=30",
        building_type="multi_family", magnitude=50, gpdpp=30,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.1, off_fract=0.1,
        load_shift=False, shed_hours=[], lu_hours=0,
        lu_on_fract=None, shed_on_fract=None,
    ),
    dict(
        label="100-unit MF, LS 8hr shed hrs 7-14, 2hr LU, no LU key",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=24.0, defrost_factor=1.0,
        on_fract=0.5, off_fract=0.1,
        load_shift=True, shed_hours=list(range(7, 15)), lu_hours=0,
        lu_on_fract=None, shed_on_fract=0.8,
    ),
    dict(
        label="100-unit MF, LS 8hr shed hrs 7-14, 2hr LU (on=0.3, shed=0.8)",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=24.0, defrost_factor=1.0,
        on_fract=0.5, off_fract=0.1,
        load_shift=True, shed_hours=list(range(7, 15)), lu_hours=2,
        lu_on_fract=0.3, shed_on_fract=0.8,
    ),
    dict(
        label="100-unit MF, LS 5hr shed hrs 10-14, 2hr LU",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=24.0, defrost_factor=1.0,
        on_fract=0.5, off_fract=0.1,
        load_shift=True, shed_hours=list(range(10, 15)), lu_hours=2,
        lu_on_fract=0.3, shed_on_fract=0.8,
    ),
    dict(
        label="200-unit MF, LS 8hr shed hrs 7-14, 3hr LU",
        building_type="multi_family", magnitude=200, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=24.0, defrost_factor=1.0,
        on_fract=0.5, off_fract=0.1,
        load_shift=True, shed_hours=list(range(7, 15)), lu_hours=3,
        lu_on_fract=0.3, shed_on_fract=0.8,
    ),
    # ----------------------------------------------------------------
    # load_shift_percent < 1.0 scenarios
    # ----------------------------------------------------------------
    dict(
        label="100-unit MF, LS 5hr shed 16-20, 3hr LU, ls_pct=1.00",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        load_shift=True, shed_hours=list(range(16, 21)), lu_hours=3,
        lu_on_fract=0.2, shed_on_fract=0.8, load_shift_percent=1.0,
    ),
    dict(
        label="100-unit MF, LS 5hr shed 16-20, 3hr LU, ls_pct=0.95",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        load_shift=True, shed_hours=list(range(16, 21)), lu_hours=3,
        lu_on_fract=0.2, shed_on_fract=0.8, load_shift_percent=0.95,
    ),
    dict(
        label="100-unit MF, LS 5hr shed 16-20, 3hr LU, ls_pct=0.85",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        load_shift=True, shed_hours=list(range(16, 21)), lu_hours=3,
        lu_on_fract=0.2, shed_on_fract=0.8, load_shift_percent=0.85,
    ),
    dict(
        label="100-unit MF, LS 5hr shed 16-20, 3hr LU, ls_pct=0.75",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        load_shift=True, shed_hours=list(range(16, 21)), lu_hours=3,
        lu_on_fract=0.2, shed_on_fract=0.8, load_shift_percent=0.75,
    ),
    dict(
        label="200-unit MF, LS 8hr shed 7-14, 3hr LU, ls_pct=0.95",
        building_type="multi_family", magnitude=200, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        load_shift=True, shed_hours=list(range(7, 15)), lu_hours=3,
        lu_on_fract=0.2, shed_on_fract=0.8, load_shift_percent=0.95,
    ),
    dict(
        label="200-unit MF, LS 8hr shed 7-14, 3hr LU, ls_pct=0.75",
        building_type="multi_family", magnitude=200, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        load_shift=True, shed_hours=list(range(7, 15)), lu_hours=3,
        lu_on_fract=0.2, shed_on_fract=0.8, load_shift_percent=0.75,
    ),
]


# ---------------------------------------------------------------------------
# Parallel Loop scenarios
# ---------------------------------------------------------------------------
# Extra fields beyond the base scenario dict:
#   return_temp_f   : recirc loop return temperature [°F]
#   return_flow_gpm : recirc loop flow rate [GPM]
#   tm_on_temp_f    : TM element turn-on temperature [°F]
#   tm_off_temp_f   : TM element turn-off temperature [°F]
#   tm_off_time_hr  : max off-cycle duration for TM heater [hr]
#   tm_safety_factor: TM capacity multiplier (must be > 1.0)

PARALLEL_SCENARIOS = [
    dict(
        label="PL: 100-unit MF, 3 GPM recirc, 10F drop",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=110.0, return_flow_gpm=3.0,
        tm_on_temp_f=115.0, tm_off_temp_f=120.0,
        tm_off_time_hr=0.5, tm_safety_factor=1.2,
    ),
    dict(
        label="PL: 200-unit MF, 5 GPM recirc, 10F drop",
        building_type="multi_family", magnitude=200, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=110.0, return_flow_gpm=5.0,
        tm_on_temp_f=115.0, tm_off_temp_f=120.0,
        tm_off_time_hr=0.5, tm_safety_factor=1.5,
    ),
    dict(
        label="PL: 50-unit MF, 2 GPM recirc, 15F drop",
        building_type="multi_family", magnitude=50, gpdpp=30,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=24.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=105.0, return_flow_gpm=2.0,
        tm_on_temp_f=112.0, tm_off_temp_f=120.0,
        tm_off_time_hr=0.5, tm_safety_factor=1.2,
    ),
    dict(
        label="PL: 300-unit MF, 8 GPM recirc, 8F drop",
        building_type="multi_family", magnitude=300, gpdpp=25,
        supply_t_f=125.0, storage_t_f=150.0, inlet_t_f=47.0, design_oat_f=47.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=117.0, return_flow_gpm=8.0,
        tm_on_temp_f=120.0, tm_off_temp_f=125.0,
        tm_off_time_hr=0.5, tm_safety_factor=1.3,
    ),
    # ----------------------------------------------------------------
    # Parallel loop + load shift with various load_shift_percent values
    # ----------------------------------------------------------------
    dict(
        label="PL: 100-unit MF, LS 5hr shed 16-20, 3hr LU, ls_pct=1.00",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=110.0, return_flow_gpm=3.0,
        tm_on_temp_f=115.0, tm_off_temp_f=120.0,
        tm_off_time_hr=0.5, tm_safety_factor=1.2,
        load_shift=True, shed_hours=list(range(16, 21)), lu_hours=3,
        lu_on_fract=0.2, shed_on_fract=0.8, load_shift_percent=1.0,
    ),
    dict(
        label="PL: 100-unit MF, LS 5hr shed 16-20, 3hr LU, ls_pct=0.95",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=110.0, return_flow_gpm=3.0,
        tm_on_temp_f=115.0, tm_off_temp_f=120.0,
        tm_off_time_hr=0.5, tm_safety_factor=1.2,
        load_shift=True, shed_hours=list(range(16, 21)), lu_hours=3,
        lu_on_fract=0.2, shed_on_fract=0.8, load_shift_percent=0.95,
    ),
    dict(
        label="PL: 100-unit MF, LS 5hr shed 16-20, 3hr LU, ls_pct=0.75",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=110.0, return_flow_gpm=3.0,
        tm_on_temp_f=115.0, tm_off_temp_f=120.0,
        tm_off_time_hr=0.5, tm_safety_factor=1.2,
        load_shift=True, shed_hours=list(range(16, 21)), lu_hours=3,
        lu_on_fract=0.2, shed_on_fract=0.8, load_shift_percent=0.75,
    ),
    dict(
        label="PL: 200-unit MF, 5GPM, LS 8hr shed 7-14, 3hr LU, ls_pct=0.95",
        building_type="multi_family", magnitude=200, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=110.0, return_flow_gpm=5.0,
        tm_on_temp_f=115.0, tm_off_temp_f=120.0,
        tm_off_time_hr=0.5, tm_safety_factor=1.5,
        load_shift=True, shed_hours=list(range(7, 15)), lu_hours=3,
        lu_on_fract=0.2, shed_on_fract=0.8, load_shift_percent=0.95,
    ),
    dict(
        label="PL: 200-unit MF, 5GPM, LS 8hr shed 7-14, 3hr LU, ls_pct=0.75",
        building_type="multi_family", magnitude=200, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=110.0, return_flow_gpm=5.0,
        tm_on_temp_f=115.0, tm_off_temp_f=120.0,
        tm_off_time_hr=0.5, tm_safety_factor=1.5,
        load_shift=True, shed_hours=list(range(7, 15)), lu_hours=3,
        lu_on_fract=0.2, shed_on_fract=0.8, load_shift_percent=0.75,
    ),
]


# ---------------------------------------------------------------------------
# Single Pass RTP scenarios
# ---------------------------------------------------------------------------
# Extra fields beyond the base scenario dict:
#   return_temp_f   : recirc loop return temperature [°F]
#   return_flow_gpm : recirc loop flow rate [GPM]

SPRTP_SCENARIOS = [
    dict(
        label="SPRTP: 100-unit MF, 3 GPM recirc, 10F drop, 16hr run",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=110.0, return_flow_gpm=3.0,
        load_shift=False, shed_hours=[], lu_hours=0,
        lu_on_fract=None, shed_on_fract=None,
    ),
    dict(
        label="SPRTP: 200-unit MF, 5 GPM recirc, 10F drop, 16hr run",
        building_type="multi_family", magnitude=200, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=110.0, return_flow_gpm=5.0,
        load_shift=False, shed_hours=[], lu_hours=0,
        lu_on_fract=None, shed_on_fract=None,
    ),
    dict(
        label="SPRTP: 50-unit MF, 2 GPM recirc, 15F drop, 24hr run",
        building_type="multi_family", magnitude=50, gpdpp=30,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=24.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=105.0, return_flow_gpm=2.0,
        load_shift=False, shed_hours=[], lu_hours=0,
        lu_on_fract=None, shed_on_fract=None,
    ),
    dict(
        label="SPRTP: 300-unit MF, 8 GPM recirc, 8F drop",
        building_type="multi_family", magnitude=300, gpdpp=25,
        supply_t_f=125.0, storage_t_f=150.0, inlet_t_f=47.0, design_oat_f=47.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=117.0, return_flow_gpm=8.0,
        load_shift=False, shed_hours=[], lu_hours=0,
        lu_on_fract=None, shed_on_fract=None,
    ),
    # ----------------------------------------------------------------
    # Load shift scenarios
    # ----------------------------------------------------------------
    dict(
        label="SPRTP: 100-unit MF, 3 GPM, LS 5hr shed 16-20, 3hr LU",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=110.0, return_flow_gpm=3.0,
        load_shift=True, shed_hours=list(range(16, 21)), lu_hours=3,
        lu_on_fract=0.2, shed_on_fract=0.8,
    ),
    dict(
        label="SPRTP: 200-unit MF, 5 GPM, LS 8hr shed 7-14, 3hr LU",
        building_type="multi_family", magnitude=200, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=110.0, return_flow_gpm=5.0,
        load_shift=True, shed_hours=list(range(7, 15)), lu_hours=3,
        lu_on_fract=0.2, shed_on_fract=0.8,
    ),
]


# ---------------------------------------------------------------------------
# Swing Tank scenarios
# ---------------------------------------------------------------------------
# Extra fields beyond the base scenario dict:
#   return_temp_f    : recirc loop return temperature [°F]
#   return_flow_gpm  : recirc loop flow rate [GPM]
#   tm_safety_factor : TM capacity multiplier (must be > 1.0)

SWING_SCENARIOS = [
    dict(
        label="ST: 100-unit MF, 3 GPM recirc, 10F drop",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=110.0, return_flow_gpm=3.0,
        tm_safety_factor=1.2,
        load_shift=False, shed_hours=[], lu_hours=0,
        lu_on_fract=None, shed_on_fract=None,
    ),
    dict(
        label="ST: 200-unit MF, 5 GPM recirc, 10F drop",
        building_type="multi_family", magnitude=200, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=110.0, return_flow_gpm=5.0,
        tm_safety_factor=1.2,
        load_shift=False, shed_hours=[], lu_hours=0,
        lu_on_fract=None, shed_on_fract=None,
    ),
    dict(
        label="ST: 50-unit MF, 2 GPM recirc, 15F drop",
        building_type="multi_family", magnitude=50, gpdpp=30,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=24.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=105.0, return_flow_gpm=2.0,
        tm_safety_factor=1.2,
        load_shift=False, shed_hours=[], lu_hours=0,
        lu_on_fract=None, shed_on_fract=None,
    ),
    dict(
        label="ST: 100-unit MF, 3 GPM, LS 5hr shed 16-20, 3hr LU",
        building_type="multi_family", magnitude=100, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=110.0, return_flow_gpm=3.0,
        tm_safety_factor=1.2,
        load_shift=True, shed_hours=list(range(16, 21)), lu_hours=3,
        lu_on_fract=0.2, shed_on_fract=0.8,
    ),
    dict(
        label="ST: 200-unit MF, 5 GPM, LS 8hr shed 7-14, 3hr LU",
        building_type="multi_family", magnitude=200, gpdpp=25,
        supply_t_f=120.0, storage_t_f=150.0, inlet_t_f=50.0, design_oat_f=35.0,
        max_run_hr=16.0, defrost_factor=1.0,
        on_fract=0.4, off_fract=0.1,
        return_temp_f=110.0, return_flow_gpm=5.0,
        tm_safety_factor=1.2,
        load_shift=True, shed_hours=list(range(7, 15)), lu_hours=3,
        lu_on_fract=0.2, shed_on_fract=0.8,
    ),
]


# ---------------------------------------------------------------------------
# Original codebase sizing (runs in subprocess to avoid package name conflict)
# ---------------------------------------------------------------------------

ORIGINAL_SRC = r"C:\Users\nolan\Documents\EcosizerEngine\src"

ORIGINAL_SCRIPT = r"""
import sys, json
sys.path.insert(0, r"{src}")

from ecoengine.engine.BuildingCreator import createBuilding
from ecoengine.objects.SystemConfig import Primary

scenarios = json.loads('{scenarios_json_escaped}')

results = []
for sc in scenarios:
    try:
        building = createBuilding(
            incomingT_F=sc["inlet_t_f"],
            magnitudeStat=sc["magnitude"],
            supplyT_F=sc["supply_t_f"],
            buildingType=sc["building_type"],
            gpdpp=sc["gpdpp"],
            designOAT_F=sc["design_oat_f"],
        )

        supply_t = sc["supply_t_f"]
        storage_t = sc["storage_t_f"]
        if sc["load_shift"]:
            # Build 24-element 0/1 schedule (0 = shed, 1 = normal/loadup)
            ls_sched = [0 if h in sc["shed_hours"] else 1 for h in range(24)]
            lu_on_fract = sc["lu_on_fract"] if sc["lu_on_fract"] is not None else sc["on_fract"]
            off_fract   = sc["off_fract"]
            system = Primary(
                storageT_F=storage_t,
                defrostFactor=sc["defrost_factor"],
                percentUseable=1.0,
                compRuntime_hr=sc["max_run_hr"],
                onFract=sc["on_fract"],
                offFract=off_fract,
                onT=supply_t,
                offT=storage_t,
                building=building,
                outletLoadUpT=None,
                onFractLoadUp=lu_on_fract,
                offFractLoadUp=off_fract,   # must be <= offFract
                onLoadUpT=None,
                offLoadUpT=None,
                onFractShed=sc["shed_on_fract"],
                offFractShed=off_fract,     # must be >= offFract
                onShedT=None,
                offShedT=None,
                doLoadShift=True,
                loadShiftSchedule=ls_sched,
                loadUpHours=sc["lu_hours"] if sc["lu_hours"] > 0 else 1,
                loadShiftPercent=sc.get("load_shift_percent", 1),
            )
        else:
            system = Primary(
                storageT_F=storage_t,
                defrostFactor=sc["defrost_factor"],
                percentUseable=1.0,
                compRuntime_hr=sc["max_run_hr"],
                onFract=sc["on_fract"],
                offFract=sc["off_fract"],
                onT=supply_t,
                offT=storage_t,
                building=building,
                outletLoadUpT=None,
                onFractLoadUp=None,
                offFractLoadUp=None,
                onLoadUpT=None,
                offLoadUpT=None,
                onFractShed=None,
                offFractShed=None,
                onShedT=None,
                offShedT=None,
            )

        results.append({{
            "label": sc["label"],
            "orig_capacity_kbtuh": round(system.PCap_kBTUhr, 2),
            "orig_storage_storageT_gal": round(system.PVol_G_atStorageT, 2),
            "orig_error": None,
        }})
    except Exception as e:
        results.append({{
            "label": sc["label"],
            "orig_capacity_kbtuh": None,
            "orig_storage_storageT_gal": None,
            "orig_error": str(e),
        }})

print(json.dumps(results))
"""


def run_original_sizing(scenarios: list[dict]) -> list[dict]:
    """Run sizing against the original EcosizerEngine codebase via subprocess."""
    scenarios_json = json.dumps(scenarios)
    # Escape single quotes so the JSON string embeds safely inside single-quoted Python
    scenarios_json_escaped = scenarios_json.replace("'", "\\'")
    script = ORIGINAL_SCRIPT.format(
        src=ORIGINAL_SRC.replace("\\", "\\\\"),
        scenarios_json_escaped=scenarios_json_escaped,
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True,
    )
    # The original codebase prints a license banner to stdout before our JSON.
    # Find the line that starts with '[' (our JSON array).
    json_line = next((l for l in proc.stdout.splitlines() if l.strip().startswith("[")), None)
    if proc.returncode != 0 or not json_line:
        print("ERROR running original sizing script:")
        print(proc.stderr[-800:])
        return [{"label": sc["label"], "orig_capacity_kbtuh": None,
                 "orig_storage_storageT_gal": None, "orig_error": proc.stderr.strip()[-120:]}
                for sc in scenarios]
    return json.loads(json_line)


# ---------------------------------------------------------------------------
# New codebase sizing
# ---------------------------------------------------------------------------

def run_new_sizing(scenarios: list[dict]) -> list[dict]:
    """Run sizing against the new EcosizerEngine2 codebase."""
    from ecoengine.objects.building.Building import Building
    from ecoengine.objects.building.ClimateZone import ClimateZone
    from ecoengine.objects.dhwsystems.DHWSystem import DHWSystem, _load_shift_fract_total_vol
    from ecoengine.objects.components.heating.Controls import Controls

    results = []
    for sc in scenarios:
        try:
            zone = ClimateZone.from_design_conditions(
                design_oat_f=sc["design_oat_f"],
                design_inlet_water_temp_f=sc["inlet_t_f"],
            )
            building = Building.from_building_type(
                building_type=sc["building_type"],
                magnitude=sc["magnitude"],
                climate_zone=zone,
                gpdpp=sc["gpdpp"] if sc["gpdpp"] else None,
            )

            if sc["load_shift"]:
                # Build control_schedule and control_map
                schedule = ["normal"] * 24
                for h in sc["shed_hours"]:
                    schedule[h] = "shed"
                first_shed = sc["shed_hours"][0]
                for i in range(sc["lu_hours"]):
                    schedule[first_shed - 1 - i] = "loadUp"

                cmap = {
                    "normal": Controls(
                        on_sensor_fract=sc["on_fract"],
                        on_trigger_t_f=sc["supply_t_f"],
                        off_sensor_fract=sc["off_fract"],
                        off_trigger_t_f=sc["storage_t_f"],
                        outlet_temp_f=sc["storage_t_f"],
                    ),
                    "shed": Controls(
                        on_sensor_fract=sc["shed_on_fract"],
                        on_trigger_t_f=sc["supply_t_f"],
                        off_sensor_fract=sc["off_fract"],
                        off_trigger_t_f=sc["storage_t_f"],
                        outlet_temp_f=sc["storage_t_f"],
                    ),
                }
                if sc["lu_hours"] > 0 and sc["lu_on_fract"] is not None:
                    cmap["loadUp"] = Controls(
                        on_sensor_fract=sc["lu_on_fract"],
                        on_trigger_t_f=sc["supply_t_f"],
                        off_sensor_fract=sc["off_fract"],
                        off_trigger_t_f=sc["storage_t_f"],
                        outlet_temp_f=sc["storage_t_f"],
                    )

                ls_fract = _load_shift_fract_total_vol(sc.get("load_shift_percent", 1.0))
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    system = DHWSystem.from_size(
                        building=building,
                        supply_temp_f=sc["supply_t_f"],
                        storage_temp_f=sc["storage_t_f"],
                        max_daily_run_hr=sc["max_run_hr"],
                        defrost_factor=sc["defrost_factor"],
                        control_schedule=schedule,
                        control_map=cmap,
                        load_shift_fract_total_vol=ls_fract,
                    )
            else:
                cmap = {
                    "normal": Controls(
                        on_sensor_fract=sc["on_fract"],
                        on_trigger_t_f=sc["supply_t_f"],
                        off_sensor_fract=sc["off_fract"],
                        off_trigger_t_f=sc["storage_t_f"],
                        outlet_temp_f=sc["storage_t_f"],
                    )
                }
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    system = DHWSystem.from_size(
                        building=building,
                        supply_temp_f=sc["supply_t_f"],
                        storage_temp_f=sc["storage_t_f"],
                        max_daily_run_hr=sc["max_run_hr"],
                        defrost_factor=sc["defrost_factor"],
                        control_map=cmap,
                    )

            results.append({
                "label": sc["label"],
                "new_capacity_kbtuh": round(system._minimum_capacity_kbtuh, 2),
                "new_storage_storageT_gal": round(system._minimum_storage_storageT_gal, 2),
                "new_error": None,
            })
        except Exception as e:
            results.append({
                "label": sc["label"],
                "new_capacity_kbtuh": None,
                "new_storage_storageT_gal": None,
                "new_error": str(e),
            })
    return results


# ---------------------------------------------------------------------------
# Parallel Loop sizing — original codebase
# ---------------------------------------------------------------------------

ORIGINAL_PARALLEL_SCRIPT = r"""
import sys, json
sys.path.insert(0, r"{src}")

from ecoengine.engine.BuildingCreator import createBuilding
from ecoengine.objects.systems.ParallelLoopTank import ParallelLoopTank

scenarios = json.loads('{scenarios_json_escaped}')

results = []
for sc in scenarios:
    try:
        building = createBuilding(
            incomingT_F=sc["inlet_t_f"],
            magnitudeStat=sc["magnitude"],
            supplyT_F=sc["supply_t_f"],
            buildingType=sc["building_type"],
            gpdpp=sc["gpdpp"],
            designOAT_F=sc["design_oat_f"],
        )
        # recirc_loss in BTU/hr — set directly on the building object
        building.recirc_loss = (
            sc["return_flow_gpm"]
            * (sc["supply_t_f"] - sc["return_temp_f"])
            * 8.353535
            * 60.0
        )

        supply_t  = sc["supply_t_f"]
        storage_t = sc["storage_t_f"]
        if sc.get("load_shift"):
            ls_sched   = [0 if h in sc["shed_hours"] else 1 for h in range(24)]
            lu_on_fract = sc["lu_on_fract"] if sc["lu_on_fract"] is not None else sc["on_fract"]
            system = ParallelLoopTank(
                safetyTM        = sc["tm_safety_factor"],
                setpointTM_F    = sc["tm_off_temp_f"],
                TMonTemp_F      = sc["tm_on_temp_f"],
                offTime_hr      = sc["tm_off_time_hr"],
                storageT_F      = storage_t,
                defrostFactor   = sc["defrost_factor"],
                percentUseable  = 1.0,
                compRuntime_hr  = sc["max_run_hr"],
                onFract         = sc["on_fract"],
                offFract        = sc["off_fract"],
                onT             = supply_t,
                offT            = storage_t,
                building        = building,
                onFractLoadUp   = lu_on_fract,
                offFractLoadUp  = sc["off_fract"],
                onFractShed     = sc["shed_on_fract"],
                offFractShed    = sc["off_fract"],
                doLoadShift     = True,
                loadShiftSchedule = ls_sched,
                loadUpHours     = sc["lu_hours"] if sc["lu_hours"] > 0 else 1,
                loadShiftPercent= sc.get("load_shift_percent", 1),
            )
        else:
            system = ParallelLoopTank(
                safetyTM        = sc["tm_safety_factor"],
                setpointTM_F    = sc["tm_off_temp_f"],
                TMonTemp_F      = sc["tm_on_temp_f"],
                offTime_hr      = sc["tm_off_time_hr"],
                storageT_F      = storage_t,
                defrostFactor   = sc["defrost_factor"],
                percentUseable  = 1.0,
                compRuntime_hr  = sc["max_run_hr"],
                onFract         = sc["on_fract"],
                offFract        = sc["off_fract"],
                onT             = supply_t,
                offT            = storage_t,
                building        = building,
            )

        results.append({{
            "label":                    sc["label"],
            "orig_capacity_kbtuh":      round(system.PCap_kBTUhr,      2),
            "orig_storage_storageT_gal":round(system.PVol_G_atStorageT,2),
            "orig_tm_volume_gal":       round(system.TMVol_G,           2),
            "orig_tm_capacity_kbtuh":   round(system.TMCap_kBTUhr,      2),
            "orig_error":               None,
        }})
    except Exception as e:
        results.append({{
            "label":                    sc["label"],
            "orig_capacity_kbtuh":      None,
            "orig_storage_storageT_gal":None,
            "orig_tm_volume_gal":       None,
            "orig_tm_capacity_kbtuh":   None,
            "orig_error":               str(e),
        }})

print(json.dumps(results))
"""


def run_original_parallel_sizing(scenarios: list[dict]) -> list[dict]:
    """Run ParallelLoopTank sizing against the original EcosizerEngine via subprocess."""
    scenarios_json = json.dumps(scenarios)
    scenarios_json_escaped = scenarios_json.replace("'", "\\'")
    script = ORIGINAL_PARALLEL_SCRIPT.format(
        src=ORIGINAL_SRC.replace("\\", "\\\\"),
        scenarios_json_escaped=scenarios_json_escaped,
    )
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    json_line = next((l for l in proc.stdout.splitlines() if l.strip().startswith("[")), None)
    if proc.returncode != 0 or not json_line:
        print("ERROR running original parallel sizing script:")
        print(proc.stderr[-800:])
        return [{"label": sc["label"], "orig_capacity_kbtuh": None,
                 "orig_storage_storageT_gal": None, "orig_tm_volume_gal": None,
                 "orig_tm_capacity_kbtuh": None, "orig_error": proc.stderr.strip()[-120:]}
                for sc in scenarios]
    return json.loads(json_line)


# ---------------------------------------------------------------------------
# Parallel Loop sizing — new codebase
# ---------------------------------------------------------------------------

def run_new_parallel_sizing(scenarios: list[dict]) -> list[dict]:
    """Run ParallelLoopSystem sizing against the new EcosizerEngine2 codebase."""
    from ecoengine.objects.building.Building import Building
    from ecoengine.objects.building.ClimateZone import ClimateZone
    from ecoengine.objects.components.heating.Controls import Controls
    from ecoengine.objects.dhwsystems.DHWSystem import _load_shift_fract_total_vol
    from ecoengine.objects.dhwsystems.recirc_systems.ParallelLoopSystem import ParallelLoopSystem

    results = []
    for sc in scenarios:
        try:
            zone = ClimateZone.from_design_conditions(
                design_oat_f=sc["design_oat_f"],
                design_inlet_water_temp_f=sc["inlet_t_f"],
            )
            building = Building.from_building_type(
                building_type=sc["building_type"],
                magnitude=sc["magnitude"],
                climate_zone=zone,
                gpdpp=sc["gpdpp"] if sc["gpdpp"] else None,
            )

            if sc.get("load_shift"):
                schedule = ["normal"] * 24
                for h in sc["shed_hours"]:
                    schedule[h] = "shed"
                first_shed = sc["shed_hours"][0]
                for i in range(sc["lu_hours"]):
                    schedule[first_shed - 1 - i] = "loadUp"
                lu_on_fract = sc["lu_on_fract"] if sc["lu_on_fract"] is not None else sc["on_fract"]
                cmap = {
                    "normal": Controls(
                        on_sensor_fract=sc["on_fract"],
                        on_trigger_t_f=sc["supply_t_f"],
                        off_sensor_fract=sc["off_fract"],
                        off_trigger_t_f=sc["storage_t_f"],
                        outlet_temp_f=sc["storage_t_f"],
                    ),
                    "shed": Controls(
                        on_sensor_fract=sc["shed_on_fract"],
                        on_trigger_t_f=sc["supply_t_f"],
                        off_sensor_fract=sc["off_fract"],
                        off_trigger_t_f=sc["storage_t_f"],
                        outlet_temp_f=sc["storage_t_f"],
                    ),
                    "loadUp": Controls(
                        on_sensor_fract=lu_on_fract,
                        on_trigger_t_f=sc["supply_t_f"],
                        off_sensor_fract=sc["off_fract"],
                        off_trigger_t_f=sc["storage_t_f"],
                        outlet_temp_f=sc["storage_t_f"],
                    ),
                }
                ls_fract = _load_shift_fract_total_vol(sc.get("load_shift_percent", 1.0))
            else:
                schedule = None
                cmap = {
                    "normal": Controls(
                        on_sensor_fract=sc["on_fract"],
                        on_trigger_t_f=sc["supply_t_f"],
                        off_sensor_fract=sc["off_fract"],
                        off_trigger_t_f=sc["storage_t_f"],
                        outlet_temp_f=sc["storage_t_f"],
                    )
                }
                ls_fract = 1.0

            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                system = ParallelLoopSystem.from_size(
                    building        = building,
                    supply_temp_f   = sc["supply_t_f"],
                    storage_temp_f  = sc["storage_t_f"],
                    return_temp_f   = sc["return_temp_f"],
                    return_flow_gpm = sc["return_flow_gpm"],
                    tm_on_temp_f    = sc["tm_on_temp_f"],
                    tm_off_temp_f   = sc["tm_off_temp_f"],
                    tm_off_time_hr  = sc["tm_off_time_hr"],
                    tm_safety_factor= sc["tm_safety_factor"],
                    max_daily_run_hr= sc["max_run_hr"],
                    defrost_factor  = sc["defrost_factor"],
                    control_schedule= schedule,
                    control_map     = cmap,
                    load_shift_fract_total_vol = ls_fract,
                )

            results.append({
                "label":                    sc["label"],
                "new_capacity_kbtuh":       round(system._minimum_capacity_kbtuh,      2),
                "new_storage_storageT_gal": round(system._minimum_storage_storageT_gal,2),
                "new_tm_volume_gal":        round(system._minimum_tm_volume_gal,        2),
                "new_tm_capacity_kbtuh":    round(system._minimum_tm_capacity_kbtuh,    2),
                "new_error":                None,
            })
        except Exception as e:
            results.append({
                "label":                    sc["label"],
                "new_capacity_kbtuh":       None,
                "new_storage_storageT_gal": None,
                "new_tm_volume_gal":        None,
                "new_tm_capacity_kbtuh":    None,
                "new_error":                str(e),
            })
    return results


# ---------------------------------------------------------------------------
# Swing Tank sizing — original codebase
# ---------------------------------------------------------------------------

ORIGINAL_SWING_SCRIPT = r"""
import sys, json
sys.path.insert(0, r"{src}")

from ecoengine.engine.BuildingCreator import createBuilding
from ecoengine.objects.systems.SwingTank import SwingTank

scenarios = json.loads('{scenarios_json_escaped}')

results = []
for sc in scenarios:
    try:
        building = createBuilding(
            incomingT_F=sc["inlet_t_f"],
            magnitudeStat=sc["magnitude"],
            supplyT_F=sc["supply_t_f"],
            buildingType=sc["building_type"],
            gpdpp=sc["gpdpp"],
            designOAT_F=sc["design_oat_f"],
        )
        building.recirc_loss = (
            sc["return_flow_gpm"]
            * (sc["supply_t_f"] - sc["return_temp_f"])
            * 8.353535
            * 60.0
        )

        supply_t  = sc["supply_t_f"]
        storage_t = sc["storage_t_f"]

        if sc.get("load_shift"):
            ls_sched    = [0 if h in sc["shed_hours"] else 1 for h in range(24)]
            lu_on_fract = sc["lu_on_fract"] if sc["lu_on_fract"] is not None else sc["on_fract"]
            system = SwingTank(
                safetyTM        = sc["tm_safety_factor"],
                storageT_F      = storage_t,
                defrostFactor   = sc["defrost_factor"],
                percentUseable  = 1.0,
                compRuntime_hr  = sc["max_run_hr"],
                onFract         = sc["on_fract"],
                offFract        = sc["off_fract"],
                onT             = supply_t,
                offT            = storage_t,
                building        = building,
                onFractLoadUp   = lu_on_fract,
                offFractLoadUp  = sc["off_fract"],
                onFractShed     = sc["shed_on_fract"],
                offFractShed    = sc["off_fract"],
                doLoadShift     = True,
                loadShiftSchedule = ls_sched,
                loadUpHours     = sc["lu_hours"] if sc["lu_hours"] > 0 else 1,
            )
        else:
            system = SwingTank(
                safetyTM        = sc["tm_safety_factor"],
                storageT_F      = storage_t,
                defrostFactor   = sc["defrost_factor"],
                percentUseable  = 1.0,
                compRuntime_hr  = sc["max_run_hr"],
                onFract         = sc["on_fract"],
                offFract        = sc["off_fract"],
                onT             = supply_t,
                offT            = storage_t,
                building        = building,
            )

        results.append({{
            "label":                    sc["label"],
            "orig_capacity_kbtuh":      round(system.PCap_kBTUhr,      2),
            "orig_storage_storageT_gal":round(system.PVol_G_atStorageT,2),
            "orig_tm_volume_gal":       round(system.TMVol_G,           2),
            "orig_tm_capacity_kbtuh":   round(system.TMCap_kBTUhr,      2),
            "orig_error":               None,
        }})
    except Exception as e:
        results.append({{
            "label":                    sc["label"],
            "orig_capacity_kbtuh":      None,
            "orig_storage_storageT_gal":None,
            "orig_tm_volume_gal":       None,
            "orig_tm_capacity_kbtuh":   None,
            "orig_error":               str(e),
        }})

print(json.dumps(results))
"""


def run_original_swing_sizing(scenarios: list[dict]) -> list[dict]:
    """Run SwingTank sizing against the original EcosizerEngine via subprocess."""
    scenarios_json = json.dumps(scenarios)
    scenarios_json_escaped = scenarios_json.replace("'", "\\'")
    script = ORIGINAL_SWING_SCRIPT.format(
        src=ORIGINAL_SRC.replace("\\", "\\\\"),
        scenarios_json_escaped=scenarios_json_escaped,
    )
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    json_line = next((l for l in proc.stdout.splitlines() if l.strip().startswith("[")), None)
    if proc.returncode != 0 or not json_line:
        print("ERROR running original swing sizing script:")
        print(proc.stderr[-800:])
        return [{"label": sc["label"], "orig_capacity_kbtuh": None,
                 "orig_storage_storageT_gal": None, "orig_tm_volume_gal": None,
                 "orig_tm_capacity_kbtuh": None, "orig_error": proc.stderr.strip()[-120:]}
                for sc in scenarios]
    return json.loads(json_line)


# ---------------------------------------------------------------------------
# Swing Tank sizing — new codebase
# ---------------------------------------------------------------------------

def run_new_swing_sizing(scenarios: list[dict]) -> list[dict]:
    """Run SwingSystem sizing against the new EcosizerEngine2 codebase."""
    from ecoengine.objects.building.Building import Building
    from ecoengine.objects.building.ClimateZone import ClimateZone
    from ecoengine.objects.components.heating.Controls import Controls
    from ecoengine.objects.dhwsystems.DHWSystem import _load_shift_fract_total_vol
    from ecoengine.objects.dhwsystems.recirc_systems.SwingSystem import SwingSystem

    results = []
    for sc in scenarios:
        try:
            zone = ClimateZone.from_design_conditions(
                design_oat_f=sc["design_oat_f"],
                design_inlet_water_temp_f=sc["inlet_t_f"],
            )
            building = Building.from_building_type(
                building_type=sc["building_type"],
                magnitude=sc["magnitude"],
                climate_zone=zone,
                gpdpp=sc["gpdpp"] if sc["gpdpp"] else None,
            )

            if sc.get("load_shift"):
                schedule = ["normal"] * 24
                for h in sc["shed_hours"]:
                    schedule[h] = "shed"
                first_shed = sc["shed_hours"][0]
                for i in range(sc["lu_hours"]):
                    schedule[first_shed - 1 - i] = "loadUp"
                lu_on_fract = sc["lu_on_fract"] if sc["lu_on_fract"] is not None else sc["on_fract"]
                cmap = {
                    "normal": Controls(
                        on_sensor_fract=sc["on_fract"],
                        on_trigger_t_f=sc["supply_t_f"],
                        off_sensor_fract=sc["off_fract"],
                        off_trigger_t_f=sc["storage_t_f"],
                        outlet_temp_f=sc["storage_t_f"],
                    ),
                    "shed": Controls(
                        on_sensor_fract=sc["shed_on_fract"],
                        on_trigger_t_f=sc["supply_t_f"],
                        off_sensor_fract=sc["off_fract"],
                        off_trigger_t_f=sc["storage_t_f"],
                        outlet_temp_f=sc["storage_t_f"],
                    ),
                    "loadUp": Controls(
                        on_sensor_fract=lu_on_fract,
                        on_trigger_t_f=sc["supply_t_f"],
                        off_sensor_fract=sc["off_fract"],
                        off_trigger_t_f=sc["storage_t_f"],
                        outlet_temp_f=sc["storage_t_f"],
                    ),
                }
            else:
                schedule = None
                cmap = {
                    "normal": Controls(
                        on_sensor_fract=sc["on_fract"],
                        on_trigger_t_f=sc["supply_t_f"],
                        off_sensor_fract=sc["off_fract"],
                        off_trigger_t_f=sc["storage_t_f"],
                        outlet_temp_f=sc["storage_t_f"],
                    )
                }

            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                system = SwingSystem.from_size(
                    building        = building,
                    supply_temp_f   = sc["supply_t_f"],
                    storage_temp_f  = sc["storage_t_f"],
                    return_temp_f   = sc["return_temp_f"],
                    return_flow_gpm = sc["return_flow_gpm"],
                    tm_safety_factor= sc["tm_safety_factor"],
                    max_daily_run_hr= sc["max_run_hr"],
                    defrost_factor  = sc["defrost_factor"],
                    control_schedule= schedule,
                    control_map     = cmap,
                )

            results.append({
                "label":                    sc["label"],
                "new_capacity_kbtuh":       round(system._minimum_capacity_kbtuh,       2),
                "new_storage_storageT_gal": round(system._minimum_storage_storageT_gal, 2),
                "new_tm_volume_gal":        round(system._minimum_tm_volume_gal,         2),
                "new_tm_capacity_kbtuh":    round(system._minimum_tm_capacity_kbtuh,     2),
                "new_error":                None,
            })
        except Exception as e:
            results.append({
                "label":                    sc["label"],
                "new_capacity_kbtuh":       None,
                "new_storage_storageT_gal": None,
                "new_tm_volume_gal":        None,
                "new_tm_capacity_kbtuh":    None,
                "new_error":                str(e),
            })
    return results


# ---------------------------------------------------------------------------
# Single Pass RTP sizing — original codebase
# ---------------------------------------------------------------------------

ORIGINAL_SPRTP_SCRIPT = r"""
import sys, json
sys.path.insert(0, r"{src}")

from ecoengine.engine.BuildingCreator import createBuilding
from ecoengine.objects.systems.SPRTP import SPRTP

scenarios = json.loads('{scenarios_json_escaped}')

results = []
for sc in scenarios:
    try:
        building = createBuilding(
            incomingT_F=sc["inlet_t_f"],
            magnitudeStat=sc["magnitude"],
            supplyT_F=sc["supply_t_f"],
            buildingType=sc["building_type"],
            gpdpp=sc["gpdpp"],
            designOAT_F=sc["design_oat_f"],
            returnT_F=sc["return_temp_f"],
            flowRate=sc["return_flow_gpm"],
        )

        supply_t  = sc["supply_t_f"]
        storage_t = sc["storage_t_f"]

        if sc.get("load_shift"):
            ls_sched    = [0 if h in sc["shed_hours"] else 1 for h in range(24)]
            lu_on_fract = sc["lu_on_fract"] if sc["lu_on_fract"] is not None else sc["on_fract"]
            system = SPRTP(
                storageT_F      = storage_t,
                defrostFactor   = sc["defrost_factor"],
                percentUseable  = 1.0,
                compRuntime_hr  = sc["max_run_hr"],
                onFract         = sc["on_fract"],
                offFract        = sc["off_fract"],
                onT             = supply_t,
                offT            = storage_t,
                building        = building,
                onFractLoadUp   = lu_on_fract,
                offFractLoadUp  = sc["off_fract"],
                onFractShed     = sc["shed_on_fract"],
                offFractShed    = sc["off_fract"],
                doLoadShift     = True,
                loadShiftSchedule = ls_sched,
                loadUpHours     = sc["lu_hours"] if sc["lu_hours"] > 0 else 1,
                loadShiftPercent= sc.get("load_shift_percent", 1),
            )
        else:
            system = SPRTP(
                storageT_F      = storage_t,
                defrostFactor   = sc["defrost_factor"],
                percentUseable  = 1.0,
                compRuntime_hr  = sc["max_run_hr"],
                onFract         = sc["on_fract"],
                offFract        = sc["off_fract"],
                onT             = supply_t,
                offT            = storage_t,
                building        = building,
            )

        sizing = system.getSizingResults()
        results.append({{
            "label":                    sc["label"],
            "orig_capacity_kbtuh":      round(sizing[1],                               2),
            "orig_storage_storageT_gal":round(sizing[0],                               2),
            "orig_recirc_cap_kbtuh":    round(sizing[2], 2) if sizing[2] is not None else None,
            "orig_error":               None,
        }})
    except Exception as e:
        results.append({{
            "label":                    sc["label"],
            "orig_capacity_kbtuh":      None,
            "orig_storage_storageT_gal":None,
            "orig_recirc_cap_kbtuh":    None,
            "orig_error":               str(e),
        }})

print(json.dumps(results))
"""


def run_original_sprtp_sizing(scenarios: list[dict]) -> list[dict]:
    """Run SPRTP sizing against the original EcosizerEngine via subprocess."""
    scenarios_json = json.dumps(scenarios)
    scenarios_json_escaped = scenarios_json.replace("'", "\\'")
    script = ORIGINAL_SPRTP_SCRIPT.format(
        src=ORIGINAL_SRC.replace("\\", "\\\\"),
        scenarios_json_escaped=scenarios_json_escaped,
    )
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    json_line = next((l for l in proc.stdout.splitlines() if l.strip().startswith("[")), None)
    if proc.returncode != 0 or not json_line:
        print("ERROR running original SPRTP sizing script:")
        print(proc.stderr[-800:])
        return [{"label": sc["label"], "orig_capacity_kbtuh": None,
                 "orig_storage_storageT_gal": None, "orig_recirc_cap_kbtuh": None,
                 "orig_error": proc.stderr.strip()[-120:]}
                for sc in scenarios]
    return json.loads(json_line)


# ---------------------------------------------------------------------------
# Single Pass RTP sizing — new codebase
# ---------------------------------------------------------------------------

def run_new_sprtp_sizing(scenarios: list[dict]) -> list[dict]:
    """Run SinglePassRTPSystem sizing against the new EcosizerEngine2 codebase."""
    from ecoengine.objects.building.Building import Building
    from ecoengine.objects.building.ClimateZone import ClimateZone
    from ecoengine.objects.components.heating.Controls import Controls
    from ecoengine.objects.dhwsystems.DHWSystem import _load_shift_fract_total_vol
    from ecoengine.objects.dhwsystems.rtp_systems.SinglePassRTPSystem import SinglePassRTPSystem

    results = []
    for sc in scenarios:
        try:
            zone = ClimateZone.from_design_conditions(
                design_oat_f=sc["design_oat_f"],
                design_inlet_water_temp_f=sc["inlet_t_f"],
            )
            building = Building.from_building_type(
                building_type=sc["building_type"],
                magnitude=sc["magnitude"],
                climate_zone=zone,
                gpdpp=sc["gpdpp"] if sc["gpdpp"] else None,
            )

            if sc.get("load_shift"):
                schedule = ["normal"] * 24
                for h in sc["shed_hours"]:
                    schedule[h] = "shed"
                first_shed = sc["shed_hours"][0]
                for i in range(sc["lu_hours"]):
                    schedule[first_shed - 1 - i] = "loadUp"
                lu_on_fract = sc["lu_on_fract"] if sc["lu_on_fract"] is not None else sc["on_fract"]
                cmap = {
                    "normal": Controls(
                        on_sensor_fract=sc["on_fract"],
                        on_trigger_t_f=sc["supply_t_f"],
                        off_sensor_fract=sc["off_fract"],
                        off_trigger_t_f=sc["storage_t_f"],
                        outlet_temp_f=sc["storage_t_f"],
                    ),
                    "shed": Controls(
                        on_sensor_fract=sc["shed_on_fract"],
                        on_trigger_t_f=sc["supply_t_f"],
                        off_sensor_fract=sc["off_fract"],
                        off_trigger_t_f=sc["storage_t_f"],
                        outlet_temp_f=sc["storage_t_f"],
                    ),
                    "loadUp": Controls(
                        on_sensor_fract=lu_on_fract,
                        on_trigger_t_f=sc["supply_t_f"],
                        off_sensor_fract=sc["off_fract"],
                        off_trigger_t_f=sc["storage_t_f"],
                        outlet_temp_f=sc["storage_t_f"],
                    ),
                }
                ls_fract = _load_shift_fract_total_vol(sc.get("load_shift_percent", 1.0))
            else:
                schedule = None
                cmap = {
                    "normal": Controls(
                        on_sensor_fract=sc["on_fract"],
                        on_trigger_t_f=sc["supply_t_f"],
                        off_sensor_fract=sc["off_fract"],
                        off_trigger_t_f=sc["storage_t_f"],
                        outlet_temp_f=sc["storage_t_f"],
                    )
                }
                ls_fract = 1.0

            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                system = SinglePassRTPSystem.from_size(
                    building        = building,
                    supply_temp_f   = sc["supply_t_f"],
                    storage_temp_f  = sc["storage_t_f"],
                    return_temp_f   = sc["return_temp_f"],
                    return_flow_gpm = sc["return_flow_gpm"],
                    max_daily_run_hr= sc["max_run_hr"],
                    defrost_factor  = sc["defrost_factor"],
                    control_schedule= schedule,
                    control_map     = cmap,
                    load_shift_fract_total_vol = ls_fract,
                )

            results.append({
                "label":                    sc["label"],
                "new_capacity_kbtuh":       round(system._minimum_capacity_kbtuh,      2),
                "new_storage_storageT_gal": round(system._minimum_storage_storageT_gal,2),
                "new_recirc_cap_kbtuh":     round(system._recirc_capacity_kbtuh,        2),
                "new_error":                None,
            })
        except Exception as e:
            results.append({
                "label":                    sc["label"],
                "new_capacity_kbtuh":       None,
                "new_storage_storageT_gal": None,
                "new_recirc_cap_kbtuh":     None,
                "new_error":                str(e),
            })
    return results


# ---------------------------------------------------------------------------
# Swing Tank ER sizing — original codebase
# ---------------------------------------------------------------------------
# Strategy: size a SwingTank normally, halve its primary capacity, then pass
# those components to SwingTankER to size the ER element.

ORIGINAL_SWING_ER_SCRIPT = r"""
import sys, json
sys.path.insert(0, r"{src}")

from ecoengine.engine.BuildingCreator import createBuilding
from ecoengine.objects.systems.SwingTankER import SwingTankER

# Each scenario already carries pre-computed sizing from the new codebase:
#   sc["shared_half_cap_kbtuh"]  — halved primary capacity to use
#   sc["shared_storage_gal"]     — primary storage volume to use
#   sc["shared_tm_volume_gal"]   — swing tank volume to use
#   sc["shared_base_tm_cap_kbtuh"] — base TM capacity (before ER) to use

scenarios = json.loads('{scenarios_json_escaped}')

results = []
for sc in scenarios:
    try:
        building = createBuilding(
            incomingT_F=sc["inlet_t_f"],
            magnitudeStat=sc["magnitude"],
            supplyT_F=sc["supply_t_f"],
            buildingType=sc["building_type"],
            gpdpp=sc["gpdpp"],
            designOAT_F=sc["design_oat_f"],
        )
        building.recirc_loss = (
            sc["return_flow_gpm"]
            * (sc["supply_t_f"] - sc["return_temp_f"])
            * 8.353535
            * 60.0
        )

        supply_t  = sc["supply_t_f"]
        storage_t = sc["storage_t_f"]

        half_cap    = sc["shared_half_cap_kbtuh"]
        prim_vol    = sc["shared_storage_gal"]
        tm_vol      = sc["shared_tm_volume_gal"]
        base_tm_cap = sc["shared_base_tm_cap_kbtuh"]

        er_system = SwingTankER(
            safetyTM            = sc["tm_safety_factor"],
            storageT_F          = storage_t,
            defrostFactor       = sc["defrost_factor"],
            percentUseable      = 1.0,
            compRuntime_hr      = sc["max_run_hr"],
            onFract             = sc["on_fract"],
            offFract            = sc["off_fract"],
            onT                 = supply_t,
            offT                = storage_t,
            building            = building,
            PVol_G_atStorageT   = prim_vol,
            PCap_kBTUhr         = half_cap,
            TMVol_G             = tm_vol,
            TMCap_kBTUhr        = base_tm_cap,
        )

        results.append({{
            "label":                  sc["label"],
            "orig_total_tm_cap_kbtuh":round(er_system.TMCap_kBTUhr,              2),
            "orig_er_addition_kbtuh": round(er_system.getERCapacityDif(kW=False), 2),
            "orig_error":             None,
        }})
    except Exception as e:
        results.append({{
            "label":                  sc["label"],
            "orig_total_tm_cap_kbtuh":None,
            "orig_er_addition_kbtuh": None,
            "orig_error":             str(e),
        }})

print(json.dumps(results))
"""


def run_original_swing_er_sizing(scenarios: list[dict]) -> list[dict]:
    """Run SwingTankER sizing against the original EcosizerEngine via subprocess."""
    scenarios_json = json.dumps(scenarios)
    scenarios_json_escaped = scenarios_json.replace("'", "\\'")
    script = ORIGINAL_SWING_ER_SCRIPT.format(
        src=ORIGINAL_SRC.replace("\\", "\\\\"),
        scenarios_json_escaped=scenarios_json_escaped,
    )
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    json_line = next((l for l in proc.stdout.splitlines() if l.strip().startswith("[")), None)
    if proc.returncode != 0 or not json_line:
        print("ERROR running original swing ER sizing script:")
        print(proc.stderr[-800:])
        return [{"label": sc["label"], "orig_total_tm_cap_kbtuh": None,
                 "orig_er_addition_kbtuh": None, "orig_error": proc.stderr.strip()[-120:]}
                for sc in scenarios]
    return json.loads(json_line)


# ---------------------------------------------------------------------------
# Swing Tank ER sizing — new codebase
# ---------------------------------------------------------------------------

def run_new_swing_er_sizing(scenarios: list[dict]) -> list[dict]:
    """
    Size SwingSystem (new), halve primary capacity, then use
    SwingERTrdOffSystem.from_components() to size the ER element.
    """
    from ecoengine.objects.building.Building import Building
    from ecoengine.objects.building.ClimateZone import ClimateZone
    from ecoengine.objects.components.heating.Controls import Controls
    from ecoengine.objects.components.heating.WaterHeater import WaterHeater
    from ecoengine.objects.dhwsystems.recirc_systems.SwingSystem import SwingSystem
    from ecoengine.objects.dhwsystems.recirc_systems.SwingERTrdOffSystem import SwingERTrdOffSystem

    results = []
    for sc in scenarios:
        try:
            zone = ClimateZone.from_design_conditions(
                design_oat_f=sc["design_oat_f"],
                design_inlet_water_temp_f=sc["inlet_t_f"],
            )
            building = Building.from_building_type(
                building_type=sc["building_type"],
                magnitude=sc["magnitude"],
                climate_zone=zone,
                gpdpp=sc["gpdpp"] if sc["gpdpp"] else None,
            )

            cmap = {
                "normal": Controls(
                    on_sensor_fract=sc["on_fract"],
                    on_trigger_t_f=sc["supply_t_f"],
                    off_sensor_fract=sc["off_fract"],
                    off_trigger_t_f=sc["storage_t_f"],
                    outlet_temp_f=sc["storage_t_f"],
                )
            }

            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                # Step 1: size SwingSystem normally
                base_swing = SwingSystem.from_size(
                    building        = building,
                    supply_temp_f   = sc["supply_t_f"],
                    storage_temp_f  = sc["storage_t_f"],
                    return_temp_f   = sc["return_temp_f"],
                    return_flow_gpm = sc["return_flow_gpm"],
                    tm_safety_factor= sc["tm_safety_factor"],
                    max_daily_run_hr= sc["max_run_hr"],
                    defrost_factor  = sc["defrost_factor"],
                    control_map     = cmap,
                )

            half_cap    = base_swing._minimum_capacity_kbtuh / 2.0
            base_tm_cap = base_swing._minimum_tm_capacity_kbtuh

            # Step 2: rebuild water heaters list with halved capacity
            orig_wh = base_swing.water_heaters[0]
            halved_wh = WaterHeater.from_nominal_capacity(
                nominal_capacity_kbtuh = half_cap,
                control_schedule       = orig_wh.control_schedule,
                control_map            = orig_wh.control_map,
            )

            # Step 3: size ER element using from_components
            er_system = SwingERTrdOffSystem.from_components(
                water_heaters             = [halved_wh],
                storage_tank              = base_swing.storage_tank,
                tm_storage_tank           = base_swing.tm_storage_tank,
                initial_tm_capacity_kbtuh = base_tm_cap,
                building                  = building,
                supply_temp_f             = sc["supply_t_f"],
                storage_temp_f            = sc["storage_t_f"],
                return_temp_f             = sc["return_temp_f"],
                return_flow_gpm           = sc["return_flow_gpm"],
            )

            results.append({
                "label":                       sc["label"],
                "shared_half_cap_kbtuh":       round(half_cap,                                    2),
                "shared_storage_gal":          round(base_swing._minimum_storage_storageT_gal,    2),
                "shared_tm_volume_gal":        round(base_swing._minimum_tm_volume_gal,           2),
                "shared_base_tm_cap_kbtuh":    round(base_tm_cap,                                 2),
                "new_total_tm_cap_kbtuh":      round(er_system._minimum_tm_capacity_kbtuh,        2),
                "new_er_addition_kbtuh":       round(er_system.get_er_capacity_kbtuh(),           2),
                "new_error":                   None,
            })
        except Exception as e:
            results.append({
                "label":                       sc["label"],
                "shared_half_cap_kbtuh":       None,
                "shared_storage_gal":          None,
                "shared_tm_volume_gal":        None,
                "shared_base_tm_cap_kbtuh":    None,
                "new_total_tm_cap_kbtuh":      None,
                "new_er_addition_kbtuh":       None,
                "new_error":                   str(e),
            })
    return results


# ---------------------------------------------------------------------------
# Main — combine and write CSV
# ---------------------------------------------------------------------------

def _diff(a, b):
    return round(b - a, 3) if (a is not None and b is not None) else None

def _pct_diff(a, b):
    if a is None or b is None or a == 0:
        return None
    return round((b - a) / a * 100, 2)

def _fmt(val, decimals=1):
    return f"{val:.{decimals}f}" if val is not None else "ERR"

def _fmt_pct(val):
    return f"{val:+.1f}%" if val is not None else "ERR"


def main():
    output_path = os.path.join(os.path.dirname(__file__), "compare_sizing_output.csv")

    # ------------------------------------------------------------------
    # Primary (no recirc) comparison
    # ------------------------------------------------------------------
    print("Running original codebase sizing (primary)...")
    orig_results = run_original_sizing(SCENARIOS)

    print("Running new codebase sizing (primary)...")
    new_results = run_new_sizing(SCENARIOS)

    orig_by_label = {r["label"]: r for r in orig_results}
    new_by_label  = {r["label"]: r for r in new_results}

    primary_fieldnames = [
        "label", "load_shift",
        "orig_capacity_kbtuh", "new_capacity_kbtuh", "cap_diff_kbtuh", "cap_pct_diff",
        "orig_storage_storageT_gal", "new_storage_storageT_gal", "vol_diff_gal", "vol_pct_diff",
        "orig_error", "new_error",
    ]
    primary_rows = []
    for sc in SCENARIOS:
        lbl  = sc["label"]
        orig = orig_by_label.get(lbl, {})
        new  = new_by_label.get(lbl, {})
        cap_orig = orig.get("orig_capacity_kbtuh")
        cap_new  = new.get("new_capacity_kbtuh")
        vol_orig = orig.get("orig_storage_storageT_gal")
        vol_new  = new.get("new_storage_storageT_gal")
        primary_rows.append({
            "label": lbl,
            "load_shift": sc["load_shift"],
            "orig_capacity_kbtuh": cap_orig,
            "new_capacity_kbtuh": cap_new,
            "cap_diff_kbtuh": _diff(cap_orig, cap_new),
            "cap_pct_diff": _pct_diff(cap_orig, cap_new),
            "orig_storage_storageT_gal": vol_orig,
            "new_storage_storageT_gal": vol_new,
            "vol_diff_gal": _diff(vol_orig, vol_new),
            "vol_pct_diff": _pct_diff(vol_orig, vol_new),
            "orig_error": orig.get("orig_error"),
            "new_error": new.get("new_error"),
        })

    # ------------------------------------------------------------------
    # Parallel Loop comparison
    # ------------------------------------------------------------------
    print("Running original codebase sizing (parallel loop)...")
    pl_orig_results = run_original_parallel_sizing(PARALLEL_SCENARIOS)

    print("Running new codebase sizing (parallel loop)...")
    pl_new_results = run_new_parallel_sizing(PARALLEL_SCENARIOS)

    pl_orig_by_label = {r["label"]: r for r in pl_orig_results}
    pl_new_by_label  = {r["label"]: r for r in pl_new_results}

    pl_fieldnames = [
        "label",
        "orig_capacity_kbtuh", "new_capacity_kbtuh", "cap_diff_kbtuh", "cap_pct_diff",
        "orig_storage_storageT_gal", "new_storage_storageT_gal", "vol_diff_gal", "vol_pct_diff",
        "orig_tm_volume_gal", "new_tm_volume_gal", "tm_vol_diff_gal", "tm_vol_pct_diff",
        "orig_tm_capacity_kbtuh", "new_tm_capacity_kbtuh", "tm_cap_diff_kbtuh", "tm_cap_pct_diff",
        "orig_error", "new_error",
    ]
    pl_rows = []
    for sc in PARALLEL_SCENARIOS:
        lbl      = sc["label"]
        orig     = pl_orig_by_label.get(lbl, {})
        new      = pl_new_by_label.get(lbl, {})
        cap_o    = orig.get("orig_capacity_kbtuh")
        cap_n    = new.get("new_capacity_kbtuh")
        vol_o    = orig.get("orig_storage_storageT_gal")
        vol_n    = new.get("new_storage_storageT_gal")
        tmv_o    = orig.get("orig_tm_volume_gal")
        tmv_n    = new.get("new_tm_volume_gal")
        tmc_o    = orig.get("orig_tm_capacity_kbtuh")
        tmc_n    = new.get("new_tm_capacity_kbtuh")
        pl_rows.append({
            "label": lbl,
            "orig_capacity_kbtuh": cap_o, "new_capacity_kbtuh": cap_n,
            "cap_diff_kbtuh": _diff(cap_o, cap_n), "cap_pct_diff": _pct_diff(cap_o, cap_n),
            "orig_storage_storageT_gal": vol_o, "new_storage_storageT_gal": vol_n,
            "vol_diff_gal": _diff(vol_o, vol_n), "vol_pct_diff": _pct_diff(vol_o, vol_n),
            "orig_tm_volume_gal": tmv_o, "new_tm_volume_gal": tmv_n,
            "tm_vol_diff_gal": _diff(tmv_o, tmv_n), "tm_vol_pct_diff": _pct_diff(tmv_o, tmv_n),
            "orig_tm_capacity_kbtuh": tmc_o, "new_tm_capacity_kbtuh": tmc_n,
            "tm_cap_diff_kbtuh": _diff(tmc_o, tmc_n), "tm_cap_pct_diff": _pct_diff(tmc_o, tmc_n),
            "orig_error": orig.get("orig_error"),
            "new_error": new.get("new_error"),
        })

    # ------------------------------------------------------------------
    # Single Pass RTP comparison
    # ------------------------------------------------------------------
    print("Running original codebase sizing (single pass RTP)...")
    sprtp_orig_results = run_original_sprtp_sizing(SPRTP_SCENARIOS)

    print("Running new codebase sizing (single pass RTP)...")
    sprtp_new_results = run_new_sprtp_sizing(SPRTP_SCENARIOS)

    sprtp_orig_by_label = {r["label"]: r for r in sprtp_orig_results}
    sprtp_new_by_label  = {r["label"]: r for r in sprtp_new_results}

    sprtp_fieldnames = [
        "label",
        "orig_capacity_kbtuh", "new_capacity_kbtuh", "cap_diff_kbtuh", "cap_pct_diff",
        "orig_storage_storageT_gal", "new_storage_storageT_gal", "vol_diff_gal", "vol_pct_diff",
        "orig_recirc_cap_kbtuh", "new_recirc_cap_kbtuh",
        "orig_error", "new_error",
    ]
    sprtp_rows = []
    for sc in SPRTP_SCENARIOS:
        lbl   = sc["label"]
        orig  = sprtp_orig_by_label.get(lbl, {})
        new   = sprtp_new_by_label.get(lbl, {})
        cap_o = orig.get("orig_capacity_kbtuh")
        cap_n = new.get("new_capacity_kbtuh")
        vol_o = orig.get("orig_storage_storageT_gal")
        vol_n = new.get("new_storage_storageT_gal")
        sprtp_rows.append({
            "label": lbl,
            "orig_capacity_kbtuh": cap_o, "new_capacity_kbtuh": cap_n,
            "cap_diff_kbtuh": _diff(cap_o, cap_n), "cap_pct_diff": _pct_diff(cap_o, cap_n),
            "orig_storage_storageT_gal": vol_o, "new_storage_storageT_gal": vol_n,
            "vol_diff_gal": _diff(vol_o, vol_n), "vol_pct_diff": _pct_diff(vol_o, vol_n),
            "orig_recirc_cap_kbtuh": orig.get("orig_recirc_cap_kbtuh"),
            "new_recirc_cap_kbtuh":  new.get("new_recirc_cap_kbtuh"),
            "orig_error": orig.get("orig_error"),
            "new_error":  new.get("new_error"),
        })

    # ------------------------------------------------------------------
    # Swing Tank comparison
    # ------------------------------------------------------------------
    print("Running original codebase sizing (swing tank)...")
    st_orig_results = run_original_swing_sizing(SWING_SCENARIOS)

    print("Running new codebase sizing (swing tank)...")
    st_new_results = run_new_swing_sizing(SWING_SCENARIOS)

    st_orig_by_label = {r["label"]: r for r in st_orig_results}
    st_new_by_label  = {r["label"]: r for r in st_new_results}

    st_fieldnames = [
        "label",
        "orig_capacity_kbtuh", "new_capacity_kbtuh", "cap_diff_kbtuh", "cap_pct_diff",
        "orig_storage_storageT_gal", "new_storage_storageT_gal", "vol_diff_gal", "vol_pct_diff",
        "orig_tm_volume_gal", "new_tm_volume_gal", "tm_vol_diff_gal", "tm_vol_pct_diff",
        "orig_tm_capacity_kbtuh", "new_tm_capacity_kbtuh", "tm_cap_diff_kbtuh", "tm_cap_pct_diff",
        "orig_error", "new_error",
    ]
    st_rows = []
    for sc in SWING_SCENARIOS:
        lbl   = sc["label"]
        orig  = st_orig_by_label.get(lbl, {})
        new   = st_new_by_label.get(lbl, {})
        cap_o = orig.get("orig_capacity_kbtuh")
        cap_n = new.get("new_capacity_kbtuh")
        vol_o = orig.get("orig_storage_storageT_gal")
        vol_n = new.get("new_storage_storageT_gal")
        tmv_o = orig.get("orig_tm_volume_gal")
        tmv_n = new.get("new_tm_volume_gal")
        tmc_o = orig.get("orig_tm_capacity_kbtuh")
        tmc_n = new.get("new_tm_capacity_kbtuh")
        st_rows.append({
            "label": lbl,
            "orig_capacity_kbtuh": cap_o, "new_capacity_kbtuh": cap_n,
            "cap_diff_kbtuh": _diff(cap_o, cap_n), "cap_pct_diff": _pct_diff(cap_o, cap_n),
            "orig_storage_storageT_gal": vol_o, "new_storage_storageT_gal": vol_n,
            "vol_diff_gal": _diff(vol_o, vol_n), "vol_pct_diff": _pct_diff(vol_o, vol_n),
            "orig_tm_volume_gal": tmv_o, "new_tm_volume_gal": tmv_n,
            "tm_vol_diff_gal": _diff(tmv_o, tmv_n), "tm_vol_pct_diff": _pct_diff(tmv_o, tmv_n),
            "orig_tm_capacity_kbtuh": tmc_o, "new_tm_capacity_kbtuh": tmc_n,
            "tm_cap_diff_kbtuh": _diff(tmc_o, tmc_n), "tm_cap_pct_diff": _pct_diff(tmc_o, tmc_n),
            "orig_error": orig.get("orig_error"),
            "new_error": new.get("new_error"),
        })

    # ------------------------------------------------------------------
    # Swing Tank ER comparison
    # ------------------------------------------------------------------
    # Run new codebase first — it sizes the base SwingSystem and provides
    # shared primary dimensions (half_cap, storage_gal, tm_volume, base_tm_cap)
    # that both codebases will use, ensuring an apples-to-apples ER comparison.
    print("Running new codebase sizing (swing tank ER)...")
    ser_new_results = run_new_swing_er_sizing(SWING_SCENARIOS)
    ser_new_by_label = {r["label"]: r for r in ser_new_results}

    # Enrich SWING_SCENARIOS with shared dimension fields from new sizing
    enriched_swing_scenarios = [
        {
            **sc,
            **{k: ser_new_by_label.get(sc["label"], {}).get(k)
               for k in ("shared_half_cap_kbtuh", "shared_storage_gal",
                         "shared_tm_volume_gal", "shared_base_tm_cap_kbtuh")},
        }
        for sc in SWING_SCENARIOS
    ]

    print("Running original codebase sizing (swing tank ER)...")
    ser_orig_results = run_original_swing_er_sizing(enriched_swing_scenarios)
    ser_orig_by_label = {r["label"]: r for r in ser_orig_results}

    ser_fieldnames = [
        "label",
        "shared_half_cap_kbtuh",
        "shared_storage_gal",
        "shared_tm_volume_gal",
        "shared_base_tm_cap_kbtuh",
        "orig_total_tm_cap_kbtuh", "new_total_tm_cap_kbtuh",
        "total_tm_cap_diff_kbtuh", "total_tm_cap_pct_diff",
        "orig_er_addition_kbtuh", "new_er_addition_kbtuh",
        "er_diff_kbtuh", "er_pct_diff",
        "orig_error", "new_error",
    ]
    ser_rows = []
    for sc in SWING_SCENARIOS:
        lbl  = sc["label"]
        orig = ser_orig_by_label.get(lbl, {})
        new  = ser_new_by_label.get(lbl, {})
        tot_o = orig.get("orig_total_tm_cap_kbtuh")
        tot_n = new.get("new_total_tm_cap_kbtuh")
        er_o  = orig.get("orig_er_addition_kbtuh")
        er_n  = new.get("new_er_addition_kbtuh")
        ser_rows.append({
            "label":                    lbl,
            "shared_half_cap_kbtuh":    new.get("shared_half_cap_kbtuh"),
            "shared_storage_gal":       new.get("shared_storage_gal"),
            "shared_tm_volume_gal":     new.get("shared_tm_volume_gal"),
            "shared_base_tm_cap_kbtuh": new.get("shared_base_tm_cap_kbtuh"),
            "orig_total_tm_cap_kbtuh":  tot_o,
            "new_total_tm_cap_kbtuh":   tot_n,
            "total_tm_cap_diff_kbtuh":  _diff(tot_o, tot_n),
            "total_tm_cap_pct_diff":    _pct_diff(tot_o, tot_n),
            "orig_er_addition_kbtuh":   er_o,
            "new_er_addition_kbtuh":    er_n,
            "er_diff_kbtuh":            _diff(er_o, er_n),
            "er_pct_diff":              _pct_diff(er_o, er_n),
            "orig_error":               orig.get("orig_error"),
            "new_error":                new.get("new_error"),
        })

    # ------------------------------------------------------------------
    # Write CSV (four sections)
    # ------------------------------------------------------------------
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["=== PRIMARY SYSTEM SIZING ==="])
        dw = csv.DictWriter(f, fieldnames=primary_fieldnames)
        dw.writeheader()
        dw.writerows(primary_rows)
        writer.writerow([])
        writer.writerow(["=== PARALLEL LOOP SIZING ==="])
        dw2 = csv.DictWriter(f, fieldnames=pl_fieldnames)
        dw2.writeheader()
        dw2.writerows(pl_rows)
        writer.writerow([])
        writer.writerow(["=== SINGLE PASS RTP SIZING ==="])
        dw_sprtp = csv.DictWriter(f, fieldnames=sprtp_fieldnames)
        dw_sprtp.writeheader()
        dw_sprtp.writerows(sprtp_rows)
        writer.writerow([])
        writer.writerow(["=== SWING TANK SIZING ==="])
        dw3 = csv.DictWriter(f, fieldnames=st_fieldnames)
        dw3.writeheader()
        dw3.writerows(st_rows)
        writer.writerow([])
        writer.writerow(["=== SWING TANK ER SIZING (primary capacity halved) ==="])
        dw4 = csv.DictWriter(f, fieldnames=ser_fieldnames)
        dw4.writeheader()
        dw4.writerows(ser_rows)

    print(f"\nResults written to: {output_path}\n")

    # ------------------------------------------------------------------
    # Console output — primary
    # ------------------------------------------------------------------
    hdr = f"{'Scenario':<55} {'OrigCap':>9} {'NewCap':>9} {'Cap%Dif':>8}  {'OrigVol':>9} {'NewVol':>9} {'Vol%Dif':>8}"
    print("PRIMARY SYSTEM")
    print(hdr)
    print("-" * len(hdr))
    for row in primary_rows:
        print(
            f"{row['label']:<55} "
            f"{_fmt(row['orig_capacity_kbtuh']):>9} {_fmt(row['new_capacity_kbtuh']):>9} {_fmt_pct(row['cap_pct_diff']):>8}  "
            f"{_fmt(row['orig_storage_storageT_gal']):>9} {_fmt(row['new_storage_storageT_gal']):>9} {_fmt_pct(row['vol_pct_diff']):>8}"
        )
        if row["orig_error"]: print(f"  ORIG ERROR: {row['orig_error']}")
        if row["new_error"]:  print(f"  NEW  ERROR: {row['new_error']}")

    # ------------------------------------------------------------------
    # Console output — parallel loop
    # ------------------------------------------------------------------
    print()
    pl_hdr = (
        f"{'Scenario':<45} "
        f"{'OCap':>8} {'NCap':>8} {'C%':>7}  "
        f"{'OVol':>8} {'NVol':>8} {'V%':>7}  "
        f"{'OTMVol':>8} {'NTMVol':>8} {'TV%':>7}  "
        f"{'OTMCap':>8} {'NTMCap':>8} {'TC%':>7}"
    )
    print("PARALLEL LOOP SYSTEM")
    print(pl_hdr)
    print("-" * len(pl_hdr))
    for row in pl_rows:
        print(
            f"{row['label']:<45} "
            f"{_fmt(row['orig_capacity_kbtuh']):>8} {_fmt(row['new_capacity_kbtuh']):>8} {_fmt_pct(row['cap_pct_diff']):>7}  "
            f"{_fmt(row['orig_storage_storageT_gal']):>8} {_fmt(row['new_storage_storageT_gal']):>8} {_fmt_pct(row['vol_pct_diff']):>7}  "
            f"{_fmt(row['orig_tm_volume_gal']):>8} {_fmt(row['new_tm_volume_gal']):>8} {_fmt_pct(row['tm_vol_pct_diff']):>7}  "
            f"{_fmt(row['orig_tm_capacity_kbtuh']):>8} {_fmt(row['new_tm_capacity_kbtuh']):>8} {_fmt_pct(row['tm_cap_pct_diff']):>7}"
        )
        if row["orig_error"]: print(f"  ORIG ERROR: {row['orig_error']}")
        if row["new_error"]:  print(f"  NEW  ERROR: {row['new_error']}")

    # ------------------------------------------------------------------
    # Console output — single pass RTP
    # ------------------------------------------------------------------
    print()
    sprtp_hdr = (
        f"{'Scenario':<50} "
        f"{'OCap':>8} {'NCap':>8} {'C%':>7}  "
        f"{'OVol':>8} {'NVol':>8} {'V%':>7}  "
        f"{'ORecircCap':>11} {'NRecircCap':>11}"
    )
    print("SINGLE PASS RTP SYSTEM")
    print(sprtp_hdr)
    print("-" * len(sprtp_hdr))
    for row in sprtp_rows:
        print(
            f"{row['label']:<50} "
            f"{_fmt(row['orig_capacity_kbtuh']):>8} {_fmt(row['new_capacity_kbtuh']):>8} {_fmt_pct(row['cap_pct_diff']):>7}  "
            f"{_fmt(row['orig_storage_storageT_gal']):>8} {_fmt(row['new_storage_storageT_gal']):>8} {_fmt_pct(row['vol_pct_diff']):>7}  "
            f"{_fmt(row['orig_recirc_cap_kbtuh']):>11} {_fmt(row['new_recirc_cap_kbtuh']):>11}"
        )
        if row["orig_error"]: print(f"  ORIG ERROR: {row['orig_error']}")
        if row["new_error"]:  print(f"  NEW  ERROR: {row['new_error']}")

    # ------------------------------------------------------------------
    # Console output — swing tank
    # ------------------------------------------------------------------
    print()
    st_hdr = (
        f"{'Scenario':<45} "
        f"{'OCap':>8} {'NCap':>8} {'C%':>7}  "
        f"{'OVol':>8} {'NVol':>8} {'V%':>7}  "
        f"{'OTMVol':>8} {'NTMVol':>8} {'TV%':>7}  "
        f"{'OTMCap':>8} {'NTMCap':>8} {'TC%':>7}"
    )
    print("SWING TANK SYSTEM")
    print(st_hdr)
    print("-" * len(st_hdr))
    for row in st_rows:
        print(
            f"{row['label']:<45} "
            f"{_fmt(row['orig_capacity_kbtuh']):>8} {_fmt(row['new_capacity_kbtuh']):>8} {_fmt_pct(row['cap_pct_diff']):>7}  "
            f"{_fmt(row['orig_storage_storageT_gal']):>8} {_fmt(row['new_storage_storageT_gal']):>8} {_fmt_pct(row['vol_pct_diff']):>7}  "
            f"{_fmt(row['orig_tm_volume_gal']):>8} {_fmt(row['new_tm_volume_gal']):>8} {_fmt_pct(row['tm_vol_pct_diff']):>7}  "
            f"{_fmt(row['orig_tm_capacity_kbtuh']):>8} {_fmt(row['new_tm_capacity_kbtuh']):>8} {_fmt_pct(row['tm_cap_pct_diff']):>7}"
        )
        if row["orig_error"]: print(f"  ORIG ERROR: {row['orig_error']}")
        if row["new_error"]:  print(f"  NEW  ERROR: {row['new_error']}")

    # ------------------------------------------------------------------
    # Console output — swing tank ER
    # ------------------------------------------------------------------
    print()
    ser_hdr = (
        f"{'Scenario':<45} "
        f"{'HalfCap':>9} {'BaseTM':>8}  "
        f"{'OTotTM':>8} {'NTotTM':>8} {'TM%':>7}  "
        f"{'OERAdd':>8} {'NERAdd':>8} {'ER%':>7}"
    )
    print("SWING TANK ER SYSTEM  (both codebases use same primary dimensions from new sizing)")
    print(ser_hdr)
    print("-" * len(ser_hdr))
    for row in ser_rows:
        print(
            f"{row['label']:<45} "
            f"{_fmt(row['shared_half_cap_kbtuh']):>9} {_fmt(row['shared_base_tm_cap_kbtuh']):>8}  "
            f"{_fmt(row['orig_total_tm_cap_kbtuh']):>8} {_fmt(row['new_total_tm_cap_kbtuh']):>8} {_fmt_pct(row['total_tm_cap_pct_diff']):>7}  "
            f"{_fmt(row['orig_er_addition_kbtuh']):>8} {_fmt(row['new_er_addition_kbtuh']):>8} {_fmt_pct(row['er_pct_diff']):>7}"
        )
        if row["orig_error"]: print(f"  ORIG ERROR: {row['orig_error']}")
        if row["new_error"]:  print(f"  NEW  ERROR: {row['new_error']}")


if __name__ == "__main__":
    main()
