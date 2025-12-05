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
import platform
import subprocess
from unittest import mock

from ansys.pyensight.core.locallauncher import LocalLauncher
import ansys.pyensight.core.session
import pytest


def test_start(mocker):
    mocker.patch.object(LocalLauncher, "get_cei_install_directory", return_value="/path/to/awp/CEI")
    launcher = LocalLauncher("/path/to/awp/")
    # Mocking Popen breaks platform.system, so the function is mocked
    mocker.patch.object(platform, "system", return_value=str(platform.system()))
    popen = mock.MagicMock("MockedPopen")
    popen.pid = 3456
    mocker.patch.object(LocalLauncher, "_is_system_egl_capable", return_value=False)
    mocker.patch.object(subprocess, "Popen", return_value=popen)
    glob_mock = mock.MagicMock("superGlob")
    glob_mock.side_effect = [["/path/to/awp/CEI/nexus345/websocketserver.py"]]
    mocker.patch.object(glob, "glob", glob_mock)
    mocker.patch.object(ansys.pyensight.core.session, "Session")
    launcher.start()
    glob_mock.side_effect = [["/path/to/awp/CEI/nexus345/websocketserver.py"]]
    launcher = LocalLauncher("/path/to/awp/", batch=False)
    launcher.start()
    glob_mock.side_effect = [["/path/to/awp/CEI/nexus345/websocketserver.py"]]
    launcher = LocalLauncher("/path/to/awp/", use_sos=3)
    launcher.start()
    os.environ["PYENSIGHT_FORCE_ENSIGHT_EGL"] = "1"
    os.environ["ENSIGHT_ANSYS_LAUNCH"] = "1"
    os.environ["PYENSIGHT_DEBUG"] = "1"
    glob_mock.side_effect = [["/path/to/awp/CEI/nexus345/websocketserver.py"]]
    launcher = LocalLauncher("/path/to/awp/", use_egl=True)


def test_get_cei_install_directory(mocker):
    exists = mocker.patch.object(os.path, "exists", return_value=True)
    path = "/path/to/darkness"
    method = LocalLauncher.get_cei_install_directory
    assert method(path) == os.path.join(path, "CEI")
    second_path = "/stairway/to/heaven"
    os.environ["PYENSIGHT_ANSYS_INSTALLATION"] = second_path
    assert method(path) == os.path.join(path, "CEI")
    assert method(None) == os.path.join(second_path)
    del os.environ["PYENSIGHT_ANSYS_INSTALLATION"]
    version = ansys.pyensight.core.__ansys_version__
    # In case tests are launched locally and the environment variable is
    # set, the launcher would manage to find an install. This trick
    # cleans it, to check all the paths
    if f"AWP_ROOT{version}" in os.environ:
        del os.environ[f"AWP_ROOT{version}"]
    found = False
    try:
        import enve

        second_path = enve.home()
        found = True
    except ModuleNotFoundError:
        pass
    os.environ[f"AWP_ROOT{version}"] = second_path
    if found is True:
        assert method(None) == second_path
    else:
        assert method(None) == os.path.join(second_path, "CEI")
    exists.return_value = False
    with pytest.raises(RuntimeError):
        method(None)
