"""
3-day design-day sizing + simulation demo using EcosizerEngine.

Building: 400-person multi-family
Temperatures: 47 F inlet / 125 F supply / 150 F storage

Four scenarios are run and plotted:
  1. Parallel loop — baseline (no load shifting)
  2. Parallel loop — load shift (shed 4PM–9PM, load-up 1PM–4PM)
  3. Swing tank — baseline (no load shifting)
  4. Swing tank — load shift (shed 4PM–9PM, load-up 1PM–4PM)

Run:
    python demo_3day_sim.py

Outputs:
    parallel_loop_baseline.html    -- parallel loop baseline chart
    parallel_loop_ls.html          -- parallel loop load-shift chart
    swing_tank_baseline.html       -- swing tank baseline chart
    swing_tank_ls.html             -- swing tank load-shift chart
"""

from ecoengine.interfaces.EcosizerEngine import EcosizerEngine

# ---------------------------------------------------------------------------
# Shared configuration
# ---------------------------------------------------------------------------
N_PEOPLE    = 400
GPDPP       = 25.0
INLET_T_F   = 47.0
SUPPLY_T_F  = 125.0
STORAGE_T_F = 150.0
DESIGN_OAT  = 47.0

CLIMATE = {
    "design_oat_f":              DESIGN_OAT,
    "design_inlet_water_temp_f": INLET_T_F,
}

RECIRC_KWARGS = dict(
    return_flow_gpm = 6,
    return_temp_f   = 120,
    tm_off_temp_f   = 135,
    tm_on_temp_f    = 125,
    tm_off_time_hr  = 0.33,
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def print_sizing(label, engine, storage_t):
    sizing = engine.get_sizing_results()
    cap    = sizing["min_capacity_kbtuh"]
    vol    = sizing["min_storage_storageT_gal"]
    print(f"\n{label}")
    print(f"  Capacity:          {cap:.1f} kBTU/hr  ({cap * 1000 / 3412.14:.1f} kW)")
    print(f"  Storage:           {vol:.0f} gal at {storage_t:.0f} F")
    if "min_tm_volume_gal" in sizing:
        print(f"  TM storage:        {sizing['min_tm_volume_gal']:.0f} gal")
        print(f"  TM capacity:       {sizing['min_tm_capacity_kbtuh']:.1f} kBTU/hr")
    print(f"  Daily DHW:         {engine._building.daily_dhw_use_supplyT_gal:,.0f} gal/day at supply temp")
    return sizing


def print_results(result, engine):
    summary = engine.get_simulation_summary(result)
    print(f"  Successful:        {summary['successful']}")
    print(f"  Stopped early:     {summary['stopped_early']}")
    print(f"  Outage minutes:    {summary['total_outage_min']}")
    print(f"  Min usable vol:    {min(result.usable_volume_supplyT_gal):.1f} gal")
    print(f"  Max usable vol:    {max(result.usable_volume_supplyT_gal):.1f} gal")
    on_pct = 100.0 * sum(1 for x in result.heater_output_kbtuh if x > 0) / len(result.heater_output_kbtuh)
    print(f"  Heater on:         {on_pct:.1f}% of timesteps")


# ===========================================================================
# Scenario 1 — Baseline (no load shifting)
# ===========================================================================
print("=" * 60)
print("SCENARIO 1: Baseline (no load shifting)")
print("=" * 60)

print("Sizing...", end=" ", flush=True)
engine_base = EcosizerEngine(
    building_type            = "multi_family",
    magnitude                = N_PEOPLE,
    zip_code_or_climate_zone = CLIMATE,
    supply_temp_f            = SUPPLY_T_F,
    storage_temp_f           = STORAGE_T_F,
    schematic                = "parallel_loop",
    gpdpp                    = GPDPP,
    max_daily_run_hr         = 16.0,
    aquastat_fract           = 0.4,
    off_sensor_fract         = 0.2,
    on_trigger_t_f           = 120.0,
    off_trigger_t_f          = 140.0,
    **RECIRC_KWARGS,
    load_shift_percent = 0.95
)
print("done.")
sizing_base = print_sizing("Baseline sizing", engine_base, STORAGE_T_F)

print("Simulating...", end=" ", flush=True)
result_base = engine_base.simulate_3day()
print("done.")
print_results(result_base, engine_base)

cap_base = sizing_base["min_capacity_kbtuh"]
vol_base = sizing_base["min_storage_storageT_gal"]
OUTPUT_BASE = "parallel_loop_baseline.html"
result_base.to_plotly(
    title = (
        f"3-Day Simulation — Parallel Loop Baseline — {N_PEOPLE}-Person Multi-Family  |  "
        f"{SUPPLY_T_F:.0f}°F supply / {STORAGE_T_F:.0f}°F storage  |  "
        f"Cap {cap_base:.0f} kBTU/hr, Storage {vol_base:.0f} gal"
    ),
    filepath             = OUTPUT_BASE,
    include_temperatures = True,
)
print(f"\nPlot saved: {OUTPUT_BASE}")

# ===========================================================================
# Scenario 2 — Load shift: shed 4PM–9PM, load-up 1PM–4PM
# ===========================================================================
print()
print("=" * 60)
print("SCENARIO 2: Load shift  (shed 4PM–9PM, load-up 1PM–4PM)")
print("=" * 60)

# 24-element schedule: 0 = shed hour, 1 = run hour
# Shed hours: 16, 17, 18, 19, 20  (4PM through 8PM inclusive → 9PM exclusive)
LS_SCHEDULE = [
    1, 1, 1, 1, 1, 1, 1, 1,   # 00–07
    1, 1, 1, 1, 1, 1, 1, 1,   # 08–15
    0, 0, 0, 0, 0,             # 16–20  ← shed
    1, 1, 1,                   # 21–23
]

print("Sizing...", end=" ", flush=True)
engine_ls = EcosizerEngine(
    building_type            = "multi_family",
    magnitude                = N_PEOPLE,
    zip_code_or_climate_zone = CLIMATE,
    supply_temp_f            = SUPPLY_T_F,
    storage_temp_f           = STORAGE_T_F,
    schematic                = "parallel_loop",
    gpdpp                    = GPDPP,
    max_daily_run_hr         = 16.0,
    # Normal controls
    aquastat_fract           = 0.4,
    off_sensor_fract         = 0.2,
    on_trigger_t_f           = 120.0,
    off_trigger_t_f          = 140.0,
    # Load shift schedule
    load_shift_schedule      = LS_SCHEDULE,
    load_up_hours            = 3,          # hours 13–15 become load-up
    # Shed controls: on_sensor=0.8, off_sensor=0.4, on=120, off=140, outlet=150
    shed_aquastat_fract      = 0.8,
    shed_off_sensor_fract    = 0.4,
    # Load-up controls: on_sensor=0.2, off_sensor=0.15, on=120, off=125, outlet=150
    load_up_aquastat_fract   = 0.2,
    load_up_off_sensor_fract = 0.15,
    load_up_off_trigger_t_f  = 125.0,
    **RECIRC_KWARGS,
    load_shift_percent = 0.89
)
print("done.")
sizing_ls = print_sizing("Load-shift sizing", engine_ls, STORAGE_T_F)

print("Simulating...", end=" ", flush=True)
result_ls = engine_ls.simulate_3day()
print("done.")
print_results(result_ls, engine_ls)

cap_ls = sizing_ls["min_capacity_kbtuh"]
vol_ls = sizing_ls["min_storage_storageT_gal"]
OUTPUT_LS = "parallel_loop_ls.html"
result_ls.to_plotly(
    title = (
        f"3-Day Simulation — Parallel Loop Load Shift (shed 4–9PM, load-up 1–4PM) — {N_PEOPLE}-Person Multi-Family  |  "
        f"{SUPPLY_T_F:.0f}°F supply / {STORAGE_T_F:.0f}°F storage  |  "
        f"Cap {cap_ls:.0f} kBTU/hr, Storage {vol_ls:.0f} gal"
    ),
    filepath             = OUTPUT_LS,
    include_temperatures = True,
)
print(f"\nPlot saved: {OUTPUT_LS}")

# ===========================================================================
# Scenario 3 — Swing Tank Baseline (no load shifting)
# ===========================================================================
print()
print("=" * 60)
print("SCENARIO 3: Swing Tank — Baseline (no load shifting)")
print("=" * 60)

print("Sizing...", end=" ", flush=True)
engine_swing = EcosizerEngine(
    building_type            = "multi_family",
    magnitude                = N_PEOPLE,
    zip_code_or_climate_zone = CLIMATE,
    supply_temp_f            = SUPPLY_T_F,
    storage_temp_f           = STORAGE_T_F,
    schematic                = "swing_tank",
    gpdpp                    = GPDPP,
    max_daily_run_hr         = 16.0,
    aquastat_fract           = 0.4,
    off_sensor_fract         = 0.2,
    on_trigger_t_f           = 120.0,
    off_trigger_t_f          = 140.0,
    **RECIRC_KWARGS,
)
print("done.")
sizing_swing = print_sizing("Swing Tank baseline sizing", engine_swing, STORAGE_T_F)

print("Simulating...", end=" ", flush=True)
result_swing = engine_swing.simulate_3day()
print("done.")
print_results(result_swing, engine_swing)

cap_swing = sizing_swing["min_capacity_kbtuh"]
vol_swing = sizing_swing["min_storage_storageT_gal"]
tm_vol_swing = sizing_swing.get("min_tm_volume_gal", 0)
OUTPUT_SWING = "swing_tank_baseline.html"
result_swing.to_plotly(
    title = (
        f"3-Day Simulation — Swing Tank Baseline — {N_PEOPLE}-Person Multi-Family  |  "
        f"{SUPPLY_T_F:.0f}°F supply / {STORAGE_T_F:.0f}°F storage  |  "
        f"Cap {cap_swing:.0f} kBTU/hr, Primary {vol_swing:.0f} gal, Swing {tm_vol_swing:.0f} gal"
    ),
    filepath             = OUTPUT_SWING,
    include_temperatures = True,
)
print(f"\nPlot saved: {OUTPUT_SWING}")

# ===========================================================================
# Scenario 4 — Swing Tank Load Shift
# ===========================================================================
print()
print("=" * 60)
print("SCENARIO 4: Swing Tank — Load shift  (shed 4PM–9PM, load-up 1PM–4PM)")
print("=" * 60)

print("Sizing...", end=" ", flush=True)
engine_swing_ls = EcosizerEngine(
    building_type            = "multi_family",
    magnitude                = N_PEOPLE,
    zip_code_or_climate_zone = CLIMATE,
    supply_temp_f            = SUPPLY_T_F,
    storage_temp_f           = STORAGE_T_F,
    schematic                = "swing_tank",
    gpdpp                    = GPDPP,
    max_daily_run_hr         = 16.0,
    aquastat_fract           = 0.4,
    off_sensor_fract         = 0.2,
    on_trigger_t_f           = 120.0,
    off_trigger_t_f          = 140.0,
    load_shift_schedule      = LS_SCHEDULE,
    load_up_hours            = 3,
    shed_aquastat_fract      = 0.8,
    shed_off_sensor_fract    = 0.4,
    load_up_aquastat_fract   = 0.2,
    load_up_off_sensor_fract = 0.15,
    load_up_off_trigger_t_f  = 125.0,
    **RECIRC_KWARGS,
    load_shift_percent = 0.89,
)
print("done.")
sizing_swing_ls = print_sizing("Swing Tank load-shift sizing", engine_swing_ls, STORAGE_T_F)

print("Simulating...", end=" ", flush=True)
result_swing_ls = engine_swing_ls.simulate_3day()
print("done.")
print_results(result_swing_ls, engine_swing_ls)

cap_swing_ls = sizing_swing_ls["min_capacity_kbtuh"]
vol_swing_ls = sizing_swing_ls["min_storage_storageT_gal"]
tm_vol_swing_ls = sizing_swing_ls.get("min_tm_volume_gal", 0)
OUTPUT_SWING_LS = "swing_tank_ls.html"
result_swing_ls.to_plotly(
    title = (
        f"3-Day Simulation — Swing Tank Load Shift (shed 4–9PM, load-up 1–4PM) — {N_PEOPLE}-Person Multi-Family  |  "
        f"{SUPPLY_T_F:.0f}°F supply / {STORAGE_T_F:.0f}°F storage  |  "
        f"Cap {cap_swing_ls:.0f} kBTU/hr, Primary {vol_swing_ls:.0f} gal, Swing {tm_vol_swing_ls:.0f} gal"
    ),
    filepath             = OUTPUT_SWING_LS,
    include_temperatures = True,
)
print(f"\nPlot saved: {OUTPUT_SWING_LS}")
print("\nOpen any HTML file in a browser to view the interactive chart.")
