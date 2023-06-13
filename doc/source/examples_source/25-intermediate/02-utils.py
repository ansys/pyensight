"""
.. _ref_utils_example:

Basic EnSight Utils
=====================

The utils modules in PyEnSight have been designed to expose standard
post-processing operations via simplified APIs.
The example walks through the utils modules with some examples on
how they can be used to perform easily specific operations.

"""

###############################################################################
# Start an EnSight session
# ------------------------
# Start by launching and connecting to an instance of EnSight.
# In this case, we use a local installation of EnSight.

from ansys.pyensight import LocalLauncher
from ansys.pyensight.enscontext import EnsContext

session = LocalLauncher().start()

###############################################################################
# Load the data
# -------------
#
# .. image:: /_static/02_utils_0.png
#
# Here we use a remote session to load a simple time-varying dataset of
# waterflow over a break.

session.load_example("waterbreak.ens")
session.show("image", width=800, height=600)

###############################################################################
# "Load" the utils modules
# -------------
#
# The utils modules are available as instances of ensight.utils. In this example
# to allow a more simple use, they are casted into new variables with the same names.

parts = session.ensight.utils.parts
views = session.ensight.utils.views
query = session.ensight.utils.query

###############################################################################
# Capture a context of the current state
# -------------
#
# With the capture_context() method a in-memory context is saved, to be retrieved
# later in the code. The context is also saved to a file for being used also in future
# PyEnSight session.

init_state = session.capture_context()
init_state.save("init_state.ctxz")

###############################################################################
# Change view direction and restore a in-memory context
# -------------
#
# .. image:: /_static/02_utils_1.png
# .. image:: /_static/02_utils_2.png
# .. image:: /_static/02_utils_1.png
# An isometric view along the direction vector (1,1,1) is set, and a new in-memory
# context is saved. The view is also saved with the name "isometric".
# All the parts are selected via the select_parts_by_tag() method,
# which returns all of them since no tags have been supplied (and also because the dataset
# hasn't got any metadata for the parts). The parts are being hidden, and then the state
# is restored, showing again the isometric view.

views.set_view_direction(1, 1, 1, name="isometric")
iso_state = session.capture_context()
session.show("image", width=800, height=600)
# Since no tags are supplied, all the parts are selected
parts.select_parts_by_tag().set_attr("VISIBLE", False)
session.show("image", width=800, height=600)
session.restore_context(iso_state)
session.show("image", width=800, height=600)


###############################################################################
# Create scoped name for easy use of the ensight submodules to generate a distance query
# -------------
#
# .. image:: /_static/02_utils_3.png
#
# PyEnSight supports the generation of context managers for the PyEnSight modules.
# This can simplify the workflow with the addition of the context manager features in Python.
# A query is so generated along a 1D part generated on the fly. The parent part is selected
# using the parts module, with the "select_parts_by_dimension" module to select all the 3D parts.
# A context is saved for later use. The rendering view should look like this:


sn = session.ensight.utils.support.scoped_name
zclip_state = None
with sn(session.ensight) as ensight, sn(session.ensight.objs.core) as core:
    clip_default = core.DEFAULTPARTS[ensight.PART_CLIP_PLANE]
    clip = clip_default.createpart(name="XClip", sources=parts.select_parts_by_dimension(3))[0]
    attrs = []
    attrs.append(["MESHPLANE", 2])  # Z axis
    attrs.append(["TOOL", 9])  # XYZ Tool
    attrs.append(["VALUE", 0.55])  # Z value
    zclip = clip_default.createpart(name="ZClip", sources=clip)[0]
    query.create_distance(
        "zlip_query", query.DISTANCE_PART1D, [zclip], core.VARIABLES["p"][0], new_plotter=True
    )
    zclip_state = session.capture_context()
session.show("image", width=800, height=600)

###############################################################################
# Restore a view
# -------------
#
# .. image:: /_static/02_utils_4.png
#
# The model orientation, position and zoom are changed, then the isometric view is
# restored. An important difference with the context restore is that the view restore
# restores the orientation and the position but not the zoom level. Also,
# a context restore restored also the objects available at the time of the context save,
# while the view can only store position and orientation data. The rendering view should
# look like this:

session.ensight.view_transf.rotate(-66.5934067, 1.71428561, 0)
session.ensight.view_transf.rotate(18.0219765, -31.6363659, 0)
session.ensight.view_transf.rotate(-4.83516455, 9.5064888, 0)
session.ensight.view_transf.zoom(0.740957975)
session.ensight.view_transf.zoom(0.792766333)
session.ensight.view_transf.translate(0.0719177574, 0.0678303316, 0)
session.ensight.view_transf.rotate(4.83516455, 3.42857122, 0)
views.restore_view("isometric")
session.show("image", width=800, height=600)


###############################################################################
# Create a temporal query
# -------------
#
# .. image:: /_static/02_utils_5.png
#
# After restoring the distance query context, a temporal query is generated.
# In particular, the query is applied to a specific XYZ point, querying the
# alpha1 variable. The XYZ point is set to be the model centroid, computed
# via the views module. The data generated are then printed with this value returned:

session.restore_context(zclip_state)
temp_query = query.create_temporal(
    "temporal_query",
    query.TEMPORAL_XYZ,
    parts.select_parts_by_dimension(3),
    "alpha1",
    xyz=views.compute_model_centroid(),
)
print(temp_query.QUERY_DATA)


###############################################################################
# Restore a context from disk
# -------------
#
# .. image:: /_static/02_utils_6.png
#
# The following code shows how to restore a context previously saved on disk.
# By default the PyEnSight context files won't store the location of the dataset,
# so the dataset will have to be loaded in advance before restoring the context.
# The rendering view should look like this:

ctx = EnsContext()
ctx.load("init_state.ctxz")
session.restore_context(ctx)
session.show("image", width=800, height=600)
