from __future__ import annotations

import csv
import math
from io import TextIOWrapper

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Cumulative hour at the start of each month (non-leap year).
# Index 0 = Jan start (hour 0); index 12 = sentinel (hour 8760).
_MONTH_HOUR_START = [
    0,     # Jan   (0  × 24 cumulative hours)
    744,   # Feb   (31 × 24)
    1416,  # Mar   (+28 × 24)
    2160,  # Apr   (+31 × 24)
    2880,  # May   (+30 × 24)
    3624,  # Jun   (+31 × 24)
    4344,  # Jul   (+30 × 24)
    5088,  # Aug   (+31 × 24)
    5832,  # Sep   (+31 × 24)
    6552,  # Oct   (+30 × 24)
    7296,  # Nov   (+31 × 24)
    8016,  # Dec   (+30 × 24)
    8760,  # sentinel
]

_MONTH_NAMES = [
    "January", "February", "March",     "April",
    "May",     "June",     "July",      "August",
    "September","October", "November",  "December",
]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _hour_to_month(hour_of_year: int) -> int:
    """Return the 0-based month index for *hour_of_year* (0–8759)."""
    for m in range(11, -1, -1):
        if hour_of_year >= _MONTH_HOUR_START[m]:
            return m
    return 0


def _is_hour_in_range(
    hour_of_day: int,
    start: int | float | None,
    end: int | float | None,
) -> bool:
    """
    Return True if *hour_of_day* (0–23) falls within [start, end).

    - If *start* or *end* is None → False.
    - If *start* == *end* → False (zero-length period).
    - If *end* < *start* → wrap-around range (e.g. 22:00–06:00).
    """
    if start is None or end is None:
        return False
    if end < start:
        return hour_of_day >= start or hour_of_day < end
    return start <= hour_of_day < end


def _validate_params(
    monthly_base_charge,
    pk_start_hour: list,
    pk_end_hour: list,
    pk_demand_charge: list,
    pk_energy_charge: list,
    off_pk_demand_charge: list,
    off_pk_energy_charge: list,
    start_month: list,
    end_month: list,
) -> None:
    """
    Validate list-normalised rate parameters.

    Raises ``ValueError`` with the same message strings as the original
    EcosizerEngine implementation so that existing error-message checks
    continue to pass.
    """
    if monthly_base_charge is None or not isinstance(monthly_base_charge, (int, float)):
        raise ValueError("Error: monthly base charge must be a number.")

    n = len(pk_start_hour)
    if not (
        len(pk_end_hour) == len(pk_demand_charge) == len(pk_energy_charge)
        == len(off_pk_demand_charge) == len(off_pk_energy_charge)
        == len(start_month) == len(end_month) == n
    ):
        raise ValueError(
            "Error: pk_start_hour, pk_end_hour, pk_demand_charge, pk_energy_charge, "
            "off_pk_demand_charge, and off_pk_energy_charge must all be the same length."
        )

    for i in range(n):
        if (
            pk_start_hour[i] is None
            or not isinstance(pk_start_hour[i], (int, float))
            or pk_start_hour[i] < 0
            or pk_start_hour[i] > 23
        ):
            raise ValueError("Error: peak start hour must be a number between 0 and 23.")

        if (
            pk_end_hour[i] is None
            or not isinstance(pk_end_hour[i], (int, float))
            or pk_end_hour[i] < pk_start_hour[i]
            or pk_end_hour[i] > 24
        ):
            raise ValueError(
                "Error: peak end hour must be a number between peak start hour and 24."
            )

        if pk_demand_charge[i] is None or not isinstance(pk_demand_charge[i], (int, float)):
            raise ValueError("Error: peak demand charge must be a number.")

        if off_pk_demand_charge[i] is None or not isinstance(off_pk_demand_charge[i], (int, float)):
            raise ValueError("Error: off-peak demand charge must be a number.")

        if pk_energy_charge[i] is None or not isinstance(pk_energy_charge[i], (int, float)):
            raise ValueError("Error: peak energy charge must be a number.")

        if off_pk_energy_charge[i] is None or not isinstance(off_pk_energy_charge[i], (int, float)):
            raise ValueError("Error: off-peak energy charge must be a number.")

        if start_month[i] is None or not isinstance(start_month[i], int):
            raise ValueError("Error: start_month must be a number between 0 and 11.")

        if i == 0:
            if start_month[i] != 0:
                raise ValueError("Error: first start_month must be 0.")
        elif start_month[i] != end_month[i - 1]:
            raise ValueError(
                "Error: current start_month must be equal to previous end month."
            )

        if (
            end_month[i] is None
            or not isinstance(end_month[i], int)
            or end_month[i] <= start_month[i]
        ):
            raise ValueError(
                "Error: end_month must be a number between (start_month+1) - 12."
            )

        if i == len(end_month) - 1 and end_month[i] != 12:
            raise ValueError("Error: final end_month must be 12.")


def _fill_period_maps(
    demand_period_chart: list[int],
    demand_charge_map: dict[int, float],
    energy_charge_map: dict[int, float],
    is_peak_map: dict[int, bool],
    is_discount_map: dict[int, bool],
    off_pk_demand: float,
    pk_demand: float,
    off_pk_energy: float,
    pk_energy: float,
    pk_start: int | float,
    pk_end: int | float,
    start_month: int,
    end_month: int,
    dscnt_energy: float | None,
    dscnt_demand: float | None,
    dscnt_start: int | float | None,
    dscnt_end: int | float | None,
    include_discount: bool,
    num_periods: int,
) -> None:
    """
    Populate charge maps and demand_period_chart for months [start_month, end_month).

    Period key scheme (num_periods=2, no discount):
        off-peak = month * 2
        peak     = month * 2 + 1

    Period key scheme (num_periods=3, with discount):
        off-peak = month * 3
        peak     = month * 3 + 1
        discount = month * 3 + 2
    """
    for m in range(start_month, end_month):
        off_key = m * num_periods
        pk_key  = m * num_periods + 1
        dc_key  = m * num_periods + 2

        demand_charge_map[off_key] = off_pk_demand
        energy_charge_map[off_key] = off_pk_energy
        is_peak_map[off_key]       = False
        is_discount_map[off_key]   = False

        demand_charge_map[pk_key]  = pk_demand
        energy_charge_map[pk_key]  = pk_energy
        is_peak_map[pk_key]        = True
        is_discount_map[pk_key]    = False

        if include_discount:
            demand_charge_map[dc_key] = dscnt_demand
            energy_charge_map[dc_key] = dscnt_energy
            is_peak_map[dc_key]       = False
            is_discount_map[dc_key]   = True

    for m in range(start_month, end_month):
        h_start = _MONTH_HOUR_START[m]
        h_end   = _MONTH_HOUR_START[m + 1]
        off_key = m * num_periods
        pk_key  = m * num_periods + 1
        dc_key  = m * num_periods + 2

        for h in range(h_start, h_end):
            hod = h % 24
            if _is_hour_in_range(hod, pk_start, pk_end):
                demand_period_chart[h] = pk_key
            elif include_discount and _is_hour_in_range(hod, dscnt_start, dscnt_end):
                demand_period_chart[h] = dc_key
            else:
                demand_period_chart[h] = off_key


# ---------------------------------------------------------------------------
# UtilityCostTracker
# ---------------------------------------------------------------------------

class UtilityCostTracker:
    """
    Stores a utility billing structure and provides per-timestep rate lookups.

    Supports monthly base charges, peak/off-peak demand charges ($/kW), and
    peak/off-peak energy charges ($/kWh), with optional seasonal variation and
    an optional third discount period (e.g. overnight super-off-peak tariffs).

    Period key scheme
    -----------------
    Without discount (num_periods = 2):
        ``month × 2``     → off-peak
        ``month × 2 + 1`` → peak

    With discount (num_periods = 3):
        ``month × 3``     → off-peak
        ``month × 3 + 1`` → peak
        ``month × 3 + 2`` → discount

    Construction
    ------------
    Use the factory classmethods rather than calling ``__init__`` directly::

        uc = UtilityCostTracker.from_params(
            monthly_base_charge=190.0,
            pk_start_hour=16,
            pk_end_hour=21,
            pk_demand_charge=38.75,
            pk_energy_charge=0.21585,
            off_pk_demand_charge=30.20,
            off_pk_energy_charge=0.14341,
        )

        uc = UtilityCostTracker.from_csv("utility_rates.csv")
    """

    def __init__(
        self,
        demand_period_chart: list[int],
        demand_charge_map: dict[int, float],
        energy_charge_map: dict[int, float],
        is_peak_map: dict[int, bool],
        is_discount_map: dict[int, bool],
        monthly_base_charge: float,
        energy_charge_by_hour: list[float] | None = None,
        include_discount: bool = False,
    ) -> None:
        self.demand_period_chart  = demand_period_chart
        self.demand_charge_map    = demand_charge_map
        self.energy_charge_map    = energy_charge_map
        self.is_peak_map          = is_peak_map
        self.is_discount_map      = is_discount_map
        self.monthly_base_charge  = monthly_base_charge
        self.energy_charge_by_hour: list[float] = energy_charge_by_hour or []
        self.include_discount     = include_discount

    # ------------------------------------------------------------------
    # Factory constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_params(
        cls,
        monthly_base_charge: float,
        pk_start_hour,
        pk_end_hour,
        pk_demand_charge,
        pk_energy_charge,
        off_pk_demand_charge,
        off_pk_energy_charge,
        start_month=0,
        end_month=12,
        include_discount: bool = False,
        dscnt_start_hour=None,
        dscnt_end_hour=None,
        discnt_demand_charge=None,
        discnt_energy_charge=None,
    ) -> UtilityCostTracker:
        """
        Build a UtilityCostTracker from rate parameters.

        All rate/hour/month parameters may be scalars (uniform year-round rate)
        or lists (seasonal variation).  When lists are supplied they must all
        have the same length *n*, where each element describes one contiguous
        block of months.  ``start_month`` and ``end_month`` must partition
        ``[0, 12]`` without gaps or overlaps: ``start_month[0]`` must be 0,
        ``end_month[-1]`` must be 12, and each ``start_month[i]`` must equal
        ``end_month[i-1]``.

        Parameters
        ----------
        monthly_base_charge : float
            Fixed monthly connection charge [$].
        pk_start_hour : int or list[int]
            Hour of day (0–23) when the peak period begins.
        pk_end_hour : int or list[int]
            Hour of day (pk_start_hour–24) when the peak period ends.
            ``pk_end_hour == pk_start_hour`` → no peak period.
            ``pk_start_hour == 0, pk_end_hour == 24`` → all-peak day.
        pk_demand_charge : float or list[float]
            Peak demand charge [$/kW].
        pk_energy_charge : float or list[float]
            Peak energy rate [$/kWh].
        off_pk_demand_charge : float or list[float]
            Off-peak demand charge [$/kW].
        off_pk_energy_charge : float or list[float]
            Off-peak energy rate [$/kWh].
        start_month : int or list[int]
            0-based month index where each rate block begins.  Default 0.
        end_month : int or list[int]
            0-based month index where each rate block ends (exclusive).
            Default 12.
        include_discount : bool
            If True, a third discount period is added within each month.
        dscnt_start_hour : int or list[int] or None
            Discount period start hour.
        dscnt_end_hour : int or list[int] or None
            Discount period end hour.
        discnt_demand_charge : float or list[float] or None
            Discount demand charge [$/kW].
        discnt_energy_charge : float or list[float] or None
            Discount energy rate [$/kWh].

        Returns
        -------
        UtilityCostTracker

        Raises
        ------
        ValueError
            If any parameter fails validation.
        """
        def _to_list(v, n: int | None = None) -> list:
            if isinstance(v, list):
                return v
            return [v] if n is None else [v] * n

        pk_start_hour      = _to_list(pk_start_hour)
        n                  = len(pk_start_hour)
        pk_end_hour        = _to_list(pk_end_hour)
        pk_demand_charge   = _to_list(pk_demand_charge)
        pk_energy_charge   = _to_list(pk_energy_charge)
        off_pk_demand_charge  = _to_list(off_pk_demand_charge)
        off_pk_energy_charge  = _to_list(off_pk_energy_charge)
        start_month        = _to_list(start_month)
        end_month          = _to_list(end_month)
        dscnt_start_hour   = _to_list(dscnt_start_hour,   n)
        dscnt_end_hour     = _to_list(dscnt_end_hour,     n)
        discnt_demand_charge = _to_list(discnt_demand_charge, n)
        discnt_energy_charge = _to_list(discnt_energy_charge, n)

        _validate_params(
            monthly_base_charge,
            pk_start_hour, pk_end_hour,
            pk_demand_charge, pk_energy_charge,
            off_pk_demand_charge, off_pk_energy_charge,
            start_month, end_month,
        )

        num_periods         = 3 if include_discount else 2
        demand_period_chart = [0] * 8760
        demand_charge_map   = {}
        energy_charge_map   = {}
        is_peak_map         = {}
        is_discount_map     = {}

        for i in range(n):
            _fill_period_maps(
                demand_period_chart,
                demand_charge_map, energy_charge_map,
                is_peak_map, is_discount_map,
                off_pk_demand_charge[i], pk_demand_charge[i],
                off_pk_energy_charge[i], pk_energy_charge[i],
                pk_start_hour[i], pk_end_hour[i],
                start_month[i], end_month[i],
                discnt_energy_charge[i], discnt_demand_charge[i],
                dscnt_start_hour[i], dscnt_end_hour[i],
                include_discount, num_periods,
            )

        return cls(
            demand_period_chart=demand_period_chart,
            demand_charge_map=demand_charge_map,
            energy_charge_map=energy_charge_map,
            is_peak_map=is_peak_map,
            is_discount_map=is_discount_map,
            monthly_base_charge=monthly_base_charge,
            include_discount=include_discount,
        )

    @classmethod
    def from_csv(
        cls,
        csv_path: str | None = None,
        csv_file: TextIOWrapper | None = None,
    ) -> UtilityCostTracker:
        """
        Build a UtilityCostTracker from an 8760-row CSV file.

        The CSV must have a header row with (at minimum) these columns:
        ``Energy Rate ($/kWh)``, ``Demand Rate ($/kW)``,
        ``Demand Period``, ``Monthly Base Charge``.

        ``Monthly Base Charge`` is read from the first data row only.
        Demand and energy rates are read from the first row in which each
        ``Demand Period`` value appears; subsequent rows may leave those
        columns blank.  Demand periods with odd labels are treated as peak;
        even labels as off-peak.

        Parameters
        ----------
        csv_path : str or None
        csv_file : TextIOWrapper or None

        Returns
        -------
        UtilityCostTracker

        Raises
        ------
        ValueError
            On missing columns, wrong row count, or bad cell values.
        """
        if csv_path is None and csv_file is None:
            raise ValueError("Either csv_path or csv_file must be provided.")

        opened_here = False
        if csv_file is None:
            csv_file    = open(csv_path, "r", newline="")
            opened_here = True

        try:
            reader = csv.reader(csv_file)
            header = next(reader)
            rows   = list(reader)
        finally:
            if opened_here:
                csv_file.close()

        if len(rows) != 8760:
            raise ValueError(
                f"Error: length of utility calculation csv must be 8760. "
                f"Instead recieved a length of {len(rows)}."
            )

        required = [
            "Energy Rate ($/kWh)", "Demand Rate ($/kW)",
            "Demand Period", "Monthly Base Charge",
        ]
        missing = [c for c in required if c not in header]
        if missing:
            raise ValueError(
                f"Missing Columns from utility calculation csv: {missing}."
            )

        energy_idx = header.index("Energy Rate ($/kWh)")
        demand_idx = header.index("Demand Rate ($/kW)")
        period_idx = header.index("Demand Period")
        base_idx   = header.index("Monthly Base Charge")

        try:
            monthly_base_charge = float(rows[0][base_idx])
        except (ValueError, IndexError):
            raise ValueError(
                "Unable to read value in row 0 of csv. "
                "Please check values for Monthly Base Charge in this row."
            )

        demand_period_chart   = [0] * 8760
        demand_charge_map     = {}
        energy_charge_map     = {}
        is_peak_map           = {}
        is_discount_map       = {}
        energy_charge_by_hour = []

        for i, row in enumerate(rows):
            # Parse demand period
            try:
                period = int(row[period_idx])
            except (ValueError, IndexError):
                raise ValueError(
                    f"Unable to read value in row {i} of csv. Please check values "
                    f"for Energy Rate ($/kWh), Demand Rate ($/kW), and Demand Period "
                    f"in this row."
                )
            demand_period_chart[i] = period

            # Energy rate (per-hour, may be blank after first occurrence)
            energy_str = row[energy_idx] if energy_idx < len(row) else ""
            if not energy_str:
                if period not in energy_charge_map:
                    raise ValueError(
                        f"Missing 'Energy Rate ($/kWh)' in row {i} of csv."
                    )
                energy_charge_by_hour.append(energy_charge_map[period])
            else:
                try:
                    energy_charge_by_hour.append(float(energy_str))
                except ValueError:
                    raise ValueError(
                        f"Unable to read value in row {i} of csv. Please check values "
                        f"for Energy Rate ($/kWh), Demand Rate ($/kW), and Demand Period "
                        f"in this row."
                    )

            # Demand/energy charge maps — stored on first occurrence of each period
            if period not in demand_charge_map:
                demand_str = row[demand_idx] if demand_idx < len(row) else ""
                try:
                    demand_charge_map[period] = float(demand_str)
                    energy_charge_map[period] = float(energy_str)
                except ValueError:
                    raise ValueError(
                        f"Unable to read value in row {i} of csv. Please check values "
                        f"for Energy Rate ($/kWh), Demand Rate ($/kW), and Demand Period "
                        f"in this row."
                    )
                is_peak_map[period]     = period % 2 == 1
                is_discount_map[period] = False

        return cls(
            demand_period_chart=demand_period_chart,
            demand_charge_map=demand_charge_map,
            energy_charge_map=energy_charge_map,
            is_peak_map=is_peak_map,
            is_discount_map=is_discount_map,
            monthly_base_charge=monthly_base_charge,
            energy_charge_by_hour=energy_charge_by_hour,
        )

    # ------------------------------------------------------------------
    # Rate lookups
    # ------------------------------------------------------------------

    def get_energy_charge_at_step(self, step: int, timestep_min: int) -> float:
        """
        Return the energy rate [$/kWh] for simulation step *step*.

        Parameters
        ----------
        step : int
            0-based step index from the simulation.
        timestep_min : int
            Simulation timestep size [minutes] (e.g. 1, 10, or 60).

        Returns
        -------
        float
        """
        hour_of_year = math.floor(step / (60.0 / timestep_min))
        if len(self.energy_charge_by_hour) == 8760:
            return self.energy_charge_by_hour[hour_of_year]
        period = self.demand_period_chart[hour_of_year]
        return self.energy_charge_map[period]

    def get_demand_period_at_step(self, step: int, timestep_min: int) -> int:
        """
        Return the demand period key for simulation step *step*.

        Parameters
        ----------
        step : int
        timestep_min : int

        Returns
        -------
        int
        """
        hour_of_year = math.floor(step / (60.0 / timestep_min))
        return self.demand_period_chart[hour_of_year]

    def get_demand_charge_for_period(self, period_key: int, max_kw: float) -> float:
        """
        Return the demand charge [$] for *period_key* given *max_kw*.

        Parameters
        ----------
        period_key : int
        max_kw : float
            Peak power draw observed during the period [kW].

        Returns
        -------
        float

        Raises
        ------
        ValueError
            If *period_key* is not a defined period.
        """
        if period_key not in self.demand_charge_map:
            raise ValueError(
                f"{period_key} is not a defined demand period for the utility calculation."
            )
        return self.demand_charge_map[period_key] * max_kw

    def get_all_demand_period_keys(self) -> list[int]:
        """Return all defined demand period keys (one per month×period type)."""
        return list(self.demand_charge_map.keys())

    def get_yearly_base_charge(self) -> float:
        """Return the annual base charge [$] (monthly_base_charge × 12)."""
        return self.monthly_base_charge * 12.0

    # ------------------------------------------------------------------
    # CSV export
    # ------------------------------------------------------------------

    def to_csv(self, csv_path: str) -> None:
        """
        Export the rate structure to a CSV file readable by ``from_csv``.

        Produces 8760 data rows (one per hour of a non-leap year) plus a header.
        Energy and demand rates are written on the *first* occurrence of each
        demand period; subsequent rows leave those fields blank.  The monthly
        base charge appears only in the first data row.

        Parameters
        ----------
        csv_path : str
            Destination file path.
        """
        header = [
            "Date", "Demand Period",
            "Energy Rate ($/kWh)", "Demand Rate ($/kW)",
            "Monthly Base Charge",
        ]
        seen_periods: set[int] = set()
        month = 0
        day   = 1

        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)

            for h in range(8760):
                # Advance month/day counters
                if h > 0 and h == _MONTH_HOUR_START[month + 1]:
                    month += 1
                    day    = 1
                elif h != 0 and h % 24 == 0:
                    day += 1

                date_str = f"{_MONTH_NAMES[month]} {day}, {h % 24:02d}:00"
                period   = self.demand_period_chart[h]

                if period not in seen_periods:
                    energy_rate = self.energy_charge_map.get(period, "")
                    demand_rate = self.demand_charge_map.get(period, "")
                    seen_periods.add(period)
                else:
                    energy_rate = ""
                    demand_rate = ""

                base_charge = self.monthly_base_charge if h == 0 else ""
                writer.writerow([date_str, period, energy_rate, demand_rate, base_charge])
