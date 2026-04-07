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
        pass

    def simulate_step(self, building, timestep_min, mode="normal"):
        """Run one timestep for a multi-pass RTP system."""
        pass
