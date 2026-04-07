from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecoengine.objects.components.storage.StorageTank import StorageTank


class Controls:
    """
    Defines the on/off control logic for a single WaterHeater, including normal
    operation setpoints and load shift (load-up / shed) overrides.

    Sensor fractions refer to fractional vertical positions in the storage tank
    (0 = bottom, 1 = top).

    Sensor position convention
    --------------------------
    The ON sensor sits *above* the OFF sensor in the tank
    (on_sensor_fract >= off_sensor_fract).

    * ON sensor (upper): the heater turns ON when this sensor drops below
      on_trigger_t_f — i.e. the top of the tank has cooled enough that hot
      water supply is at risk.
    * OFF sensor (lower): the heater turns OFF when this sensor rises above
      off_trigger_t_f — i.e. the entire tank has been heated to setpoint.

    Both sensor parameters are required: the ON sensor drives sizing
    (stratification factor, short-cycling check) and simulation; the OFF
    sensor drives the short-cycling check and simulation.
    """

    def __init__(
        self,
        on_sensor_fract: float,
        on_trigger_t_f: float,
        off_sensor_fract: float,
        off_trigger_t_f: float,
        load_up_sensor_fract: float | None = None,
        load_up_trigger_t_f: float | None = None,
        shed_sensor_fract: float | None = None,
        shed_trigger_t_f: float | None = None,
        load_up_hours: float = 0,
    ) -> None:
        """
        Parameters
        ----------
        on_sensor_fract : float
            Fractional tank height of the ON (upper) temperature sensor
            (0 = bottom, 1 = top). Must be >= off_sensor_fract.
            Used during sizing (stratification factor, short-cycling check) and simulation.
        on_trigger_t_f : float
            Temperature at on_sensor_fract that triggers the heater ON [°F].
            Used during sizing (stratification factor, short-cycling check) and simulation.
        off_sensor_fract : float
            Fractional tank height of the OFF (lower) temperature sensor
            (0 = bottom, 1 = top). Must be <= on_sensor_fract.
            Used during sizing (short-cycling check) and simulation.
        off_trigger_t_f : float
            Temperature at off_sensor_fract that triggers the heater OFF [°F].
            Used during sizing (short-cycling check) and simulation.
        load_up_sensor_fract : float | None
            Sensor fraction used during load-up mode.
        load_up_trigger_t_f : float | None
            OFF trigger temperature during load-up mode [°F].
        shed_sensor_fract : float | None
            Sensor fraction used during shed mode.
        shed_trigger_t_f : float | None
            ON trigger temperature during shed mode [°F].
        load_up_hours : float
            Number of hours spent in load-up mode before the first shed period.
        """
        self.on_sensor_fract      = on_sensor_fract
        self.on_trigger_t_f       = on_trigger_t_f
        self.off_sensor_fract     = off_sensor_fract
        self.off_trigger_t_f      = off_trigger_t_f
        self.load_up_sensor_fract = load_up_sensor_fract
        self.load_up_trigger_t_f  = load_up_trigger_t_f
        self.shed_sensor_fract    = shed_sensor_fract
        self.shed_trigger_t_f     = shed_trigger_t_f
        self.load_up_hours        = load_up_hours

    def should_turn_on(self, storage_tank: StorageTank, mode: str = "normal") -> bool:
        """
        Return True if the heater should turn on given the current tank state and mode.

        Parameters
        ----------
        storage_tank : StorageTank
        mode : str
            One of 'normal', 'load_up', or 'shed'.

        Returns
        -------
        bool
        """
        pass

    def should_turn_off(self, storage_tank: StorageTank, mode: str = "normal") -> bool:
        """
        Return True if the heater should turn off given the current tank state and mode.

        Parameters
        ----------
        storage_tank : StorageTank
        mode : str
            One of 'normal', 'load_up', or 'shed'.

        Returns
        -------
        bool
        """
        pass

    def get_active_mode(self, timestep: int, load_shift_schedule: list[int]) -> str:
        """
        Determine the current operating mode based on the load shift schedule.

        Parameters
        ----------
        timestep : int
            Current simulation timestep (minutes from start of day).
        load_shift_schedule : list[int]
            24-element list of 0s and 1s (0 = shed/off, 1 = run).

        Returns
        -------
        str
            One of 'normal', 'load_up', or 'shed'.
        """
        pass
