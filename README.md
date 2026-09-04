# EcosizerEngine

EcosizerEngine Copyright (C) 2023  Ecotope Inc.
This program comes with ABSOLUTELY NO WARRANTY. This is free software, and you are welcome to redistribute under certain conditions; details check GNU AFFERO GENERAL PUBLIC LICENSE_08102020.docx.

A Python simulation engine for sizing and simulating domestic hot water (DHW) systems in multi-family and commercial buildings, with a focus on heat pump water heater (HPWH) technology.

Requires Python 3.11 (capped below 3.12). Dependencies: `numpy`, `scipy`, `plotly`.

Version bounds are deliberate. `ecoengine` is installed into the same environments as `ecopipeline` (DataPipelinePackage) and `rcc-dash-viewer` (RCCDashViewer, which depends on `ecoengine` directly), so the pins are set to resolve alongside both. See the comments in `pyproject.toml` before loosening them.

---

## Installation

Dependencies are managed with [uv](https://docs.astral.sh/uv/). `uv.lock` is committed, so `uv sync` reproduces the exact environment CI and the published package are built against:

```bash
uv sync
```

That creates `.venv` and installs `ecoengine` in editable mode — changes to the source files take effect immediately without reinstalling. Prefix commands with `uv run` to use it (`uv run python your_script.py`).

Consumers who are not using uv can still install normally; the pins in `pyproject.toml` are what a plain `pip install` resolves against:

```bash
pip install -e .        # from the repo root
pip install ecoengine   # from PyPI
```

---

## Changing the version or dependencies

`uv.lock` records the project's own version alongside its dependency graph, so **any edit to `pyproject.toml` needs a `uv lock` in the same commit** — including a bare version bump. The release workflow runs `uv sync --locked`, which fails the build if the two have drifted rather than silently re-resolving.

```bash
uv version 3.1.7        # bumps pyproject.toml and updates uv.lock together
git add pyproject.toml uv.lock
git commit -m "version bump to 3.1.7"
```

Editing `pyproject.toml` by hand works too — just run `uv lock` afterward and commit both files. Never hand-edit `uv.lock`.

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
uv run pytest
```

`testpaths` in `pyproject.toml` points at the suite, so no path argument is needed. Pass one to narrow the run:

```bash
uv run pytest src/ecoengine/tests/test_buildings.py
```
