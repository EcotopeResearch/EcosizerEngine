"""
Multi-family HPWH sizing and simulation script.

Fill in your values in the INPUTS section below, then run:
    python run_simulation.py
"""

import sys, os, io, contextlib

# ############################################################
# INPUTS -- edit these values before running
# ############################################################

# --- Building ---
n_people        = 100     # number of occupants
gpdpp           = 25      # gallons per person per day (design day)

# --- Temperatures (deg F) ---
incoming_t_f    = 50      # incoming cold water temperature
supply_t_f      = 120     # hot water delivery temperature
storage_t_f     = 150     # hot water storage temperature

# --- Equipment ---
storage_vol_gal = 500     # primary storage volume at storage temperature (gallons)
capacity_kw     = 30      # water heater output capacity (kW)

# ############################################################

# Make sure the original ecoengine package is importable
_orig_src = os.path.join(os.path.dirname(__file__), "..", "EcosizerEngine", "src")
if os.path.isdir(_orig_src) and _orig_src not in sys.path:
    sys.path.insert(0, _orig_src)

with contextlib.redirect_stdout(io.StringIO()):
    from ecoengine.engine.EcosizerEngine import EcosizerEngine

W_TO_BTUHR = 3.41214


def make_engine(storage_vol_gal=None, capacity_kw=None):
    kwargs = dict(
        incomingT_F    = incoming_t_f,
        magnitudeStat  = n_people,
        supplyT_F      = supply_t_f,
        storageT_F     = storage_t_f,
        percentUseable = 0.9,
        onFract        = 0.4,
        schematic      = "primary",
        buildingType   = "multi_family",
        gpdpp          = gpdpp,
        compRuntime_hr = 16,
        defrostFactor  = 1,
        returnT_F      = None,
        flowRate       = None,
    )
    if storage_vol_gal is not None:
        kwargs["PVol_G_atStorageT"] = storage_vol_gal
    if capacity_kw is not None:
        kwargs["PCap_kW"] = capacity_kw
    with contextlib.redirect_stdout(io.StringIO()):
        return EcosizerEngine(**kwargs)


def main():
    capacity_kbtuh = capacity_kw * W_TO_BTUHR

    print("=" * 60)
    print("  EcosizerEngine  --  Multi-Family HPWH Simulation")
    print("  System: Primary (no recirculation)")
    print("=" * 60)
    print(f"\n  Occupants:       {n_people}  |  {gpdpp} gal/person/day")
    print(f"  Temperatures:    {incoming_t_f} cold / {supply_t_f} supply / {storage_t_f} storage  (deg F)")
    print(f"  Your equipment:  {storage_vol_gal} gal storage  |  {capacity_kw} kW")

    # --- Minimum sizing ---
    print("\n--- Sizing ---")
    print("  Computing minimum sizing requirements...", end=" ", flush=True)
    try:
        engine_min = make_engine()
    except Exception as e:
        print(f"\n  ERROR: {e}")
        return

    min_vol_gal, min_cap_kbtuh = engine_min.getSizingResults()
    min_cap_kw = min_cap_kbtuh / W_TO_BTUHR
    print("done.")

    print(f"\n  Minimum storage (at storage temp):  {min_vol_gal:.0f} gal")
    print(f"  Minimum heating capacity:           {min_cap_kbtuh:.1f} kBTU/hr  ({min_cap_kw:.1f} kW)")

    vol_ok = storage_vol_gal >= min_vol_gal
    cap_ok = capacity_kbtuh  >= min_cap_kbtuh
    print(f"\n  Your storage:   {storage_vol_gal:.0f} gal  -> " +
          ("OK" if vol_ok else f"BELOW MINIMUM by {min_vol_gal - storage_vol_gal:.0f} gal"))
    print(f"  Your capacity:  {capacity_kw:.1f} kW     -> " +
          ("OK" if cap_ok else f"BELOW MINIMUM by {min_cap_kw - capacity_kw:.1f} kW"))

    # --- 3-day simulation ---
    print("\n--- 3-Day Simulation ---")
    print("  Running...", end=" ", flush=True)
    try:
        engine_user = make_engine(storage_vol_gal=storage_vol_gal, capacity_kw=capacity_kw)
        sim = engine_user.getSimRun(minuteIntervals=1, nDays=3, exceptOnWaterShortage=False)
    except Exception as e:
        print(f"\n  ERROR: {e}")
        return
    print("done.")

    pv            = sim.pV
    demand        = sim.hwDemand
    total_demand  = sum(demand)
    min_pv        = min(pv)
    avg_pv        = sum(pv) / len(pv)
    outage_min    = sum(1 for v in pv if v <= 0)
    passed        = outage_min == 0

    print("\n" + "=" * 60)
    print("  RESULT: " + ("PASS -- system met all demand over 3 days" if passed
                          else "FAIL -- hot water outage occurred"))
    print("=" * 60)
    print(f"\n  Total DHW demand (3 days):          {total_demand:.0f} gal at supply temp")
    print(f"  Min tank volume during simulation:  {min_pv:.1f} gal at storage temp")
    print(f"  Avg tank volume during simulation:  {avg_pv:.1f} gal at storage temp")

    if not passed:
        print(f"\n  Outage: {outage_min} minute(s) over 3 days")
        print(f"  To fix: increase storage above {min_vol_gal:.0f} gal")
        print(f"          and/or increase capacity above {min_cap_kw:.1f} kW")
    else:
        print(f"\n  Storage margin:  +{storage_vol_gal - min_vol_gal:.0f} gal above minimum")
        print(f"  Capacity margin: +{capacity_kw - min_cap_kw:.1f} kW above minimum")
    print()


if __name__ == "__main__":
    main()
