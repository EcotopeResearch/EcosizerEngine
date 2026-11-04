"""
Tests for WaterHeater.update_state() mode-switch behavior.

QPL alignment: on a change of load-shift mode, heaters are disabled. If the
new mode's ON sensor is warmer than its ON trigger, the heater must stay off
even though it would otherwise keep heating toward the new mode's OFF point.
"""
import pytest
from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.storage.StratifiedTank import StratifiedTank

_ON_SENSOR_FRACT  = 0.8
_OFF_SENSOR_FRACT = 0.2
_SWITCH_HOUR      = 10   # first hour of the "shed" block
_SWITCH_MIN       = _SWITCH_HOUR * 60   # first 1-minute interval of the "shed" block


def _make_tank() -> StratifiedTank:
    tank = StratifiedTank(total_volume_gal=500.0)
    tank.initialize(
        storage_temp_f=140.0,
        cold_temp_f=50.0,
        initial_hot_fract=0.5,
        supply_temp_f=120.0,
    )
    return tank


def _make_heater(tank: StratifiedTank, schedule: list[str]) -> WaterHeater:
    """
    Build a heater whose "shed" mode is set so that, for the given tank:
      * should_turn_off() is False (OFF sensor below the shed OFF trigger), and
      * should_turn_on()  is False (ON sensor above the shed ON trigger).
    """
    t_on_sensor  = tank.get_temperature_at_fraction(_ON_SENSOR_FRACT)
    t_off_sensor = tank.get_temperature_at_fraction(_OFF_SENSOR_FRACT)

    normal = Controls(
        on_sensor_fract=_ON_SENSOR_FRACT,
        on_trigger_t_f=t_on_sensor + 5.0,
        off_sensor_fract=_OFF_SENSOR_FRACT,
        off_trigger_t_f=t_off_sensor + 5.0,
        outlet_temp_f=140.0,
    )
    shed = Controls(
        on_sensor_fract=_ON_SENSOR_FRACT,
        on_trigger_t_f=t_on_sensor - 5.0,
        off_sensor_fract=_OFF_SENSOR_FRACT,
        off_trigger_t_f=t_off_sensor + 5.0,
        outlet_temp_f=140.0,
    )
    return WaterHeater.from_nominal_capacity(
        nominal_capacity_kbtuh=100.0,
        control_schedule=schedule,
        control_map={"normal": normal, "shed": shed},
    )


def _schedule_with_switch() -> list[str]:
    return ["normal"] * _SWITCH_HOUR + ["shed"] * (24 - _SWITCH_HOUR)


class TestUpdateStateModeSwitch:

    def test_tank_state_preconditions(self):
        """Shed controls would keep a running heater on but not start an idle one."""
        tank = _make_tank()
        heater = _make_heater(tank, _schedule_with_switch())
        shed = heater.control_map["shed"]

        assert not shed.should_turn_off(tank)
        assert not shed.should_turn_on(tank)

    def test_heater_on_before_switch(self):
        tank = _make_tank()
        heater = _make_heater(tank, _schedule_with_switch())

        heater.update_state(tank, _SWITCH_MIN - 1)

        assert heater.is_active()

    def test_heater_turns_off_at_mode_switch(self):
        tank = _make_tank()
        heater = _make_heater(tank, _schedule_with_switch())

        heater.update_state(tank, _SWITCH_MIN - 1)
        assert heater.is_active()

        heater.update_state(tank, _SWITCH_MIN)

        assert not heater.is_active()

    def test_heater_stays_off_after_switch(self):
        """Within the shed block (no further switch) the heater does not restart."""
        tank = _make_tank()
        heater = _make_heater(tank, _schedule_with_switch())

        heater.update_state(tank, _SWITCH_MIN - 1)
        heater.update_state(tank, _SWITCH_MIN)
        heater.update_state(tank, _SWITCH_MIN + 60)

        assert not heater.is_active()

    def test_heater_stays_on_without_mode_switch(self):
        """Control case: same tank and shed setpoints, but no mode change -> heater keeps heating."""
        tank = _make_tank()
        heater = _make_heater(tank, ["shed"] * 24)
        heater.turn_on()

        heater.update_state(tank, _SWITCH_MIN)

        assert heater.is_active()

    def test_turn_off_only_on_first_interval(self):
        """After the first interval of the new mode, normal control logic resumes."""
        tank = _make_tank()
        heater = _make_heater(tank, _schedule_with_switch())

        heater.update_state(tank, _SWITCH_MIN - 1)
        heater.update_state(tank, _SWITCH_MIN)
        assert not heater.is_active()

        # Restarted heater is not forced off again later in the same hour
        heater.turn_on()
        heater.update_state(tank, _SWITCH_MIN + 1)

        assert heater.is_active()

    def test_ten_minute_intervals(self):
        """With interval_min=10 the switch is at timestep 60 (hour 10), and only there."""
        tank = _make_tank()
        heater = _make_heater(tank, _schedule_with_switch())
        steps_per_hour = 6

        heater.update_state(tank, _SWITCH_HOUR * steps_per_hour - 1, interval_min=10)
        assert heater.is_active()

        heater.update_state(tank, _SWITCH_HOUR * steps_per_hour, interval_min=10)
        assert not heater.is_active()

        heater.turn_on()
        heater.update_state(tank, _SWITCH_HOUR * steps_per_hour + 1, interval_min=10)
        assert heater.is_active()

    def test_mode_switch_at_midnight(self):
        """A change between hour 23 (normal) and hour 0 (shed) is detected."""
        tank = _make_tank()
        heater = _make_heater(tank, ["shed"] + ["normal"] * 23)

        heater.update_state(tank, 24 * 60 - 1)
        assert heater.is_active()

        heater.update_state(tank, 24 * 60)

        assert not heater.is_active()
