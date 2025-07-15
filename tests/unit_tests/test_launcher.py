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

from unittest import mock

from ansys.pyensight.core.common import find_unused_ports
from ansys.pyensight.core.launcher import Launcher
import pytest
import requests


def test_find_unused_port(mocker):
    found = find_unused_ports(2)
    assert len(found) == 2
    found = find_unused_ports(1, avoid=[1000, 1001])
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
