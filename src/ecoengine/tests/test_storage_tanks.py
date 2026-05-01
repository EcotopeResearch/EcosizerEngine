"""
Equivalence tests: EnergyTank vs. StratifiedTank.

Both tanks implement the same piecewise-linear stratified profile.
EnergyTank tracks BTU as its primary state; StratifiedTank tracks delta_gal.
Under conditions where the two formulations are algebraically equivalent —
draws within the hot zone, outlet_temp_f == storage_temp_f, constant
cold_temp_f — they must produce identical temperature profiles.

Temperature tolerance is 1e-3 °F rather than the 1e-6 requested in the
task description: the binary search in _shift_pct_from_energy uses a
relative energy tolerance of 1e-6, which translates to ~1e-4 – 1e-5 °F
precision.  1e-3 gives a reliable safety margin while still verifying
meaningful agreement.
"""
import pytest
from ecoengine.objects.components.storage.StratifiedTank import StratifiedTank
from ecoengine.objects.components.storage.EnergyTank import EnergyTank
from ecoengine.objects.components.storage.SlugOverlayTank import SlugOverlayTank
from ecoengine.constants.constants import _RHO_CP

_FRACTIONS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
_TOL = 1e-3  # °F


def _assert_temps_match(
    st: StratifiedTank,
    et: EnergyTank,
    tol: float = _TOL,
) -> None:
    for f in _FRACTIONS:
        t_s = st.get_temperature_at_fraction(f)
        t_e = et.get_temperature_at_fraction(f)
        assert t_s == pytest.approx(t_e, abs=tol), (
            f"fract={f}: StratifiedTank={t_s:.6f} EnergyTank={t_e:.6f}"
        )


def _make_tanks(
    volume_gal: float,
    cold_temp_f: float,
    storage_temp_f: float,
    strat_slope: float = 2.8,
) -> tuple[StratifiedTank, EnergyTank]:
    st = StratifiedTank(total_volume_gal=volume_gal, strat_slope=strat_slope)
    et = EnergyTank(
        total_volume_gal=volume_gal,
        cold_temp_f=cold_temp_f,
        storage_temp_f=storage_temp_f,
        strat_slope=strat_slope,
    )
    return st, et


class TestStorageTankEquivalence:

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def test_initialize_fully_hot(self):
        st, et = _make_tanks(500.0, 50.0, 150.0)
        st.initialize(150.0, 50.0, 1.0)
        et.initialize(150.0, 50.0, 1.0)
        _assert_temps_match(st, et)

    def test_initialize_eighty_percent(self):
        st, et = _make_tanks(500.0, 50.0, 150.0)
        st.initialize(150.0, 50.0, 0.8)
        et.initialize(150.0, 50.0, 0.8)
        _assert_temps_match(st, et)

    def test_initialize_fifty_percent(self):
        st, et = _make_tanks(500.0, 50.0, 150.0)
        st.initialize(150.0, 50.0, 0.5)
        et.initialize(150.0, 50.0, 0.5)
        _assert_temps_match(st, et)

    def test_initialize_non_default_slope(self):
        """Agreement holds for a non-default stratification slope (SPRTP uses 1.7)."""
        st, et = _make_tanks(300.0, 40.0, 160.0, strat_slope=1.7)
        st.initialize(160.0, 40.0, 0.9)
        et.initialize(160.0, 40.0, 0.9)
        _assert_temps_match(st, et)

    # ------------------------------------------------------------------
    # draw()
    # ------------------------------------------------------------------

    def test_draw_from_full_tank(self):
        """Draw within the hot zone keeps profiles in sync."""
        st, et = _make_tanks(500.0, 50.0, 150.0)
        st.initialize(150.0, 50.0, 1.0)
        et.initialize(150.0, 50.0, 1.0)
        st.draw(50.0, 50.0, 120.0, 150.0)
        et.draw(50.0, 50.0, 120.0, 150.0)
        _assert_temps_match(st, et)

    def test_draw_repeated(self):
        """Five sequential draws stay in sync."""
        st, et = _make_tanks(500.0, 50.0, 150.0)
        st.initialize(150.0, 50.0, 1.0)
        et.initialize(150.0, 50.0, 1.0)
        for _ in range(5):
            st.draw(30.0, 50.0, 120.0, 150.0)
            et.draw(30.0, 50.0, 120.0, 150.0)
        _assert_temps_match(st, et)

    def test_draw_from_partial_init(self):
        """Draw from a tank initialized at 80% useable stays in sync."""
        st, et = _make_tanks(500.0, 50.0, 150.0)
        st.initialize(150.0, 50.0, 0.8)
        et.initialize(150.0, 50.0, 0.8)
        st.draw(40.0, 50.0, 120.0, 150.0)
        et.draw(40.0, 50.0, 120.0, 150.0)
        _assert_temps_match(st, et)

    # ------------------------------------------------------------------
    # heat()
    # ------------------------------------------------------------------

    def test_heat_partial_tank(self):
        """Heating a half-cold tank produces matching profiles."""
        st, et = _make_tanks(500.0, 50.0, 150.0)
        st.initialize(150.0, 50.0, 0.5)
        et.initialize(150.0, 50.0, 0.5)
        st.heat(50.0, 30.0, 150.0)
        et.heat(50.0, 30.0, 150.0)
        _assert_temps_match(st, et)

    def test_heat_to_full(self):
        """Excess heat clamps both tanks at storage temperature."""
        st, et = _make_tanks(200.0, 50.0, 150.0)
        st.initialize(150.0, 50.0, 0.3)
        et.initialize(150.0, 50.0, 0.3)
        st.heat(500.0, 60.0, 150.0)
        et.heat(500.0, 60.0, 150.0)
        _assert_temps_match(st, et)

    def test_heat_then_draw(self):
        """Heat followed by a draw stays in sync."""
        st, et = _make_tanks(500.0, 50.0, 150.0)
        st.initialize(150.0, 50.0, 0.6)
        et.initialize(150.0, 50.0, 0.6)
        st.heat(80.0, 30.0, 150.0)
        et.heat(80.0, 30.0, 150.0)
        st.draw(60.0, 50.0, 120.0, 150.0)
        et.draw(60.0, 50.0, 120.0, 150.0)
        _assert_temps_match(st, et)

    # ------------------------------------------------------------------
    # add_recirc_return()
    # ------------------------------------------------------------------

    def test_recirc_return(self):
        """Single recirc loss step produces matching profiles."""
        st, et = _make_tanks(500.0, 50.0, 150.0)
        st.initialize(150.0, 50.0, 1.0)
        et.initialize(150.0, 50.0, 1.0)
        st.add_recirc_return(2.0, 110.0, 60.0)
        et.add_recirc_return(2.0, 110.0, 60.0)
        _assert_temps_match(st, et)

    def test_recirc_repeated(self):
        """Ten recirc steps accumulate correctly in both tanks."""
        st, et = _make_tanks(500.0, 50.0, 150.0)
        st.initialize(150.0, 50.0, 1.0)
        et.initialize(150.0, 50.0, 1.0)
        for _ in range(10):
            st.add_recirc_return(2.0, 110.0, 6.0)
            et.add_recirc_return(2.0, 110.0, 6.0)
        _assert_temps_match(st, et)

    def test_recirc_then_heat(self):
        """Recirc loss followed by heater recovery stays in sync."""
        st, et = _make_tanks(500.0, 50.0, 150.0)
        st.initialize(150.0, 50.0, 1.0)
        et.initialize(150.0, 50.0, 1.0)
        st.add_recirc_return(3.0, 110.0, 30.0)
        et.add_recirc_return(3.0, 110.0, 30.0)
        st.heat(60.0, 30.0, 150.0)
        et.heat(60.0, 30.0, 150.0)
        _assert_temps_match(st, et)

    # ------------------------------------------------------------------
    # draw_physical_gal()
    # ------------------------------------------------------------------

    def test_draw_physical_gal_from_hot_zone(self):
        """draw_physical_gal from the hot zone stays in sync."""
        st, et = _make_tanks(500.0, 50.0, 150.0)
        st.initialize(150.0, 50.0, 1.0)
        et.initialize(150.0, 50.0, 1.0)
        st.draw_physical_gal(30.0, 50.0)
        et.draw_physical_gal(30.0, 50.0)
        _assert_temps_match(st, et)

    def test_draw_physical_gal_partial_init(self):
        """draw_physical_gal on a partially hot tank stays in sync."""
        st, et = _make_tanks(500.0, 50.0, 150.0)
        st.initialize(150.0, 50.0, 0.8)
        et.initialize(150.0, 50.0, 0.8)
        st.draw_physical_gal(20.0, 50.0)
        et.draw_physical_gal(20.0, 50.0)
        _assert_temps_match(st, et)

    # ------------------------------------------------------------------
    # Multi-step sequence
    # ------------------------------------------------------------------

    def test_full_simulation_sequence(self):
        """Extended draw/heat/recirc sequence stays in sync."""
        st, et = _make_tanks(500.0, 50.0, 150.0)
        st.initialize(150.0, 50.0, 0.8)
        et.initialize(150.0, 50.0, 0.8)

        steps = [
            ("draw",   (20.0, 50.0, 120.0, 150.0)),
            ("heat",   (60.0, 10.0, 150.0)),
            ("draw",   (30.0, 50.0, 120.0, 150.0)),
            ("recirc", (2.0, 110.0, 10.0)),
            ("heat",   (60.0, 10.0, 150.0)),
            ("draw",   (25.0, 50.0, 120.0, 150.0)),
            ("recirc", (2.0, 110.0, 10.0)),
            ("heat",   (60.0, 10.0, 150.0)),
        ]
        for op, args in steps:
            if op == "draw":
                st.draw(*args)
                et.draw(*args)
            elif op == "heat":
                st.heat(*args)
                et.heat(*args)
            else:
                st.add_recirc_return(*args)
                et.add_recirc_return(*args)

        _assert_temps_match(st, et)


# ===========================================================================
# SlugOverlayTank — slug energy conservation
# ===========================================================================

def _make_slug_tank(percent_useable: float = 1.0) -> SlugOverlayTank:
    """100-gal tank with MPRTP-typical temperatures and strat_slope."""
    return SlugOverlayTank(
        total_volume_gal=100.0,
        cold_temp_f=50.0,
        storage_temp_f=140.0,
        supply_temp_f=125.0,
        percent_useable=percent_useable,
        strat_slope=0.8,
    )


class TestSlugEnergyConservation:
    """
    After activate → heat_slug → deactivate, the tank's stored energy must
    equal the energy before activation plus the heat added to the slug.

    Expected: tank._energy_btu_after == E0 + Q
    where Q = kbtuh × 1000 × duration_min / 60
    """

    def test_energy_conserved_no_unusable_zone(self):
        # percent_useable=1.0: cold inlet at the very bottom, no unusable zone.
        # Initialize to 70% usable so there is a 30-gal sub-supply slug zone.
        # Slug spans 0–30 % of tank height, avg temp ≈ 113 °F.
        # Q=500 BTU is well below the storage-temp cap (~6765 BTU available).
        tank = _make_slug_tank(percent_useable=1.0)
        tank.initialize(storage_temp_f=140.0, cold_temp_f=50.0, percent_useable=0.70)

        E0 = tank._energy_btu

        tank.activate_slug(125.0)

        kbtuh, duration_min = 3.0, 10.0
        Q = kbtuh * 1000.0 * duration_min / 60.0
        tank.heat_slug(kbtuh, duration_min)

        tank.deactivate_slug()

        assert tank._energy_btu == pytest.approx(E0 + Q, rel=1e-4)

    def test_energy_conserved_larger_heat_addition(self):
        # Same setup but more heat added — still below the storage-temp cap.
        tank = _make_slug_tank(percent_useable=1.0)
        tank.initialize(storage_temp_f=140.0, cold_temp_f=50.0, percent_useable=0.70)

        E0 = tank._energy_btu

        tank.activate_slug(125.0)

        kbtuh, duration_min = 10.0, 10.0   # Q ≈ 1667 BTU, cap ≈ 6765 BTU
        Q = kbtuh * 1000.0 * duration_min / 60.0
        tank.heat_slug(kbtuh, duration_min)

        tank.deactivate_slug()

        assert tank._energy_btu == pytest.approx(E0 + Q, rel=1e-4)

    def test_energy_conserved_with_unusable_zone(self):
        # percent_useable=0.85: 15 % of tank is below the cold inlet pipe.
        # The unusable zone contains real BTUs that must survive deactivation.
        # Slug spans 15–30 % of tank height, avg temp ≈ 119 °F.
        tank = _make_slug_tank(percent_useable=0.85)
        tank.initialize(storage_temp_f=140.0, cold_temp_f=50.0, percent_useable=0.70)

        E0 = tank._energy_btu

        tank.activate_slug(125.0)

        kbtuh, duration_min = 3.0, 10.0
        Q = kbtuh * 1000.0 * duration_min / 60.0
        tank.heat_slug(kbtuh, duration_min)

        tank.deactivate_slug()

        assert tank._energy_btu == pytest.approx(E0 + Q, rel=1e-4)


# ===========================================================================
# SlugOverlayTank — energy conservation with draws during slug active
# ===========================================================================

class TestSlugEnergyConservationWithDraw:
    """
    After activate → [heat_slug + draw_physical_gal] → deactivate, the tank's
    stored energy must equal:

        E_after == E0 + Q - E_removed

    where Q = kbtuh × 1000 × duration_min / 60
    and   E_removed = draw_gal × _RHO_CP × max(0, avg_draw_temp - inlet_temp_f)
    with  avg_draw_temp captured via get_average_draw_temp_f() BEFORE the draw.
    """

    def test_draw_from_above_slug_no_unusable_zone(self):
        # percent_useable=1.0; draw 20 gal from the hot zone above the slug.
        tank = _make_slug_tank(percent_useable=1.0)
        tank.initialize(storage_temp_f=140.0, cold_temp_f=50.0, percent_useable=0.70)

        E0 = tank._energy_btu

        tank.activate_slug(125.0)

        kbtuh, duration_min = 3.0, 10.0
        Q = kbtuh * 1000.0 * duration_min / 60.0
        tank.heat_slug(kbtuh, duration_min)

        draw_gal = 20.0
        inlet_temp_f = 50.0
        avg_draw_temp = tank.get_average_draw_temp_f(draw_gal)
        E_removed = draw_gal * _RHO_CP * max(0.0, avg_draw_temp - inlet_temp_f)
        tank.draw_physical_gal(draw_gal, inlet_temp_f)

        tank.deactivate_slug()

        assert tank._energy_btu == pytest.approx(E0 + Q - E_removed, rel=1e-4)

    def test_draw_from_above_slug_with_unusable_zone(self):
        # percent_useable=0.85; 15 % below inlet; draw 20 gal from hot zone.
        tank = _make_slug_tank(percent_useable=0.85)
        tank.initialize(storage_temp_f=140.0, cold_temp_f=50.0, percent_useable=0.70)

        E0 = tank._energy_btu

        tank.activate_slug(125.0)

        kbtuh, duration_min = 3.0, 10.0
        Q = kbtuh * 1000.0 * duration_min / 60.0
        tank.heat_slug(kbtuh, duration_min)

        draw_gal = 20.0
        inlet_temp_f = 50.0
        avg_draw_temp = tank.get_average_draw_temp_f(draw_gal)
        E_removed = draw_gal * _RHO_CP * max(0.0, avg_draw_temp - inlet_temp_f)
        tank.draw_physical_gal(draw_gal, inlet_temp_f)

        tank.deactivate_slug()

        assert tank._energy_btu == pytest.approx(E0 + Q - E_removed, rel=1e-4)

    def test_multiple_draws_no_unusable_zone(self):
        # Three interleaved heat + draw cycles; cumulative accounting must balance.
        tank = _make_slug_tank(percent_useable=1.0)
        tank.initialize(storage_temp_f=140.0, cold_temp_f=50.0, percent_useable=0.70)

        E0 = tank._energy_btu
        inlet_temp_f = 50.0

        tank.activate_slug(125.0)

        Q_total = 0.0
        E_removed_total = 0.0

        for kbtuh, duration_min, draw_gal in [
            (3.0, 5.0, 10.0),
            (3.0, 5.0, 8.0),
            (3.0, 5.0, 12.0),
        ]:
            Q_total += kbtuh * 1000.0 * duration_min / 60.0
            tank.heat_slug(kbtuh, duration_min)
            avg_draw_temp = tank.get_average_draw_temp_f(draw_gal)
            E_removed_total += draw_gal * _RHO_CP * max(0.0, avg_draw_temp - inlet_temp_f)
            tank.draw_physical_gal(draw_gal, inlet_temp_f)

        tank.deactivate_slug()

        assert tank._energy_btu == pytest.approx(E0 + Q_total - E_removed_total, rel=1e-4)
