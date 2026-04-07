from .MultiPassRTPSystem import MultiPassRTPSystem


class MP_RTPInSeriesSystem(MultiPassRTPSystem):
    """
    Multi-pass RTP system where the recirculation return is fed in series
    (back into the inlet of the primary heat pump).
    """

    def size(self, building):
        """
        Size an MP RTP in-series system.

        Parameters
        ----------
        building : Building
        """
        pass

    def simulate_step(self, building, timestep_min, mode="normal"):
        """Run one timestep for an MP RTP in-series system."""
        pass
