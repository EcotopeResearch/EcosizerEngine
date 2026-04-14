from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING

from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.storage.StorageTank import StratifiedTank
from ecoengine.objects.components.storage.MixedStorageTank import MixedStorageTank
from ecoengine.objects.dhwsystems.DHWSystem import _get_peak_indices
from .RecircSystem import RecircSystem, _RHO_CP

if TYPE_CHECKING:
    from ecoengine.objects.building.Building import Building

# Swing tank TM sizing table [gallons].
# Volume is the smallest entry >= recirc_loss_btuhr / (100 W/gal * 3.412142 BTU/hr/W).
_SWING_SIZING_TABLE: list[int] = [
    40, 50, 80, 100, 120, 160, 175, 240, 350, 400, 500, 600, 800, 1000, 1250
]
_WATTS_PER_GAL: float = 100.0
_W_TO_BTUHR:   float = 3.412142

# TM element deadband: fires at supply_temp_f, shuts off at supply_temp_f + 8 °F.
_ELEMENT_DEADBAND_F: float = 8.0


def _hr_to_min(hourly_arr: np.ndarray) -> np.ndarray:
    """Repeat each hourly value 60 times → per-minute array (length × 60)."""
    return np.repeat(hourly_arr, 60)


class SwingSystem(RecircSystem):
    """
    Swing tank system: a single fully-mixed tank in SERIES with the primary
    storage acts as both the recirculation temperature-maintenance (TM) volume
    and a draw-through buffer.

    All DHW demand passes through the swing tank before delivery, so the
    primary storage only needs to supply the deficit not met by the swing
    tank's thermal mass.  This reduces effective primary demand (captured by
    ``_eff_mix_fraction``) but requires the TM element to maintain the swing
    tank at or above supply temperature.

    Sizing order (overrides DHWSystem)
    -----------------------------------
    1. Size TM (table lookup from recirc loss rate).
    2. Compute running volume via swing-tank simulation — yields
       ``_eff_mix_fraction`` as a side-effect.
    3. Compute primary capacity using ``_eff_mix_fraction`` and storage temp.

    Construction
    ------------
    Use the factory classmethod::

        system = SwingSystem.from_size(
            building        = building,
            supply_temp_f   = 120.0,
            storage_temp_f  = 150.0,
            return_temp_f   = 110.0,
            return_flow_gpm = 3.0,
            tm_safety_factor = 1.2,
        )
    """

    def __init__(
        self,
        water_heaters,
        storage_tank,
        supply_temp_f: float,
        storage_temp_f: float,
        return_temp_f: float,
        return_flow_gpm: float,
        tm_safety_factor: float = 1.2,
        max_daily_run_hr: float = 24.0,
        defrost_factor: float = 1.0,
    ):
        super().__init__(
            water_heaters,
            storage_tank,
            supply_temp_f,
            storage_temp_f,
            return_temp_f,
            return_flow_gpm,
            max_daily_run_hr=max_daily_run_hr,
            defrost_factor=defrost_factor,
        )
        if tm_safety_factor <= 1.0:
            raise ValueError(
                "tm_safety_factor must be > 1.0 — the TM element must outpace recirc losses."
            )
        self.tm_safety_factor = tm_safety_factor

        # TM sizing results — populated by _size_tm_system()
        self._minimum_tm_volume_gal:     float | None = None
        self._minimum_tm_capacity_kbtuh: float | None = None

        # Effective mix fraction — populated by _calc_running_volume_supplyT_gal()
        # during size(). Captures the swing tank's reduction of primary demand (≤ 1.0).
        self._eff_mix_fraction: float = 1.0

        # TM (swing tank) components — populated by from_size() after sizing.
        self.tm_storage_tank:  MixedStorageTank | None = None
        self.tm_water_heater:  WaterHeater | None      = None

    # ------------------------------------------------------------------
    # Factory constructor
    # ------------------------------------------------------------------

    @classmethod
    def from_size(
        cls,
        building: Building,
        supply_temp_f: float,
        storage_temp_f: float,
        return_temp_f: float,
        return_flow_gpm: float,
        tm_safety_factor: float = 1.2,
        max_daily_run_hr: float = 24.0,
        defrost_factor: float = 1.0,
        control_schedule: list[str] | None = None,
        control_map: dict[str, Controls] | None = None,
        strat_slope: float = 2.8,
        load_shift_fract_total_vol: float = 1.0,
    ) -> SwingSystem:
        system = cls(
            water_heaters=[],
            storage_tank=None,
            supply_temp_f=supply_temp_f,
            storage_temp_f=storage_temp_f,
            return_temp_f=return_temp_f,
            return_flow_gpm=return_flow_gpm,
            tm_safety_factor=tm_safety_factor,
            max_daily_run_hr=max_daily_run_hr,
            defrost_factor=defrost_factor,
        )
        system.size(
            building,
            control_schedule=control_schedule,
            control_map=control_map,
            strat_slope=strat_slope,
            load_shift_fract_total_vol=load_shift_fract_total_vol,
        )
        system.storage_tank = StratifiedTank(
            total_volume_gal=system._minimum_storage_storageT_gal,
            strat_slope=strat_slope,
        )
        system.water_heaters = [WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=system._minimum_capacity_kbtuh,
            control_schedule=control_schedule,
            control_map=control_map,
        )]

        # TM (swing tank) components
        system.tm_storage_tank = MixedStorageTank(
            total_volume_gal=system._minimum_tm_volume_gal,
        )
        tm_controls = Controls(
            on_sensor_fract  = 0.5,   # irrelevant for fully-mixed tank
            on_trigger_t_f   = supply_temp_f,
            off_sensor_fract = 0.5,
            off_trigger_t_f  = supply_temp_f + _ELEMENT_DEADBAND_F,
            outlet_temp_f    = supply_temp_f + _ELEMENT_DEADBAND_F,
        )
        system.tm_water_heater = WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=system._minimum_tm_capacity_kbtuh,
            control_schedule=["normal"] * 24,
            control_map={"normal": tm_controls},
        )

        return system

    # ------------------------------------------------------------------
    # Sizing — public interface (overrides DHWSystem.size())
    # ------------------------------------------------------------------

    def size(
        self,
        building: Building,
        control_schedule: list[str] | None = None,
        control_map: dict[str, Controls] | None = None,
        strat_slope: float = 2.8,
        load_shift_fract_total_vol: float = 1.0,
    ) -> None:
        """
        Size the swing tank system.

        Overrides DHWSystem.size() to enforce the correct order:
        volume first (which yields ``_eff_mix_fraction``), then capacity.
        The SwingTank capacity formula uses storage temperature, not supply
        temperature, matching the original codebase's _primaryHeatHrs2kBTUHR.
        """
        was_annual = building.is_annual_load_shape()
        if was_annual:
            building.set_to_daily_load_shape()

        original_max_run_hr = self.max_daily_run_hr
        if control_schedule and self._is_load_shifting(control_map):
            non_shed = float(sum(1 for h in control_schedule if h != "shed"))
            self.max_daily_run_hr = min(self.max_daily_run_hr, non_shed)

        try:
            design_inlet_temp_f = self._require_design_inlet_temp(building)

            # Step 1: TM sizing (table lookup) — must come first so that
            # _sim_just_swing can use _minimum_tm_volume_gal and
            # _minimum_tm_capacity_kbtuh.
            self._size_tm_system()

            # Step 2: Running volume (side-effect: populates _eff_mix_fraction)
            self._eff_mix_fraction = 1.0
            running_vol_supplyT_gal = self._calc_running_volume_supplyT_gal(
                building, capacity_kbtuh=None
            )
            strat_factor = self._calc_stratification_factor(control_map, strat_slope, design_inlet_temp_f)
            storage_vol_storageT_gal = self._calc_storage_volume_storageT_gal(
                running_vol_supplyT_gal, strat_factor
            )

            # Step 3: Capacity uses storage temp + _eff_mix_fraction from normal sizing.
            # Note: this intentionally diverges from the original codebase, which fed
            # the LS effMixFraction back into the capacity formula (i.e. it would call
            # sizePrimaryTankVolume() — which ran _calcRunningVolLS — before calling
            # _primaryHeatHrs2kBTUHR() with the resulting LSeffMixFract).  The original
            # SwingTank._primaryHeatHrs2kBTUHR() also computed Vload using raw aquastat
            # fractions instead of strat-adjusted percentages, meaning its LU gen rate
            # was inflated relative to the thermodynamically correct value.  Both of
            # these are bugs in the original.  The new code:
            #   (a) uses _strat_pct_of_tank (correct thermal accounting for Vload), and
            #   (b) computes capacity with normal_eff_mix (no feedback from LS path).
            # The result is a slightly smaller capacity for some LS scenarios, which is
            # the physically correct answer — a smaller, better-matched system.
            capacity_kbtuh = self._calc_required_capacity(building)

            if control_schedule and self._is_load_shifting(control_map):
                ls_gen_rate_gph = self._calc_gen_rate_ls_gph(
                    control_schedule, control_map, building, strat_slope,
                    fract_total_vol=load_shift_fract_total_vol,
                )
                ls_capacity_kbtuh = self._calc_required_capacity_ls_kbtuh(
                    control_schedule, control_map, building, strat_slope,
                    fract_total_vol=load_shift_fract_total_vol,
                )
                ls_running_vol, ls_eff_mix = self._calc_running_volume_ls_swing(
                    control_schedule, building, ls_gen_rate_gph,
                    fract_total_vol=load_shift_fract_total_vol,
                )
                ls_storage_vol = self._calc_storage_volume_ls_storageT_gal(
                    ls_running_vol, control_map, strat_slope, design_inlet_temp_f
                )
                capacity_kbtuh = max(capacity_kbtuh, ls_capacity_kbtuh)

                if ls_storage_vol > storage_vol_storageT_gal:
                    storage_vol_storageT_gal = ls_storage_vol
                    self._eff_mix_fraction = ls_eff_mix

            self._minimum_capacity_kbtuh       = capacity_kbtuh
            self._minimum_storage_storageT_gal = storage_vol_storageT_gal

        finally:
            self.max_daily_run_hr = original_max_run_hr

        if was_annual:
            building.set_to_annual_load_shape()

    # ------------------------------------------------------------------
    # TM sizing
    # ------------------------------------------------------------------

    def _size_tm_system(self) -> None:
        """
        Size the swing tank TM element and volume from the recirc loss rate.

        Volume is the smallest table entry satisfying:
            recirc_loss_btuhr / (100 W/gal × 3.412142 BTU/hr/W) ≤ entry

        Capacity is:
            tm_safety_factor × recirc_loss_kbtuh
        """
        recirc_loss_btuhr = self.get_recirc_loss_kbtuh() * 1000.0
        vol_required = recirc_loss_btuhr / (_WATTS_PER_GAL * _W_TO_BTUHR)
        if vol_required > max(_SWING_SIZING_TABLE):
            raise ValueError(
                f"Recirculation losses ({recirc_loss_btuhr:.0f} BTU/hr) require a swing "
                f"tank larger than {max(_SWING_SIZING_TABLE)} gal. "
                "Consider splitting into multiple central plants."
            )
        self._minimum_tm_volume_gal = min(
            v for v in _SWING_SIZING_TABLE if v >= vol_required
        )
        self._minimum_tm_capacity_kbtuh = self.tm_safety_factor * recirc_loss_btuhr / 1000.0

    # ------------------------------------------------------------------
    # Capacity — uses storage temp (key difference from base DHWSystem)
    # ------------------------------------------------------------------

    def _calc_required_capacity(self, building: Building) -> float:
        """
        Override: capacity formula uses storage temperature, not supply.

        ``capacity = (daily_gal × effMixFraction / heatHrs)
                     × RHO_CP × (storage_temp − inlet_temp) / defrost / 1000``

        ``_eff_mix_fraction`` must be set by
        ``_calc_running_volume_supplyT_gal()`` before this is called.
        """
        design_inlet_temp_f = self._require_design_inlet_temp(building)
        gen_rate_gph = (
            building.daily_dhw_use_supplyT_gal
            * self._eff_mix_fraction
            / self.max_daily_run_hr
        )
        delta_t = self.storage_temp_f - design_inlet_temp_f
        return gen_rate_gph * _RHO_CP * delta_t / self.defrost_factor / 1000

    # ------------------------------------------------------------------
    # Running volume — swing simulation
    # ------------------------------------------------------------------

    def _calc_running_volume_supplyT_gal(
        self,
        building: Building,
        capacity_kbtuh: float,  # unused; kept for base-class signature compatibility
    ) -> float:
        """
        Override: compute running volume via per-peak swing-tank simulation.

        For each surplus→deficit transition in the peak load shape, the swing
        tank is simulated over 24 hours.  The demand placed on the PRIMARY
        (``hw_out_from_swing``) is the thermal deficit the swing tank cannot
        absorb from its own mass.  The maximum cumulative deficit of
        (primary generation − primary demand) is the running volume.

        Side-effect: populates ``self._eff_mix_fraction``.

        Returns
        -------
        float
            Running volume [gallons at supply temperature].
        """
        daily_gal  = building.daily_dhw_use_supplyT_gal
        load_shape = building.peak_load_shape   # 24 normalised fractions
        inlet_t_f  = self._require_design_inlet_temp(building)

        # Hourly generation rate (normalised: each non-zero hour = 1/heatHrs)
        gen_norm      = np.ones(24) / self.max_daily_run_hr
        hourly_diff   = gen_norm - load_shape

        peak_indices = _get_peak_indices(hourly_diff)
        if not peak_indices:
            return 0.0

        n_real_peaks = len(peak_indices)
        # Also probe the hour after each real peak (matches original safety check)
        extended = list(peak_indices)
        for idx in peak_indices:
            if idx + 1 < 24:
                extended.append(idx + 1)
        extended = sorted(set(extended))

        running_vol      = 0.0
        eff_mix_fraction = 1.0

        for k, peak_idx in enumerate(extended):
            hw_out_hrly = np.tile(load_shape, 2)[peak_idx : peak_idx + 24]
            hw_out_min  = _hr_to_min(hw_out_hrly) / 60.0 * daily_gal  # gal/min

            _, _, hw_from_swing = self._sim_just_swing(
                len(hw_out_min), hw_out_min, building, self.supply_temp_f + 0.1
            )

            temp_eff_mix = sum(hw_from_swing) / daily_gal

            gen_hrly = np.tile(gen_norm, 2)[peak_idx : peak_idx + 24]
            gen_min  = _hr_to_min(gen_hrly) / 60.0 * daily_gal * temp_eff_mix

            diff_min = gen_min - np.array(hw_from_swing)
            cum_diff = np.cumsum(diff_min)
            neg_vals = cum_diff[cum_diff < 0]

            # Skip extra-peak safety indices when no deficit is found
            if k >= n_real_peaks and len(neg_vals) == 0:
                continue
            if len(neg_vals) == 0:
                continue

            new_vol = float(-np.min(neg_vals))
            if new_vol > running_vol:
                running_vol      = new_vol
                eff_mix_fraction = temp_eff_mix

        self._eff_mix_fraction = eff_mix_fraction

        # The swing simulation works in storage-frame gallons (the primary feeds
        # the swing tank at storage_temp_f).  Convert to supply-temp equivalent
        # so _calc_storage_volume_storageT_gal receives a consistent unit.
        running_vol *= (self.storage_temp_f - inlet_t_f) / (self.supply_temp_f - inlet_t_f)
        return running_vol

    # ------------------------------------------------------------------
    # LS prelim volumes — swing-aware override
    # ------------------------------------------------------------------

    def _calc_prelim_vols_supplyT_gal(
        self,
        control_schedule: list[str],
        building: Building,
        fract_total_vol: float = 1.0,
    ) -> tuple[float, float]:
        """
        Override: adjust preliminary volumes for swing tank contribution.

        Each raw volume (demand during the period) is reduced by the fraction
        that the swing tank can absorb from its thermal mass, determined by
        simulating the swing tank over that period.
        """
        daily_gal  = building.daily_dhw_use_supplyT_gal
        load_shape = building.avg_load_shape
        load_shape_gph = load_shape * daily_gal

        first_shed_block, load_up_hours = (
            self._get_first_shed_block_and_load_up_hours(control_schedule)
        )

        # --- Vshift (demand during first shed block) ---
        vshift_raw = float(sum(load_shape_gph[h] for h in first_shed_block))
        shed_hw_min = _hr_to_min(
            np.array([load_shape_gph[h] for h in first_shed_block])
        ) / 60.0
        _, _, hw_swing_shed = self._sim_just_swing(
            len(shed_hw_min), shed_hw_min, building, self.supply_temp_f + 0.1
        )
        eff_shed = sum(hw_swing_shed) / vshift_raw if vshift_raw > 0 else 1.0
        vshift = vshift_raw * eff_shed * fract_total_vol

        # --- VconsumedLU (demand during load-up hours) ---
        lu_start = first_shed_block[0] - load_up_hours
        vconsumed_lu_raw = float(
            sum(load_shape_gph[h] for h in range(lu_start, first_shed_block[0]))
        )
        if load_up_hours > 0 and vconsumed_lu_raw > 0:
            lu_hw_min = _hr_to_min(
                np.array([load_shape_gph[h] for h in range(lu_start, first_shed_block[0])])
            ) / 60.0
            _, _, hw_swing_lu = self._sim_just_swing(
                len(lu_hw_min), lu_hw_min, building, self.supply_temp_f + 0.1
            )
            eff_lu = sum(hw_swing_lu) / vconsumed_lu_raw
            vconsumed_lu = vconsumed_lu_raw * eff_lu
        else:
            vconsumed_lu = vconsumed_lu_raw

        return vshift, vconsumed_lu

    # ------------------------------------------------------------------
    # LS generation rate — uses storage temp in capacity formula
    # ------------------------------------------------------------------

    def _calc_gen_rate_ls_gph(
        self,
        control_schedule: list[str],
        control_map: dict[str, Controls],
        building: Building,
        strat_slope: float,
        fract_total_vol: float = 1.0,
    ) -> float:
        """
        Override: LS gen rate using swing-adjusted prelim volumes and storage temp.

        Normal gen rate = daily_gal × effMixFraction / heatHrs.
        LU gen rate     = (Vload + VconsumedLU) / loadUpHours.

        Returns the maximum.
        """
        daily_gal           = building.daily_dhw_use_supplyT_gal
        normal_gen_rate_gph = daily_gal * self._eff_mix_fraction / self.max_daily_run_hr

        _, load_up_hours = self._get_first_shed_block_and_load_up_hours(control_schedule)
        if load_up_hours == 0:
            return normal_gen_rate_gph

        vshift, vconsumed_lu = self._calc_prelim_vols_supplyT_gal(
            control_schedule, building, fract_total_vol
        )

        normal_ctrl = control_map["normal"]
        lu_ctrl     = control_map.get("loadUp", normal_ctrl)
        shed_ctrl   = control_map["shed"]

        lu_strat     = self._strat_pct_of_tank(lu_ctrl.on_sensor_fract,     lu_ctrl.on_trigger_t_f,     strat_slope)
        normal_strat = self._strat_pct_of_tank(normal_ctrl.on_sensor_fract, normal_ctrl.on_trigger_t_f, strat_slope)
        shed_strat   = self._strat_pct_of_tank(shed_ctrl.on_sensor_fract,   shed_ctrl.on_trigger_t_f,   strat_slope)

        ls_band = lu_strat - shed_strat
        if ls_band <= 0:
            return normal_gen_rate_gph

        vload = vshift * (lu_strat - normal_strat) / ls_band
        lu_gen_rate_gph = (vload + vconsumed_lu) / load_up_hours

        return max(normal_gen_rate_gph, lu_gen_rate_gph)

    def _calc_required_capacity_ls_kbtuh(
        self,
        control_schedule: list[str],
        control_map: dict[str, Controls],
        building: Building,
        strat_slope: float,
        fract_total_vol: float = 1.0,
    ) -> float:
        """
        Override: LS capacity uses storage temperature (matches normal path).
        """
        design_inlet_temp_f = self._require_design_inlet_temp(building)
        gen_rate_ls_gph = self._calc_gen_rate_ls_gph(
            control_schedule, control_map, building, strat_slope, fract_total_vol
        )
        delta_t = self.storage_temp_f - design_inlet_temp_f
        return gen_rate_ls_gph * _RHO_CP * delta_t / self.defrost_factor / 1000

    # ------------------------------------------------------------------
    # LS running volume — swing-aware
    # ------------------------------------------------------------------

    def _calc_running_volume_ls_swing(
        self,
        control_schedule: list[str],
        building: Building,
        gen_rate_ls_gph: float,
        fract_total_vol: float = 1.0,
    ) -> tuple[float, float]:
        """
        Swing-aware LS running volume calculation.

        Simulates the swing tank over the 24 hours starting from the end of
        the first shed period.  Returns (running_vol_supplyT_gal, eff_mix_fraction).
        """
        daily_gal  = building.daily_dhw_use_supplyT_gal
        load_shape = building.avg_load_shape
        inlet_t_f  = self._require_design_inlet_temp(building)

        first_shed_block, _ = self._get_first_shed_block_and_load_up_hours(control_schedule)
        vshift, _ = self._calc_prelim_vols_supplyT_gal(
            control_schedule, building, fract_total_vol
        )

        # 24-hr gen profile: gen_rate_ls during non-shed hours, 0 during shed
        gen_profile_gph = np.array([
            0.0 if control_schedule[h] == "shed" else gen_rate_ls_gph
            for h in range(24)
        ])

        # Start from the first hour after the shed ends
        shed_end_idx = first_shed_block[-1] + 1

        hw_out_hourly = np.tile(load_shape * daily_gal, 2)[shed_end_idx : shed_end_idx + 24]
        hw_out_min    = _hr_to_min(hw_out_hourly) / 60.0

        _, _, hw_from_swing = self._sim_just_swing(
            len(hw_out_min), hw_out_min, building, self.supply_temp_f + 0.1
        )
        eff_mix_fraction = sum(hw_from_swing) / daily_gal

        # Generation per minute — NOT scaled by effMixFraction (matches original)
        gen_hrly = np.tile(gen_profile_gph, 2)[shed_end_idx : shed_end_idx + 24]
        gen_min  = _hr_to_min(gen_hrly) / 60.0

        diff_min = gen_min - np.array(hw_from_swing)
        cum_diff = np.cumsum(diff_min)
        neg_vals = cum_diff[cum_diff < 0]
        deficit  = float(-np.min(neg_vals)) if len(neg_vals) > 0 else 0.0

        running_vol = deficit + vshift
        # Same storage-frame → supply-temp conversion as the normal path.
        running_vol *= (self.storage_temp_f - inlet_t_f) / (self.supply_temp_f - inlet_t_f)
        return running_vol, eff_mix_fraction

    # ------------------------------------------------------------------
    # Swing tank helpers
    # ------------------------------------------------------------------

    def _sim_just_swing(
        self,
        n_steps: int,
        hw_out: np.ndarray,
        building: Building,
        init_st: float | None = None,
    ) -> tuple[list[float], list[float], list[float]]:
        """
        Simulate the swing tank in isolation at 1-minute timesteps.

        The primary is assumed to always supply water at ``storage_temp_f``.
        Returns (swing_temps, tm_run_fractions, hw_out_from_swing) where
        ``hw_out_from_swing[i]`` is the volume drawn from primary storage each
        minute (at swing-tank temperature), which is the demand that the primary
        system must satisfy.
        """
        inlet_t_f = self._require_design_inlet_temp(building)

        swing_temps     = [self.supply_temp_f] * n_steps
        tm_run          = [0.0] * n_steps
        hw_from_primary = [0.0] * n_steps

        swing_temps[0]     = init_st if init_st is not None else self.supply_temp_f
        hw_from_primary[0] = hw_out[0]  # first step: assume full demand from primary

        swingheating = False

        for i in range(1, n_steps):
            t_prev = swing_temps[i - 1]
            # Demand on primary = supply-temp volume converted to swing-tank-temp volume
            if t_prev > inlet_t_f:
                hw_from_primary[i] = (
                    hw_out[i]
                    * (self.supply_temp_f - inlet_t_f)
                    / (t_prev - inlet_t_f)
                )
            else:
                hw_from_primary[i] = hw_out[i]

            swingheating, swing_temps[i], tm_run[i] = self._run_one_swing_step(
                swingheating,
                t_prev,
                hw_from_primary[i],
                self.storage_temp_f,  # primary always feeds at storage temp
            )

        return swing_temps, tm_run, hw_from_primary

    def _run_one_swing_step(
        self,
        swingheating: bool,
        t_curr: float,
        hw_out: float,
        primary_storage_t_f: float,
    ) -> tuple[bool, float, float]:
        """
        Advance the swing tank by one minute.

        1. Mix primary hot water into the tank.
        2. Apply recirculation heat loss.
        3. Apply TM element heat if active; check on/off triggers.

        Parameters
        ----------
        swingheating : bool
            True if element was active at the start of this step.
        t_curr : float
            Tank temperature at start of step [°F].
        hw_out : float
            Volume drawn from primary storage this minute [gal].
        primary_storage_t_f : float
            Temperature of hot water fed from primary into swing tank [°F].

        Returns
        -------
        (swingheating, t_new, time_run)
        """
        tm_vol = self._minimum_tm_volume_gal
        t_new  = t_curr

        # Mix primary hot water in
        if hw_out > 0:
            vol_remaining = tm_vol - hw_out
            if vol_remaining <= 0:
                raise ValueError(
                    f"Swing tank ({tm_vol:.0f} gal) is undersized: "
                    f"per-minute draw of {hw_out:.3f} gal exceeds tank volume."
                )
            t_new = (hw_out * primary_storage_t_f + t_curr * vol_remaining) / tm_vol

        # Recirc heat loss [°F/min]
        recirc_btuhr = self.get_recirc_loss_kbtuh() * 1000.0
        t_new -= recirc_btuhr / 60.0 / (_RHO_CP * tm_vol)

        # TM element heat rate [°F/min]
        element_dT = (self._minimum_tm_capacity_kbtuh * 1000.0) / 60.0 / (_RHO_CP * tm_vol)

        time_running = 0.0
        if swingheating:
            t_new        += element_dT
            time_running  = 1.0
            if t_new > self.supply_temp_f + _ELEMENT_DEADBAND_F:
                time_over    = min(
                    (t_new - (self.supply_temp_f + _ELEMENT_DEADBAND_F)) / element_dT, 1.0
                )
                t_new        -= element_dT * time_over
                time_running  = 1.0 - time_over
                swingheating  = False
        elif t_new <= self.supply_temp_f:
            time_missed  = min((self.supply_temp_f - t_new) / element_dT, 1.0)
            t_new        += element_dT * time_missed
            time_running  = time_missed
            swingheating  = True

        if t_new < self.supply_temp_f:
            raise ValueError(
                "Swing tank dropped below supply temperature during sizing simulation. "
                "System is undersized — increase TM capacity or reduce recirc losses."
            )

        return swingheating, t_new, time_running

    # ------------------------------------------------------------------
    # TM property — derived from tm_water_heater controls
    # ------------------------------------------------------------------

    @property
    def tm_off_temp_f(self) -> float:
        """
        Temperature at which the TM element shuts off (the swing tank's
        fully-charged setpoint).

        Derived from ``tm_water_heater``'s Controls rather than stored
        separately.  Falls back to ``supply_temp_f + _ELEMENT_DEADBAND_F``
        before ``from_size()`` has been called (e.g. during sizing).

        The Simulator reads this attribute to initialize the swing tank at
        the correct starting temperature.
        """
        if self.tm_water_heater is not None:
            ctrl = self.tm_water_heater.get_controls_for_hour(0)
            if ctrl is not None:
                return ctrl.off_trigger_t_f
        return self.supply_temp_f + _ELEMENT_DEADBAND_F

    # ------------------------------------------------------------------
    # TM sizing result accessors
    # ------------------------------------------------------------------

    def get_minimum_tm_volume_gal(self) -> float:
        if self._minimum_tm_volume_gal is None:
            raise RuntimeError("size() must be called before get_minimum_tm_volume_gal().")
        return self._minimum_tm_volume_gal

    def get_minimum_tm_capacity_kbtuh(self) -> float:
        if self._minimum_tm_capacity_kbtuh is None:
            raise RuntimeError("size() must be called before get_minimum_tm_capacity_kbtuh().")
        return self._minimum_tm_capacity_kbtuh

    # ------------------------------------------------------------------
    # ER resize stub (to be implemented later)
    # ------------------------------------------------------------------

    def resize_with_er(self, building: Building, primary_capacity_kbtuh: float) -> None:
        """
        Placeholder for ER-element resizing (SwingTankER behavior).

        When implemented, this will reduce the primary heating capacity to
        ``primary_capacity_kbtuh`` and add an ER element to the swing tank
        to compensate for the reduced primary output at design conditions,
        following the SwingTankER.sizeERElement() logic from the original.
        """
        raise NotImplementedError("resize_with_er() is not yet implemented.")

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def simulate_step(
        self,
        building : Building,
        timestep_interval: int,
        interval_min: int = 1,
        mode: str = "normal",
    ) -> dict:
        """
        Execute one simulation timestep for the swing tank system.

        The swing tank sits in series between the primary storage and the
        building.  All DHW demand passes through the swing tank; the primary
        storage only needs to supply what the swing tank cannot absorb from its
        own thermal mass.

        Order of operations
        -------------------
        1. Query building for demand, OAT, and inlet water temperature.
        2. Update primary WaterHeater states; apply heat to primary StratifiedTank.
        3. Compute physical gallons that must flow from primary to swing tank this
           timestep based on current swing tank temperature and demand.
        4. Obtain the average temperature of that draw block from the primary tank's
           stratification profile (handles partial hot-zone depletion).
        5. Mix primary inflow into swing tank (``tm_storage_tank.mix_primary_inflow``).
        6. Apply recirculation heat loss to swing tank (``add_recirc_return``).
        7. Update TM WaterHeater state; apply TM heat to swing tank.
        8. Draw the computed physical volume from the primary storage tank.
        9. Determine usable volume: 0 if swing tank is below supply temperature,
           otherwise derived from the primary tank's stratification profile.
        10. Merge primary and TM energy outputs and return per-step metrics.

        Parameters
        ----------
        building : Building
        timestep_interval : int
        interval_min : int
        mode : str
            Ignored — operating mode is determined by each heater's control schedule.

        Returns
        -------
        dict
            Same keys as DHWSystem.simulate_step(). ``heater_output_kbtuh`` and
            ``heater_power_in_kw`` include both primary and TM heater contributions.
        """
        # --- 1. Building data ---
        use_avg = any(wh.is_load_shifting() for wh in self.water_heaters)
        demand_supplyT_gal = building.get_dhw_load_supplyT_gal(
            timestep_interval, interval_min, use_avg=use_avg
        )
        oat_f        = building.get_oat_f(timestep_interval, interval_min)
        inlet_temp_f = building.get_inlet_water_temp_f(timestep_interval, interval_min)
        hour_of_day  = (timestep_interval * interval_min // 60) % 24
        outlet_temp_f = self._get_outlet_temp_f(hour_of_day)
        step_mode = (
            self.water_heaters[0].control_schedule[hour_of_day]
            if self.water_heaters and self.water_heaters[0].control_schedule
            else "normal"
        )

        # --- 2. Primary heater: update state and heat primary tank ---
        for wh in self.water_heaters:
            wh.update_state(self.storage_tank, hour_of_day)

        top_temp_f    = self.storage_tank.get_temperature_at_fraction(1.0)
        primary_kbtuh = sum(
            wh.get_output_kbtuh(oat_f, top_temp_f) for wh in self.water_heaters
        )
        primary_kw_list = [
            wh.get_power_in_kw(oat_f, top_temp_f)
            for wh in self.water_heaters
            if wh.is_active()
        ]
        primary_kw: float | None = (
            sum(kw or 0.0 for kw in primary_kw_list) if primary_kw_list else None
        )
        self.storage_tank.heat(primary_kbtuh, interval_min, outlet_temp_f)

        # --- 3. Physical gallons drawn from primary → swing tank this timestep ---
        swing_t = self.tm_storage_tank.get_temperature_at_fraction(0.5)
        if swing_t > inlet_temp_f: # TODO : shouldn't this be self.supply_temp_f instead of inlet_temp_f?
            hw_swing_gal = (
                demand_supplyT_gal
                * (self.supply_temp_f - inlet_temp_f)
                / (swing_t - inlet_temp_f)
            )
        else:
            # Swing tank is cold; full demand volume must come from primary
            hw_swing_gal = demand_supplyT_gal

        # --- 4. Average feed temperature from primary stratification profile ---
        feed_temp_f = self.storage_tank.get_average_draw_temp_f(hw_swing_gal)

        # --- 5. Mix primary inflow into swing tank ---
        self.tm_storage_tank.mix_primary_inflow(hw_swing_gal, feed_temp_f)

        # --- 6. Recirculation heat loss (fixed rate, consistent with sizing formula) ---
        self.tm_storage_tank.apply_fixed_heat_loss_kbtuh(
            self.get_recirc_loss_kbtuh(), interval_min
        )

        # --- 7. TM element: update state and heat swing tank ---
        self.tm_water_heater.update_state(self.tm_storage_tank, hour_of_day)
        tm_top_t    = self.tm_storage_tank.get_temperature_at_fraction(1.0)
        tm_kbtuh    = self.tm_water_heater.get_output_kbtuh(oat_f, tm_top_t)
        tm_kw_val   = (
            self.tm_water_heater.get_power_in_kw(oat_f, tm_top_t)
            if self.tm_water_heater.is_active()
            else None
        )
        tm_ctrl = self.tm_water_heater.get_controls_for_hour(hour_of_day)
        tm_outlet_f = tm_ctrl.outlet_temp_f if tm_ctrl is not None else self.tm_off_temp_f
        self.tm_storage_tank.heat(tm_kbtuh, interval_min, tm_outlet_f)

        # --- 8. Draw computed volume from primary storage ---
        self.storage_tank.draw_physical_gal(hw_swing_gal, inlet_temp_f)

        # --- 9. Usable volume ---
        if swing_t < self.supply_temp_f:
            usable_vol_gal = 0.0
        else:
            usable_vol_gal = self.storage_tank.get_usable_volume_supplyT_gal(
                self.supply_temp_f
            )

        # --- 10. Tank temperature profile (primary stratified tank) ---
        tank_temps_f = [
            self.storage_tank.get_temperature_at_fraction(f)
            for f in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        ]

        # --- 11. Merge primary + TM outputs ---
        # heater_output_kbtuh stays PRIMARY-ONLY (used for gal/hr plot in top chart).
        # heater_power_in_kw merges both so get_total_energy_kwh() is accurate.
        if primary_kw is not None or tm_kw_val is not None:
            total_kw: float | None = (primary_kw or 0.0) + (tm_kw_val or 0.0)
        else:
            total_kw = None

        return {
            "demand_supplyT_gal":        demand_supplyT_gal,
            "usable_volume_supplyT_gal": usable_vol_gal,
            "heater_output_kbtuh":       primary_kbtuh,
            "heater_power_in_kw":        total_kw,
            "oat_f":                     oat_f,
            "inlet_water_temp_f":        inlet_temp_f,
            "tank_temps_f":              tank_temps_f,
            "mode":                      step_mode,
            # TM panel data (consumed by SimulationRun for the swing-tank subplot)
            "tm_tank_temp_f":            self.tm_storage_tank.get_temperature_at_fraction(0.5),
            "tm_heater_output_kbtuh":    tm_kbtuh,
        }
