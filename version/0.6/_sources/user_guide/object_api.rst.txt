.. _ref_object_api:

EnSight object API
==================

The object interface directly exposes core EnSight objects using *proxy* Python objects
that hold references to the underlying C++ objects. These proxy objects can be used to
get or set attributes on the C++ objects as well as call methods on them. The object
interface has a number of advantages over the native interface.

- Attributes support the event callback mechanism. This makes it possible to
  register callbacks in Python that are executed when a specific set of attributes
  change on a single object or a class of objects.
- The interface supports the specification of objects via name, ID, or object. This helps
  remove ambiguity and adds flexibility when passing things like parts.
- In general, the object API does not necessitate the use of stored state, meaning
  the command language's *currently selected parts* notion. The API provides access
  to and the ability to change the state for interoperability with the native API,
  but it does not require its use.

Proxy objects: ``ENSOBJ`` class
-------------------------------

The object interface revolves around proxy object classes. The base class for these
objects is the ``ENSOBJ`` class. The object is a wrapper around an EnSight
object ID. An EnSight object ID is a monotonically increasing 64-bit integer, unique for a
given EnSight session. The proxy object stores the object ID in the :samp:`objid` object and
can make method and attribute calls directly on the C++ core objects via that ID. The
``ENSOBJ`` interface supports attribute introspection, including attribute names, types, and
general organization. In most cases where an attribute takes an object, the API supports
objects, descriptions, and IDs, making transition between the various APIs fairly seamless.
For example, the Python bindings search the variable list for names and IDs if
those types are provided::

    part = session.objs.core.PARTS["Clip"][0]
    var = session.ensight.objs.core.VARIABLES["temperature"][0]
    print(var, var.DESCRIPTION, var.ID)
    # The COLORBYPALETTE attribute is defined as being a ENS_VAR object.
    # It is legal to pass the object, the object name or the object ID.
    p.COLORBYPALETTE = var
    p.COLORBYPALETTE = var.DESCRIPTION
    p.COLORBYPALETTE = var.ID


Interface root: ``ensight.objs`` module
---------------------------------------

The session ``ensight.objs`` module serves as the access point into the object interface.
All other EnSight objects can be accessed from methods and objects in this
module. Key modules and objects include ``ensight.objs.enums`` (enumerations used for
attribute IDs and values) and all proxy object base classes (such as the
``ensight.objs.ENS_VAR`` class). There are also methods for searching for objects
and manipulating object IDs.


Global state: ``ensight.objs.core`` object
------------------------------------------

Access to the global state of the EnSight session is stored in an ``ENS_GLOBALS`` singleton object
accessed by the :samp:`session.ensight.objs.core` object. All other object instances can be
accessed through attributes or methods on this object. For example, ``ENS_PART`` objects can
be accessed via the ``PARTS`` property, and ``ENS_VAR`` objects can be accessed via the
``VARIABLES`` property.


Attributes
----------

The state of all objects is stored as a collection of attributes on the object.
There are a collection of methods for accessing attributes. Here is an example::

    p = session.ensight.objs.core.PARTS[0]
    p.DESCRIPTION = "HELLO"
    p.setattr("DESCRIPTION", "HELLO")
    p.setattr(session.ensight.objs.enums.DESCRIPTION, "HELLO")
    p.setattrs(dict(DESCRIPTION="HELLO"))


Attribute names may be specified using string names or enumerations. There are multiple
interfaces to get or set attributes. You can use the :func:`attrinfo<ansys.api.pyensight.ens_annot.ENS_ANNOT.attrinfo>`
method or the  :func:`attrtree<ansys.api.pyensight.ens_annot.ENS_ANNOT.attrtree>`
method to access detailed information about an attribute. Descriptions of attributes
are available in multiple languages, which can be selected via the :samp:`Session.language`
property.

One nuance to the attribute interface is that all object attributes are lists. Thus,
while an attribute like :samp:`COLORBYPALETTE` is a single variable object, it is always
returned as a list.

Finally, objects are always returned as ``ensobjlist`` instances. This is a subclass
of a Python list object that includes extra methods for searching via ``'[]'``
indexing and the :func:`find<ansys.pyensight.core.ensobjlist.find>` method as well as
calls to get or set attribute values in bulk on all the objects in the container.

It is also possible to create user-defined attributes. These may hold simple
values, string, integers, or floats. They are stored in the ``METADATA`` attribute,
but they behave the same as intrinsic attributes.

Events
------

Whenever an attribute changes its value, an event is generated. Callback functions
can be attached to these events. Thus, a PyEnSight app can respond to changes
in state caused by Python calls or intrinsic changes in the EnSight core state (such
as a time-varying animation playback). Here is a simple example that connects the
``part_event()`` function to any changes in the ``VISIBLE`` or ``COLORBYRGB`` properties
on any ``ENS_PART`` subclass object::

    def part_event(uri: str):
        p = urlparse(uri)
        q = parse_qs(p.query)
        obj = session.ensight.objs.wrap_id(int(q["uid"][0]))
        value = obj.getattr(q["enum"][0])
        part_disp.value = f"Part: {obj}, Attribute: {q['enum'][0]} Value: {value}"

    attribs = [session.ensight.objs.enums.VISIBLE, session.ensight.objs.enums.COLORBYRGB]
    session.add_callback("'ENS_PART'", "partattr", attribs, part_event)


Replacing the ``ENS_PART`` string with a specific ``ENSOBJ`` instance would limit the
function to the one specific object instance rather than a class of objects.


Selection and the native API
----------------------------

Unlike the native API, the object API does not require a "current selection" as
the target of all operations is explicit. The object API supports SELECTED attributes
and selection group objects. These directly represent the state of the EnSight GUI.
In cases where one would like to use both APIs in a single script, it can become
necessary to synchronize these two selections. See: :ref:`selection_transfer` for details
on how this can be done.


Tips and tricks
---------------

You can access an additional collection of EnSight-specific Python notes in the
`Python and EnSight documentation <https://nexusdemo.ensight.com/docs/python/html/Python.html>`_.
