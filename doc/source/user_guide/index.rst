
.. _user_guide:

User guide
==========

In these pages we will describe the relationship between the various EnSight Python
interfaces and the EnSight core.

.. toctree::
   :maxdepth: 1
   :hidden:

   cmdlang_native
   object_api
   api_differences


EnSight and PyEnSight Interfaces
--------------------------------

There is a Python interpreter embedded in the EnSight desktop application.  In
general that interpreter is referred to as the 'EnSight' or 'embedded' interpreter.
This interface is based on a built-in 'ensight' module that cannot be imported
into any other interpreter.  It is the fastest Python interface to EnSight and
much of EnSight itself is written in Python running in this interpreter.

The other interface is PyEnSight.  This interface is implemented as a portable
wheel and can be installed in most any Python interpreter.  The interface provided
by this component resides in the ansys.pyensight module.  It is a 'remote' interface
in that it actually starts an independent EnSight instance in another process and
connects to it.  Over that connection, the pyensight interface makes it possible
to execute Python commands in the embedded interpreter and return results.
The pyensight interface has a nearly identical API to the embedded interface
so code written for one interface will basically work in the other if the code
is structured properly.  See: :ref:`api_differences` for more differences.


History: Native and Object APIs
-------------------------------

The EnSight application has always has a journaling language, often referred to
as 'command language' or 'cmdlang'.  This system made it possible to view and
review every interaction in EnSight as a command stream and users could play
back the journal streams to automate tasks.

Around EnSight 9.x, an embedded Python interpreter was introduced into the EnSight
core.  The initial language binding to EnSight was via the 'native API'.  The native
API is derived from the EnSight journaling language.  It is basically a direct Python
mapping with object specific conversion operations to simplify the interface.  See
:ref:`ref_cmdlang_native` for more details.  This interface is the most complete
interface to EnSight and there are tools in the EnSight script editor that allow
for the conversion of blocks of command language into this Python API.

As the sophistication of Python scripts increased, users began to run into limitations
in the journal-based interface.  In response, the object API was developed.
The object API is a direct interface to the core C++ EnSight objects.  It is a
proxy interface that exposes C++ object attribute interfaces as Python
properties.  The advantages of the object API is support for fine grained
queries and event handling. See :ref:`ref_object_api` for more details.  This
API does not as of yet cover all of the ground the native API does, but it
allows for more interactive and reactive components interfaces to be used.
So much so, that a significant portion of the EnSight GUI is written using
this API.


EnSight Architecture
~~~~~~~~~~~~~~~~~~~~

The EnSight Python APIs reflect the core EnSight architecture.  There are two
types of objects in EnSight.  The first set are part of the code and are
generally created automatically at startup.

Note: in the following sections, many of the core classes are described.  This
is not a complete list, only commonly used objects are discussed here.


Common Static Objects
---------------------

There are fixed number of each of these objects and they are all allocated
statically at startup.  The Python API allows for attributes on these objects
to be modified and their status queried.  The key object is ENS_GLOBAL which
is accessed via ensight.objs.core.  Properties on that object can generally
access all of the other objects in the system.

================ ==================================================
Class            Description
================ ==================================================
ENS_CAMERA       Cameras are used to set up views of the current scene.
                 They can be associated with viewports and attached to
                 polylines, nodes and other graphics entities.
ENS_CASE         Case objects are used to read a dataset.  There are a
                 fixed number of case objects that can be active and
                 each case can load a dataset in a different format.
ENS_GLOBALS      The globals object provides an interface to the
                 core EnSight state.  All of the objects
                 cane be accessed via properties on this object.
ENS_LIGHTSOURCE  The EnSight scene supports a finite number of
                 preallocated lighting sources.  These objects
                 provide the interface to the light properties.
ENS_PROBE        The probe object allows for creation of spatial data
                 probes.  The result of probe queries can be
                 accessed via this object.
ENS_TEXTURE      Texture object maintain the pixel arrays that can
                 be applied via projective or explict texture coordinates.
ENS_TOOL         Tools are spatial input devices in the scene.  They
                 allow for the selection of points, regions of space,
                 reference lines/planes, etc.  There are several
                 unique tools types.  The PyEnSight API uses these
                 subclasses for each tool singleton.

                 =================== ===========================================
                 Subclass            Description
                 =================== ===========================================
                 ENS_TOOL_BOX        box.
                 ENS_TOOL_CONE       line segment with a base radius.
                 ENS_TOOL_SPHERE     sphere.
                 ENS_TOOL_CURSOR     single point.
                 ENS_TOOL_CYLINDER   line segment with fixed radius.
                 ENS_TOOL_LINE       line segment.
                 ENS_TOOL_PLANE      bounded plane.
                 ENS_TOOL_REVOLUTION line segment with a list of radii.
                 =================== ===========================================

ENS_VPORT        There are a fixed number of independent viewports.
                 Each viewport has an independent camera/projection
                 and the visibility of all 3D objects can be specified
                 independently for each viewport.
================ ==================================================


Common Dynamic Objects
----------------------

There are fixed number of each of these objects and they are all allocated
statically at startup.  The Python API allows for attributes on these objects
to be modified and their status queried.

================ ==================================================
Class            Description
================ ==================================================
ENS_ANNOT        Annotation base class.  Annotations are mostly 2D objects that
                 overlay the 3D scene.  Things like text blocks, lines, etc.
                 There are more complex types, for example a legend annotation
                 is used to display the palette associated with a variable.
                 The PyEnSight API uses specific subclasses for each annotation
                 type.

                 =============== ===============================================
                 Subclass        Description
                 =============== ===============================================
                 ENS_ANNOT_ARROW 3D arrow pointing at a location in data space.
                 ENS_ANNOT_DIAL  display of a constant variable as a dial.
                 ENS_ANNOT_GAUGE display of a constant variable as a linear gauge.
                 ENS_ANNOT_LGND  legend representation of a variable palette.
                                 Note: these are only created by ENS_VAR objects.
                 ENS_ANNOT_LINE  single line.
                 ENS_ANNOT_LOGO  image annotation.
                 ENS_ANNOT_SHAPE generic 2D shapes: box, circle and 2D arrow.
                 ENS_ANNOT_TEXT  block of 2D overlay text.
                 =============== ===============================================

ENS_GROUP        Group objects play two roles.  First, they provide a
                 hierarchical interface to collections of ENS_PART, ENS_LPART
                 objects for display in the GUI or general organization.  Second,
                 groups can be the output of a find operation, which can be handy
                 since they support fast, recursive, bulk property changes.
ENS_LPART        The LPART object represents an unloaded mesh object in a dataset.
                 LPARTs are created by ENS_CASE objects when a case loads a dataset.
                 The LPART object is used to create ENS_PART objects from a dataset.
                 In most cases, these objects are automatically leveraged when a
                 dataset is loaded.
ENS_PALETTE      These objects are allocated dynamically, but only indirectly under user
                 control. Every ENS_VARIABLE object has one or more ENS_PALETTE objects.
                 One for scalars and four for vectors ([X],[Y],[Z],mag).
ENS_PART         A PART object represents a block of geometry in the current scene.  The
                 geometry can come from the dataset on disk (via an LPART) or it can come
                 from part "creation" methods for example: iso-contour, clips, profiles,
                 vortex cores, etc.
                 The PyEnSight API uses specific subclasses for each annotation
                 type.  They all represent a mesh consisting of a collection of elements.
                 Usually these are located in the EnSight server, but in some cases they
                 are realized in the client.

                 ========================== ======================================================
                 Subclass                   Description
                 ========================== ======================================================
                 ENS_PART_AUX_GEOM          An auxiliary geometry part allows for scripted creation
                                            of objects like boxes that can be used in other
                                            calculations or to enhance visualizations (e.g., for a
                                            backdrop).
                 ENS_PART_BUILT_UP          This part is more commonly known as a "subset" part. It
                                            allows for collections of elements/nodes to be selected
                                            from a set of input parts.  These are merged into this
                                            part.
                 ENS_PART_CLIP              Created by clipping a parent set of parts.
                 ENS_PART_CONTOUR           The result of contouring a parent set of parts.
                 ENS_PART_DEVELOPED_SURFACE A developed surface is generated by treating any
                                            2D Part (or parent Part) as a surface of revolution,
                                            and mapping specific curvilinear coordinates of the
                                            revolved surface into a planar representation.
                 ENS_PART_ELEVATED_SURFACE  For a given collection of 2D parent parts, this
                                            part presents a displacement of the surface of the
                                            parents based on a specific variable and various
                                            parameters.
                 ENS_PART_FILTER            A filter part is created by applying a collection of
                                            variable range filters to a collection of parent parts.
                 ENS_PART_FX_SEP_ATT        Separation and attachment lines can be created on
                                            2D surfaces.  These help visualize areas where flow
                                            abruptly leaves or returns to the 2D surface in 3D flow
                                            fields.
                 ENS_PART_FX_SHOCK          Shock region parts help visualize shock waves in a 3D
                                            flow field. Shock waves are characterized by an abrupt
                                            increase in density, energy, and pressure gradients,
                                            as well as a simultaneous sudden decrease in the
                                            velocity gradient.
                 ENS_PART_FX_VORTEX_CORE    Vortex cores help visualize the centers of swirling
                                            flow in a flow field. EnSight creates vortex core
                                            segments from the velocity gradient tensor of 3D flow
                                            field part(s).
                 ENS_PART_ISOSURFACE        Created by applying isosurfacing to a parent set of
                                            parts.
                 ENS_PART_MODEL             Read from a dataset via an LPART.
                 ENS_PART_PARTICLE_TRACE    Particle traces generated by integrating points
                                            through a vector field defined on a collection of
                                            parent parts.
                 ENS_PART_POINT             This part can be created via API or from a file.  It is
                                            a list of points.  Commonly, the point tool is used to
                                            generate these parts.
                 ENS_PART_PROFILE           Profile parts are created by combining a 1D entity
                                            (line clip, contour, particle trace) with a surface
                                            part.  The profile of a specific variable, sampled over
                                            the 1D entity is captured in a profile part.
                 ENS_PART_TENSOR_GLYPH      A part representing a tensor field on a collection of
                                            parts as a collection of orientated and colored glyphs.
                 ENS_PART_VECTOR_ARROW      A part representing a vector field on a collection of
                                            parts as a collection of orientated and colored arrows.
                 ========================== ======================================================

ENS_PLOTTER      A plotter object is a visual frame for displaying one or more ENS_QUERY objects.
                 It includes axis, title, backgrounds, borders, legends, etc.
ENS_POLYLINE     Polyline objects are called splines in EnSight.  They can be used to set up
                 things like camera paths.
ENS_QUERY        Query objects represent y = f(x) data.  This data can come directly from a dataset,
                 created when the ENS_CASE object loads a dataset, or queries can be created using
                 loaded/computed data.  For example, one could query the values of pressure along
                 a line segment through a PART of volumetric elements.
ENS_VAR          Variable objects represent a specific field variable, case or part constant.
                 The base object contains the metadata associated with the variable (e.g.,
                 ranges, etc).  Variables can be introduced directly from datasets, but they
                 can also be created using calculator functions.
================ ==================================================