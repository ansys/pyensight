import glob
import os

from ansys.pyensight.core import DockerLauncher, LocalLauncher
import pytest
import pathlib
from urllib.parse import urlparse
from urllib.request import url2pathname


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
    with open("test_exec_run_script.py", "w") as _file:
        _file.write("")
    session.run_script("test_exec_run_script.py")
    session.run_script(os.path.abspath("test_exec_run_script.py"))
    session.load_example("waterbreak.ens", root=root)
    core = session.ensight.objs.core
    core.PARTS.set_attr("COLORBYPALETTE", "alpha1")
    export = session.ensight.utils.export
    export.image("test.png")
    export.image("test.png", width=800, height=600)
    export.image("test.tiff", enhanced=True)
    export.animation("test.mp4", anim_type=export.ANIM_TYPE_SOLUTIONTIME)
    export.animation(
        "test.mp4", 
        anim_type=export.ANIM_TYPE_SOLUTIONTIME, 
        width=800, 
        height=600, 
        frames=30, 
        frames_per_second=80, 
        starting_frame=2,
        format_options="Quality Hight Type 2"
    )
    export.animation(
        "test_ray.mp4", 
        anim_type=export.ANIM_TYPE_SOLUTIONTIME, 
        width=800, 
        height=600, 
        frames=30, 
        frames_per_second=80, 
        starting_frame=2,
        format_options="Quality Hight Type 2",
        raytrace=True
    )
    session.ensight.anim_flipbook.begin_time_step(0)
    session.ensight.anim_flipbook.end_time_step(20)
    session.ensight.anim_flipbook.specify_time_as("step")
    session.ensight.anim_flipbook.load()
    export.animation(
        "test2.mp4", 
        anim_type=export.ANIM_TYPE_FLIPBOOK, 
        width=800, 
        height=600, 
        frames_per_second=80, 
        starting_frame=2,
    )
    session.ensight.anim_keyframe.keyframing("ON")
    session.ensight.anim_keyframe.create_keyframe()
    session.ensight.view_transf.rotate(11.4172411,-36.7627106,0)
    session.ensight.anim_keyframe.create_keyframe()
    export.animation(
        "test3.mp4", 
        anim_type=export.ANIM_TYPE_KEYFRAME, 
        width=800, 
        height=600, 
        frames_per_second=80, 
        starting_frame=2,
    )
    session.ensight.ptrace.create_bypart([6,100])
    session.ensight.part.select_lastcreatedpart()
    session.ensight.part.colorby_palette("u")
    session.ensight.command.delay_refresh("OFF")
    export.animation(
        "test4.mp4", 
        anim_type=export.ANIM_TYPE_ANIMATEDTRACES, 
        width=800, 
        height=600, 
        frames=30, 
        frames_per_second=80, 
        starting_frame=2,
    )
    with pytest.raises(RuntimeError):
        export.animation(
            "test4.mp4", 
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
    views._normalize_vector([0,0,0])
    views.set_view_direction(1,1,1)
    views.set_view_direction(-1,1,1)
    views.set_view_direction(-1,-1,1)
    views.set_view_direction(-1,-1,-1)
    views.set_view_direction(1,-1,1)
    views.set_view_direction(1,-1,-1)
    views.set_view_direction(1,1,-1)
    views.set_view_direction(-1,1,-1)
    views.set_view_direction(-1,-1,1)
    views.set_center_of_transform(0,1,2)
    views.compute_model_centroid()
    views.compute_model_centroid()
    views.set_view_direction(1,1,1, perspective=True)
    views.save_current_view("test")
    views.save_current_view("")
    views.restore_view("test")
    views.restore_center_of_transform()
    views.reinitialize_view()
    views._convert_rotation_matrix_to_quaternion([1, 0, 0], [0, -1, 0], [0, 0, -3])
    views._convert_rotation_matrix_to_quaternion([-5, 0, 0], [0, 2, 0], [0, 0, 1])
    views._convert_rotation_matrix_to_quaternion([-5, 0, 0], [0, 1, 0], [0, 0, 2])
    views.set_view_direction(1,1,1)
    session.ensight.tools.line("ON")
    query = session.ensight.utils.query
    query.create_distance(
        "line", 
        query.DISTANCE_LINE, 
        session.ensight.objs.core.PARTS["defaultFaces"],
        "alpha1",
        point1=[1.918665e-01, 3.840137e-01, 2.539995e-02],
        point2=[1.918665e-01, 1.069867e-01, 2.539995e-02]
    )
    session.ensight.view_transf.spline_new()
    session.ensight.view_transf.splinepoint_create(0,0,0)
    session.ensight.view_transf.splinepoint_edit(0.292100012,0.292100012,0)
    session.ensight.view_transf.splinepoint_create(0,0,0)
    session.ensight.view_transf.splinepoint_edit(0.358806312,0.322734863,0)
    query.create_distance(
        "spline", 
        query.DISTANCE_SPLINE, 
        ["defaultFaces"],
        "alpha1",
        spline_name="0-new_spline0"
    )
    with pytest.raises(ValueError):
        # Varoa;e mpt existing
        query.create_distance(
            "spline", 
            query.DISTANCE_SPLINE, 
            [6],
            "alpha15",
            spline_name="0-new_spline0"
        )
    session.ensight.objs.core.PARTS[0].getattrs(["VISIBLE", "DESCRIPTION"])
    session.ensight.objs.core.PARTS[0].attrtree()
    if not use_local:
        launcher.enshell_log_contents()




