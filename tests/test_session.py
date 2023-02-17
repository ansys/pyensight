"""Unit tests for session.py"""
import os
import platform
from unittest import mock
import webbrowser

import pytest

import ansys.pyensight
from ansys.pyensight import Launcher, LocalLauncher, ensobjlist
import ansys.pyensight.renderable


def test_session_without_installation() -> None:
    """todo: just a stub. Remove and write actual tests like below"""
    version = ansys.pyensight.__ansys_version__
    # In case tests are launched locally and the environment variable is
    # set, the launcher would manage to find an install. This trick
    # avoids it
    if f"AWP_ROOT{version}" in os.environ:
        del os.environ[f"AWP_ROOT{version}"]
    with pytest.raises(RuntimeError) as exec_info:
        session = LocalLauncher().start()
        session.close()
    assert "Unable to detect an EnSight installation" in str(exec_info)


def test_show(mocked_session, mocker):
    session = mocked_session
    session.ensight.objs.core.TIMESTEP = 1
    session.ensight.objs.core.TIMESTEP_LIMITS = [0, 5]
    vars = mock.MagicMock("EnSightVARS")
    pressure_mock = mock.MagicMock("Pressure")
    density_mock = mock.MagicMock("Density")
    pressure_mock.DESCRIPTION = "Pressure"
    density_mock.DESCRIPTION = "Density"
    vars.find = lambda val, str: [pressure_mock, density_mock]
    session.ensight.objs.core.VARIABLES = vars
    filename = f"{session._launcher.session_directory}/remote_filename"
    mocker.patch.object(
        ansys.pyensight.renderable.Renderable,
        "_generate_filename",
        return_value=(f"{filename}", "remote_filename"),
    )
    stream_mock = mock.MagicMock("stream")
    stream_mock.side_effect = lambda *args, **kwargs: 6
    session.ensight.dsg_new_stream = stream_mock
    update_mock = mock.MagicMock("update")
    update_mock.side_effect = lambda *args, **kwargs: True
    session.ensight.dsg_new_stream = stream_mock
    session.ensight.dsg_save_update = update_mock
    session.show()
    session.show("webgl")
    session.show("remote")
    session.show("remote_scene")
    session.show("deep_pixel")
    session.show("animation")
    session._cei_suffix = "232"
    session.show("sgeo")
    session._cei_suffix = "211"
    session.show("sgeo")
    with pytest.raises(RuntimeError) as exec_info:
        session.show("3DVRRendering")
    assert "Unable to generate requested visualization" in str(exec_info)
    session._html_port = None
    with pytest.raises(RuntimeError) as exec_info:
        session.show()
    assert "No websocketserver has been associated with this Session" in str(exec_info)


def test_exec(mocked_session):
    def function(*args, **kwargs):
        return True

    session = mocked_session
    session._cei_suffix = 211
    fargs = ["1", "2"]
    fkwargs = {"a": 3, "b": 4}
    with pytest.raises(RuntimeError):
        session.exec(function, *fargs, remote=True, **fkwargs)
    session._cei_suffix = 232
    session._ensight_python_version("4", "5", "23")
    with pytest.raises(RuntimeError):
        session.exec(function, *fargs, remote=True, **fkwargs)
    session.cmd = lambda *args, **kwargs: "Bob"
    session._ensight_python_version = platform.python_version_tuple()
    assert session.exec(function, *fargs, remote=True, **fkwargs) == "Bob"
    assert session.exec(function, *fargs, remote=False, **fkwargs) is True


def test_session_load_data(mocked_session):
    session = mocked_session
    session.cmd = lambda *args, **kwargs: 0
    case = mock.MagicMock("EnSightCase")
    case.DESCRIPTION = "CurrentCase"
    session.ensight.objs.core.CURRENTCASE = [case]
    session.load_data(
        data_file="/stairway/to/heaven",
        result_file="/path/do/darkness",
        file_format=".mobi",
        reader_options={"a": 1, "b": 2},
        new_case=False,
        representation="3D_feature_2D_full",
    )
    session.load_data(
        data_file="/stairway/to/heaven",
        file_format=".mobi",
        new_case=False,
        representation="3D_feature_2D_full",
    )
    case = mock.MagicMock("EnSightCase")
    case.DESCRIPTION = "CurrentCase"
    case.ACTIVE = 0
    session.ensight.objs.core.CASES = [case]
    session.load_data(
        data_file="/stairway/to/heaven",
        result_file="/path/do/darkness",
        file_format=".mobi",
        reader_options={"a": 1, "b": 2},
        new_case=True,
        representation="3D_feature_2D_full",
    )
    case.ACTIVE = 1
    with pytest.raises(RuntimeError):
        session.load_data(
            data_file="/stairway/to/heaven",
            result_file="/path/do/darkness",
            file_format=".mobi",
            reader_options={"a": 1, "b": 2},
            new_case=True,
            representation="3D_feature_2D_full",
        )
    session.cmd = mock.MagicMock("envision_cmd")
    session.cmd.side_effect = ["envision", 0]
    session.load_data(
        data_file="/stairway/to/heaven",
        result_file="/path/do/darkness",
        file_format=".mobi",
        reader_options={"a": 1, "b": 2},
        new_case=True,
        representation="3D_feature_2D_full",
    )
    session.cmd.side_effect = ["envision", -1]
    with pytest.raises(RuntimeError):
        session.load_data(
            data_file="/stairway/to/heaven",
            result_file="/path/do/darkness",
            file_format=".mobi",
            reader_options={"a": 1, "b": 2},
            new_case=True,
            representation="3D_feature_2D_full",
        )
    session.cmd = mock.MagicMock("fileformat_cmd")
    session.cmd.side_effect = [0] * 7 + [".cas"] + [0] * 12
    session.load_data(
        data_file="/stairway/to/heaven",
        result_file="/path/do/darkness",
        reader_options={"a": 1, "b": 2},
        new_case=False,
        representation="3D_feature_2D_full",
    )
    session.cmd.side_effect = [0] * 7 + [RuntimeError] + [0] * 12
    with pytest.raises(RuntimeError) as exec_info:
        session.load_data(
            data_file="/stairway/to/heaven",
            result_file="/path/do/darkness",
            reader_options={"a": 1, "b": 2},
            new_case=False,
            representation="3D_feature_2D_full",
        )
    assert "Unable to determine file format for /stairway/to/heaven" in str(exec_info)
    session.cmd.side_effect = [0] * 7 + [".encas"] + [0] * 11 + [-1]
    with pytest.raises(RuntimeError) as exec_info:
        session.load_data(
            data_file="/stairway/to/heaven",
            result_file="/path/do/darkness",
            reader_options={"a": 1, "b": 2},
            new_case=False,
            representation="3D_feature_2D_full",
        )
    assert "Unable to load the dataset." in str(exec_info)


def test_load_example(mocked_session, mocker):
    session = mocked_session
    cmd = mocker.patch.object(session, "cmd")
    session.load_example("large_dataset")
    args = cmd.call_args.args
    assert "import requests" in args[0]
    assert "https://s3.amazonaws.com/www3.ensight.com/PyEnSight/ExampleData" in args[0]
    session.load_example("large_dataset", "www.ansys.com")
    args = cmd.call_args.args
    assert "www.ansys.com" in args[0]


def test_callbacks(mocked_session, mocker):
    session = mocked_session
    cmd = mocker.patch.object(session, "cmd", return_value=1)
    session._grpc.event_stream_enable = mock.MagicMock("stream")
    session._grpc.prefix = lambda: ""
    session.add_callback(
        "test",
        "vport?w={{WIDTH}}&h={{HEIGHT}}&x={{ORIGINX}}&y={{ORIGINY}}",
        ["a", "b"],
        print,
    )
    assert session._callbacks["vport"] == (1, print)
    with pytest.raises(RuntimeError) as exec_info:
        session.add_callback("test", "vport", ["a", "b"], print)
    assert "A callback for vport already exists"
    session.add_callback("test", "partlist", ["a", "b"], print)
    assert session._callbacks["partlist"] == (1, print)
    session.add_callback("test", "variablelist", ["a", "b"], print, compress=False)
    target = mock.MagicMock("testtarget")
    target.__OBJID__ = 12
    session.add_callback(target, "statelist", ["a", "b"], print, compress=False)
    session.remove_callback("statelist")
    with pytest.raises(RuntimeError) as exec_info:
        session.remove_callback("geomlist")
    assert "A callback for tag 'geomlist' does not exist" in str(exec_info)
    cmd = mock.MagicMock("event_cmd")
    cmd.find = mock.MagicMock("magic find")
    cmd.find.side_effect = [1, 5]
    url = "grpc://abcd1234-5678efgh/vport?enum=1&uid=0"
    session._event_callback(url)
    url = "grpc://abcd1234-5678efgh/?tag&vport?enum=1&uid=0"
    session._event_callback(url)
    session._callbacks.clear()


def test_convert_ctor(mocked_session, mocker):
    session = mocked_session
    value = session._convert_ctor("Class: ENS_GLOBALS, CvfObjID: 221, cached:yes")
    assert value == "session.ensight.objs.ENS_GLOBALS(session, 221)"
    cmd = mocker.patch.object(session, "cmd", return_value=0)
    value = session._convert_ctor("Class: ENS_PART, desc: 'Sphere', CvfObjID: 1078, cached:no")
    assert (
        value
        == "session.ensight.objs.ENS_PART_MODEL(session, 1078,attr_id=1610612792, attr_value=0)"
    )
    cmd.return_value = 3
    value = session._convert_ctor("Class: ENS_ANNOT, desc: 'Pressure', CvfObjID: 4761, cached:no")
    assert (
        value
        == "session.ensight.objs.ENS_ANNOT_LGND(session, 4761,attr_id=1610612991, attr_value=3)"
    )
    cmd.return_value = 6
    value = session._convert_ctor("Class: ENS_TOOL, desc: 'Sphere', CvfObjID: 763, cached:no")
    assert (
        value
        == "session.ensight.objs.ENS_TOOL_SPHERE(session, 763,attr_id=1610613030, attr_value=6)"
    )
    session._ensobj_hash = {i: i for i in range(10000000)}
    value = session._convert_ctor("Class: ENS_GLOBALS, CvfObjID: 221, cached:yes")
    assert value == "session.ensight.objs.ENS_GLOBALS(session, 221)"
    session._convert_ctor("test")
    session._convert_ctor("CvfObjID: 221, Class: ENS_GLOBALS, cached:yes")
    session._convert_ctor("CvfObjID: 221, Class: ENS_GLOBALS, cachedcachedcached:yes")
    object = mock.MagicMock("Test")
    object.__OBJID__ = 763
    session.add_ensobj_instance(object)
    assert session.obj_instance(763) == object
    value = session._convert_ctor("Class: ENS_TOOL, desc: 'Sphere', CvfObjID: 763, cached:no")
    assert value == "session.obj_instance(763)"


def test_close(mocked_session, mocker):
    session = mocked_session
    session._grpc.shutdown = mock.MagicMock("shutdown")
    session.close()
    session._halt_ensight_on_close = True
    session._launcher = Launcher()
    session = mocked_session
    with pytest.raises(RuntimeError) as exec_info:
        session.close()
    assert "Session not associated with this Launcher" in str(exec_info)


def test_render(mocked_session):
    mocked_session.grpc.render = mock.MagicMock("render")
    mocked_session.render(300, 400, 5)
    mocked_session.grpc.render.assert_called_once()


def test_geometry(mocked_session):
    mocked_session.grpc.geometry = mock.MagicMock("render")
    mocked_session.geometry()
    mocked_session.grpc.geometry.assert_called_once()


def test_properties(mocked_session):
    assert mocked_session.timeout == 120.0
    mocked_session.timeout = 113.5
    assert mocked_session.language == "en"
    assert mocked_session.halt_ensight_on_close == False
    mocked_session._cei_home = "/new/path"
    mocked_session._cei_suffix = "178"
    assert mocked_session.cei_home == "/new/path"
    assert mocked_session.cei_suffix == "178"
    assert mocked_session.jupyter_notebook == False
    mocked_session._jupyter_notebook = True
    assert mocked_session.jupyter_notebook == True


def test_help(mocked_session, mocker):
    web = mocker.patch.object(webbrowser, "open")
    mocked_session.help()
    web.assert_called_once_with("https://furry-waffle-422870de.pages.github.io/")


"""
def test_close(local_launcher_session) -> None:
    local_launcher_session.close()
    assert local_launcher_session.launcher is None
"""
