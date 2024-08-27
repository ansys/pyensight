import hashlib
import json
import logging
import os
import queue
import sys
import threading
import time
from typing import Any, Dict, List, Optional

from ansys.api.pyensight.v0 import dynamic_scene_graph_pb2
from ansys.pyensight.core import ensight_grpc
import numpy


class Part(object):
    def __init__(self, session: "DSGSession"):
        """
        This object roughly represents an EnSight "Part".  It contains the connectivity,
        coordinates, normals and texture coordinate information for one DSG entity

        This object stores basic geometry information coming from the DSG protocol.  The
        update_geom() method can parse an "UpdateGeom" protobuffer and merges the results
        into the Part object.

        Parameters
        ----------
        session:
            The DSG connection session object.
        """
        self.session = session
        self.conn_tris = numpy.array([], dtype="int32")
        self.conn_lines = numpy.array([], dtype="int32")
        self.coords = numpy.array([], dtype="float32")
        self.normals = numpy.array([], dtype="float32")
        self.normals_elem = False
        self.tcoords = numpy.array([], dtype="float32")
        self.tcoords_elem = False
        self.node_sizes = numpy.array([], dtype="float32")
        self.cmd: Optional[Any] = None
        self.hash = hashlib.new("sha256")
        self.reset()

    def reset(self, cmd: Any = None) -> None:
        self.conn_tris = numpy.array([], dtype="int32")
        self.conn_lines = numpy.array([], dtype="int32")
        self.coords = numpy.array([], dtype="float32")
        self.normals = numpy.array([], dtype="float32")
        self.normals_elem = False
        self.tcoords = numpy.array([], dtype="float32")
        self.tcoords_var_id = None
        self.tcoords_elem = False
        self.node_sizes = numpy.array([], dtype="float32")
        self.hash = hashlib.new("sha256")
        if cmd is not None:
            self.hash.update(cmd.hash.encode("utf-8"))
        self.cmd = cmd

    def update_geom(self, cmd: dynamic_scene_graph_pb2.UpdateGeom) -> None:
        """
        Merge an update geometry command into the numpy buffers being cached in this object

        Parameters
        ----------
        cmd:
            This is an array update command.  It could be for coordinates, normals, variables, connectivity, etc.
        """
        if cmd.payload_type == dynamic_scene_graph_pb2.UpdateGeom.COORDINATES:
            if self.coords.size != cmd.total_array_size:
                self.coords = numpy.resize(self.coords, cmd.total_array_size)
            self.coords[cmd.chunk_offset : cmd.chunk_offset + len(cmd.flt_array)] = cmd.flt_array
        elif cmd.payload_type == dynamic_scene_graph_pb2.UpdateGeom.TRIANGLES:
            if self.conn_tris.size != cmd.total_array_size:
                self.conn_tris = numpy.resize(self.conn_tris, cmd.total_array_size)
            self.conn_tris[cmd.chunk_offset : cmd.chunk_offset + len(cmd.int_array)] = cmd.int_array
        elif cmd.payload_type == dynamic_scene_graph_pb2.UpdateGeom.LINES:
            if self.conn_lines.size != cmd.total_array_size:
                self.conn_lines = numpy.resize(self.conn_lines, cmd.total_array_size)
            self.conn_lines[
                cmd.chunk_offset : cmd.chunk_offset + len(cmd.int_array)
            ] = cmd.int_array
        elif (cmd.payload_type == dynamic_scene_graph_pb2.UpdateGeom.ELEM_NORMALS) or (
            cmd.payload_type == dynamic_scene_graph_pb2.UpdateGeom.NODE_NORMALS
        ):
            self.normals_elem = cmd.payload_type == dynamic_scene_graph_pb2.UpdateGeom.ELEM_NORMALS
            if self.normals.size != cmd.total_array_size:
                self.normals = numpy.resize(self.normals, cmd.total_array_size)
            self.normals[cmd.chunk_offset : cmd.chunk_offset + len(cmd.flt_array)] = cmd.flt_array
        elif (cmd.payload_type == dynamic_scene_graph_pb2.UpdateGeom.ELEM_VARIABLE) or (
            cmd.payload_type == dynamic_scene_graph_pb2.UpdateGeom.NODE_VARIABLE
        ):
            # Get the variable definition
            if cmd.variable_id in self.session.variables:
                if self.cmd.color_variableid == cmd.variable_id:  # type: ignore
                    # Receive the colorby var values
                    self.tcoords_elem = (
                        cmd.payload_type == dynamic_scene_graph_pb2.UpdateGeom.ELEM_VARIABLE
                    )
                    if self.tcoords.size != cmd.total_array_size:
                        self.tcoords = numpy.resize(self.tcoords, cmd.total_array_size)
                    self.tcoords[
                        cmd.chunk_offset : cmd.chunk_offset + len(cmd.flt_array)
                    ] = cmd.flt_array
                if self.cmd.node_size_variableid == cmd.variable_id:  # type: ignore
                    # Receive the node size var values
                    if self.node_sizes.size != cmd.total_array_size:
                        self.node_sizes = numpy.resize(self.node_sizes, cmd.total_array_size)
                    self.node_sizes[
                        cmd.chunk_offset : cmd.chunk_offset + len(cmd.flt_array)
                    ] = cmd.flt_array
        # Combine the hashes for the UpdatePart and all UpdateGeom messages
        self.hash.update(cmd.hash.encode("utf-8"))

    def nodal_surface_rep(self):
        """
        This function processes the geometry arrays and converts them into nodal representation.
        It will duplicate triangles as needed (to preserve element normals) and will convert
        variable data into texture coordinates.

        Returns
        -------
        On failure, the method returns None for the first return value.  The returned tuple is:

        (part_command, vertices, connectivity, normals, tex_coords, var_command)

        part_command: UPDATE_PART command object
        vertices: numpy array of the nodal coordinates
        connectivity: numpy array of the triangle indices into the vertices array
        normals: numpy array of per vertex normal values (optional)
        tcoords: numpy array of per vertex texture coordinates (optional)
        var_command: UPDATE_VARIABLE command object for the variable the texture coordinate correspond to, if any
        """
        if self.cmd is None:
            return None, None, None, None, None, None
        if self.conn_tris.size == 0:
            self.session.log(f"Note: part '{self.cmd.name}' contains no triangles.")
            return None, None, None, None, None, None
        verts = self.coords
        self.normalize_verts(verts)

        conn = self.conn_tris
        normals = self.normals
        tcoords = None
        if self.tcoords.size:
            tcoords = self.tcoords
        if self.tcoords_elem or self.normals_elem:
            verts_per_prim = 3
            num_prims = int(conn.size / verts_per_prim)
            # "flatten" the triangles to move values from elements to nodes
            new_verts = numpy.ndarray((num_prims * verts_per_prim * 3,), dtype="float32")
            new_conn = numpy.ndarray((num_prims * verts_per_prim,), dtype="int32")
            new_tcoords = None
            if tcoords is not None:
                # remember that the input values are 1D at this point, we will expand to 2D later
                new_tcoords = numpy.ndarray((num_prims * verts_per_prim,), dtype="float32")
            new_normals = None
            if normals is not None:
                if normals.size == 0:
                    self.session.log("Warning: zero length normals!")
                else:
                    new_normals = numpy.ndarray((num_prims * verts_per_prim * 3,), dtype="float32")
            j = 0
            for i0 in range(num_prims):
                for i1 in range(verts_per_prim):
                    idx = conn[i0 * verts_per_prim + i1]
                    # new connectivity (identity)
                    new_conn[j] = j
                    # copy the vertex
                    new_verts[j * 3 + 0] = verts[idx * 3 + 0]
                    new_verts[j * 3 + 1] = verts[idx * 3 + 1]
                    new_verts[j * 3 + 2] = verts[idx * 3 + 2]
                    if new_normals is not None:
                        if self.normals_elem:
                            # copy the normal associated with the face
                            new_normals[j * 3 + 0] = normals[i0 * 3 + 0]
                            new_normals[j * 3 + 1] = normals[i0 * 3 + 1]
                            new_normals[j * 3 + 2] = normals[i0 * 3 + 2]
                        else:
                            # copy the same normal as the vertex
                            new_normals[j * 3 + 0] = normals[idx * 3 + 0]
                            new_normals[j * 3 + 1] = normals[idx * 3 + 1]
                            new_normals[j * 3 + 2] = normals[idx * 3 + 2]
                    if new_tcoords is not None:
                        # remember, 1D texture coords at this point
                        if self.tcoords_elem:
                            # copy the texture coord associated with the face
                            new_tcoords[j] = tcoords[i0]
                        else:
                            # copy the same texture coord as the vertex
                            new_tcoords[j] = tcoords[idx]
                    j += 1
            # new arrays.
            verts = new_verts
            conn = new_conn
            normals = new_normals
            if tcoords is not None:
                tcoords = new_tcoords

        var_cmd = None
        # texture coords need transformation from variable value to [ST]
        if tcoords is not None:
            var_dsg_id = self.cmd.color_variableid
            var_cmd = self.session.variables[var_dsg_id]
            v_min = None
            v_max = None
            for lvl in var_cmd.levels:
                if (v_min is None) or (v_min > lvl.value):
                    v_min = lvl.value
                if (v_max is None) or (v_max < lvl.value):
                    v_max = lvl.value
            var_minmax = [v_min, v_max]
            # build a power of two x 1 texture
            num_texels = int(len(var_cmd.texture) / 4)
            half_texel = 1 / (num_texels * 2.0)
            num_verts = int(verts.size / 3)
            tmp = numpy.ndarray((num_verts * 2,), dtype="float32")
            tmp.fill(0.5)  # fill in the T coordinate...
            tex_width = half_texel * 2 * (num_texels - 1)  # center to center of num_texels
            # if the range is 0, adjust the min by -1.   The result is that the texture
            # coords will get mapped to S=1.0 which is what EnSight does in this situation
            if (var_minmax[1] - var_minmax[0]) == 0.0:
                var_minmax[0] = var_minmax[0] - 1.0
            var_width = var_minmax[1] - var_minmax[0]
            for idx in range(num_verts):
                # normalized S coord value (clamp)
                s = (tcoords[idx] - var_minmax[0]) / var_width
                if s < 0.0:
                    s = 0.0
                if s > 1.0:
                    s = 1.0
                # map to the texture range and set the S value
                tmp[idx * 2] = s * tex_width + half_texel
            tcoords = tmp

        self.session.log(
            f"Part '{self.cmd.name}' defined: {self.coords.size/3} verts, {self.conn_tris.size/3} tris."
        )
        command = self.cmd

        return command, verts, conn, normals, tcoords, var_cmd

    def normalize_verts(self, verts: numpy.ndarray):
        """
        This function scales and translates vertices, so the longest axis in the scene is of
        length 1.0, and data is centered at the origin

        Returns the scale factor
        """
        s = 1.0
        if self.session.normalize_geometry and self.session.scene_bounds is not None:
            num_verts = int(verts.size / 3)
            midx = (self.session.scene_bounds[3] + self.session.scene_bounds[0]) * 0.5
            midy = (self.session.scene_bounds[4] + self.session.scene_bounds[1]) * 0.5
            midz = (self.session.scene_bounds[5] + self.session.scene_bounds[2]) * 0.5
            dx = self.session.scene_bounds[3] - self.session.scene_bounds[0]
            dy = self.session.scene_bounds[4] - self.session.scene_bounds[1]
            dz = self.session.scene_bounds[5] - self.session.scene_bounds[2]
            s = dx
            if dy > s:
                s = dy
            if dz > s:
                s = dz
            if s == 0:
                s = 1.0
            for i in range(num_verts):
                j = i * 3
                verts[j + 0] = (verts[j + 0] - midx) / s
                verts[j + 1] = (verts[j + 1] - midy) / s
                verts[j + 2] = (verts[j + 2] - midz) / s
        return 1.0 / s

    def point_rep(self):
        """
        This function processes the geometry arrays and returns values to represent point data

        Returns
        -------
        On failure, the method returns None for the first return value.  The returned tuple is:

        (part_command, vertices, sizes, colors, var_command)

        part_command: UPDATE_PART command object
        vertices: numpy array of per-node coordinates
        sizes: numpy array of per-node radii
        colors: numpy array of per-node rgb colors
        var_command: UPDATE_VARIABLE command object for the variable the colors correspond to, if any
        """
        if self.cmd is None:
            return None, None, None, None, None
        if self.cmd.render != self.cmd.NODES:
            # Early out.  Rendering type for this object is a surface rep, not a point rep
            return None, None, None, None, None
        verts = self.coords
        num_verts = int(verts.size / 3)
        norm_scale = self.normalize_verts(verts)

        # Convert var values in self.tcoords to RGB colors
        # For now, look up RGB colors.  Planned USD enhancements should allow tex coords instead.
        colors = None
        var_cmd = None

        if self.tcoords.size and self.tcoords.size == num_verts:
            var_dsg_id = self.cmd.color_variableid
            var_cmd = self.session.variables[var_dsg_id]
            if len(var_cmd.levels) == 0:
                self.session.log(
                    f"Note: Node rep not created for part '{self.cmd.name}'.  It has var values, but a palette with 0 levels."
                )
                return None, None, None, None, None

            p_min = None
            p_max = None
            for lvl in var_cmd.levels:
                if (p_min is None) or (p_min > lvl.value):
                    p_min = lvl.value
                if (p_max is None) or (p_max < lvl.value):
                    p_max = lvl.value

            num_texels = int(len(var_cmd.texture) / 4)

            colors = numpy.ndarray((num_verts * 3,), dtype="float32")
            low_color = [c / 255.0 for c in var_cmd.texture[0:3]]
            high_color = [
                c / 255.0 for c in var_cmd.texture[4 * (num_texels - 1) : 4 * (num_texels - 1) + 3]
            ]
            if p_min == p_max:
                # Special case where palette min == palette max
                mid_color = var_cmd[4 * (num_texels // 2) : 4 * (num_texels // 2) + 3]
                for idx in range(num_verts):
                    val = self.tcoords[idx]
                    if val == p_min:
                        colors[idx * 3 : idx * 3 + 3] = mid_color
                    elif val < p_min:
                        colors[idx * 3 : idx * 3 + 3] = low_color
                    elif val > p_min:
                        colors[idx * 3 : idx * 3 + 3] = high_color
            else:
                for idx in range(num_verts):
                    val = self.tcoords[idx]
                    if val <= p_min:
                        colors[idx * 3 : idx * 3 + 3] = low_color
                    else:
                        pal_pos = (num_texels - 1) * (val - p_min) / (p_max - p_min)
                        pal_idx, pal_sub = divmod(pal_pos, 1)
                        pal_idx = int(pal_idx)

                        if pal_idx >= num_texels - 1:
                            colors[idx * 3 : idx * 3 + 3] = high_color
                        else:
                            col0 = var_cmd.texture[pal_idx * 4 : pal_idx * 4 + 3]
                            col1 = var_cmd.texture[4 + pal_idx * 4 : 4 + pal_idx * 4 + 3]
                            for ii in range(0, 3):
                                colors[idx * 3 + ii] = (
                                    col0[ii] * pal_sub + col1[ii] * (1.0 - pal_sub)
                                ) / 255.0
            self.session.log(f"Part '{self.cmd.name}' defined: {self.coords.size/3} points.")

        node_sizes = None
        if self.node_sizes.size and self.node_sizes.size == num_verts:
            # Pass out the node sizes if there is a size-by variable
            node_size_default = self.cmd.node_size_default * norm_scale
            node_sizes = numpy.ndarray((num_verts,), dtype="float32")
            for ii in range(0, num_verts):
                node_sizes[ii] = self.node_sizes[ii] * node_size_default
        elif norm_scale != 1.0:
            # Pass out the node sizes if the model is normalized to fit in a unit cube
            node_size_default = self.cmd.node_size_default * norm_scale
            node_sizes = numpy.ndarray((num_verts,), dtype="float32")
            for ii in range(0, num_verts):
                node_sizes[ii] = node_size_default

        self.session.log(f"Part '{self.cmd.name}' defined: {self.coords.size/3} points.")
        command = self.cmd

        return command, verts, node_sizes, colors, var_cmd


class UpdateHandler(object):
    """
    This class serves as the interface between a DSGSession and a hosting application.
    The DSGSession processes the general aspects of the gRPC pipeline and collects the
    various DSG objects into collections of: groups, variables, etc.  It also coalesces
    the individual array updates into a "Part" object which represents a single addressable
    mesh chunk.
    UpdateHandler methods are called as the various update happen, and it is called when
    a mesh chunk has been entirely defined.  In most scenarios, a subclass of UpdateHandler
    is passed to the DSGSession to handshake the mesh data to the application target.
    """

    def __init__(self) -> None:
        self._session: "DSGSession"

    @property
    def session(self) -> "DSGSession":
        """The session object this handler has been associated with"""
        return self._session

    @session.setter
    def session(self, session: "DSGSession") -> None:
        self._session = session

    def add_group(self, id: int, view: bool = False) -> None:
        """Called when a new group command has been added: self.session.groups[id]"""
        if view:
            self.session.log(f"Adding view: {self.session.groups[id]}")
        else:
            self.session.log(f"Adding group: {self.session.groups[id].name}")

    def add_variable(self, id: int) -> None:
        """Called when a new group command has been added: self.session.variables[id]"""
        self.session.log(f"Adding variable: {self.session.variables[id].name}")

    def finalize_part(self, part: Part) -> None:
        """Called when all the updates on a Part object have been completed.

        Note: this superclass method should be called after the subclass has processed
        the part geometry as the saved part command will be destroyed by this call.
        """
        if part.cmd:
            self.session.log(f"Part finalized: {part.cmd.name}")
        part.cmd = None

    def start_connection(self) -> None:
        """A new gRPC connection has been established:  self.session.grpc"""
        grpc = self.session.grpc
        self.session.log(f"gRPC connection established to: {grpc.host}:{grpc.port}")

    def end_connection(self) -> None:
        """The previous gRPC connection has been closed"""
        self.session.log("gRPC connection closed")

    def begin_update(self) -> None:
        """A new scene update is about to begin"""
        self.session.log("Begin update ------------------------")

    def end_update(self) -> None:
        """The scene update is complete"""
        self.session.log("End update ------------------------")

    def get_dsg_cmd_attribute(self, obj: Any, name: str, default: Any = None) -> Optional[str]:
        """Utility function to get an attribute from a DSG update object

        Note: UpdateVariable and UpdateGroup commands support generic attributes
        """
        return obj.attributes.get(name, default)

    def group_matrix(self, group: Any) -> Any:
        matrix = group.matrix4x4
        # The Case matrix is basically the camera transform.  In vrmode, we only want
        # the raw geometry, so use the identity matrix.
        if (
            self.get_dsg_cmd_attribute(group, "ENS_OBJ_TYPE") == "ENS_CASE"
        ) and self.session.vrmode:
            matrix = [
                1.0,
                0.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.0,
                0.0,
                0.0,
                1.0,
            ]
        return matrix


class DSGSession(object):
    def __init__(
        self,
        port: int = 12345,
        host: str = "127.0.0.1",
        security_code: str = "",
        verbose: int = 0,
        normalize_geometry: bool = False,
        vrmode: bool = False,
        time_scale: float = 1.0,
        handler: UpdateHandler = UpdateHandler(),
    ):
        """
        Manage a gRPC connection and link it to an UpdateHandler instance

        This class makes a DSG gRPC connection via the specified port and host (leveraging
        the passed security code).  As DSG protobuffers arrive, they are merged into Part
        object instances and the UpdateHandler is invoked to further process them.

        Parameters
        ----------
        port : int
            The port number the EnSight gRPC service is running on.
            The default is ``12345``.
        host : str
            Name of the host that the EnSight gRPC service is running on.
            The default is ``"127.0.0.1"``, which is the localhost.
        security_code : str
            Shared security code for validating the gRPC communication.
            The default is ``""``.
        verbose : int
            The verbosity level.  If set to 1 or higher the class will call logging.info
            for log output.  The default is ``0``.
        normalize_geometry : bool
            If True, the scene coordinates will be remapped into the volume [-1,-1,-1] - [1,1,1]
            The default is not to remap coordinates.
        vrmode : bool
            If True, do not include the EnSight camera in the generated view group. The default
            is to include the EnSight view in the scene transformations.
        time_scale : float
            All DSG protobuffers time values will be multiplied by this factor after
            being received.  The default is ``1.0``.
        handler : UpdateHandler
            This is an UpdateHandler subclass that is called back when the state of
            a scene transfer changes.  For example, methods are called when the
            transfer begins or ends and when a Part (mesh block) is ready for processing.
        """
        super().__init__()
        self._grpc = ensight_grpc.EnSightGRPC(port=port, host=host, secret_key=security_code)
        self._callback_handler = handler
        self._verbose = verbose
        self._thread: Optional[threading.Thread] = None
        self._message_queue: queue.Queue = queue.Queue()  # Messages coming from EnSight
        self._dsg_queue: Optional[queue.SimpleQueue] = None  # Outgoing messages to EnSight
        self._shutdown = False
        self._dsg = None
        self._normalize_geometry = normalize_geometry
        self._vrmode = vrmode
        self._time_scale = time_scale
        self._time_limits = [
            sys.float_info.max,
            -sys.float_info.max,
        ]  # Min/max across all time steps
        self._mesh_block_count = 0
        self._variables: Dict[int, Any] = dict()
        self._groups: Dict[int, Any] = dict()
        self._part: Part = Part(self)
        self._scene_bounds: Optional[List] = None
        self._cur_timeline: List = [0.0, 0.0]  # Start/End time for current update
        self._callback_handler.session = self
        # log any status changes to this file.  external apps will be monitoring
        self._status_file = os.environ.get("ANSYS_OV_SERVER_STATUS_FILENAME", "")
        self._status = dict(status="idle", start_time=0.0, processed_buffers=0, total_buffers=0)

    @property
    def scene_bounds(self) -> Optional[List]:
        return self._scene_bounds

    @property
    def mesh_block_count(self) -> int:
        return self._mesh_block_count

    @property
    def vrmode(self) -> bool:
        return self._vrmode

    @vrmode.setter
    def vrmode(self, value: bool) -> None:
        self._vrmode = value

    @property
    def normalize_geometry(self) -> bool:
        return self._normalize_geometry

    @normalize_geometry.setter
    def normalize_geometry(self, value: bool) -> None:
        self._normalize_geometry = value

    @property
    def variables(self) -> dict:
        return self._variables

    @property
    def groups(self) -> dict:
        return self._groups

    @property
    def part(self) -> Part:
        return self._part

    @property
    def time_limits(self) -> List:
        return self._time_limits

    @property
    def cur_timeline(self) -> List:
        return self._cur_timeline

    @cur_timeline.setter
    def cur_timeline(self, timeline: List) -> None:
        self._cur_timeline = timeline
        self._time_limits[0] = min(self._time_limits[0], self._cur_timeline[0])
        self._time_limits[1] = max(self._time_limits[1], self._cur_timeline[1])

    @property
    def grpc(self) -> ensight_grpc.EnSightGRPC:
        return self._grpc

    def log(self, s: str, level: int = 0) -> None:
        """Log a string to the logging system

        If the message level is less than the current verbosity,
        emit the message.
        """
        if level < self._verbose:
            logging.info(s)

    @staticmethod
    def warn(s: str) -> None:
        """Issue a warning to the logging system

        The logging message is mapped to "warn" and cannot be blocked via verbosity
        checks.
        """
        logging.warning(s)

    def start(self) -> int:
        """Start a gRPC connection to an EnSight instance

        Make a gRPC connection and start a DSG stream handler.

        Returns
        -------
            0 on success, -1 on an error.
        """
        # Start by setting up and verifying the connection
        self._grpc.connect()
        if not self._grpc.is_connected():
            self.log(f"Unable to establish gRPC connection to: {self._grpc.host}:{self._grpc.port}")
            return -1
        # Streaming API requires an iterator, so we make one from a queue
        # it also returns an iterator.  self._dsg_queue is the input stream interface
        # self._dsg is the returned stream iterator.
        if self._dsg is not None:
            return 0
        self._dsg_queue = queue.SimpleQueue()
        self._dsg = self._grpc.dynamic_scene_graph_stream(
            iter(self._dsg_queue.get, None)  # type:ignore
        )
        self._thread = threading.Thread(target=self._poll_messages)
        if self._thread is not None:
            self._thread.start()
        self._callback_handler.start_connection()
        return 0

    def end(self):
        """Stop a gRPC connection to the EnSight instance"""
        self._callback_handler.end_connection()
        self._grpc.shutdown()
        self._shutdown = True
        self._thread.join()
        self._grpc.shutdown()
        self._dsg = None
        self._thread = None
        self._dsg_queue = None

    def is_shutdown(self):
        """Check the service shutdown request status"""
        return self._shutdown

    def _update_status_file(self, timed: bool = False):
        """
        Update the status file contents. The status file will contain the
        following json object, stored as: self._status

        {
        'status' : "working|idle",
        'start_time' : timestamp_of_update_begin,
        'processed_buffers' : number_of_protobuffers_processed,
        'total_buffers' : number_of_protobuffers_total,
        }

        Parameters
        ----------
        timed : bool, optional:
            if True, only update every second.

        """
        if self._status_file:
            current_time = time.time()
            if timed:
                last_time = self._status.get("last_time", 0.0)
                if current_time - last_time < 1.0:  # type: ignore
                    return
            self._status["last_time"] = current_time
            try:
                message = json.dumps(self._status)
                with open(self._status_file, "w") as status_file:
                    status_file.write(message)
            except IOError:
                pass  # Note failure is expected here in some cases

    def request_an_update(self, animation: bool = False, allow_spontaneous: bool = True) -> None:
        """Start a DSG update
        Send a command to the DSG protocol to "init" an update.

        Parameters
        ----------
        animation:
            if True, export all EnSight timesteps.
        allow_spontaneous:
            if True, allow EnSight to trigger async updates.
        """
        # Send an INIT command to trigger a stream of update packets
        cmd = dynamic_scene_graph_pb2.SceneClientCommand()
        cmd.command_type = dynamic_scene_graph_pb2.SceneClientCommand.INIT
        # Allow EnSight push commands, but full scene only for now...
        cmd.init.allow_spontaneous = allow_spontaneous
        cmd.init.include_temporal_geometry = animation
        cmd.init.allow_incremental_updates = False
        cmd.init.maximum_chunk_size = 1024 * 1024
        self._dsg_queue.put(cmd)  # type:ignore

    def _poll_messages(self) -> None:
        """Core interface to grab DSG events from gRPC and queue them for processing

        This is run by a thread that is monitoring the dsg RPC call for update messages
        it places them in _message_queue as it finds them.  They are picked up by the
        main thread via get_next_message()
        """
        while not self._shutdown:
            try:
                self._message_queue.put(next(self._dsg))  # type:ignore
            except Exception:
                self._shutdown = True
                self.log("DSG connection broken, calling exit")
                os._exit(0)

    def _get_next_message(self, wait: bool = True) -> Any:
        """Get the next queued up protobuffer message

        Called by the main thread to get any messages that were pulled in from the
        dsg stream and placed here by _poll_messages()
        """
        try:
            return self._message_queue.get(block=wait)
        except queue.Empty:
            return None

    def handle_one_update(self) -> None:
        """Monitor the DSG stream and handle a single update operation

        Wait until we get the scene update begin message.  From there, reset the current
        scene buckets and then parse all the incoming commands until we get the scene
        update end command.   At which point, save the generated stage (started in the
        view command handler).  Note: Parts are handled with an available bucket at all times.
        When a new part update comes in or the scene update end happens, the part is "finished".
        """
        # An update starts with a UPDATE_SCENE_BEGIN command
        cmd = self._get_next_message()
        while (cmd is not None) and (
            cmd.command_type != dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_SCENE_BEGIN
        ):
            # Look for a begin command
            cmd = self._get_next_message()

        # Start anew
        self._variables = {}
        self._groups = {}
        self._part = Part(self)
        self._scene_bounds = None
        self._mesh_block_count = 0  # reset when a new group shows up
        self._callback_handler.begin_update()

        # Update our status
        self._status = dict(
            status="working", start_time=time.time(), processed_buffers=1, total_buffers=1
        )
        self._update_status_file()

        # handle the various commands until UPDATE_SCENE_END
        cmd = self._get_next_message()
        while (cmd is not None) and (
            cmd.command_type != dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_SCENE_END
        ):
            self._handle_update_command(cmd)
            self._status["processed_buffers"] += 1  # type: ignore
            self._status["total_buffers"] = self._status["processed_buffers"] + self._message_queue.qsize()  # type: ignore
            self._update_status_file(timed=True)
            cmd = self._get_next_message()

        # Flush the last part
        self._finish_part()

        self._callback_handler.end_update()

        # Update our status
        self._status = dict(status="idle", start_time=0.0, processed_buffers=0, total_buffers=0)
        self._update_status_file()

    def _handle_update_command(self, cmd: dynamic_scene_graph_pb2.SceneUpdateCommand) -> None:
        """Dispatch out a scene update command to the proper handler

        Given a command object, pull out the correct portion of the protobuffer union and
        pass it to the appropriate handler.

        Parameters
        ----------
        cmd:
            The command to be dispatched.
        """
        name = "Unknown"
        if cmd.command_type == dynamic_scene_graph_pb2.SceneUpdateCommand.DELETE_ID:
            name = "Delete IDs"
        elif cmd.command_type == dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_PART:
            name = "Part update"
            tmp = cmd.update_part
            self._handle_part(tmp)
        elif cmd.command_type == dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_GROUP:
            name = "Group update"
            tmp = cmd.update_group
            self._handle_group(tmp)
        elif cmd.command_type == dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_GEOM:
            name = "Geom update"
            tmp = cmd.update_geom
            self._part.update_geom(tmp)
        elif cmd.command_type == dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_VARIABLE:
            name = "Variable update"
            tmp = cmd.update_variable
            self._handle_variable(tmp)
        elif cmd.command_type == dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_VIEW:
            name = "View update"
            tmp = cmd.update_view
            self._handle_view(tmp)
        elif cmd.command_type == dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_TEXTURE:
            name = "Texture update"
        self.log(f"{name} --------------------------")

    def _finish_part(self) -> None:
        """Complete the current part

        There is always a part being modified.  This method completes the current part, committing
        it to the handler.
        """
        try:
            self._callback_handler.finalize_part(self.part)
        except Exception as e:
            self.warn(f"Error encountered while finalizing part geometry: {str(e)}")
        self._mesh_block_count += 1

    def _handle_part(self, part_cmd: Any) -> None:
        """Handle a DSG UPDATE_PART command

        Finish the current part and set up the next part.

        Parameters
        ----------
        part:
            The command coming from the EnSight stream.
        """
        self._finish_part()
        self._part.reset(part_cmd)

    def _handle_group(self, group: Any) -> None:
        """Handle a DSG UPDATE_GROUP command

        Parameters
        ----------
        group:
            The command coming from the EnSight stream.
        """
        # reset current mesh (part) count for unique "part" naming in USD
        self._mesh_block_count = 0

        # record the scene bounds in case they are needed later
        self._groups[group.id] = group
        bounds = group.attributes.get("ENS_SCENE_BOUNDS", None)
        if bounds:
            minmax = list()
            for v in bounds.split(","):
                try:
                    minmax.append(float(v))
                except ValueError:
                    pass
            if len(minmax) == 6:
                self._scene_bounds = minmax
        # callback
        self._callback_handler.add_group(group.id)

    def _handle_variable(self, var: Any) -> None:
        """Handle a DSG UPDATE_VARIABLE command

        Save off the EnSight variable DSG command object.

        Parameters
        ----------
        var:
            The command coming from the EnSight stream.
        """
        self._variables[var.id] = var
        self._callback_handler.add_variable(var.id)

    def _handle_view(self, view: Any) -> None:
        """Handle a DSG UPDATE_VIEW command

        Parameters
        ----------
        view:
            The command coming from the EnSight stream.
        """
        self._finish_part()
        self._scene_bounds = None
        self._groups[view.id] = view
        if len(view.timeline) == 2:
            view.timeline[0] *= self._time_scale
            view.timeline[1] *= self._time_scale
            self.cur_timeline = [view.timeline[0], view.timeline[1]]
        self._callback_handler.add_group(view.id, view=True)
