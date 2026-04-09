from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecoengine.objects.components.storage.StorageTank import StorageTank


class Controls:
    """
    Setpoints for one operating mode of a WaterHeater.

    A WaterHeater carries a control_schedule (24-length list of int) and a
    control_map (dict[int, Controls]) so that different Controls objects can
    be active at different hours of the day. Each Controls object represents
    a single mode's setpoints — there is no load-shift scheduling logic here.

    Sensor position convention
    --------------------------
    ON sensor (upper, on_sensor_fract >= off_sensor_fract):
        Heater turns ON when this sensor drops below on_trigger_t_f.
    OFF sensor (lower):
        Heater turns OFF when this sensor rises above off_trigger_t_f.
    """

    def __init__(
        self,
        on_sensor_fract: float,
        on_trigger_t_f: float,
        off_sensor_fract: float,
        off_trigger_t_f: float,
        outlet_temp_f: float,
    ) -> None:
        """
        Parameters
        ----------
        on_sensor_fract : float
            Fractional tank height of the ON (upper) temperature sensor
            (0 = bottom, 1 = top). Must be >= off_sensor_fract.
        on_trigger_t_f : float
            Temperature at on_sensor_fract that triggers the heater ON [°F].
        off_sensor_fract : float
            Fractional tank height of the OFF (lower) temperature sensor
            (0 = bottom, 1 = top). Must be <= on_sensor_fract.
        off_trigger_t_f : float
            Temperature at off_sensor_fract that triggers the heater OFF [°F].
        outlet_temp_f : float
            Target hot-water outlet temperature for this operating mode [°F].
            Typically equal to storage_temp_f for normal operation, but may
            differ for load-up or other modes.
        """
        self.on_sensor_fract  = on_sensor_fract
        self.on_trigger_t_f   = on_trigger_t_f
        self.off_sensor_fract = off_sensor_fract
        self.off_trigger_t_f  = off_trigger_t_f
        self.outlet_temp_f    = outlet_temp_f

    def should_turn_on(self, storage_tank: StorageTank) -> bool:
        """
        Return True if the heater should turn on given the current tank state.

        The heater turns ON when the upper (on) sensor drops below
        ``on_trigger_t_f``.

        Parameters
        ----------
        storage_tank : StorageTank

        Returns
        -------
        bool
        """
        temp = storage_tank.get_temperature_at_fraction(self.on_sensor_fract)
        return temp < self.on_trigger_t_f

    def should_turn_off(self, storage_tank: StorageTank) -> bool:
        """
        Return True if the heater should turn off given the current tank state.

        The heater turns OFF when the lower (off) sensor rises to or above
        ``off_trigger_t_f``.

        Parameters
        ----------
        storage_tank : StorageTank

        Returns
        -------
        bool
        """
        temp = storage_tank.get_temperature_at_fraction(self.off_sensor_fract)
        return temp >= self.off_trigger_t_f
