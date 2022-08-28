
.. _user_guide:

User Guide
==========

In this document we describe how to use the PyEnSight APIs to control
an EnSight post-processing instance.

API Differences
---------------

There are a few differences between the EnSight Python and and the
PyEnSight API.  Generally, the 'ensight' module in EnSight and the
Session.ensight class instance have the same interface.  Most
source code written against that API will run in both environment.

Free ENS_GROUP Objects
^^^^^^^^^^^^^^^^^^^^^^

In EnSight, the following is legal::

    group = ensight.objs.core.create_group()

This is not legal in PyEnSight as the target object ('group') does not exist
in the EnSight session.  In general, methods that create fre ENS_GROUP
objects have been removed from the PyEnSight API.

Object Class Specialization
^^^^^^^^^^^^^^^^^^^^^^^^^^^

In EnSight, ENS_PART proxy objects are used for all part types. Model,
Clip and Iso-contours are all of class ENS_PART.  In PyEnSight,
model parts are ENS_PART_MODEL class and clips are ENS_PART_CLIP class.
These are both subclasses of ENS_PART in PyEnSight.  This mechanism
applies to ENS_PART, ENS_ANNOT and ENS_TOOL.

ENS_PART.get_values()
^^^^^^^^^^^^^^^^^^^^^

The ENS_PART get_values() method does not properly generate numpy
arrays for the remote stream.  For the present, the method cannot
be called directly.  It is possible to run the command by running
more of the method remotely::

    shape = session.cmd("ensight.objs.core.PARTS[0].get_values(['Coordinates'])['Coordinates'].shape")
    s = session.cmd("ensight.objs.core.PARTS[0].get_values(['Coordinates'])['Coordinates'].tostring()")
    array = numpy.frombuffer(s, dtype=numpy.float32).reshape(shape)
