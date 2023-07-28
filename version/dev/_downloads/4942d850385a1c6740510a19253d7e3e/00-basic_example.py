"""
.. _ref_basic_example:

Basic usage
===========

This most basic EnSight processing example loads some data
from an EnSight installation and generates a simplistic scene.

"""

###############################################################################
# Start an EnSight session
# ------------------------
# Launch and connect to an instance of EnSight.
# This example uses a local EnSight installation.

from ansys.pyensight.core import LocalLauncher

session = LocalLauncher().start()
core = session.ensight.objs.core

###############################################################################
# Load a dataset
# --------------
# Load some data included in the EnSight installation and set up
# a slightly rotated view (30 degrees over the X and Y axes).
#
# .. image:: /_static/00_basic_0.png

session.load_data(f"{session.cei_home}/ensight{session.cei_suffix}/data/cube/cube.case")
session.ensight.view_transf.rotate(30, 30, 0)
session.show("image", width=800, height=600)


###############################################################################
# Create a clip plane
# -------------------
# Create a clip through the volumetric parts.
#
# .. image:: /_static/00_basic_1.png

clip_default = core.DEFAULTPARTS[session.ensight.PART_CLIP_PLANE]
parent_parts = core.PARTS
clip = clip_default.createpart(name="Clip", sources=parent_parts)[0]
session.show("image", width=800, height=600)
print("Parts:", core.PARTS)


# .. note::
#    There is an issue with the version of PyEnSight that ships with EnSight
#    2023 R1. The ``core.DEFAULTPARTS`` attribute may fail with an error
#    message like this: :samp:`"AttributeError: 'objs' object has no attribute 'ENS_PART_BUILTUP'"`.
#    A workaround, other than updating the PyEnSight installation, is to use the
#    :func:`cmd<ansys.pyensight.core.Session.cmd>` method:
#
clip_default = session.cmd("ensight.objs.core.DEFAULTPARTS[ensight.PART_CLIP_PLANE]")


###############################################################################
# Color the clip plane
# --------------------
# Color the clip plane using the temperature variable.
#
# .. image:: /_static/00_basic_2.png

clip.COLORBYPALETTE = core.VARIABLES["temperature"][0]
session.show("image", width=800, height=600)
print("Variables:", core.VARIABLES)


###############################################################################
# Change the visual representation
# --------------------------------
# Change the visual representation a bit as follows:
#
# #. Display the volume part in border mode instead of feature mode.
# #. Make the volume part transparent so the clip is still visible.
# #. Enable element edge display, outlining elements in black lines.
#
# .. image:: /_static/00_basic_3.png

core.PARTS.set_attr("ELTREPRESENTATION", session.ensight.objs.enums.BORD_FULL)
core.PARTS[0].OPAQUENESS = 0.1
d = dict(HIDDENLINE=True, HIDDENLINE_USE_RGB=True, HIDDENLINE_RGB=[0, 0, 0])
core.setattrs(d)
session.show("image", width=800, height=600)


###############################################################################
# Create an annotation
# --------------------
# Create a text annotation and place it near the top of the viewport in the
# center.
#
# .. image:: /_static/00_basic_4.png

text = core.DEFAULTANNOTS[session.ensight.ANNOT_TEXT].createannot("Temperature Clip")
text.setattrs(dict(LOCATIONX=0.5, LOCATIONY=0.95))
session.show("image", width=800, height=600)

###############################################################################
# Export content
# --------------
# Save the current image and a GLB file of the scene to disk.

pngdata = session.render(1920, 1080, aa=4)
with open("simple_example.png", "wb") as fp:
    fp.write(pngdata)
glbdata = session.geometry()
with open("simple_example.glb", "wb") as fp:
    fp.write(glbdata)

###############################################################################
# Enable direct interaction
# -------------------------
# Open an embedded EnSight window in a browser frame.

session.show("remote")

###############################################################################
# Close the session
# -----------------
# Close the connection and shut down the EnSight instance.

session.close()
