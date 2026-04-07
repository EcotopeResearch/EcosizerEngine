from .SinglePassRTPSystem import SinglePassRTPSystem


class SP_RTPInParallelSystem(SinglePassRTPSystem):
    """
    Single-pass RTP system where the recirculation return is fed in parallel
    (mixed into the tank rather than routed through the heat pump inlet).
    """

    def size(self, building):
        """
        Size an SP RTP in-parallel system.

        Parameters
        ----------
        building : Building
        """
        pass

    def simulate_step(self, building, timestep_min, mode="normal"):
        """Run one timestep for an SP RTP in-parallel system."""
        pass
