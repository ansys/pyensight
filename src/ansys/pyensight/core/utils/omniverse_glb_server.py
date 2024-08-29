import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

from ansys.api.pyensight.v0 import dynamic_scene_graph_pb2
import pygltflib

sys.path.insert(0, os.path.dirname(__file__))
from dsg_server import Part, UpdateHandler  # noqa: E402


class GLBSession(object):
    def __init__(
        self,
        verbose: int = 0,
        normalize_geometry: bool = False,
        time_scale: float = 1.0,
        handler: UpdateHandler = UpdateHandler(),
    ):
        """
        Provide an interface to read a GLB file and link it to an UpdateHandler instance

        This class reads GLB files and provides the data to an UpdateHandler instance for
        further processing.

        Parameters
        ----------
        verbose : int
            The verbosity level.  If set to 1 or higher the class will call logging.info
            for log output.  The default is ``0``.
        normalize_geometry : bool
            If True, the scene coordinates will be remapped into the volume [-1,-1,-1] - [1,1,1]
            The default is not to remap coordinates.
        time_scale : float
            Scale time values by this factor after being read.  The default is ``1.0``.
        handler : UpdateHandler
            This is an UpdateHandler subclass that is called back when the state of
            a scene transfer changes.  For example, methods are called when the
            transfer begins or ends and when a Part (mesh block) is ready for processing.
        """
        super().__init__()
        self._callback_handler = handler
        self._verbose = verbose
        self._normalize_geometry = normalize_geometry
        self._time_scale = time_scale
        self._time_limits = [
            sys.float_info.max,
            -sys.float_info.max,
        ]  # Min/max across all time steps
        self._mesh_block_count = 0
        self._node_idx: int = -1
        self._variables: Dict[int, Any] = dict()
        self._groups: Dict[int, Any] = dict()
        self._part: Part = Part(self)
        self._scene_bounds: Optional[List] = None
        self._cur_timeline: List = [0.0, 0.0]  # Start/End time for current update
        self._callback_handler.session = self
        # log any status changes to this file.  external apps will be monitoring
        self._status_file = os.environ.get("ANSYS_OV_SERVER_STATUS_FILENAME", "")
        self._status = dict(status="idle", start_time=0.0, processed_buffers=0, total_buffers=0)
        self._gltf: pygltflib.GLTF2 = pygltflib.GLTF2()
        self._id_num: int = 0

    def _reset(self):
        self._variables = dict()
        self._groups = dict()
        self._part = Part(self)
        self._scene_bounds = None
        self._cur_timeline = [0.0, 0.0]  # Start/End time for current update
        self._status = dict(status="idle", start_time=0.0, processed_buffers=0, total_buffers=0)
        self._gltf = pygltflib.GLTF2()
        self._node_idx = -1
        self._mesh_block_count = 0
        self._id_num = 0

    def _next_id(self) -> int:
        self._id_num += 1
        return self._id_num

    @property
    def scene_bounds(self) -> Optional[List]:
        return self._scene_bounds

    @property
    def mesh_block_count(self) -> int:
        return self._mesh_block_count

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
    def vrmode(self) -> bool:
        """No camera support for the present."""
        return True

    def log(self, s: str, level: int = 0) -> None:
        """Log a string to the logging system

        If the message level is less than the current verbosity,
        emit the message.
        """
        if level < self._verbose:
            logging.info(s)

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

    def _parse_mesh(self, meshid: Any) -> None:
        mesh = self._gltf.meshes[meshid]
        logging.warning(f"mesh id: {meshid}, {mesh}")
        for prim in mesh.primitives:
            # TODO: GLB Prim -> DSG Part
            self.log(f"prim {prim}")
            # TODO: GLB Attributes -> DSG Geom

        # mesh.mode, mesh.indices
        # mesh.attributes(POSITION, NORMAL, COLOR_0, TEXCOORD_0, TEXCOORD_1)
        # mesh.material
        # mesh.images

    def _walk_node(self, nodeid: Any) -> None:
        node = self._gltf.nodes[nodeid]
        self.log(f"node id: {nodeid}, {node}")
        # TODO: GLB node -> DSG Group

        if node.mesh is not None:
            self._parse_mesh(node.mesh)

        # Handle node.rotation, node.translation, node.scale, node.matrix
        for child_id in node.children:
            self._walk_node(child_id)

    def upload_file(self, glb_filename: str) -> bool:
        """Parse a GLB file and call out to the handler to present the data
        to another interface (e.g. Omniverse)

        Parameters
        ----------
        glb_filename : str
            The name of the GLB file to parse

        Returns
        -------
            bool:
                returns True on success, False otherwise
        """
        try:
            ok = True
            self._gltf = pygltflib.GLTF2().load(glb_filename)
            self.log(f"File: {glb_filename}  Info: {self._gltf.asset}")

            self._callback_handler.begin_update()
            self._update_status_file()

            # TODO: Variables, Textures

            # TODO: GLB Scene -> DSG View

            # for present, just the default scene
            for node_id in self._gltf.scenes[self._gltf.scene].nodes:
                self._walk_node(node_id)

            self._finish_part()
            self._callback_handler.end_update()

        except Exception as e:
            self.log(f"Error: Unable to process: {glb_filename} : {e}")
            ok = False

        self._reset()
        self._update_status_file()
        return ok

    def _finish_part(self) -> None:
        """Complete the current part

        There is always a part being modified.  This method completes the current part, committing
        it to the handler.
        """
        self._callback_handler.finalize_part(self.part)
        self._mesh_block_count += 1

    def _name(self, node: Any) -> str:
        if node.name:
            return node.name
        self._node_idx += 1
        if self._node_idx == 0:
            return "Root"
        return f"Node_{self._node_idx}"

    def _create_pb(
        self, cmd_type: str, parent_id: int = -1, name: str = ""
    ) -> "dynamic_scene_graph_pb2.SceneUpdateCommand":
        cmd = dynamic_scene_graph_pb2.SceneUpdateCommand()
        if cmd_type == "PART":
            cmd.command_type = dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_PART
            subcmd = cmd.update_part
        elif cmd_type == "GROUP":
            cmd.command_type = dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_GROUP
            subcmd = cmd.update_group
        elif cmd_type == "VARIABLE":
            cmd.command_type = dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_VARIABLE
            subcmd = cmd.update_variable
        elif cmd_type == "GEOM":
            cmd.command_type = dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_GEOM
            subcmd = cmd.update_geom
        elif cmd_type == "VIEW":
            cmd.command_type = dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_VIEW
            subcmd = cmd.update_view
        subcmd.id = self._next_id()
        if parent_id >= 0:
            subcmd.parent_id = parent_id
        if cmd_type not in ("GEOM", "VIEW"):
            if name:
                subcmd.name = name
        return cmd, subcmd
