from ..DHWSystem import DHWSystem

# Volumetric heat capacity of water [BTU / (gallon · °F)]
_RHO_CP: float = 8.353535


class RecircSystem(DHWSystem):
    """
    Base class for DHW systems that include a recirculation loop.

    Not intended for direct use — exists to share recirc-loop attributes and
    helpers between SwingSystem and ParallelLoopSystem. Systems where recirc
    return water enters the primary tank directly are handled separately in the
    rtp_systems section.
    """

    def __init__(
        self,
        water_heaters,
        storage_tank,
        supply_temp_f,
        storage_temp_f,
        return_temp_f,
        return_flow_gpm,
        max_daily_run_hr: float = 24.0,
        defrost_factor: float = 1.0,
    ):
        """
        Parameters
        ----------
        water_heaters : list[WaterHeater]
        storage_tank : StorageTank
        supply_temp_f : float
            DHW delivery temperature [°F].
        storage_temp_f : float
            Storage setpoint [°F].
        return_temp_f : float
            Temperature of water returning from the recirculation loop [°F].
        return_flow_gpm : float
            Recirculation loop flow rate [GPM] (assumed constant).
        max_daily_run_hr : float
            Maximum hours the primary heating system may run per day.
        defrost_factor : float
            Fraction of rated capacity available after defrost cycles (0–1).
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

    def get_recirc_loss_kbtuh(self) -> float:
        """
        Return the steady-state recirculation heat loss rate [kBTU/hr].

        Computed from loop flow rate and the temperature difference between
        supply and return:

            loss = flow_gpm × (supply_T − return_T) × ρCp × 60 min/hr / 1000

        Returns
        -------
        float
        """
        return (
            self.return_flow_gpm
            * (self.supply_temp_f - self.return_temp_f)
            * _RHO_CP
            * 60.0
            / 1000.0
        )

    def get_daily_recirc_loss_kbtu(self) -> float:
        """
        Return total daily recirculation heat loss [kBTU].

        Returns
        -------
        float
        """
        return self.get_recirc_loss_kbtuh() * 24.0

    def simulate_step(self, building, timestep_interval, interval_min=1, mode="normal"):
        """Delegate to DHWSystem.simulate_step() via super()."""
        return super().simulate_step(building, timestep_interval, interval_min, mode)
