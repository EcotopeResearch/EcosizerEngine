# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install in editable mode (required before running tests)
pip install -e .

# Run all tests
pytest src/ecoengine/tests/

# Run a single test file
pytest src/ecoengine/tests/test_buildings.py

# Run a single test by name
pytest src/ecoengine/tests/test_buildings.py::test_name

# Run demo/example
python run_simulation.py
```

## Reference Codebase

The original **EcosizerEngine** lives at `C:\Users\nolan\Documents\EcosizerEngine\`. It is useful for checking algorithmic logic when something is unclear, but do **not** copy structure — the whole point of this project is the new decomposition.

Key mappings old → new:
- `engine/EcosizerEngine.py` + `SystemCreator.py` + `BuildingCreator.py` → `interfaces/EcosizerEngine.py`
- `objects/SystemConfig.py` → `objects/dhwsystems/DHWSystem.py` (and subclasses)
- `objects/PrefMapTracker.py` → `objects/components/heating/PerformanceMap.py`
- Storage tank logic (embedded in SystemConfig) → `objects/components/storage/StorageTank.py`
- `objects/Building.py` → `objects/building/Building.py` + `ClimateZone.py` + `UtilityCostTracker.py`
- `engine/Simulator.py` → `interfaces/Simulator.py`

## Project Overview

EcosizerEngine2 is a Python 3.11+ simulation engine for sizing and simulating domestic hot water (DHW) systems in multi-family and commercial buildings, focused on heat pump water heater (HPWH) technology. It has **no external dependencies** except numpy and pytest.

The engine performs three core functions:
1. **Sizing** — calculates minimum heating capacity (kBTU/hr) and storage volume (gallons) required to meet peak demand
2. **3-Day Design-Day Simulation** — models system performance at 1-minute timesteps over 3 peak-demand days
3. **Annual Simulation** — full-year simulation at 10-minute timesteps for cost/efficiency analysis

## Architecture

### Layer Overview

```
interfaces/          # Public API (EcosizerEngine orchestration, Simulator dispatch)
objects/
  building/          # Building model (occupancy, loads, climate)
  components/        # Equipment: WaterHeater, StorageTank, Controls, PerformanceMap
  dhwsystems/        # DHW piping configurations (base + subclasses)
  simulation/        # SimulationRun (per-timestep output accumulator)
data/
  load_shapes/       # 24-hr normalized DHW demand profiles (JSON) per building type
  climate_data/      # CA climate zone weather data (CSV): temps, zip lookups
  preformanceMaps/   # HPWH performance map pkl files (note: typo in directory name)
```

### Key Classes

**`EcosizerEngine`** (`interfaces/EcosizerEngine.py`) — Top-level orchestrator. Accepts all user-facing parameters and drives the pipeline: `build()` → `size()` → `simulate_3day()` / `simulate_annual()`. Also exposes `get_sizing_results()`, `get_simulation_summary()`, `get_annual_cost_estimate()`, and `plot_sizing_curve()`. Module-level `get_oat_buckets(zip_code, zone_id, weather_station)` convenience function also lives here and is re-exported from the top-level `ecoengine` package (`from ecoengine import get_oat_buckets`).

**`Building`** (`objects/building/Building.py`) — Encapsulates occupancy type, daily DHW demand, 24-hr load shape, and climate data. Key factory: `Building.from_building_type()` supports named types (`multi_family`, `apartment`, `office`, `mens_dorm`, `womens_dorm`, `nursing_home`, `motel`, `food_service_a/b`, `elementary_school`, `junior_high`, `senior_high`) and multi-use blending (weighted mix of types). For `multi_family` with `standard_gpd='ca'`, uses California bedroom-count-based GPD profiles from `multi_family.json`.

**`ClimateZone`** (`objects/building/ClimateZone.py`) — Stores hourly OAT (8,760 values) and monthly inlet water temps (12 values). Factory constructors: `from_zip_code()`, `from_zone_id()`, `from_weather_station()`, `from_design_conditions()`. Key methods: `get_oat_f(timestep, interval_min)`, `get_inlet_water_temp_f(timestep, interval_min)`, `get_design_oat_f()`, `get_design_inlet_water_temp_f()`, `get_oat_buckets()` (365 daily averages bucketed into 5°F bins).

**`DHWSystem`** (`objects/dhwsystems/DHWSystem.py`) — Base class for all piping configurations. Fully implemented. Key public methods: `size()`, `get_sizing_curve()`, `get_ls_sizing_curve()`, `plot_sizing_curve()`, `simulate_step()`, `check_for_outage()`. Factory classmethods: `from_size()` (post-sizing shortcut), `from_components()` (direct construction). Subclass hierarchy:
- `InstantWHSystem` — tankless, no storage
- `MPNoRecircSystem` — multi-pass, no recirculation
- `RecircSystem` → `ParallelLoopSystem`, `SwingSystem` — systems with recirc loops
  - `SwingSystem` → `SwingERTrdOffSystem` — ER trade-off variant; adds `get_er_sized_points(building)` and `get_er_sizing_curve(building)` which iterate building load from 120%→0% to produce a Plotly slider figure of ER element size vs. percent coverage
- `RTPSystem` → `SinglePassRTPSystem`, `MultiPassRTPSystem`, `SP_RTPInParallelSystem`, `SP_RTPInSeriesSystem`, `MP_RTPInSeriesSystem` — Return-to-Primary systems

**`StorageTank`** (`objects/components/storage/StorageTank.py`) — Abstract base class. `StratifiedTank` subclass implements a 12-node model. `MixedStorageTank` subclass uses a single fully-mixed node. Key methods: `initialize()`, `draw()`, `heat()`, `add_recirc_return()`, `get_usable_volume_supplyT_gal()`, `get_stratification_factor()`.

**`WaterHeater`** (`objects/components/heating/WaterHeater.py`) — Single HPWH unit with on/off state. Factory classmethods: `from_nominal_capacity()`, `from_model_name()`. Backed by `PerformanceMap` for capacity/power lookup and `Controls` for temperature setpoints. Key methods: `update_state()`, `get_capacity_kbtuh()`, `get_power_in_kw()`, `get_output_kbtuh()`.

**`PerformanceMap`** (`objects/components/heating/PerformanceMap.py`) — Abstract base with three concrete subclasses:
- `NominalPerformanceMap` — constant capacity, no OAT/temp dependence
- `PklPerformanceMap` — interpolates from a pickled 3-D grid (OAT × inlet_temp × outlet_temp); data lives in `data/preformanceMaps/pkls/`
- `HPWHsimPerformanceMap` — polynomial curve-fit model using quadratic + linear coefficients

**`Controls`** (`objects/components/heating/Controls.py`) — Holds on/off temperature setpoints for a single operating schedule block (e.g., load-up, normal, shed). A `control_map` is a `dict[str, Controls]` keyed by schedule label (e.g., `"normal"`, `"load_up"`, `"shed"`).

**`SimulationRun`** (`objects/simulation/SimulationRun.py`) — Accumulates per-timestep outputs. Key methods: `record_timestep()`, `record_outage()`, `is_successful()`, `get_summary()`, `get_total_energy_kwh()`, `get_peak_demand_kw()`, `to_csv()`, `to_plotly()`, `get_annual_utility_cost()`, `get_monthly_cost_breakdown()`.

**`Simulator`** (`interfaces/Simulator.py`) — Module-level functions: `simulate(dhw_system, building, duration)`, `simulate_3day()`, `simulate_annual()`.

### Important Patterns and Gotchas

**`_sizing_strat_slope` pattern** — After `DHWSystem.size()` (and `SwingSystem.size()`) runs, it stores `self._sizing_strat_slope = strat_slope`. The `get_sizing_curve()` and `get_ls_sizing_curve()` methods read this back via `getattr(self, "_sizing_strat_slope", strat_slope)` so the curve always uses the same slope that sizing used. SPRTP uses `strat_slope=1.7`; base class defaults to `2.8`.

**`control_map` from the object, not the caller** — `get_sizing_curve()` reads `_cmap = self.water_heaters[0].control_map if self.water_heaters else None` rather than accepting `control_map` as a parameter. This ensures the correct stratification factor is always computed. Same pattern should be applied if any new sizing methods need the control map.

**`SwingSystem` call order** — In `SwingSystem`, `_calc_running_volume_supplyT_gal()` must be called *before* `_calc_required_capacity()` because the former sets `self._eff_mix_fraction` which the latter uses. The base class `get_sizing_curve()` calls them in the wrong order for Swing, so `SwingSystem` overrides `get_sizing_curve()` to enforce the correct order.

**`_calc_running_volume_ls_supplyT_gal()` override in `SwingSystem`** — The base class LS volume method is generic. `SwingSystem` overrides it to delegate to `_calc_running_volume_ls_swing()` (which accounts for swing tank thermal mass). The override returns just the volume from the `(volume, eff_mix_fraction)` tuple.

**`SwingSystem` CA TM volume** — After `size()`, `get_minimum_tm_ca_volume_gal()` returns the TM volume snapped to the CA commercially-available tank size table `[80, 96, 168, 288, 480]` gal (capped at 480 when standard sizing exceeds it). The standard sizing table is `_SWING_SIZING_TABLE`; the CA table is `_SWING_SIZING_TABLE_CA`, both in `SwingSystem.py`.

**`RTPSystem` LS recirc capacity** — `RTPSystem` overrides `_calc_required_capacity_ls_kbtuh()` to add the same recirc loss contribution (`recirc_loss × 24 / max_daily_run_hr / defrost`) that `_calc_required_capacity()` adds for the non-LS path. Without this override, LS sizing underestimates capacity for all RTP system variants.

**`SwingERTrdOffSystem` ER curve — `daily_dhw_use_supplyT_gal` scaling** — `get_er_sized_points()` temporarily scales `building.daily_dhw_use_supplyT_gal` (not a `magnitude` attribute, which does not exist on `Building`) to simulate different load fractions, then restores it. The same pattern should be used if any other method needs to probe the system at a fraction of the building load.

**`get_oat_buckets()` skips header** — The old codebase had a bug where the CSV header row was not skipped, shifting one day's bucket assignment. The new implementation correctly skips the header. Do not try to replicate the old behavior.

**`interval_min` parameter convention** — Many methods on `Building`, `ClimateZone`, and `DHWSystem` take `(timestep_interval, interval_min=1)` where `timestep_interval` is the count of elapsed intervals and `interval_min` is the length of each interval in minutes. Actual elapsed minutes = `timestep_interval * interval_min`.

### Data Flow

```
User parameters
    → EcosizerEngine.build()
        → Building (from_building_type or direct)
        → DHWSystem (with WaterHeater + StorageTank + Controls)
    → EcosizerEngine.size()
        → DHWSystem.size() → stores _minimum_capacity_kbtuh, _minimum_storage_storageT_gal, _sizing_strat_slope
    → EcosizerEngine.simulate_3day() / simulate_annual()
        → Simulator.simulate() loop
            → Building.get_dhw_load_supplyT_gal(t, interval_min)
            → ClimateZone.get_oat_f(t, interval_min)
            → DHWSystem.simulate_step(demand, oat, ...)
                → Controls.should_turn_on/off()
                → WaterHeater.update_state(storage_tank, hour_of_day)
                → StorageTank.draw() / heat() / add_recirc_return()
                → SimulationRun.record_timestep()
    → EcosizerEngine.get_simulation_summary() / get_annual_cost_estimate()
```

### Units Convention

- Temperature: °F throughout
- Volume: gallons (gal), flow in GPM
- Capacity: kBTU/hr
- Power: kW
- Energy: kWh (or kBTU for heat)
- Storage volume sizing: specified at storage temperature (storageT), demand volumes at supply temperature (supplyT)

## Implementation Status

**All classes are fully implemented.** The codebase is feature-complete with 257 passing tests.

Implemented components: `EcosizerEngine`, `Simulator`, `Building`, `ClimateZone`, `UtilityCostTracker`, `WaterHeater`, `Controls`, `PerformanceMap` (+ `NominalPerformanceMap`, `PklPerformanceMap`, `HPWHsimPerformanceMap`), `StorageTank` (+ `StratifiedTank`, `MixedStorageTank`), `DHWSystem` and all subclasses, `SimulationRun`.

## Common Extension Points

- **New building type:** Add a JSON load shape to `src/ecoengine/data/load_shapes/`, add an entry to `_ASHRAE_GPD_PER_UNIT` in `Building.py`, and register the type name in `from_building_type()`.
- **New DHW system schematic:** Subclass `DHWSystem` (or `RecircSystem`/`RTPSystem`), implement `size()` and `simulate_step()`. If sizing uses a non-default `strat_slope`, store it as `self._sizing_strat_slope` at the end of `size()`.
- **New performance map model:** Subclass `PerformanceMap`, implement `get_capacity_kbtuh()`, `get_power_in_kw()`, and `is_within_operating_bounds()`.
