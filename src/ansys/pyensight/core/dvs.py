"""The module provides a concrete implementation for the DVS bindings in PyEnSight.

It also provides a collection of utilities to starts DVS servers, clients,
launch a local PyEnSight session, or connect to an existing one, and finally
to send data from the clients to the servers.
"""
import glob
import io
import logging
import os
import pathlib
import platform
import re
import sys
import tarfile
import tempfile
import threading
import time
import traceback
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
import warnings

from ansys.api.pyensight.dvs_api import dvs_base
from ansys.pyensight.core import DockerLauncher, LocalLauncher
from ansys.pyensight.core.common import safe_extract
import numpy

if TYPE_CHECKING:
    from ansys.pyensight.core import Session


class DVS(dvs_base):
    """Create an instance of the DVS module.

    The module tries to look for the DVS Python bindings from the input
    Ansys installation folder (which might also be the CEI folder) or the input
    lib_folder. If not found, and if a PyEnSight session is provided,
    the DVS commands will be launched on the remote EnSight Python interpreter.

    Parameters
    ----------

    session: Session
        An optional PyEnSight session. This must be provided in case the
        DVS modules needs to be used on a remote session of EnSight.
    ansys_installation: str
        The optional full path to a local Ansys installation, or the CEI folder
        from an Ansys installation
    lib_folder: str
        The optional full path to a folder that contains the DVS libraries and Python
        bindings.
    """

    def __init__(
        self,
        session: Optional["Session"] = None,
        ansys_installation: Optional[str] = None,
        lib_folder: Optional[str] = None,
    ) -> None:
        super().__init__(session=session)
        self._ansys_installation: Optional[str] = None
        if ansys_installation:
            self._ansys_installation = LocalLauncher.get_cei_install_directory(ansys_installation)
        self._lib_folder: Optional[str] = lib_folder
        if self._session:
            if not self._ansys_installation and hasattr(self._session._launcher, "_install_path"):
                self._ansys_installation = self._session._launcher._install_path
        if not self._session and not self._ansys_installation and not self._lib_folder:
            raise RuntimeError(
                "Either a PyEnSight session or an ansys installation path, or a folder containing the DVS Python modules need to be provided."
            )
        self._connect_session = self._session
        self._servers: Dict[int, Dict[str, Union[str, int]]] = {}
        self._server_ids: List[int] = []
        self._clients: Dict[int, Dict[str, Union[str, int, bool]]] = {}
        self._client_count = 0
        self._attempt_dvs_python_bindings_import()
        self._parts: Dict[int, Any] = {}
        self._vars: Dict[int, Any] = {}
        self._update_num = 0
        self._current_update = 0
        self._elem_type_map = {
            2: self.ELEMTYPE_BAR_2,
            3: self.ELEMTYPE_TRIANGLE,
            4: self.ELEMTYPE_QUADRANGLE,
        }
        self._total_ranks = 0
        if hasattr(self._session._launcher, "_install_path"):
            self._temp_cache = tempfile.TemporaryDirectory(prefix="pyensight_dvs")
            os.mkdir(os.path.join(self._temp_cache.name, "dvs_cache"))
            self._cache_folder: str = os.path.join(self._temp_cache.name, "dvs_cache")
        else:
            self._cache_folder = "/home/ensight/dvs_cache"
        self._dataset_name: Optional[str] = None
        self._secret_key: Optional[str] = None

    @staticmethod
    def _is_windows():
        """True if the platform being used is Windows."""
        return "Win" in platform.system()

    def launch_local_pyensight_session(
        self,
        use_egl=False,
        use_sos: Optional[int] = None,
        additional_command_line_options: Optional[List] = None,
    ):
        """Launch a local PyEnSight session.

        If an ansys installation has been provided, it will be used to launch EnSight.
        The session will be associated to the current DVS module instance.

        Parameters

        use_egl : bool, optional
            Whether to use EGL hardware for accelerated graphics. The platform
            must be able to support this hardware. This parameter is defined on
            the parent ``Launcher`` class, where the default is ``False``.
        use_sos : int, optional
            Number of EnSight servers to use for SOS (Server of Server) mode.
            This parameter is defined on the parent ``Launcher`` class, where
            the default is ``None``, in which case SOS mode is not used.
        additional_command_line_options: list, optional
            Additional command line options to be used to launch EnSight.
        """
        launcher = LocalLauncher(
            ansys_installation=self._ansys_installation,
            use_sos=use_sos,
            use_egl=use_egl,
            additional_command_line_options=additional_command_line_options,
        )
        session = launcher.start()
        self._session = session

    def _attempt_dvs_python_bindings_import(self):
        """Attempt to load the actual DVS Python bindings.

        If an input lib folder has been provided, it will be tried first.
        If an ansys installation has been provided, it will be tried as second choice.
        """
        if self._lib_folder:
            try:
                sys.path.append(self._lib_folder)
                import dynamic_visualization_store

                self._dvs_module = dynamic_visualization_store
            except (ModuleNotFoundError, ImportError):
                raise RuntimeError("Cannot import DVS module from provided library folder.")
        if self._ansys_installation:
            # Check if you are inside of an ansys install
            apex_path = glob.glob(os.path.join(self._ansys_installation, "apex???"))
            if not apex_path:
                # try dev path
                raise RuntimeError("Cannot find a valid EnSight install")
            apex_path = apex_path[-1]
            arch = "win64" if self._is_windows() else "linux_2.6_64"
            apex_libs = os.path.join(apex_path, "machines", arch)
            python_path = glob.glob(os.path.join(apex_libs, "Python-3.*"))[-1]
            apex_py_version = re.search(
                r"Python-3.([0-9]+).([0-9]+)", os.path.basename(python_path)
            )
            apex_py_major_version = apex_py_version.group(1)
            lib_path = os.path.join(python_path, "lib", f"python3.{apex_py_major_version}")
            if self._is_windows():
                lib_path = os.path.join(python_path, "DLLs")
            sys.path.append(lib_path)
            try:
                import dynamic_visualization_store

                self._dvs_module = dynamic_visualization_store
            except (ModuleNotFoundError, ImportError):
                python_cei = os.path.join(apex_libs, "Python-CEI")
                if os.path.isdir(python_cei):
                    python_cei_lib_path = os.path.join(
                        python_cei, "lib", f"python3.{apex_py_major_version}"
                    )
                    if self._is_windows():
                        python_cei_lib_path = os.path.join(python_cei, "DLLs")
                    sys.path.append(python_cei_lib_path)
                try:
                    import dynamic_visualization_store

                    self._dvs_module = dynamic_visualization_store
                except (ModuleNotFoundError, ImportError):
                    warnings.warn(
                        "Cannot import DVS module from provided ansys installation folder."
                    )

    DVS_NULL_TRANSPORT = 0
    DVS_GRPC_TRANSPORT = 1

    @property
    def session(self):
        return self._session

    @session.setter
    def session(self, session: "Session"):
        self._session = session

    def start_dvs_servers(
        self, num_servers: int, transport: int = 0, ranks_per_server: int = 1, secret_key: str = ""
    ):
        """Start DVS servers using the Python bindings.

        The DVS servers will be started externall to the eventual EnSigth session available.
        For simplicity, it is assumed that each server will receive the same number of ranks,
        declared in input.

        Parameters
        ----------
        num_servers: int
            the number of DVS servers to launch
        transport: int
            the kind of transport to be used. Defaults to null.
            Description of options as follows.

            ================== =========================================================
            Name               Query type
            ================== =========================================================
            DVS_NULL_TRANSPORT Start the servers with the null protocol. Default
            DVS_GRPC_TRANSPORT Start the servers with the grpc protocol.
            ================== =========================================================
        ranks_per_server: int
            the number or ranks that will be connected to each server. Defaults to 1
        secret_key: str
            the secret key that will be used for the eventual gRPC connection.
            Can be an empty string, that is also the default value.
        """
        if not self._secret_key:
            self._secret_key = secret_key
        transport_string = "null" if transport == 0 else "grpc"
        uri = f"{transport_string}://"
        grpc = transport == self.DVS_GRPC_TRANSPORT
        options = {"CACHE_URI": f"hdf5:///{pathlib.Path(self._cache_folder).as_posix()}"}
        if grpc:
            uri += "127.0.0.1:0"
            options.update(
                {
                    "SERVER_SECURITY_SECRET": secret_key,
                }
            )
        try:
            for n in range(0, num_servers):
                # Assume ranks equally distributed
                server_id = self.server_create(uri=uri)
                self.server_start(
                    server_id, server_num=n, local_ranks=ranks_per_server, options=options
                )
                self._server_ids.append(server_id)
                self._servers[n] = {
                    "server_id": server_id,
                    "ranks": ranks_per_server,
                    "in_ensight": False,
                }
                if grpc:
                    uri_to_save = self.server_get_uri(server_id)
                    port = re.search(":([0-9]+)", uri_to_save)
                    if port:
                        self._servers[n].update(
                            {"server_uri": uri_to_save, "port": int(port.group(1))}
                        )
            self._total_ranks = ranks_per_server * len(self._server_ids)
            started = False
            start = time.time()
            while not started and time.time() - start < 60:
                if not all([self.server_started(s) for s in self._server_ids]):
                    time.sleep(0.5)
                else:
                    started = True
            if not started:
                raise RuntimeError("The DVS servers have not started in 60 seconds.")
        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Couldn't start the servers, error: {e}")

    def _start_dvs_client(self, server_id: int, rank: int, dedup=False):
        """Start a DVS client.

        Parameters
        ----------
        server_id: int
            the server ID to connect to
        rank: int
            the rank of the client to launch
        secret_key: str
            the secret key to be used to connect to the DVS server
        dedup: bool
            True to not send duplicate data to server
        """
        if server_id not in self._server_ids:
            raise RuntimeError(f"Server ID {server_id} not started in this process.")
        flags = self.FLAGS_BLOCK_FOR_SERVER
        if dedup:
            flags |= self.FLAGS_DEDUP
        try:
            client_id = self.connect(server_id=server_id, secret=self._secret_key, flags=flags)
        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Couldn't start the client, error {e}")
        self._clients[self._client_count] = {
            "client_id": client_id,
            "server_id": server_id,
            "rank": rank,
            "update_started": False,
        }
        self._client_count += 1

    def start_dvs_servers_in_ensight(self, ranks_per_server: int, secret_key=""):
        """Launch the DVS servers in EnSight for an in-situ session.

        On each EnSight server a DVS server will be launched.

        Parameters
        ----------
        ranks_per_server: int
            how many ranks will be sent to each server. This will be used
            in a later stage for the clients launch and connection.
        secret_key: str
            the secret key that will be used for the eventual gRPC connection.
            Can be an empty string, that is also the default value.
        """
        if not self._secret_key:
            self._secret_key = secret_key
        if not self._session:
            raise RuntimeError(
                "A PyEnSight session is required to start the DVS servers in EnSight."
            )
        thread, port = self._session.ensight.utils.readers.dvs.launch_live_dvs(
            secret_key=secret_key
        )
        num_servers = self._session._launcher._use_sos or 1
        base_uri = f"grpc://{self._session.hostname}"
        self._total_ranks = num_servers * ranks_per_server
        # Need to implement SOS support in session.ensight.utils.readers.dvs.launch_live_dvs
        for n in range(num_servers):
            # Just create a server but not start it
            server_id = self.server_create(uri=base_uri + f":{port+n}")
            self._server_ids.append(server_id)
            self._servers[n] = {
                "server_uri": base_uri + ":{}".format(port + n),
                "port": port + n,
                "server_id": server_id,
                "in_ensight": True,
                "ranks": ranks_per_server,
            }

    def start_dvs_clients(self, dataset_name: str, dedup=False):
        """Launch the DVS clients and connect to the existing DVS servers.

        Parameters
        ----------
        dataset_name: str
            The dataset name required to initialize the following exports.
        """
        self._dataset_name = dataset_name
        rank_per_server = list(self._servers.values())[0].get("ranks")
        local_ranks = 0
        n = 0
        for rank in range(0, self._total_ranks):
            server = self._servers[n]
            local_ranks += 1
            if local_ranks == rank_per_server:
                local_ranks = 0
                n += 1
            self._start_dvs_client(int(server["server_id"]), rank, dedup=dedup)

    def _begin_update(
        self, client_dict: Dict[str, Union[str, int, bool]], time: float, rank: int, chunk: int
    ):
        """Start an update.

        Parameters
        ----------
        client_dict: dict
            A dictionary holding the DVS client parameters
        time: float
            The time value for the current update. May be a time already used
        rank: int
            The rank of the update
        chunk: int
            The chunk of the update
        """
        try:
            _ = self.begin_update(client_dict["client_id"], self._update_num, time, rank, chunk)
            client_dict["update_started"] = True
        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Couldn't begin update. Error: {e}")

    def begin_updates(self, time: float):
        """Begin an update on all the clients available for the input time value.

        Each update will be launched on a separate thread. The client associated
        to the update will be flagged for the update start.

        Currently we are assuming one chunk. Chunking support will be added in a future
        release.

        Parameters
        ----------
        time: float
            The time value for the current update. May be a time already used
        """
        for _, client_vals in self._clients.items():
            thread = threading.Thread(
                target=self._begin_update, args=(client_vals, time, client_vals["rank"], 0)
            )
            thread.start()

    def begin_initialization(self):
        """Begin initialization for all the clients."""
        for c in range(self._client_count):
            client = self._clients[c]
            _ = self.begin_init(
                client["client_id"],
                dataset_name=f"Simba_{self._dataset_name}",
                rank=client["rank"],
                total_ranks=self._total_ranks,
                num_chunks=1,
            )

    def end_initialization(self):
        """End initialization for all the clients."""
        for c in range(self._client_count):
            client = self._clients[c]
            _ = self.end_init(client["client_id"])

    def create_part(self, part_id: int, part_name: str, metadata: Optional[Dict[str, str]] = None):
        """Create a part definition for the DVS export.

        Parameters
        ----------
        part_id: int
            the ID of the part to be exported
        part_name: str
            the name of the part to export
        metadata: dict
            An optional dictionary of metadata to attach to the part.
        """
        if not metadata:
            metadata = {}
        if self._parts.get(part_id):
            print("Part already created, skip")
            return
        part = {
            "id": part_id,
            "name": part_name,
            "structured": False,
            "chunking": False,
            "tags": metadata,
        }
        for c in range(self._client_count):
            client = self._clients[c]
            self.add_part_info(client["client_id"], [part])
        self._parts[part_id] = part

    def create_variable(
        self,
        var_id: int,
        var_name: str,
        var_type: int,
        location: int,
        unit: str = "",
        unit_label="",
        metadata: Optional[Dict[str, str]] = None,
    ):
        """Create a variable definition for the DVS export.

        Parameters
        ----------
        var_id: int
            the ID of the var to be exported
        var_name: str
            the name of the var to export
        var_type: int
            The variable type. Check the VARTYPE enums available with this module
        location: int
            The variable location. Check the LOCATION enums available with this module
        unit: str
            The variable units. See https://nexusdemo.ensight.com/docs/python/html/ENS_UNITSSchema.html
        unit_label: str
            The label for the variable units. See https://nexusdemo.ensight.com/docs/python/html/ENS_UNITSSchema.html
        metadata: dict
            An optional dictionary of metadata to attach to the var.
        """
        if not metadata:
            metadata = {}
        if self._vars.get(var_id):
            print("Var already created, skip")
            return
        var = {
            "id": var_id,
            "name": var_name,
            "tags": metadata,
            "type": var_type,
            "location": location,
            "unit": unit,
            "unit_label": unit_label,
        }
        for c in range(self._client_count):
            client = self._clients[c]
            self.add_var_info(client["client_id"], [var])
        self._vars[var_id] = var

    def _check_updates_started(self):
        """Check that all the updates started successfully.

        This is required because the launch of the updates is threaded.
        """
        started = False
        start = time.time()
        while not started and time.time() - start < 60:
            started = all([vals["update_started"] for c, vals in self._clients.items()])
            if not started:
                time.sleep(0.5)
        if not started:
            for c, vals in self._clients.items():
                update = vals["update_started"]
                logging.debug(f"Client {c}, update: {update}")
            raise RuntimeError("Not all clients have begun the updates.")

    def send_coordinates(self, part_id: int, vertices: Union[List[float], numpy.ndarray]):
        """Send the coordinates data for the input part.

        The full coordinates array will be sent across all the ranks.
        The data will be used for building a mesh chunk in DVS.
        The data are assumed in the following format:
        [x0, y0, z0, x1, y1, z1, ...]

        Parameters
        ----------
        part_id: int
            the part to define the coordinates for
        vertices: List[int] or numpy array
            the coordinates array. The format is described above.
        """
        if not self._parts.get(part_id):
            raise RuntimeError(
                "Please create the part first via create_part() or the lower level add_part_info."
            )
        if not isinstance(vertices, numpy.ndarray):
            vertices = numpy.array(vertices)
        reshaped_vertices = vertices.reshape(-1, 3)
        x_coords = reshaped_vertices[:, 0]
        y_coords = reshaped_vertices[:, 1]
        z_coords = reshaped_vertices[:, 2]
        self._check_updates_started()
        for c in range(self._client_count):
            client = self._clients[c]
            self.update_nodes(
                client["client_id"], part_id=part_id, x=x_coords, y=y_coords, z=z_coords
            )

    def send_variable_data(
        self,
        var_id: int,
        part_id: int,
        values: Union[List[float], numpy.ndarray],
    ):
        """Send the variable data for the input variable.

        Parameters
        ----------
        var_id: int
            the ID of the variable that will get its values updated.
        part_id: int
            the ID of the part to update the variable for
        values: List[int] or numpy array
            the variablle array. If the variable is a vector, the values are expected as
            [v1x, v1y, v1z, v2x, v2y, v2z ...]
        """
        if not self._vars.get(var_id):
            raise RuntimeError(
                "Please create the variable first via create_var() or the lower level add_var_info."
            )
        if not self._parts.get(part_id):
            raise RuntimeError(
                "Please create the part first via create_part() or the lower level add_part_info."
            )
        if not self._parts[part_id].get("dvs_elem_type"):
            raise RuntimeError(f"Please send first the part connectivity for part {part_id}")
        elem_type = self._parts[part_id]["dvs_elem_type"]
        if not isinstance(values, numpy.ndarray):
            values = numpy.array(values)
        self._check_updates_started()
        var_type = self._vars[var_id]["type"]
        location = self._vars[var_id]["location"]
        # The following checks are there just to make mypy happy
        if isinstance(var_type, (str, bool, dict)):
            raise RuntimeError("Var type is not an integer")
        if isinstance(location, (str, bool, dict)):
            raise RuntimeError("Location is not an integer")
        for c in range(self._client_count):
            client = self._clients[c]
            if var_type == self.VARTYPE_SCALAR:
                if location == self.LOCATION_NODE:
                    self.update_var_node_scalar(
                        client["client_id"], var_id=var_id, part_id=part_id, values=values
                    )
                elif location == self.LOCATION_ELEMENT:
                    self.update_var_element_scalar(
                        client["client_id"],
                        var_id=var_id,
                        part_id=part_id,
                        elem_type=elem_type,
                        values=values,
                    )
            elif var_type == self.VARTYPE_VECTOR:
                if location == self.LOCATION_NODE:
                    self.update_var_node_vector(
                        client["client_id"], var_id=var_id, part_id=part_id, values=values
                    )
                elif location == self.LOCATION_ELEMENT:
                    self.update_var_element_vector(
                        client["client_id"],
                        var_id=var_id,
                        part_id=part_id,
                        elem_type=elem_type,
                        values=values,
                    )

    @staticmethod
    def _split_list(lst: Union[List[int], List[float]], num_parts: int):
        """Split the input list in n parts.

        lst: list
            the list to be split
        num_parts: int
            the number of parts to split the list into

        Returns
        -------
        parts: list
            A list containing the parts the original list was split into
        """
        n = len(lst)
        part_size = n // num_parts
        remainder = n % num_parts
        parts = []
        start = 0
        for i in range(num_parts):
            end = start + part_size + (1 if i < remainder else 0)
            parts.append(lst[start:end])
            start = end
        return parts

    def send_connectivity(
        self,
        part_id,
        offsets: Union[List, numpy.ndarray],
        faces: Union[List, numpy.ndarray],
        ghost=False,
    ):
        """Send the connectivity data for the input part.

        The data will be used for building an element block in DVS.
        The connectivity array will be split among all the available ranks.
        The faces data are assumed in the following format:
        [n, i1, i2, ...in, m, j1, j2, ...jn, p, k1, k2, ...kp, ...]
        The offsets data instead:
        [0, n, n+m, n+m+p ....]
        The faces list indicates the IDs of the vertices of each face, in order.
        The offsets lists indicates the index where to find a specific face.

        Parameters
        ----------
        part_id: int
            the part to define the connectivity for
        offsets: List[int] or numpy array
            the offsets values. The format is described above.
        faces: List[int] or numpy array
            the connectivity value. The format is described above.
        ghost: bool
            True if the input data contains ghost elements.
        """
        if not self._clients:
            raise RuntimeError("No DVS clients started yet.")
        if not self._parts.get(part_id):
            raise RuntimeError(
                "Please create the part first via create_part() or the lower level add_part_info."
            )
        if not isinstance(faces, numpy.ndarray):
            faces = numpy.array(faces)
        if not isinstance(offsets, numpy.ndarray):
            offsets = numpy.array(offsets)
        vertices_per_face = numpy.diff(offsets)
        connectivity_split = numpy.split(faces, numpy.cumsum(vertices_per_face[:-1]))
        elem_type = self.ELEMTYPE_N_SIDED_POLYGON
        all_same = numpy.all(numpy.array(vertices_per_face) == vertices_per_face[0])
        if all_same:
            num_vertices = vertices_per_face[0]
            _elem_type = self._elem_type_map.get(num_vertices)
            if _elem_type:
                elem_type = _elem_type
        if ghost:
            elem_type += 1
        self._check_updates_started()
        split_arrays = self._split_list(connectivity_split, self._total_ranks)
        split_num_faces = self._split_list(vertices_per_face, self._total_ranks)
        for c in range(self._client_count):
            client = self._clients[c]
            arrays = split_arrays[c]
            if len(arrays) > 1:
                indices = numpy.concatenate(arrays)
            elif arrays:
                indices = arrays[0]
            else:
                indices = numpy.array([])
            if elem_type not in [
                self.ELEMTYPE_N_SIDED_POLYGON,
                self.ELEMTYPE_N_SIDED_POLYGON_GHOST,
            ]:
                self.update_elements(
                    client["client_id"], part_id=part_id, elem_type=elem_type, indices=indices
                )
            else:
                connectivity_num_faces = split_num_faces[c]
                self.update_elements_polygon(
                    client["client_id"],
                    part_id=part_id,
                    elem_type=elem_type,
                    nodes_per_polygon=numpy.array(connectivity_num_faces),
                    indices=indices,
                )
        self._parts[part_id]["dvs_elem_type"] = elem_type

    def _check_timestep_count(self, timeout=120.0):
        """Check that there are no pending timesteps before loading data.

        Parameters
        ----------
        timeout: float
            the timeout to set while checking for pending timesteps
        """
        ready = False
        start = time.time()
        while not ready and time.time() - start < timeout:
            vals = []
            for server_id in self._server_ids:
                num_pending, num_complete = self.server_timestep_count(server_id)
                vals.append(num_pending == 0)
            ready = all(vals)
            if not ready:
                time.sleep(0.5)
        if not ready:
            raise RuntimeError(
                f"There are still pending timesteps within the input timeout of {timeout} seconds"
            )

    def load_dataset_in_ensight(self, timeout=120.0):
        """Launch the cached dataset in EnSight.

        Parameters
        ----------
        timeout: float
            the timeout to set while checking for pending timesteps
        """
        if not self._session:
            raise RuntimeError("A PyEnSight session must be available.")
        self._check_timestep_count(timeout=timeout)
        self._session.load_data(os.path.join(self._cache_folder, f"Simba_{self._dataset_name}.dvs"))

    def end_updates(self):
        """End the current updates."""
        for c in range(self._client_count):
            client = self._clients[c]
            _ = self.end_update(client["client_id"])
            client["update_started"] = False
        self._update_num += 1

    def delete_item_on_clients(self, update_num, filter=""):
        """Delete an item from all the running clients.

        Parameters
        ----------
        update_num: int
            the update number to remove from the database
        filter: str
            the filter to apply when deleting the update number
        """
        for c in range(self._client_count):
            client = self._clients[c]
            _ = self.delete_item(client["client_id"], update_num, client["rank"], filter)

    def get_dvs_data_from_container(self, destination: str, use_docker=False):
        """Utility to save the data from the container to a local destination.

        destination: str
            the folder where to copy the files to
        use_docker: bool
            if True, download is done using the docker CLI
        """
        if not isinstance(self._session._launcher, DockerLauncher):
            raise RuntimeError("Method only available for DockerLauncher instances.")
        if not os.path.exists(destination):
            os.makedirs(destination)
        posix_uri = pathlib.Path(destination).as_uri()
        if use_docker:
            bits, stat = self._session._launcher._container.get_archive(self._cache_folder)
            with tarfile.open(fileobj=io.BytesIO(b"".join(bits)), mode="r") as tar:
                safe_extract(tar, destination)
            os.remove(bits)
        else:
            self._session.copy_from_session(posix_uri, ["dvs_cache"])
