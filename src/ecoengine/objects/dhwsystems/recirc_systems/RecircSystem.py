from ..DHWSystem import DHWSystem


class RecircSystem(DHWSystem):
    """
    Base class for DHW systems that include a recirculation loop.
    Adds return temperature and return flow fields used in sizing and simulation.
    """

    def __init__(
        self,
        water_heaters,
        storage_tank,
        supply_temp_f,
        storage_temp_f,
        return_temp_f,
        return_flow_gpm,
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
        """
        super().__init__(water_heaters, storage_tank, supply_temp_f, storage_temp_f)
        self.return_temp_f = return_temp_f
        self.return_flow_gpm = return_flow_gpm

    def get_recirc_loss_kbtuh(self):
        """
        Return the steady-state recirculation heat loss rate [kBTU/hr].

        Returns
        -------
        float
        """
        pass

    def get_daily_recirc_loss_kbtu(self):
        """
        Return total daily recirculation heat loss [kBTU].

        Returns
        -------
        float
        """
        pass

    def simulate_step(self, building, timestep_min, mode="normal"):
        """Run one timestep, including recirculation return flow into tank."""
        pass
