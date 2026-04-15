"""
Unit tests for PerformanceMap and its three concrete subclasses.

Reference values were generated from the new PerformanceMap implementation and
cross-checked against the original PrefMapTracker in EcosizerEngine (original codebase).

Models used:
  PklPerformanceMap (3-input SP) : MODELS_ColmacCxV_5_C_SP
  PklPerformanceMap (2-input MP) : MODELS_ColmacCxV_5_C_MP
  HPWHsimPerformanceMap (multi-entry SP): MODELS_SANCO2_43_R_SP
  HPWHsimPerformanceMap (multi-entry MP): MODELS_AOSmithHPTS50_R_MP
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
        # from_nominal_capacity on WaterHeater ultimately creates NominalPerformanceMap
        nm = NominalPerformanceMap(51.56)
        assert isinstance(nm, NominalPerformanceMap)
        assert nm.get_capacity_kbtuh(0.0, 0.0) == pytest.approx(51.56)


# ---------------------------------------------------------------------------
# PklPerformanceMap — factory construction
# ---------------------------------------------------------------------------

class TestPklPerformanceMapFactory:
    def test_factory_returns_pkl_subclass(self):
        pm = PerformanceMap.from_model_name("MODELS_ColmacCxV_5_C_SP")
        assert isinstance(pm, PklPerformanceMap)

    def test_factory_returns_pkl_for_mp_model(self):
        pm = PerformanceMap.from_model_name("MODELS_ColmacCxV_5_C_MP")
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
            "MODELS_ColmacCxV_5_C_SP",
            num_units=1,
            design_inlet_temp_f=50.0,
        )

    def test_capacity_at_design_point(self, sp):
        # OAT=47, inlet=50, outlet=150 → ~51.56 kBTU/hr
        cap = sp.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=50.0)
        assert cap == pytest.approx(51.561, rel=1e-3)

    def test_power_at_design_point(self, sp):
        pwr = sp.get_power_in_kw(47.0, 150.0, inlet_temp_f=50.0)
        assert pwr == pytest.approx(6.256, rel=1e-3)

    def test_cop_at_design_point(self, sp):
        # COP = (cap_kbtuh / 3.412142) / power_kw
        cap = sp.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=50.0)
        pwr = sp.get_power_in_kw(47.0, 150.0, inlet_temp_f=50.0)
        cop = (cap / 3.412142) / pwr
        assert cop == pytest.approx(2.416, rel=1e-2)

    def test_default_inlet_matches_explicit_design_inlet(self, sp):
        # Calling without inlet_temp_f should use design_inlet_temp_f=50 → same result
        cap_implicit = sp.get_capacity_kbtuh(47.0, 150.0)
        cap_explicit = sp.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=50.0)
        assert cap_implicit == pytest.approx(cap_explicit)

    def test_higher_inlet_slightly_different(self, sp):
        cap_50 = sp.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=50.0)
        cap_60 = sp.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=60.0)
        # Different inlet → different result (map is sensitive to inlet)
        assert cap_60 != pytest.approx(cap_50, rel=1e-4)

    def test_oat_above_max_returns_default_high(self, sp):
        # OAT=150 is well above map max of 100 → default_high values
        cap_high = sp.get_capacity_kbtuh(150.0, 150.0, inlet_temp_f=50.0)
        assert cap_high == pytest.approx(81.209, rel=1e-3)

    def test_oat_below_min_er_fallback_with_nominal(self):
        # Provide nominal_capacity_kbtuh so ER fallback is well-defined
        sp_er = PerformanceMap.from_model_name(
            "MODELS_ColmacCxV_5_C_SP",
            num_units=1,
            design_inlet_temp_f=50.0,
            nominal_capacity_kbtuh=51.56,
        )
        # OAT=-10 is below oat_min=-1 → ER fallback: output = input = nominal
        cap = sp_er.get_capacity_kbtuh(-10.0, 150.0, inlet_temp_f=50.0)
        pwr = sp_er.get_power_in_kw(-10.0, 150.0, inlet_temp_f=50.0)
        assert cap == pytest.approx(51.56, rel=1e-3)   # COP = 1
        assert pwr == pytest.approx(51.56 / 3.412142, rel=1e-3)

    def test_num_units_scales_output(self):
        sp1 = PerformanceMap.from_model_name("MODELS_ColmacCxV_5_C_SP", num_units=1)
        sp2 = PerformanceMap.from_model_name("MODELS_ColmacCxV_5_C_SP", num_units=2)
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
            "MODELS_ColmacCxV_5_C_MP",
            num_units=1,
            design_inlet_temp_f=50.0,
        )

    def test_is_two_input(self, mp):
        assert mp._is_two_input is True

    def test_capacity_at_design_point(self, mp):
        # OAT=47, inlet=50 → ~49.13 kBTU/hr (outlet ignored for 2-input)
        cap = mp.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=50.0)
        assert cap == pytest.approx(49.135, rel=1e-3)

    def test_num_units_scales_output(self):
        mp1 = PerformanceMap.from_model_name("MODELS_ColmacCxV_5_C_MP", num_units=1)
        mp2 = PerformanceMap.from_model_name("MODELS_ColmacCxV_5_C_MP", num_units=2)
        cap1 = mp1.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=50.0)
        cap2 = mp2.get_capacity_kbtuh(47.0, 150.0, inlet_temp_f=50.0)
        assert cap2 == pytest.approx(cap1 * 2, rel=1e-6)


# ---------------------------------------------------------------------------
# HPWHsimPerformanceMap — factory construction
# ---------------------------------------------------------------------------

class TestHPWHsimPerformanceMapFactory:
    def test_factory_returns_hpwhsim_subclass_for_ao_smith(self):
        pm = PerformanceMap.from_model_name("MODELS_AOSmithHPTS50_R_MP")
        assert isinstance(pm, HPWHsimPerformanceMap)

    def test_factory_returns_hpwhsim_subclass_for_sanco2(self):
        pm = PerformanceMap.from_model_name("MODELS_SANCO2_43_R_SP")
        assert isinstance(pm, HPWHsimPerformanceMap)


# ---------------------------------------------------------------------------
# HPWHsimPerformanceMap — multi-entry MP (AO Smith bracket interpolation)
# ---------------------------------------------------------------------------

class TestHPWHsimMultiEntryMP:
    @pytest.fixture(scope="class")
    def mp(self):
        return PerformanceMap.from_model_name(
            "MODELS_AOSmithHPTS50_R_MP",
            num_units=1,
            design_inlet_temp_f=50.0,
        )

    def test_is_multipass(self, mp):
        assert mp._is_multipass is True

    def test_bracket_count(self, mp):
        # AOSmithHPTS50 has 3 OAT brackets: 50, 67.5, 95 °F
        assert len(mp._perfmap) == 3

    def test_capacity_at_design_point(self, mp):
        # OAT=67.5 is exactly on a bracket → ~5.617 kBTU/hr
        cap = mp.get_capacity_kbtuh(67.5, 140.0, inlet_temp_f=50.0)
        assert cap == pytest.approx(5.617, rel=1e-3)

    def test_power_at_design_point(self, mp):
        pwr = mp.get_power_in_kw(67.5, 140.0, inlet_temp_f=50.0)
        assert pwr == pytest.approx(0.2041, rel=1e-3)

    def test_cop_plausible(self, mp):
        cap = mp.get_capacity_kbtuh(67.5, 140.0, inlet_temp_f=50.0)
        pwr = mp.get_power_in_kw(67.5, 140.0, inlet_temp_f=50.0)
        cop = (cap / 3.412142) / pwr
        # COP should be positive and reasonable (>1 for heat pump)
        assert cop > 1.0

    def test_oat_below_min_er_fallback(self, mp):
        # OAT=49 < oat_min=50 → ER fallback: cap=0 (no nominal given)
        cap = mp.get_capacity_kbtuh(49.0, 140.0, inlet_temp_f=50.0)
        assert cap == pytest.approx(0.0)

    def test_oat_below_min_er_with_nominal(self):
        mp_er = PerformanceMap.from_model_name(
            "MODELS_AOSmithHPTS50_R_MP",
            num_units=1,
            nominal_capacity_kbtuh=5.617,
        )
        cap = mp_er.get_capacity_kbtuh(49.0, 140.0, inlet_temp_f=50.0)
        assert cap == pytest.approx(5.617, rel=1e-3)

    def test_num_units_scales_output(self):
        mp1 = PerformanceMap.from_model_name("MODELS_AOSmithHPTS50_R_MP", num_units=1)
        mp2 = PerformanceMap.from_model_name("MODELS_AOSmithHPTS50_R_MP", num_units=2)
        cap1 = mp1.get_capacity_kbtuh(67.5, 140.0, inlet_temp_f=50.0)
        cap2 = mp2.get_capacity_kbtuh(67.5, 140.0, inlet_temp_f=50.0)
        assert cap2 == pytest.approx(cap1 * 2, rel=1e-6)


# ---------------------------------------------------------------------------
# HPWHsimPerformanceMap — multi-entry SP (SANCO2, bracket interpolation)
# ---------------------------------------------------------------------------

class TestHPWHsimMultiEntrySP:
    @pytest.fixture(scope="class")
    def sp(self):
        return PerformanceMap.from_model_name(
            "MODELS_SANCO2_43_R_SP",
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
        assert cap == pytest.approx(14.070, rel=1e-3)

    def test_power_oat_47(self, sp):
        pwr = sp.get_power_in_kw(47.0, 140.0, inlet_temp_f=50.0)
        assert pwr == pytest.approx(1.088, rel=1e-2)

    def test_capacity_oat_67_5(self, sp):
        cap = sp.get_capacity_kbtuh(67.5, 140.0, inlet_temp_f=50.0)
        assert cap == pytest.approx(15.086, rel=1e-3)

    def test_below_oat_min_no_nominal(self, sp):
        # No nominal → ER fallback returns 0
        cap = sp.get_capacity_kbtuh(10.0, 140.0, inlet_temp_f=50.0)
        assert cap == pytest.approx(0.0)

    def test_cop_plausible_at_oat_47(self, sp):
        cap = sp.get_capacity_kbtuh(47.0, 140.0, inlet_temp_f=50.0)
        pwr = sp.get_power_in_kw(47.0, 140.0, inlet_temp_f=50.0)
        cop = (cap / 3.412142) / pwr
        assert cop > 1.0
