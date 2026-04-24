from __future__ import annotations

from .StorageTank import StorageTank
from ecoengine.constants.constants import _RHO_CP

_DEFAULT_STRAT_SLOPE: float = 2.8


class StratifiedTank(StorageTank):
    """
    Stratified storage tank model using a continuous linear temperature profile.

    Temperature profile
    -------------------
    The tank is hot on top and cold on bottom. Temperature as a function of
    height is described by three regions:

        T(x_pct) = inlet_temp_f                                   x_pct <= x_cold
                 = strat_slope * (x_pct + shift_pct) + strat_inter  x_cold < x_pct < x_hot
                 = outlet_temp_f                                   x_pct >= x_hot

    where x_pct is height as a percentage (0 = bottom, 100 = top) and
    shift_pct = delta_gal / total_volume_gal * 100 translates the gallons-based
    running tally into a percentage shift of the thermocline.

    delta_gal bookkeeping
    ---------------------
    ``_delta_gal`` tracks how much the thermocline has shifted from its
    initialized position, measured in gallons:

    * ``draw()`` decreases ``_delta_gal`` — cold water enters the bottom,
      the thermocline rises (less hot water available).
    * ``heat()`` increases ``_delta_gal`` — cold water is heated and moves to
      the top, the thermocline falls (more hot water available).
    """

    def __init__(
        self,
        total_volume_gal: float,
        num_nodes: int = 12,
        strat_slope: float = _DEFAULT_STRAT_SLOPE,
    ) -> None:
        """
        Parameters
        ----------
        total_volume_gal : float
            Total physical tank volume [gallons].
        num_nodes : int
            Number of vertical temperature nodes (retained for future use;
            the analytical profile model does not use discrete nodes).
        strat_slope : float
            Temperature gradient through the transition zone between cold and
            hot layers [°F per percentage-point of tank height]. Higher values
            mean a sharper thermocline (better stratification). Defaults to
            2.8, calibrated for a standard 12-node tank. DHWSystem subclasses
            that model different schematics may set a different value here.
        """
        self.total_volume_gal = total_volume_gal
        self.num_nodes        = num_nodes
        self.strat_slope      = strat_slope

        # Internal state — set by initialize()
        self._delta_gal:    float = 0.0
        self._strat_inter:  float = 0.0
        self._inlet_temp_f: float = 50.0   # updated each timestep by draw()
        self._outlet_temp_f: float = 140.0  # updated each timestep by heat()

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
        Set initial temperature stratification profile.

        Places the cold boundary (where T = cold_temp_f) at
        ``(1 - percent_useable) * 100`` percent height, so the top
        ``percent_useable`` fraction of the tank starts at storage temperature.

        Parameters
        ----------
        storage_temp_f : float
            Initial hot storage temperature [°F]. Also sets the initial
            outlet temperature cap.
        cold_temp_f : float
            Cold/incoming water temperature [°F].
        percent_useable : float
            Fraction of tank volume that starts hot (0–1).
        """
        self._inlet_temp_f  = cold_temp_f
        self._outlet_temp_f = storage_temp_f
        self._delta_gal     = 0.0

        # Solve for strat_inter so the ramp passes through cold_temp_f at
        # x_cold_pct with delta_gal = 0:
        #   strat_slope * x_cold_pct + strat_inter = cold_temp_f
        x_cold_pct = (1.0 - percent_useable) * 100.0
        self._strat_inter = cold_temp_f - self.strat_slope * x_cold_pct

    # ------------------------------------------------------------------
    # Temperature queries
    # ------------------------------------------------------------------

    def get_temperature_at_fraction(self, fract: float) -> float:
        """
        Return interpolated water temperature at a fractional tank height.

        Parameters
        ----------
        fract : float
            Fractional height from bottom (0) to top (1).

        Returns
        -------
        float
            Temperature [°F], clamped to [inlet_temp_f, outlet_temp_f].
        """
        x_pct     = fract * 100.0
        shift_pct = self._delta_gal / self.total_volume_gal * 100.0
        temp      = self.strat_slope * (x_pct + shift_pct) + self._strat_inter
        return max(self._inlet_temp_f, min(self._outlet_temp_f, temp))

    def get_usable_volume_supplyT_gal(self, supply_temp_f: float) -> float:
        """
        Return gallons of water currently at or above supply temperature.

        Parameters
        ----------
        supply_temp_f : float

        Returns
        -------
        float
        """
        # Solve for x_pct where T = supply_temp_f (lower boundary of usable zone):
        #   strat_slope * (x_pct + shift_pct) + strat_inter = supply_temp_f
        #   x_pct = (supply_temp_f - strat_inter) / strat_slope - shift_pct
        shift_pct     = self._delta_gal / self.total_volume_gal * 100.0
        x_supply_pct  = (supply_temp_f - self._strat_inter) / self.strat_slope - shift_pct
        x_supply_pct  = max(0.0, min(100.0, x_supply_pct))
        usable_fract  = (100.0 - x_supply_pct) / 100.0
        return usable_fract * self.total_volume_gal

    # ------------------------------------------------------------------
    # Simulation operations
    # ------------------------------------------------------------------

    def _delta_gal_floor(self, min_temp_f: float | None = None) -> float:
        """
        Minimum physical value of ``_delta_gal``: the state where the top of
        the tank is at ``min_temp_f`` (thermocline at the very top).

        When ``min_temp_f`` is ``supply_temp_f``, this is the point where the
        entire primary storage has dropped below usable delivery temperature —
        drawing further provides no hot water and only deepens the recovery hole.

        When ``min_temp_f`` is ``None``, falls back to ``_inlet_temp_f`` (the
        absolute fully-cold baseline).

        Symmetric with the cap applied in ``heat()`` for the fully-hot case.
        """
        t_floor = min_temp_f if min_temp_f is not None else self._inlet_temp_f
        shift_pct_min = (t_floor - self._strat_inter) / self.strat_slope - 100.0
        return shift_pct_min * self.total_volume_gal / 100.0

    def draw(
        self,
        volume_supplyT_gal: float,
        cold_temp_f: float,
        supply_temp_f: float,
        outlet_temp_f: float,
    ) -> None:
        """
        Remove hot water from the top of the tank and replace with cold at the
        bottom, representing DHW delivery to building occupants.

        When the hot zone at ``outlet_temp_f`` is deep enough to cover the
        entire draw, the standard conversion is used:

            physical_vol = volume_supplyT_gal
                           × (supply_temp_f − cold_temp_f)
                           / (outlet_temp_f − cold_temp_f)

        When the hot zone is partially depleted, the drawn block dips into the
        transition zone and its average temperature falls below ``outlet_temp_f``.
        In that case, ``get_average_draw_temp_f`` is used to binary-search for
        the physical volume whose actual supply-temp yield equals the demand.

        If even drawing the full tank cannot satisfy the demand (true outage),
        the entire tank volume is drawn and the caller detects the shortfall via
        ``get_usable_volume_supplyT_gal() == 0``.

        Decreases ``_delta_gal`` (thermocline rises → less hot water).

        Parameters
        ----------
        volume_supplyT_gal : float
            DHW demand in supply-temperature gallons [gal].
        cold_temp_f : float
            Incoming cold water temperature [°F]. Stored for subsequent
            temperature queries.
        supply_temp_f : float
            System supply (delivery) temperature [°F].
        outlet_temp_f : float
            Current maximum hot water temperature at the tank outlet [°F].
        """
        self._inlet_temp_f = cold_temp_f
        self._outlet_temp_f = outlet_temp_f
        if outlet_temp_f <= cold_temp_f or volume_supplyT_gal <= 0.0:
            return

        supply_delta = supply_temp_f - cold_temp_f
        outlet_delta = outlet_temp_f - cold_temp_f

        # Standard estimate: all drawn water at outlet_temp_f
        physical_vol = volume_supplyT_gal * supply_delta / outlet_delta

        # Fast path: check whether the drawn block is entirely within the hot zone.
        # If avg_temp ≈ outlet_temp_f the standard formula is exact.
        avg_temp = self.get_average_draw_temp_f(physical_vol)
        if avg_temp >= outlet_temp_f - 1e-6:
            self._delta_gal -= physical_vol
            self._delta_gal = max(self._delta_gal, self._delta_gal_floor(supply_temp_f))
            return

        # Slow path: draw dips into the transition / cold zone.
        # Binary-search for draw_gal where supply-temp yield equals demand.
        #   yield(draw_gal) = draw_gal × (avg_temp(draw_gal) − cold) / supply_delta
        lo = physical_vol
        hi = self.total_volume_gal

        for _ in range(52):
            mid = (lo + hi) * 0.5
            avg_t = self.get_average_draw_temp_f(mid)
            if avg_t > cold_temp_f:
                yield_mid = mid * (avg_t - cold_temp_f) / supply_delta
            else:
                yield_mid = 0.0
            if yield_mid < volume_supplyT_gal:
                lo = mid
            else:
                hi = mid
            if hi - lo < 1e-6:
                break

        self._delta_gal -= min((lo + hi) * 0.5, self.total_volume_gal)
        self._delta_gal = max(self._delta_gal, self._delta_gal_floor(supply_temp_f))

    def heat(
        self,
        kbtuh: float,
        duration_min: float,
        outlet_temp_f: float,
    ) -> None:
        """
        Apply heat from active water heaters for one timestep.

        Models the HPWH drawing cold water from the bottom of the tank,
        heating it to ``outlet_temp_f``, and returning it to the top.

        Increases ``_delta_gal`` (thermocline falls → more hot water), capped
        when the tank is fully heated.

        Parameters
        ----------
        kbtuh : float
            Total heating rate from all active heaters [kBTU/hr].
        duration_min : float
            Length of the timestep [minutes].
        outlet_temp_f : float
            Maximum temperature the heater delivers to the tank top [°F].
            Sets the hot-zone temperature cap for subsequent temperature queries.
        """
        self._outlet_temp_f = outlet_temp_f
        if kbtuh <= 0.0 or outlet_temp_f <= self._inlet_temp_f:
            return

        heat_kbtu    = kbtuh * duration_min / 60.0           # kBTU
        v_heated_gal = heat_kbtu * 1000.0 / (_RHO_CP * (outlet_temp_f - self._inlet_temp_f))  # gal
        self._delta_gal += v_heated_gal

        # Cap: tank cannot be heated beyond "fully hot" (hot zone fills the
        # entire tank, x=0% is at outlet_temp_f):
        #   strat_slope * (0 + shift_pct_max) + strat_inter = outlet_temp_f
        #   shift_pct_max = (outlet_temp_f - strat_inter) / strat_slope
        shift_pct_max  = (outlet_temp_f - self._strat_inter) / self.strat_slope
        delta_gal_max  = shift_pct_max * self.total_volume_gal / 100.0
        self._delta_gal = min(self._delta_gal, delta_gal_max)

    def add_recirc_return(
        self,
        flow_gpm: float,
        return_temp_f: float,
        duration_min: float,
        supply_temp_f: float | None = None,
    ) -> None:
        """
        Apply recirculation loop heat loss to the tank.

        The recirc loop draws water from the supply line at ``supply_temp_f``,
        circulates it through the building, and returns it at ``return_temp_f``.
        The heat lost in the loop — ``flow × rho_cp × (supply_temp - return_temp)``
        — is extracted from storage.  Total tank volume is unchanged; only the
        energy content (and thus the hot-zone depth) decreases.

        Parameters
        ----------
        flow_gpm : float
            Recirculation loop flow rate [GPM].
        return_temp_f : float
            Temperature of water returning from the recirc loop [°F].
        duration_min : float
            Length of the timestep [minutes].
        supply_temp_f : float | None
            DHW delivery temperature [°F].  Defaults to ``outlet_temp_f``
            (correct for TM tanks where supply == storage temperature).
            Pass explicitly when ``supply_temp_f < storage_temp_f`` (e.g.
            SPRTP primary storage) to avoid over-counting the heat loss.
        """
        if self._outlet_temp_f <= self._inlet_temp_f:
            return
        t_supply     = supply_temp_f if supply_temp_f is not None else self._outlet_temp_f
        vol_gal      = flow_gpm * duration_min
        recirc_loss_kbtu = vol_gal * _RHO_CP * (t_supply - return_temp_f) / 1000.0
        net_delta_gal    = recirc_loss_kbtu * 1000.0 / (_RHO_CP * (self._outlet_temp_f - self._inlet_temp_f))
        self._delta_gal -= net_delta_gal

    def get_average_draw_temp_f(self, draw_gal: float) -> float:
        """
        Return the volume-weighted average temperature of the top ``draw_gal``
        physical gallons.

        Analytically integrates the stratified temperature profile over the draw
        zone (top of tank downward), splitting the zone into cold, transition,
        and hot sub-regions.

        Parameters
        ----------
        draw_gal : float
            Physical gallons to draw from the top of the tank [gal].

        Returns
        -------
        float
            Volume-weighted average temperature [°F] of the drawn block.
        """
        draw_gal = min(draw_gal, self.total_volume_gal)
        if draw_gal <= 0.0:
            return self._outlet_temp_f

        shift_pct  = self._delta_gal / self.total_volume_gal * 100.0
        x_draw_pct = max(0.0, 100.0 - draw_gal / self.total_volume_gal * 100.0)

        # Zone boundaries (percentage height, 0 = bottom, 100 = top)
        x_cold_pct = max(0.0, min(100.0,
            (self._inlet_temp_f  - self._strat_inter) / self.strat_slope - shift_pct))
        x_hot_pct  = max(0.0, min(100.0,
            (self._outlet_temp_f - self._strat_inter) / self.strat_slope - shift_pct))

        # Cold zone: T = inlet_temp_f
        lo, hi = max(x_draw_pct, 0.0), min(100.0, x_cold_pct)
        cold_integral = self._inlet_temp_f * max(0.0, hi - lo)

        # Transition zone: T = strat_slope * (x + shift_pct) + strat_inter
        lo, hi = max(x_draw_pct, x_cold_pct), min(100.0, x_hot_pct)
        if hi > lo:
            a, b = lo, hi
            trans_integral = (
                self.strat_slope / 2.0 * ((b + shift_pct) ** 2 - (a + shift_pct) ** 2)
                + self._strat_inter * (b - a)
            )
        else:
            trans_integral = 0.0

        # Hot zone: T = outlet_temp_f
        lo, hi = max(x_draw_pct, x_hot_pct), 100.0
        hot_integral = self._outlet_temp_f * max(0.0, hi - lo)

        total_width = 100.0 - x_draw_pct
        if total_width <= 0.0:
            return self._outlet_temp_f
        return (cold_integral + trans_integral + hot_integral) / total_width

    def draw_physical_gal(
        self,
        gal: float,
        inlet_temp_f: float,
        supply_temp_f: float | None = None,
    ) -> None:
        """
        Remove ``gal`` physical gallons from the top of the tank and replace
        with cold make-up water at the bottom.

        Decreases ``_delta_gal`` directly by the physical volume (thermocline
        rises). Unlike ``draw()``, no supply-temperature conversion is applied —
        the caller provides physical gallons directly.

        Parameters
        ----------
        gal : float
            Physical gallons to remove [gal].
        inlet_temp_f : float
            Incoming cold water temperature [°F].
        supply_temp_f : float | None
            Hot-water delivery temperature [°F]. When provided, ``_delta_gal``
            is floored at the state where the tank top is at ``supply_temp_f``
            (no more usable hot water). When ``None``, the absolute fully-cold
            floor (``inlet_temp_f`` at top) is used instead.
        """
        self._inlet_temp_f = inlet_temp_f
        if gal > 0.0:
            self._delta_gal -= gal
            self._delta_gal = max(self._delta_gal, self._delta_gal_floor(supply_temp_f))

    # ------------------------------------------------------------------
    # Sizing support
    # ------------------------------------------------------------------

    def get_stratification_factor(
        self,
        on_fract: float,
        supply_temp_f: float,
        storage_temp_f: float,
    ) -> float:
        """
        Return the stratification factor: the fraction of total tank volume
        that is usable at supply temperature given the ON aquastat position.

        Matches the sizing formula used in DHWSystem:
            strat_factor_pct = (storage_temp_f - supply_temp_f) / strat_slope
            usable_fraction  = strat_factor_pct * (1 - on_fract)

        Parameters
        ----------
        on_fract : float
        supply_temp_f : float
        storage_temp_f : float

        Returns
        -------
        float
        """
        if storage_temp_f <= supply_temp_f:
            return 0.0
        strat_factor_pct = (storage_temp_f - supply_temp_f) / self.strat_slope
        return max(0.0, strat_factor_pct * (1.0 - on_fract))
