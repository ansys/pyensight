import threading
import time

from ansys.pyensight.core import DockerLauncher, LocalLauncher
from ansys.pyensight.core.dvs import DVS
from ansys.pyensight.core.utils.dsg_server import DSGSession, UpdateHandler
import numpy
import pytest


def handle_update(dsg_link):
    dsg_link.start()
    dsg_link.request_an_update()
    while not dsg_link.is_shutdown():
        dsg_link.handle_one_update()
    dsg_link.end()
    dsg_link._callback_handler.shutdown()


class LocalUpdateHandler(UpdateHandler):
    def __init__(self):
        super().__init__()
        self._conn = None
        self._coords = None
        self._tcoords = None

    def finalize_part(self, part):
        vals = super().finalize_part(part)
        self._conn = part.conn_tris
        self._coords = part.coords
        self._tcoords = part.tcoords
        return vals


def wait_for_data(handler):
    available = False
    start = time.time()
    while not available and time.time() - start < 60:
        if (
            handler._conn is not None
            and handler._coords is not None
            and handler._tcoords is not None
        ):
            available = True
        time.sleep(0.5)
    return available


def build_numpy_conn_simba_format(conn):
    replacement = 3
    num_insertions = int(conn.size / replacement)
    new_values = numpy.full(num_insertions, replacement)
    face_array = numpy.insert(conn, numpy.arange(0, int(conn.size), replacement), new_values)
    return face_array


def test_dvs_data(tmpdir, pytestconfig: pytest.Config):
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    if use_local:
        launcher = LocalLauncher()
    else:
        launcher = DockerLauncher(data_directory=data_dir, use_dev=True)
    session = launcher.start()
    cas_file = session.download_pyansys_example("mixing_elbow.cas.h5", "pyfluent/mixing_elbow")
    dat_file = session.download_pyansys_example("mixing_elbow.dat.h5", "pyfluent/mixing_elbow")
    session.load_data(cas_file, result_file=dat_file)
    dvs = None
    if use_local:
        dvs = DVS(ansys_installation=session._install_path, session=session)
    else:
        dvs = DVS(session=session)
    update_handler = LocalUpdateHandler()
    link = DSGSession(
        port=session._grpc_port,
        host=session.hostname,
        security_code=session.secret_key,
        vrmode=False,
        handler=update_handler,
    )
    dsg_thread = threading.Thread(target=handle_update, args=(link,))
    dsg_thread.start()
    session.ensight.objs.core.PARTS.set_attr("VISIBLE", False)
    part = session.ensight.objs.core.PARTS.find("wall-inlet")[0]
    part.VISIBLE = True
    part.COLORBYPALETTE = "Static_Pressure"
    variable = session.ensight.objs.core.VARIABLES.find("Static_Pressure")[0]
    session.cmd("import enspyqtgui_int", do_eval=False)
    session.cmd(
        'enspyqtgui_int.dynamic_scene_graph_command("dynamicscenegraph://localhost/client/update")'
    )
    assert wait_for_data(update_handler)
    conn = build_numpy_conn_simba_format(update_handler._conn)
    dvs.start_dvs_servers(3, 0, 1)
    dvs.start_dvs_clients("TestDatasetSimbaFormat")
    dvs.create_part(part.PARTNUMBER, part.DESCRIPTION)
    dvs.begin_updates(session.ensight.objs.core.TIMEVALUES[0][1])
    dvs.send_connectivity(part.PARTNUMBER, conn)
    dvs.send_coordinates(part.PARTNUMBER, update_handler._coords)
    var_location = (
        dvs.LOCATION_ELEMENT
        if variable.LOCATION == session.ensight.objs.enums.ENS_VAR_ELEM
        else dvs.LOCATION_NODE
    )
    var_type = dvs.VARTYPE_SCALAR
    dvs.create_variable(
        variable.ID,
        variable.DESCRIPTION,
        var_type,
        var_location,
        variable.ENS_UNITS_DIMS,
        variable.ENS_UNITS_LABEL,
        variable.metadata,
    )
    dvs.send_variable_data(variable.ID, part.PARTNUMBER, update_handler._tcoords)
