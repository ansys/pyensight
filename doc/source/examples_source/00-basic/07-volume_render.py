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

session = LocalLauncher(batch=False).start()


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

# LPARTS are loadable parts in EnSight. The idea here is to take the
# only structured part available and build after it a 2D surface, that
# is the body surface. This is accomplished just selecting the max
# values of the I,J,K directions and then loading the LPART
lpart = session.ensight.objs.core.CURRENTCASE[0].LPARTS[0]
lpart.NODEMAX = [53, 63, 1]
lpart.load()

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

# PARTS[1] is the body surface, just created
session.ensight.objs.core.PARTS[1].COLORBYRGB = [0.6, 0.6, 0.6]
session.ensight.view.highlight_parts("OFF")

#
# Color the 3D flow field by the variable that we
#  wish to visualize using Volume Rendering, Mach
#

# PARTS[0] is the 3D flow part
session.ensight.objs.core.PARTS[0].COLORBYPALETTE = "Mach"
session.ensight.function.palette("Mach")
session.ensight.function.modify_begin()
session.ensight.function.restore_predefinedpal("use_new_levels", "Magma")
session.ensight.function.modify_end()

#
#  Volume Rendering, in EnSight, is accomplished by subdividing
#   the flow field into a finite number of hex elements and then
#   doing the rendering of the variable in each box according to
#   the normalized variable value and the opacity ('alpha') for
#   ranges of values set using function points and the magnitude
#

session.ensight.part.select_begin(1)
session.ensight.clip.begin()
session.ensight.part.colorby_palette("Mach")
session.ensight.clip.domain("volume")
session.ensight.clip.tool("xyz_box")
session.ensight.clip.sample_step(128, 128, 128)
session.ensight.clip.origin(-0.497170001, 1.27204275, -0.879772604)
#
session.ensight.clip.axis("x", 0, 0, 1)
session.ensight.clip.axis("y", 0, -1, 0)
session.ensight.clip.axis("z", 1, 0, 0)

session.ensight.clip.length(2.24244738, 1.39883041, 3.60410643)
session.ensight.clip.end()
session.ensight.clip.create()
session.ensight.legend.width(0.0244169608)
session.ensight.legend.height(0.662014842)
session.ensight.function.palette("Mach")


session.ensight.function.point(0, "alpha", 0.000000, 0.000000)
session.ensight.function.point(1, "alpha", 0.061172, 0.000000)
session.ensight.function.point(2, "alpha", 0.133467, 0.000000)
session.ensight.function.point(3, "alpha", 0.194639, 0.000000)
session.ensight.function.point(4, "alpha", 0.236347, 0.899835)
session.ensight.function.point(5, "alpha", 0.316983, 0.899835)
session.ensight.function.point(6, "alpha", 0.319764, 0.000000)
session.ensight.function.point(7, "alpha", 0.361472, 0.000000)
session.ensight.function.point(8, "alpha", 0.364253, 0.908182)
session.ensight.function.point(9, "alpha", 0.433767, 0.908182)
session.ensight.function.point(10, "alpha", 0.444889, 0.000000)
session.ensight.function.point(11, "alpha", 0.486597, 0.000000)


session.ensight.function.add_knot(12, "alpha")


session.ensight.function.point(12, "alpha", 0.500500, 0.933223)
session.ensight.function.point(13, "alpha", 0.611722, 0.883140)
session.ensight.function.point(14, "alpha", 0.639528, 0.000000)
session.ensight.function.point(15, "alpha", 0.959292, 0.000000)
session.ensight.function.point(16, "alpha", 1.000000, 0.899835)

#
#  By adjusting the min and max of the variable values
#  shown, this can isolate the view to only the values
#  of interest within the alpha filtering.
#

session.ensight.function.range(0.02, 0.504598)
session.ensight.function.range(0.02, 0.353)

#
# This is a symmetric analysis about the Y axis
#

session.ensight.viewport.select_begin(0)
session.ensight.viewport.background_type("constant")
session.ensight.viewport.constant_rgb(0, 0, 0)
session.ensight.part.select_begin(1)
session.ensight.part.visible("OFF")
session.ensight.part.select_begin(2, 3)
session.ensight.part.modify_begin()
session.ensight.part.symmetry_type("mirror")
session.ensight.part.modify_end()
session.ensight.part.select_begin(2, 3)
session.ensight.part.modify_begin()
session.ensight.part.symmetry_mirror_y("ON")
session.ensight.part.modify_end()

#
#  Adjust the view
#

session.ensight.view_transf.rotate(-0.214030892, 0.477030873, 0)
session.ensight.view_transf.rotate(-82.8465729, 5.88338804, 0)
session.ensight.view_transf.rotate(0.665434599, 113.692574, 0)
session.ensight.view_transf.zoom(0.317107886)
session.ensight.view_transf.translate(-0.815654397, 0.113996685, 0)
session.ensight.view_transf.rotate(16.6358604, 3.3392241, 0)
session.ensight.view_transf.rotate(-6.32162857, -5.72438145, 0)
session.ensight.view_transf.rotate(9.64879894, 6.2014122, 0)

session.show("image", width=800, height=600)

###############################################################################
# Thumbnail
# sphinx_gallery_thumbnail_path = '_static/07_volume_rendering_3.png'


session.close()
