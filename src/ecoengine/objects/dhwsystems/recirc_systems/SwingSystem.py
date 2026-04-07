from .RecircSystem import RecircSystem


class SwingSystem(RecircSystem):
    """
    Swing tank system: a single tank serves as both primary storage and
    temperature-maintenance (TM) volume. The tank "swings" between supply
    temperature and storage temperature.

    Sizing uses the same maximum-deficit method as the base class but also
    simulates how much water the swing tank pulls from storage during each
    peak period.
    """

    def __init__(
        self,
        water_heaters,
        storage_tank,
        supply_temp_f,
        storage_temp_f,
        return_temp_f,
        return_flow_gpm,
        tm_safety_factor=1.0,
    ):
        """
        Parameters
        ----------
        water_heaters : list[WaterHeater]
        storage_tank : StorageTank
        supply_temp_f : float
        storage_temp_f : float
        return_temp_f : float
        return_flow_gpm : float
        tm_safety_factor : float
            Multiplier applied to the TM sizing result for additional margin.
        """
        super().__init__(
            water_heaters, storage_tank, supply_temp_f, storage_temp_f,
            return_temp_f, return_flow_gpm,
        )
        self.tm_safety_factor = tm_safety_factor

    def size(self, building):
        """
        Size the swing tank system, including TM volume based on recirc losses.

        Parameters
        ----------
        building : Building
        """
        pass

    def _calc_running_volume_supplyT_gal(self, building, capacity_kbtuh):
        """
        Override: simultaneously simulate swing-tank draw while computing
        the maximum DHW deficit.

        Parameters
        ----------
        building : Building
        capacity_kbtuh : float

        Returns
        -------
        float
            Running volume [gallons at supply temperature].
        """
        pass

    def simulate_step(self, building, timestep_min, mode="normal"):
        """Run one timestep for a swing tank system."""
        pass
