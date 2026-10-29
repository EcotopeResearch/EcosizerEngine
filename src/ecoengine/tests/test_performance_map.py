"""
Unit tests for PerformanceMap and its three concrete subclasses.

Bundled models used (anonymized):
  PklPerformanceMap (3-input SP) : MODELS_GenericHPWH3_C_SP
  PklPerformanceMap (2-input MP) : MODELS_GenericHPWH4_C_MP
  HPWHsimPerformanceMap (multi-entry MP): MODELS_GenericHPWH1_C_MP
  HPWHsimPerformanceMap (multi-entry SP): MODELS_GenericHPWH2_R_SP
"""
import pytest
from ecoengine.objects.components.heating.PerformanceMap import (
    HPWHsimPerformanceMap,
    NominalPerformanceMap,
    PerformanceMap,
    PklPerformanceMap,
)


# ---------------------------------------------------------------------------
# NominalPerformanceMap
# ---------------------------------------------------------------------------

class TestNominalPerformanceMap:
    def test_capacity_is_constant(self):
        nm = NominalPerformanceMap(407.2)
        assert nm.get_capacity_kbtuh(47.0, 150.0) == pytest.approx(407.2)
        assert nm.get_capacity_kbtuh(10.0, 120.0) == pytest.approx(407.2)
        assert nm.get_capacity_kbtuh(100.0, 180.0) == pytest.approx(407.2)

    def test_capacity_with_inlet_arg_ignored(self):
        nm = NominalPerformanceMap(100.0)
        assert nm.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=60.0) == pytest.approx(100.0)

    def test_power_is_none(self):
        nm = NominalPerformanceMap(407.2)
        assert nm.get_power_in_kw(47.0, 150.0) is None

    def test_factory_method_produces_nominal(self):
        nm = NominalPerformanceMap(51.56)
        assert isinstance(nm, NominalPerformanceMap)
        assert nm.get_capacity_kbtuh(0.0, 0.0) == pytest.approx(51.56)


# ---------------------------------------------------------------------------
# PklPerformanceMap — factory construction
# ---------------------------------------------------------------------------

class TestPklPerformanceMapFactory:
    def test_factory_returns_pkl_subclass(self):
        pm = PerformanceMap.from_model_name("MODELS_GenericHPWH3_C_SP")
        assert isinstance(pm, PklPerformanceMap)

    def test_factory_returns_pkl_for_mp_model(self):
        pm = PerformanceMap.from_model_name("MODELS_GenericHPWH4_C_MP")
        assert isinstance(pm, PklPerformanceMap)

    def test_unknown_model_raises(self):
        with pytest.raises(ValueError, match="not found in the performance map registry"):
            PerformanceMap.from_model_name("MODELS_DoesNotExist")


# ---------------------------------------------------------------------------
# PklPerformanceMap — single-pass (3-input) interpolation
# ---------------------------------------------------------------------------

class TestPklSinglePass:
    @pytest.fixture(scope="class")
    def sp(self):
        return PerformanceMap.from_model_name(
            "MODELS_GenericHPWH3_C_SP",
            num_units=1,
            design_inlet_temp_f=50.0,
        )

    def test_capacity_at_design_point(self, sp):
        # OAT=47, inlet=50, outlet=150
        cap = sp.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=50.0)
        assert cap == pytest.approx(214.439, rel=1e-3)

    def test_power_at_design_point(self, sp):
        pwr = sp.get_power_in_kw(47.0, 150.0, inlet_temp_f=50.0)
        assert pwr == pytest.approx(28.119, rel=1e-3)

    def test_cop_at_design_point(self, sp):
        cap = sp.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=50.0)
        pwr = sp.get_power_in_kw(47.0, 150.0, inlet_temp_f=50.0)
        cop = (cap / 3.412142) / pwr
        assert cop == pytest.approx(2.235, rel=1e-2)

    def test_default_inlet_matches_explicit_design_inlet(self, sp):
        cap_implicit = sp.get_capacity_kbtuh(47.0, 150.0)
        cap_explicit = sp.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=50.0)
        assert cap_implicit == pytest.approx(cap_explicit)

    def test_higher_inlet_slightly_different(self, sp):
        cap_50 = sp.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=50.0)
        cap_60 = sp.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=60.0)
        assert cap_60 != pytest.approx(cap_50, rel=1e-4)

    def test_oat_above_max_returns_default_high(self, sp):
        cap_high = sp.get_capacity_kbtuh(150.0, 150.0, inlet_temp_f=50.0)
        assert cap_high == pytest.approx(354.522, rel=1e-3)

    def test_oat_below_min_er_fallback_with_nominal(self):
        nominal = 214.439
        sp_er = PerformanceMap.from_model_name(
            "MODELS_GenericHPWH3_C_SP",
            num_units=1,
            design_inlet_temp_f=50.0,
            nominal_capacity_kbtuh=nominal,
        )
        cap = sp_er.get_capacity_kbtuh(-10.0, 150.0, inlet_temp_f=50.0)
        pwr = sp_er.get_power_in_kw(-10.0, 150.0, inlet_temp_f=50.0)
        assert cap == pytest.approx(nominal, rel=1e-3)
        assert pwr == pytest.approx(nominal / 3.412142, rel=1e-3)

    def test_num_units_scales_output(self):
        sp1 = PerformanceMap.from_model_name("MODELS_GenericHPWH3_C_SP", num_units=1)
        sp2 = PerformanceMap.from_model_name("MODELS_GenericHPWH3_C_SP", num_units=2)
        cap1 = sp1.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=50.0)
        cap2 = sp2.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=50.0)
        assert cap2 == pytest.approx(cap1 * 2, rel=1e-6)

    def test_is_within_bounds(self, sp):
        assert sp.is_within_operating_bounds(47.0) == True
        assert sp.is_within_operating_bounds(60.0) == True
        assert sp.is_within_operating_bounds(sp.oat_min) == True
        assert sp.is_within_operating_bounds(sp.oat_min - 1) == False


# ---------------------------------------------------------------------------
# PklPerformanceMap — multi-pass / two-input (inlet + OAT only)
# ---------------------------------------------------------------------------

class TestPklMultiPass:
    @pytest.fixture(scope="class")
    def mp(self):
        return PerformanceMap.from_model_name(
            "MODELS_GenericHPWH4_C_MP",
            num_units=1,
            design_inlet_temp_f=50.0,
        )

    def test_is_two_input(self, mp):
        assert mp._is_two_input is True

    def test_capacity_at_design_point(self, mp):
        cap = mp.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=50.0)
        assert cap == pytest.approx(224.246, rel=1e-3)

    def test_num_units_scales_output(self):
        mp1 = PerformanceMap.from_model_name("MODELS_GenericHPWH4_C_MP", num_units=1)
        mp2 = PerformanceMap.from_model_name("MODELS_GenericHPWH4_C_MP", num_units=2)
        cap1 = mp1.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=50.0)
        cap2 = mp2.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=50.0)
        assert cap2 == pytest.approx(cap1 * 2, rel=1e-6)


# ---------------------------------------------------------------------------
# PklPerformanceMap — conservative snapping fallback (_force_closest)
# ---------------------------------------------------------------------------

class _GridInterp:
    """Stub interpolator: returns a value only at exact grid points, else NaN."""
    def __init__(self, points: dict):
        self._points = points

    def __call__(self, arr):
        return [[self._points.get(tuple(arr[0]), float("nan"))]]


def _make_grid_map(unique_oats, inTs_outTs, out_pts, in_pts):
    return PklPerformanceMap(
        model_name="grid_stub",
        output_interpolator=_GridInterp(out_pts),
        input_interpolator=_GridInterp(in_pts),
        unique_oats=unique_oats,
        inTs_and_outTs_by_oat=inTs_outTs,
        inlet_min=40.0,
        inlet_max=70.0,
        default_out_high_kw=0.0,
        default_in_high_kw=0.0,
        default_out_low_kw=0.0,
        default_in_low_kw=0.0,
        num_units=1,
        is_two_input=False,
        secondary_hx=False,
        hx_increase=0.0,
        nominal_capacity_kbtuh=None,
        design_inlet_temp_f=50.0,
    )


class TestPklConservativeSnap:
    def test_exact_match_wins(self):
        assert PklPerformanceMap._pick_biased([90.0, 100.0, 101.0], 100.0, False, 10.0) == 1

    def test_lower_oat_preferred_within_tol(self):
        # 98 is lower and within 10 °F of the nearest point (101)
        assert PklPerformanceMap._pick_biased([98.0, 101.0], 100.0, False, 10.0) == 0

    def test_lower_oat_rejected_outside_tol(self):
        # 80 is 20 °F away; nearest (101) is 1 °F away → 20 > 1 + 10
        assert PklPerformanceMap._pick_biased([80.0, 101.0], 100.0, False, 10.0) == 1

    def test_no_lower_oat_uses_nearest(self):
        assert PklPerformanceMap._pick_biased([101.0, 105.0], 100.0, False, 10.0) == 0

    def test_higher_inlet_preferred_within_tol(self):
        assert PklPerformanceMap._pick_biased([50.0, 60.0, 70.0], 64.4, True, 15.0) == 2

    def test_higher_inlet_rejected_outside_tol(self):
        # 80 is 28 °F away; nearest (50) is 2 °F away → 28 > 2 + 15
        assert PklPerformanceMap._pick_biased([40.0, 50.0, 80.0], 52.0, True, 15.0) == 1

    def test_higher_outlet_preferred_within_tol(self):
        assert PklPerformanceMap._pick_biased([140.0, 160.0, 180.0], 165.0, True, 20.0) == 2

    def test_force_closest_snaps_conservatively(self):
        # Mirrors the sparse high-OAT tail of the Laars eTherm map
        pm = _make_grid_map(
            unique_oats=[97.1, 98.3, 101.1],
            inTs_outTs=[
                [[50.0, [160.0]]],
                [[70.0, [160.0]]],
                [[50.0, [140.0]]],
            ],
            out_pts={(50.0, 160.0, 97.1): 120.0, (70.0, 160.0, 98.3): 100.0, (50.0, 140.0, 101.1): 111.9},
            in_pts ={(50.0, 160.0, 97.1): 30.0,  (70.0, 160.0, 98.3): 40.0,  (50.0, 140.0, 101.1): 27.0},
        )
        # Lower OAT 98.3 (within 10 °F), higher inlet 70, exact outlet 160
        assert pm._force_closest(64.4, 160.0, 100.94) == (100.0, 40.0)

    def test_lower_outlet_adjustment_keeps_cop(self):
        pm = _make_grid_map(
            unique_oats=[100.0],
            inTs_outTs=[[[50.0, [140.0]]]],
            out_pts={(50.0, 140.0, 100.0): 111.9},
            in_pts ={(50.0, 140.0, 100.0): 27.0},
        )
        out_kw, inp_kw = pm._force_closest(50.0, 160.0, 100.0)
        expected_out = 111.9 * (1 + (160.0 - 140.0) / (160.0 - 50.0))
        assert out_kw == pytest.approx(expected_out)
        assert out_kw / inp_kw == pytest.approx(111.9 / 27.0)


# ---------------------------------------------------------------------------
# HPWHsimPerformanceMap — factory construction
# ---------------------------------------------------------------------------

class TestHPWHsimPerformanceMapFactory:
    def test_factory_returns_hpwhsim_subclass_for_generic1(self):
        pm = PerformanceMap.from_model_name("MODELS_GenericHPWH1_C_MP")
        assert isinstance(pm, HPWHsimPerformanceMap)

    def test_factory_returns_hpwhsim_subclass_for_generic2(self):
        pm = PerformanceMap.from_model_name("MODELS_GenericHPWH2_R_SP")
        assert isinstance(pm, HPWHsimPerformanceMap)


# ---------------------------------------------------------------------------
# HPWHsimPerformanceMap — multi-entry MP (GenericHPWH1, bracket interpolation)
# ---------------------------------------------------------------------------

class TestHPWHsimMultiEntryMP:
    @pytest.fixture(scope="class")
    def mp(self):
        return PerformanceMap.from_model_name(
            "MODELS_GenericHPWH1_C_MP",
            num_units=1,
            design_inlet_temp_f=50.0,
        )

    def test_is_multipass(self, mp):
        assert mp._is_multipass is True

    def test_bracket_count(self, mp):
        assert len(mp._perfmap) == 3

    def test_capacity_at_design_point(self, mp):
        cap = mp.get_capacity_kbtuh(67.5, 140.0, inlet_temp_f=50.0)
        assert cap == pytest.approx(51.710, rel=1e-3)

    def test_power_at_design_point(self, mp):
        pwr = mp.get_power_in_kw(67.5, 140.0, inlet_temp_f=50.0)
        assert pwr == pytest.approx(2.076, rel=1e-3)

    def test_cop_plausible(self, mp):
        cap = mp.get_capacity_kbtuh(67.5, 140.0, inlet_temp_f=50.0)
        pwr = mp.get_power_in_kw(67.5, 140.0, inlet_temp_f=50.0)
        cop = (cap / 3.412142) / pwr
        assert cop > 1.0

    def test_oat_below_min_er_fallback(self, mp):
        cap = mp.get_capacity_kbtuh(49.0, 140.0, inlet_temp_f=50.0)
        assert cap > 0.0

    def test_oat_below_min_er_with_nominal(self):
        nominal = 51.710
        mp_er = PerformanceMap.from_model_name(
            "MODELS_GenericHPWH1_C_MP",
            num_units=1,
            nominal_capacity_kbtuh=nominal,
        )
        cap = mp_er.get_capacity_kbtuh(49.0, 140.0, inlet_temp_f=50.0)
        assert cap == pytest.approx(nominal, rel=1e-3)

    def test_num_units_scales_output(self):
        mp1 = PerformanceMap.from_model_name("MODELS_GenericHPWH1_C_MP", num_units=1)
        mp2 = PerformanceMap.from_model_name("MODELS_GenericHPWH1_C_MP", num_units=2)
        cap1 = mp1.get_capacity_kbtuh(67.5, 140.0, inlet_temp_f=50.0)
        cap2 = mp2.get_capacity_kbtuh(67.5, 140.0, inlet_temp_f=50.0)
        assert cap2 == pytest.approx(cap1 * 2, rel=1e-6)


# ---------------------------------------------------------------------------
# HPWHsimPerformanceMap — multi-entry SP (GenericHPWH2, bracket interpolation)
# ---------------------------------------------------------------------------

class TestHPWHsimMultiEntrySP:
    @pytest.fixture(scope="class")
    def sp(self):
        return PerformanceMap.from_model_name(
            "MODELS_GenericHPWH2_R_SP",
            num_units=1,
            design_inlet_temp_f=50.0,
        )

    def test_is_not_multipass(self, sp):
        assert sp._is_multipass is False

    def test_bracket_count(self, sp):
        assert len(sp._perfmap) == 5

    def test_oat_min(self, sp):
        assert sp.oat_min == pytest.approx(17.0)

    def test_capacity_oat_47(self, sp):
        cap = sp.get_capacity_kbtuh(47.0, 140.0, inlet_temp_f=50.0)
        assert cap == pytest.approx(18.191, rel=1e-3)

    def test_power_oat_47(self, sp):
        pwr = sp.get_power_in_kw(47.0, 140.0, inlet_temp_f=50.0)
        assert pwr == pytest.approx(1.088, rel=1e-2)

    def test_capacity_oat_67_5(self, sp):
        cap = sp.get_capacity_kbtuh(67.5, 140.0, inlet_temp_f=50.0)
        assert cap == pytest.approx(19.924, rel=1e-3)

    def test_below_oat_min_no_nominal(self, sp):
        cap = sp.get_capacity_kbtuh(10.0, 140.0, inlet_temp_f=50.0)
        assert cap > 0.0

    def test_cop_plausible_at_oat_47(self, sp):
        cap = sp.get_capacity_kbtuh(47.0, 140.0, inlet_temp_f=50.0)
        pwr = sp.get_power_in_kw(47.0, 140.0, inlet_temp_f=50.0)
        cop = (cap / 3.412142) / pwr
        assert cop > 1.0
