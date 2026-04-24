from __future__ import annotations

import json
import math
import os
import pickle

from ecoengine.constants.constants import _W_TO_KBTUH

# Absolute path to the performance maps data directory
_DATA_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "data", "preformanceMaps",
    )
)

# Model names whose pkl interpolator takes only (inlet, OAT) — no outlet dimension
_TWO_INPUT_PKL_NAMES = frozenset({
    "MODELS_SANCO2_C_SP",
    "MODELS_COLMAC_R454B_C_SP",
    "MODELS_Droplet_C_SP",
})


def _load_maps_json() -> dict:
    """Return the parsed maps.json model registry (cached after first load)."""
    if not hasattr(_load_maps_json, "_cache"):
        path = os.path.join(_DATA_DIR, "maps.json")
        with open(path) as f:
            _load_maps_json._cache = json.load(f)
    return _load_maps_json._cache


class PerformanceMap:
    """
    Wraps HPWH performance map data to predict real-world heating capacity and
    power input as a function of outdoor air temperature and water temperature.

    Construction
    ------------
    Use the factory class method rather than calling __init__ directly:

    * ``PerformanceMap.from_model_name(model_name, ...)``
        Loads the appropriate concrete subclass from the equipment model registry:

        - ``PklPerformanceMap``    — pickle-based LinearND interpolator (lab data)
        - ``HPWHsimPerformanceMap``— coefficient-based polynomial (HPWHsim model)

    * ``NominalPerformanceMap(nominal_capacity_kbtuh)``
        Constant-output placeholder for use during preliminary sizing.
        **Do not change this subclass.**

    API notes
    ---------
    * ``outlet_temp_f`` — outlet water temperature leaving the heater [°F].
      In a stratified-tank simulation this is ``top_temp_f`` (the storage setpoint).
    * ``inlet_temp_f``  — cold water entering the heater from the tank bottom [°F].
      Optional; falls back to the ``design_inlet_temp_f`` stored at construction
      when not provided.
    """

    def __init__(self, map_data: object, model_name: str = "") -> None:
        self.map_data   = map_data
        self.model_name = model_name

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_model_name(
        cls,
        model_name: str,
        num_units: int = 1,
        design_inlet_temp_f: float = 50.0,
        nominal_capacity_kbtuh: float | None = None,
    ) -> PerformanceMap:
        """
        Load a PerformanceMap from the equipment model registry by name.

        Returns a ``PklPerformanceMap`` when pickle interpolator files are
        available for the model, otherwise an ``HPWHsimPerformanceMap``.

        Parameters
        ----------
        model_name : str
            Equipment model identifier as it appears in ``maps.json``
            (e.g. ``'MODELS_ColmacCxV_5_C_SP'``).
        num_units : int
            Number of identical heat pump units deployed.  All capacity and
            power outputs are scaled by this factor.  Default 1.
        design_inlet_temp_f : float
            Cold-water inlet temperature used as fallback when ``inlet_temp_f``
            is not passed to ``get_capacity_kbtuh`` / ``get_power_in_kw``.
            Default 50 °F.
        nominal_capacity_kbtuh : float | None
            Total system output capacity at design conditions [kBTU/hr].
            Required for the ER fallback path (OAT below performance-map
            minimum); if None the fallback returns 0 kBTU/hr.

        Raises
        ------
        ValueError
            If ``model_name`` is not found in the registry, or the registry
            entry has neither pkl nor perfmap data.
        """
        registry = _load_maps_json()
        if model_name not in registry:
            raise ValueError(
                f"Model '{model_name}' not found in the performance map registry. "
                "Check maps.json for valid model names."
            )

        entry = registry[model_name]
        secondary_hx = bool(entry.get("secondary_heat_exchanger", False))
        hx_increase  = float(entry.get("hx_increase", 0.0))

        # Two-input pkl: inlet + OAT only (no outlet dimension)
        is_two_input_pkl = (
            model_name in _TWO_INPUT_PKL_NAMES
            or model_name.endswith("MP")
            or "Lochinvar" in model_name
        )
        is_multipass = model_name.endswith("MP")

        if "pkl_prefix" in entry:
            prefix   = entry["pkl_prefix"]
            pkls_dir = os.path.join(_DATA_DIR, "pkls")

            with open(os.path.join(pkls_dir, f"{prefix}_capacity_interpolator.pkl"), "rb") as f:
                output_interp = pickle.load(f)
            with open(os.path.join(pkls_dir, f"{prefix}_power_in_interpolator.pkl"), "rb") as f:
                input_interp  = pickle.load(f)
            with open(os.path.join(pkls_dir, f"{prefix}_bounds.pkl"), "rb") as f:
                bounds = pickle.load(f)

            unique_oats           = bounds[0]
            inTs_and_outTs_by_oat = bounds[1]
            inlet_min, inlet_max  = bounds[2]
            default_out_high_kw, default_in_high_kw = bounds[3]
            default_out_low_kw,  default_in_low_kw  = bounds[4]

            return PklPerformanceMap(
                model_name            = model_name,
                output_interpolator   = output_interp,
                input_interpolator    = input_interp,
                unique_oats           = unique_oats,
                inTs_and_outTs_by_oat = inTs_and_outTs_by_oat,
                inlet_min             = inlet_min,
                inlet_max             = inlet_max,
                default_out_high_kw   = default_out_high_kw,
                default_in_high_kw    = default_in_high_kw,
                default_out_low_kw    = default_out_low_kw,
                default_in_low_kw     = default_in_low_kw,
                num_units             = num_units,
                is_two_input          = is_two_input_pkl,
                secondary_hx          = secondary_hx,
                hx_increase           = hx_increase,
                nominal_capacity_kbtuh= nominal_capacity_kbtuh,
                design_inlet_temp_f   = design_inlet_temp_f,
            )

        if "perfmap" in entry:
            return HPWHsimPerformanceMap(
                model_name             = model_name,
                perfmap                = entry["perfmap"],
                num_units              = num_units,
                is_multipass           = is_multipass,
                nominal_capacity_kbtuh = nominal_capacity_kbtuh,
                design_inlet_temp_f    = design_inlet_temp_f,
            )

        raise ValueError(
            f"Registry entry for '{model_name}' has neither 'pkl_prefix' nor "
            "'perfmap' — cannot construct a PerformanceMap."
        )

    # ------------------------------------------------------------------
    # Public interface (stubs — overridden by concrete subclasses)
    # ------------------------------------------------------------------

    def get_capacity_kbtuh(
        self,
        oat_f: float,
        outlet_temp_f: float,
        inlet_temp_f: float | None = None,
    ) -> float | None:
        """Return heating output [kBTU/hr] at the given conditions."""
        pass

    def get_power_in_kw(
        self,
        oat_f: float,
        outlet_temp_f: float,
        inlet_temp_f: float | None = None,
    ) -> float | None:
        """Return electrical power input [kW] at the given conditions."""
        pass

    def get_cop(
        self,
        oat_f: float,
        outlet_temp_f: float,
        inlet_temp_f: float | None = None,
    ) -> float | None:
        """Return COP at the given conditions (None if power data is unavailable)."""
        cap_kbtuh = self.get_capacity_kbtuh(oat_f, outlet_temp_f, inlet_temp_f)
        pwr_kw    = self.get_power_in_kw(oat_f, outlet_temp_f, inlet_temp_f)
        if cap_kbtuh is None or pwr_kw is None or pwr_kw <= 0:
            return None
        return (cap_kbtuh / _W_TO_KBTUH) / pwr_kw

    def is_within_operating_bounds(self, oat_f: float) -> bool:
        """Return True if the conditions are within the map's valid operating range."""
        pass


# ---------------------------------------------------------------------------
# NominalPerformanceMap — constant-output placeholder (do not change)
# ---------------------------------------------------------------------------

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

    def get_capacity_kbtuh(self, oat_f: float, outlet_temp_f: float, inlet_temp_f: float | None = None) -> float:
        """Return the fixed nominal capacity [kBTU/hr] regardless of conditions."""
        return self.nominal_capacity_kbtuh


# ---------------------------------------------------------------------------
# PklPerformanceMap — pickle-based LinearND interpolator
# ---------------------------------------------------------------------------

class PklPerformanceMap(PerformanceMap):
    """
    Performance map backed by scipy ``LinearNDInterpolator`` pickle files.

    Single-pass models interpolate over (inlet_temp, outlet_temp, OAT).
    Multipass and certain named models use a two-input grid (inlet_temp, OAT).

    Out-of-bounds handling (mirrors PrefMapTracker behaviour)
    ---------------------------------------------------------
    * OAT ≥ oat_max  → use stored default high-OAT capacity/power values.
    * OAT < oat_min  → Electric Resistance fallback: output = input =
      ``nominal_capacity_kbtuh / num_units`` (COP = 1).
    * NaN in range   → attempt to snap inlet/outlet to nearest valid grid
      point (``_force_closest``); if still NaN, assume COP = 1.5.
    """

    def __init__(
        self,
        model_name: str,
        output_interpolator: object,
        input_interpolator: object,
        unique_oats: list[float],
        inTs_and_outTs_by_oat: list[list[tuple[float, list[float]]]],
        inlet_min: float,
        inlet_max: float,
        default_out_high_kw: float,
        default_in_high_kw: float,
        default_out_low_kw: float,
        default_in_low_kw: float,
        num_units: int,
        is_two_input: bool,
        secondary_hx: bool,
        hx_increase: float,
        nominal_capacity_kbtuh: float | None,
        design_inlet_temp_f: float,
    ) -> None:
        super().__init__(map_data=None, model_name=model_name)
        self._output_interp      = output_interpolator
        self._input_interp       = input_interpolator
        self._unique_oats        = unique_oats
        self._inTs_outTs         = inTs_and_outTs_by_oat
        self._inlet_min          = inlet_min
        self._inlet_max          = inlet_max
        self._default_out_high_kw = default_out_high_kw
        self._default_in_high_kw  = default_in_high_kw
        self._default_out_low_kw  = default_out_low_kw
        self._default_in_low_kw   = default_in_low_kw
        self.num_units           = num_units
        self._is_two_input       = is_two_input
        self._secondary_hx       = secondary_hx
        self._hx_increase        = hx_increase
        self._nominal_kbtuh      = nominal_capacity_kbtuh
        self._design_inlet_f     = design_inlet_temp_f

    @property
    def oat_min(self) -> float:
        return self._unique_oats[0]

    @property
    def oat_max(self) -> float:
        return self._unique_oats[-1]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_temps(
        self, outlet_temp_f: float, inlet_temp_f: float | None
    ) -> tuple[float, float]:
        """Apply HX shift and inlet capping; return (inlet, outlet)."""
        inlet  = inlet_temp_f if inlet_temp_f is not None else self._design_inlet_f
        outlet = outlet_temp_f
        if self._secondary_hx:
            inlet  += self._hx_increase
            outlet += self._hx_increase
        inlet = min(inlet, self._inlet_max)
        return inlet, outlet

    def _raw_query(
        self, inlet_t: float, outlet_t: float, oat_f: float
    ) -> tuple[float, float]:
        """Call the interpolators. Returns (output_kw, input_kw) per unit."""
        if self._is_two_input:
            arr = [[inlet_t, oat_f]]
        else:
            arr = [[inlet_t, outlet_t, oat_f]]
        return (
            float(self._output_interp(arr)[0][0]),
            float(self._input_interp(arr)[0][0]),
        )

    def _idx_nearest_oat(self, oat_f: float) -> int:
        best, idx = abs(self._unique_oats[0] - oat_f), 0
        for i in range(1, len(self._unique_oats)):
            d = abs(self._unique_oats[i] - oat_f)
            if d < best:
                best, idx = d, i
        return idx

    def _idx_nearest_inlet(self, oat_idx: int, inlet_t: float) -> int:
        """
        Find the index of the nearest available inlet temp that is >= inlet_t.
        Returns -1 (last element) when none qualifies.
        """
        entries = self._inTs_outTs[oat_idx]
        best    = abs(entries[-1][0] - inlet_t)
        closest = -1
        for i, (t_in, _) in enumerate(entries):
            d = abs(t_in - inlet_t)
            if d < best and t_in >= inlet_t:
                best, closest = d, i
        return closest

    def _nearest_outlet(self, oat_idx: int, inlet_idx: int, outlet_t: float) -> float:
        """Return the outlet temp in the bounds grid nearest to outlet_t."""
        outlets = self._inTs_outTs[oat_idx][inlet_idx][1]
        best    = abs(self._unique_oats[0] - outlet_t)   # mirrors original init
        best_i  = 0
        for i, o in enumerate(outlets):
            d = abs(o - outlet_t)
            if d < best:
                best, best_i = d, i
        return outlets[best_i]

    def _force_closest(
        self, inlet_t: float, outlet_t: float, oat_f: float
    ) -> tuple[float, float] | None:
        """
        Attempt to recover a valid interpolation result by snapping inlet and
        outlet to the nearest valid grid points. Returns (out_kw, inp_kw) per
        unit, or None when the inputs are too far outside the map.
        """
        oat_idx = self._idx_nearest_oat(oat_f)
        try:
            inlet_idx = self._idx_nearest_inlet(oat_idx, inlet_t)
        except Exception:
            return None

        snapped_oat   = self._unique_oats[oat_idx]
        snapped_inlet = self._inTs_outTs[oat_idx][inlet_idx][0]

        out_kw, inp_kw = self._raw_query(snapped_inlet, outlet_t, snapped_oat)
        if not (math.isnan(out_kw) or math.isnan(inp_kw)):
            return out_kw, inp_kw

        # Try snapping outlet as well
        snapped_outlet = self._nearest_outlet(oat_idx, inlet_idx, outlet_t)
        out_kw, inp_kw = self._raw_query(snapped_inlet, snapped_outlet, snapped_oat)
        if not (math.isnan(out_kw) or math.isnan(inp_kw)):
            if snapped_outlet < outlet_t and outlet_t > snapped_inlet:
                # Proportional capacity adjustment for lower outlet temperature
                adj = out_kw * (
                    (outlet_t - snapped_inlet) - (snapped_outlet - snapped_inlet)
                ) / (outlet_t - snapped_inlet)
                out_kw += adj
                inp_kw += adj
            return out_kw, inp_kw

        return None

    def _er_per_unit_kw(self) -> float:
        """kW per unit at COP=1 (Electric Resistance fallback)."""
        if self._nominal_kbtuh is not None:
            return (self._nominal_kbtuh / self.num_units) / _W_TO_KBTUH
        return self._default_out_low_kw

    def _get_per_unit_kw(
        self, oat_f: float, inlet_t: float, outlet_t: float
    ) -> tuple[float, float]:
        """
        Core lookup. Returns (output_kw, input_kw) for a single unit,
        with full out-of-bounds handling.
        """
        if oat_f is None:
            raise ValueError(
                "oat_f is required for real performance maps. "
                "Provide a ClimateZone with a design OAT when constructing the Building."
            )
        # OAT at or above map maximum → use default high-OAT values
        if oat_f >= self.oat_max:
            return self._default_out_high_kw, self._default_in_high_kw

        # Normal interpolation
        out_kw, inp_kw = self._raw_query(inlet_t, outlet_t, oat_f)
        if not (math.isnan(out_kw) or math.isnan(inp_kw)):
            return out_kw, inp_kw

        # OAT below map minimum → Electric Resistance fallback (COP=1)
        if oat_f < self.oat_min:
            er = self._er_per_unit_kw()
            return er, er

        # OAT in-range NaN → try snapping to nearest valid grid point
        result = self._force_closest(inlet_t, outlet_t, oat_f)
        if result is not None:
            return result

        # Last resort: assume COP = 1.5
        er  = self._er_per_unit_kw()
        return er, er / 1.5

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_capacity_kbtuh(
        self,
        oat_f: float,
        outlet_temp_f: float,
        inlet_temp_f: float | None = None,
    ) -> float:
        inlet, outlet = self._resolve_temps(outlet_temp_f, inlet_temp_f)
        out_kw, _     = self._get_per_unit_kw(oat_f, inlet, outlet)
        return out_kw * self.num_units * _W_TO_KBTUH

    def get_power_in_kw(
        self,
        oat_f: float,
        outlet_temp_f: float,
        inlet_temp_f: float | None = None,
    ) -> float:
        inlet, outlet = self._resolve_temps(outlet_temp_f, inlet_temp_f)
        _, inp_kw     = self._get_per_unit_kw(oat_f, inlet, outlet)
        return inp_kw * self.num_units

    def is_within_operating_bounds(self, oat_f: float) -> bool:
        return oat_f >= self.oat_min


# ---------------------------------------------------------------------------
# HPWHsimPerformanceMap — coefficient-based polynomial
# ---------------------------------------------------------------------------

class HPWHsimPerformanceMap(PerformanceMap):
    """
    Performance map using the HPWHsim polynomial coefficient model.

    Multi-entry maps (most models)
    -------------------------------
    A list of OAT bracket entries, each with ``T_F``, ``COP_coeffs`` (3
    terms), and ``inputPower_coeffs`` (3 terms, producing Watts).

    At each bracket: ``value = c0 + c1·x + c2·x²`` where ``x`` is the
    condenser (inlet) water temperature.  The result is linearly interpolated
    between the two bracketing OAT entries.

    Single-entry maps (rare)
    -------------------------
    * Single-pass: 11-term full quadratic in (OAT, outlet_T, inlet_T).
    * Multipass: 6-term quadratic in (OAT, inlet_temp_f).

    OAT below the minimum bracket → Electric Resistance fallback (COP = 1).
    """

    def __init__(
        self,
        model_name: str,
        perfmap: list[dict],
        num_units: int,
        is_multipass: bool,
        nominal_capacity_kbtuh: float | None,
        design_inlet_temp_f: float,
    ) -> None:
        super().__init__(map_data=perfmap, model_name=model_name)
        self._perfmap      = perfmap
        self.num_units     = num_units
        self._is_multipass = is_multipass
        self._nominal_kbtuh = nominal_capacity_kbtuh
        self._design_inlet_f = design_inlet_temp_f

    @property
    def oat_min(self) -> float:
        return self._perfmap[0]["T_F"] if self._perfmap else float("-inf")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _linear_interp(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
        return y0 + (x - x0) * (y1 - y0) / (x1 - x0)

    @staticmethod
    def _quad(coeffs: list[float], x: float) -> float:
        return coeffs[0] + coeffs[1] * x + coeffs[2] * x * x

    @staticmethod
    def _poly11(coeffs: list[float], oat: float, out_t: float, in_t: float) -> float:
        """11-term full quadratic in (OAT, outlet_T, inlet_T)."""
        c = coeffs
        return (
            c[0]
            + c[1] * oat + c[2] * out_t + c[3] * in_t
            + c[4] * oat * oat + c[5] * out_t * out_t + c[6] * in_t * in_t
            + c[7] * oat * out_t + c[8] * oat * in_t + c[9] * out_t * in_t
            + c[10] * oat * out_t * in_t
        )

    @staticmethod
    def _poly6(coeffs: list[float], x1: float, x2: float) -> float:
        """6-term quadratic in two inputs."""
        c = coeffs
        return (
            c[0] + c[1] * x1 + c[2] * x2
            + c[3] * x1 * x1 + c[4] * x2 * x2 + c[5] * x1 * x2
        )

    def _er_per_unit_kbtuh(self) -> float:
        if self._nominal_kbtuh is not None:
            return self._nominal_kbtuh / self.num_units
        return 0.0

    def _get_per_unit_kbtuh(
        self, oat_f: float, inlet_temp_f: float, outlet_t: float
    ) -> tuple[float, float]:
        """Returns (output_kbtuh, input_kbtuh) for a single unit."""
        if oat_f is None:
            raise ValueError(
                "oat_f is required for real performance maps. "
                "Provide a ClimateZone with a design OAT when constructing the Building."
            )
        perfmap = self._perfmap

        if not perfmap:
            er = self._er_per_unit_kbtuh()
            return er, er

        if len(perfmap) > 1:
            # --- Multi-entry: bracket OAT and quadratic in inlet_temp_f ---
            i_prev, i_next = None, None
            for i in range(len(perfmap)):
                if oat_f < perfmap[i]["T_F"]:
                    if i == 0:
                        # Below minimum OAT → ER fallback
                        er = self._er_per_unit_kbtuh()
                        return er, er
                    i_prev, i_next = i - 1, i
                    break
                if i == len(perfmap) - 1:
                    # Above maximum OAT → extrapolate from last bracket pair
                    i_prev, i_next = i - 1, i

            COP_T1  = self._quad(perfmap[i_prev]["COP_coeffs"],          inlet_temp_f)
            COP_T2  = self._quad(perfmap[i_next]["COP_coeffs"],          inlet_temp_f)
            pwr_T1_W = self._quad(perfmap[i_prev]["inputPower_coeffs"],   inlet_temp_f)
            pwr_T2_W = self._quad(perfmap[i_next]["inputPower_coeffs"],   inlet_temp_f)

            T1, T2   = perfmap[i_prev]["T_F"], perfmap[i_next]["T_F"]
            cop      = self._linear_interp(oat_f, T1, T2, COP_T1, COP_T2)
            input_kw = self._linear_interp(oat_f, T1, T2, pwr_T1_W / 1000.0, pwr_T2_W / 1000.0)

        else:
            # --- Single-entry: full regressed polynomial ---
            if self._is_multipass:
                input_kw = self._poly6(perfmap[0]["inputPower_coeffs"], oat_f, inlet_temp_f)
                cop      = self._poly6(perfmap[0]["COP_coeffs"],        oat_f, inlet_temp_f)
            else:
                input_kw = self._poly11(perfmap[0]["inputPower_coeffs"], oat_f, outlet_t, inlet_temp_f)
                cop      = self._poly11(perfmap[0]["COP_coeffs"],        oat_f, outlet_t, inlet_temp_f)

        output_kw = cop * input_kw
        # Convert kW to kBTU/hr
        return output_kw * _W_TO_KBTUH, input_kw * _W_TO_KBTUH

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_capacity_kbtuh(
        self,
        oat_f: float,
        outlet_temp_f: float,
        inlet_temp_f: float | None = None,
    ) -> float:
        inlet_temp_f = inlet_temp_f if inlet_temp_f is not None else self._design_inlet_f
        out_kbtuh, _ = self._get_per_unit_kbtuh(oat_f, inlet_temp_f, outlet_temp_f)
        return out_kbtuh * self.num_units

    def get_power_in_kw(
        self,
        oat_f: float,
        outlet_temp_f: float,
        inlet_temp_f: float | None = None,
    ) -> float:
        inlet_temp_f  = inlet_temp_f if inlet_temp_f is not None else self._design_inlet_f
        _, inp_kbtuh = self._get_per_unit_kbtuh(oat_f, inlet_temp_f, outlet_temp_f)
        return inp_kbtuh / _W_TO_KBTUH * self.num_units

    def is_within_operating_bounds(self, oat_f: float) -> bool:
        return oat_f >= self.oat_min
