DHW Systems
===========

All system classes share the base :class:`~ecoengine.objects.dhwsystems.DHWSystem.DHWSystem`
interface. Subclasses add recirc-loop or return-to-primary logic as needed.

Base class
----------

.. autoclass:: ecoengine.objects.dhwsystems.DHWSystem.DHWSystem
   :members:
   :special-members: __init__

No-recirc systems
-----------------

.. autoclass:: ecoengine.objects.dhwsystems.InstantWHSystem.InstantWHSystem
   :members:

.. autoclass:: ecoengine.objects.dhwsystems.MPNoRecircSystem.MPNoRecircSystem
   :members:

Recirculation systems
---------------------

.. autoclass:: ecoengine.objects.dhwsystems.recirc_systems.RecircSystem.RecircSystem
   :members:

.. autoclass:: ecoengine.objects.dhwsystems.recirc_systems.SwingSystem.SwingSystem
   :members:

.. autoclass:: ecoengine.objects.dhwsystems.recirc_systems.SwingERTrdOffSystem.SwingERTrdOffSystem
   :members:

.. autoclass:: ecoengine.objects.dhwsystems.recirc_systems.ParallelLoopSystem.ParallelLoopSystem
   :members:

Return-to-Primary (RTP) systems
--------------------------------

.. autoclass:: ecoengine.objects.dhwsystems.rtp_systems.RTPSystem.RTPSystem
   :members:

.. autoclass:: ecoengine.objects.dhwsystems.rtp_systems.SinglePassRTPSystem.SinglePassRTPSystem
   :members:

.. autoclass:: ecoengine.objects.dhwsystems.rtp_systems.MultiPassRTPSystem.MultiPassRTPSystem
   :members:

.. autoclass:: ecoengine.objects.dhwsystems.rtp_systems.SP_RTPInParallelSystem.SP_RTPInParallelSystem
   :members:

.. autoclass:: ecoengine.objects.dhwsystems.rtp_systems.SP_RTPInSeriesSystem.SP_RTPInSeriesSystem
   :members:

.. autoclass:: ecoengine.objects.dhwsystems.rtp_systems.MP_RTPInSeriesSystem.MP_RTPInSeriesSystem
   :members:
