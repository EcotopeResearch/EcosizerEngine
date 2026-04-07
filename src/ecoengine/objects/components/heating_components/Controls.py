class Controls:
    """
    Defines the on/off control logic for a single WaterHeater, including normal
    operation setpoints and load shift (load-up / shed) overrides.

    Sensor fractions refer to fractional vertical positions in the storage tank
    (0 = bottom, 1 = top).
    """

    def __init__(
        self,
        on_sensor_fract,
        off_sensor_fract,
        on_trigger_t_f,
        off_trigger_t_f,
        load_up_sensor_fract=None,
        load_up_trigger_t_f=None,
        shed_sensor_fract=None,
        shed_trigger_t_f=None,
        load_up_hours=0,
    ):
        """
        Parameters
        ----------
        on_sensor_fract : float
            Fractional tank height of the ON temperature sensor.
        off_sensor_fract : float
            Fractional tank height of the OFF temperature sensor.
        on_trigger_t_f : float
            Temperature at on_sensor_fract that triggers the heater ON [°F].
        off_trigger_t_f : float
            Temperature at off_sensor_fract that triggers the heater OFF [°F].
        load_up_sensor_fract : float, optional
            Sensor fraction used during load-up mode.
        load_up_trigger_t_f : float, optional
            OFF trigger temperature during load-up mode [°F].
        shed_sensor_fract : float, optional
            Sensor fraction used during shed mode.
        shed_trigger_t_f : float, optional
            ON trigger temperature during shed mode [°F].
        load_up_hours : float
            Number of hours spent in load-up mode before the first shed period.
        """
        self.on_sensor_fract = on_sensor_fract
        self.off_sensor_fract = off_sensor_fract
        self.on_trigger_t_f = on_trigger_t_f
        self.off_trigger_t_f = off_trigger_t_f
        self.load_up_sensor_fract = load_up_sensor_fract
        self.load_up_trigger_t_f = load_up_trigger_t_f
        self.shed_sensor_fract = shed_sensor_fract
        self.shed_trigger_t_f = shed_trigger_t_f
        self.load_up_hours = load_up_hours

    def should_turn_on(self, storage_tank, mode="normal"):
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

    def should_turn_off(self, storage_tank, mode="normal"):
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

    def get_active_mode(self, timestep, load_shift_schedule):
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
