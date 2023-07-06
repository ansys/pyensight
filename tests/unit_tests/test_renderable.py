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
    web.called_once_with(render.url)


def test_download(mocked_session, mocker):
    render = renderable.Renderable(mocked_session)
    render._url = "http://ansys.com"
    render._download_names = ["John", "Doe"]
    mocker.patch.object(requests, "get")
    mocker.patch.object(shutil, "copyfileobj")
    with mock.patch("builtins.open", mock.mock_open(), create=False):
        assert render.download(".") == ["John", "Doe"]
