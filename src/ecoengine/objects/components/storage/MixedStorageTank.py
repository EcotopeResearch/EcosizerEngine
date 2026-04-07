from .StorageTank import StorageTank


class MixedStorageTank(StorageTank):
    """
    Fully-mixed (uniform temperature) storage tank model.
    Inherits the StorageTank interface but models the tank as a single
    temperature node rather than a stratified profile.
    """

    def __init__(self, total_volume_gal):
        """
        Parameters
        ----------
        total_volume_gal : float
            Total physical tank volume [gallons].
        """
        super().__init__(total_volume_gal, num_nodes=1)
        self._temp_f = None  # single mixed temperature

    def initialize(self, storage_temp_f, cold_temp_f, percent_useable):
        """Set initial mixed temperature as a blend of hot and cold fractions."""
        pass

    def get_temperature_at_fraction(self, fract):
        """Return uniform temperature regardless of height fraction."""
        pass

    def get_usable_volume_supplyT_gal(self, supply_temp_f):
        """Return full tank volume if above supply temp, else 0."""
        pass

    def draw(self, volume_supplyT_gal, cold_temp_f):
        """Draw hot water and mix in cold water, updating the uniform temperature."""
        pass

    def heat(self, kbtuh, duration_min, supply_temp_f):
        """Raise the uniform tank temperature by the heat added this timestep."""
        pass
