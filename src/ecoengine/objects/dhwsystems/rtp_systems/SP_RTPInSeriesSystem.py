from .SinglePassRTPSystem import SinglePassRTPSystem


class SP_RTPInSeriesSystem(SinglePassRTPSystem):
    """
    Single-pass RTP system where the recirculation return is fed in series
    (back into the inlet of the primary heat pump).
    """

    def size(self, building):
        """
        Size an SP RTP in-series system.

        Parameters
        ----------
        building : Building
        """
        pass

    def simulate_step(self, building, timestep_min, mode="normal"):
        """Run one timestep for an SP RTP in-series system."""
        pass
