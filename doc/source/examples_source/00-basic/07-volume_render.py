"""
.. _volume_render:

Volume Rendering to Visualize Flow
=======================================================

Utilze EnSight to demonstrate the value of Volume Rendering
as a tool to visulize flow in 3D

Intended to work with EnSight version 24.2 or later

"""

###############################################################################
# Start an EnSight session
# ------------------------
# Launch and connect to an instance of EnSight.
# This example uses a local EnSight installation.
from ansys.pyensight.core import LocalLauncher

# batch is default (no visible ensight session)
session = LocalLauncher().start()

# use below for interactive debugging with a visible ensight session 
#session = LocalLauncher(batch=False).start()

# You can also specify the version of EnSight to use
#ansys_loc = r"""C:\Program Files\ANSYS Inc\v242"""
#session=LocalLauncher(ansys_installation = ansys_loc, batch=False).start()

# Setup shortcuts for long winded calls.
sesse = session.ensight
eocore = sesse.objs.core
eoutil = sesse.utils

###############################################################################
# Load a dataset
# --------------
# Load Shuttle Session file included in the EnSight installation and render
#
# .. image:: /_static/07_volume_render_0.png
#

xyz_file = f"{session.cei_home}/ensight{session.cei_suffix}/data/plot3d/shuttle.xyz"
q_file = f"{session.cei_home}/ensight{session.cei_suffix}/data/plot3d/shuttle.q"
session.load_data(
    data_file=xyz_file,
    result_file=q_file,
    file_format="PLOT3D",
    representation="3D_feature_2D_full",
)
session.show("image", width=800, height=600)

###############################################################################
# The PLOT3D reader only reads the volume by default. Now, extract a
#  particular IJK range for the surface of the shuttle
# ------------------------------------------------------------------

sesse.data_partbuild.begin()
sesse.case.select("Case 1")
sesse.data_partbuild.data_type("structured")
sesse.data_partbuild.group("OFF")
sesse.data_partbuild.select_begin(1)
sesse.data_partbuild.domain("all")
sesse.data_partbuild.noderange_i(1, 53)
sesse.data_partbuild.noderange_j(1, 63)
sesse.data_partbuild.noderange_k(1, 1)
sesse.data_partbuild.nodestep(1, 1, 1)
sesse.data_partbuild.nodedelta(0, 0, 0)
sesse.data_partbuild.description("Shuttle")
sesse.data_partbuild.create()
sesse.part.select_byname_begin("(CASE:Case 1)Shuttle")
sesse.case.select("Case 1")
sesse.data_partbuild.end()
session.show("image", width=800, height=600)

##############################################################################
# Volume Render Flow
# ------------------------------------------------------------------
# 
# .. image:: /_static/07_volume_render_1.png
#
#
# Make the shuttle surface an uninteresting, uniform color grey
#
sesse.part.select_begin(2)
sesse.part.colorby_palette("none")
sesse.part.colorby_rgb(0.6,0.6,0.6)
sesse.view.highlight_parts("OFF")
#
# Color the 3D flow field by the variable that we
#  wish to visualize using Volume Rendering, Mach
#
sesse.part.select_begin(1)
sesse.part.modify_begin()
sesse.part.colorby_palette("Mach")
sesse.legend.select_palette_begin("Mach")
sesse.part.modify_end()
sesse.legend.select_palette_begin("Mach")
sesse.function.palette("Mach")
sesse.function.palette("Mach")
sesse.function.modify_begin()
sesse.function.restore_predefinedpal("use_new_levels","Magma")
sesse.function.modify_end()
#
#  Volume Rendering, in EnSight, is accomplished by subdividing
#   the flow field into a finite number of hex elements and then
#   doing the rendering of the variable in each box according to
#   the normalized variable value and the opacity ('alpha') for
#   ranges of values set using function points and the magnitude
#
sesse.part.select_begin(1)
sesse.clip.begin()
sesse.part.colorby_palette("Mach")
sesse.clip.domain("volume")
sesse.clip.tool("xyz_box")
sesse.clip.sample_step(128,128,128)
sesse.clip.origin(-0.497170001,1.27204275,-0.879772604)
#
sesse.clip.axis("x",0,0,1)
sesse.clip.axis("y",0,-1,0)
sesse.clip.axis("z",1,0,0)
#
sesse.clip.length(2.24244738,1.39883041,3.60410643)
sesse.clip.end()
sesse.clip.create()
sesse.legend.width(0.0244169608)
sesse.legend.height(0.662014842)
sesse.function.palette("Mach")
#
#
#
sesse.function.point(0,"alpha",0.000000,0.000000)
sesse.function.point(1,"alpha",0.061172,0.000000)
sesse.function.point(2,"alpha",0.133467,0.000000)
sesse.function.point(3,"alpha",0.194639,0.000000)
sesse.function.point(4,"alpha",0.236347,0.899835)
sesse.function.point(5,"alpha",0.316983,0.899835)
sesse.function.point(6,"alpha",0.319764,0.000000)
sesse.function.point(7,"alpha",0.361472,0.000000)
sesse.function.point(8,"alpha",0.364253,0.908182)
sesse.function.point(9,"alpha",0.433767,0.908182)
sesse.function.point(10,"alpha",0.444889,0.000000)
sesse.function.point(11,"alpha",0.486597,0.000000)
#
#
sesse.function.add_knot(12,"alpha")
#
#
sesse.function.point(12,"alpha",0.500500,0.933223)
sesse.function.point(13,"alpha",0.611722,0.883140)
sesse.function.point(14,"alpha",0.639528,0.000000)
sesse.function.point(15,"alpha",0.959292,0.000000)
sesse.function.point(16,"alpha",1.000000,0.899835)
#
#  by adjusting the min and max of the variable values
#  shown, this can isolate the view to only the values
#  of interest within the alpha filterig.
#
sesse.function.range(0.02,0.504598)
sesse.function.range(0.02,0.353)
#
# This is a symmetric analysis about the Y axis
#
sesse.viewport.select_begin(0)
sesse.viewport.background_type("constant")
sesse.viewport.constant_rgb(0,0,0)
sesse.part.select_begin(1)
sesse.part.visible("OFF")
sesse.part.select_begin(2,3)
sesse.part.modify_begin()
sesse.part.symmetry_type("mirror")
sesse.part.modify_end()
sesse.part.select_begin(2,3)
sesse.part.modify_begin()
sesse.part.symmetry_mirror_y("ON")
sesse.part.modify_end()
#
#  Adjust the view
#
sesse.view_transf.rotate(-0.214030892,0.477030873,0)
sesse.view_transf.rotate(-82.8465729,5.88338804,0)
sesse.view_transf.rotate(0.665434599,113.692574,0)
sesse.view_transf.zoom(0.317107886)
sesse.view_transf.translate(-0.815654397,0.113996685,0)
sesse.view_transf.rotate(16.6358604,3.3392241,0)
sesse.view_transf.rotate(-6.32162857,-5.72438145,0)
sesse.view_transf.rotate(9.64879894,6.2014122,0)

session.show("image", width=800, height=600)
###############################################################################
# Thumbnail
# sphinx_gallery_thumbnail_path = '_static/07_volume_rendering_3.png'


session.close()
