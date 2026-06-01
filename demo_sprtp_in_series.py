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

Output:
    sprtp_in_series_all.html  — all scenarios in one file, top to bottom
"""

from ecoengine.objects.building.Building import Building
from ecoengine.objects.building.ClimateZone import ClimateZone
from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.storage.EnergyTank import EnergyTank
from ecoengine.objects.dhwsystems.rtp_systems.SinglePassRTPSystem import SinglePassRTPSystem, _SPRTP_STRAT_SLOPE
from ecoengine.objects.dhwsystems.rtp_systems.SP_RTPInSeriesSystem import SP_RTPInSeriesSystem, _GAS_DEADBAND_F
from ecoengine.interfaces.Simulator import simulate_3day
from ecoengine.constants.constants import _RHO_CP

OUTPUT_FILE = "sprtp_in_series_all.html"

# ---------------------------------------------------------------------------
# Shared parameters
# ---------------------------------------------------------------------------
DESIGN_OAT_F   = 47.0
DESIGN_INLET_F = 55.0
SUPPLY_T_F     = 120.0
STORAGE_T_F    = 140.0
RETURN_T_F     = 100.0
RETURN_GPM     = 3.0


def _zone() -> ClimateZone:
    return ClimateZone.from_design_conditions(
        design_oat_f=DESIGN_OAT_F,
        design_inlet_water_temp_f=DESIGN_INLET_F,
    )


def _normal_controls() -> Controls:
    return Controls(
        on_sensor_fract=0.4,
        on_trigger_t_f=SUPPLY_T_F,
        off_sensor_fract=0.2,
        off_trigger_t_f=STORAGE_T_F - 10.0,
        outlet_temp_f=STORAGE_T_F,
    )


def _full_sprtp_sizing(building: Building) -> tuple[float, float, SinglePassRTPSystem]:
    """Return (min_capacity_kbtuh, min_storage_gal, sized_system) for a fully-sized SPRTP."""
    system = SinglePassRTPSystem.from_size(
        building=building,
        supply_temp_f=SUPPLY_T_F,
        storage_temp_f=STORAGE_T_F,
        return_temp_f=RETURN_T_F,
        return_flow_gpm=RETURN_GPM,
        control_schedule=["normal"] * 24,
        control_map={"normal": _normal_controls()},
    )
    return system._minimum_capacity_kbtuh, system._minimum_storage_storageT_gal, system


def run_scenario(
    building_type: str,
    magnitude: int,
    primary_fraction: float,
    label: str,
) -> str:
    """Size, simulate, and return an HTML div string for this scenario."""
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
    full_cap_kbtuh, full_vol_gal, sprtp_system = _full_sprtp_sizing(building)
    nominal_cap_kbtuh = full_cap_kbtuh * primary_fraction
    nominal_vol_gal   = full_vol_gal   * primary_fraction
    print(f"  Full SPRTP:    {full_cap_kbtuh:.1f} kBTU/hr, {full_vol_gal:.0f} gal")
    print(f"  Primary cap:   {nominal_cap_kbtuh:.1f} kBTU/hr ({primary_fraction:.0%} of full)")
    print(f"  Primary vol:   {nominal_vol_gal:.0f} gal ({primary_fraction:.0%} of full)")

    # --- size in-series system ---
    print("  Sizing gas backup...", end=" ", flush=True)
    system = SP_RTPInSeriesSystem.from_size(
        building=building,
        supply_temp_f=SUPPLY_T_F,
        storage_temp_f=STORAGE_T_F,
        return_temp_f=RETURN_T_F,
        return_flow_gpm=RETURN_GPM,
        nominal_capacity_kbtuh=nominal_cap_kbtuh,
        nominal_storage_gal=nominal_vol_gal,
        control_schedule=["normal"] * 24,
        control_map={"normal": _normal_controls()},
    )
    gas_cap = system.gas_water_heater.get_capacity_kbtuh(DESIGN_OAT_F, SUPPLY_T_F + _GAS_DEADBAND_F)
    gas_vol = system.gas_storage_tank.total_volume_gal
    print("done.")
    print(f"  Gas heater:    {gas_cap:.1f} kBTU/hr")
    print(f"  Gas tank:      {gas_vol:.0f} gal")

    # --- simulate ---
    print("  Simulating 3-day...", end=" ", flush=True)
    sim = simulate_3day(system, building)
    print("done.")
    status = "PASS" if sim.is_successful() else f"FAIL — {sim.get_failure_message()}"
    print(f"  Result:        {status}")

    # --- build specs table ---
    daily_gal = building.daily_dhw_use_supplyT_gal
    inlet_temp_f       = building.get_design_inlet_water_temp_f()
    recirc_loss_kbtuh  = system.get_recirc_loss_kbtuh()
    recirc_daily_kbtu  = recirc_loss_kbtuh * 24.0
    daily_load_kbtu    = daily_gal * _RHO_CP * (SUPPLY_T_F - inlet_temp_f) / 1000.0
    recirc_pct         = recirc_daily_kbtu / daily_load_kbtu * 100.0
    result_style = "color:#2a7a2a;font-weight:bold" if sim.is_successful() else "color:#b00;font-weight:bold"
    specs_html = f"""
<div style="font-family:sans-serif;margin:24px 0 8px 0;">
  <h2 style="margin:0 0 8px 0;">{label}</h2>
  <table style="border-collapse:collapse;font-size:14px;">
    <tr style="background:#f0f0f0;">
      <th colspan="2" style="padding:6px 16px;text-align:left;border:1px solid #ccc;">Building</th>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Type</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{building_type.replace("_"," ").title()}</td>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Magnitude</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{magnitude}</td>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Daily DHW demand</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{daily_gal:,.0f} gal/day at {SUPPLY_T_F:.0f}°F</td>
    </tr>
    <tr style="background:#f0f0f0;">
      <th colspan="2" style="padding:6px 16px;text-align:left;border:1px solid #ccc;">Recirculation loop</th>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Flow / ΔT</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{RETURN_GPM:.1f} GPM, {SUPPLY_T_F:.0f}°F → {RETURN_T_F:.0f}°F ({SUPPLY_T_F - RETURN_T_F:.0f}°F drop)</td>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Loss rate</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{recirc_loss_kbtuh:.1f} kBTU/hr</td>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Daily recirc loss</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{recirc_daily_kbtu:,.0f} kBTU/day ({recirc_pct:.1f}% of daily DHW heating load)</td>
    </tr>
    <tr style="background:#f0f0f0;">
      <th colspan="2" style="padding:6px 16px;text-align:left;border:1px solid #ccc;">Full SPRTP sizing (reference)</th>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Capacity</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{full_cap_kbtuh:.1f} kBTU/hr</td>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Storage</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{full_vol_gal:.0f} gal at {STORAGE_T_F:.0f}°F</td>
    </tr>
    <tr style="background:#f0f0f0;">
      <th colspan="2" style="padding:6px 16px;text-align:left;border:1px solid #ccc;">Primary HPWH ({primary_fraction:.0%} of full)</th>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Capacity</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{nominal_cap_kbtuh:.1f} kBTU/hr</td>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Storage</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{nominal_vol_gal:.0f} gal at {STORAGE_T_F:.0f}°F</td>
    </tr>
    <tr style="background:#f0f0f0;">
      <th colspan="2" style="padding:6px 16px;text-align:left;border:1px solid #ccc;">Gas backup (auto-sized)</th>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Capacity</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{gas_cap:.1f} kBTU/hr</td>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Storage</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{gas_vol:.0f} gal at {SUPPLY_T_F + _GAS_DEADBAND_F:.0f}°F</td>
    </tr>
    <tr style="background:#f0f0f0;">
      <th colspan="2" style="padding:6px 16px;text-align:left;border:1px solid #ccc;">Simulation result</th>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">3-day sim</td>
      <td style="padding:4px 16px;border:1px solid #ccc;{result_style}">{status}</td>
    </tr>
  </table>
</div>
"""

    # --- plotly chart ---
    title = (
        f"SP RTP In-Series — {label}  |  "
        f"Primary: {nominal_cap_kbtuh:.0f} kBTU/hr / {nominal_vol_gal:.0f} gal  |  "
        f"Gas: {gas_cap:.0f} kBTU/hr / {gas_vol:.0f} gal"
    )
    fig = sim.to_plotly(title=title, include_temperatures=True)
    chart_div = fig.to_html(full_html=False, include_plotlyjs=False)

    # --- gas backup sizing curve ---
    sizing_curve_title = f"Gas Backup Sizing Curve — {label}"
    sizing_curve_fig = system.get_sizing_curve()
    sizing_curve_fig.update_layout(title=sizing_curve_title)
    sizing_curve_div = sizing_curve_fig.to_html(full_html=False, include_plotlyjs=False)

    # --- undersized SPRTP alone (no gas backup, early-stop disabled) ---
    print("  Simulating undersized SPRTP alone...", end=" ", flush=True)
    undersized_sprtp = SinglePassRTPSystem(
        water_heaters=[WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=nominal_cap_kbtuh,
            control_schedule=["normal"] * 24,
            control_map={"normal": _normal_controls()},
        )],
        storage_tank=EnergyTank(
            total_volume_gal=nominal_vol_gal,
            cold_temp_f=building.get_design_inlet_water_temp_f(),
            storage_temp_f=STORAGE_T_F,
            strat_slope=_SPRTP_STRAT_SLOPE,
        ),
        supply_temp_f=SUPPLY_T_F,
        storage_temp_f=STORAGE_T_F,
        return_temp_f=RETURN_T_F,
        return_flow_gpm=RETURN_GPM,
    )
    undersized_sim = simulate_3day(undersized_sprtp, building, outlet_deficit_threshold_f=9999.0)
    print("done.")
    undersized_status = "PASS" if undersized_sim.is_successful() else f"FAIL — {undersized_sim.get_failure_message()}"
    print(f"  Undersized result: {undersized_status}")

    undersized_result_style = "color:#2a7a2a;font-weight:bold" if undersized_sim.is_successful() else "color:#b00;font-weight:bold"
    undersized_header_html = f"""
<div style="font-family:sans-serif;margin:24px 0 8px 0;">
  <h2 style="margin:0 0 8px 0;">{label} — Undersized Primary HPWH Only ({primary_fraction:.0%} of full, no gas backup)</h2>
  <table style="border-collapse:collapse;font-size:14px;">
    <tr style="background:#f0f0f0;">
      <th colspan="2" style="padding:6px 16px;text-align:left;border:1px solid #ccc;">Primary HPWH ({primary_fraction:.0%} of full)</th>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Capacity</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{nominal_cap_kbtuh:.1f} kBTU/hr</td>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Storage</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{nominal_vol_gal:.0f} gal at {STORAGE_T_F:.0f}°F</td>
    </tr>
    <tr style="background:#f0f0f0;">
      <th colspan="2" style="padding:6px 16px;text-align:left;border:1px solid #ccc;">Simulation result</th>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">3-day sim (no early-stop)</td>
      <td style="padding:4px 16px;border:1px solid #ccc;{undersized_result_style}">{undersized_status}</td>
    </tr>
  </table>
</div>
"""
    undersized_title = (
        f"Undersized SPRTP alone — {label}  |  "
        f"{nominal_cap_kbtuh:.0f} kBTU/hr / {nominal_vol_gal:.0f} gal  |  no early-stop"
    )
    undersized_fig = undersized_sim.to_plotly(title=undersized_title, include_temperatures=True)
    undersized_chart_div = undersized_fig.to_html(full_html=False, include_plotlyjs=False)

    # --- reference: full SinglePassRTPSystem ---
    print("  Simulating reference SPRTP...", end=" ", flush=True)
    sprtp_sim = simulate_3day(sprtp_system, building)
    print("done.")
    sprtp_status = "PASS" if sprtp_sim.is_successful() else f"FAIL — {sprtp_sim.get_failure_message()}"
    print(f"  SPRTP result:  {sprtp_status}")

    sprtp_result_style = "color:#2a7a2a;font-weight:bold" if sprtp_sim.is_successful() else "color:#b00;font-weight:bold"
    sprtp_specs_html = f"""
<div style="font-family:sans-serif;margin:24px 0 8px 0;">
  <h2 style="margin:0 0 8px 0;">{label} — Reference SinglePassRTPSystem</h2>
  <table style="border-collapse:collapse;font-size:14px;">
    <tr style="background:#f0f0f0;">
      <th colspan="2" style="padding:6px 16px;text-align:left;border:1px solid #ccc;">Building</th>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Type</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{building_type.replace("_"," ").title()}</td>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Magnitude</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{magnitude}</td>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Daily DHW demand</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{daily_gal:,.0f} gal/day at {SUPPLY_T_F:.0f}°F</td>
    </tr>
    <tr style="background:#f0f0f0;">
      <th colspan="2" style="padding:6px 16px;text-align:left;border:1px solid #ccc;">SinglePassRTPSystem sizing</th>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Capacity</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{full_cap_kbtuh:.1f} kBTU/hr</td>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">Storage</td>
      <td style="padding:4px 16px;border:1px solid #ccc;">{full_vol_gal:.0f} gal at {STORAGE_T_F:.0f}°F</td>
    </tr>
    <tr style="background:#f0f0f0;">
      <th colspan="2" style="padding:6px 16px;text-align:left;border:1px solid #ccc;">Simulation result</th>
    </tr>
    <tr>
      <td style="padding:4px 16px;border:1px solid #ccc;">3-day sim</td>
      <td style="padding:4px 16px;border:1px solid #ccc;{sprtp_result_style}">{sprtp_status}</td>
    </tr>
  </table>
</div>
"""
    sprtp_title = (
        f"SP RTP (Reference) — {label}  |  "
        f"{full_cap_kbtuh:.0f} kBTU/hr / {full_vol_gal:.0f} gal at {STORAGE_T_F:.0f}°F"
    )
    sprtp_fig = sprtp_sim.to_plotly(title=sprtp_title, include_temperatures=True)
    sprtp_chart_div = sprtp_fig.to_html(full_html=False, include_plotlyjs=False)

    return (
        specs_html
        + chart_div
        + sizing_curve_div
        + undersized_header_html
        + undersized_chart_div
        + sprtp_specs_html
        + sprtp_chart_div
    )


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------
SCENARIOS = [
    # (building_type,  magnitude, primary_fraction, label)
    ("multi_family",  100,  0.70, "Multi-Family 100 units"),
    ("multi_family",  200,  0.40, "Multi-Family 200 units"),
    ("multi_family",  400,  0.60, "Multi-Family 400 units"),
    ("multi_family",  600,  0.80, "Multi-Family 600 units"),
    ("motel",          80,  0.70, "Motel 80 rooms"),
    ("elementary_school",1000,  0.70, "elementary_school 100 students"),
    ("junior_high",1000,  0.50, "junior_high 1000 students"),
    ("food_service_a",          800,  0.70, "food_service_a 800 meals"),
]
divs = []
for building_type, magnitude, primary_fraction, label in SCENARIOS:
    divs.append(run_scenario(building_type, magnitude, primary_fraction, label))

# ---------------------------------------------------------------------------
# Write single combined HTML
# ---------------------------------------------------------------------------
DIVIDER = "\n<hr style='margin:48px 0;border:2px solid #aaa;'>\n"

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write("<!DOCTYPE html>\n<html>\n<head>\n")
    f.write("  <meta charset='utf-8'>\n")
    f.write("  <title>SP RTP In-Series — All Scenarios</title>\n")
    f.write("  <script src='https://cdn.plot.ly/plotly-latest.min.js'></script>\n")
    f.write("</head>\n<body style='font-family:sans-serif;max-width:1400px;margin:0 auto;padding:24px;'>\n")
    f.write("  <h1>SP RTP In-Series System — Sizing &amp; 3-Day Simulation</h1>\n")
    f.write(DIVIDER.join(divs))
    f.write("\n</body>\n</html>\n")

print(f"\nSaved: {OUTPUT_FILE}")
print("Open in a browser to view all scenarios.")
