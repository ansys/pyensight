.. _ref_object_api:

EnSight Object API
==================

The object interface directly exposes core EnSight objects using "proxy" Python objects
that hold references to the underlying C++ objects.  These proxy objects ca be used to
get/set attributes on the C++ objects as well as call methods on them.  The object
interface has a number of advantages over the native interface.  Attributes support
the event callback mechanism.  This makes it possible to register callbacks in Python
that are executed when a specific set of attributes change on a single or a class of objects.
The interface supports the specification of objects via name, id or object.  This helps
remove ambiguity and adds flexibility when passing things like parts, etc.  In general,
the object API does not necessitate the use of stored state (e.g. the command language
"currently selected parts" notion).  The API provides access to and the ability to
change the state (for interoperability with the native API), but is does not require it.

Proxy Objects: ENSOBJ Class
---------------------------

The object interface revolves around proxy object classes. The base class for these
objects is :class:`ENSOBJ<pyensight.ensobj.ENSOBJ>`.  The object is a wrapper around an EnSight
object ID.  An EnSight object ID is a monotonically increasing 64bit integer, unique for a
given EnSight session.  The proxy object stores the object ID in :samp:`__objid__` and
can make method and attribute calls directly on the C++ core objects via that ID.  The
ENSOBJ interface supports attribute introspection including attribute names, types and
general organization.  In most cases where an attribute takes an object, the API supports
objects, descriptions or IDs, making transition between the various APIs fairly seamless.
For example, the Python bindings will search the variable list for names and IDs if
those types are provided::

    part = session.objs.core.PARTS["Clip"][0]
    var = session.ensight.objs.core.VARIABLES["temperature"][0]
    print(var, var.DESCRIPTION, var.ID)
    # The COLORBYPALETTE attribute is defined as being a ENS_VAR object.
    # It is legal to pass the object, the object name or the object ID.
    p.COLORBYPALETTE = var
    p.COLORBYPALETTE = var.DESCRIPTION
    p.COLORBYPALETTE = var.ID


Interface Root: ensight.objs
----------------------------

The session ensight.objs module serves as access point into the object interface.
All other EnSight objects can be accessed from methods and objects in this
module.  Key modules and objects include ensight.objs.enums (enums used for
attribute IDs and values) and all of the proxy object base classes (e.g., ensight.objs.ENS_VAR).
There are also methods for searching for objects and manipulating object ids.


Global State: ensight.objs.core
-------------------------------

Access to the global state of the EnSight session is stored in an ENS_GLOBALS singleton object
accessed by:  :samp:`session.ensight.objs.core`.  All other object instances can be
accessed through attributes or methods on this object.


Attributes
----------

The state of all objects is stored as a collection of attributes on the object.
There are a collection of methods for accessing attributes.  For example::

    p = session.ensight.objs.core.PARTS[0]
    p.DESCRIPTION = "HELLO"
    p.setattr("DESCRIPTION", "HELLO")
    p.setattr(session.ensight.objs.enums.DESCRIPTION, "HELLO")
    p.setattrs(dict(DESCRIPTION="HELLO"))

Attribute names may be specified using string names or enums and there are multiple
interfaces to get/set attributes.  Detailed information about an attribute can be
accessed via attrinfo() and attrtree().   Descriptions of attributes are available in
multiple languages which can be selected via the :samp:`session.language` property.

One nuance to the attribute interface, all object attributes are lists.  Thus,
attributes like :samp:`COLORBYPALETTE`, while a single variable object is always
returned as a list.  Finally, the objects are always returned as
:class:`ensobjlist<pyensight.ensobjlist>` instances. This is a subclass of a
Python list object that includes extra methods for searching via '[]' indexing and
a find() method as well as calls to get/set attribute values in bulk on all the
objects in the container.  See:

It is also possible to create user-defined attributes.  These may hold simple
values, string, integers or floats.  They are stored in the METADATA attribute,
but behave the same as intrinsic attributes.


Events
------

Whenever an attribute changes its value, an event is generated.  Callback functions
can be attached to these events.  Thus a PyEnSight application can respond to changes
in state caused by Python calls or intrinsic changes in the EnSight core state. For
example time-varying animation playback.


Tips and Tricks
---------------

Finally, an additional collection of EnSight specific Python notes are accessible via the
`EnSight Python <https://nexusdemo.ensight.com/docs/python/html/Python.html>`_ website.
