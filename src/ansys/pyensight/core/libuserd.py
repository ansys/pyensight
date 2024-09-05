"""libuserd module.

The ``libuserd`` module allows PyEnSight to directly access EnSight
user-defined readers (USERD).  Any file format for which EnSight
uses a USERD interface can be read using this API

Examples:

>>> from ansys.pyensight import libuserd
>>> userd = libuserd.LibUserd()
>>> userd.initialize()
>>> print(userd.library_version())
>>> datafile = "/example/data/CFX/Axial_001.res"
>>> readers = userd.query_format(datafile)
>>> data = readers[0].read_dataset(datafile)
>>> print(data.parts())
>>> print(data.variables())
>>> userd.shutdown()

"""
import enum
import os
import platform
import subprocess
import tempfile
import time
from typing import List, Optional, Tuple, Union
import uuid

from ansys.api.pyensight.v0 import libuserd_pb2, libuserd_pb2_grpc
import grpc
import numpy
import psutil


class LibUserdError(Exception):
    """
    This class represents an error returned from the libuserd
    library itself (not the gRPC remote interface).
    """

    def __init__(self, msg):
        super(LibUserdError, self).__init__(msg)
        self.code = libuserd_pb2.ErrorCodes.UNKNOWN_ERROR
        if msg.startswith("LibUserd("):
            try:
                self.code = int(msg[len("LibUserd(") :].split(")")[0])
            except Exception:
                pass

    @property
    def code(self):
        """The numeric error code: LibUserd.ErrorCodes"""
        return self.code


class Query(object):
    def __init__(self, userd: "LibUserd", pb: libuserd_pb2.QueryInfo):
        self._userd = userd
        self.id = pb.id
        self.name = pb.name
        self.x_title = pb.xTitle
        self.y_title = pb.yTitle
        self.metadata = {}
        for key in pb.metadata.keys():
            self.metadata[key] = pb.metadata[key]

    def __str__(self):
        return f"Query id: {self.id}, name: '{self.name}'"

    def data(self) -> List["numpy.array"]:
        self._userd.connect_check()
        pb = libuserd_pb2.Query_dataRequest()
        try:
            reply = self._userd.stub.Query_data(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        return [numpy.array(reply.x), numpy.array(reply.y)]


class Variable(object):
    def __init__(self, userd: "LibUserd", pb: libuserd_pb2.VariableInfo):
        self._userd = userd
        self.id = pb.id
        self.name = pb.name
        self.unitLabel = pb.unitLabel
        self.unitDims = pb.unitDims
        self.location = self._userd.VariableLocation(pb.varLocation)
        self.type = self._userd.VariableType(pb.type)
        self.timeVarying = pb.timeVarying
        self.isComplex = pb.isComplex
        self.interleaveFlag = pb.interleaveFlag
        self.numOfComponents = pb.numOfComponents
        self.metadata = {}
        for key in pb.metadata.keys():
            self.metadata[key] = pb.metadata[key]

    def __str__(self):
        return f"Variable id: {self.id}, name: '{self.name}', type: {self.type.name}, location: {self.location.name}"


class Part(object):
    def __init__(self, userd: "LibUserd", pb: libuserd_pb2.PartInfo):
        self._userd = userd
        self.index = pb.index
        self.id = pb.id
        self.name = pb.name
        self.reader_id = pb.reader_id
        self.host = pb.hints
        self.reader_api_version = pb.reader_api_version
        self.metadata = {}
        for key in pb.metadata.keys():
            self.metadata[key] = pb.metadata[key]

    def __str__(self):
        return f"Part id: {self.id}, name: '{self.name}'"

    def nodes(self) -> "numpy.array":
        self._userd.connect_check()
        pb = libuserd_pb2.Part_nodesRequest()
        pb.part_id = self.id
        try:
            stream = self._userd.stub.Part_nodes(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        nodes = numpy.empty(0, dtype=numpy.float32)
        for chunk in stream:
            if len(nodes) < chunk.total_size:
                nodes = numpy.empty(chunk.total_size, dtype=numpy.float32)
            offset = chunk.offset
            for f in chunk.xyz:
                nodes[offset] = f
                offset += 1
        return nodes

    def num_elements(self) -> dict:
        self._userd.connect_check()
        pb = libuserd_pb2.Part_num_elementsRequest()
        pb.part_id = self.id
        try:
            reply = self._userd.stub.Part_num_elements(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        elements = {}
        for key in reply.elementCount.keys():
            if reply.elementCount[key] > 0:
                elements[key] = reply.elementCount[key]
        return elements

    def element_conn(self, elem_type: int) -> "numpy.array":
        pb = libuserd_pb2.Part_element_connRequest()
        pb.part_id = self.id
        pb.elemType = elem_type
        try:
            stream = self._userd.stub.Part_element_conn(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        conn = numpy.empty(0, dtype=numpy.uint32)
        for chunk in stream:
            if len(conn) < chunk.total_size:
                conn = numpy.empty(chunk.total_size, dtype=numpy.uint32)
            offset = chunk.offset
            for i in chunk.connectivity:
                conn[offset] = i
                offset += 1
        return conn

    def element_conn_nsided(self, elem_type: int) -> List["numpy.array"]:
        self._userd.connect_check()
        pb = libuserd_pb2.Part_element_conn_nsidedRequest()
        pb.part_id = self.id
        pb.elemType = elem_type
        try:
            stream = self._userd.stub.Part_element_conn_nsided(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        nodes = numpy.empty(0, dtype=numpy.uint32)
        indices = numpy.empty(0, dtype=numpy.uint32)
        for chunk in stream:
            if len(nodes) < chunk.nodes_total_size:
                nodes = numpy.empty(chunk.nodes_total_size, dtype=numpy.uint32)
            if len(indices) < chunk.indices_total_size:
                indices = numpy.empty(chunk.indices_total_size, dtype=numpy.uint32)
            offset = chunk.nodes_offset
            for i in chunk.nodesPerPolygon:
                nodes[offset] = i
                offset += 1
            offset = chunk.indices_offset
            for i in chunk.nodeIndices:
                indices[offset] = i
                offset += 1
        return [nodes, indices]

    def element_conn_nfaced(self, elem_type: int) -> List["numpy.array"]:
        self._userd.connect_check()
        pb = libuserd_pb2.Part_element_conn_nfacedRequest()
        pb.part_id = self.id
        pb.elemType = elem_type
        try:
            stream = self._userd.stub.Part_element_conn_nfaced(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        face = numpy.empty(0, dtype=numpy.uint32)
        npf = numpy.empty(0, dtype=numpy.uint32)
        nodes = numpy.empty(0, dtype=numpy.uint32)
        for chunk in stream:
            if len(face) < chunk.face_total_size:
                face = numpy.empty(chunk.face_total_size, dtype=numpy.uint32)
            if len(npf) < chunk.npf_total_size:
                npf = numpy.empty(chunk.npf_total_size, dtype=numpy.uint32)
            if len(nodes) < chunk.nodes_total_size:
                nodes = numpy.empty(chunk.nodes_total_size, dtype=numpy.uint32)
            offset = chunk.face_offset
            for i in chunk.facesPerElement:
                face[offset] = i
                offset += 1
            offset = chunk.npf_offset
            for i in chunk.nodesPerFace:
                npf[offset] = i
                offset += 1
            offset = chunk.nodes_offset
            for i in chunk.nodeIndices:
                nodes[offset] = i
                offset += 1
        return [face, npf, nodes]

    def variable_values(
        self, variable: "Variable", elem_type: int = 0, complex: bool = False, component: int = 0
    ) -> "numpy.array":
        self._userd.connect_check()
        pb = libuserd_pb2.Part_variable_valuesRequest()
        pb.part_id = self.id
        pb.var_id = variable.id
        pb.elemType = elem_type
        pb.varComponent = component
        pb.complex = complex
        try:
            stream = self._userd.stub.Part_variable_values(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        v = numpy.empty(0, dtype=numpy.float32)
        for chunk in stream:
            if len(v) < chunk.total_size:
                v = numpy.empty(chunk.total_size, dtype=numpy.float32)
            offset = chunk.offset
            for f in chunk.varValues:
                v[offset] = f
                offset += 1
        return v

    def rigid_body_transform(self) -> dict:
        self._userd.connect_check()
        pb = libuserd_pb2.Part_rigid_body_transformRequest()
        pb.part_id = self.id
        try:
            reply = self._userd.stub.Part_rigid_body_transform(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        out = {
            "translation": numpy.array(reply.transform.translation),
            "euler_value": numpy.array(reply.transform.euler_value),
            "center_of_gravity": numpy.array(reply.transform.center_of_gravity),
            "rotation_order": reply.transform.rotation_order,
            "rotation_angles": numpy.array(reply.transform.rotation_angles),
        }
        return out


class Reader(object):
    def __init__(self, userd: "LibUserd", pb: libuserd_pb2.Reader):
        self._userd = userd
        self.unit_system = pb.unitSystem
        self.metadata = {}
        for key in pb.metadata.keys():
            self.metadata[key] = pb.metadata[key]
        self.raw_metadata = pb.raw_metadata

    def parts(self) -> List[Part]:
        self._userd.connect_check()
        pb = libuserd_pb2.Reader_partsRequest()
        try:
            parts = self._userd.stub.Reader_parts(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        out = []
        for part in parts.partList:
            out.append(Part(self._userd, part))
        return out

    def variables(self) -> List[Variable]:
        self._userd.connect_check()
        pb = libuserd_pb2.Reader_variablesRequest()
        try:
            variables = self._userd.stub.Reader_variables(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        out = []
        for variable in variables.variableList:
            out.append(Variable(self._userd, variable))
        return out

    def queries(self) -> List[Query]:
        self._userd.connect_check()
        pb = libuserd_pb2.Reader_queriesRequest()
        try:
            queries = self._userd.stub.Reader_queries(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        out = []
        for query in queries.queryList:
            out.append(Query(self._userd, query))
        return out

    def timevalues(self) -> List[float]:
        self._userd.connect_check()
        pb = libuserd_pb2.Reader_timevaluesRequest()
        pb.timeSetNumber = 1
        try:
            timevalues = self._userd.stub.Reader_timevalues(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        return numpy.array(timevalues.timeValues)

    def set_timevalue(self, timevalue: float) -> None:
        self._userd.connect_check()
        pb = libuserd_pb2.Reader_set_timevalueRequest()
        pb.timeSetNumber = 1
        try:
            _ = self._userd.stub.Reader_set_timevalue(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)

    def set_timestep(self, timestep: int) -> None:
        self._userd.connect_check()
        pb = libuserd_pb2.Reader_set_timestepRequest()
        pb.timeSetNumber = 1
        pb.timeStep = timestep
        try:
            _ = self._userd.stub.Reader_set_timestep(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)

    def is_geometry_changing(self) -> bool:
        self._userd.connect_check()
        pb = libuserd_pb2.Reader_is_geometry_changingRequest()
        try:
            reply = self._userd.stub.Reader_is_geometry_changing(
                pb, metadata=self._userd.metadata()
            )
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        return reply.isGeomChanging

    def variable_value(self, variable: "Variable") -> float:
        self._userd.connect_check()
        pb = libuserd_pb2.Reader_variable_valueRequest()
        pb.variable_id = variable.id
        try:
            reply = self._userd.stub.Reader_variable_value(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        return reply.value


class ReaderInfo(object):
    def __init__(self, userd: "LibUserd", pb: libuserd_pb2.ReaderInfo):
        self._userd = userd
        self.id = pb.id
        self.name = pb.name
        self.description = pb.description
        self.fileLabel1 = pb.fileLabel1
        self.fileLabel2 = pb.fileLabel2
        self.opt_booleans = []
        for b in pb.options.booleans:
            self.opt_booleans.append(dict(name=b.name, value=b.value, default=b.default_value))
        self.opt_options = []
        for o in pb.options.options:
            values = []
            for v in o.values:
                values.append(v)
            self.opt_options.append(
                dict(name=o.name, values=values, value=o.value_index, default=o.default_value_index)
            )
        self.opt_fields = []
        for f in pb.options.fields:
            self.opt_fields.append(dict(name=f.name, value=f.value, default=f.default_value))

    def read_dataset(self, file1: str, file2: str = "") -> "Reader":
        self._userd.connect_check()
        pb = libuserd_pb2.ReaderInfo_read_datasetRequest()
        pb.filename_1 = file1
        if file2:
            pb.filename_2 = file2
        pb.reader_id = self.id
        options = self._get_option_values()
        for b in options["booleans"]:
            pb.option_values_bools.append(b)
        for o in options["options"]:
            pb.option_values_options.append(o)
        for f in options["fields"]:
            pb.option_values_fields.append(f)
        try:
            reader = self._userd.stub.ReaderInfo_read_dataset(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        return Reader(self._userd, reader.reader)

    def _get_option_values(self) -> dict:
        out = dict()
        booleans = []
        for b in self.opt_booleans:
            booleans.append(b["value"])
        out["booleans"] = booleans
        options = []
        for o in self.opt_options:
            options.append(o["value"])
        out["options"] = options
        fields = []
        for f in self.opt_fields:
            fields.append(f["value"])
        out["fields"] = fields
        return out

    def __str__(self):
        return f"ReaderInfo id: {self.id}, name: {self.name}, description: {self.description}"


class LibUserd(object):
    def __init__(self, ansys_installation: str = ""):
        # find the pathname to the server
        self._server_pathname = self._find_ensight_server_name(
            ansys_installation=ansys_installation
        )
        if self._server_pathname is None:
            raise RuntimeError("Unable to detect an EnSight server installation.")
        # default to our token
        self._security_token = str(uuid.uuid1())
        self._grpc_port = 0
        self._host = "127.0.0.1"
        self._server_process = None
        self._channel = None
        self._stub = None

        # enums
        values = {}
        for v in libuserd_pb2.ErrorCodes.items():
            values[v[0]] = v[1]
        self.ErrorCodes = enum.IntEnum("ErrorCodes", values)  # type: ignore
        values = {}
        for v in libuserd_pb2.ElementType.items():
            values[v[0]] = v[1]
        self.ElementType = enum.IntEnum("ElementType", values)  # type: ignore
        values = {}
        for v in libuserd_pb2.VariableLocation.items():
            values[v[0]] = v[1]
        self.VariableLocation = enum.IntEnum("VariableLocation", values)  # type: ignore
        values = {}
        for v in libuserd_pb2.VariableType.items():
            values[v[0]] = v[1]
        self.VariableType = enum.IntEnum("VariableType", values)  # type: ignore
        values = {}
        for v in libuserd_pb2.PartHints.items():
            values[v[0]] = v[1]
        self.PartHints = enum.IntEnum("PartHints", values)  # type: ignore

        # have the server save status so we can read it later
        with tempfile.TemporaryDirectory() as tmpdirname:
            self._security_file = os.path.join(tmpdirname, "security.grpc")

            # Build the command line
            cmd = [self.server_pathname]
            cmd.extend(["-grpc_server", str(self.grpc_port)])
            cmd.extend(["-security_file", self._security_file])
            env_vars = os.environ.copy()
            if self.security_token:
                env_vars["ENSIGHT_SECURITY_TOKEN"] = self.security_token
            env_vars["ENSIGHT_GRPC_SECURITY_FILE"] = self._security_file
            # start the server
            try:
                self._server_process = subprocess.Popen(
                    cmd,
                    close_fds=True,
                    env=env_vars,
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                )
            except Exception as error:
                raise error

            start_time = time.time()
            while (self._grpc_port == 0) and (time.time() - start_time < 20.0):
                try:
                    # Read the port and security token from the security file
                    with open(self._security_file, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("grpc_port:"):
                                self._grpc_port = int(line[len("grpc_port:") :])
                            elif line.startswith("grpc_password:"):
                                self._security_token = line[len("grpc_password:") :]
                except (OSError, IOError):
                    pass

            # Unable to get the grpc port/password
            if self._grpc_port == 0:
                self.shutdown()
                raise RuntimeError("Unable to start the gRPC server.")

            # Build the gRPC connection
            self._connect()

    @property
    def stub(self):
        """A libuserd_pb2_grpc.LibUSERDServiceStub instance bound to a gRPC connection channel"""
        return self._stub

    @property
    def server_pathname(self):
        return self._server_pathname

    @property
    def security_token(self):
        """The current gRPC security token"""
        return self._security_token

    @property
    def grpc_port(self):
        """The current gRPC port"""
        return self._grpc_port

    def __del__(self) -> None:
        self.shutdown()

    @staticmethod
    def _find_ensight_server_name(ansys_installation: str = "") -> Optional[str]:
        """
        Parameters
        ----------
        ansys_installation : str
            Path to the local Ansys installation, including the version
            directory. The default is ``None``, in which case common locations
            are scanned to detect the latest local Ansys installation. The
            ``PYENSIGHT_ANSYS_INSTALLATION`` environmental variable is checked first.

        Returns
        -------
            The first valid ensight_server found or None

        """
        dirs_to_check = []
        if ansys_installation:
            dirs_to_check.append(ansys_installation)

        if "PYENSIGHT_ANSYS_INSTALLATION" in os.environ:
            env_inst = os.environ["PYENSIGHT_ANSYS_INSTALLATION"]
            dirs_to_check.append(env_inst)
            # Note: PYENSIGHT_ANSYS_INSTALLATION is designed for devel builds
            # where there is no CEI directory, but for folks using it in other
            # ways, we'll add that one too, just in case.
            dirs_to_check.append(os.path.join(env_inst, "CEI"))

        if "CEI_HOME" in os.environ:
            env_inst = os.environ["CEI_HOME"]
            dirs_to_check.append(env_inst)

        # Look for most recent Ansys install
        awp_roots = []
        for env_name in dict(os.environ).keys():
            if env_name.startswith("AWP_ROOT"):
                try:
                    version = int(env_name[len("AWP_ROOT") :])
                    # this API is new in 2025 R1 distributions
                    if version >= 251:
                        awp_roots.append(env_name)
                except ValueError:
                    pass
        awp_roots.sort(reverse=True)
        for env_name in awp_roots:
            dirs_to_check.append(os.path.join(os.environ[env_name], "CEI"))

        # check all the collected locations in order
        app_name = "ensight_server"
        if platform.system() == "Windows":
            app_name += ".bat"
        for install_dir in dirs_to_check:
            launch_file = os.path.join(install_dir, "bin", app_name)
            if os.path.isfile(launch_file):
                return launch_file
        return None

    def _is_connected(self) -> bool:
        """Check to see if the gRPC connection is live

        Returns
        -------
             True if the connection is active.
        """
        return self._channel is not None

    def _connect(self, timeout: float = 15.0) -> None:
        """Establish the gRPC connection to EnSight

        Attempt to connect to an EnSight gRPC server using the host and port
        established by the constructor.  Note on failure, this function just
        returns, but is_connected() will return False.

        Parameters
        ----------
        timeout: float
            how long to wait for the connection to timeout
        """
        if self._is_connected():
            return
        # set up the channel
        self._channel = grpc.insecure_channel(
            "{}:{}".format(self._host, self._grpc_port),
            options=[
                ("grpc.max_receive_message_length", -1),
                ("grpc.max_send_message_length", -1),
                ("grpc.testing.fixed_reconnect_backoff_ms", 1100),
            ],
        )
        try:
            grpc.channel_ready_future(self._channel).result(timeout=timeout)
        except grpc.FutureTimeoutError:  # pragma: no cover
            self._channel = None  # pragma: no cover
            return  # pragma: no cover
        # hook up the stub interface
        self._stub = libuserd_pb2_grpc.LibUSERDServiceStub(self._channel)

    def metadata(self) -> List[Tuple[bytes, Union[str, bytes]]]:
        """Compute the gRPC stream metadata

        Compute the list to be passed to the gRPC calls for things like security
        and the session name.

        Returns
        -------
            A list object of the metadata elements needed in a gRPC call to
            satisfy the EnSight server gRPC requirements.
        """
        ret: List[Tuple[bytes, Union[str, bytes]]] = list()
        s: Union[str, bytes]
        if self._security_token:  # pragma: no cover
            s = self._security_token
            if type(s) == str:  # pragma: no cover
                s = s.encode("utf-8")
            ret.append((b"shared_secret", s))
        return ret

    def libuserd_exception(self, e: grpc.RpcError) -> Exception:
        """
        Given an exception raised as the result of a gRPC call, return either
        the input exception or a LibUserdError exception object to differentiate
        between gRPC issues and libuserd issues.

        Parameters
        ----------
        e
            The exception raised by a gRPC call.

        Returns
        -------
            Either the original exception or a LibUserdError exception instance, depending on
            the original exception message details.
        """
        msg = e.details()
        if msg.startswith("LibUserd("):
            return LibUserdError(msg)
        return e

    def _disconnect(self, no_error: bool = False) -> None:
        """Close down the gRPC connection

        Disconnect all connections to the gRPC server.  Send the shutdown request gRPC command
        to the server first.

        Parameters
        ----------
        no_error
            If true, ignore errors resulting from the shutdown operation.
        """
        if not self._is_connected():  # pragma: no cover
            return
        # Note: this is expected to return an error
        try:
            pb = libuserd_pb2.Libuserd_shutdownRequest()
            self._stub.Libuserd_shutdown(pb, metadata=self.metadata())  # type: ignore
            if self._channel:
                self._channel.close()
        except grpc.RpcError as e:
            if not no_error:
                raise self.libuserd_exception(e)
        finally:
            # clean up control objects
            self._stub = None
            self._channel = None

    def connect_check(self) -> None:
        """
        Verify that there is an active gRPC connection established.  If not raise
        a RuntimeError

        Raises
        ------
            RuntimeError if there is no active connection.
        """
        if not self._is_connected():
            raise RuntimeError("gRPC connection not established")

    """
    gRPC method bindings
    """

    def shutdown(self) -> None:
        """
        Close any active gRPC connection and shut down the EnSight server.
        The object is no longer usable.
        """
        self._disconnect(no_error=True)
        # Just in case, we will try to kill the server directly as well
        if self._server_process:
            if psutil.pid_exists(self._server_process.pid):
                proc = psutil.Process(self._server_process.pid)
                for child in proc.children(recursive=True):
                    if psutil.pid_exists(child.pid):
                        # This can be a race condition, so it is ok if the child is dead already
                        try:
                            child.kill()
                        except psutil.NoSuchProcess:
                            pass
                # Same issue, this process might already be shutting down, so NoSuchProcess is ok.
                try:
                    proc.kill()
                except psutil.NoSuchProcess:
                    pass
        self._server_process = None

    def ansys_release_string(self) -> str:
        self.connect_check()
        pb = libuserd_pb2.Libuserd_ansys_release_stringRequest()
        try:
            ret = self.stub.Libuserd_ansys_release_string(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def ansys_release_number(self) -> int:
        self.connect_check()
        pb = libuserd_pb2.Libuserd_ansys_release_numberRequest()
        try:
            ret = self.stub.Libuserd_ansys_release_number(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def library_version(self) -> str:
        self.connect_check()
        pb = libuserd_pb2.Libuserd_library_versionRequest()
        try:
            ret = self.stub.Libuserd_library_version(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def nodes_per_element(self, element_type: int) -> int:
        self.connect_check()
        pb = libuserd_pb2.Libuserd_nodes_per_elementRequest()
        pb.element_type = element_type
        try:
            ret = self.stub.Libuserd_nodes_per_element(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def element_is_ghost(self, element_type: int) -> bool:
        self.connect_check()
        pb = libuserd_pb2.Libuserd_element_is_ghostRequest()
        pb.element_type = element_type
        try:
            ret = self.stub.Libuserd_element_is_ghost(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def element_is_zoo(self, element_type: int) -> bool:
        self.connect_check()
        pb = libuserd_pb2.Libuserd_element_is_zooRequest()
        pb.element_type = element_type
        try:
            ret = self.stub.Libuserd_element_is_zoo(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def element_is_nsided(self, element_type: int) -> bool:
        self.connect_check()
        pb = libuserd_pb2.Libuserd_element_is_nsidedRequest()
        pb.element_type = element_type
        try:
            ret = self.stub.Libuserd_element_is_nsided(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def element_is_nfaced(self, element_type: int) -> bool:
        self.connect_check()
        pb = libuserd_pb2.Libuserd_element_is_nfacedRequest()
        pb.element_type = element_type
        try:
            ret = self.stub.Libuserd_element_is_nfaced(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def number_of_simple_element_types(self) -> int:
        self.connect_check()
        pb = libuserd_pb2.Libuserd_number_of_simple_element_typesRequest()
        try:
            ret = self.stub.Libuserd_number_of_simple_element_types(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def initialize(self) -> None:
        self.connect_check()
        pb = libuserd_pb2.Libuserd_initializeRequest()
        try:
            _ = self.stub.Libuserd_initialize(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)

    def get_all_readers(self) -> List["ReaderInfo"]:
        self.connect_check()
        pb = libuserd_pb2.Libuserd_get_all_readersRequest()
        try:
            readers = self.stub.Libuserd_get_all_readers(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        out = []
        for reader in readers.readerInfo:
            out.append(ReaderInfo(self, reader))
        return out

    def query_format(self, name1: str, name2: str = "") -> List["ReaderInfo"]:
        self.connect_check()
        pb = libuserd_pb2.Libuserd_query_formatRequest()
        pb.name1 = name1
        if name2:
            pb.name2 = name2
        try:
            readers = self.stub.Libuserd_query_format(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        out = []
        for reader in readers.readerInfo:
            out.append(ReaderInfo(self, reader))
        return out
