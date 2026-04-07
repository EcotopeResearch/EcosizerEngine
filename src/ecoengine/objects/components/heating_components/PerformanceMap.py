class PerformanceMap:
    """
    Wraps HPWH performance map data to predict real-world heating capacity and
    power input as a function of outdoor air temperature and water temperature.
    """

    def __init__(self, map_data):
        """
        Parameters
        ----------
        map_data : object
            Raw performance map data (e.g. loaded from pickle/JSON files).
        """
        self.map_data = map_data

    def get_capacity_kbtuh(self, oat_f, water_temp_f):
        """
        Return heating output capacity in kBTU/hr for the given conditions.

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
        Return electrical power input in kW for the given conditions.

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

    def get_cop(self, oat_f, water_temp_f):
        """
        Return coefficient of performance (COP) for the given conditions.

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

    def is_within_operating_bounds(self, oat_f, water_temp_f):
        """
        Return True if the given conditions are within the map's valid operating range.

        Parameters
        ----------
        oat_f : float
        water_temp_f : float

        Returns
        -------
        bool
        """
        pass
