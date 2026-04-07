from __future__ import annotations

import csv
import importlib.resources as pkg_resources

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

# First day-of-year (0-indexed) for each month (0 = January, 11 = December).
# Used to convert a day-of-year into a month index for inlet-water lookups.
_MONTH_START_DAY = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]

_CLIMATE_DATA_PKG = 'ecoengine.data.climate_data'


def _open_climate_csv(filename: str):
    """Return an open text stream for a file in the climate_data package."""
    return (pkg_resources.files(_CLIMATE_DATA_PKG) / filename).open('r', newline='')


def _day_of_year_to_month(day_of_year: int) -> int:
    """
    Convert a 0-indexed day-of-year (0-364) to a 0-indexed month (0-11).
    January = 0, December = 11.
    """
    for month in range(11, -1, -1):
        if day_of_year >= _MONTH_START_DAY[month]:
            return month
    return 0  # shouldn't be reached for valid input


# ---------------------------------------------------------------------------
# ClimateZone
# ---------------------------------------------------------------------------

class ClimateZone:
    """
    Stores outdoor air temperature (OAT) and cold/inlet water temperature for a
    building's location over a typical meteorological year.

    OAT is stored hourly  (8,760 values — one per hour of the year).
    Inlet water temp is stored monthly (12 values — one per month).

    The simulator queries this object at every timestep to obtain ambient
    conditions for heat-pump performance and load calculations.
    """

    def __init__(
        self,
        zone_id: int | None,
        oat_f_by_hour: list[float] | None,
        inlet_water_temp_f_by_month: list[float] | None,
        constant_oat_f: float | None = None,
        constant_inlet_water_temp_f: float | None = None,
    ) -> None:
        """
        Parameters
        ----------
        zone_id : int | None
            Numeric climate zone identifier (1-96 for OAT data;
            1-19 for full CA data including kG/kWh). None for design-condition zones.
        oat_f_by_hour : list[float] | None
            Outdoor air temperatures for every hour of a typical year [°F].
            8,760 elements for real zones; None for design-condition zones.
        inlet_water_temp_f_by_month : list[float] | None
            Average cold-water inlet temperature for each calendar month [°F].
            12 elements for real zones; None for design-condition zones.
        constant_oat_f : float | None
            If set, all OAT queries return this value instead of reading from
            oat_f_by_hour. Set automatically by from_design_conditions().
        constant_inlet_water_temp_f : float | None
            If set, all inlet water temp queries return this value instead of
            reading from inlet_water_temp_f_by_month. Set automatically by
            from_design_conditions().
        """
        self.zone_id = zone_id
        self._oat_f_by_hour = oat_f_by_hour
        self._inlet_water_temp_f_by_month = inlet_water_temp_f_by_month
        self._constant_oat_f = constant_oat_f
        self._constant_inlet_water_temp_f = constant_inlet_water_temp_f

    # ------------------------------------------------------------------
    # Factory constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_zip_code(cls, zip_code: str | int) -> ClimateZone:
        """
        Construct a ClimateZone by looking up the CA climate zone for a zip code
        and loading the corresponding weather data.

        Parameters
        ----------
        zip_code : str | int
            A California 5-digit zip code.

        Returns
        -------
        ClimateZone

        Raises
        ------
        ValueError
            If the zip code is not found in the CA lookup table.
        """
        zone_id = cls._lookup_zone_for_zip(zip_code)
        return cls.from_zone_id(zone_id)

    @classmethod
    def from_weather_station(cls, station_id: str) -> ClimateZone:
        """
        Construct a ClimateZone from a named weather station.

        Parameters
        ----------
        station_id : str
            Weather station name exactly as it appears in the lookup CSV
            (e.g. ``'ID - Boise Air Terminal'``).

        Returns
        -------
        ClimateZone

        Raises
        ------
        ValueError
            If the station name is not found in the lookup table.
        """
        zone_id = cls._lookup_zone_for_station(station_id)
        return cls.from_zone_id(zone_id)

    @classmethod
    def from_zone_id(cls, zone_id: int) -> ClimateZone:
        """
        Construct a ClimateZone directly from a numeric climate zone ID.

        Parameters
        ----------
        zone_id : int
            Climate zone number (1-96 for OAT data; 1-19 for full CA data).

        Returns
        -------
        ClimateZone
        """
        oat_f_by_hour               = cls._load_oat_data(zone_id)
        inlet_water_temp_f_by_month = cls._load_inlet_water_data(zone_id)
        return cls(zone_id, oat_f_by_hour, inlet_water_temp_f_by_month)

    @classmethod
    def _from_zone_id(cls, zone_id: int) -> ClimateZone:
        """Internal alias for from_zone_id, used by from_zip_code / from_weather_station."""
        return cls.from_zone_id(zone_id)

    @classmethod
    def from_design_conditions(
        cls,
        design_oat_f: float | None = None,
        design_inlet_water_temp_f: float | None = None,
    ) -> ClimateZone:
        """
        Create a constant-condition ClimateZone for use when real climate data
        is unavailable.

        Every OAT query returns design_oat_f; every inlet water temp query
        returns design_inlet_water_temp_f. The design values are also returned
        by get_design_oat_f() and get_design_inlet_water_temp_f() directly.

        Parameters
        ----------
        design_oat_f : float | None
            Constant outdoor air temperature to return for all timesteps [°F].
        design_inlet_water_temp_f : float | None
            Constant cold-water inlet temperature to return for all timesteps [°F].

        Returns
        -------
        ClimateZone
        """
        return cls(
            zone_id=None,
            oat_f_by_hour=None,
            inlet_water_temp_f_by_month=None,
            constant_oat_f=design_oat_f,
            constant_inlet_water_temp_f=design_inlet_water_temp_f,
        )

    # ------------------------------------------------------------------
    # Per-timestep queries (called by the simulator at every step)
    # ------------------------------------------------------------------

    def get_oat_f(self, timestep_interval: int, interval_min: int = 1) -> float:
        """
        Return outdoor air temperature at the given simulation timestep.

        OAT data is stored hourly, so this rounds down to the nearest hour.
        Wraps around yearly (safe for multi-year or 3-day simulations that
        start mid-year).

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
        if self._constant_oat_f is not None:
            return self._constant_oat_f
        actual_minute = timestep_interval * interval_min
        hour_of_year  = (actual_minute // 60) % len(self._oat_f_by_hour)
        return self._oat_f_by_hour[hour_of_year]

    def get_inlet_water_temp_f(self, timestep_interval: int, interval_min: int = 1) -> float:
        """
        Return cold/inlet water temperature at the given simulation timestep.

        Inlet water temperature is stored as a monthly average, so the
        timestep is converted to a day-of-year and then to a month.

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
        if self._constant_inlet_water_temp_f is not None:
            return self._constant_inlet_water_temp_f
        actual_minute = timestep_interval * interval_min
        day_of_year   = (actual_minute // (60 * 24)) % 365
        month         = _day_of_year_to_month(day_of_year)
        return self._inlet_water_temp_f_by_month[month]

    # ------------------------------------------------------------------
    # Design-condition queries (used during sizing, not simulation)
    # ------------------------------------------------------------------

    def get_design_oat_f(self) -> float:
        """
        Return the design-day outdoor air temperature [°F].

        For real climate zones: the annual minimum OAT (worst-case heating
        condition for heat-pump sizing).
        For design-condition zones: the constant value set at construction.
        """
        if self._constant_oat_f is not None:
            return self._constant_oat_f
        return min(self._oat_f_by_hour)

    def get_design_inlet_water_temp_f(self) -> float:
        """
        Return the design-day cold water inlet temperature [°F].

        For real climate zones: the coldest monthly average (worst-case
        sizing condition).
        For design-condition zones: the constant value set at construction.
        """
        if self._constant_inlet_water_temp_f is not None:
            return self._constant_inlet_water_temp_f
        return min(self._inlet_water_temp_f_by_month)

    # ------------------------------------------------------------------
    # CSV loading helpers (private)
    # ------------------------------------------------------------------

    @classmethod
    def _lookup_zone_for_zip(cls, zip_code: str | int) -> int:
        """
        Search ZipCode_ClimateZone_Lookup.csv for the given zip code.

        Returns
        -------
        int
            Climate zone ID.

        Raises
        ------
        ValueError
            If the zip code is not in the table.
        """
        zip_str = str(zip_code).strip()
        with _open_climate_csv('ZipCode_ClimateZone_Lookup.csv') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['Zip Code'].strip() == zip_str:
                    return int(row['Building CZ'])
        raise ValueError(
            f"Zip code '{zip_code}' was not found in the CA climate zone lookup. "
            f"Only California zip codes are supported."
        )

    @classmethod
    def _lookup_zone_for_station(cls, station_id: str) -> int:
        """
        Search WeatherStation_ClimateZone_Lookup.csv for the given station name.

        Returns
        -------
        int
            Climate zone ID.

        Raises
        ------
        ValueError
            If the station name is not in the table.
        """
        station_str = str(station_id).strip()
        with _open_climate_csv('WeatherStation_ClimateZone_Lookup.csv') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['Weather Station'].strip() == station_str:
                    return int(row['Building CZ'])
        raise ValueError(
            f"Weather station '{station_id}' was not found in the lookup table."
        )

    @classmethod
    def _load_oat_data(cls, zone_id: int) -> list[float]:
        """
        Load the full-year hourly OAT sequence for the given zone from
        DryBulbTemperatures_ByClimateZone.csv.

        The CSV has one column per climate zone (headers 1-96) and one row
        per hour of the year (8,760 data rows, not including the header).

        Returns
        -------
        list[float]
            8,760 hourly OAT values [°F].
        """
        col_index = zone_id - 1  # CSV columns are 1-indexed

        oat_values = []
        with _open_climate_csv('DryBulbTemperatures_ByClimateZone.csv') as f:
            reader = csv.reader(f)
            next(reader)  # skip header row
            for row in reader:
                oat_values.append(float(row[col_index]))

        return oat_values

    @classmethod
    def _load_inlet_water_data(cls, zone_id: int) -> list[float]:
        """
        Load the 12 monthly average inlet-water temperatures for the given zone
        from InletWaterTemperatures_ByClimateZone.csv.

        The CSV has one column per climate zone (headers 1-96) and one row
        per month (12 data rows, not including the header).

        Returns
        -------
        list[float]
            12 monthly average inlet water temperatures [°F],
            index 0 = January, index 11 = December.
        """
        col_index = zone_id - 1  # CSV columns are 1-indexed

        monthly_temps = []
        with _open_climate_csv('InletWaterTemperatures_ByClimateZone.csv') as f:
            reader = csv.reader(f)
            next(reader)  # skip header row
            for row in reader:
                monthly_temps.append(float(row[col_index]))

        return monthly_temps
