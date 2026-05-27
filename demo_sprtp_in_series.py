"""
SP_RTPInSeriesSystem sizing + 3-day simulation demo.

Each scenario sizes a SinglePassRTPSystem fully, then caps the primary HPWH
at a fraction of that to create deliberate undersizing.  The gas backup water
heater and storage tank are auto-sized by SP_RTPInSeriesSystem._size_gas_backup()
from the 2-day undersized simulation.

Scenarios
---------
  Multi-family 100 units  — 40 % primary
  Multi-family 200 units  — 40 % primary
  Multi-family 400 units  — 40 % primary
  Multi-family 600 units  — 40 % primary
  Apartment    150 units  — 50 % primary
  Motel         80 rooms  — 50 % primary

Run:
    python demo_sprtp_in_series.py

Outputs one HTML per scenario (simulation chart + sizing note).
"""

from ecoengine.objects.building.Building import Building
from ecoengine.objects.building.ClimateZone import ClimateZone
from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.dhwsystems.rtp_systems.SinglePassRTPSystem import SinglePassRTPSystem
from ecoengine.objects.dhwsystems.rtp_systems.SP_RTPInSeriesSystem import SP_RTPInSeriesSystem, _GAS_DEADBAND_F
from ecoengine.interfaces.Simulator import simulate_3day

# ---------------------------------------------------------------------------
# Shared parameters
# ---------------------------------------------------------------------------
DESIGN_OAT_F   = 47.0
DESIGN_INLET_F = 55.0
SUPPLY_T_F     = 120.0
STORAGE_T_F    = 150.0
RETURN_T_F     = 100.0
RETURN_GPM     = 3.0


def _zone() -> ClimateZone:
    return ClimateZone.from_design_conditions(
        design_oat_f=DESIGN_OAT_F,
        design_inlet_water_temp_f=DESIGN_INLET_F,
    )


def _normal_controls() -> Controls:
    return Controls(
        on_sensor_fract=0.5,
        on_trigger_t_f=SUPPLY_T_F,
        off_sensor_fract=0.0,
        off_trigger_t_f=STORAGE_T_F,
        outlet_temp_f=STORAGE_T_F,
    )


def _full_sprtp_sizing(building: Building) -> tuple[float, float]:
    """Return (min_capacity_kbtuh, min_storage_gal) for a fully-sized SPRTP."""
    control_map      = {"normal": _normal_controls()}
    control_schedule = ["normal"] * 24
    system = SinglePassRTPSystem.from_size(
        building=building,
        supply_temp_f=SUPPLY_T_F,
        storage_temp_f=STORAGE_T_F,
        return_temp_f=RETURN_T_F,
        return_flow_gpm=RETURN_GPM,
        control_schedule=control_schedule,
        control_map=control_map,
    )
    return system._minimum_capacity_kbtuh, system._minimum_storage_storageT_gal


def run_scenario(
    building_type: str,
    magnitude: int,
    primary_fraction: float,
    label: str,
    output_file: str,
) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}  (primary fraction = {primary_fraction:.0%})")
    print(f"{'='*60}")

    zone     = _zone()
    building = Building.from_building_type(
        building_type=building_type,
        magnitude=magnitude,
        climate_zone=zone,
    )

    # --- full SPRTP sizing (reference) ---
    full_cap_kbtuh, full_vol_gal = _full_sprtp_sizing(building)
    nominal_cap_kbtuh = full_cap_kbtuh * primary_fraction
    nominal_vol_gal   = full_vol_gal   * primary_fraction
    print(f"  Full SPRTP:    {full_cap_kbtuh:.1f} kBTU/hr, {full_vol_gal:.0f} gal")
    print(f"  Primary cap:   {nominal_cap_kbtuh:.1f} kBTU/hr ({primary_fraction:.0%} of full)")
    print(f"  Primary vol:   {nominal_vol_gal:.0f} gal ({primary_fraction:.0%} of full)")

    # --- size in-series system ---
    print("  Sizing gas backup...", end=" ", flush=True)
    control_map      = {"normal": _normal_controls()}
    control_schedule = ["normal"] * 24
    system = SP_RTPInSeriesSystem.from_size(
        building=building,
        supply_temp_f=SUPPLY_T_F,
        storage_temp_f=STORAGE_T_F,
        return_temp_f=RETURN_T_F,
        return_flow_gpm=RETURN_GPM,
        nominal_capacity_kbtuh=nominal_cap_kbtuh,
        nominal_storage_gal=nominal_vol_gal,
        control_schedule=control_schedule,
        control_map=control_map,
    )
    gas_cap   = system.gas_water_heater.get_capacity_kbtuh(DESIGN_OAT_F, SUPPLY_T_F + _GAS_DEADBAND_F)
    gas_vol   = system.gas_storage_tank.total_volume_gal
    print("done.")
    print(f"  Gas heater:    {gas_cap:.1f} kBTU/hr")
    print(f"  Gas tank:      {gas_vol:.0f} gal")

    # --- initialize gas storage tank (Simulator handles primary; gas is extra) ---
    inlet_temp_f = building.get_design_inlet_water_temp_f()
    system.gas_storage_tank.initialize(
        storage_temp_f=SUPPLY_T_F + _GAS_DEADBAND_F,
        cold_temp_f=inlet_temp_f,
        percent_useable=1.0,
    )

    # --- simulate ---
    print("  Simulating 3-day...", end=" ", flush=True)
    sim = simulate_3day(system, building)
    print("done.")
    status = "PASS" if sim.is_successful() else f"FAIL — {sim.get_failure_message()}"
    print(f"  Result:        {status}")

    # --- plot ---
    title = (
        f"SP RTP In-Series — {label}  |  "
        f"Primary: {nominal_cap_kbtuh:.0f} kBTU/hr / {nominal_vol_gal:.0f} gal  |  "
        f"Gas backup: {gas_cap:.0f} kBTU/hr / {gas_vol:.0f} gal"
    )
    fig = sim.to_plotly(title=title, include_temperatures=True)
    html = fig.to_html(full_html=True, include_plotlyjs="cdn")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved:         {output_file}")


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------
SCENARIOS = [
    # (building_type,  magnitude, primary_fraction, label,                        output)
    ("multi_family",  100,  0.40, "Multi-Family 100 units",  "sprtp_series_mf100.html"),
    ("multi_family",  200,  0.40, "Multi-Family 200 units",  "sprtp_series_mf200.html"),
    ("multi_family",  400,  0.40, "Multi-Family 400 units",  "sprtp_series_mf400.html"),
    ("multi_family",  600,  0.40, "Multi-Family 600 units",  "sprtp_series_mf600.html"),
    ("apartment",     150,  0.50, "Apartment 150 units",     "sprtp_series_apt150.html"),
    ("motel",          80,  0.50, "Motel 80 rooms",          "sprtp_series_motel80.html"),
]

for building_type, magnitude, primary_fraction, label, output_file in SCENARIOS:
    run_scenario(building_type, magnitude, primary_fraction, label, output_file)

print("\nDone. Open any HTML file in a browser to view the simulation chart.")
