from .DHWSystem import DHWSystem


class InstantWHSystem(DHWSystem):
    """
    Instantaneous (tankless) water heater system.
    No storage — the heater must supply demand in real time.
    """

    def __init__(self, water_heaters, supply_temp_f, storage_temp_f):
        """
        Parameters
        ----------
        water_heaters : list[WaterHeater]
        supply_temp_f : float
        storage_temp_f : float
        """
        super().__init__(water_heaters, storage_tank=None,
                         supply_temp_f=supply_temp_f, storage_temp_f=storage_temp_f)

    def size(self, building):
        """
        Size an instantaneous system: capacity must cover peak instantaneous demand.

        Parameters
        ----------
        building : Building
        """
        pass

    def simulate_step(self, building, timestep_min, mode="normal"):
        """Instantaneous systems satisfy demand directly without tank draw."""
        pass
