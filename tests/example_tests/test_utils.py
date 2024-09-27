import os
from typing import TYPE_CHECKING, Any, Optional, Tuple
import warnings

from ansys.pyensight.core.enscontext import EnsContext

warnings.filterwarnings("ignore")


if TYPE_CHECKING:
    from ansys.pyensight.core import Session


def test_utils(launch_pyensight_session: Tuple["Session", Any, Optional[str]]):
    session, data_dir, root = launch_pyensight_session
    session2 = session._launcher.start()
    # Check that only one session is associated to a launcher
    assert session == session2
    session.load_example("waterbreak.ens", root=root)
    # "Load" the utils modules
    parts = session.ensight.utils.parts
    views = session.ensight.utils.views
    query = session.ensight.utils.query
    init_state = session.capture_context()
    init_state.save(os.path.join(data_dir, "init_state.ctxz"))
    views.set_view_direction(1, 1, 1, name="isometric")
    iso_state = session.capture_context()
    # Since no tags are supplied, all the parts are selected
    parts.select_parts_by_tag().set_attr("VISIBLE", False)
    session.restore_context(iso_state)
    sn = session.ensight.utils.support.scoped_name
    zclip_state = None
    with sn(session.ensight) as ensight, sn(session.ensight.objs.core) as core:
        clip_default = core.DEFAULTPARTS[ensight.PART_CLIP_PLANE]
        clip = clip_default.createpart(name="XClip", sources=parts.select_parts_by_dimension(3))[0]
        attrs = []
        attrs.append(["MESHPLANE", ensight.objs.enums.MESH_SLICE_Z])  # Z axis
        attrs.append(["TOOL", ensight.objs.enums.CT_XYZ])  # XYZ Tool
        attrs.append(["VALUE", 0.55])  # Z value
        zclip = clip_default.createpart(name="ZClip", sources=clip)[0]
        query.create_distance(
            "zlip_query", query.DISTANCE_PART1D, [zclip], core.VARIABLES["p"][0], new_plotter=True
        )
        zclip_state = session.capture_context()
    session.show("remote")
    # Change the view to test the view restoring
    with sn(session.ensight, native_exceptions=True) as ensight:
        ensight.view_transf.rotate(-66.5934067, 1.71428561, 0)
        ensight.view_transf.rotate(18.0219765, -31.6363659, 0)
        ensight.view_transf.rotate(-4.83516455, 9.5064888, 0)
        ensight.view_transf.zoom(0.740957975)
        ensight.view_transf.zoom(0.792766333)
        ensight.view_transf.translate(0.0719177574, 0.0678303316, 0)
        ensight.view_transf.rotate(4.83516455, 3.42857122, 0)
    views.restore_view("isometric")
    session.show("remote")
    session.restore_context(zclip_state)
    temp_query = query.create_temporal(
        "temporal_query",
        query.TEMPORAL_XYZ,
        parts.select_parts_by_dimension(3),
        "alpha1",
        xyz=views.compute_model_centroid(),
        new_plotter=True,
    )
    print(temp_query.QUERY_DATA)
    session.show("remote")
    ctx = EnsContext()
    ctx.load(os.path.join(data_dir, "init_state.ctxz"))
    session.restore_context(ctx)
