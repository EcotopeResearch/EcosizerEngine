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

This project is a clean-room redesign of the original **EcosizerEngine** located at `C:\Users\nolan\Documents\EcosizerEngine\`. When implementing placeholder stubs, reference the original for algorithmic logic and data patterns — but do **not** copy structure blindly; the whole point is the new decomposition into separate components (see Architecture below).

Key mappings from old → new:
- `engine/EcosizerEngine.py` + `engine/SystemCreator.py` + `engine/BuildingCreator.py` → `interfaces/EcosizerEngine.py`
- `objects/SystemConfig.py` → `objects/dhwsystems/DHWSystem.py` (and subclasses)
- `objects/PrefMapTracker.py` → `objects/components/heating_components/PerformanceMap.py`
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
```

### Key Classes and Relationships

**`EcosizerEngine`** (`interfaces/EcosizerEngine.py`) — Top-level orchestrator. Accepts all user-facing parameters and drives the pipeline: `build()` → `size()` → `simulate_3day()` / `simulate_annual()`.

**`Building`** (`objects/building/Building.py`) — Most complete class. Encapsulates occupancy type, daily DHW demand, 24-hr load shape, and climate data. Key factory: `Building.from_building_type()` supports named types (`multi_family`, `apartment`, `office`, `mens_dorm`, `womens_dorm`, `nursing_home`, `motel`, `food_service_a/b`, `elementary_school`, `junior_high`, `senior_high`) and multi-use blending (weighted mix of types). For `multi_family` with `standard_gpd='ca'`, uses California bedroom-count-based GPD profiles from `multi_family.json`.

**`DHWSystem`** (`objects/dhwsystems/DHWSystem.py`) — Base class for all piping configurations. Key methods: `size()`, `simulate_step()`. Subclass hierarchy:
- `InstantWHSystem` — tankless, no storage
- `MPNoRecircSystem` — multi-pass, no recirculation
- `RecircSystem` → `ParallelLoopSystem`, `SwingSystem` — systems with recirc loops
- `RTPSystem` → `SinglePassRTPSystem`, `MultiPassRTPSystem`, `SP_RTPInParallelSystem`, `SP_RTPInSeriesSystem`, `MP_RTPInSeriesSystem` — Return-to-Primary systems

**`StorageTank`** (`objects/components/storage/StorageTank.py`) — 12-node stratified tank model. `MixedStorageTank` subclass uses single-node (fully mixed) assumption.

**`WaterHeater`** (`objects/components/heating/WaterHeater.py`) — Single HPWH unit with on/off state, backed by `PerformanceMap` (capacity/power/COP as functions of OAT and water temp) and `Controls` (temperature sensor triggers, load-up/shed setpoints for demand response).

**`SimulationRun`** (`objects/simulation/SimulationRun.py`) — Accumulates per-timestep outputs (demand, usable volume, heater output, power, OAT, inlet water temp). Provides summary statistics and monthly energy breakdowns.

**`Simulator`** (`interfaces/Simulator.py`) — Module-level functions that drive the simulation loop: `simulate(dhw_system, building, duration)`.

### Data Flow

```
User parameters
    → EcosizerEngine.build()
        → Building (from_building_type or direct)
        → DHWSystem (with WaterHeater + StorageTank + Controls)
    → EcosizerEngine.size()
        → DHWSystem.size() → sizing results dict
    → EcosizerEngine.simulate_3day() / simulate_annual()
        → Simulator.simulate() loop
            → Building.get_dhw_load_supplyT_gal(t)   # demand at timestep t
            → Building.get_oat_f(t)                   # outdoor air temp
            → DHWSystem.simulate_step(demand, oat, ...)
                → Controls.should_turn_on/off()
                → WaterHeater.update_state()
                → StorageTank.draw() / heat()
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

**Complete:** `Building` class and factory, data loading (JSON/CSV), build/test setup.

**Placeholder stubs (body is `pass`):** `EcosizerEngine`, `Simulator`, `ClimateZone`, `UtilityCostTracker`, `WaterHeater`, `Controls`, `PerformanceMap`, `StorageTank`, `MixedStorageTank`, `DHWSystem` and all subclasses, `SimulationRun`.

## Common Extension Points

- **New building type:** Add a JSON load shape to `src/ecoengine/data/load_shapes/`, add an entry to `_ASHRAE_GPD_PER_UNIT` in `Building.py`, and register the type name in `from_building_type()`.
- **New DHW system schematic:** Subclass `DHWSystem` (or `RecircSystem`/`RTPSystem`), implement `size()` and `simulate_step()`.
- **Performance map data:** Implement interpolation in `PerformanceMap.get_capacity_kbtuh()` and `get_power_in_kw()` over OAT × water-temp grid.
