import os
import pathlib

from ansys.pyensight.core import DockerLauncher, LocalLauncher
import pytest


def test_coverage_increase(tmpdir, pytestconfig: pytest.Config):
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    root = None
    if use_local:
        launcher = LocalLauncher()
        root = "http://s3.amazonaws.com/www3.ensight.com/PyEnSight/ExampleData"
    else:
        launcher = DockerLauncher(data_directory=data_dir, use_dev=True)
    session = launcher.start()
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
        pathlib.Path(os.path.join(data_dir, "test_exec_run_script.py")).parents[1].as_uri(),
        ["test_exec_run_script.py", "test_dir"],
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
        with pytest.raises(RuntimeError):
            session.copy_from_session(
                "grpc:///",
                [os.path.basename(os.path.dirname(__file__))],
            )
    session.language = "zh"
    session.language = "en"
    session.halt_ensight_on_close = False
    session.halt_ensight_on_close = True
    session.jupyter_notebook = True
    session.jupyter_notebook = False
    assert session.sos is False
    session.load_example("waterbreak.ens", root=root)
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
