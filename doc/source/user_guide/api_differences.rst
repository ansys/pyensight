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
Clip and Iso-contours are all of the ``ENS_PART`` class.  In PyEnSight,
model parts are of the ``ENS_PART_MODEL`` class and clips are of the
``ENS_PART_CLIP`` class. These are both subclasses of PyEnSight's ``ENS_PART``
class. This mechanism applies to ``ENS_PART``, ``ENS_ANNOT``, and ``ENS_TOOL``
classes.

``ENS_PART.get_values()`` method
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``ENS_PART get_values()`` method does not properly generate numpy
arrays for the remote stream. While this method cannot be called directly,
you can generate numpy arrays for the remote stream by using this coe::

    shape = session.cmd("ensight.objs.core.PARTS[0].get_values(['Coordinates'])['Coordinates'].shape")
    s = session.cmd("ensight.objs.core.PARTS[0].get_values(['Coordinates'])['Coordinates'].tostring()")
    array = numpy.frombuffer(s, dtype=numpy.float32).reshape(shape)


The EnSight (not PyEnSight) get_values method looks this::

    ENS_PART.get_values(variables: List[Any],
                        ids: List[int] = None,
                        use_nan: int = 0,
                        activate: int = 0) -> Dict


This method gets variable values for the variables specified in variables
on the part.

Args:
    variables:
        A list of variable references.  A mixture of ENS_VAR objects,
        variable names (string) or variable ids (integers).
    ids:
        This keyword can be used to restrict the output
        to a specific collection of element or node ids. If you restrict
        to a given list of ids and ids are not present then an empty
        dictionary will be returned. It is not possible to specify
        separate lists for both node and element ids, so the caller
        must separate these into two calls. Select your part in the
        part list and query the part.  The resulting dialog will
        tell you if you have ids and the ranges of the node and/or
        element ids.  This feature can also be used to "batch" the
        operation.
    use_nan:
        EnSight uses a specific value for the 'Undefined' value
        (ensight.Undefined), ``use_nan`` is set to 1, the API will
        return NumPy NaN values wherever this value would be returned.
    activate:
        By default, if a variable specified in ``variables`` is not active,
        this method will throw an exception.  If 1 is specified,
        any inactive variables will be activated as needed.
Returns:
    The returned value is a dictionary.  The keys to the dictionary
    are the objects passed in ``variables`` and the values are
    NumPy Float arrays.  For constants the value is a one dimensional
    array with a single value.  For other scalar variables, the value
    will be a 1D array of values (complex values are returned as
    NumPy complex types). For vector, tensor and Coordinate variables,
    a 2D array is returned.  The first dimension is the element or
    node count and the second dimension will be 3, 9 or 3 respectively
    Note: Tensor variables will always be expanded to 9 values when
    returned. If any nodal variables are returned, an additional
    key "NODAL_IDS" will be present and will contain a NumPy array
    of integers that are the EnSight node IDs for any returned node value.
    Similarly if any element variables are returned, "ELEMENT_IDS"
    will be present.  Note if the part does not have element or
    nodal ids then a list of [-1,-1,-1,....] will be returned.
    If the variable is a case constant, the value is returned.
    If the variable is a part constant, the value for this part
    is returned.
