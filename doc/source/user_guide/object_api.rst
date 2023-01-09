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

EnSight Object Interface Overview
---------------------------------

WIP
