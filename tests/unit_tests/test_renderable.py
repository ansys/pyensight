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

import shutil
from unittest import mock
import webbrowser

from ansys.pyensight.core import launcher, renderable
import requests


def test_generate_filename(mocked_session):
    render = renderable.Renderable(mocked_session)
    render._url = "http://ansys.com"
    assert repr(render) == f"Renderable( url='{render.url}' )"
    mocked_session.launcher = launcher.Launcher()
    mocked_session.launcher.session_directory = "/this/path"
    filename = f"{render._session.secret_key}_{render._guid}_{render._filename_index}.png"
    assert render._generate_filename(".png") == (f"/this/path/{filename}", filename)


def test_browser(mocked_session, mocker):
    render = renderable.Renderable(mocked_session)
    render._url = "http://ansys.com"
    web = mocker.patch.object(webbrowser, "open")
    render.browser()
    web.assert_called_once_with(render.url)


def test_download(mocked_session, mocker):
    render = renderable.Renderable(mocked_session)
    render._url = "http://ansys.com"
    render._download_names = ["John", "Doe"]
    mocker.patch.object(requests, "get")
    mocker.patch.object(shutil, "copyfileobj")
    with mock.patch("builtins.open", mock.mock_open(), create=False):
        assert render.download(".") == ["John", "Doe"]
