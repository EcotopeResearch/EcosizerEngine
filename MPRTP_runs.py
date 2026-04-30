"""
Size and simulate a MultiPassRTPSystem across a range of building magnitudes.

Outputs all simulation graphs (successful or not) to MPRTP_runs.html.
Each graph is preceded by a summary block showing building specs, sizing
results, and control setpoints.

Run:
    python MPRTP_runs.py
"""

from ecoengine.objects.building.Building import Building
from ecoengine.objects.building.ClimateZone import ClimateZone
from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.dhwsystems.rtp_systems.MultiPassRTPSystem import MultiPassRTPSystem
from ecoengine.interfaces.Simulator import simulate_3day

OUTPUT = "MPRTP_runs.html"

# ---------------------------------------------------------------------------
# Shared configuration
# ---------------------------------------------------------------------------
SUPPLY_T_F   = 120.0
STORAGE_T_F  = 150.0
RETURN_T_F   = 110.0
RETURN_GPM   = 7.0
GPDPP        = 25.0
DESIGN_OAT   = 35.0
DESIGN_INLET = 50.0

CTRL = Controls(
    on_sensor_fract  = 0.4,
    on_trigger_t_f   = 115.0,
    off_sensor_fract = 0.1,
    off_trigger_t_f  = 135.0,
    outlet_temp_f    = STORAGE_T_F,
)

MAGNITUDES = [50, 100, 200, 6000]

# ---------------------------------------------------------------------------
# HTML info block rendered before each chart
# ---------------------------------------------------------------------------

def _info_block_html(magnitude: int, daily_gal: float, cap_kbtuh: float,
                     vol_gal: float, summary: dict, ctrl: Controls) -> str:
    success     = summary["successful"]
    outage_min  = summary["total_outage_min"]
    stopped     = summary["stopped_early"]
    steps       = summary["num_steps_recorded"]
    accent      = "#1a7a1a" if success else "#c00000"
    status_text = "PASSED" if success else "FAILED"

    outage_note = ""
    if outage_min > 0:
        outage_note = f"&nbsp;&nbsp;·&nbsp;&nbsp;{outage_min} min outage"
    if stopped:
        outage_note += "&nbsp;&nbsp;·&nbsp;&nbsp;stopped early"

    return f"""
<div style="font-family: Arial, sans-serif; background: #f8f8f8;
            border-left: 5px solid {accent}; padding: 14px 20px;
            margin: 48px 0 6px 0; border-radius: 0 4px 4px 0;">
  <h3 style="margin: 0 0 10px 0; font-size: 1.05em; color: #222;">
    {magnitude}-Person Multi-Family&nbsp;&nbsp;
    <span style="color:{accent}; font-weight:bold;">{status_text}</span>
    <span style="font-weight:normal; color:#666;">{outage_note}</span>
  </h3>
  <table style="border-collapse:collapse; font-size:0.88em; line-height:1.6;">
    <tr>
      <td style="padding:1px 18px 1px 0; font-weight:bold; color:#555;
                 white-space:nowrap;">Building</td>
      <td>multi_family &nbsp;·&nbsp; {magnitude} people &nbsp;·&nbsp;
          {GPDPP:.0f} GPD/person &nbsp;·&nbsp; {daily_gal:,.0f} gal/day total</td>
    </tr>
    <tr>
      <td style="padding:1px 18px 1px 0; font-weight:bold; color:#555;">Climate</td>
      <td>Design OAT {DESIGN_OAT:.0f} °F &nbsp;·&nbsp;
          Design inlet water {DESIGN_INLET:.0f} °F</td>
    </tr>
    <tr>
      <td style="padding:1px 18px 1px 0; font-weight:bold; color:#555;">Recirc</td>
      <td>{RETURN_GPM:.0f} GPM return flow &nbsp;·&nbsp;
          {RETURN_T_F:.0f} °F return temp</td>
    </tr>
    <tr>
      <td style="padding:1px 18px 1px 0; font-weight:bold; color:#555;">Controls</td>
      <td>On-sensor {ctrl.on_sensor_fract:.0%} @ {ctrl.on_trigger_t_f:.0f} °F
          &nbsp;·&nbsp;
          Off-sensor {ctrl.off_sensor_fract:.0%} @ {ctrl.off_trigger_t_f:.0f} °F
          &nbsp;·&nbsp;
          Outlet setpoint {ctrl.outlet_temp_f:.0f} °F</td>
    </tr>
    <tr>
      <td style="padding:1px 18px 1px 0; font-weight:bold; color:#555;">Sizing</td>
      <td>{cap_kbtuh:.1f} kBTU/hr capacity &nbsp;·&nbsp;
          {vol_gal:.0f} gal primary storage
          &nbsp;·&nbsp;
          {SUPPLY_T_F:.0f} °F supply / {STORAGE_T_F:.0f} °F storage</td>
    </tr>
    <tr>
      <td style="padding:1px 18px 1px 0; font-weight:bold; color:#555;">Simulation</td>
      <td>{steps:,} timesteps recorded (3-day · 1-min steps)</td>
    </tr>
  </table>
</div>
"""


# ---------------------------------------------------------------------------
# Run scenarios
# ---------------------------------------------------------------------------
cz = ClimateZone.from_design_conditions(
    design_oat_f              = DESIGN_OAT,
    design_inlet_water_temp_f = DESIGN_INLET,
)
ctrl_map = {"normal": CTRL}

html_parts: list[str] = []

for mag in MAGNITUDES:
    print(f"Building {mag:>4} people  sizing...", end=" ", flush=True)

    building = Building.from_building_type(
        "multi_family",
        magnitude    = mag,
        gpdpp        = GPDPP,
        climate_zone = cz,
    )

    system = MultiPassRTPSystem.from_size(
        building         = building,
        supply_temp_f    = SUPPLY_T_F,
        storage_temp_f   = STORAGE_T_F,
        return_temp_f    = RETURN_T_F,
        return_flow_gpm  = RETURN_GPM,
        control_schedule = ["normal"] * 24,
        control_map      = ctrl_map,
        percent_useable= 0.9
    )

    cap = system._minimum_capacity_kbtuh
    vol = system._minimum_storage_storageT_gal
    daily_gal = building.daily_dhw_use_supplyT_gal

    print(f"cap={cap:.0f} kBTU/hr  vol={vol:.0f} gal  simulating...", end=" ", flush=True)

    sim     = simulate_3day(system, building)
    summary = sim.get_summary()

    status  = "SUCCESS" if summary["successful"] else (
        f"FAILED (outage={summary['total_outage_min']} min"
        + (", stopped early" if summary["stopped_early"] else "")
        + ")"
    )
    print(status)

    title = (
        f"MPRTP 3-Day Simulation — {mag}-Person Multi-Family  |  "
        f"{SUPPLY_T_F:.0f}°F supply / {STORAGE_T_F:.0f}°F storage  |  "
        f"{cap:.0f} kBTU/hr · {vol:.0f} gal"
        + ("  [FAILED]" if not summary["successful"] else "")
    )

    fig = sim.to_plotly(title=title, include_temperatures=True)

    include_js = "cdn" if not html_parts else False
    fig_html   = fig.to_html(full_html=False, include_plotlyjs=include_js)

    html_parts.append(_info_block_html(mag, daily_gal, cap, vol, summary, CTRL))
    html_parts.append(fig_html)


# ---------------------------------------------------------------------------
# Write combined HTML
# ---------------------------------------------------------------------------
with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("<!DOCTYPE html>\n<html>\n<head>\n")
    f.write("  <meta charset='utf-8'>\n")
    f.write("  <title>Multi-Pass RTP — Sizing &amp; Simulation Runs</title>\n")
    f.write("  <style>body{margin:24px 48px;background:#fff;}</style>\n")
    f.write("</head>\n<body>\n")
    f.write("<h1 style='font-family:Arial;color:#222;margin-bottom:4px;'>"
            "Multi-Pass RTP System — Sizing &amp; Simulation</h1>\n")
    f.write(f"<p style='font-family:Arial;color:#666;font-size:0.9em;margin-top:0;'>"
            f"Building type: multi_family &nbsp;·&nbsp; "
            f"{GPDPP:.0f} GPD/person &nbsp;·&nbsp; "
            f"Supply {SUPPLY_T_F:.0f}°F / Storage {STORAGE_T_F:.0f}°F &nbsp;·&nbsp; "
            f"Recirc {RETURN_GPM:.0f} GPM @ {RETURN_T_F:.0f}°F return &nbsp;·&nbsp; "
            f"Design OAT {DESIGN_OAT:.0f}°F / Inlet {DESIGN_INLET:.0f}°F"
            f"</p>\n")
    f.write("\n".join(html_parts))
    f.write("\n</body>\n</html>\n")

print(f"\nSaved: {OUTPUT}")
