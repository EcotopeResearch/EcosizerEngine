Quick Start
===========

Installation
------------

.. code-block:: bash

   pip install ecoengine

Basic Usage
-----------

The main entry point is :class:`~ecoengine.EcosizerEngine`. Construct it
with building and system parameters, call :meth:`~ecoengine.interfaces.EcosizerEngine.EcosizerEngine.build`,
:meth:`~ecoengine.interfaces.EcosizerEngine.EcosizerEngine.size`, and then run a
simulation.

.. code-block:: python

   from ecoengine import EcosizerEngine

   engine = EcosizerEngine(
       building_type            = "multi_family",
       magnitude                = 100,          # units
       zip_code_or_climate_zone = "94103",       # San Francisco zip
       supply_temp_f            = 120.0,
       storage_temp_f           = 150.0,
       schematic                = "primary_no_recirc",
       num_heaters              = 2,
       hpwh_model               = "MODELS_ColmacCxV_5_C_SP",
   )

   engine.build()
   engine.size()

   # Inspect sizing results
   print(engine.get_sizing_results())

   # Run 3-day design-day simulation
   engine.simulate_3day()
   print(engine.get_simulation_summary())

   # Plot simulation output
   fig = engine.plot_simulation()
   fig.show()

Recirculation Systems
---------------------

For buildings with a recirculation loop, choose a recirc schematic and
provide the loop parameters:

.. code-block:: python

   engine = EcosizerEngine(
       building_type            = "multi_family",
       magnitude                = 200,
       zip_code_or_climate_zone = 3,             # CA climate zone ID
       supply_temp_f            = 120.0,
       storage_temp_f           = 150.0,
       schematic                = "swing_tank",
       return_temp_f            = 110.0,
       return_flow_gpm          = 4.0,
       num_heaters              = 3,
   )

   engine.build()
   engine.size()

Available Schematics
--------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - ``schematic``
     - Description
   * - ``primary_no_recirc``
     - Basic HPWH + stratified tank; no recirculation loop
   * - ``parallel_loop``
     - Separate temperature-maintenance (TM) tank in parallel for recirc losses
   * - ``swing_tank``
     - Swing-tank system; TM element in a small mixed tank in series
   * - ``single_pass_rtp``
     - Single-pass return-to-primary
   * - ``multi_pass_rtp``
     - Multi-pass return-to-primary
   * - ``instant_wh``
     - Instantaneous (tankless) water heater; no storage

Annual Simulation & Cost Analysis
----------------------------------

.. code-block:: python

   from ecoengine import EcosizerEngine
   from ecoengine.objects.building.UtilityCostTracker import UtilityCostTracker

   tracker = UtilityCostTracker(
       energy_rate_per_kwh = 0.18,
       demand_rate_per_kw  = 12.0,
   )

   engine = EcosizerEngine(
       building_type            = "multi_family",
       magnitude                = 100,
       zip_code_or_climate_zone = "94103",
       supply_temp_f            = 120.0,
       storage_temp_f           = 150.0,
       schematic                = "primary_no_recirc",
       utility_cost_tracker     = tracker,
   )

   engine.build()
   engine.size()
   engine.simulate_annual()

   print(engine.get_annual_cost_estimate())

Climate Zone Helpers
--------------------

.. code-block:: python

   from ecoengine import get_oat_buckets, get_weather_stations

   # OAT distribution for a zip code (used in MPRTP sizing)
   buckets = get_oat_buckets(zip_code="94103")

   # List available weather stations
   stations = get_weather_stations()
