import os
import pathlib
import time

from ansys.pyensight.core import DockerLauncher, LocalLauncher, launch_ensight
from ansys.pyensight.core.enscontext import EnsContext
from ansys.pyensight.core.utils.parts import convert_part, convert_variable
from ansys.pyensight.core.utils.variables import vec_mag
import pytest


def test_coverage_increase(tmpdir, pytestconfig: pytest.Config):
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    install_path = pytestconfig.getoption("install_path")
    root = None
    if use_local:
        launcher = LocalLauncher(ansys_installation=install_path)
        root = "http://s3.amazonaws.com/www3.ensight.com/PyEnSight/ExampleData"
    else:
        launcher = DockerLauncher(
            data_directory=data_dir, use_dev=True, grpc_disable_tls=True, grpc_use_tcp_sockets=True
        )
    session = launcher.start()
    if not use_local:
        launcher._enshell.host
        launcher._enshell.port
        launcher._enshell.run_command("printenv")
        launcher._enshell.run_command_with_env("printenv", "ENSIGHT_ANSYS_ALPHA_FLAG=1")
    with open(os.path.join(data_dir, "test_exec_run_script.py"), "w") as _file:
        _file.write("")
    os.mkdir(os.path.join(data_dir, "test_dir"))
    with open(os.path.join(data_dir, "test_dir", "second_script.py"), "w") as _file:
        _file.write("")
    session.run_script(os.path.join(data_dir, "test_exec_run_script.py"))
    session.run_script(os.path.join(data_dir, "test_exec_run_script.py"))
    session.copy_to_session(
        pathlib.Path(os.path.join(data_dir, "test_exec_run_script.py")).parents[0].as_uri(),
        ["test_exec_run_script.py"],
        remote_prefix="files",
        progress=True,
    )
    session.copy_to_session(
        pathlib.Path(data_dir).as_uri(),
        ["test_dir"],
    )
    with pytest.raises(RuntimeError):
        session.copy_to_session(
            "grpc:///", ["test_exec_run_script.py"], remote_prefix="files", progress=True
        )
    if not use_local:
        session.copy_from_session("file:///data", ["test_exec_run_script.py"], progress=True)
        session.copy_from_session(
            "file:///data",
            ["test_dir"],
        )
        session.copy_from_session(
            "file:///data", ["test_exec_run_script.py"], remote_prefix="files", progress=True
        )
        with pytest.raises(RuntimeError):
            session.copy_from_session(
                "grpc:///",
                [os.path.basename(os.path.dirname(__file__))],
            )
    vec_mag([0, 1])
    session.language = "zh"
    session.language = "en"
    session.halt_ensight_on_close = False
    session.halt_ensight_on_close = True
    session.jupyter_notebook = True
    session.jupyter_notebook = False
    assert session.sos is False
    session.load_example("waterbreak.ens", root=root)
    session.ensight.utils.variables.calculator.area(["leftWall"])
    assert session.ensight.utils.variables.get_const_val("Area_0", ["leftWall"]) > 0
    session.ensight.utils.variables.get_const_vars()
    session.ensight.utils.variables.get_const_var_names()
    temp_part = session.ensight.objs.core.PARTS.find(1, attr="PARTNUMBER")[0]
    convert_part(session.ensight, temp_part)
    convert_variable(session.ensight, session.ensight.objs.core.VARIABLES[0])
    session.ensight.utils.export._numpy_to_dict(None)
    session.ensight.utils.export._numpy_from_dict(None)
    context = session.capture_context()
    context.save("test.ctxz")
    context2 = EnsContext("test.ctxz")
    with pytest.raises(RuntimeError):
        context2.load("test.zippp")
    session.ensight.utils.variables._check_for_var_elem(
        "alpha1", session.ensight.objs.core.PARTS["default_region"[0]]
    )
    session.ensight.utils.variables._move_var_to_elem(
        session.ensight.objs.core.PARTS, session.ensight.objs.core.VARIABLES["alpha1"][0]
    )
    session.ensight.utils.variables._calc_var(None, None)
    try:
        session.ensight.utils.variables._calc_var(
            session.ensight.objs.core.PARTS["default_region"[0]], "test"
        )
    except RuntimeError:
        pass
    core = session.ensight.objs.core
    core.PARTS.set_attr("COLORBYPALETTE", "alpha1")
    export = session.ensight.utils.export
    export.image(os.path.join(data_dir, "test.png"))
    export.image(os.path.join(data_dir, "test.png"), width=800, height=600)
    export.image(os.path.join(data_dir, "test.tiff"), enhanced=True)
    export.animation(os.path.join(data_dir, "test.mp4"), anim_type=export.ANIM_TYPE_SOLUTIONTIME)
    export.animation(
        os.path.join(data_dir, "test.mp4"),
        anim_type=export.ANIM_TYPE_SOLUTIONTIME,
        format_options=None,
    )
    export.animation(
        os.path.join(data_dir, "test.mp4"),
        anim_type=export.ANIM_TYPE_SOLUTIONTIME,
        width=800,
        height=600,
        frames=30,
        frames_per_second=80,
        starting_frame=2,
        format_options="Quality High Type 2",
    )
    export.animation(
        os.path.join(data_dir, "test_ray.mp4"),
        anim_type=export.ANIM_TYPE_SOLUTIONTIME,
        width=800,
        height=600,
        frames=30,
        frames_per_second=80,
        starting_frame=2,
        format_options="Quality High Type 2",
        raytrace=True,
    )
    session.ensight.anim_flipbook.begin_time_step(0)
    session.ensight.anim_flipbook.end_time_step(20)
    session.ensight.anim_flipbook.specify_time_as("step")
    session.ensight.anim_flipbook.load()
    export.animation(
        os.path.join(data_dir, "test2.mp4"),
        anim_type=export.ANIM_TYPE_FLIPBOOK,
        width=800,
        height=600,
        frames_per_second=80,
        starting_frame=2,
    )
    session.ensight.anim_keyframe.keyframing("ON")
    session.ensight.anim_keyframe.create_keyframe()
    session.ensight.view_transf.rotate(11.4172411, -36.7627106, 0)
    session.ensight.anim_keyframe.create_keyframe()
    export.animation(
        os.path.join(data_dir, "test3.mp4"),
        anim_type=export.ANIM_TYPE_KEYFRAME,
        width=800,
        height=600,
        frames_per_second=80,
        starting_frame=2,
    )
    session.ensight.part.select_begin(6)
    session.ensight.command.delay_refresh("ON")
    session.ensight.variables.activate("u")
    session.ensight.ptrace.select_default()
    session.ensight.ptrace.variable("u")
    session.ensight.part.select_all()
    session.ensight.ptrace.create_bypart(6, 100)
    session.ensight.part.select_lastcreatedpart()
    session.ensight.part.colorby_palette("u")
    session.ensight.command.delay_refresh("OFF")
    session.ensight.part.select_lastcreatedpart()
    session.ensight.part.colorby_palette("u")
    session.ensight.command.delay_refresh("OFF")
    export.animation(
        os.path.join(data_dir, "test4.mp4"),
        anim_type=export.ANIM_TYPE_ANIMATEDTRACES,
        width=800,
        height=600,
        frames=30,
        frames_per_second=80,
        starting_frame=2,
    )
    with pytest.raises(RuntimeError):
        export.animation(
            os.path.join(data_dir, "test4.mp4"),
            anim_type=export.ANIM_TYPE_ANIMATEDTRACES,
            width=800,
            height=600,
            frames_per_second=80,
            starting_frame=2,
        )
    parts = session.ensight.utils.parts
    parts.select_parts_invert()
    session.ensight.objs.core.PARTS[0].setmetatag("test_tag1", "3")
    assert (
        parts.select_parts_by_tag(tag="test_tag1", value="3")[0]
        == session.ensight.objs.core.PARTS[0]
    )
    assert parts.select_parts_by_tag(tag="TEST", value="val") == []
    assert parts.select_parts_by_tag(tag="TEST") == []
    assert parts.select_parts_by_tag(value="val") == []
    assert parts.select_parts_by_tag() == session.ensight.objs.core.PARTS
    assert parts.select_parts_by_tag(tagdict={"TEST": "VAL"}) == []
    assert parts.select_parts_by_tag(tagdict={}) == session.ensight.objs.core.PARTS
    views = session.ensight.utils.views
    views._normalize_vector([0, 0, 0])
    views.set_view_direction(1, 1, 1)
    views.set_view_direction(-1, 1, 1)
    views.set_view_direction(-1, -1, 1)
    views.set_view_direction(-1, -1, -1)
    views.set_view_direction(1, -1, 1)
    views.set_view_direction(1, -1, -1)
    views.set_view_direction(1, 1, -1)
    views.set_view_direction(-1, 1, -1)
    views.set_view_direction(-1, -1, 1)
    views.set_center_of_transform(0, 1, 2)
    views.compute_model_centroid()
    views.compute_model_centroid()
    views.set_view_direction(1, 1, 1, perspective=True)
    views.save_current_view("test")
    views.save_current_view("")
    views.restore_view("test")
    with pytest.raises(KeyError):
        views.restore_view("non_existing_view")
    views.restore_center_of_transform()
    views.reinitialize_view()
    views._convert_rotation_matrix_to_quaternion([1, 0, 0], [0, -1, 0], [0, 0, -3])
    views._convert_rotation_matrix_to_quaternion([-5, 0, 0], [0, 2, 0], [0, 0, 1])
    views._convert_rotation_matrix_to_quaternion([-5, 0, 0], [0, 1, 0], [0, 0, 2])
    views.set_view_direction(1, 1, 1)
    session.ensight.tools.line("ON")
    query = session.ensight.utils.query
    query.create_distance(
        "line",
        query.DISTANCE_LINE,
        session.ensight.objs.core.PARTS["defaultFaces"],
        "alpha1",
        point1=[1.918665e-01, 3.840137e-01, 2.539995e-02],
        point2=[1.918665e-01, 1.069867e-01, 2.539995e-02],
    )
    session.ensight.view_transf.spline_new()
    session.ensight.view_transf.splinepoint_create(0.255759448, 0.291166872, 0.025399996)
    session.ensight.view_transf.splinepoint_create(0.302727759, 0.306592941, 0.0253999885)
    session.ensight.view_transf.splinepoint_create(0.369678676, 0.318534851, 0.0254000034)
    session.ensight.view_transf.splinepoint_create(0.412878871, 0.329110414, 0.0253999978)
    session.ensight.view_transf.splinepoint_create(0.457060218, 0.365240633, 0.0253999904)
    session.ensight.view_transf.splinepoint_create(0.453760058, 0.382999331, 0.0253999867)
    query.create_distance(
        "spline query", query.DISTANCE_SPLINE, ["defaultFaces"], "alpha1", spline_name="new_spline0"
    )
    query.create_temporal(
        "temporal_query",
        query.TEMPORAL_NODE,
        parts.select_parts_by_tag(),
        "alpha1",
        node_id=13198,
    )
    query.create_temporal(
        "temporal_query",
        query.TEMPORAL_ELEMENT,
        parts.select_parts_by_tag(),
        "alpha1",
        element_id=21161,
    )
    query.create_temporal(
        "temporal_query",
        query.TEMPORAL_MINIMUM,
        parts.select_parts_by_tag(),
        "alpha1",
    )
    query.create_temporal(
        "temporal_query",
        query.TEMPORAL_MAXIMUM,
        parts.select_parts_by_tag(),
        "alpha1",
    )
    with pytest.raises(ValueError):
        # Varoa;e mpt existing
        query.create_distance(
            "spline", query.DISTANCE_SPLINE, [6], "alpha15", spline_name="0-new_spline0"
        )
    session.ensight.objs.core.PARTS[0].getattrs(["VISIBLE", "DESCRIPTION"])
    session.ensight.objs.core.PARTS[0].getattrs()
    session.ensight.objs.core.PARTS[0].attrtree()
    session.ensight.objs.core.PARTS[0].attrinfo()
    session.ensight.objs.core.PARTS[0].attrtree(filter=parts.select_parts_by_dimension(3))
    session.ensight.objs.core.PARTS[0].attrtree(include=session.ensight.objs.enums.VISIBLE)
    session.ensight.objs.core.PARTS[0].attrtree(exclude=session.ensight.objs.enums.VISIBLE)
    session.ensight.objs.core.PARTS[0].attrtree(group_include=session.ensight.objs.enums.VISIBLE)
    session.ensight.objs.core.PARTS[0].attrtree(group_exclude=session.ensight.objs.enums.VISIBLE)
    session.ensight.objs.core.PARTS[0].attrinfo("VISIBLE")
    session.ensight.objs.core.PARTS[0].attrissensitive("VISIBLE")
    session.ensight.objs.core.PARTS[0].setattr_begin()
    session.ensight.objs.core.PARTS[0].setattr_end()
    session.ensight.objs.core.PARTS[0].setattr_status()
    session.ensight.objs.core.PARTS[0].setmetatag("ENS_KIND", "fluid")
    session.ensight.objs.core.PARTS[0].hasmetatag("ENS_KIND")
    session.ensight.objs.core.PARTS[0].getmetatag("ENS_KIND")
    session.ensight.objs.core.PARTS.find(True, "VISIBLE")
    session.ensight.objs.core.PARTS.find(True, "VISIBLE", wildcard=1)
    session.ensight.objs.core.PARTS.find(True, "VISIBLE", wildcard=2)
    session.ensight.objs.core.PARTS.set_attr("VISIBLE", True)
    str(session.ensight.objs.core.PARTS[0])
    str(session.ensight.objs.core.TEXTURES[0])
    if not use_local:
        launcher.enshell_log_contents()
    assert session.ensight.objs.core.PARTS[0] != session.ensight.objs.core.PARTS[1]
    counter = 0
    success = False
    while not success and counter < 5:
        try:
            cas_file = session.download_pyansys_example(
                "mixing_elbow.cas.h5", "pyfluent/mixing_elbow"
            )
            dat_file = session.download_pyansys_example(
                "mixing_elbow.dat.h5", "pyfluent/mixing_elbow"
            )
            success = True
        except Exception:
            counter += 1
            time.sleep(60)
    if counter == 5 and not success:
        raise RuntimeError("Couldn't download data from github")
    session.load_data(cas_file, result_file=dat_file)
    #
    assert session.ensight_version_check("2021 R1")
    assert session.ensight_version_check("211")
    try:
        session.ensight_version_check("2100 R2")
        assert False
    except Exception:
        pass
    assert session.grpc.port() == session._grpc_port
    assert session.grpc.host == session._hostname
    assert session.grpc.security_token == session._secret_key
    session.close()


def test_particle_traces_and_geometry(tmpdir, pytestconfig: pytest.Config):
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    root = None
    if use_local:
        launcher = LocalLauncher(enable_rest_api=True)
        root = "http://s3.amazonaws.com/www3.ensight.com/PyEnSight/ExampleData"
    else:
        launcher = DockerLauncher(
            data_directory=data_dir,
            use_dev=True,
            enable_rest_api=True,
            grpc_disable_tls=True,
            grpc_use_tcp_sockets=True,
        )
    session = launcher.start()
    session.load_example("waterbreak.ens", root=root)
    session.show("webensight")
    session.show("webgl")
    session.show("remote")._update_2023R2_or_less()
    parts = session.ensight.utils.parts
    export = session.ensight.utils.export
    session.ensight.objs.core.PARTS.set_attr("COLORBYPALETTE", "alpha1")
    session.ensight.objs.core.PARTS[0].setmetatag("testtag", None)
    export.geometry("test.glb", format=export.GEOM_EXPORT_GLTF, starting_timestep=0)
    export.geometry(
        "second_test.glb", format=export.GEOM_EXPORT_GLTF, starting_timestep=0, frames=-1
    )
    assert os.path.exists("test.glb")
    for i in range(20):
        assert os.path.exists(f"second_test{str(i).zfill(3)}.glb")
    point_pt = parts.create_particle_trace_from_points(
        "test", "u", points=[[0.01, 0.1, 0]], source_parts=parts.select_parts_by_dimension(3)
    )
    line_pt = parts.create_particle_trace_from_line(
        "test2",
        "u",
        point1=[0.01, 0.1, -0.02],
        point2=[0.01, 0.1, 0.02],
        source_parts=parts.select_parts_by_dimension(3),
        pathlines=True,
        emit_time=0.0,
        total_time=1.0,
        delta_time=0.025,
        num_points=3,
    )
    plane_pt = parts.create_particle_trace_from_plane(
        "test3",
        5,
        direction=parts.PT_NEG_TIME,
        source_parts=parts.select_parts_by_dimension(3),
        point1=[0.5, 0.2, 0.013],
        point2=[0.5, 0.2, -0.002],
        point3=[0.5, 0.35, -0.002],
        num_points_x=4,
        num_points_y=5,
    )
    part_pt = parts.create_particle_trace_from_parts(
        "test4",
        "u",
        source_parts=parts.select_parts_by_dimension(3),
        parts=["leftWall"],
        num_points=10,
    )
    parts.create_particle_trace_from_parts(
        "test10",
        "u",
        source_parts=parts.select_parts_by_dimension(3),
        parts=["leftWall"],
        num_points=10,
        surface_restrict=True,
    )
    parts.add_emitter_parts_to_particle_trace_part(
        part_pt, parts=["lowerWall"], num_points=5, part_distribution_type=parts.PART_EMIT_FROM_AREA
    )
    parts.add_emitter_points_to_particle_trace_part(
        point_pt,
        points=[[0.02, 0.1, 0]],
    )
    parts.add_emitter_line_to_particle_trace_part(
        line_pt, point1=[0.02, 0.1, -0.02], point2=[0.02, 0.1, 0.02], num_points=3
    )
    parts._find_palette("alpha1")
    with pytest.raises(RuntimeError):
        parts._find_palette("alpha2")
    parts.select_parts(None)
    parts.get_part_id_obj_name(session.ensight.objs.core.PARTS, ret_flag=None)
    parts.get_part_id_obj_name(session.ensight.objs.core.PARTS[0])
    parts.get_part_id_obj_name([1, 2], "name")
    parts.get_part_id_obj_name(["1", "2"], "obj")
    temp_part = parts.add_emitter_plane_to_particle_trace_part(
        plane_pt,
        point1=[0.3, 0.2, 0.013],
        point2=[0.3, 0.2, -0.002],
        point3=[0.3, 0.35, -0.002],
        num_points_x=4,
        num_points_y=5,
    )
    temp_part.destroy()


def test_sos(tmpdir, pytestconfig: pytest.Config):
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    is_docker = False
    if use_local:
        launcher = LocalLauncher(use_sos=2)
    else:
        is_docker = True
        launcher = DockerLauncher(
            data_directory=data_dir,
            use_dev=True,
            use_sos=2,
            grpc_disable_tls=True,
            grpc_use_tcp_sockets=True,
        )
    session = launcher.start()
    session.load_data(f"{session.cei_home}/ensight{session.cei_suffix}/data/cube/cube.case")
    assert session.grpc.port() == session._grpc_port
    assert session.grpc.host == session._hostname
    assert session.grpc.security_token == session._secret_key
    session.close()
    if is_docker:
        session = launch_ensight(
            use_docker=True,
            use_dev=True,
            data_directory=data_dir,
            grpc_disable_tls=True,
            grpc_use_tcp_sockets=True,
        )
        assert session._launcher._enshell.host() == session._hostname
        session._launcher._enshell.port()
        session._launcher._enshell.metadata()
        _parts = session.ensight.objs.core.PARTS
        session.ensight.utils.parts.get_part_id_obj_name(_parts, "id")
        session.ensight.utils.parts.get_part_id_obj_name(_parts, "name")
        session.ensight.utils.parts.get_part_id_obj_name(_parts, "obj")
        _parts = [p.ID for p in session.ensight.objs.core.PARTS]
        session.ensight.utils.parts.get_part_id_obj_name(_parts, "id")
        session.ensight.utils.parts.get_part_id_obj_name(_parts, "name")
        session.ensight.utils.parts.get_part_id_obj_name(_parts, "obj")
        _parts = [f"{p.ID}" for p in session.ensight.objs.core.PARTS]
        session.ensight.utils.parts.get_part_id_obj_name(_parts, "id")
        session.ensight.utils.parts.get_part_id_obj_name(_parts, "name")
        session.ensight.utils.parts.get_part_id_obj_name(_parts, "obj")
        _parts = [p.DESCRIPTION for p in session.ensight.objs.core.PARTS]
        session.ensight.utils.parts.get_part_id_obj_name(_parts, "id")
        session.ensight.utils.parts.get_part_id_obj_name(_parts, "name")
        session.ensight.utils.parts.get_part_id_obj_name(_parts, "obj")
