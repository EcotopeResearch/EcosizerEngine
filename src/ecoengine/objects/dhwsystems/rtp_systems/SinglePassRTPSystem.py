from __future__ import annotations

from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.storage.StorageTank import StratifiedTank
from ecoengine.objects.dhwsystems.DHWSystem import _RHO_CP
from .RTPSystem import RTPSystem


class SinglePassRTPSystem(RTPSystem):
    """
    Single-pass Return-to-Primary system.

    Cold water passes through the heat pump once per heating cycle and is
    delivered directly at supply temperature.  Recirc loop return flow feeds
    back into the primary heat pump (not a separate TM tank), so the required
    heating capacity includes the steady-state recirc loss scaled by the run
    time ratio (24 / max_daily_run_hr).

    Storage volume sizing adds the daily recirc volume equivalent to the
    building magnitude before running the maximum-deficit algorithm.  This
    ensures that continuous recirc heat loss — which drains storage even when
    the heater is off — is accounted for without re-normalising the load shape.
    The same boost is applied for load-shift sizing to cover shed and load-up
    windows.

    Construction
    ------------
    Use the factory classmethod rather than calling __init__ directly::

        system = SinglePassRTPSystem.from_size(
            building        = building,
            supply_temp_f   = 120.0,
            storage_temp_f  = 150.0,
            return_temp_f   = 110.0,
            return_flow_gpm = 3.0,
        )
    """

    # ------------------------------------------------------------------
    # Factory constructor
    # ------------------------------------------------------------------

    @classmethod
    def from_size(
        cls,
        building,
        supply_temp_f: float,
        storage_temp_f: float,
        return_temp_f: float,
        return_flow_gpm: float,
        max_daily_run_hr: float = 16.0,
        defrost_factor: float = 1.0,
        control_schedule: list[str] | None = None,
        control_map: dict[str, Controls] | None = None,
        strat_slope: float = 1.7,
        load_shift_fract_total_vol: float = 1.0,
    ) -> SinglePassRTPSystem:
        """
        Size the system for the given building, then build it.

        Parameters
        ----------
        building : Building
        supply_temp_f : float
            DHW delivery temperature [°F].
        storage_temp_f : float
            Hot water storage setpoint [°F].
        return_temp_f : float
            Recirculation loop return temperature [°F].
        return_flow_gpm : float
            Recirculation loop flow rate [GPM].
        max_daily_run_hr : float
            Maximum hours the heater may run per day. Default 16.
        defrost_factor : float
            Fraction of rated capacity available after defrost (0-1). Default 1.0.
        control_schedule : list[str] | None
            24-element list of control keys. None for no load-shifting.
        control_map : dict[str, Controls] | None
            Controls objects keyed by schedule label.
        strat_slope : float
            Temperature gradient [°F per %-height] for stratification factor.
            Default 1.7 (mirrors original SPRTP.setStratificationPercentageSlope).
        load_shift_fract_total_vol : float
            Demand scaling factor for load-shift sizing (0-1). Default 1.0.

        Returns
        -------
        SinglePassRTPSystem
        """
        system = cls(
            water_heaters=[],
            storage_tank=None,
            supply_temp_f=supply_temp_f,
            storage_temp_f=storage_temp_f,
            return_temp_f=return_temp_f,
            return_flow_gpm=return_flow_gpm,
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
        return system

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------

    def size(
        self,
        building,
        control_schedule: list[str] | None = None,
        control_map: dict[str, Controls] | None = None,
        strat_slope: float = 1.7,
        load_shift_fract_total_vol: float = 1.0,
    ) -> None:
        """
        Size the single-pass RTP system.

        Runs the standard DHWSystem sizing pipeline (which dispatches to the
        RTPSystem capacity override and the LS volume override below), then
        stores the recirc capacity contribution as a separate result for
        reporting.

        Parameters
        ----------
        building : Building
        control_schedule : list[str] | None
        control_map : dict[str, Controls] | None
        strat_slope : float
        load_shift_fract_total_vol : float
        """
        super().size(
            building,
            control_schedule=control_schedule,
            control_map=control_map,
            strat_slope=strat_slope,
            load_shift_fract_total_vol=load_shift_fract_total_vol,
        )
        self._recirc_capacity_kbtuh: float = (
            self.get_recirc_loss_kbtuh()
            * 24.0
            / self.max_daily_run_hr
            / self.defrost_factor
        )

    def get_recirc_capacity_kbtuh(self) -> float:
        """
        Return the recirc-loss contribution to total heating capacity [kBTU/hr].

        This is the portion of the sized capacity dedicated to continuously
        offsetting recirculation loop losses.

        Raises
        ------
        RuntimeError
            If size() has not been called yet.
        """
        if not hasattr(self, "_recirc_capacity_kbtuh") or self._recirc_capacity_kbtuh is None:
            raise RuntimeError("size() must be called before get_recirc_capacity_kbtuh().")
        return self._recirc_capacity_kbtuh

    # ------------------------------------------------------------------
    # Running volume overrides (normal + load-shift)
    # ------------------------------------------------------------------

    def _calc_running_volume_supplyT_gal(
        self,
        building,
        capacity_kbtuh: float,
    ) -> float:
        """
        Add the daily recirc volume equivalent to the building magnitude before
        running the base-class storage deficit algorithm.

        Rationale
        ---------
        During heater-off periods the recirc loop continuously drains heat from
        storage, beyond what the DHW load shape captures.  The capacity boost
        compensates only while the heater is running.  By boosting
        ``building.daily_dhw_use_supplyT_gal`` by the 24-hour recirc equivalent
        the deficit algorithm sees the full effective daily demand (DHW + recirc),
        and the generation rate rises to match, so the sized storage covers the
        peak off-period recirc drain.

        The building magnitude is always restored via ``finally``.

        Parameters
        ----------
        building : Building
        capacity_kbtuh : float
            Total required heating capacity [kBTU/hr].

        Returns
        -------
        float
            Required running volume [gal at supplyT].
        """
        design_inlet = self._require_design_inlet_temp(building)
        recirc_daily_supplyT_gal = (
            self.get_recirc_loss_kbtuh()
            * 1000.0
            / (_RHO_CP * (self.supply_temp_f - design_inlet))
            * 24.0
        )

        # building.daily_dhw_use_supplyT_gal += recirc_daily_supplyT_gal
        # try:
        result = super()._calc_running_volume_supplyT_gal(building, capacity_kbtuh)
        # finally:
        #     building.daily_dhw_use_supplyT_gal -= recirc_daily_supplyT_gal
        return result

    def _calc_running_volume_ls_supplyT_gal(
        self,
        control_schedule: list[str],
        building,
        gen_rate_ls_gph: float,
        fract_total_vol: float = 1.0,
    ) -> float:
        """
        Add the daily recirc volume equivalent to the building magnitude before
        running the base-class load-shift deficit algorithm.

        Rationale
        ---------
        During a shed window the heater is off, but the recirc loop still
        continuously drains heat from storage.  By boosting
        ``building.daily_dhw_use_supplyT_gal`` by the 24-hour recirc
        equivalent, all sub-calculations inside the base method (vshift,
        load-up consumption, post-shed deficit) automatically account for
        the continuous recirc drain.

        The load shape itself is left unchanged — the recirc volume is
        distributed proportionally to the existing shape rather than as a
        flat per-hour offset, preserving peak-demand characteristics.

        The building magnitude is always restored via ``finally``.

        Parameters
        ----------
        control_schedule : list[str]
        building : Building
        gen_rate_ls_gph : float
            Load-shift generation rate [gal/hr at supplyT].
        fract_total_vol : float

        Returns
        -------
        float
            Load-shift running volume [gal at supplyT].
        """
        design_inlet = self._require_design_inlet_temp(building)
        recirc_daily_supplyT_gal = (
            self.get_recirc_loss_kbtuh()
            * 1000.0
            / (_RHO_CP * (self.supply_temp_f - design_inlet))
            * 24.0
        )

        building.daily_dhw_use_supplyT_gal += recirc_daily_supplyT_gal
        try:
            result = super()._calc_running_volume_ls_supplyT_gal(
                control_schedule, building, gen_rate_ls_gph, fract_total_vol
            )
        finally:
            building.daily_dhw_use_supplyT_gal -= recirc_daily_supplyT_gal
        return result

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def simulate_step(
        self,
        building,
        timestep_interval: int,
        interval_min: int = 1,
        mode: str = "normal",
    ) -> dict:
        """
        Run one timestep for a single-pass RTP system.

        Delegates the DHW draw and heater logic to the base class, then
        applies recirculation losses to the storage tank.  The recirc
        return flow cools the bottom of the tank every minute, reducing
        usable volume.  The returned dict is updated to reflect post-recirc
        tank state.
        """
        step = super().simulate_step(building, timestep_interval, interval_min, mode)
        if self.storage_tank is not None:
            self.storage_tank.add_recirc_return(
                self.return_flow_gpm, self.return_temp_f, interval_min,
                supply_temp_f=self.supply_temp_f,
            )
            step["usable_volume_supplyT_gal"] = (
                self.storage_tank.get_usable_volume_supplyT_gal(self.supply_temp_f)
            )
            step["tank_temps_f"] = [
                self.storage_tank.get_temperature_at_fraction(f)
                for f in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
            ]
        return step
