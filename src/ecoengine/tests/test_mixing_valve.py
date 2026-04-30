"""
Unit tests for mixing_valve_behavior (dhwsystems/utils.py).

Focus: at the critical flow boundary (load_supplyT_gal == critical_flow_g),
the mixing valve should require exactly load_supplyT_gal gallons from storage
at cold_temp_f inlet — i.e., the recirc return is fully absorbed into the
DHW stream and pure cold make-up water fills the tank bottom.
"""

import pytest
from ecoengine.objects.dhwsystems.utils import mixing_valve_behavior
from ecoengine.constants.constants import _RHO_CP


def _critical_flow_g(flow_returnT_gal, supply_temp_f, return_temp_f, storage_temp_f):
    recirc_loss_btu = flow_returnT_gal * _RHO_CP * (supply_temp_f - return_temp_f)
    return recirc_loss_btu / (_RHO_CP * (storage_temp_f - supply_temp_f))


# ---------------------------------------------------------------------------
# Boundary tests: load == critical_flow_g
# ---------------------------------------------------------------------------

class TestCriticalFlowBoundary:
    """
    At load == critical_flow_g the recirc return is exactly enough to
    compensate for loop losses without any recirc-only storage draw, so:
      - storage_draw_gal == load_supplyT_gal
      - inlet_temp_f     == cold_temp_f
    """

    def test_typical_temperatures(self):
        cold, return_t, supply, storage, flow = 50.0, 100.0, 120.0, 150.0, 3.0
        load = _critical_flow_g(flow, supply, return_t, storage)
        result = mixing_valve_behavior(load, flow, cold, supply, return_t, storage)
        assert result["storage_draw_gal"] == pytest.approx(load, rel=1e-6)
        assert result["inlet_temp_f"]     == pytest.approx(cold,  rel=1e-6)

    def test_higher_storage_temp(self):
        cold, return_t, supply, storage, flow = 45.0, 105.0, 120.0, 160.0, 2.0
        load = _critical_flow_g(flow, supply, return_t, storage)
        result = mixing_valve_behavior(load, flow, cold, supply, return_t, storage)
        assert result["storage_draw_gal"] == pytest.approx(load, rel=1e-6)
        assert result["inlet_temp_f"]     == pytest.approx(cold,  rel=1e-6)

    def test_low_return_temp(self):
        cold, return_t, supply, storage, flow = 55.0, 85.0, 120.0, 140.0, 1.5
        load = _critical_flow_g(flow, supply, return_t, storage)
        result = mixing_valve_behavior(load, flow, cold, supply, return_t, storage)
        assert result["storage_draw_gal"] == pytest.approx(load, rel=1e-6)
        assert result["inlet_temp_f"]     == pytest.approx(cold,  rel=1e-6)

    def test_high_flow_rate(self):
        cold, return_t, supply, storage, flow = 50.0, 110.0, 125.0, 155.0, 5.0
        load = _critical_flow_g(flow, supply, return_t, storage)
        result = mixing_valve_behavior(load, flow, cold, supply, return_t, storage)
        assert result["storage_draw_gal"] == pytest.approx(load, rel=1e-6)
        assert result["inlet_temp_f"]     == pytest.approx(cold,  rel=1e-6)

    def test__various_time_periods(self):
        cold, return_t, supply, storage, flow = 50.0, 100.0, 120.0, 150.0, 3.0
        load = _critical_flow_g(flow, supply, return_t, storage)
        result = mixing_valve_behavior(load, flow, cold, supply, return_t, storage)
        assert result["storage_draw_gal"] == pytest.approx(load, rel=1e-6)
        assert result["inlet_temp_f"]     == pytest.approx(cold,  rel=1e-6)
        # 10 minutes
        flow = flow * 10
        load = load * 10
        result = mixing_valve_behavior(load, flow, cold, supply, return_t, storage)
        assert result["storage_draw_gal"] == pytest.approx(load, rel=1e-6)
        assert result["inlet_temp_f"]     == pytest.approx(cold,  rel=1e-6)
        # 1 hour
        flow = flow * 6
        load = load * 6
        result = mixing_valve_behavior(load, flow, cold, supply, return_t, storage)
        assert result["storage_draw_gal"] == pytest.approx(load, rel=1e-6)
        assert result["inlet_temp_f"]     == pytest.approx(cold,  rel=1e-6)

    def test_below_critical_load(self):
        cold, return_t, supply, storage, flow = 50.0, 100.0, 120.0, 150.0, 3.0
        load = _critical_flow_g(flow, supply, return_t, storage)
        load = load/2
        result = mixing_valve_behavior(load, flow, cold, supply, return_t, storage)
        assert result["storage_draw_gal"] > load
        assert result["inlet_temp_f"]     > cold

    def test_above_critical_load(self):
        cold, return_t, supply, storage, flow = 50.0, 100.0, 120.0, 150.0, 3.0
        load = _critical_flow_g(flow, supply, return_t, storage)
        load = load + 5
        result = mixing_valve_behavior(load, flow, cold, supply, return_t, storage)
        assert result["storage_draw_gal"] < load
        assert result["inlet_temp_f"]     == pytest.approx(cold,  rel=1e-6)
