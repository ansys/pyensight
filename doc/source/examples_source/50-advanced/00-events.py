"""
.. _ref_events:

Asynchronous Event Support
==========================

Every attribute change may have an event callback associated with it.
In this example, different connection mechanisms are explored along
with different mechanisms for getting data values.

"""

###############################################################################
# Start an EnSight session
# ------------------------
# Start by launching and connecting to an instance of EnSight.
# In this case, we use a local installation of EnSight.

from urllib.parse import parse_qs, urlparse

from IPython.display import display
from ipywidgets import widgets

from ansys.pyensight.core import LocalLauncher

session = LocalLauncher().start()

###############################################################################
# Simple event
# ------------
#
# The simplest case is to register a callback for a specific attribute on a
# specific object.  Here a callback is registered to the 'ensight.objs.core'
# object.  Whenever the PARTS attribute changes, the callback function will
# be called.  This function will be called when we load a dataset.  Every
# callback function includes a string that is returned as a parameter to the
# callback function.

partlist_disp = widgets.HTML()
display(partlist_disp)


def part_list(name: str):
    partlist_disp.value = f"Event: {name}"


session.add_callback(session.ensight.objs.core, "partlist_name", ["PARTS"], part_list)


###############################################################################
# Load a dataset
# --------------
#
# .. image:: /_static/00_events_0.png
#
# Load some data included in the EnSight distribution and bring up and interactive
# viewer for the scene.
#
# Note the callback string:  grpc://.../partlist_name?enum=PARTS&uid=220
# The callback is in the form of a URI.  "partlist_name" is the string from the add_callback()
# call.  The name of the attribute is always returned as "enum" and the id of the object
# will be returned in "uid".

session.load_data(f"{session.cei_home}/ensight{session.cei_suffix}/data/guard_rail/crash.case")
render = session.show("remote")


###############################################################################
# Class event callback
# --------------------
#
# .. image:: /_static/00_events_1.png
#
# Events can be associated with classes as well.  Here we associate a callback
# with all part objects, listening to both the VISIBLE and COLORBYRGB attributes.
# The urllib module is used to parse out the returned value.
#
# After running this code, the cell value will call out the change in the
# color of the windshield.

part_disp = widgets.HTML()
display(part_disp)


def part_event(uri: str):
    p = urlparse(uri)
    q = parse_qs(p.query)
    obj = session.ensight.objs.wrap_id(int(q["uid"][0]))
    value = obj.getattr(q["enum"][0])
    part_disp.value = f"Part: {obj}, Attribute: {q['enum'][0]} Value: {value}"


attribs = [session.ensight.objs.enums.VISIBLE, session.ensight.objs.enums.COLORBYRGB]
session.add_callback("'ENS_PART'", "partattr", attribs, part_event)

session.ensight.objs.core.PARTS["hood"][0].COLORBYRGB = [1.0, 0.0, 0.0]


###############################################################################
# Trigger Visible Attribute
# -------------------------
#
# .. image:: /_static/00_events_2.png
#
# Changing the visible attribute will trigger the same callback, but with
# different values.

session.ensight.objs.core.parts["windshields"].set_attr(session.ensight.objs.enums.VISIBLE, True)


###############################################################################
# Callback macros
# ---------------
#
# .. image:: /_static/00_events_3.png
#
# The name string includes a mechanism for including target object values directly
# in the returned URI.  This mechanism avoids the need to make PyEnSight calls
# from within a callback function.  This can avoid reentrancy and performance
# issues.  This approach is more efficient than the previous example.
#
# Extending the previous example to capture both visibility and RGB color
# values using the macro mechanism.

macro_disp = widgets.HTML()
display(macro_disp)


def macro_event(uri: str):
    p = urlparse(uri)
    q = parse_qs(p.query)
    obj = session.ensight.objs.wrap_id(int(q["uid"][0]))
    obj.getattr(q["enum"][0])
    macro_disp.value = f"Part: {obj}, Attr: {q['enum'][0]} Visible: {q['visible']}  RGB: {q['rgb']}"


attribs = [session.ensight.objs.enums.VISIBLE, session.ensight.objs.enums.COLORBYRGB]
name = "partmacro?visible={{VISIBLE}}&rgb={{COLORBYRGB}}"
session.add_callback("'ENS_PART'", name, attribs, macro_event)

session.ensight.objs.core.PARTS["hood"][0].COLORBYRGB = [0.0, 1.0, 0.0]

###############################################################################
# Close the session
# -----------------
# Close the connection and shut down the EnSight instance

session.close()
