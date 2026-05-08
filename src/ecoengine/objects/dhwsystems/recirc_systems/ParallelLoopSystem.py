from __future__ import annotations

from ecoengine.objects.components.heating.Controls import Controls
from ecoengine.objects.components.heating.WaterHeater import WaterHeater
from ecoengine.objects.components.storage.StorageTank import StorageTank
from ecoengine.objects.components.storage.StratifiedTank import StratifiedTank
from ecoengine.objects.components.storage.MixedStorageTank import MixedStorageTank
from .RecircSystem import RecircSystem
from ecoengine.constants.constants import _RHO_CP
from ecoengine.objects.building.Building import Building

# Minimum recommended TM heater run time per cycle [hr].
# Below this, short cycling risk is high (mirrors original constant).
_TM_MIN_RUNTIME_HR: float = 20.0 / 60.0   # 20 minutes


class ParallelLoopSystem(RecircSystem):
    """
    Parallel loop system: a separate temperature-maintenance (TM) tank sits in
    parallel with the primary storage tank.

    * Primary tank  — stratified StorageTank, sized for DHW demand only.
    * TM tank       — MixedStorageTank, sized to absorb recirc loop losses.

    The two tanks operate completely independently each timestep.

    Construction
    ------------
    Use the factory classmethod rather than calling __init__ directly::

        system = ParallelLoopSystem.from_size(
            building        = building,
            supply_temp_f   = 120.0,
            storage_temp_f  = 150.0,
            return_temp_f   = 110.0,
            return_flow_gpm = 3.0,
            tm_on_temp_f    = 115.0,
            tm_off_temp_f   = 120.0,
        )
    """

    def __init__(
        self,
        water_heaters,
        storage_tank,
        supply_temp_f: float,
        storage_temp_f: float,
        return_temp_f: float,
        return_flow_gpm: float,
        tm_on_temp_f: float,
        tm_off_temp_f: float,
        tm_off_time_hr: float = 0.5,
        tm_safety_factor: float = 1.2,
        tm_storage_tank=None,
        tm_water_heater=None,
        num_tm_heaters: int = 1,
        max_daily_run_hr: float = 24.0,
        defrost_factor: float = 1.0,
    ):
        """
        Parameters
        ----------
        water_heaters : list[WaterHeater]
            Primary system heaters.
        storage_tank : StorageTank | None
            Primary storage tank (None during intermediate construction).
        supply_temp_f : float
            DHW delivery temperature [°F].
        storage_temp_f : float
            Primary hot water storage setpoint [°F].
        return_temp_f : float
            Temperature of water returning from the recirculation loop [°F].
        return_flow_gpm : float
            Recirculation loop flow rate [GPM].
        tm_on_temp_f : float
            TM tank turn-on temperature — element fires when tank drops to this [°F].
        tm_off_temp_f : float
            TM tank turn-off temperature — element shuts off when tank reaches this [°F].
        tm_off_time_hr : float
            Maximum allowed off-cycle duration for the TM heater [hr].
            The TM tank volume is sized so the tank cools from tm_off_temp_f to
            tm_on_temp_f in exactly this much time under recirc loss alone.
            Must be > 0 and <= 1.0. Default 0.5.
        tm_safety_factor : float
            Multiplier applied to the recirc loss rate when sizing TM capacity.
            Must be > 1.0. Default 1.2.
        tm_storage_tank : MixedStorageTank | None
            TM storage tank (populated by from_size() or size()).
        tm_water_heater : WaterHeater | None
            TM heater representing a single unit (populated by from_size() or size()).
        num_tm_heaters : int
            Number of identical TM heater units. Output from tm_water_heater is
            multiplied by this before being applied to tank heating and recorded.
            Default 1.
        max_daily_run_hr : float
            Maximum hours the primary heating system may run per day.
        defrost_factor : float
            Fraction of rated capacity available after defrost (0–1).
        """
        super().__init__(
            water_heaters,
            storage_tank,
            supply_temp_f,
            storage_temp_f,
            return_temp_f,
            return_flow_gpm,
            max_daily_run_hr=max_daily_run_hr,
            defrost_factor=defrost_factor,
        )
        self.tm_on_temp_f    = tm_on_temp_f
        self.tm_off_temp_f   = tm_off_temp_f
        self.tm_off_time_hr  = tm_off_time_hr
        self.tm_safety_factor = tm_safety_factor
        self.tm_storage_tank  = tm_storage_tank
        self.tm_water_heater  = tm_water_heater
        self.num_tm_heaters   = num_tm_heaters

        # TM sizing results — populated by size_tm_system()
        self._minimum_tm_volume_gal:    float | None = None
        self._minimum_tm_capacity_kbtuh: float | None = None

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
        tm_on_temp_f: float,
        tm_off_temp_f: float,
        tm_off_time_hr: float = 0.5,
        tm_safety_factor: float = 1.2,
        num_tm_heaters: int = 1,
        max_daily_run_hr: float = 24.0,
        defrost_factor: float = 1.0,
        control_schedule=None,
        control_map=None,
        strat_slope: float = 2.8,
        load_shift_fract_total_vol: float = 1.0,
    ) -> ParallelLoopSystem:
        """
        Size the system for the given building, then build it.

        Parameters
        ----------
        building : Building
        supply_temp_f : float
        storage_temp_f : float
        return_temp_f : float
            Temperature of the recirculation loop return water [°F].
        return_flow_gpm : float
            Recirculation loop flow rate [GPM].
        tm_on_temp_f : float
            TM element turn-on temperature [°F].
        tm_off_temp_f : float
            TM element turn-off temperature [°F].
        tm_off_time_hr : float
            Max TM heater off-cycle duration [hr]. Default 0.5.
        tm_safety_factor : float
            TM capacity safety multiplier (must be > 1.0). Default 1.2.
        num_tm_heaters : int
            Number of identical TM heater units. The total sized TM capacity is
            divided by this to get per-unit capacity; simulate_step scales back
            by num_tm_heaters. Default 1.
        max_daily_run_hr : float
            Max primary heater run time per day. Default 24.0.
        defrost_factor : float
            Primary heater defrost derating (0–1). Default 1.0.
        control_schedule : list[str] | None
        control_map : dict[str, Controls] | None
        strat_slope : float

        Returns
        -------
        ParallelLoopSystem
        """
        system = cls(
            water_heaters=[],
            storage_tank=None,
            supply_temp_f=supply_temp_f,
            storage_temp_f=storage_temp_f,
            return_temp_f=return_temp_f,
            return_flow_gpm=return_flow_gpm,
            tm_on_temp_f=tm_on_temp_f,
            tm_off_temp_f=tm_off_temp_f,
            tm_off_time_hr=tm_off_time_hr,
            tm_safety_factor=tm_safety_factor,
            num_tm_heaters=num_tm_heaters,
            max_daily_run_hr=max_daily_run_hr,
            defrost_factor=defrost_factor,
        )
        system.size(
            building,
            control_schedule=control_schedule,
            control_map=control_map,
            strat_slope=strat_slope,
            load_shift_fract_total_vol=load_shift_fract_total_vol,
        )

        # Build primary components
        system.storage_tank = StratifiedTank(
            total_volume_gal=system._minimum_storage_storageT_gal,
            strat_slope=strat_slope,
        )
        system.water_heaters = [WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=system._minimum_capacity_kbtuh,
            control_schedule=control_schedule,
            control_map=control_map,
        )]

        # Build TM components
        system.tm_storage_tank = MixedStorageTank(
            total_volume_gal=system._minimum_tm_volume_gal,
        )
        tm_controls = Controls(
            on_sensor_fract  = 0.5,   # center — irrelevant for fully-mixed tank
            on_trigger_t_f   = tm_on_temp_f,
            off_sensor_fract = 0.5,
            off_trigger_t_f  = tm_off_temp_f,
            outlet_temp_f    = tm_off_temp_f,
        )
        system.tm_water_heater = WaterHeater.from_nominal_capacity(
            nominal_capacity_kbtuh=system._minimum_tm_capacity_kbtuh / system.num_tm_heaters,
            control_schedule=["normal"] * 24,
            control_map={"normal": tm_controls},
        )

        return system

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_tm_inputs(self) -> None:
        """Raise ValueError if TM parameters are physically inconsistent."""
        if self.tm_safety_factor <= 1.0:
            raise ValueError(
                "tm_safety_factor must be > 1.0. The TM heater must be able to "
                "outpace recirc losses over a full cycle."
            )
        if not (0 < self.tm_off_time_hr <= 1.0):
            raise ValueError(
                "tm_off_time_hr must be > 0 and <= 1.0 hour."
            )
        if self.tm_off_temp_f <= self.tm_on_temp_f:
            raise ValueError(
                "tm_off_temp_f must be greater than tm_on_temp_f."
            )
        expected_runtime_hr = self.tm_off_time_hr / (self.tm_safety_factor - 1.0)
        if _TM_MIN_RUNTIME_HR >= expected_runtime_hr:
            raise ValueError(
                f"Expected TM heater runtime ({expected_runtime_hr * 60:.1f} min) is below "
                f"the recommended minimum ({_TM_MIN_RUNTIME_HR * 60:.0f} min). "
                f"Increase tm_off_time_hr or tm_safety_factor."
            )

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------

    def size(
        self,
        building,
        control_schedule=None,
        control_map=None,
        strat_slope: float = 2.8,
        load_shift_fract_total_vol: float = 1.0,
    ) -> None:
        """
        Size both the primary DHW system and the TM system.

        Primary sizing uses the standard DHWSystem max-deficit algorithm.
        TM sizing uses recirc loss rate, off-time, and safety factor.
        """
        self._validate_tm_inputs()
        # Primary sizing (DHWSystem.size() via RecircSystem which doesn't override it)
        super().size(
            building,
            control_schedule=control_schedule,
            control_map=control_map,
            strat_slope=strat_slope,
            load_shift_fract_total_vol=load_shift_fract_total_vol,
        )
        # TM sizing
        self.size_tm_system()

    def size_tm_system(self) -> None:
        """
        Size the temperature-maintenance tank and heater from recirc loss parameters.

        Formulas
        --------
        TM volume:
            The tank must hold enough thermal mass that during a full off-cycle
            (tm_off_time_hr) it cools from tm_off_temp_f to tm_on_temp_f while
            losing heat at the steady recirc loss rate:

                TMVol_gal = (recirc_loss_btuhr / rhoCp)
                            * (tm_off_time_hr / (tm_off_temp_f − tm_on_temp_f))

        TM capacity:
            Must outpace the recirc loss by the safety factor:

                TMCap_kbtuh = safety_factor × recirc_loss_kbtuh
        """
        recirc_loss_btuhr = self.get_recirc_loss_kbtuh() * 1000.0
        self._minimum_tm_volume_gal = (
            (recirc_loss_btuhr / _RHO_CP)
            * (self.tm_off_time_hr / (self.tm_off_temp_f - self.tm_on_temp_f))
        )
        self._minimum_tm_capacity_kbtuh = self.tm_safety_factor * recirc_loss_btuhr / 1000.0

    # ------------------------------------------------------------------
    # Sizing result accessors
    # ------------------------------------------------------------------

    def get_minimum_tm_volume_gal(self) -> float:
        if self._minimum_tm_volume_gal is None:
            raise RuntimeError("size() must be called before get_minimum_tm_volume_gal().")
        return self._minimum_tm_volume_gal

    def get_minimum_tm_capacity_kbtuh(self) -> float:
        if self._minimum_tm_capacity_kbtuh is None:
            raise RuntimeError("size() must be called before get_minimum_tm_capacity_kbtuh().")
        return self._minimum_tm_capacity_kbtuh

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def simulate_step(
        self,
        building : Building,
        timestep_interval: int,
        interval_min: int = 1,
        mode: str = "normal",
    ) -> dict:
        """
        Execute one simulation timestep for the parallel loop system.

        Delegates the entire primary system step to DHWSystem.simulate_step()
        via super(), then layers on the TM system (recirc loss → heater response)
        and merges the energy outputs into the returned dict.

        Primary system (via super())
        -----------------------------
        1. Query building for demand, OAT, and inlet water temperature.
        2. Update primary WaterHeater states; apply heat to StratifiedTank.
        3. Draw DHW demand; measure usable volume and tank temperature profile.

        TM system (parallel, independent)
        -----------------------------------
        4. Apply recirc loop heat loss to MixedStorageTank via add_recirc_return().
        5. Update TM WaterHeater state; heat TM tank if active.

        The recirc loop connects only to the TM tank — the primary StratifiedTank
        receives no recirc return flow.

        Parameters
        ----------
        building : Building
        timestep_interval : int
        interval_min : int
        mode : str
            Ignored — operating mode determined by each heater's control schedule.

        Returns
        -------
        dict
            Same keys as DHWSystem.simulate_step(). heater_output_kbtuh and
            heater_power_in_kw include both primary and TM heater contributions.
        """
        # Run primary system: super() → RecircSystem → DHWSystem
        step = super().simulate_step(building, timestep_interval, interval_min, mode)

        # ------------------------------------------------------------------
        # TM system — recirc loss applied first, then heater responds
        # ------------------------------------------------------------------
        hour_of_day = (timestep_interval * interval_min // 60) % 24
        oat_f       = step["oat_f"]

        self.tm_storage_tank.add_recirc_return(
            self.return_flow_gpm, self.return_temp_f, interval_min
        )

        self.tm_water_heater.update_state(self.tm_storage_tank, hour_of_day)

        tm_top_temp_f   = self.tm_storage_tank.get_temperature_at_fraction(1.0)
        tm_inlet_temp_f = (self.tm_off_temp_f + self.tm_on_temp_f) / 2.0
        tm_kbtuh        = self.tm_water_heater.get_output_kbtuh(oat_f, tm_top_temp_f, tm_inlet_temp_f) * self.num_tm_heaters
        tm_kw_per_unit  = (
            self.tm_water_heater.get_power_in_kw(oat_f, tm_top_temp_f, tm_inlet_temp_f)
            if self.tm_water_heater.is_active()
            else None
        )
        tm_kw = tm_kw_per_unit * self.num_tm_heaters if tm_kw_per_unit is not None else None
        self.tm_storage_tank.heat(tm_kbtuh, interval_min, self.tm_off_temp_f)

        # ------------------------------------------------------------------
        # Merge TM outputs into primary step dict
        # ------------------------------------------------------------------
        # heater_output_kbtuh stays PRIMARY-ONLY (used for gal/hr plot in top chart).
        # TM thermal output is tracked separately in tm_heater_output_kbtuh.
        # heater_power_in_kw merges both so get_total_energy_kwh() is accurate.
        # if tm_kw is not None:
        #     step["heater_power_in_kw"] = (step["heater_power_in_kw"] or 0.0) + tm_kw

        # TM panel data (consumed by SimulationRun for the TM subplot)
        step["tm_tank_temp_f"]         = self.tm_storage_tank.get_temperature_at_fraction(0.5)
        step["tm_heater_output_kbtuh"] = tm_kbtuh
        step["tm_heater_input_kw"]     = tm_kw
        print(f'{step["tm_heater_input_kw"]}, {step["tm_tank_temp_f"] }, {step["tm_heater_output_kbtuh"]}')
        return step
