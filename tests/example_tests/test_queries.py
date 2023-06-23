import glob
from operator import attrgetter
import os

from ansys.pyensight.core.dockerlauncher import DockerLauncher
from ansys.pyensight.core.locallauncher import LocalLauncher
import numpy as np
import pytest


def test_queries(tmpdir, pytestconfig: pytest.Config):
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    root = None
    if use_local:
        launcher = LocalLauncher()
        root = "http://s3.amazonaws.com/www3.ensight.com/PyEnSight/ExampleData"
    else:
        launcher = DockerLauncher(data_directory=data_dir, use_dev=True)
    session = launcher.start()
    session.load_example("waterbreak.ens", root=root)
    # Get the core part and variable objects
    var = session.ensight.objs.core.VARIABLES["p"][0]
    part = session.ensight.objs.core.PARTS["default_region"][0]
    # Isolate the 3D part "default_region" and display it at
    # solution time 0.7, coloring it by the 'p' variable.
    session.ensight.objs.core.PARTS.set_attr("VISIBLE", False)
    part.VISIBLE = True
    part.ELTREPRESENTATION = session.ensight.objs.enums.BORD_FULL
    part.COLORBYPALETTE = var
    session.ensight.objs.core.SOLUTIONTIME = 0.7
    session.ensight.objs.core.HIDDENLINE_USE_RGB = True
    session.ensight.objs.core.HIDDENLINE = True
    # Rotate the view a bit
    session.ensight.view_transf.rotate(-66.5934067, 1.71428561, 0)
    session.ensight.view_transf.rotate(18.0219765, -31.6363659, 0)
    session.ensight.view_transf.rotate(-4.83516455, 9.5064888, 0)
    session.ensight.view_transf.zoom(0.740957975)
    session.ensight.view_transf.zoom(0.792766333)
    session.ensight.view_transf.translate(0.0719177574, 0.0678303316, 0)
    session.ensight.view_transf.rotate(4.83516455, 3.42857122, 0)
    # Display it
    image = session.show("image", width=800, height=600)
    image.download(data_dir)
    session.ensight.part.select_begin(part.PARTNUMBER)
    session.ensight.query_ent_var.begin()
    session.ensight.query_ent_var.description("Pressure vs Distance")
    session.ensight.query_ent_var.query_type("generated")
    session.ensight.query_ent_var.number_of_sample_pts(20)
    session.ensight.query_ent_var.constrain("line_tool")
    session.ensight.query_ent_var.line_loc(1, 0.00, 0.075, 0.0)
    session.ensight.query_ent_var.line_loc(2, 0.58, 0.075, 0.0)
    session.ensight.query_ent_var.distance("arc_length")
    session.ensight.query_ent_var.variable_1(var.DESCRIPTION)
    session.ensight.query_ent_var.generate_over("distance")
    session.ensight.query_ent_var.variable_2("DISTANCE")
    session.ensight.query_ent_var.end()
    session.ensight.query_ent_var.query()
    # This is an interesting trick.  The above code uses the
    # 'native' command bindings.  We would like to be able to
    # use the query object.  EnSight object 'values' are monotonically
    # increasing numbers.  Thus, the 'max()' operation on a list
    # of EnSight objects will return the most recently created one.
    line_query = max(session.ensight.objs.core.QUERIES, key=attrgetter("__OBJID__"))
    print(line_query, line_query.QUERY_DATA["xydata"])
    line_plot = session.ensight.objs.core.defaultplot[0].createplotter()
    line_query.addtoplot(line_plot)
    line_plot.rescale()
    line_plot.PLOTTITLE = f"{var.DESCRIPTION} vs Distance"
    line_plot.AXISXTITLE = "Distance"
    line_plot.AXISYTITLE = var.DESCRIPTION
    line_plot.LEGENDVISIBLE = False
    line_plot.AXISXAUTOSCALE = False
    line_plot.AXISXMIN = 0.0
    line_plot.AXISXMAX = 0.6
    line_plot.AXISXLABELFORMAT = "%.2f"
    line_plot.AXISXGRIDTYPE = 1
    line_plot.AXISYGRIDTYPE = 1
    line_plot.TIMEMARKER = False
    line_plot.AXISYAUTOSCALE = False
    line_plot.AXISYMIN = -200.0
    line_plot.AXISYMAX = 2200.0
    image = session.show("image", width=800, height=600)
    image.download(data_dir)
    elem_ids = [134, 398, 662]
    session.ensight.part.select_begin(part.PARTNUMBER)
    session.ensight.query_interact.search("exact")
    session.ensight.query_interact.query("element")
    session.ensight.query_interact.number_displayed(3)
    # Create 3 element probes using pre-selected element numbers
    for id in elem_ids:
        session.ensight.query_interact.create(id)
    # Make the probe locations a bit more visible
    session.ensight.objs.core.PROBES[0].LABELALWAYSONTOP = True

    # Make three queries.  Again, a generated query but with
    # "time" as "variable 2" and specific simulation start and
    # end times specified
    session.ensight.part.select_begin(part.PARTNUMBER)
    elem_queries = []
    for id in elem_ids:
        session.ensight.query_ent_var.begin()
        session.ensight.query_ent_var.description(f"{id}")
        session.ensight.query_ent_var.query_type("generated")
        session.ensight.query_ent_var.number_of_sample_pts(20)
        session.ensight.query_ent_var.begin_simtime(0)
        session.ensight.query_ent_var.end_simtime(1)
        session.ensight.query_ent_var.constrain("element")
        session.ensight.query_ent_var.sample_by("value")
        session.ensight.query_ent_var.variable_1(var.DESCRIPTION)
        session.ensight.query_ent_var.elem_id(id)
        session.ensight.query_ent_var.generate_over("time")
        session.ensight.query_ent_var.variable_2("TIME")
        session.ensight.query_ent_var.update_with_newtimesteps("ON")
        session.ensight.query_ent_var.end()
        session.ensight.query_ent_var.query()
        # Just like before, grab the query objects.
        elem_queries.append(max(session.ensight.objs.core.QUERIES, key=attrgetter("__OBJID__")))
    print(elem_queries)
    elem_plot = session.ensight.objs.core.defaultplot[0].createplotter(
        xtitle="Time", ytitle=var.DESCRIPTION
    )
    for query in elem_queries:
        query.addtoplot(elem_plot)
    elem_plot.rescale()
    elem_plot.PLOTTITLE = "Elements vs Time"
    elem_plot.AXISXLABELFORMAT = "%.1f"
    elem_plot.AXISXGRIDTYPE = 1
    elem_plot.AXISYGRIDTYPE = 1
    anim = session.show("animation", width=800, height=600, fps=5)
    anim.download(data_dir)
    session.ensight.objs.core.SOLUTIONTIME = 0.7
    data = np.array(line_query.QUERY_DATA["xydata"])
    fit = np.polyfit(data[:, 0], data[:, 1], 6)
    new_y = np.polyval(fit, data[:, 0])
    data[:, 1] = new_y
    session.ensight.query_xy_create("curvefit", "fit", "Distance", data.tolist())
    fit_query = max(session.ensight.objs.core.QUERIES)
    fit_query.addtoplot(line_plot)
    session.show("remote")
    local_files = glob.glob(os.path.join(data_dir, "*"))
    png_local = [x for x in local_files if ".png" in x]
    mp4_local = [x for x in local_files if ".mp4" in x]
    assert len(png_local) == 2
    assert len(mp4_local) == 1
    session.close()
