import logging
import os
from unittest import mock

from ansys.pyensight.core import DockerLauncher
import ansys.pyensight.core.session
import docker
import pytest


def test_start(mocker, capsys, caplog):
    os.environ["ANSYSLMD_LICENSE_FILE"] = "1055@mockedserver.com"
    docker_client = mock.MagicMock("Docker")
    run = mock.MagicMock("MockedRun")
    run.exec_run = mock.MagicMock("MockedExec")
    path = "/ansys_inc/v345/CEI/bin/ensight"
    cei_home = path.encode("utf-8")
    values = [
        [0, cei_home],  # first run, to find the ensight version
        [0, "ensight_run"],  # second run
        [0, "websocket_run"],
    ]
    returned = mocker.patch.object(run, "exec_run", side_effect=values.copy())
    docker_client.containers = mock.MagicMock("MockedContainers")
    docker_client.containers.run = mock.MagicMock("MockedContainer")
    mocker.patch.object(docker_client.containers, "run", return_value=run)
    dock = mocker.patch.object(docker, "from_env", return_value=docker_client)
    launcher = DockerLauncher(data_directory=".")
    launcher = DockerLauncher(data_directory=".", use_dev=True, docker_image_name="super_ensight")
    mocked_session = mock.MagicMock("MockedSession")
    mocker.patch.object(ansys.pyensight.core.session, "Session", return_value=mocked_session)
    with caplog.at_level(logging.DEBUG):
        assert launcher.start() == mocked_session
        out, err = capsys.readouterr()
        assert "Ansys Version= 345" in out
        assert (
            "Running command: ['bash', '--login', '-c', ' ensight -batch -v 3"
            in caplog.records[0].message
        )
        assert (
            "Running command: ['bash', '--login', '-c', "
            "'cpython /ansys_inc/v345/CEI/nexus345/nexus_launcher/websocketserver.py "
            "--http_directory /home/ensight" in caplog.records[1].message
        )
    assert launcher.ansys_version() == "345"
    values[0][0] = 1
    returned.side_effect = values.copy()
    with pytest.raises(RuntimeError) as exec_info:
        launcher.start()
    assert "find /ansys_inc/vNNN/CEI/bin/ensight in the Docker container." in str(exec_info)
    values[0][0] = 0
    values[0][1] = "/path/to/darkness".encode("utf-8")
    returned.side_effect = values.copy()
    with pytest.raises(RuntimeError) as exec_info:
        launcher.start()
    assert "find version from cei_home in the Docker container." in str(exec_info)
    dock = mocker.patch.object(docker, "from_env", return_value=docker_client)
    dock.side_effect = ModuleNotFoundError
    with pytest.raises(RuntimeError) as exec_info:
        launcher = DockerLauncher(data_directory=".")
    assert "The pyansys-docker module must be installed for DockerLauncher" in str(exec_info)
    dock.side_effect = KeyError
    with pytest.raises(RuntimeError) as exec_info:
        launcher = DockerLauncher(data_directory=".")
    assert "Cannot initialize Docker" in str(exec_info)


def test_pull(mocker):
    def simulate_network_issue(image):
        raise ConnectionAbortedError

    docker_client = mock.MagicMock("Docker")
    docker_client.images = mock.MagicMock("ImagesInterface")
    docker_client.images.pull = mock.MagicMock("Pull")
    docker_client.images.pull = lambda unused: True
    mocker.patch.object(docker, "from_env", return_value=docker_client)
    launcher = DockerLauncher(data_directory=".")
    launcher.pull()
    docker_client.images.pull = simulate_network_issue
    with pytest.raises(RuntimeError) as exec_info:
        launcher.pull()
    assert "pull Docker image: ghcr.io/ansys-internal/ensight" in str(exec_info)
