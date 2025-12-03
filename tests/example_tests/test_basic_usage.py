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

import glob
import os

from ansys.pyensight.core import DockerLauncher, LocalLauncher
import pytest


def test_basic_usage(tmpdir, pytestconfig: pytest.Config):
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    install_path = pytestconfig.getoption("install_path")
    if use_local:
        launcher = LocalLauncher(ansys_installation=install_path)
    else:
        launcher = DockerLauncher(
            data_directory=data_dir, use_dev=True, grpc_disable_tls=True, grpc_use_tcp_sockets=True
        )
    session = launcher.start()
    core = session.ensight.objs.core
    session.load_data(f"{session.cei_home}/ensight{session.cei_suffix}/data/cube/cube.case")
    session.ensight.view_transf.rotate(30, 30, 0)
    session.show("image", width=800, height=600)
    clip_default = core.DEFAULTPARTS[session.ensight.PART_CLIP_PLANE]
    parent_parts = core.PARTS
    clip = clip_default.createpart(name="Clip", sources=parent_parts)[0]
    image = session.show("image", width=800, height=600)
    image.download(data_dir)
    print("Parts:", core.PARTS)
    clip_default = session.cmd("ensight.objs.core.DEFAULTPARTS[ensight.PART_CLIP_PLANE]")
    clip.COLORBYPALETTE = core.VARIABLES["temperature"][0]
    image = session.show("image", width=800, height=600)
    image.download(data_dir)
    print("Variables:", core.VARIABLES)
    core.PARTS.set_attr("ELTREPRESENTATION", session.ensight.objs.enums.BORD_FULL)
    core.PARTS[0].OPAQUENESS = 0.1
    d = dict(HIDDENLINE=True, HIDDENLINE_USE_RGB=True, HIDDENLINE_RGB=[0, 0, 0])
    core.setattrs(d)
    image = session.show("image", width=800, height=600)
    image.download(data_dir)
    text = core.DEFAULTANNOTS[session.ensight.ANNOT_TEXT].createannot("Temperature Clip")
    text.setattrs(dict(LOCATIONX=0.5, LOCATIONY=0.95))
    image = session.show("image", width=800, height=600)
    image.download(data_dir)
    pngdata = session.render(1920, 1080, aa=4)
    with open(os.path.join(data_dir, "simple_example.png"), "wb") as fp:
        fp.write(pngdata)
    glbdata = session.geometry()
    with open(os.path.join(data_dir, "simple_example.glb"), "wb") as fp:
        fp.write(glbdata)
    session.show("remote")
    local_files = glob.glob(os.path.join(data_dir, "*"))
    png_local = [x for x in local_files if ".png" in x]
    glb_local = [x for x in local_files if ".glb" in x]
    assert len(png_local) == 5
    assert len(glb_local) == 1
    session.close()
