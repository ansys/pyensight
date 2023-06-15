.. _api_differences:

Python API Differences in Ensight versus PyEnSight
==================================================

There are a few differences between the EnSight Python API and the
PyEnSight API. Generally, the ``ensight`` module in EnSight and the
``Session.ensight`` class instance have the same interface. Most
source code written against this API runs in both environment.

Free ``ENS_GROUP`` objects
^^^^^^^^^^^^^^^^^^^^^^^^^^

In EnSight, the following code is legal::

    group = ensight.objs.core.create_group()


This code is not legal in PyEnSight because the target object (*group*) does not exist
in the EnSight session. In general, methods that create free ``ENS_GROUP``
objects have been removed from the PyEnSight API.

Object class specialization
^^^^^^^^^^^^^^^^^^^^^^^^^^^

In EnSight, ``ENS_PART`` proxy objects are used for all part types. Model,
Clip and Iso-contours are all of the ``ENS_PART`` class. In PyEnSight,
model parts are of the ``ENS_PART_MODEL`` class and clips are of the
``ENS_PART_CLIP`` class. These are both subclasses of PyEnSight's ``ENS_PART``
class. This mechanism applies to ``ENS_PART``, ``ENS_ANNOT``, and ``ENS_TOOL``
classes.
