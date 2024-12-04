from ansys.api.pyensight.dvs_api import dvs_base

from typing import Dict, List, Optional, TYPE_CHECKING, Union
import glob
import os
import numpy
import pathlib
import platform
import re
import sys
import traceback
import tempfile
from math import floor
from ansys.pyensight.core.common import find_unused_ports

if TYPE_CHECKING:
    from ansys.pyensight.core import Session

SERVER_ID_MASK = 8388608


class DVS(dvs_base):

    def __init__(self, 
                 session: Optional["Session"]=None, 
                 ansys_installation: Optional[str]=None,
                 lib_folder: Optional[str]=None) -> None:
        super().__init__(session=session)
        self._ansys_installation = ansys_installation
        self._lib_folder = lib_folder
        if self._session:
            if not self._ansys_installation:
                self._ansys_installation = os.path.dirname(self._session._launcher._install_path)
        if not self._session and not self._ansys_installation and not self._lib_folder:
            raise RuntimeError("Either a PyEnSight session or an ansys installation path, or a folder containing the DVS Python modules need to be provided.")
        self._connect_session = self._session
        self._servers: Dict[int, Dict[str, Union[str, int]]] = {}
        self._server_ids: List[int] = []
        self._clients: Dict[int, Dict[str, Union[str, int]]]  = {}
        self._client_count = 0
        self._build_python_path()
        self._parts: Dict[int, Dict[str, Union[str, int]]] = {}
        self._vars: Dict[int, Dict[str, Union[str, int]]] = {}
        self._update_num = 0
        self._current_update = 0
        self._elem_type_map = {
            2: self.ELEMTYPE_BAR_2,
            3: self.ELEMTYPE_TRIANGLE,
            4: self.ELEMTYPE_QUADRANGLE,
        }
        self._total_ranks = 0
        self._temp_cache = tempfile.TemporaryDirectory(prefix="pyensight_dvs")
        os.mkdir(os.path.join(self._temp_cache.name, "dvs_cache"))
        self._cache_folder = os.path.join(self._temp_cache.name, "dvs_cache")
        self._dataset_name = None

    @staticmethod
    def _is_windows():
        return "Win" in platform.system()

    def _build_python_path(self):
        if self._lib_folder:
            try:
                sys.path.append(self._lib_folder)
                import dynamic_visualization_store
                self._dvs_module = dynamic_visualization_store
            except (ModuleNotFoundError, ImportError):
                raise RuntimeError("Cannot import DVS module from provided library folder.")
        if self._ansys_installation:
            # Check if you are inside of an ansys install
            cei_install = os.path.join(self._ansys_installation, "CEI")
            apex_path = glob.glob(os.path.join(cei_install, "apex???"))
            if not apex_path:
                # try dev path
                apex_path = glob.glob(os.path.join(self._ansys_installation, "apex???"))
                if not apex_path:
                    raise RuntimeError("Cannot find a valid EnSight install")
            apex_path = apex_path[-1]
            arch = "win64" if self._is_windows() else "linux_2.6_64"
            apex_libs = os.path.join(apex_path, "machines", arch)
            python_path = glob.glob(os.path.join(apex_libs, "Python-*"))[-1]
            apex_py_version = re.search("Python-3.([0-9]+).([0-9]+)", os.path.basename(python_path))
            apex_py_major_version = apex_py_version.group(1)
            lib_path = os.path.join(python_path, "lib", f"python3.{apex_py_major_version}")
            if self._is_windows():
                lib_path = os.path.join(python_path, "DLLs")
            sys.path.append(lib_path)
            try:
                import dynamic_visualization_store
                self._dvs_module = dynamic_visualization_store
            except (ModuleNotFoundError, ImportError):
                raise RuntimeError("Cannot import DVS module from provided ansys installation folder.")
    
    DVS_NULL_TRANSPORT = 0
    DVS_GRPC_TRANSPORT = 1

    def connect_pyensight_session(self, session: "Session"):
        self._session = session

    def start_dvs_servers(self, num_servers: int, transport: int= 0, ranks_per_server: int= 1, secret_key: str= ""):
        transport_string = "null" if transport == 0 else "grpc"
        uri = f"{transport_string}://"
        grpc = transport == self.DVS_GRPC_TRANSPORT
        options = {
            "CACHE_URI": f"hdf5:///{pathlib.Path(self._cache_folder).as_posix()}"
        }
        if grpc:
            ports = find_unused_ports(3)
            uri += "127.0.0.1"
            options.update({
                "SERVER_SECURITY_SECRET": secret_key,
            })
        try:
            for n in range(0, num_servers):
                # Assume ranks equally distributed
                local_uri = uri + f":{ports[n]}"
                server_id = self.server_create(uri=local_uri)
                self.server_start(server_id, server_num=n, local_ranks=ranks_per_server, options=options)
                self._server_ids.append(server_id)
                self._servers[n] = {
                    "server_id": server_id,
                    "ranks": ranks_per_server,
                    "in_ensight": False
                }
                if grpc:
                    uri_to_save = self.server_get_uri(server_id)
                    port = int(re.search(":([0-9]+)", uri_to_save).group(1))
                    self._servers[n].update(
                        {
                            "server_uri": uri_to_save,
                            "port": port
                        }
                    )
            self._total_ranks = ranks_per_server * len(self._server_ids)
        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Couldn't start the servers, error: {e}")

    def _start_dvs_client(self, server_id: int, rank: int, secret_key="", block_for_servers=False, dedup=False):
        if server_id not in self._server_ids:
            raise RuntimeError(f"Server ID {server_id} not started in this process.")
        flags = self.FLAGS_NONE
        if block_for_servers:
            flags &= self.FLAGS_BLOCK_FOR_SERVER
        if dedup:
            flags &= self.FLAGS_DEDUP
        try:
            client_id = self.connect(server_id=server_id, secret=secret_key, flags=flags)
        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Couldn't start the client, error {e}")
        self._clients[self._client_count] = {
            "client_id": client_id,
            "server_id": server_id,
            "rank": rank
        }
        self._client_count += 1
    
    @staticmethod
    def _generate_server_id_for_ensight_dvs_server(num_server):
        return num_server | SERVER_ID_MASK 
    
    def start_servers_in_ensight(self, secret_key= ""):
        if not self._session:
            raise RuntimeError("A PyEnSight session is required to start the DVS servers in EnSight.")
        thread, port = self._session.ensight.utils.readers.dvs.launch_live_dvs(secret_key=secret_key)
        num_servers = self._session._launcher._use_sos or 1
        base_uri = f"grpc://{self._session.hostname}"
        # Need to implement SOS support in session.ensight.utils.readers.dvs.launch_live_dvs
        for n in range(num_servers):
            server_id = self._generate_server_id_for_ensight_dvs_server(n)
            self._servers[n] = {
                "server_uri": base_uri+ ":{}".format(port+n),
                "port": port+n,
                "server_id": server_id,
                "in_ensight": True
            }

    def start_sending_dataset(self, dataset_name: str, secret_key: str = "", block_for_servers=False, dedup=False):
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
            self._start_dvs_client(server["server_id"], rank, secret_key=secret_key, block_for_servers=block_for_servers, dedup=dedup)
        
    def begin_updates(self, time):
        update_num = self._update_num
        self._current_update = update_num
        for _, client_vals in self._clients.items():
            self.begin_update(client_vals["client_id"], update_num, time, client_vals["rank"], 0)
        self._update_num += 1
    
    def create_part(self, part_id: int, part_name: int, metadata: Optional[Dict[str, str]]=None):
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
            "tags": metadata
        }
        for c in range(self._client_count):
            client = self._clients[c]
            self.begin_init(self._clients[self._client_count-1]["client_id"], dataset_name=f"Simba_{self._dataset_name}_{part_name}", rank=client["rank"], total_ranks=self._total_ranks, num_chunks=1)
            self.add_part_info(client["client_id"], [part])
        for c in range(self._client_count):
            client = self._clients[c]
            self.end_init(client["client_id"])
        self._parts[part_id] = part
    
    
    def send_vertices(self, part_id, vertices):
        if not self._parts.get(part_id):
            raise RuntimeError("Please create the part first via create_part() or the lower level add_part_info.")
        if not self._parts[part_id].get("vert_indices"):
            raise RuntimeError(f"Please send first the faces for part {part_id}")
        if not isinstance(vertices, numpy.ndarray):
            vertices = numpy.ndarray(vertices)
        reshaped_vertices = vertices.reshape(-1, 3)
        x_coords = reshaped_vertices[:, 0]
        y_coords = reshaped_vertices[:, 1]
        z_coords = reshaped_vertices[:, 2]
        vert_indices = self._parts[part_id]["vert_indices"]
        self.update_nodes(client["client_id"], part_id=part_id,x=x_coords[vert_indices], y=y_coords[vert_indices], z=z_coords[vert_indices])
        del self._parts[part_id]["vert_indices"]

    def send_faces(self, part_id, faces: Union[List, numpy.ndarray], ghost=False):
        if not self._clients:
            raise RuntimeError("No DVS clients started yet.")
        if not self._parts.get(part_id):
            raise RuntimeError("Please create the part first via create_part() or the lower level add_part_info.")
        if not isinstance(faces, numpy.ndarray):
            faces = numpy.ndarray(faces)
        i = 0
        vertices_per_face = []
        connectivity_1d = []
        while i < len(faces):
            num_vertices = faces[i]
            vertices_per_face.append(num_vertices)
            connectivity_1d.extend(faces[i+1:i+1+num_vertices])
            i += num_vertices + 1
        connectivity_split = numpy.split(connectivity_1d, numpy.cumsum(vertices_per_face[:-1]))
        all_same = numpy.all(numpy.array(vertices_per_face) == vertices_per_face[0])
        num_split = floor(len(connectivity_split) / self._total_ranks)
        additional = len(connectivity_split) % self._total_ranks
        elem_type = self.ELEMTYPE_N_SIDED_POLYGON
        if all_same:
            num_vertices = vertices_per_face[0]
            _elem_type = self._elem_type_map.get(num_vertices)
            if _elem_type:
                elem_type = _elem_type
        if ghost:
            elem_type += 1
        for c in range(self._client_count):
            client = self._clients[c]
            arrays = connectivity_split[c:c+num_split-1]
            if additional and c==self._client_count-1:
                arrays.extend(connectivity_split[-1*additional:])
            indices = numpy.concatenate(arrays)
            vert_indices = numpy.unique(indices)
            self._parts[part_id]["vert_indices"] = vert_indices
            if elem_type not in [self.ELEMTYPE_N_SIDED_POLYGON, self.ELEMTYPE_N_SIDED_POLYGON_GHOST]:
                self.update_elements(client["client_id"], part_id=part_id, elem_type=elem_type, indices=indices)
            else:
                connectivity_num_faces = vertices_per_face[c:c+num_split-1]
                self.update_elements_polygon(client["client_id"], part_id=part_id, elem_type=elem_type, nodes_per_polygon=numpy.array(connectivity_num_faces), indices=indices)
                
    def load_dataset_in_ensight(self):
        if not self._session:
            raise RuntimeError("A PyEnSight session must be available.")
        self._session.load_data(os.path.join(self._temp_cache.name, f"{self._dataset_name}.dvs"))
    
    def send_done(self):
        for c in range(self._client_count):
            client = self._clients[c]
            self.end_update(client["client_id"])
        self._update_num += 1









    





    