from unittest import mock

import pytest
import requests

from ansys.pyensight import Launcher


def test_find_unused_port(mocker):
    launcher = Launcher()
    found = launcher._find_unused_ports(2)
    assert len(found) == 2
    found = launcher._find_unused_ports(1, avoid=[1000, 1001])
    assert found not in [1000, 1001]


def test_close(mocked_session, mocker):
    launcher = Launcher()
    with pytest.raises(RuntimeError) as exec_info:
        launcher.close(mocked_session)
    assert "Session not associated with this Launcher" in str(exec_info)
    launcher._sessions.append(mocked_session)
    mocked_session._grpc.shutdown = mock.MagicMock("shutdown")
    mocker.patch.object(requests, "get")
    launcher.close(mocked_session)
    mock1 = mock.MagicMock("mock1")
    mock1.grpc = mock.MagicMock("grpc")
    mock1.grpc.shutdown = mock.MagicMock("shutdown")
    mock2 = mock.MagicMock("mock2")
    mock2.grpc = mock.MagicMock("grpc")
    mock2.grpc.shutdown = mock.MagicMock("shutdown")
    mock2.hostname = "workstation"
    mock2.html_port = 34567
    launcher._sessions.append(mock1)
    launcher._sessions.append(mock2)
    launcher.close(mock1)
    mock2.secret_key = "abcd1234"
    launcher.close(mock2)
