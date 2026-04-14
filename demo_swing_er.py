"""
SwingERTrdOffSystem demo — size from an undersized SwingSystem and simulate.

Workflow:
  1. Size a full SwingSystem to get the minimum-required primary capacity,
     storage volume, and TM (swing tank) volume.
  2. Halve the primary capacity to simulate an intentionally undersized HPWH
     (e.g. real equipment constraint or load-shifting trade-off).
  3. Pass those components to SwingERTrdOffSystem.from_components() which
     keeps all primary/TM volumes unchanged and sizes only the ER element
     needed to close the temperature deficit the undersized primary creates.
  4. Simulate 3 design days and export an interactive Plotly HTML chart.

Building: 200-person multi-family
Temperatures: 50 F inlet / 120 F supply / 150 F storage
Recirc loop: 5 GPM, 10 F drop (return at 110 F)

Output: swing_er_simulation.html
"""

from ecoengine.objects.building.Building import Building
from ecoengine.objects.building.ClimateZone import ClimateZone
from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.dhwsystems.recirc_systems.SwingSystem import SwingSystem
from ecoengine.objects.dhwsystems.recirc_systems.SwingERTrdOffSystem import SwingERTrdOffSystem
from ecoengine.interfaces.Simulator import simulate_3day

# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------
INLET_T_F       = 50.0
SUPPLY_T_F      = 120.0
STORAGE_T_F     = 150.0
RETURN_T_F      = 110.0
RETURN_FLOW_GPM = 5.0
DESIGN_OAT      = 35.0
N_PEOPLE        = 200
GPDPP           = 25.0
TM_SAFETY       = 1.2

zone = ClimateZone.from_design_conditions(
    design_oat_f              = DESIGN_OAT,
    design_inlet_water_temp_f = INLET_T_F,
)
building = Building.from_building_type(
    building_type = "multi_family",
    magnitude     = N_PEOPLE,
    climate_zone  = zone,
    gpdpp         = GPDPP,
)
print(f"Building daily DHW use: {building.daily_dhw_use_supplyT_gal:,.0f} gal/day at supply temp")

# ---------------------------------------------------------------------------
# Step 1: size SwingSystem normally
# ---------------------------------------------------------------------------
normal_controls = Controls(
    on_sensor_fract  = 0.4,
    on_trigger_t_f   = SUPPLY_T_F,
    off_sensor_fract = 0.1,
    off_trigger_t_f  = STORAGE_T_F,
    outlet_temp_f    = STORAGE_T_F,
)
control_map      = {"normal": normal_controls}
control_schedule = ["normal"] * 24

import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    base_swing = SwingSystem.from_size(
        building        = building,
        supply_temp_f   = SUPPLY_T_F,
        storage_temp_f  = STORAGE_T_F,
        return_temp_f   = RETURN_T_F,
        return_flow_gpm = RETURN_FLOW_GPM,
        tm_safety_factor= TM_SAFETY,
        control_schedule= control_schedule,
        control_map     = control_map,
    )

full_cap    = base_swing._minimum_capacity_kbtuh
storage_gal = base_swing._minimum_storage_storageT_gal
tm_vol_gal  = base_swing._minimum_tm_volume_gal
base_tm_cap = base_swing._minimum_tm_capacity_kbtuh

print(f"\nFull SwingSystem sizing:")
print(f"  Primary capacity:  {full_cap:.1f} kBTU/hr  ({full_cap * 1000 / 3412.14:.1f} kW)")
print(f"  Primary storage:   {storage_gal:.0f} gal at {STORAGE_T_F:.0f} F")
print(f"  TM (swing) volume: {tm_vol_gal:.0f} gal")
print(f"  TM base capacity:  {base_tm_cap:.2f} kBTU/hr  ({base_tm_cap * 1000 / 3412.14:.2f} kW)")

# ---------------------------------------------------------------------------
# Step 2: halve primary capacity
# ---------------------------------------------------------------------------
half_cap = full_cap * 0.5
orig_wh  = base_swing.water_heaters[0]
halved_wh = WaterHeater.from_nominal_capacity(
    nominal_capacity_kbtuh = half_cap,
    control_schedule       = orig_wh.control_schedule,
    control_map            = orig_wh.control_map,
)

print(f"\nUndersized primary capacity: {half_cap:.1f} kBTU/hr  ({half_cap * 1000 / 3412.14:.1f} kW)  (50% of full)")

# ---------------------------------------------------------------------------
# Step 3: size ER element via SwingERTrdOffSystem.from_components()
# ---------------------------------------------------------------------------
er_system = SwingERTrdOffSystem.from_components(
    water_heaters             = [halved_wh],
    storage_tank              = base_swing.storage_tank,
    tm_storage_tank           = base_swing.tm_storage_tank,
    initial_tm_capacity_kbtuh = base_tm_cap,
    building                  = building,
    supply_temp_f             = SUPPLY_T_F,
    storage_temp_f            = STORAGE_T_F,
    return_temp_f             = RETURN_T_F,
    return_flow_gpm           = RETURN_FLOW_GPM,
)

er_add_kbtuh = er_system.get_er_capacity_kbtuh()
er_add_kw    = er_system.get_er_capacity_kw()
total_tm_cap = er_system._minimum_tm_capacity_kbtuh

print(f"\nSwingERTrdOffSystem sizing result:")
print(f"  ER addition:       {er_add_kbtuh:.2f} kBTU/hr  ({er_add_kw:.2f} kW)")
print(f"  Total TM capacity: {total_tm_cap:.2f} kBTU/hr  ({total_tm_cap * 1000 / 3412.14:.2f} kW)")
print(f"  (base {base_tm_cap:.2f} + ER {er_add_kbtuh:.2f} = {total_tm_cap:.2f} kBTU/hr)")

# ---------------------------------------------------------------------------
# Step 4: 3-day simulation
# ---------------------------------------------------------------------------
print("\nRunning 3-day simulation...", end=" ", flush=True)
result = simulate_3day(er_system, building)
print("done.")

summary = result.get_summary()
print(f"\nSimulation summary:")
print(f"  Successful:      {summary['successful']}")
print(f"  Stopped early:   {summary['stopped_early']}")
print(f"  Outage minutes:  {summary['total_outage_min']} ({summary['total_outage_min'] / 60:.1f} hr)")
print(f"  Min usable vol:  {min(result.usable_volume_supplyT_gal):.1f} gal")
print(f"  Max usable vol:  {max(result.usable_volume_supplyT_gal):.1f} gal")

# ---------------------------------------------------------------------------
# Step 5: export Plotly HTML
# ---------------------------------------------------------------------------
OUTPUT_HTML = "swing_er_simulation.html"

fig = result.to_plotly(
    title=(
        f"SwingERTrdOffSystem — {N_PEOPLE}-Person Multi-Family  |  "
        f"{SUPPLY_T_F:.0f} F supply / {STORAGE_T_F:.0f} F storage  |  "
        f"Primary {half_cap:.0f} kBTU/hr (50% of full {full_cap:.0f})  |  "
        f"ER addition {er_add_kw:.1f} kW → TM total {total_tm_cap * 1000 / 3412.14:.1f} kW"
    ),
    filepath=OUTPUT_HTML,
)

print(f"\nPlot saved: {OUTPUT_HTML}")
print("Open it in any browser to view the interactive chart.")
