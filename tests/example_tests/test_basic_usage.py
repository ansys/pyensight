import glob
import os

from ansys.pyensight import DockerLauncher, LocalLauncher


def test_basic_usage(tmpdir):
    data_dir = tmpdir.mkdir("datadir")
    try:
        launcher = DockerLauncher(data_directory=data_dir, use_dev=True)
    except Exception:
        launcher = LocalLauncher()
    session = launcher.start()
    core = session.ensight.objs.core
    session.load_data(f"{session.cei_home}/ensight{session.cei_suffix}/data/cube/cube.case")
    session.ensight.view_transf.rotate(30, 30, 0)
    session.show("image", width=800, height=600)
    clip_default = core.DEFAULTPARTS[session.ensight.PART_CLIP_PLANE]
    parent_parts = core.PARTS
    clip = clip_default.createpart(name="Clip", sources=parent_parts)[0]
    session.show("image", width=800, height=600)
    print("Parts:", core.PARTS)
    clip_default = session.cmd("ensight.objs.core.DEFAULTPARTS[ensight.PART_CLIP_PLANE]")
    clip.COLORBYPALETTE = core.VARIABLES["temperature"][0]
    session.show("image", width=800, height=600)
    print("Variables:", core.VARIABLES)
    core.PARTS.set_attr("ELTREPRESENTATION", session.ensight.objs.enums.BORD_FULL)
    core.PARTS[0].OPAQUENESS = 0.1
    d = dict(HIDDENLINE=True, HIDDENLINE_USE_RGB=True, HIDDENLINE_RGB=[0, 0, 0])
    core.setattrs(d)
    session.show("image", width=800, height=600)
    text = core.DEFAULTANNOTS[session.ensight.ANNOT_TEXT].createannot("Temperature Clip")
    text.setattrs(dict(LOCATIONX=0.5, LOCATIONY=0.95))
    session.show("image", width=800, height=600)
    pngdata = session.render(1920, 1080, aa=4)
    with open(os.path.join(data_dir, "simple_example.png"), "wb") as fp:
        fp.write(pngdata)
    glbdata = session.geometry()
    with open(os.path.join(data_dir, "simple_example.glb"), "wb") as fp:
        fp.write(glbdata)
    session.show("remote")
    files_in_dir = glob.glob(os.path.join(launcher.session_directory, "*"))
    png = [x for x in files_in_dir if ".png" in x]
    html = [x for x in files_in_dir if ".html" in x]
    local_files = glob.glob(os.path.join(data_dir, "*"))
    png_local = [x for x in local_files if ".png" in x]
    glb_local = [x for x in local_files if ".glb" in x]
    assert len(png) == 5
    assert len(html) == 5
    assert len(png_local) == 1
    assert len(glb_local) == 1
    session.close()
