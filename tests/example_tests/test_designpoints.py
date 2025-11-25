import glob
import os

from ansys.pyensight.core import DockerLauncher, LocalLauncher
import pytest


def test_designpoints(tmpdir, pytestconfig: pytest.Config):
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    root = None
    if use_local:
        launcher = LocalLauncher()
        root = "http://s3.amazonaws.com/www3.ensight.com/PyEnSight/ExampleData"
    else:
        launcher = DockerLauncher(
            data_directory=data_dir, use_dev=True, grpc_disable_tls=True, grpc_use_tcp_sockets=True
        )
    session = launcher.start()
    session.load_example("elbow_dp0_dp1.ens", root=root)
    image = session.show("image", width=800, height=600)
    image.download(data_dir)
    print([p.PATHNAME for p in session.ensight.objs.core.PARTS])
    # Create two more viewports (there is always one viewport)
    session.ensight.objs.core.DEFAULTVPORT[0].createviewport()
    session.ensight.objs.core.DEFAULTVPORT[0].createviewport()
    # Make these viewports visible and grab references to the viewport objects.
    session.ensight.objs.core.VPORTS.set_attr(session.ensight.objs.enums.VISIBLE, True)
    vp0 = session.ensight.objs.core.VPORTS[0]
    vp1 = session.ensight.objs.core.VPORTS[1]
    vp2 = session.ensight.objs.core.VPORTS[2]
    # Position the viewports by setting their WIDTH, HEIGHT, ORIGINX and ORIGINY attributes.
    vp0.WIDTH = 0.5
    vp1.WIDTH = 0.5
    vp2.WIDTH = 1.0
    session.ensight.objs.core.VPORTS.set_attr(session.ensight.objs.enums.HEIGHT, 0.5)
    vp0.ORIGINX = 0.0
    vp0.ORIGINY = 0.5
    vp0.BORDERVISIBLE = True
    vp1.ORIGINX = 0.5
    vp1.ORIGINY = 0.5
    vp2.ORIGINX = 0.0
    vp2.ORIGINY = 0.0
    # Link the transforms of all the viewports to each other
    session.ensight.objs.core.VPORTS.set_attr(session.ensight.objs.enums.LINKED, True)
    # Hide all but the "fluid" parts
    session.ensight.objs.core.PARTS.set_attr(session.ensight.objs.enums.VISIBLE, False)
    session.ensight.objs.core.PARTS["fluid"].set_attr(session.ensight.objs.enums.VISIBLE, True)
    session.ensight.objs.core.PARTS["fluid"].set_attr(
        session.ensight.objs.enums.ELTREPRESENTATION, session.ensight.objs.enums.BORD_FULL
    )
    image = session.show("image", width=800, height=600)
    image.download(data_dir)
    fluid0 = session.ensight.objs.core.PARTS["fluid"][0]
    fluid1 = session.ensight.objs.core.PARTS["fluid"][1]

    # Using an LPART: we find the ENS_LPART instance in the first case
    # for the part named "fluid".  If we load() this object, we get a
    # new instance of the case 0 "fluid" mesh.
    fluid0_diff = session.ensight.objs.core.CASES[0].LPARTS.find("fluid")[0].load()
    fluid0_diff.ELTREPRESENTATION = session.ensight.objs.enums.BORD_FULL

    # Get the temperature variable and color the fluid parts by it.
    temperature = session.ensight.objs.core.VARIABLES["Static_Temperature"][0]
    fluid0_diff.COLORBYPALETTE = temperature
    fluid0.COLORBYPALETTE = temperature
    fluid1.COLORBYPALETTE = temperature

    # Each of the three parts should only be visible in one viewport.
    fluid0.VIEWPORTVIS = session.ensight.objs.enums.VIEWPORT00
    fluid1.VIEWPORTVIS = session.ensight.objs.enums.VIEWPORT01
    fluid0_diff.VIEWPORTVIS = session.ensight.objs.enums.VIEWPORT02
    image = session.show("image", width=800, height=600)
    image.download(data_dir)
    temperature_diff = session.ensight.objs.core.create_variable(
        "Temperature_Difference",
        value="CaseMapDiff(plist, 2, Static_Temperature, 0, 1)",
        sources=[fluid0_diff],
    )

    fluid0_diff.COLORBYPALETTE = temperature_diff
    image = session.show("image", width=800, height=600)
    image.download(data_dir)
    limits = [(round(v / 5.0) * 5) for v in temperature_diff.MINMAX]
    temperature_diff.PALETTE[0].MINMAX = limits
    session.show("remote")
    local_files = glob.glob(os.path.join(data_dir, "*"))
    png_local = [x for x in local_files if ".png" in x]
    assert len(png_local) == 4
    session.close()
