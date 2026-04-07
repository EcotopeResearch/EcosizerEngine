from ..DHWSystem import DHWSystem


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
        storage_temp_f : float
        return_temp_f : float
            Temperature of recirculation return water [°F].
        return_flow_gpm : float
            Recirculation loop flow rate [GPM].
        """
        super().__init__(water_heaters, storage_tank, supply_temp_f, storage_temp_f)
        self.return_temp_f = return_temp_f
        self.return_flow_gpm = return_flow_gpm

    def _calc_required_capacity(self, building):
        """
        Override: add daily recirc-loss BTUs to DHW-use BTUs before dividing
        by daily run hours.

        Parameters
        ----------
        building : Building

        Returns
        -------
        float
        """
        pass

    def get_recirc_loss_kbtuh(self):
        """
        Return the steady-state recirculation heat loss rate [kBTU/hr].

        Returns
        -------
        float
        """
        pass
