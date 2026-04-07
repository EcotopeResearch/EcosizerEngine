from .DHWSystem import DHWSystem


class MPNoRecircSystem(DHWSystem):
    """
    Multi-pass system with no recirculation loop.
    Water passes through the heat pump multiple times to reach storage temperature.
    """

    def __init__(self, water_heaters, storage_tank, supply_temp_f, storage_temp_f):
        """
        Parameters
        ----------
        water_heaters : list[WaterHeater]
        storage_tank : StorageTank
        supply_temp_f : float
        storage_temp_f : float
        """
        super().__init__(water_heaters, storage_tank, supply_temp_f, storage_temp_f)

    def size(self, building):
        """
        Size a multi-pass no-recirc system.

        Parameters
        ----------
        building : Building
        """
        pass

    def simulate_step(self, building, timestep_min, mode="normal"):
        """Run one timestep for a multi-pass no-recirc system."""
        pass
