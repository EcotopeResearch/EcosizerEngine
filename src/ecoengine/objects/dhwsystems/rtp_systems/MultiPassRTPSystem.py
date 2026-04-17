from .RTPSystem import RTPSystem


class MultiPassRTPSystem(RTPSystem):
    """
    Multi-pass Return-to-Primary system.

    Running volume is determined using the "growing slug" method: the algorithm
    assumes a tank with infinite volume and accumulates a slug of water from DHW
    use and recirc return until the system heats that water to storage temperature.
    """

    def size(self, building):
        """
        Size a multi-pass RTP system using the growing-slug method.

        Parameters
        ----------
        building : Building
        """
        pass

    def _calc_running_volume_supplyT_gal(self, building, capacity_kbtuh):
        """
        Override: growing-slug method for running volume determination.

        Parameters
        ----------
        building : Building
        capacity_kbtuh : float

        Returns
        -------
        float
            Running volume [gallons at supply temperature].
        """

        ################
        # Algorithm idea:
        # 0) size capacity for high like 9 hr or as high as you can
        # 1) find peak and simulate on that peak, assume incoming water = amount of supply water used (at supply temp) + recirc (at return temp)
        # 2) applying heat to it SHOULD NOT be able to keep up because its a peak
        # 3) deficit not met is running vol at supply temp
        ################
        pass

    def simulate_step(self, building, timestep_min, mode="normal"):
        """Run one timestep for a multi-pass RTP system.""" 
        pass
