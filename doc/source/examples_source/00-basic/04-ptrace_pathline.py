"""
.. _ptrace_pathline:

Pathline (transient streamline) Creation
========================================

Utilize EnSight Particle Trace for Pathline (transient streamline).
Create a Pathline and Animate it.

"""

###############################################################################
# Start an EnSight session
# ------------------------
# Launch and connect to an instance of EnSight.
# This example uses a local EnSight installation.
from ansys.pyensight.core import LocalLauncher

session = LocalLauncher().start()

# Setup shortcuts for long winded calls.
eocore = session.ensight.objs.core
eonums = session.ensight.objs.enums
eoutil = session.ensight.utils

###############################################################################
# Load a dataset
# --------------
# Load Flow2D dataset included in the EnSight installation
# set the timestep to the minimum timestep and render.
#
# .. image:: /_static/04_pathline_0.png

session.load_data(f"{session.cei_home}/ensight{session.cei_suffix}/data/flow2d/flow2d.case")
varname = eocore.VARIABLES["VITESSE"][0]
eocore.PARTS.set_attr("COLORBYPALETTE", varname)
session.ensight.objs.core.TIMESTEP = session.ensight.objs.core.TIMESTEP_LIMITS[0]
session.show("image", width=800, height=600)


###############################################################################
# Create a clip plane
# -------------------
# Create a clip through the domain, at X = 0.75.
# We first call up the default clip part, set attributes, and then create the clip
# MESHPLANE sets the type of clip (e.g. X, Y, Z, R, T, Z, etc)
# TOOL sets the tool to create the clip from.
# VALUE is the location of the clip.
# DOMAIN controls intersection vs inside vs outside etc.
# Parent Part is named 'Part by All Elements'
#

clip = eocore.DEFAULTPARTS[session.ensight.PART_CLIP_PLANE]
parent_parts = eocore.PARTS["Part by All Elements"][0]

attrs = []
attrs.append(["MESHPLANE", eonums.MESH_SLICE_X])
attrs.append(["TOOL", eonums.CT_XYZ])
attrs.append(["VALUE", 0.75])
attrs.append(["DOMAIN", eonums.CLIP_DOMAIN_INTER])
clip = clip.createpart(name="X_Clip", sources=[parent_parts], attributes=attrs)


###############################################################################
# Create a Pathline Trace Emitting from the Clip Part
# ---------------------------------------------------------
# Using the 2D parts as the parent (model is 2d), with the "from Part" as the emission type
# "VITESSE" as the vector, and 25 points along the Clip line as emitter locations.
# We also setup to first emit the Pathlines at time = 4 seconds.
# and Emit NEW pathlines ever 20 seconds after that. (They will follow NEW path)
#
# .. image:: /_static/04_pathline_1.png

emitter_part = clip
parent_parts = eoutil.parts.select_parts_by_dimension(2)
npts = 25  # number of emitters
vector_var = varname  # Vector variable to use
pathline_part = eoutil.parts.create_particle_trace_from_parts(
    "Pathline",
    vector_var,
    parts=emitter_part,
    num_points=npts,
    source_parts=parent_parts,
    pathlines=True,
    emit_time=4.0,
    delta_time=20.0,
)
session.show("image", width=800, height=600)


###############################################################################
# Change Visual Attributes
# ----------------------------------------------------------
#  Modify the attributes of the pathlines and animate over time
#
# .. image:: /_static/04_pathline_2.png

pathline_part.REPRESENTATION = eonums.TRACE_TUBE
pathline_part.WIDTHSCALEFACTOR = 0.012
session.show("image", width=800, height=600)


###############################################################################
# Animate the Pathlines
# ----------------------------------------------------------
#  Turn OFF the pathline lines visibility (to see the animate under)
#  Turn ON the animate pathlines.
#  Change to Sphere representation, size, and adjust speed and length.
#
# .. video:: ../../_static/04_pathline_3.mp4
#     :width: 640
#     :height: 360
#

pathline_part.VISIBLE = False
pathline_part.ANIMATE = True
eocore.HEADTYPE = eonums.ATRACE_HEAD_SPHERE
eocore.HEADSCALE = 0.3
session.ensight.solution_time.play_forward()
session.show("animation", width=800, height=600, fps=15)

###############################################################################
# Close the session

# sphinx_gallery_thumbnail_path = '_static/04_pathline_2.png'
session.close()
