from .RecircSystem import RecircSystem


class ParallelLoopSystem(RecircSystem):
    """
    Parallel loop system: a separate temperature-maintenance (TM) tank sits in
    parallel with the primary storage tank. The TM tank handles recirc losses;
    the primary tank handles DHW demand.

    Sizing computes both primary and TM system requirements.
    """

    def __init__(
        self,
        water_heaters,
        storage_tank,
        supply_temp_f,
        storage_temp_f,
        return_temp_f,
        return_flow_gpm,
        tm_storage_tank=None,
        tm_water_heaters=None,
        tm_safety_factor=1.0,
    ):
        """
        Parameters
        ----------
        water_heaters : list[WaterHeater]
            Primary system heaters.
        storage_tank : StorageTank
            Primary storage tank.
        supply_temp_f : float
        storage_temp_f : float
        return_temp_f : float
        return_flow_gpm : float
        tm_storage_tank : StorageTank, optional
            Temperature-maintenance storage tank.
        tm_water_heaters : list[WaterHeater], optional
            Temperature-maintenance heaters.
        tm_safety_factor : float
            Multiplier applied to TM sizing result.
        """
        super().__init__(
            water_heaters, storage_tank, supply_temp_f, storage_temp_f,
            return_temp_f, return_flow_gpm,
        )
        self.tm_storage_tank = tm_storage_tank
        self.tm_water_heaters = tm_water_heaters or []
        self.tm_safety_factor = tm_safety_factor

    def size(self, building):
        """
        Size both the primary and TM systems.

        Parameters
        ----------
        building : Building
        """
        pass

    def size_tm_system(self, building):
        """
        Size the temperature-maintenance system based on recirculation losses.

        Parameters
        ----------
        building : Building
        """
        pass

    def simulate_step(self, building, timestep_min, mode="normal"):
        """Run one timestep for a parallel loop system, stepping both primary and TM."""
        pass
