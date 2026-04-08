from __future__ import annotations


class PerformanceMap:
    """
    Wraps HPWH performance map data to predict real-world heating capacity and
    power input as a function of outdoor air temperature and water temperature.

    Construction
    ------------
    Use one of the factory class methods rather than calling __init__ directly:

    * PerformanceMap.from_model_name(model_name)
        Loads performance map data from the equipment model registry by name.
        (Registry lookup is a stub — to be implemented.)

    * NominalPerformanceMap(nominal_capacity_kbtuh)
        Constant-output placeholder for use during preliminary sizing.
    """

    def __init__(self, map_data: object, model_name: str = "") -> None:
        """
        Parameters
        ----------
        map_data : object
            Raw performance map data (e.g. loaded from pickle/JSON files).
        model_name : str
            Human-readable equipment model identifier (e.g.
            ``'Rheem_PROPH80_T2_RH380-30'``). Used to look up map data from
            the equipment model registry via from_model_name().
        """
        self.map_data   = map_data
        self.model_name = model_name

    @classmethod
    def from_model_name(cls, model_name: str) -> PerformanceMap:
        """
        Load a PerformanceMap from the equipment model registry by name.

        Parameters
        ----------
        model_name : str
            Equipment model identifier as it appears in the model registry
            (e.g. ``'Rheem_PROPH80_T2_RH380-30'``).

        Returns
        -------
        PerformanceMap
        """
        pass  # TODO: load map_data from model registry by model_name

    def get_capacity_kbtuh(self, oat_f: float, water_temp_f: float) -> float:
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

    def get_power_in_kw(self, oat_f: float, water_temp_f: float) -> float:
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

    def get_cop(self, oat_f: float, water_temp_f: float) -> float:
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

    def is_within_operating_bounds(self, oat_f: float, water_temp_f: float) -> bool:
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


class NominalPerformanceMap(PerformanceMap):
    """
    Constant-output performance map for use during preliminary sizing, when a
    real equipment model is not yet selected.

    Every capacity query returns the fixed nominal_capacity_kbtuh regardless of
    outdoor air temperature or water temperature — analogous to how
    ClimateZone.from_design_conditions() returns a constant OAT for all timesteps.
    Power and COP queries remain stubs until a real map is assigned.
    """

    def __init__(self, nominal_capacity_kbtuh: float, model_name: str = "") -> None:
        """
        Parameters
        ----------
        nominal_capacity_kbtuh : float
            Fixed heating output capacity [kBTU/hr] returned for all conditions.
        model_name : str
            Optional human-readable identifier.
        """
        super().__init__(map_data=None, model_name=model_name)
        self.nominal_capacity_kbtuh = nominal_capacity_kbtuh

    def get_capacity_kbtuh(self, oat_f: float, water_temp_f: float) -> float:
        """Return the fixed nominal capacity [kBTU/hr] regardless of conditions."""
        return self.nominal_capacity_kbtuh
