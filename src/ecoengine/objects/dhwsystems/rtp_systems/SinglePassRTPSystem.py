from .RTPSystem import RTPSystem


class SinglePassRTPSystem(RTPSystem):
    """
    Single-pass Return-to-Primary system.

    Water passes through the heat pump once per heating cycle. Running volume
    uses the standard maximum-deficit method with recirc losses added to capacity.
    """

    def size(self, building):
        """
        Size a single-pass RTP system.

        Parameters
        ----------
        building : Building
        """
        pass

    def simulate_step(self, building, timestep_min, mode="normal"):
        """Run one timestep for a single-pass RTP system."""
        pass
