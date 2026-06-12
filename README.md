# EcosizerEngine

EcosizerEngine Copyright (C) 2023  Ecotope Inc.
This program comes with ABSOLUTELY NO WARRANTY. This is free software, and you are welcome to redistribute under certain conditions; details check GNU AFFERO GENERAL PUBLIC LICENSE_08102020.docx.

A Python simulation engine for sizing and simulating domestic hot water (DHW) systems in multi-family and commercial buildings, with a focus on heat pump water heater (HPWH) technology.

Requires Python 3.11+. Dependencies: `numpy`, `scipy`, `plotly`.

---

## Installation

To make the package available to other local apps without publishing it to PyPI, install it in editable mode from the repo root:

```bash
pip install -e .
```

Any app that shares the same Python environment can then import from `ecoengine` directly. Changes made to the source files take effect immediately without reinstalling.

---

## What the engine does

The engine performs three core functions:

1. **Sizing** — calculates the minimum heating capacity (kBTU/hr) and storage volume (gallons) needed to meet peak daily demand.
2. **3-day design-day simulation** — models system performance at 1-minute timesteps over three consecutive peak-demand days.
3. **Annual simulation** — full-year simulation at 10-minute timesteps for cost and efficiency analysis.

---

## Package structure

```
src/ecoengine/
├── __init__.py                  # Re-exports EcosizerEngine and top-level helpers
│
├── interfaces/
│   ├── EcosizerEngine.py        # Top-level orchestrator and public API
│   └── Simulator.py             # simulate(), simulate_3day(), simulate_annual()
│
├── objects/
│   ├── building/
│   │   ├── Building.py          # Occupancy, daily demand, load shapes
│   │   ├── ClimateZone.py       # Hourly OAT and monthly inlet water temps
│   │   └── UtilityCostTracker.py
│   │
│   ├── components/
│   │   ├── heating/
│   │   │   ├── WaterHeater.py   # Single HPWH unit with on/off state
│   │   │   ├── PerformanceMap.py # Capacity/power lookup (nominal, pkl, polynomial)
│   │   │   └── Controls.py      # Aquastat setpoints per operating mode
│   │   └── storage/
│   │       ├── StorageTank.py   # Abstract base class
│   │       ├── StratifiedTank.py    # Continuous linear temperature profile model
│   │       ├── MixedStorageTank.py  # Fully-mixed single-node model (TM tanks)
│   │       ├── EnergyTank.py        # Energy-based base for MPRTP
│   │       └── SlugOverlayTank.py   # Slug overlay for multi-pass RTP simulation
│   │
│   ├── dhwsystems/
│   │   ├── DHWSystem.py         # Base class: sizing, simulation step, sizing curve
│   │   ├── InstantWHSystem.py   # Tankless (no storage)
│   │   ├── MPNoRecircSystem.py  # Multi-pass, no recirculation
│   │   ├── recirc_systems/
│   │   │   ├── RecircSystem.py        # Base for systems with recirc loops
│   │   │   ├── ParallelLoopSystem.py  # Parallel loop with separate TM tank
│   │   │   ├── SwingSystem.py         # Swing tank system
│   │   │   └── SwingERTrdOffSystem.py # Swing + ER element trade-off variant
│   │   └── rtp_systems/
│   │       ├── RTPSystem.py             # Base for return-to-primary systems
│   │       ├── SinglePassRTPSystem.py   # SPRTP: recirc returns to primary tank
│   │       ├── MultiPassRTPSystem.py    # MPRTP: growing-slug sizing and simulation
│   │       ├── SP_RTPInParallelSystem.py
│   │       ├── SP_RTPInSeriesSystem.py
│   │       └── MP_RTPInSeriesSystem.py
│   │
│   └── simulation/
│       └── SimulationRun.py     # Per-timestep output accumulator and reporting
│
└── data/
    ├── load_shapes/             # 24-hr normalized DHW demand profiles (JSON)
    ├── climate_data/            # CA climate zone weather data (CSV)
    └── preformanceMaps/         # HPWH performance map pkl and JSON files
```

---

## Entry point

All normal usage goes through `EcosizerEngine`:

```python
from ecoengine import EcosizerEngine

engine = EcosizerEngine(
    building_type   = "multi_family",
    num_units       = 100,
    zip_code        = 94105,
    supply_temp_f   = 120,
    storage_temp_f  = 150,
    system_type     = "parallel_loop",
)

engine.build()
engine.size()
results = engine.get_sizing_results()
```

Top-level helper functions are also importable directly:

```python
from ecoengine import get_oat_buckets, get_list_of_models, get_weather_stations
```

---

## Simulation example

The example below sizes a parallel loop system, runs a 3-day design-day simulation, and writes two HTML files: one with the simulation time-series and one with the sizing curve.

```python
from ecoengine import EcosizerEngine

# 1. Configure and size the system.
#    zip_code_or_climate_zone accepts a CA zip code, a zone ID (int),
#    or a dict of design conditions (design_oat_f, design_inlet_water_temp_f).
engine = EcosizerEngine(
    building_type            = "multi_family",
    magnitude                = 100,           # people
    zip_code_or_climate_zone = 94105,         # San Francisco
    supply_temp_f            = 120.0,
    storage_temp_f           = 150.0,
    schematic                = "parallel_loop",
    gpdpp                    = 25.0,          # gallons per person per day
    max_daily_run_hr         = 16.0,
    aquastat_fract           = 0.4,           # ON sensor at 40% tank height
    off_sensor_fract         = 0.2,           # OFF sensor at 20% tank height
    on_trigger_t_f           = 120.0,
    off_trigger_t_f          = 140.0,
    return_flow_gpm          = 3.0,
    return_temp_f            = 110.0,
    tm_on_temp_f             = 115.0,
    tm_off_temp_f            = 125.0,
    tm_off_time_hr           = 0.5,
)

# 2. Check sizing results.
sizing = engine.get_sizing_results()
print(f"Capacity:  {sizing['min_capacity_kbtuh']:.1f} kBTU/hr")
print(f"Storage:   {sizing['min_storage_storageT_gal']:.0f} gal")
print(f"TM tank:   {sizing['min_tm_volume_gal']:.0f} gal")

# 3. Run the 3-day design-day simulation (1-minute timesteps).
result = engine.simulate_3day()

# 4. Plot the simulation time-series and write to an HTML file.
fig_sim = result.to_plotly(
    title              = "3-Day Simulation — 100-Person Multi-Family Parallel Loop",
    include_temperatures = True,
)
fig_sim.write_html("simulation.html")

# 5. Plot the sizing curve (capacity vs. storage) and write to an HTML file.
engine.plot_sizing_curve(
    title    = "Sizing Curve — 100-Person Multi-Family Parallel Loop",
    filepath = "sizing_curve.html",
)

print("Saved simulation.html and sizing_curve.html")
```

Open either HTML file in a browser to view the interactive Plotly chart.

**Available schematics:** `"parallel_loop"`, `"swing_tank"`, `"single_pass_rtp"`, `"multi_pass_rtp"`, `"no_recirc"`, `"instant"`.

For a full working example including load-shift scheduling across multiple system types, see `demo_3day_sim.py` in the repo root.

---

## Running tests

```bash
pytest src/ecoengine/tests/
```
