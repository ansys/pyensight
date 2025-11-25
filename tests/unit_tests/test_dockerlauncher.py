import logging
import os
from unittest import mock

import ansys
from ansys.pyensight.core import DockerLauncher, enshell_grpc
import docker
import pytest


def test_start(mocker, capsys, caplog, enshell_mock, tmpdir):
    mocked_session = mock.MagicMock("MockedSession")
    mocker.patch.object(ansys.pyensight.core.session, "Session", return_value=mocked_session)
    values_run_command = enshell_mock[1].copy()
    mocker.patch.object(enshell_grpc, "EnShellGRPC", return_value=enshell_mock[0])
    os.environ["ANSYSLMD_LICENSE_FILE"] = "1055@mockedserver.com"
    docker_client = mock.MagicMock("Docker")
    run = mock.MagicMock("MockedRun")
    run.images = mock.MagicMock("DockerImages")
    run.images.pull = lambda x: ""
    docker_client.containers = mock.MagicMock("MockedContainers")
    docker_client.containers.run = mock.MagicMock("MockedContainer")
    mocker.patch.object(docker_client.containers, "run", return_value=run)
    dock = mocker.patch.object(docker, "from_env", return_value=docker_client)
    os.environ["PYENSIGHT_DEBUG"] = "1"
    enshell_mock[0].run_command.side_effect = values_run_command.copy()
    mocker.patch.object(enshell_grpc, "EnShellGRPC", return_value=enshell_mock[0])
    launcher = DockerLauncher(
        data_directory=".", use_dev=True, docker_image_name="super_ensight", timeout=5, use_sos=2
    )
    launcher.start()
    enshell_mock[0].run_command.side_effect = values_run_command.copy()
    mocker.patch.object(enshell_grpc, "EnShellGRPC", return_value=enshell_mock[0])
    launcher = DockerLauncher(
        data_directory=".", use_dev=True, docker_image_name="super_ensight", timeout=5
    )
    with caplog.at_level(logging.DEBUG):
        assert launcher.start() == mocked_session
        out, err = capsys.readouterr()
        assert "Ansys Version= 345" in out
        assert (
            "Running container super_ensight with cmd -app -v 3 -grpc_server"
            in caplog.records[1].message
        )
        assert "Starting EnSight with args: -batch -v 3 -grpc_server" in caplog.records[12].message
    assert launcher.ansys_version() == "345"
    # No data volume
    mocker.patch.object(DockerLauncher, "_is_system_egl_capable", return_value=True)
    os.environ["PYENSIGHT_FORCE_ENSIGHT_EGL"] = "1"
    os.environ["ENSIGHT_ANSYS_LAUNCH"] = "1"
    os.environ["ENSIGHT_ANSYS_APIP_CONFIG"] = "1"
    # Data volume + egl
    enshell_mock[0].run_command.side_effect = values_run_command.copy()
    mocker.patch.object(enshell_grpc, "EnShellGRPC", return_value=enshell_mock[0])
    launcher = DockerLauncher(
        data_directory=".", use_dev=True, docker_image_name="super_ensight", timeout=5, use_egl=True
    )
    launcher.start()
    # No Data Volume + egl
    enshell_mock[0].run_command.side_effect = values_run_command.copy()
    mocker.patch.object(enshell_grpc, "EnShellGRPC", return_value=enshell_mock[0])
    launcher = DockerLauncher(
        use_dev=True, docker_image_name="super_ensight", timeout=5, use_egl=True
    )
    launcher.start()
    enshell_mock[0].run_command.side_effect = values_run_command.copy()
    mocker.patch.object(enshell_grpc, "EnShellGRPC", return_value=enshell_mock[0])
    launcher = DockerLauncher(use_dev=True, docker_image_name="super_ensight", timeout=5)
    launcher.start()
    enshell_mock[0].run_command.side_effect = values_run_command.copy()
    mocker.patch.object(enshell_grpc, "EnShellGRPC", return_value=enshell_mock[0])
    launcher = DockerLauncher(
        data_directory=".", use_dev=True, docker_image_name="super_ensight", timeout=5
    )
    launcher.start()
    enshell_mock[0].run_command.side_effect = values_run_command.copy()
    mocker.patch.object(enshell_grpc, "EnShellGRPC", return_value=enshell_mock[0])
    launcher = DockerLauncher(
        data_directory=".", use_dev=True, docker_image_name="super_ensight", timeout=5, use_sos=3
    )
    launcher.start()
    values_run_command[0] = [1, "cannot set no reroute"]
    enshell_mock[0].run_command.side_effect = values_run_command.copy()
    with pytest.raises(RuntimeError) as exec_info:
        launcher.start()
    assert (
        "Error sending EnShell command: set_no_reroute_log ret: [1, 'cannot set no reroute']"
        in str(exec_info)
    )
    values_run_command[0] = [0, "set_no_reroute_log"]
    enshell_mock[0].run_command.side_effect = values_run_command.copy()
    mocker.patch.object(enshell_grpc, "EnShellGRPC", return_value=enshell_mock[0])
    dock = mocker.patch.object(docker, "from_env", return_value=docker_client)
    dock.side_effect = ModuleNotFoundError
    with pytest.raises(RuntimeError) as exec_info:
        launcher = DockerLauncher(
            data_directory=".", grpc_disable_tls=True, grpc_use_tcp_sockets=True
        )
    assert "The docker module must be installed for DockerLauncher" in str(exec_info)
    dock.side_effect = KeyError
    with pytest.raises(RuntimeError) as exec_info:
        launcher = DockerLauncher(
            data_directory=".", grpc_disable_tls=True, grpc_use_tcp_sockets=True
        )
    assert "Cannot initialize Docker" in str(exec_info)


def test_pull(mocker):
    def simulate_network_issue(image):
        raise ConnectionAbortedError

    docker_client = mock.MagicMock("Docker")
    docker_client.images = mock.MagicMock("ImagesInterface")
    docker_client.images.pull = mock.MagicMock("Pull")
    docker_client.images.pull = lambda unused: True
    mocker.patch.object(docker, "from_env", return_value=docker_client)
    launcher = DockerLauncher(data_directory=".", grpc_disable_tls=True, grpc_use_tcp_sockets=True)
    launcher.pull()
    docker_client.images.pull = simulate_network_issue
    with pytest.raises(RuntimeError) as exec_info:
        launcher.pull()
    assert "pull Docker image: ghcr.io/ansys-internal/ensight" in str(exec_info)
    assert launcher._get_host_port("http://ensight.com:3000") == ("ensight.com", 3000)
