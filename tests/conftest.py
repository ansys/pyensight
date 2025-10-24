"""
Global fixtures go here.
"""
import atexit
import os
import subprocess
from unittest import mock

import ansys.pyensight.core
from ansys.pyensight.core import enshell_grpc, ensight_grpc
from ansys.pyensight.core.dockerlauncher import DockerLauncher
from ansys.pyensight.core.libuserd import LibUserd
from ansys.pyensight.core.locallauncher import LocalLauncher
from ansys.pyensight.core.session import Session
import numpy
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    This let's you specify the install path when you run pytest:
    $ pytest tests --install-path "/ansys_inc/v231/CEI/bin/ensight"
    TODO: Default must be set to the one on the CI/CD server.
    """
    parser.addoption("--install-path", action="store")
    parser.addoption("--use-local-launcher", default=False, action="store_true")
    parser.addoption("--use-local-test-data", default=False, action="store_true")


@pytest.fixture
def local_launcher_session(pytestconfig: pytest.Config) -> "ansys.pyensight.Session":
    session = LocalLauncher(ansys_installation=pytestconfig.getoption("install_path")).start()
    yield session
    session.close()


def cleanup_docker(request) -> None:
    # Stop and remove 'ensight' and 'ensight_dev' containers. This needs to be deleted
    # once we address the issue in the pyensight code by giving unique names to the containers
    try:
        subprocess.run(["docker", "stop", "ensight"])
        subprocess.run(["docker", "rm", "ensight"])
    except Exception:
        # There might not be a running ensight container. That is fine, just continue
        pass
    try:
        subprocess.run(["docker", "stop", "ensight_dev"])
        subprocess.run(["docker", "rm", "ensight_dev"])
    except Exception:
        # There might not be a running ensight_dev container. That is fine, just continue
        pass


@pytest.fixture
def docker_launcher_session() -> "Session":
    cleanup_docker()
    launcher = DockerLauncher(data_directory=".", use_dev=True)
    launcher.pull()
    session = launcher.start()
    yield session
    session.close()


@pytest.fixture
def enshell_mock():
    mocked_grpc = mock.MagicMock("GRPC")
    mocked_grpc.command = mock.MagicMock("command")
    mocked_grpc.is_connected = lambda: True
    mocked_grpc.connect = mock.MagicMock("execute_connection")
    values_run_command = [
        [0, "set_no_reroute_log"],  # first run, to find the ensight version
        [0, "set_debug_log"],  # second run
        [0, "verbose 3"],
    ]
    mocked_grpc.run_command = mock.MagicMock("enshell run command")
    mocked_grpc.run_command.side_effect = values_run_command.copy()
    path = "/ansys_inc/v345/CEI/bin/ensight"
    cei_home = path.encode("utf-8")
    mocked_grpc.cei_home = lambda: cei_home
    mocked_grpc.ansys_version = lambda: "345"
    mocked_grpc.start_ensight = lambda cmd, env: [0, cmd]
    mocked_grpc.start_other = lambda cmd, extra_env: [0, cmd]
    return mocked_grpc, values_run_command


enve = mock.MagicMock("enve")
ensight = mock.MagicMock("ensight")
_file = mock.MagicMock("ensight_file")
_file.image_format = lambda x: ""
_file.image_file = lambda x: ""
_file.image_window_size = lambda x: ""
_file.image_window_xy = lambda x, y: ""
_file.image_rend_offscreen = lambda x: ""
_file.image_numpasses = lambda x: ""
_file.image_stereo = lambda x: ""
_file.image_screen_tiling = lambda x, y: ""
_file.raytracer_options = lambda x: ""
_file.image_raytrace_it = lambda x: ""
_file.save_image = lambda: ""

ensight.file = _file
img = mock.MagicMock("img")
img.metadata = []
img.variabledata = numpy.zeros(shape=(1, 1))
img.pickdata = numpy.zeros(shape=(1, 1))
img.pixeldata = numpy.zeros(shape=(1, 1))
img.load = mock.MagicMock("load")
ensight.render = lambda x, y, num_samples, enhanced: img
enve.image = lambda: img


@pytest.fixture
@mock.patch.dict("sys.modules", {"ensight": ensight, "enve": enve})
def mocked_session(mocker, tmpdir, enshell_mock) -> "Session":
    cmd_mock = mock.MagicMock("cmd_mock")
    mock_dict = {"a": 1, "b": 2, "c": 3}
    cmd_mock.items = lambda: mock_dict.items()
    mocked_grpc = mock.MagicMock("GRPC")
    mocked_grpc.command = mock.MagicMock("command")
    mocked_grpc.is_connected = lambda: True
    mocked_grpc.connect = mock.MagicMock("execute_connection")
    mocker.patch.object(ensight_grpc, "EnSightGRPC", return_value=mocked_grpc)
    mocker.patch.object(enshell_grpc, "EnShellGRPC", return_value=enshell_mock[0])
    mocker.patch.object(ansys.pyensight.core.Session, "cmd", return_value=cmd_mock)
    session_dir = tmpdir.mkdir("test_dir")
    remote = session_dir.join("remote_filename")
    remote.write("test_html")
    mocker.patch.object(atexit, "register")
    session = Session(
        host="superworkstation",
        install_path="/path/to/darkness",
        secret_key="abcd1234-5678efgh",
        grpc_port=12345,
        html_port=23456,
        ws_port=34567,
        session_directory=session_dir,
        timeout=120.0,
    )
    session._build_utils_interface()
    session._cei_suffix = "345"
    return session


@pytest.fixture
def launch_libuserd_and_get_files(tmpdir, pytestconfig: pytest.Config):
    def _files(filename1, filename2, filepath1, filepath2):
        data_dir = tmpdir.mkdir("datadir")
        use_local = pytestconfig.getoption("use_local_launcher")
        install_path = pytestconfig.getoption("install_path")
        use_local_test_data = pytestconfig.getoption("use_local_test_data")
        session = None
        if use_local:
            # Launch locally
            libuserd = LibUserd(ansys_installation=install_path)
            session = LocalLauncher(ansys_installation=install_path).start()
        else:
            # Launch on docker otherwise
            libuserd = LibUserd(use_docker=True, use_dev=True, data_directory=data_dir)
            session = DockerLauncher(use_dev=True, data_directory=data_dir).start()

        libuserd.initialize()
        if not use_local_test_data:
            count = 0
            while count < 5:
                try:
                    file1_userd = libuserd.download_pyansys_example(filename1, filepath1)
                    file1_session = session.download_pyansys_example(filename1, filepath1)

                    if filename2 is None:
                        file2_userd = ""
                        file2_session = ""
                    else:
                        file2_userd = libuserd.download_pyansys_example(filename2, filepath2)
                        file2_session = session.download_pyansys_example(filename2, filepath2)
                    break
                except (KeyError, ConnectionError):
                    count += 1
            if count == 5 and (not file1_userd or not file1_session):
                raise RuntimeError("Couldn't download files for test.")
        else:
            pyensight_test_data_path = os.path.join(
                session.cei_home,
                f"apex{session.cei_suffix}",
                "machines",
                "common",
                "PyEnSightTestData",
            )
            file1_userd = os.path.join(pyensight_test_data_path, filename1)
            file1_session = file1_userd
            if not filename2:
                file2_userd = ""
                file2_session = ""
            else:
                file2_userd = os.path.join(pyensight_test_data_path, filename2)
                file2_session = file2_userd
        return file1_userd, file2_userd, file1_session, file2_session, libuserd, session, data_dir

    return _files
