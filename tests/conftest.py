"""
Global fixtures go here.
"""
import atexit
from unittest import mock

import pytest

import ansys.pyensight
from ansys.pyensight import (DockerLauncher, LocalLauncher, Session,
                             ensight_grpc)


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    This let's you specify the install path when you run pytest:
    $ pytest tests --install-path "/ansys_inc/v231/CEI/bin/ensight"
    TODO: Default must be set to the one on the CI/CD server.
    """
    parser.addoption(
        "--install-path",
        action="store",
        default="/ansys_inc/v222/",
    )


@pytest.fixture
def local_launcher_session(pytestconfig: pytest.Config) -> "ansys.pyensight.Session":
    session = LocalLauncher(
        ansys_installation=pytestconfig.getoption("install_path")
    ).start()
    yield session
    session.close()


@pytest.fixture
def docker_launcher_session() -> "ansys.pyensight.Session":
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
