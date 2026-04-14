"""
Undersized system demo — shows what a failed 3-day simulation looks like.

Uses from_components() to manually specify a system that is intentionally
undersized relative to the peak load, so the tank runs out within the first
few hours of the design day.

Building: 400-person multi-family (same as demo_3day_sim.py)
Sizing: ~88% of the minimum capacity and storage derived from from_size()
    Correct sizing:    407 kBTU/hr,  2259 gal
    This demo:         360 kBTU/hr,  2000 gal  (~88%)

Output: simulation_failed.html
"""

from ecoengine.objects.building.Building import Building
from ecoengine.objects.building.ClimateZone import ClimateZone
from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.dhwsystems.DHWSystem import DHWSystem
from ecoengine.interfaces.Simulator import simulate_3day

# ---------------------------------------------------------------------------
# Building (identical to demo_3day_sim.py)
# ---------------------------------------------------------------------------
INLET_T_F   = 47.0
SUPPLY_T_F  = 125.0
STORAGE_T_F = 150.0
N_PEOPLE    = 400
GPDPP       = 25.0
DESIGN_OAT  = 47.0

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
# Controls (same as demo_3day_sim.py)
# ---------------------------------------------------------------------------
normal_controls = Controls(
    on_sensor_fract  = 0.4,
    on_trigger_t_f   = 120.0,
    off_sensor_fract = 0.2,
    off_trigger_t_f  = 140.0,
    outlet_temp_f    = STORAGE_T_F,
)

control_schedule = ["normal"] * 24
control_map      = {"normal": normal_controls}

# ---------------------------------------------------------------------------
# Manually build an undersized system via from_components()
# Correct minimum: ~407 kBTU/hr, ~2259 gal
# Undersized to:   ~305 kBTU/hr, ~1700 gal  (75%)
# ---------------------------------------------------------------------------
CAPACITY_KBTUH  = 360.0
STORAGE_GAL     = 2000.0

heater = WaterHeater.from_nominal_capacity(
    nominal_capacity_kbtuh = CAPACITY_KBTUH,
    control_schedule       = control_schedule,
    control_map            = control_map,
)

system = DHWSystem.from_components(
    storage_volume_storageT_gal = STORAGE_GAL,
    water_heaters               = [heater],
    supply_temp_f               = SUPPLY_T_F,
    storage_temp_f              = STORAGE_T_F,
)

cap_kw = CAPACITY_KBTUH * 1000 / 3412.14
print(f"Undersized system: {CAPACITY_KBTUH:.0f} kBTU/hr ({cap_kw:.1f} kW), {STORAGE_GAL:.0f} gal storage")
print("(Correct minimum: ~407 kBTU/hr, ~2259 gal -- this system is ~88%)")

# ---------------------------------------------------------------------------
# 3-day simulation
# ---------------------------------------------------------------------------
print("Running 3-day simulation...", end=" ", flush=True)

result = simulate_3day(system, building)

print("done.")
summary = result.get_summary()
print(f"  Successful:      {summary['successful']}")
print(f"  Stopped early:   {summary['stopped_early']}")
print(f"  Outage minutes:  {summary['total_outage_min']} ({summary['total_outage_min']/60:.1f} hours)")
print(f"  Min usable vol:  {min(result.usable_volume_supplyT_gal):.1f} gal")
print(f"  Max usable vol:  {max(result.usable_volume_supplyT_gal):.1f} gal")
heater_pct = 100.0 * sum(1 for x in result.heater_output_kbtuh if x > 0) / len(result.heater_output_kbtuh)
print(f"  Heater on:       {heater_pct:.1f}% of timesteps")

# ---------------------------------------------------------------------------
# Export Plotly HTML
# ---------------------------------------------------------------------------
OUTPUT_HTML = "simulation_failed.html"

fig = result.to_plotly(
    title    = (
        f"3-Day Simulation (UNDERSIZED) — {N_PEOPLE}-Person Multi-Family  |  "
        f"{SUPPLY_T_F:.0f} F supply / {STORAGE_T_F:.0f} F storage  |  "
        f"Cap {CAPACITY_KBTUH:.0f} kBTU/hr (~75%), Storage {STORAGE_GAL:.0f} gal (~75%)  |  "
        f"Outage: {summary['total_outage_min']} min ({summary['total_outage_min']/60:.1f} hr)"
    ),
    filepath = OUTPUT_HTML,
)

print(f"\nPlot saved: {OUTPUT_HTML}")
print("Open it in any browser to view the interactive chart.")
