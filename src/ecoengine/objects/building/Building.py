from __future__ import annotations

import json
import numpy as np
import importlib.resources as pkg_resources
from typing import TYPE_CHECKING
from ecoengine.objects.building.ClimateZone import ClimateZone

if TYPE_CHECKING:
    from ecoengine.objects.building.UtilityCostTracker import UtilityCostTracker

# ASHRAE maximum daily GPD per occupancy unit, keyed by building_type.
# Source: ASHRAE/original EcosizerEngine Building subclasses.
_ASHRAE_GPD_PER_UNIT = {
    'mens_dorm':         23.6,   # per student
    'womens_dorm':       19.6,   # per student
    'motel':             21.4,   # per unit
    'nursing_home':      23.4,   # per bed
    'office_building':    2.1,   # per person
    'food_service_a':   11.032,  # per meal
    'food_service_b':    6.44,   # per meal
    'apartment':         54.6,   # per unit
    'elementary_school':  1.34,  # per student
    'junior_high':        3.75,  # per student
    'senior_high':        3.26,  # per student
    # multi_family uses gpdpp * n_people instead
}

# Valid standard GPD specification keys for multi_family buildings.
_STANDARD_GPD_KEYS = ['ca', 'ashLow', 'ashMed', 'ecoMark']


def _load_shape_json(building_type: str) -> dict:
    """Load and return the parsed JSON dict for a building type's load shape file."""
    data_pkg = pkg_resources.files('ecoengine.data.load_shapes')
    try:
        with (data_pkg / f'{building_type}.json').open('r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise ValueError(f"No default load shape found for building type '{building_type}'.")


def _validate_load_shape(load_shape: list[float], label: str = 'load shape') -> None:
    """Raise ValueError if load_shape is not a valid normalized 24-element list."""
    if len(load_shape) != 24:
        raise ValueError(f"{label} must have 24 elements, got {len(load_shape)}.")
    total = sum(load_shape)
    if abs(total - 1.0) > 1e-3:
        raise ValueError(f"{label} must sum to 1.0 (got {total:.4f}).")
    if any(x < 0 for x in load_shape):
        raise ValueError(f"{label} cannot contain negative values.")
    return


class Building:
    """
    Stores information about the building and surrounding environment where a
    DHW system will be sized and/or simulated.

    Holds a ClimateZone (ambient conditions), a UtilityCostTracker (billing
    structure), and the building's DHW load data (daily use and load shapes).
    """

    def __init__(
        self,
        climate_zone: ClimateZone | None,
        daily_dhw_use_supplyT_gal: float,
        peak_load_shape: list[float] | np.ndarray,
        avg_load_shape: list[float] | np.ndarray,
        utility_cost_tracker: UtilityCostTracker | None = None,
        building_type: str = "",
        design_oat_f: float | None = None,
        design_inlet_water_temp_f: float | None = None,
    ) -> None:
        """
        Parameters
        ----------
        climate_zone : ClimateZone | None
            Ambient OAT and cold water temperature data for this location.
            If None and design conditions are provided, a constant-value
            ClimateZone is created automatically from those conditions.
        daily_dhw_use_supplyT_gal : float
            Design daily hot water consumption at supply temperature [gallons].
        peak_load_shape : list[float] | np.ndarray
            Normalized 24-hour load profile for the design (peaky) day.
            Each value is the fraction of daily DHW use in that hour.
        avg_load_shape : list[float] | np.ndarray
            Normalized 24-hour load profile for an average day.
        utility_cost_tracker : UtilityCostTracker | None
        building_type : str
            Label for the building type (e.g. 'multi_family', 'multi_use').
        design_oat_f : float | None
            Design outdoor air temperature [°F]. Used only when climate_zone
            is None; creates a constant-OAT ClimateZone that returns this
            value for every timestep and as the design condition.
        design_inlet_water_temp_f : float | None
            Design cold-water inlet temperature [°F]. Used only when
            climate_zone is None; creates a constant-inlet-temp ClimateZone
            that returns this value for every timestep and as the design
            condition.
        """
        # If no real climate zone is provided but design conditions are given,
        # build a constant-value ClimateZone so the rest of the code can
        # always delegate to self.climate_zone without special-casing None.
        if climate_zone is None and (design_oat_f is not None or design_inlet_water_temp_f is not None):
            climate_zone = ClimateZone.from_design_conditions(design_oat_f, design_inlet_water_temp_f)

        self.climate_zone = climate_zone
        self.daily_dhw_use_supplyT_gal = daily_dhw_use_supplyT_gal
        self.peak_load_shape = np.array(peak_load_shape)
        self.avg_load_shape  = np.array(avg_load_shape)
        self.utility_cost_tracker = utility_cost_tracker
        self.building_type = building_type

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_building_type(
        cls,
        building_type: str | None | list[str | None],
        magnitude: float | None | list,
        climate_zone: ClimateZone | None,
        # multi_family-specific
        gpdpp: float = 25,
        standard_gpd: str | None = None,
        n_br: list[int] | None = None,
        # optional load shape overrides
        # For multi-use: pass a list of (24-element list | None), one per building type.
        # For single use: pass a single 24-element list.
        custom_peak_load_shape: list[float] | list[list[float] | None] | None = None,
        custom_avg_load_shape: list[float] | list[list[float] | None] | None = None,
        # use full annual load shape (multi_family only)
        annual: bool = False,
        # forwarded to __init__
        **kwargs,
    ) -> Building:
        """
        Construct a Building from a named building type (or a list of types for
        multi-use buildings).

        Parameters
        ----------
        building_type : str | None | list[str | None]
            Named type(s): 'multi_family', 'apartment', 'motel', 'office_building',
            'mens_dorm', 'womens_dorm', 'nursing_home', 'food_service_a',
            'food_service_b', 'elementary_school', 'junior_high', 'senior_high'.
            Use None for a custom-load-shape-only building (requires
            custom_peak_load_shape). Pass a list for a multi-use building.
        magnitude : float | None | list
            Occupancy metric matching the building type(s). For multi-use, pass
            a list of the same length as building_type. An individual entry may
            be None only when building_type is also None for that slot (magnitude
            is then derived from the sum of the unnormalized custom load shape).
        climate_zone : ClimateZone | None
        gpdpp : float
            Gallons per person per day. Used for 'multi_family' when standard_gpd
            is None.
        standard_gpd : str | None
            Standard GPD key for 'multi_family': 'ashLow', 'ashMed', 'ecoMark',
            or 'ca'. Overrides gpdpp when provided.
        n_br : list[int] | None
            Unit counts by bedroom size [0BR-5BR]. Required for standard_gpd='ca'.
        custom_peak_load_shape : list[float] | list[list[float] | None] | None
            24-element normalized peak load shape override. For multi-use, pass
            a list of shapes (or None entries to use the default for that type).
        custom_avg_load_shape : list[float] | list[list[float] | None] | None
            Same as custom_peak_load_shape but for the average day.
        annual : bool
            If True, load the 8760-hour annual load shape instead of the 24-hour
            daily shape. Only supported for multi_family buildings.
        **kwargs
            Forwarded to Building.__init__ (e.g. design_oat_f, utility_cost_tracker).

        Returns
        -------
        Building

        Raises
        ------
        ValueError
        """
        # --- Collapse single-element lists to scalars ---
        if isinstance(building_type, list) and len(building_type) == 1:
            building_type = building_type[0]
        if isinstance(magnitude, list) and len(magnitude) == 1:
            magnitude = magnitude[0]

        # --- Multi-use path ---
        if isinstance(building_type, list):
            return cls._from_multi_use(
                building_type, magnitude, climate_zone,
                custom_peak_load_shape, custom_avg_load_shape,
                gpdpp, standard_gpd, n_br, **kwargs,
            )

        # --- Single building path ---
        if not isinstance(building_type, (str, type(None))):
            raise ValueError(
                "building_type must be a string, None (for custom load shape only), "
                "or a list of strings for multi-use buildings."
            )

        daily_gal, peak_ls, avg_ls = cls._compute_single_gal_and_shapes(
            building_type, magnitude,
            custom_peak_load_shape, custom_avg_load_shape,
            gpdpp, standard_gpd, n_br,
        )

        building = cls(
            climate_zone=climate_zone,
            daily_dhw_use_supplyT_gal=daily_gal,
            peak_load_shape=peak_ls,
            avg_load_shape=avg_ls,
            building_type=building_type if building_type is not None else 'custom',
            **kwargs,
        )
        if annual:
            building.set_to_annual_load_shape()
        return building

    @classmethod
    def _from_multi_use(
        cls,
        building_types: list[str | None],
        magnitudes: list,
        climate_zone: ClimateZone | None,
        custom_peak_load_shapes: list[list[float] | None] | None,
        custom_avg_load_shapes: list[list[float] | None] | None,
        gpdpp: float,
        standard_gpd: str | None,
        n_br: list[int] | None,
        **kwargs,
    ) -> Building:
        """Blend multiple building types into a single weighted Building."""
        n = len(building_types)

        # Validate magnitudes list
        if not isinstance(magnitudes, list):
            raise ValueError(
                f"Multi-use building requires a list of magnitudes (one per building type), "
                f"got a single value for {n} types."
            )
        if len(magnitudes) != n:
            raise ValueError(
                f"Multi-use building: got {n} building types but "
                f"{len(magnitudes)} magnitude values."
            )

        # Normalize custom load shape lists
        cpls_list = cls._normalize_multi_use_shapes(custom_peak_load_shapes, n, 'custom_peak_load_shape')
        cals_list = cls._normalize_multi_use_shapes(custom_avg_load_shapes,  n, 'custom_avg_load_shape')

        # Compute per-sub-building gal and shapes
        sub_daily_gals, sub_peaks, sub_avgs = [], [], []
        for bt, mag, cpls, cals in zip(building_types, magnitudes, cpls_list, cals_list):
            daily_gal, peak_ls, avg_ls = cls._compute_single_gal_and_shapes(
                bt, mag, cpls, cals, gpdpp, standard_gpd, n_br,
            )
            sub_daily_gals.append(daily_gal)
            sub_peaks.append(peak_ls)
            sub_avgs.append(avg_ls)

        # Blend load shapes weighted by each sub-building's daily use
        total_daily_gal = sum(sub_daily_gals)
        blended_peak = sum(g * ls for g, ls in zip(sub_daily_gals, sub_peaks)) / total_daily_gal
        blended_avg  = sum(g * ls for g, ls in zip(sub_daily_gals, sub_avgs))  / total_daily_gal

        return cls(
            climate_zone=climate_zone,
            daily_dhw_use_supplyT_gal=total_daily_gal,
            peak_load_shape=blended_peak,
            avg_load_shape=blended_avg,
            building_type='multi_use',
            **kwargs,
        )

    @staticmethod
    def _normalize_multi_use_shapes(
        custom_shapes: list[list[float] | None] | None,
        n: int,
        label: str,
    ) -> list[list[float] | None]:
        """Return a list of n per-building custom shape entries (or None)."""
        if custom_shapes is None:
            return [None] * n
        # Guard: a bare 24-element list of numbers is a single load shape, not a list-of-shapes
        if (len(custom_shapes) == 24
                and not isinstance(custom_shapes[0], (list, type(None)))):
            raise ValueError(
                f"For multi-use buildings, {label} must be a list of load shapes "
                f"(one per building type), not a single 24-element list."
            )
        if len(custom_shapes) != n:
            raise ValueError(
                f"Multi-use building: got {n} building types but "
                f"{len(custom_shapes)} {label} values."
            )
        return custom_shapes

    @classmethod
    def _compute_single_gal_and_shapes(
        cls,
        building_type: str | None,
        magnitude: float | None,
        custom_peak_ls: list[float] | None,
        custom_avg_ls: list[float] | None,
        gpdpp: float,
        standard_gpd: str | None,
        n_br: list[int] | None,
    ) -> tuple[float, np.ndarray, np.ndarray]:
        """
        Compute (daily_dhw_use_supplyT_gal, peak_load_shape, avg_load_shape)
        for one building type.  building_type may be None for custom-only.
        """
        # ------------------------------------------------------------------
        # building_type = None  →  custom load shape, no named type
        # ------------------------------------------------------------------
        if building_type is None:
            if custom_peak_ls is None:
                raise ValueError(
                    "building_type=None requires a custom_peak_load_shape."
                )
            raw = list(custom_peak_ls)
            raw_sum = sum(raw)

            if magnitude is None:
                # derive magnitude from unnormalized shape sum
                daily_gal = float(raw_sum)
                peak_ls   = np.array([x / raw_sum for x in raw])
            else:
                daily_gal = float(magnitude)
                # normalize if unnormalized, otherwise validate
                if abs(raw_sum - 1.0) > 1e-3:
                    peak_ls = np.array([x / raw_sum for x in raw])
                else:
                    _validate_load_shape(raw, 'custom_peak_load_shape')
                    peak_ls = np.array(raw)

            if custom_avg_ls is not None:
                raw_avg     = list(custom_avg_ls)
                avg_sum     = sum(raw_avg)
                avg_ls      = np.array([x / avg_sum for x in raw_avg])
                _validate_load_shape(list(avg_ls), 'custom_avg_load_shape')
            else:
                avg_ls = peak_ls.copy()

            return daily_gal, peak_ls, avg_ls

        # ------------------------------------------------------------------
        # Named building type
        # ------------------------------------------------------------------
        if not isinstance(magnitude, (int, float)) or magnitude <= 0:
            raise ValueError("magnitude must be a positive number.")

        # Compute daily_gal
        if building_type == 'multi_family':
            if standard_gpd is not None:
                if not isinstance(standard_gpd, str) or standard_gpd not in _STANDARD_GPD_KEYS:
                    raise ValueError(
                        f"standard_gpd must be one of {_STANDARD_GPD_KEYS}, got '{standard_gpd}'."
                    )
                data = _load_shape_json('multi_family')
                if standard_gpd.lower() == 'ca':
                    if (n_br is None or not isinstance(n_br, (list, np.ndarray))
                            or len(n_br) != 6 or sum(n_br) == 0):
                        raise ValueError(
                            "standard_gpd='ca' requires n_br: a 6-element list "
                            "[0BR, 1BR, 2BR, 3BR, 4BR, 5BR]."
                        )
                    daily_totals = np.zeros(365)
                    for i in range(6):
                        daily_totals += n_br[i] * np.array(data['ca_gpdpp'][f'{i}br'])
                    gpdpp = round(float(np.percentile(daily_totals, 98)) / sum(n_br), 1)
                else:
                    gpdpp = data['gpdpp'][standard_gpd][0]
            if not isinstance(gpdpp, (int, float)):
                raise ValueError("gpdpp must be a number.")
            daily_gal = gpdpp * magnitude

        elif building_type in _ASHRAE_GPD_PER_UNIT:
            daily_gal = _ASHRAE_GPD_PER_UNIT[building_type] * magnitude

        else:
            raise ValueError(
                f"Unrecognized building_type '{building_type}'. "
                f"Valid types: {sorted(list(_ASHRAE_GPD_PER_UNIT.keys()) + ['multi_family'])}"
            )

        # Load shapes
        if custom_peak_ls is not None:
            raw = list(custom_peak_ls)
            _validate_load_shape(raw, 'custom_peak_load_shape')
            peak_ls = np.array(raw)
        else:
            data    = _load_shape_json(building_type)
            peak_ls = np.array(data['loadshapes']['Stream'])

        if custom_avg_ls is not None:
            raw = list(custom_avg_ls)
            _validate_load_shape(raw, 'custom_avg_load_shape')
            avg_ls = np.array(raw)
        else:
            data    = _load_shape_json(building_type)
            avg_key = 'Stream_Avg' if 'Stream_Avg' in data['loadshapes'] else 'Stream'
            avg_ls  = np.array(data['loadshapes'][avg_key])

        return daily_gal, peak_ls, avg_ls

    # ------------------------------------------------------------------
    # Annual vs daily load shape switching
    # ------------------------------------------------------------------

    def is_annual_load_shape(self) -> bool:
        """Return True if the building is currently using the 8760-hour annual load shape."""
        return len(self.peak_load_shape) == 8760

    def set_to_annual_load_shape(self) -> None:
        """
        Switch to the full 8760-hour annual load shape.

        Only supported for multi_family buildings, which have an
        'Annual_Normalized' profile in their load shape JSON. The annual
        shape serves as both peak and avg (there is no separate peaky day
        for an annual simulation).

        Raises
        ------
        ValueError
            If called on a non-multi_family building type.
        """
        if self.building_type != 'multi_family':
            raise ValueError(
                "Annual load shapes are only available for multi_family buildings. "
                f"This building is type '{self.building_type}'."
            )
        data      = _load_shape_json('multi_family')
        annual_ls = np.array(data['loadshapes']['Annual_Normalized'])
        self.peak_load_shape = annual_ls
        self.avg_load_shape  = annual_ls  # one shape for the whole year; no separate peak/avg

    def set_to_daily_load_shape(self) -> None:
        """
        Switch back to the 24-hour daily load shapes (Stream / Stream_Avg).

        Only supported for multi_family buildings.

        Raises
        ------
        ValueError
            If called on a non-multi_family building type.
        """
        if self.building_type != 'multi_family':
            raise ValueError(
                "set_to_daily_load_shape() is only available for multi_family buildings. "
                f"This building is type '{self.building_type}'."
            )
        data = _load_shape_json('multi_family')
        self.peak_load_shape = np.array(data['loadshapes']['Stream'])
        self.avg_load_shape  = np.array(data['loadshapes']['Stream_Avg'])

    # ------------------------------------------------------------------
    # Simulation interface
    # ------------------------------------------------------------------

    def get_dhw_load_supplyT_gal(
        self,
        timestep_interval: int,
        interval_min: int = 1,
        use_avg: bool = False,
    ) -> float:
        """
        Return the DHW load in gallons at supply temperature for one timestep.

        The load shape describes what fraction of the daily total falls in each
        hour. The returned value is scaled down to the interval duration so that
        summing over all intervals in a day always equals daily_dhw_use_supplyT_gal.

        Parameters
        ----------
        timestep_interval : int
            Number of intervals elapsed from the start of the simulation day/year.
        interval_min : int
            Length of each interval in minutes. Defaults to 1 (minute-resolution).
        use_avg : bool
            If True, use avg_load_shape; otherwise use peak_load_shape.

        Returns
        -------
        float
            Gallons of DHW load at supply temperature for this interval.
        """
        load_shape    = self.avg_load_shape if use_avg else self.peak_load_shape
        actual_minute = timestep_interval * interval_min
        # For 24-hour daily shapes, wrap within the day (memory-efficient: no tiling).
        # For 8760-hour annual shapes, index directly into the year (wrap at year boundary).
        n_hours    = len(load_shape)
        hour_index = (actual_minute // 60) % n_hours
        return self.daily_dhw_use_supplyT_gal * load_shape[hour_index] * interval_min / 60

    def get_oat_f(self, timestep_interval: int, interval_min: int = 1) -> float:
        """
        Return outdoor air temperature at the given timestep via ClimateZone.

        Parameters
        ----------
        timestep_interval : int
            Number of intervals elapsed from the start of the simulation.
        interval_min : int
            Length of each interval in minutes. Defaults to 1 (minute-resolution).
            Example: timestep_interval=3, interval_min=15 → minute 45.

        Returns
        -------
        float
            Outdoor air temperature [°F].
        """
        return self.climate_zone.get_oat_f(timestep_interval, interval_min)

    def get_inlet_water_temp_f(self, timestep_interval: int, interval_min: int = 1) -> float:
        """
        Return cold/inlet water temperature at the given timestep via ClimateZone.

        Parameters
        ----------
        timestep_interval : int
            Number of intervals elapsed from the start of the simulation.
        interval_min : int
            Length of each interval in minutes. Defaults to 1 (minute-resolution).
            Example: timestep_interval=3, interval_min=15 → minute 45.

        Returns
        -------
        float
            Inlet water temperature [°F].
        """
        return self.climate_zone.get_inlet_water_temp_f(timestep_interval, interval_min)

    def get_design_oat_f(self) -> float | None:
        """
        Return the design-day outdoor air temperature [°F].

        Delegates to ClimateZone.get_design_oat_f(). Returns None if no
        climate zone (real or design-condition) was provided at construction.
        """
        if self.climate_zone is not None:
            return self.climate_zone.get_design_oat_f()
        return None

    def get_design_inlet_water_temp_f(self) -> float | None:
        """
        Return the design-day cold/inlet water temperature [°F].

        Delegates to ClimateZone.get_design_inlet_water_temp_f(). Returns
        None if no climate zone was provided at construction.
        """
        if self.climate_zone is not None:
            return self.climate_zone.get_design_inlet_water_temp_f()
        return None
