# Copyright (C) 2022 - 2025 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import warnings

from ansys.pyensight.core.dockerlauncher import DockerLauncher
from ansys.pyensight.core.enscontext import EnsContext
from ansys.pyensight.core.locallauncher import LocalLauncher
import pytest

warnings.filterwarnings("ignore")


def test_utils(tmpdir, pytestconfig: pytest.Config):
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    install_path = pytestconfig.getoption("install_path")
    root = None
    if use_local:
        launcher = LocalLauncher(ansys_installation=install_path)
        root = "http://s3.amazonaws.com/www3.ensight.com/PyEnSight/ExampleData"
    else:
        launcher = DockerLauncher(data_directory=data_dir, use_dev=True)
    session = launcher.start()
    session2 = launcher.start()
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
