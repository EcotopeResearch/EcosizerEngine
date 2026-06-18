from __future__ import annotations

from typing import TYPE_CHECKING

from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.storage.MixedStorageTank import MixedStorageTank
from ecoengine.objects.components.storage.StratifiedTank import StratifiedTank
from ecoengine.objects.dhwsystems.DHWSystem import DHWSystem
from ecoengine.constants.constants import _RHO_CP, _W_TO_KBTUH
from ecoengine.objects.dhwsystems.utils import (
    mixing_valve_behavior,
    mixing_valve_behavior_swing,
    size_supplemental_heating_and_storage,
    gas_backup_from_window,
    get_ashrae_sizing_curve,
    plot_ashrae_sizing_curve,
)
from .SwingSystem import SwingSystem, _ELEMENT_DEADBAND_F

if TYPE_CHECKING:
    from ecoengine.objects.building.Building import Building


class _SwingDualFuelPrimary(DHWSystem):
    """
    Sizing proxy used exclusively inside SwingDualFuelSystem._size_supplemental().

    Wraps the primary HPWH and primary StratifiedTank in a plain DHWSystem so
    that ``size_supplemental_heating_and_storage`` can simulate primary-only
    behavior and identify worst-case peak-demand outage windows.  Does not
    reference SwingDualFuelSystem.
    """

    def __init__(
        self,
        water_heaters: list,
        storage_tank,
        supply_temp_f: float,
        storage_temp_f: float,
        return_temp_f: float,
        return_flow_gpm: float,
        max_daily_run_hr: float = 24.0,
        defrost_factor: float = 1.0,
    ) -> None:
        super().__init__(
            water_heaters=water_heaters,
            storage_tank=storage_tank,
            supply_temp_f=supply_temp_f,
            storage_temp_f=storage_temp_f,
            max_daily_run_hr=max_daily_run_hr,
            defrost_factor=defrost_factor,
        )
        self.return_temp_f   = return_temp_f
        self.return_flow_gpm = return_flow_gpm
        self.swing_tank_temp_f = supply_temp_f

    def get_recirc_loss_kbtuh(self) -> float:
        return (
            self.return_flow_gpm
            * (self.supply_temp_f - self.return_temp_f)
            * _RHO_CP
            * 60.0
            / 1000.0
        )

    def simulate_step(
        self,
        building: Building,
        timestep_interval: int,
        interval_min: int = 1,
        mode: str = "normal",
    ) -> dict:
        use_avg = any(wh.is_load_shifting() for wh in self.water_heaters)
        demand_supplyT_gal = building.get_dhw_load_supplyT_gal(
            timestep_interval, interval_min, use_avg=use_avg
        )
        oat_f         = building.get_oat_f(timestep_interval, interval_min)
        inlet_temp_f  = building.get_inlet_water_temp_f(timestep_interval, interval_min)
        hour_of_day   = (timestep_interval * interval_min // 60) % 24
        outlet_temp_f = self._get_outlet_temp_f(hour_of_day)

        for wh in self.water_heaters:
            wh.update_state(self.storage_tank, hour_of_day)

        total_kbtuh = sum(
            wh.get_output_kbtuh(oat_f, wh.get_outlet_temp_f(hour_of_day), inlet_temp_f)
            for wh in self.water_heaters
        )

        self.storage_tank.heat(total_kbtuh, interval_min, outlet_temp_f)
        avg_tank_temp_for_draw_f = self.storage_tank.get_average_draw_temp_f(demand_supplyT_gal)

        result = mixing_valve_behavior_swing(
            demand_supplyT_gal,
            self.return_flow_gpm * interval_min,
            inlet_temp_f,
            self.supply_temp_f,
            self.return_temp_f,
            self.swing_tank_temp_f,
            avg_tank_temp_for_draw_f,
        )

        self.swing_tank_temp_f = result["inlet_temp_f"]
        self.storage_tank.draw_physical_gal(
            result["cold_load_to_storage_gal"], inlet_temp_f, self.supply_temp_f
        )

        return {
            "draw_thru_system_gal": result["storage_draw_gal"],
            "swing_inlet_temp_f" : self.swing_tank_temp_f
        }


class SwingDualFuelSystem(SwingSystem):
    """
    Swing tank system with a supplemental gas swing tank sized via the ASHRAE method.

    The primary HPWH and primary storage are sized the same way as a standard
    SwingSystem.  The swing tank (``tm_storage_tank``) and its element
    (``tm_water_heater``) are then re-sized using a peak-aligned 2-day
    simulation via ``size_supplemental_heating_and_storage``, replacing the
    simple table-lookup result from ``_size_tm_system()``.

    Construction
    ------------
    Use the factory classmethod::

        system = SwingDualFuelSystem.from_size(
            building         = building,
            supply_temp_f    = 120.0,
            storage_temp_f   = 150.0,
            return_temp_f    = 110.0,
            return_flow_gpm  = 3.0,
            tm_safety_factor = 1.2,
        )
    """

    outage_volume_gal:   list[float]
    outage_temp_delta_f: list[float]

    # ------------------------------------------------------------------
    # Factory constructor
    # ------------------------------------------------------------------

    @classmethod
    def from_size(
        cls,
        building: Building,
        supply_temp_f: float,
        storage_temp_f: float,
        return_temp_f: float,
        return_flow_gpm: float,
        nominal_capacity_kbtuh: float,
        nominal_storage_gal: float,
        tm_safety_factor: float = 1.2,
        max_daily_run_hr: float = 24.0,
        defrost_factor: float = 1.0,
        control_schedule: list[str] | None = None,
        control_map: dict[str, Controls] | None = None,
        strat_slope: float = 2.8,
        load_shift_fract_total_vol: float = 1.0,
    ) -> SwingDualFuelSystem:
        """
        Size the primary SwingSystem, cap it at the caller-supplied nominal
        specs, then size the supplemental swing tank via the ASHRAE method.

        The full SwingSystem sizing is always run first so that
        ``_size_tm_system`` populates ``_minimum_tm_volume_gal`` and
        ``_minimum_tm_capacity_kbtuh`` for the internal swing-tank simulation
        used during primary capacity calculation.  The actual primary HPWH and
        StratifiedTank are then built at the (typically smaller) nominal values,
        creating a deliberate shortfall that the supplemental swing tank covers.

        Parameters
        ----------
        building : Building
        supply_temp_f : float
            DHW delivery temperature [°F].
        storage_temp_f : float
            Primary storage setpoint [°F].
        return_temp_f : float
            Recirculation loop return temperature [°F].
        return_flow_gpm : float
            Recirculation loop flow rate [GPM].
        nominal_capacity_kbtuh : float
            Primary HPWH heating capacity ceiling [kBTU/hr].
        nominal_storage_gal : float
            Primary storage tank volume ceiling [gal at storageT].
        tm_safety_factor : float
            Multiplier on recirc loss for TM element capacity. Must be > 1.0.
        max_daily_run_hr : float
            Maximum hours the primary heater may run per day. Default 24.
        defrost_factor : float
            Fraction of rated capacity available after defrost (0–1). Default 1.0.
        control_schedule : list[str] | None
            24-element list of control-map keys.
        control_map : dict[str, Controls] | None
            Controls objects keyed by schedule label.
        strat_slope : float
            Stratification slope [°F/%-height] for primary tank sizing.
        load_shift_fract_total_vol : float
            Demand scaling factor for load-shift sizing (0–1). Default 1.0.

        Returns
        -------
        SwingDualFuelSystem
        """
        system = cls(
            water_heaters=[],
            storage_tank=None,
            supply_temp_f=supply_temp_f,
            storage_temp_f=storage_temp_f,
            return_temp_f=return_temp_f,
            return_flow_gpm=return_flow_gpm,
            tm_safety_factor=tm_safety_factor,
            max_daily_run_hr=max_daily_run_hr,
            defrost_factor=defrost_factor,
        )

        # Step 1: Run full SwingSystem sizing so _size_tm_system populates
        # _minimum_tm_volume_gal/_minimum_tm_capacity_kbtuh for _sim_just_swing.
        system.size(
            building,
            control_schedule=control_schedule,
            control_map=control_map,
            strat_slope=strat_slope,
            load_shift_fract_total_vol=load_shift_fract_total_vol,
        )

        # Step 2: Build primary components capped at the caller-supplied nominal
        # specs (deliberately undersized relative to the full swing sizing).
        system.storage_tank = StratifiedTank(
            total_volume_gal=nominal_storage_gal,
            strat_slope=strat_slope,
        )
        system.water_heaters = [WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=nominal_capacity_kbtuh,
            control_schedule=control_schedule,
            control_map=control_map,
        )]

        # Step 3: Build an initial swing tank (same controls as SwingSystem.from_size)
        # so the proxy has a fully-initialized tm_storage_tank during the ASHRAE sizing.
        tm_controls = Controls(
            on_sensor_fract  = 0.5,
            on_trigger_t_f   = supply_temp_f,
            off_sensor_fract = 0.5,
            off_trigger_t_f  = supply_temp_f + _ELEMENT_DEADBAND_F,
            outlet_temp_f    = supply_temp_f + _ELEMENT_DEADBAND_F,
        )
        system.tm_storage_tank = MixedStorageTank(
            total_volume_gal=system._minimum_tm_volume_gal,
        )
        system.tm_water_heater = WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=system._minimum_tm_capacity_kbtuh,
            control_schedule=["normal"] * 24,
            control_map={"normal": tm_controls},
        )

        # Step 4: Re-size swing tank and element via the ASHRAE method,
        # replacing the table-lookup results from Step 3.
        system._size_supplemental(
            building=building,
            tm_controls=tm_controls,
            nominal_capacity_kbtuh=nominal_capacity_kbtuh,
        )

        return system

    # ------------------------------------------------------------------
    # Supplemental sizing
    # ------------------------------------------------------------------

    def _size_supplemental(
        self,
        building: Building,
        tm_controls: Controls,
        nominal_capacity_kbtuh: float,
    ) -> None:
        """
        Re-size ``tm_storage_tank`` and ``tm_water_heater`` via the ASHRAE
        peak-aligned 2-day method, replacing the table-lookup result.

        A ``_SwingDualFuelPrimary`` proxy is created from the current system
        state (primary HPWH + primary StratifiedTank) and passed to
        ``size_supplemental_heating_and_storage`` as the primary system.  The
        sizing function simulates the primary-only behavior and records outage
        volume and temperature-deficit arrays, which are then used to size the
        supplemental swing tank at the default 30-minute ASHRAE window.

        Parameters
        ----------
        building : Building
        tm_controls : Controls
            Controls for the supplemental swing tank element (on at supply_temp,
            off at supply_temp + deadband).
        nominal_capacity_kbtuh : float
            Primary HPWH capacity ceiling [kBTU/hr]; used to identify peak-demand
            hours for the sizing simulation.

        Raises
        ------
        ValueError
            If the primary system is already adequate (outage <= 10 min and
            max deficit <= 2 °F), meaning no supplemental swing tank is needed.
        """
        _WINDOW_MIN = 30

        proxy = _SwingDualFuelPrimary(
            water_heaters=self.water_heaters,
            storage_tank=self.storage_tank,
            supply_temp_f=self.supply_temp_f,
            storage_temp_f=self.storage_temp_f,
            return_temp_f=self.return_temp_f,
            return_flow_gpm=self.return_flow_gpm,
            max_daily_run_hr=self.max_daily_run_hr,
            defrost_factor=self.defrost_factor,
        )

        self.outage_volume_gal, self.outage_temp_delta_f = (
            size_supplemental_heating_and_storage(
                primary_system=proxy,
                building=building,
                nominal_capacity_kbtuh=nominal_capacity_kbtuh,
                temperature_variable="swing_inlet_temp_f"
            )
        )

        tm_capacity_kbtuh, tm_storage_vol_gal = gas_backup_from_window(
            self.outage_volume_gal, self.outage_temp_delta_f, _WINDOW_MIN
        )

        self.tm_storage_tank = MixedStorageTank(total_volume_gal=tm_storage_vol_gal)
        self.tm_water_heater = WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=tm_capacity_kbtuh,
            control_schedule=["normal"] * 24,
            control_map={"normal": tm_controls},
        )

    # ------------------------------------------------------------------
    # Supplemental sizing curve
    # ------------------------------------------------------------------

    def get_sizing_curve(self) -> dict:
        """
        Return the supplemental swing tank sizing curve as a data dict.

        Keys: ``"window_sizes"``, ``"capacities_kbtuh"``, ``"storages_gal"``,
        ``"recommended_index"``.  Pass to ``plot_sizing_curve()`` for a figure.

        Raises
        ------
        RuntimeError
            If ``from_size()`` has not been called yet.
        """
        if not getattr(self, "outage_volume_gal", None):
            raise RuntimeError(
                "Supplemental outage data not available. Call from_size() first."
            )
        return get_ashrae_sizing_curve(self.outage_volume_gal, self.outage_temp_delta_f)

    def plot_sizing_curve(
        self,
        title: str = "Supplemental Swing Tank Sizing Curve — Dual Fuel Swing",
    ) -> "plotly.graph_objects.Figure":
        """
        Return a Plotly sizing-curve figure for the supplemental swing tank.

        Parameters
        ----------
        title : str
            Figure title.

        Returns
        -------
        plotly.graph_objects.Figure

        Raises
        ------
        RuntimeError
            If ``from_size()`` has not been called yet.
        """
        return plot_ashrae_sizing_curve(self.get_sizing_curve(), title=title)

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def simulate_step(
        self,
        building: Building,
        timestep_interval: int,
        interval_min: int = 1,
        mode: str = "normal",
    ) -> dict:
        """
        Execute one simulation timestep for the dual-fuel swing tank system.

        The primary HPWH heats the primary StratifiedTank.  Water is drawn
        through the swing tank (``tm_storage_tank``) via a mixing valve before
        delivery to the building.  The supplemental TM element maintains the
        swing tank at or above supply temperature.
        """
        # --- 1. Building data ---
        use_avg = any(wh.is_load_shifting() for wh in self.water_heaters)
        demand_supplyT_gal = building.get_dhw_load_supplyT_gal(
            timestep_interval, interval_min, use_avg=use_avg
        )
        oat_f        = building.get_oat_f(timestep_interval, interval_min)
        inlet_temp_f = building.get_inlet_water_temp_f(timestep_interval, interval_min)
        hour_of_day  = (timestep_interval * interval_min // 60) % 24
        outlet_temp_f = self._get_outlet_temp_f(hour_of_day)
        step_mode = (
            self.water_heaters[0].control_schedule[hour_of_day]
            if self.water_heaters and self.water_heaters[0].control_schedule
            else "normal"
        )

        # --- 2. Primary heater: update state and heat primary tank ---
        for wh in self.water_heaters:
            wh.update_state(self.storage_tank, hour_of_day)

        primary_kbtuh = sum(
            wh.get_output_kbtuh(oat_f, wh.get_outlet_temp_f(hour_of_day), inlet_temp_f)
            for wh in self.water_heaters
        )
        primary_kw_list = [
            wh.get_power_in_kw(oat_f, wh.get_outlet_temp_f(hour_of_day), inlet_temp_f)
            for wh in self.water_heaters
            if wh.is_active()
        ]
        primary_kw: float | None = (
            sum(kw or 0.0 for kw in primary_kw_list) if primary_kw_list else None
        )
        self.storage_tank.heat(primary_kbtuh, interval_min, outlet_temp_f)

        # --- 3. Mixing valve: determine draw from primary and swing tank contribution ---
        swing_t = self.tm_storage_tank.get_temperature_at_fraction(0.5)
        preliminary_result = mixing_valve_behavior(
            demand_supplyT_gal,
            self.return_flow_gpm * interval_min,
            inlet_temp_f,
            self.supply_temp_f,
            self.return_temp_f,
            swing_t,
        )
        primary_feed_temp_f = self.storage_tank.get_average_draw_temp_f(
            preliminary_result["cold_load_to_storage_gal"]
        )
        result = mixing_valve_behavior_swing(
            demand_supplyT_gal,
            self.return_flow_gpm * interval_min,
            inlet_temp_f,
            self.supply_temp_f,
            self.return_temp_f,
            swing_t,
            primary_feed_temp_f,
        )

        # --- 4. Mix primary inflow into swing tank ---
        self.tm_storage_tank.mix_primary_inflow(result["storage_draw_gal"], result["inlet_temp_f"])

        # --- 5. TM element: update state and heat swing tank ---
        self.tm_water_heater.update_state(self.tm_storage_tank, hour_of_day)
        tm_ctrl     = self.tm_water_heater.get_controls_for_hour(hour_of_day)
        tm_outlet_f = tm_ctrl.off_trigger_t_f
        tm_kbtuh    = self.tm_water_heater.get_output_kbtuh(oat_f, tm_outlet_f)
        tm_kw_val   = (
            self.tm_water_heater.get_power_in_kw(oat_f, tm_outlet_f)
            if self.tm_water_heater.is_active()
            else None
        )
        self.tm_storage_tank.heat(tm_kbtuh, interval_min, tm_outlet_f)

        # --- 6. Draw computed volume from primary storage ---
        self.storage_tank.draw_physical_gal(
            result["cold_load_to_storage_gal"], inlet_temp_f, self.supply_temp_f
        )

        # --- 7. Usable volume ---
        if swing_t < self.supply_temp_f:
            usable_vol_gal = 0.0
        else:
            usable_vol_gal = self.storage_tank.get_usable_volume_supplyT_gal(
                self.supply_temp_f
            )

        # --- 8. Tank temperature profile (primary stratified tank) ---
        tank_temps_f = [
            self.storage_tank.get_temperature_at_fraction(f)
            for f in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        ]

        # heater_output_kbtuh is PRIMARY-ONLY (used for gal/hr plot in top chart).
        # heater_power_in_kw merges both so get_total_energy_kwh() is accurate.
        total_kw: float | None = (primary_kw or 0.0) if primary_kw is not None or tm_kw_val is not None else None
        swing_mid_temp_f = self.tm_storage_tank.get_temperature_at_fraction(0.5)
        return {
            "demand_supplyT_gal":        demand_supplyT_gal,
            "usable_volume_supplyT_gal": usable_vol_gal,
            "heater_output_kbtuh":       primary_kbtuh,
            "heater_power_in_kw":        total_kw,
            "oat_f":                     oat_f,
            "inlet_water_temp_f":        inlet_temp_f,
            "tank_temps_f":              tank_temps_f,
            "mode":                      step_mode,
            # Swing tank is the actual delivery point — its temperature drives
            # the outlet-deficit early-stop check.
            "delivery_temp_f":           swing_mid_temp_f,
            # TM panel data (consumed by SimulationRun for the swing-tank subplot)
            "tm_tank_temp_f":            swing_mid_temp_f,
            "tm_heater_output_kbtuh":    tm_kbtuh,
            "tm_heater_input_kw":        tm_kbtuh / _W_TO_KBTUH,
        }
