"""
.. _surface_traces_lic:

Surface Restricted Traces and Line Integral Convolution
=======================================================

Utilze EnSight to investigate two types of surface streamlines:
Surface Restricted Traces (using Particle Trace)
and LIC (Line Integral Convolution)

Intended to work with EnSight version 24.2 or later

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
eoutil = session.ensight.utils

###############################################################################
# Load a dataset
# --------------
# Load Shuttle Session file included in the EnSight installation and render
#
# .. image:: /_static/05_srt_lic_0.png

session.ensight.objs.ensxml_restore_file(
    f"{session.cei_home}/ensight{session.cei_suffix}gui/demos/Shuttle Basic.ens"
)
session.ensight.view.highlight_parts("OFF")
session.ensight.view_transf.fit(0)
session.show("image", width=800, height=600)

###############################################################################
# Option 1. Using Particle Trace to create Surface Restricted Traces
# ------------------------------------------------------------------
# Using a Particle Trace capability
# Parent Part and Emit part are the same part.
# Surface Restriction is ON.
# .. image:: /_static/05_srt_lic_1.png

emitter_part = eoutil.parts.select_parts_by_dimension(2)
parent_parts = emitter_part
npts = 1500  # number of emitters
vector_var = eocore.VARIABLES["Momentum"][0]  # Vector variable to use

SRTpart = eoutil.parts.create_particle_trace_from_parts(
    "SurfaceRestrictedTrace",
    vector_var,
    parts=emitter_part,
    source_parts=parent_parts,
    direction="+/-",
    surface_restrict=True,
    num_points=npts,
)
session.show("image", width=800, height=600)

###############################################################################
# Change Visual Attributes
# ----------------------------------------------------------
#  Modify the attributes of the Surface Restricted Traces to
#  be visually closer to Flourescene or Titantiam Dioxide (experimental use)
# .. image:: /_static/05_str_lic_2.png

SRTpart.colorbyrgb = [0, 1, 0]
SRTpart.OPAQUENESS = 0.25
session.show("image", width=800, height=600)

###############################################################################
# Try Line Integral Convolution (LIC) instead
# ----------------------------------------------------------
#  As we don't already have a near-surface, non-zero vector defined we need to create 'Offset' Variable.
#  Create Offset Variable for Value of Momentum at 2.e-5 distance into fluid domain
#  Specify Offset Variable as the variable for LIC.
#  Specify High Contrast and 1 length for the LIC
#  Specify that we want to see LIC for the Shuttle Surface
# .. image:: /_static/05_srt_lic_3.png

SRTpart.VISIBLE = False
session.ensight.part.select_byname_begin("(CASE:Case 1)Shuttle")
session.ensight.variables.evaluate("OffsetVar = OffsetVar(plist,Momentum,2e-05)")

session.ensight.case.sft_variable("OffsetVar")
session.ensight.case.sft_contrast("ON")
session.ensight.case.sft_norm_length(1.000000)

session.ensight.part.select_byname_begin("(CASE:Case 1)Shuttle")
session.ensight.part.show_sft("ON")
session.show("image", width=800, height=600)

###############################################################################
# Thumbnail
# sphinx_gallery_thumbnail_path = '_static/05_srt_lic_3.png'


session.close()
