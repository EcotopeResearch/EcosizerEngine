Simulation
==========

SimulationRun
-------------

:class:`~ecoengine.objects.simulation.SimulationRun.SimulationRun` accumulates
per-timestep outputs and provides summary, cost, and plotting methods.

.. autoclass:: ecoengine.objects.simulation.SimulationRun.SimulationRun
   :members:
   :special-members: __init__

Simulator
---------

Module-level functions that drive the simulation loop.

.. autofunction:: ecoengine.interfaces.Simulator.simulate
.. autofunction:: ecoengine.interfaces.Simulator.simulate_3day
.. autofunction:: ecoengine.interfaces.Simulator.simulate_annual
