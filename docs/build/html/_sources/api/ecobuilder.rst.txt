EcoBuilder (Component-by-Component API)
=======================================

:class:`~ecoengine.interfaces.EcoBuilder.EcoBuilder` builds a pre-sized
:class:`~ecoengine.objects.dhwsystems.DHWSystem.DHWSystem` from components the
caller defines: temperatures, tank volumes, recirc loop, performance maps,
controls and water heaters. No sizing is done, and the system's
``get_minimum_*()`` getters raise ``RuntimeError``.

Use it when each heater needs its own controls or schedule, which the flat
parameter set of :class:`~ecoengine.interfaces.EcosizerEngine.EcosizerEngine`
does not allow. Simulate the result with
:func:`~ecoengine.interfaces.Simulator.simulate_3day` or
:func:`~ecoengine.interfaces.Simulator.simulate_annual`.

``EcoBuilder`` is re-exported from the top-level ``ecoengine`` package.

EcoBuilder class
----------------

.. autoclass:: ecoengine.interfaces.EcoBuilder.EcoBuilder
   :members:
   :special-members: __init__
