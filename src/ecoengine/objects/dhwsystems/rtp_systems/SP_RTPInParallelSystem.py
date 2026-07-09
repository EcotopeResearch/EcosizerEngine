from __future__ import annotations

from typing import TYPE_CHECKING

from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.storage.EnergyTank import EnergyTank
from ecoengine.constants.constants import _RHO_CP, _W_TO_KBTUH
from ..utils import (
    mixing_valve_behavior,
    size_supplemental_heating_and_storage,
    gas_backup_from_window,
    get_ashrae_sizing_curve,
    plot_ashrae_sizing_curve,
    set_dual_fuel_shed_controls,
)
from .SinglePassRTPSystem import SinglePassRTPSystem, _SPRTP_STRAT_SLOPE

if TYPE_CHECKING:
    from ecoengine.objects.building.Building import Building


def _gas_capacity_from_peak_deficit(
    outage_volume_gal: list[float],
    outage_temp_delta_f: list[float],
) -> float:
    """
    Return the gas backup capacity [kBTU/hr] needed to cover the single
    worst-minute heat deficit in the outage arrays.

    Unlike ``gas_backup_from_window`` (which sizes a downstream storage
    buffer by averaging over an ASHRAE window), the gas heater here has no
    buffer of its own -- it heats directly into the shared primary tank --
    so it must be able to cover the worst single minute directly:
    ``outage_volume_gal[i]`` gallons raised ``outage_temp_delta_f[i]``
    degrees, for whichever minute ``i`` makes that the largest.

    Parameters
    ----------
    outage_volume_gal : list[float]
        Per-minute demand during primary outage (0 outside outage) [gal].
    outage_temp_delta_f : list[float]
        Per-minute temperature deficit during outage (0 outside) [°F].

    Returns
    -------
    float
        Gas backup capacity [kBTU/hr]. 0.0 if the arrays are empty.
    """
    if not outage_volume_gal:
        return 0.0
    return max(
        _RHO_CP * v * 60.0 * d / 1000.0
        for v, d in zip(outage_volume_gal, outage_temp_delta_f)
    )


class SP_RTPInParallelSystem(SinglePassRTPSystem):
    """
    Single-pass RTP system with a supplementary gas water heater connected to the primary storage tank in addition to the heat pumps.

    The primary HPWH (EnergyTank + WaterHeater) is intentionally capped at
    caller-supplied nominal specs.  ``gas_water_heater`` heats directly into
    that same primary tank (no storage buffer of its own) and is sized to
    cover the single worst-minute heat deficit observed while running the
    undersized primary alone.

    Construction
    ------------
    Use the factory classmethod rather than calling __init__ directly::

        system = SP_RTPInParallelSystem.from_size(
            building               = building,
            supply_temp_f          = 120.0,
            storage_temp_f         = 150.0,
            return_temp_f          = 110.0,
            return_flow_gpm        = 3.0,
            nominal_capacity_kbtuh = 50.0,
            nominal_storage_gal    = 200.0,
        )
    """

    gas_water_heater: WaterHeater
    outage_volume_gal: list[float]
    outage_temp_delta_f: list[float]

    # ------------------------------------------------------------------
    # Factory constructor
    # ------------------------------------------------------------------

    @classmethod
    def from_size(
        cls,
        building,
        supply_temp_f: float,
        storage_temp_f: float,
        return_temp_f: float,
        return_flow_gpm: float,
        nominal_capacity_kbtuh: float,
        nominal_storage_gal: float,
        max_daily_run_hr: float = 16.0,
        defrost_factor: float = 1.0,
        tm_safety_factor: float = 1.0,
        control_schedule: list[str] | None = None,
        control_map: dict[str, Controls] | None = None,
        strat_slope: float = _SPRTP_STRAT_SLOPE,
        load_shift_fract_total_vol: float = 1.0, # TODO make sure this is applied to LS dual fuel models
    ) -> SP_RTPInParallelSystem:
        """
        Size the system for the given building, then build it.

        The primary HPWH is capped at ``nominal_capacity_kbtuh`` and
        ``nominal_storage_gal``; the gas backup is sized to cover the
        remainder via ``_size_gas_backup``.

        Parameters
        ----------
        building : Building
        supply_temp_f : float
            DHW delivery temperature [°F].
        storage_temp_f : float
            Hot water storage setpoint [°F].
        return_temp_f : float
            Recirculation loop return temperature [°F].
        return_flow_gpm : float
            Recirculation loop flow rate [GPM].
        nominal_capacity_kbtuh : float
            Primary HPWH heating capacity ceiling [kBTU/hr].
        nominal_storage_gal : float
            Primary storage tank volume ceiling [gal at storageT].
        max_daily_run_hr : float
            Maximum hours the primary heater may run per day. Default 16.
        defrost_factor : float
            Fraction of rated capacity available after defrost (0–1). Default 1.0.
        control_schedule : list[str] | None
            24-element list of control keys. None for no load-shifting.
        control_map : dict[str, Controls] | None
            Controls objects keyed by schedule label.
        strat_slope : float
            Temperature gradient [°F per %-height] for stratification factor.
        load_shift_fract_total_vol : float
            Demand scaling factor for load-shift sizing (0–1). Default 1.0.

        Returns
        -------
        SP_RTPInParallelSystem
        """
        # ensure shed turns primary system completely off
        control_map = set_dual_fuel_shed_controls(control_map)

        system = cls(
            water_heaters=[],
            storage_tank=None,
            supply_temp_f=supply_temp_f,
            storage_temp_f=storage_temp_f,
            return_temp_f=return_temp_f,
            return_flow_gpm=return_flow_gpm,
            max_daily_run_hr=max_daily_run_hr,
            defrost_factor=defrost_factor,
            tm_safety_factor=tm_safety_factor,
        )

        system._minimum_capacity_kbtuh = nominal_capacity_kbtuh
        system._minimum_storage_storageT_gal = nominal_storage_gal

        # Primary HPWH: capped at caller-provided nominal specs
        system.storage_tank = EnergyTank(
            total_volume_gal=nominal_storage_gal,
            cold_temp_f=building.get_design_inlet_water_temp_f(),
            storage_temp_f=storage_temp_f,
            strat_slope=strat_slope,
        )
        system.water_heaters = [WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=nominal_capacity_kbtuh,
            control_schedule=control_schedule,
            control_map=control_map,
        )]

        # Gas backup controls: on at supply_temp, off at supply_temp + deadband
        gas_controls = Controls(
            on_sensor_fract=0.8,
            on_trigger_t_f=supply_temp_f,
            off_sensor_fract=0.4,
            off_trigger_t_f=supply_temp_f + 5.0,
            outlet_temp_f=storage_temp_f,
        )
        system._size_gas_backup(
            building=building,
            nominal_capacity_kbtuh=nominal_capacity_kbtuh,
            nominal_storage_gal=nominal_storage_gal,
            gas_controls=gas_controls,
        )
        return system

    # ------------------------------------------------------------------
    # Gas backup sizing
    # ------------------------------------------------------------------

    def _size_gas_backup(
        self,
        building,
        nominal_capacity_kbtuh: float,
        nominal_storage_gal: float,
        gas_controls: Controls,
    ) -> None:
        """
        Size gas_water_heater by simulating 2 days as a plain
        SinglePassRTPSystem (undersized primary only), then sizing gas
        capacity to cover the single worst-minute heat deficit observed.

        Unlike SP_RTPInSeriesSystem, there is no downstream gas storage tank
        here -- the gas heater feeds the shared primary tank directly -- so
        capacity is not derived from an ASHRAE window average. See
        ``_gas_capacity_from_peak_deficit`` for the sizing formula.

        Parameters
        ----------
        building : Building
        nominal_capacity_kbtuh : float
            Primary HPWH capacity ceiling [kBTU/hr].
        nominal_storage_gal : float
            Primary storage volume ceiling [gal at storageT].
        gas_controls : Controls
            Controls for the gas backup water heater.

        Raises
        ------
        ValueError
            If the primary SPRTP is already adequately sized (outage < 10 min
            and max deficit < 2 °F), meaning no gas backup is needed.
        """
        # --- 1 & 2. Sizing simulation → outage arrays (raises ValueError if no backup needed) ---
        self.outage_volume_gal, self.outage_temp_delta_f = size_supplemental_heating_and_storage(
            primary_system=self,
            building=building,
            nominal_capacity_kbtuh=nominal_capacity_kbtuh,
        )

        # --- 3. Size gas capacity to cover the single worst-minute deficit ---
        gas_capacity_kbtuh = _gas_capacity_from_peak_deficit(
            self.outage_volume_gal, self.outage_temp_delta_f
        )
        # TODO add thermal efficiency

        self.gas_water_heater = WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=gas_capacity_kbtuh,
            control_schedule=["normal"] * 24,
            control_map={"normal": gas_controls},
        )

    # ------------------------------------------------------------------
    # Gas backup sizing helpers
    # ------------------------------------------------------------------

    def get_sizing_curve(
        self,
        building: Building,
        strat_slope: float = 2.8,
        step: float = 0.25,
    ) -> dict:
        """
        TODO: revisit. Sizing is now a single peak-deficit capacity value
        rather than an ASHRAE window/storage trade-off, so there is no curve
        to compute yet.

        ``building``, ``strat_slope``, and ``step`` are accepted for call-
        signature parity with ``DHWSystem.get_sizing_curve()`` but have no
        effect here.
        """
        pass

    def plot_sizing_curve(
        self,
        title: str = "Gas Backup Sizing Curve — SP RTP In-Parallel",
    ) -> "plotly.graph_objects.Figure":
        """
        TODO: revisit. See ``get_sizing_curve``.
        """
        pass

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def simulate_step(
        self,
        building,
        timestep_interval: int,
        interval_min: int = 1,
        mode: str = "normal",
    ) -> dict:
        """
        Run one timestep for a single-pass RTP system.

        Delegates the DHW draw and heater logic to the base class, then
        applies recirculation losses to the storage tank.  The recirc
        return flow cools the bottom of the tank every minute, reducing
        usable volume.  The returned dict is updated to reflect post-recirc
        tank state.
        """
        if not hasattr(self, "gas_water_heater"):
            return SinglePassRTPSystem.simulate_step(
                self, building, timestep_interval, interval_min, mode
            )
        use_avg = any(wh.is_load_shifting() for wh in self.water_heaters)
        demand_supplyT_gal = building.get_dhw_load_supplyT_gal(
            timestep_interval, interval_min, use_avg=use_avg
        )

        oat_f          = building.get_oat_f(timestep_interval, interval_min)
        inlet_temp_f   = building.get_inlet_water_temp_f(timestep_interval, interval_min)
        hour_of_day    = (timestep_interval * interval_min // 60) % 24
        outlet_temp_f  = self._get_outlet_temp_f(hour_of_day)
        mode = (
            self.water_heaters[0].control_schedule[hour_of_day]
            if self.water_heaters and self.water_heaters[0].control_schedule
            else "normal"
        )

        draw_gal = 0.0
        self.storage_tank.update_cold_temp_f(inlet_temp_f)
        # Update on/off state for each heater based on current tank condition
        for wh in self.water_heaters:
            wh.update_state(self.storage_tank, hour_of_day)
        self.gas_water_heater.update_state(self.storage_tank, hour_of_day)
        # Apply heating from all active heaters to the tank
        total_kbtuh    = sum(
            wh.get_output_kbtuh(oat_f, wh.get_outlet_temp_f(hour_of_day), inlet_temp_f)
            for wh in self.water_heaters
        )
        gas_outlet_temp_f = self.gas_water_heater.get_controls_for_hour(hour_of_day).outlet_temp_f
        gas_kbtuh = self.gas_water_heater.get_output_kbtuh(oat_f, gas_outlet_temp_f, inlet_temp_f)
        total_kw: float | None = None
        active_kws = [
            wh.get_power_in_kw(oat_f, wh.get_outlet_temp_f(hour_of_day), inlet_temp_f)
            for wh in self.water_heaters
            if wh.is_active()
        ]
        # TODO track gas use
        if any(kw is not None for kw in active_kws):
            total_kw = sum(kw or 0.0 for kw in active_kws)

        self.storage_tank.heat(total_kbtuh, interval_min, outlet_temp_f)
        self.storage_tank.heat(gas_kbtuh, interval_min, gas_outlet_temp_f)
        top_temp_f     = self.storage_tank.get_temperature_at_fraction(1.0)

        # --- Mixing valve draw ---
        flow_per_min_gal = self.return_flow_gpm * interval_min
        result = mixing_valve_behavior(
            demand_supplyT_gal,
            flow_per_min_gal,
            inlet_temp_f,
            self.supply_temp_f,
            self.return_temp_f,
            top_temp_f,
        )
        draw_gal       = result["storage_draw_gal"]
        mv_inlet_temp_f = result["inlet_temp_f"]

        self.storage_tank.draw_physical_gal(draw_gal, mv_inlet_temp_f, update_internal_cold_temp = False)

        usable_vol_gal = self.storage_tank.get_usable_volume_supplyT_gal(
            self.supply_temp_f
        )
        tank_temps_f = [
            self.storage_tank.get_temperature_at_fraction(f)
            for f in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        ]

        return {
            "demand_supplyT_gal":        demand_supplyT_gal,
            "usable_volume_supplyT_gal": usable_vol_gal,
            "heater_output_kbtuh":       total_kbtuh,
            "heater_power_in_kw":        total_kw,
            "oat_f":                     oat_f,
            "inlet_water_temp_f":        inlet_temp_f,
            "tank_temps_f":              tank_temps_f,
            "mode":                      mode,
            "tm_heater_output_kbtuh":    gas_kbtuh,
            "tm_heater_input_kw":        gas_kbtuh / _W_TO_KBTUH,
            "draw_thru_system_gal":      draw_gal,
        }