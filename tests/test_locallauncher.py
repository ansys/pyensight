import glob
import os
import platform
import shutil
import subprocess
import time
from unittest import mock

import pytest

import ansys.pyensight
from ansys.pyensight import LocalLauncher


def test_start(mocker):
    mocker.patch.object(LocalLauncher, "get_cei_install_directory", return_value="/path/to/awp/CEI")
    launcher = LocalLauncher("/path/to/awp/")
    popen = mock.MagicMock("MockedPopen")
    popen.pid = 3456
    mocker.patch.object(subprocess, "Popen", return_value=popen)
    glob_mock = mock.MagicMock("superGlob")
    glob_mock.side_effect = ["/path/to/awp/CEI/nexus345/websocketserver.py"]
    mocker.patch.object(glob, "glob", glob_mock)
    mocker.patch.object(ansys.pyensight, "Session")
    # Mocking Popen breaks platform.system, so the function is mocked
    system = mocker.patch.object(platform, "system", return_value="Windows")
    launcher.start()
    system = mocker.patch.object(platform, "system", return_value="Linux")
    glob_mock.side_effect = ["/path/to/awp/CEI/nexus345/websocketserver.py"]
    launcher = LocalLauncher("/path/to/awp/", batch=False)
    launcher.start()


def test_stop(mocker, tmpdir):
    mocker.patch.object(LocalLauncher, "get_cei_install_directory", return_value="/path/to/awp/CEI")
    session_dir = tmpdir.mkdir("session_dir")
    launcher = LocalLauncher("/path/to/awp/")
    launcher.session_directory = session_dir
    launcher._ports = [1111, 2222]
    launcher.stop()
    assert not os.path.exists(session_dir)
    assert launcher._ports is None


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
    version = ansys.pyensight.__ansys_version__
    # In case tests are launched locally and the environment variable is
    # set, the launcher would manage to find an install. This trick
    # cleans it, to check all the paths
    if f"AWP_ROOT{version}" in os.environ:
        del os.environ[f"AWP_ROOT{version}"]
    os.environ[f"AWP_ROOT{version}"] = second_path
    assert method(None) == os.path.join(second_path, "CEI")
    exists.return_value = False
    with pytest.raises(RuntimeError):
        method(None)
