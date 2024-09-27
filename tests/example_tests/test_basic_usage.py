import glob
import os
from typing import TYPE_CHECKING, Any, Optional, Tuple

if TYPE_CHECKING:
    from ansys.pyensight.core import Session


def test_basic_usage(launch_pyensight_session: Tuple["Session", Any, Optional[str]]):
    session, data_dir, _ = launch_pyensight_session
    core = session.ensight.objs.core
    session.load_data(f"{session.cei_home}/ensight{session.cei_suffix}/data/cube/cube.case")
    session.ensight.view_transf.rotate(30, 30, 0)
    session.show("image", width=800, height=600)
    clip_default = core.DEFAULTPARTS[session.ensight.PART_CLIP_PLANE]
    parent_parts = core.PARTS
    clip = clip_default.createpart(name="Clip", sources=parent_parts)[0]
    image = session.show("image", width=800, height=600)
    image.download(data_dir)
    print("Parts:", core.PARTS)
    clip_default = session.cmd("ensight.objs.core.DEFAULTPARTS[ensight.PART_CLIP_PLANE]")
    clip.COLORBYPALETTE = core.VARIABLES["temperature"][0]
    image = session.show("image", width=800, height=600)
    image.download(data_dir)
    print("Variables:", core.VARIABLES)
    core.PARTS.set_attr("ELTREPRESENTATION", session.ensight.objs.enums.BORD_FULL)
    core.PARTS[0].OPAQUENESS = 0.1
    d = dict(HIDDENLINE=True, HIDDENLINE_USE_RGB=True, HIDDENLINE_RGB=[0, 0, 0])
    core.setattrs(d)
    image = session.show("image", width=800, height=600)
    image.download(data_dir)
    text = core.DEFAULTANNOTS[session.ensight.ANNOT_TEXT].createannot("Temperature Clip")
    text.setattrs(dict(LOCATIONX=0.5, LOCATIONY=0.95))
    image = session.show("image", width=800, height=600)
    image.download(data_dir)
    pngdata = session.render(1920, 1080, aa=4)
    with open(os.path.join(data_dir, "simple_example.png"), "wb") as fp:
        fp.write(pngdata)
    glbdata = session.geometry()
    with open(os.path.join(data_dir, "simple_example.glb"), "wb") as fp:
        fp.write(glbdata)
    session.show("remote")
    local_files = glob.glob(os.path.join(data_dir, "*"))
    png_local = [x for x in local_files if ".png" in x]
    glb_local = [x for x in local_files if ".glb" in x]
    assert len(png_local) == 5
    assert len(glb_local) == 1
    session.close()
