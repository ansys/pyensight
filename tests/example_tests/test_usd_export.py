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
import sys
import time
import warnings

from ansys.pyensight.core import DockerLauncher, LocalLauncher
import pytest


def compare_prims(prim1, prim2):
    if prim1.GetPath() != prim2.GetPath():
        return False
    if prim1.GetTypeName() != prim2.GetTypeName():
        return False
    for attr1 in prim1.GetAttributes():
        attr2 = prim2.GetAttribute(attr1.GetName())
        if not attr2 or attr1.Get() != attr2.Get():
            return False
    return True


def compare_usd_files(stage1, stage2):
    if not stage1 or not stage2:
        raise RuntimeError("Cannot open one of the Usd files")
    prims1 = list(stage1.Traverse())
    prims2 = list(stage2.Traverse())
    if len(prims1) != len(prims2):
        print("Different number of prims.")
        return False
    for prim1, prim2 in zip(prims1, prims2):
        if not compare_prims(prim1, prim2):
            print(f"Differences found in prim: {prim1.GetPath()}")
            return False
    print("No differences found.")
    return True


def wait_for_idle(session):
    found = False
    start = time.time()
    while not found and time.time() - start < 60:
        status = session.ensight.utils.omniverse.read_status_file()
        if status.get("status") == "idle":
            found = True
        time.sleep(0.5)
    return found


def test_usd_export(tmpdir, pytestconfig: pytest.Config):
    if sys.version_info.minor >= 13:
        warnings.warn("Test not supported for Python >= 3.13")
        return
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    install_path = pytestconfig.getoption("install_path")
    if use_local:
        launcher = LocalLauncher(ansys_installation=install_path)
    else:
        launcher = DockerLauncher(data_directory=data_dir, use_dev=True)
    session = launcher.start()
    session.load_example("waterbreak.ens")
    session.ensight.utils.omniverse.create_connection(data_dir)
    assert wait_for_idle(session)
    usd_files = glob.glob(os.path.join(data_dir, "*.usd"))
    assert len(usd_files) == 1
    base_usd = usd_files[0]
    parts = glob.glob(os.path.join(data_dir, "Parts", "*.usd"))
    assert len(parts) >= 5
    from pxr import Usd

    temp_stage = Usd.Stage.Open(usd_files[0])
    # Save off the first stage to make it static and not get live updates for
    # later comparison
    temp_stage.Export(os.path.join(data_dir, "stage1.usd"))
    stage1 = Usd.Stage.Open(os.path.join(data_dir, "stage1.usd"))
    session.ensight.objs.core.PARTS.set_attr("COLORBYPALETTE", "alpha1")
    session.ensight.utils.omniverse.update()
    assert wait_for_idle(session)
    stage2 = Usd.Stage.Open(base_usd)
    diff = compare_usd_files(stage1, stage2)
    assert diff is False
    diff = compare_usd_files(temp_stage, stage2)
    assert diff is True
    session.ensight.utils.omniverse.update(temporal=True)
    assert wait_for_idle(session)
    parts = glob.glob(os.path.join(data_dir, "Parts", "*.usd"))
    # Considering deduplication, at the end of the export there will be 39 items
    # not 100 (5*20)
    assert len(parts) > 5
