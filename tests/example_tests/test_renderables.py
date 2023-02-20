import os
import glob

from ansys.pyensight import DockerLauncher, LocalLauncher

def test_renderables(tmpdir):
    data_dir = tmpdir.mkdir("datadir")
    try:
        launcher = DockerLauncher(data_directory=data_dir, use_dev=True)
    except:
        launcher = LocalLauncher()
    session = launcher.start()
    session.load_data(f"{session.cei_home}/ensight{session.cei_suffix}/data/guard_rail/crash.case")
    # Apply displacements
    displacement = session.ensight.objs.core.VARIABLES["displacement"][0]
    session.ensight.objs.core.PARTS.set_attr("DISPLACEBY", displacement)
    # Color by the variable "plastic"
    plastic = session.ensight.objs.core.VARIABLES["plastic"][0]
    session.ensight.objs.core.PARTS.set_attr("COLORBYPALETTE", plastic)
    # Adjust the palette range
    plastic.LEGEND[0].RANGE = [0.0, 0.007]
    session.ensight.view_transf.rotate(-36.0, 23.0, 0.0)
    session.ensight.view_transf.fit(0)
    image = session.show("image", width=800, height=600, aa=4)
    session.ensight.view_transf.rotate(10.0, 0.0, 0.0)
    image.update()
    print(image.url)
    local_directory_pathname = "."
    image.download(local_directory_pathname)
    deep_image = session.show("deep_pixel", width=800, height=600, aa=4)
    animation = session.show("animation", width=800, height=600, aa=2, fps=2.0)
    webgl = session.show("webgl")
    remote = session.show("remote")
    remote_scene = session.show("remote_scene", width=800, height=600, temporal=True)
    pngdata = session.render(1920, 1080, aa=4)
    with open(os.path.join(data_dir, "simple_example.png"), "wb") as fp:
        fp.write(pngdata)
    glbdata = session.geometry()
    with open(os.path.join(data_dir, "simple_example.glb"), "wb") as fp:
        fp.write(glbdata)
    files_in_dir = glob.glob(os.path.join(launcher.session_directory, "*"))
    png = [x for x in files_in_dir if ".png" in x]
    html = [x for x in files_in_dir if ".html" in x]
    avz = [x for x in files_in_dir if ".avz" in x]
    evsn = [x for x in files_in_dir if ".evsn" in x]
    tiff = [x for x in files_in_dir if ".tiff" in x or ".tif" in x]
    local_files = glob.glob(os.path.join(data_dir, "*"))
    png_local = [x for x in local_files if ".png" in x]
    glb_local = [x for x in local_files if ".glb" in x]
    assert len(png) == 2
    assert len(html) == 5
    assert len(avz) == 1
    assert len(tiff) == 1
    assert len(evsn) == 1
    assert len(png_local) == 1
    assert len(glb_local) == 1
