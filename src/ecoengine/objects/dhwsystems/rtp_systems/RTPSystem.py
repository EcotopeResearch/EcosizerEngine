from __future__ import annotations

from ..DHWSystem import DHWSystem, _RHO_CP


class RTPSystem(DHWSystem):
    """
    Base class for Return-to-Primary (RTP) systems.

    RTP systems route recirculation loop return flow back through the primary
    heat pump rather than into a separate TM system. Sizing adds daily BTUs
    needed to offset recirculation losses on top of the DHW-use BTUs.
    """

    def __init__(
        self,
        water_heaters,
        storage_tank,
        supply_temp_f: float,
        storage_temp_f: float,
        return_temp_f: float,
        return_flow_gpm: float,
        max_daily_run_hr: float = 16.0,
        defrost_factor: float = 1.0,
    ):
        """
        Parameters
        ----------
        water_heaters : list[WaterHeater]
        storage_tank : StorageTank
        supply_temp_f : float
        storage_temp_f : float
        return_temp_f : float
            Temperature of recirculation return water [°F].
        return_flow_gpm : float
            Recirculation loop flow rate [GPM].
        max_daily_run_hr : float
            Maximum hours the heating system may run per day. Default 16.
        defrost_factor : float
            Fraction of rated capacity available after defrost (0-1). Default 1.0.
        """
        super().__init__(
            water_heaters,
            storage_tank,
            supply_temp_f,
            storage_temp_f,
            max_daily_run_hr=max_daily_run_hr,
            defrost_factor=defrost_factor,
        )
        self.return_temp_f   = return_temp_f
        self.return_flow_gpm = return_flow_gpm

    # ------------------------------------------------------------------
    # Recirc loss
    # ------------------------------------------------------------------

    def get_recirc_loss_kbtuh(self) -> float:
        """
        Return the steady-state recirculation heat loss rate [kBTU/hr].

        Formula
        -------
        recirc_loss = return_flow_gpm × 60 × RHO_CP × (supply_temp - return_temp) / 1000

        Returns
        -------
        float
        """
        return (
            self.return_flow_gpm
            * 60.0
            * _RHO_CP
            * (self.supply_temp_f - self.return_temp_f)
            / 1000.0
        )

    # ------------------------------------------------------------------
    # Sizing override
    # ------------------------------------------------------------------

    def _calc_required_capacity(self, building) -> float:
        """
        Add recirc-loss capacity to the base DHW heating capacity.

        The heater must cover 24 hours of continuous recirc loss during its
        allotted daily run time, so the required recirc contribution scales
        with the run-time ratio (24 / max_daily_run_hr).

        Formula
        -------
        recirc_cap = recirc_loss_kbtuh × (24 / max_daily_run_hr) / defrost_factor
        total_cap  = dhw_cap + recirc_cap

        Parameters
        ----------
        building : Building

        Returns
        -------
        float
            Total required capacity [kBTU/hr].
        """
        dhw_cap    = super()._calc_required_capacity(building)
        recirc_cap = (
            self.get_recirc_loss_kbtuh()
            * 24.0
            / self.max_daily_run_hr
            / self.defrost_factor
        )
        return dhw_cap + recirc_cap

    def _calc_required_capacity_ls_kbtuh(
        self,
        control_schedule,
        control_map,
        building,
        strat_slope: float,
        fract_total_vol: float = 1.0,
    ) -> float:
        """
        Add recirc-loss capacity to the base DHW load-shift capacity.

        Mirrors _calc_required_capacity: the recirc loop runs 24 h/day
        regardless of the shed schedule, so the same steady-state recirc
        contribution (recirc_loss × 24 / max_daily_run_hr / defrost) is
        added on top of whatever DHW-only LS capacity the base class returns.

        Parameters
        ----------
        control_schedule : list[str]
        control_map : dict[str, Controls]
        building : Building
        strat_slope : float
        fract_total_vol : float

        Returns
        -------
        float
            Total required LS capacity [kBTU/hr].
        """
        dhw_ls_cap = super()._calc_required_capacity_ls_kbtuh(
            control_schedule, control_map, building, strat_slope, fract_total_vol
        )
        recirc_cap = (
            self.get_recirc_loss_kbtuh()
            * 24.0
            / self.max_daily_run_hr
            / self.defrost_factor
        )
        return dhw_ls_cap + recirc_cap
