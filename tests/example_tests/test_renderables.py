import glob
import os

from ansys.pyensight.core import DockerLauncher, LocalLauncher
import pytest


def test_renderables(tmpdir, pytestconfig: pytest.Config):
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    install_path = pytestconfig.getoption("install_path")
    if use_local:
        launcher = LocalLauncher(ansys_installation=install_path)
    else:
        launcher = DockerLauncher(data_directory=data_dir, use_dev=True)
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
    image.download(data_dir)
    session.ensight.view_transf.rotate(10.0, 0.0, 0.0)
    image.update()
    print(image.url)
    image.download(data_dir)
    deep = session.show("deep_pixel", width=800, height=600, aa=4)
    deep.download(data_dir)
    anim = session.show("animation", width=800, height=600, aa=2, fps=2.0)
    anim.download(data_dir)
    avz = session.show("webgl")
    avz.download(data_dir)
    session.show("remote")
    session.show("remote_scene", width=800, height=600, temporal=True)
    pngdata = session.render(1920, 1080, aa=4)
    with open(os.path.join(data_dir, "simple_example.png"), "wb") as fp:
        fp.write(pngdata)
    glbdata = session.geometry()
    with open(os.path.join(data_dir, "simple_example.glb"), "wb") as fp:
        fp.write(glbdata)
    local_files = glob.glob(os.path.join(data_dir, "*"))
    png_local = [x for x in local_files if ".png" in x]
    glb_local = [x for x in local_files if ".glb" in x]
    tif_local = [x for x in local_files if ".tif" in x]
    avz_local = [x for x in local_files if ".avz" in x]
    assert len(png_local) == 2
    assert len(glb_local) == 1
    assert len(tif_local) == 1
    assert len(avz_local) == 1
    session.close()
