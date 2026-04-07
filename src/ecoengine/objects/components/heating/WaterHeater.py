class WaterHeater:
    """
    Represents a single heat pump water heater unit. Owns a PerformanceMap
    and a Controls object. Tracks its own active/inactive state.
    """

    def __init__(self, performance_map, controls, model_name=""):
        """
        Parameters
        ----------
        performance_map : PerformanceMap
            Performance map for this specific HPWH model.
        controls : Controls
            Control setpoints and logic for this heater.
        model_name : str
            Human-readable model identifier.
        """
        self.performance_map = performance_map
        self.controls = controls
        self.model_name = model_name
        self._active = False

    def is_active(self):
        """Return True if this heater is currently running."""
        return self._active

    def turn_on(self):
        """Activate this heater."""
        self._active = True

    def turn_off(self):
        """Deactivate this heater."""
        self._active = False

    def get_capacity_kbtuh(self, oat_f, water_temp_f):
        """
        Return heating output capacity [kBTU/hr] at current conditions.

        Parameters
        ----------
        oat_f : float
            Outdoor air temperature [°F].
        water_temp_f : float
            Entering water temperature [°F].

        Returns
        -------
        float
        """
        pass

    def get_power_in_kw(self, oat_f, water_temp_f):
        """
        Return electrical power input [kW] at current conditions.

        Parameters
        ----------
        oat_f : float
        water_temp_f : float

        Returns
        -------
        float
        """
        pass

    def get_output_kbtuh(self, oat_f, water_temp_f):
        """
        Return actual heating output this timestep (0 if inactive).

        Parameters
        ----------
        oat_f : float
        water_temp_f : float

        Returns
        -------
        float
        """
        pass

    def update_state(self, storage_tank, mode="normal"):
        """
        Check controls and update active/inactive state based on current tank condition.

        Parameters
        ----------
        storage_tank : StorageTank
        mode : str
            One of 'normal', 'load_up', or 'shed'.
        """
        pass
