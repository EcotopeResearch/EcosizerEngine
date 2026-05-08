EcosizerEngine (Top-Level API)
==============================

The :class:`~ecoengine.interfaces.EcosizerEngine.EcosizerEngine` class is the
primary public interface. All sizing, simulation, and result-retrieval methods
are accessed through it.

Module-level convenience functions are also re-exported from the top-level
``ecoengine`` package.

EcosizerEngine class
--------------------

.. autoclass:: ecoengine.interfaces.EcosizerEngine.EcosizerEngine
   :members:
   :special-members: __init__

Module-level functions
----------------------

.. autofunction:: ecoengine.interfaces.EcosizerEngine.get_oat_buckets
.. autofunction:: ecoengine.interfaces.EcosizerEngine.get_list_of_models
.. autofunction:: ecoengine.interfaces.EcosizerEngine.get_weather_stations
.. autofunction:: ecoengine.interfaces.EcosizerEngine.get_hpwh_output_capacity
.. autofunction:: ecoengine.interfaces.EcosizerEngine.get_sizing_curve_plot
.. autofunction:: ecoengine.interfaces.EcosizerEngine.get_annual_utility_comparison_graph
