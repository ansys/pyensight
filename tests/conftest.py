"""
Global fixtures go here.
"""
import atexit
import subprocess
from unittest import mock

import ansys.pyensight.core
from ansys.pyensight.core import DockerLauncher, LocalLauncher, Session, ensight_grpc
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    This let's you specify the install path when you run pytest:
    $ pytest tests --install-path "/ansys_inc/v231/CEI/bin/ensight"
    TODO: Default must be set to the one on the CI/CD server.
    """
    parser.addoption(
        "--install-path",
        action="store",
        default=f"/ansys_inc/v{ansys.pyensight.core.__ansys_version__}/",
    )
    parser.addoption("--use-local-launcher", default=False, action="store_true")


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
def docker_launcher_session() -> "ansys.pyensight.Session":
    cleanup_docker()
    launcher = DockerLauncher(data_directory=".", use_dev=True)
    launcher.pull()
    session = launcher.start()
    yield session
    session.close()


@pytest.fixture
def mocked_session(mocker, tmpdir) -> "ansys.pyensight.Session":
    cmd_mock = mock.MagicMock("cmd_mock")
    mock_dict = {"a": 1, "b": 2, "c": 3}
    cmd_mock.items = lambda: mock_dict.items()
    mocked_grpc = mock.MagicMock("GRPC")
    mocked_grpc.command = mock.MagicMock("command")
    mocked_grpc.is_connected = lambda: True
    mocked_grpc.connect = mock.MagicMock("execute_connection")
    mocker.patch.object(ensight_grpc, "EnSightGRPC", return_value=mocked_grpc)
    mocker.patch.object(ansys.pyensight.Session, "cmd", return_value=cmd_mock)
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
    return session
