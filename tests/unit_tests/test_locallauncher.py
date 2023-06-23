import glob
import os
import platform
import subprocess
from unittest import mock

import ansys.pyensight.core
from ansys.pyensight.core.locallauncher import LocalLauncher
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
    glob_mock.side_effect = ["/path/to/awp/CEI/nexus345/websocketserver.py"]
    mocker.patch.object(glob, "glob", glob_mock)
    mocker.patch.object(ansys.pyensight, "Session")
    launcher.start()
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
