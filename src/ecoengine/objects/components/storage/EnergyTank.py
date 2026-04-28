from __future__ import annotations

from .StorageTank import StorageTank
from ecoengine.constants.constants import _RHO_CP

_DEFAULT_STRAT_SLOPE: float = 2.8


class EnergyTank(StorageTank):
    """
    Storage tank that tracks thermal energy [BTU] as its primary state variable.

    Cold water at ``cold_temp_f`` defines the zero-energy baseline.  All stored
    energy is measured above that baseline.

    Temperature profile
    -------------------
    Temperature queries back-calculate a virtual StratifiedTank profile from the
    stored energy.  The profile uses ``strat_inter = cold_temp_f`` (i.e., the
    thermocline ramp is anchored at the cold baseline):

        T(x_pct) = cold_temp_f                                    x_pct <= x_cold
                 = strat_slope * (x_pct + shift_pct) + cold_temp_f  x_cold < x_pct < x_hot
                 = storage_temp_f                                  x_pct >= x_hot

    where ``shift_pct = delta_gal / total_volume_gal * 100`` is derived
    analytically from the stored energy via ``_shift_pct_from_energy()``.

    Energy ↔ shift_pct relationship
    --------------------------------
    Given the profile above, the stored energy above ``cold_temp_f`` is:

        I(s)  = strat_slope/2 * [(b+s)² − (a+s)²] + dT * (100 − b)
        E     = _RHO_CP * total_volume_gal / 100 * I(s)

    where s = shift_pct, dT = storage_temp_f − cold_temp_f,
    a = max(0, min(100, −s)), b = max(0, min(100, dT/strat_slope − s)).

    The inverse (E → s) is computed by binary search in ``_shift_pct_from_energy()``.
    """

    def __init__(
        self,
        total_volume_gal: float,
        cold_temp_f: float,
        storage_temp_f: float,
        strat_slope: float = _DEFAULT_STRAT_SLOPE,
    ) -> None:
        """
        Parameters
        ----------
        total_volume_gal : float
            Total physical tank volume [gallons].
        cold_temp_f : float
            Inlet / cold-water temperature [°F].  Defines the zero-energy baseline.
        storage_temp_f : float
            Maximum storage (hot-zone) temperature [°F].
        strat_slope : float
            Temperature gradient through the thermocline transition zone
            [°F per percentage-point of tank height].  Defaults to 2.8.
        """
        self.total_volume_gal = total_volume_gal
        self._cold_temp_f     = cold_temp_f
        self._storage_temp_f  = storage_temp_f
        self.strat_slope      = strat_slope
        self._energy_btu: float = 0.0

    # ------------------------------------------------------------------
    # Energy ↔ shift_pct helpers
    # ------------------------------------------------------------------

    def _max_energy_btu(self) -> float:
        """Energy [BTU] when the tank is fully charged to storage_temp_f."""
        return self.total_volume_gal * _RHO_CP * (self._storage_temp_f - self._cold_temp_f)

    def _energy_at_shift_pct(self, s: float) -> float:
        """
        Forward mapping: compute stored energy [BTU] for a given thermocline
        shift_pct ``s``.

        Uses the unified integral over cold / transition / hot zones:

            a = clamp(-s, 0, 100)               cold-zone boundary [pct]
            b = clamp(x_ramp − s, 0, 100)       hot-zone start [pct]
            I = strat_slope/2 * ((b+s)² − (a+s)²) + dT * (100 − b)
            E = _RHO_CP * V / 100 * I
        """
        dT = self._storage_temp_f - self._cold_temp_f
        if dT <= 0.0:
            return 0.0
        x_ramp = dT / self.strat_slope
        a = max(0.0, min(100.0, -s))
        b = max(0.0, min(100.0, x_ramp - s))
        I = self.strat_slope / 2.0 * ((b + s) ** 2 - (a + s) ** 2) + dT * (100.0 - b)
        return _RHO_CP * self.total_volume_gal / 100.0 * I

    def _shift_pct_from_energy(self) -> float:
        """
        Inverse mapping: return shift_pct for the current ``_energy_btu`` via
        binary search on ``_energy_at_shift_pct``.

        shift_pct ranges from −100 (fully cold) to x_ramp (fully hot).
        30 iterations give sub-nanogallon precision on any physical tank.
        """
        dT = self._storage_temp_f - self._cold_temp_f
        if dT <= 0.0:
            return 0.0
        E = max(0.0, min(self._energy_btu, self._max_energy_btu()))
        if E <= 0.0:
            return -100.0
        if E >= self._max_energy_btu():
            return dT / self.strat_slope
        lo: float = -100.0
        hi: float = dT / self.strat_slope
        tol: float = 1e-6 * max(E, 1.0)
        for _ in range(30):
            mid = (lo + hi) * 0.5
            e_mid = self._energy_at_shift_pct(mid)
            if abs(e_mid - E) < tol:
                break
            if e_mid < E:
                lo = mid
            else:
                hi = mid
        return (lo + hi) * 0.5

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(
        self,
        storage_temp_f: float,
        cold_temp_f: float,
        percent_useable: float,
    ) -> None:
        """
        Set initial energy state.

        Places the cold boundary at ``(1 − percent_useable) × 100`` percent
        height — identical to how StratifiedTank initializes its profile — then
        converts that thermocline position to a stored energy value.

        Parameters
        ----------
        storage_temp_f : float
            Hot storage temperature [°F].
        cold_temp_f : float
            Cold / inlet water temperature [°F].
        percent_useable : float
            Fraction of tank volume that starts at storage temperature (0–1).
        """
        self._cold_temp_f    = cold_temp_f
        self._storage_temp_f = storage_temp_f
        s_init = (percent_useable - 1.0) * 100.0
        self._energy_btu = self._energy_at_shift_pct(s_init)

    # ------------------------------------------------------------------
    # Temperature queries
    # ------------------------------------------------------------------

    def get_temperature_at_fraction(self, fract: float) -> float:
        """
        Return water temperature at fractional tank height (0=bottom, 1=top).

        Back-calculates the virtual StratifiedTank profile from the current
        stored energy, then evaluates it at ``fract``.
        """
        shift_pct = self._shift_pct_from_energy()
        x_pct     = fract * 100.0
        temp      = self.strat_slope * (x_pct + shift_pct) + self._cold_temp_f
        return max(self._cold_temp_f, min(self._storage_temp_f, temp))

    def get_usable_volume_supplyT_gal(self, supply_temp_f: float) -> float:
        """Return gallons currently at or above ``supply_temp_f``."""
        shift_pct    = self._shift_pct_from_energy()
        x_supply_pct = (supply_temp_f - self._cold_temp_f) / self.strat_slope - shift_pct
        x_supply_pct = max(0.0, min(100.0, x_supply_pct))
        return (100.0 - x_supply_pct) / 100.0 * self.total_volume_gal

    # ------------------------------------------------------------------
    # Simulation operations
    # ------------------------------------------------------------------

    def draw(
        self,
        volume_supplyT_gal: float,
        cold_temp_f: float,
        supply_temp_f: float,
        outlet_temp_f: float,
    ) -> None:
        """
        Remove DHW demand from the tank.

        Draws ``volume_supplyT_gal × _RHO_CP × (supply_temp_f − cold_temp_f)``
        BTU from storage — the exact useful energy content of the demand volume
        at supply temperature above the cold baseline.  Cold make-up water at
        ``cold_temp_f`` refills the vacated volume with 0 BTU (by definition).
        """
        self._cold_temp_f = cold_temp_f
        if volume_supplyT_gal <= 0.0 or supply_temp_f <= cold_temp_f:
            return
        energy_requested = volume_supplyT_gal * _RHO_CP * (supply_temp_f - cold_temp_f)
        self._energy_btu = max(0.0, self._energy_btu - energy_requested)

    def add_energy_btu(self, btu: float) -> None:
        """Add ``btu`` BTU to storage, capped at the fully-charged energy level."""
        if btu > 0.0:
            self._energy_btu = min(self._energy_btu + btu, self._max_energy_btu())

    def heat(
        self,
        kbtuh: float,
        duration_min: float,
        outlet_temp_f: float,
    ) -> None:
        """
        Add heat from active water heaters for one timestep.

        Adds ``kbtuh × 1000 × duration_min / 60`` BTU to storage, capped at
        the fully-charged energy level (all water at ``storage_temp_f``).
        """
        if kbtuh <= 0.0 or outlet_temp_f <= self._cold_temp_f:
            return
        heat_btu = kbtuh * 1000.0 * duration_min / 60.0
        self._energy_btu = min(self._energy_btu + heat_btu, self._max_energy_btu())

    def add_recirc_return(
        self,
        flow_gpm: float,
        return_temp_f: float,
        duration_min: float,
        supply_temp_f: float | None = None,
    ) -> None:
        """
        Apply recirculation loop heat loss.

        Removes ``flow × duration × _RHO_CP × (supply_temp − return_temp)``
        BTU from storage, floored at 0.

        Parameters
        ----------
        flow_gpm : float
        return_temp_f : float
        duration_min : float
        supply_temp_f : float | None
            Defaults to ``storage_temp_f`` when ``None``.
        """
        t_supply = supply_temp_f if supply_temp_f is not None else self._storage_temp_f
        recirc_loss_btu = flow_gpm * duration_min * _RHO_CP * (t_supply - return_temp_f)
        self._energy_btu = max(0.0, self._energy_btu - recirc_loss_btu)

    def _zone_average_temp_f(self, lo_pct: float, hi_pct: float) -> float:
        """
        Return the volume-weighted average temperature over the vertical zone
        [``lo_pct``, ``hi_pct``] (both in 0–100 percentage-height units).

        Uses the same back-calculated stratified profile as
        ``get_temperature_at_fraction`` and ``get_average_draw_temp_f``.
        Returns ``cold_temp_f`` if the zone has zero width.
        """
        if hi_pct <= lo_pct:
            return self._cold_temp_f
        shift_pct  = self._shift_pct_from_energy()
        dT         = self._storage_temp_f - self._cold_temp_f
        x_ramp     = dT / self.strat_slope if dT > 0.0 else 0.0
        x_cold_pct = max(0.0, min(100.0, -shift_pct))
        x_hot_pct  = max(0.0, min(100.0, x_ramp - shift_pct))

        lo_c, hi_c = max(lo_pct, 0.0), min(hi_pct, x_cold_pct)
        cold_integral = self._cold_temp_f * max(0.0, hi_c - lo_c)

        lo_t = max(lo_pct, x_cold_pct)
        hi_t = min(hi_pct, x_hot_pct)
        if hi_t > lo_t:
            a, b = lo_t, hi_t
            trans_integral = (
                self.strat_slope / 2.0 * ((b + shift_pct) ** 2 - (a + shift_pct) ** 2)
                + self._cold_temp_f * (b - a)
            )
        else:
            trans_integral = 0.0

        lo_h = max(lo_pct, x_hot_pct)
        hi_h = min(hi_pct, 100.0)
        hot_integral = self._storage_temp_f * max(0.0, hi_h - lo_h)

        return (cold_integral + trans_integral + hot_integral) / (hi_pct - lo_pct)

    def get_average_draw_temp_f(self, draw_gal: float) -> float:
        """
        Return the volume-weighted average temperature of the top ``draw_gal``
        physical gallons.

        Analytically integrates the back-calculated stratified profile over
        the draw zone (top of tank downward).
        """
        draw_gal = min(draw_gal, self.total_volume_gal)
        if draw_gal <= 0.0:
            return self._storage_temp_f
        x_draw_pct = max(0.0, 100.0 - draw_gal / self.total_volume_gal * 100.0)
        return self._zone_average_temp_f(x_draw_pct, 100.0)

    def draw_physical_gal(
        self,
        gal: float,
        inlet_temp_f: float,
        supply_temp_f: float | None = None,
        update_internal_cold_temp: bool = True,
    ) -> None:
        """
        Remove ``gal`` physical gallons from the top of the tank and replace
        with make-up water at the bottom.

        The energy removed equals ``gal × _RHO_CP × (avg_top_temp − inlet_temp_f)``
        where ``avg_top_temp`` is from ``get_average_draw_temp_f(gal)``.

        Parameters
        ----------
        gal : float
        inlet_temp_f : float
            Temperature of make-up water entering the bottom.
        supply_temp_f : float | None
            Unused; kept for interface compatibility.
        update_internal_cold_temp : bool
            When ``True`` (default) ``_cold_temp_f`` is updated to
            ``inlet_temp_f``.  Pass ``False`` when the inlet is a warm
            mixing-valve return (to avoid corrupting the cold baseline).
        """
        if update_internal_cold_temp:
            self._cold_temp_f = inlet_temp_f
        if gal <= 0.0:
            return
        avg_temp       = self.get_average_draw_temp_f(gal)
        energy_removed = gal * _RHO_CP * max(0.0, avg_temp - inlet_temp_f)
        self._energy_btu = max(0.0, self._energy_btu - energy_removed)
