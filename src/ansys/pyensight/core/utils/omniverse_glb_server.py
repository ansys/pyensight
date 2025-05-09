import io
import json
import logging
import os
import sys
from typing import Any, List, Optional
import uuid

from PIL import Image
from ansys.api.pyensight.v0 import dynamic_scene_graph_pb2
import ansys.pyensight.core.utils.dsg_server as dsg_server
import numpy
import pygltflib

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(__file__))
original_stdout = sys.stdout
original_stderr = sys.stderr
sys.stderr = open(os.devnull, "w")
sys.stdout = open(os.devnull, "w")
try:
    from dsg_server import UpdateHandler  # noqa: E402
except AttributeError as exc:
    if "_ARRAY_API" not in str(exc):
        raise exc
finally:
    sys.stderr = original_stderr
    sys.stdout = original_stdout


class GLBSession(dsg_server.DSGSession):
    def __init__(
        self,
        verbose: int = 0,
        normalize_geometry: bool = False,
        time_scale: float = 1.0,
        vrmode: bool = False,
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
        vrmode : bool
            If True, do not include the camera in the output.
        handler : UpdateHandler
            This is an UpdateHandler subclass that is called back when the state of
            a scene transfer changes.  For example, methods are called when the
            transfer begins or ends and when a Part (mesh block) is ready for processing.
        """
        super().__init__(
            verbose=verbose,
            normalize_geometry=normalize_geometry,
            time_scale=time_scale,
            vrmode=vrmode,
            handler=handler,
        )
        self._gltf: pygltflib.GLTF2 = pygltflib.GLTF2()
        self._id_num: int = 0
        self._node_idx: int = -1
        self._glb_textures: dict = {}
        self._scene_id: int = 0

    def _reset(self) -> None:
        """
        Reset the current state to prepare for a new dataset.
        """
        super()._reset()
        self._cur_timeline = [0.0, 0.0]  # Start/End time for current update
        self._status = dict(status="idle", start_time=0.0, processed_buffers=0, total_buffers=0)
        self._gltf = pygltflib.GLTF2()
        self._node_idx = -1
        self._id_num = 0
        self._glb_textures = {}
        self._scene_id = 0

    def _next_id(self) -> int:
        """Simple sequential number source
        Called whenever a unique integer is needed.

        Returns
        -------
        int
            A unique, monotonically increasing integer.
        """
        self._id_num += 1
        return self._id_num

    def _map_material(self, glb_materialid: int, part_pb: Any) -> None:
        """
        Apply various material properties to part protocol buffer.

        Parameters
        ----------
        glb_materialid : int
            The GLB material ID to use as the source information.
        part_pb : Any
            The DSG UpdatePart protocol buffer to update.
        """
        mat = self._gltf.materials[glb_materialid]
        color = [1.0, 1.0, 1.0, 1.0]
        # Change the color if we can find one
        if hasattr(mat, "pbrMetallicRoughness"):
            if hasattr(mat.pbrMetallicRoughness, "baseColorFactor"):
                color = mat.pbrMetallicRoughness.baseColorFactor
        part_pb.fill_color.extend(color)
        part_pb.line_color.extend(color)
        # Constants for now
        part_pb.ambient = 1.0
        part_pb.diffuse = 1.0
        part_pb.specular_intensity = 1.0
        if "ANSYS_material_details" in mat.extensions:
            part_pb.material_name = json.dumps(mat.extensions["ANSYS_material_details"])
        # if the material maps to a variable, set the variable id for coloring
        glb_varid = self._find_variable_from_glb_mat(glb_materialid)
        if glb_varid:
            part_pb.color_variableid = glb_varid

    def _parse_mesh(self, meshid: int, parentid: int, parentname: str) -> None:
        """
        Walk a mesh id found in a "node" instance.  This amounts to
        walking the list of "primitives" in the "meshes" list indexed
        by the meshid.

        Parameters
        ----------
        meshid: int
            The index of the mesh in the "meshes" list.

        parentid: int
            The DSG parent id.

        parentname: str
            The name of the GROUP parent of the meshes.
        """
        mesh = self._gltf.meshes[meshid]
        for prim_idx, prim in enumerate(mesh.primitives):
            # POINTS, LINES, TRIANGLES, LINE_LOOP, LINE_STRIP, TRIANGLE_STRIP, TRIANGLE_FAN
            mode = prim.mode
            if mode not in (
                pygltflib.TRIANGLES,
                pygltflib.LINES,
                pygltflib.POINTS,
                pygltflib.LINE_LOOP,
                pygltflib.LINE_STRIP,
                pygltflib.TRIANGLE_STRIP,
                pygltflib.TRIANGLE_FAN,
            ):
                self.warn(f"Unhandled connectivity detected: {mode}.  Geometry skipped.")
                continue
            glb_materialid = prim.material
            line_width = self._callback_handler._omni.line_width

            # GLB Prim -> DSG Part
            part_name = f"{parentname}_prim{prim_idx}_"
            cmd, part_pb = self._create_pb("PART", parent_id=parentid, name=part_name)
            if mode == pygltflib.POINTS:
                part_pb.render = dynamic_scene_graph_pb2.UpdatePart.RenderingMode.NODES
                # Size of the spheres
                part_pb.node_size_default = line_width
            else:
                part_pb.render = dynamic_scene_graph_pb2.UpdatePart.RenderingMode.CONNECTIVITY
            part_pb.shading = dynamic_scene_graph_pb2.UpdatePart.ShadingMode.NODAL
            self._map_material(glb_materialid, part_pb)
            part_dsg_id = part_pb.id
            self._handle_update_command(cmd)

            # GLB Attributes -> DSG Geom
            # Verts
            num_verts = 0
            if prim.attributes.POSITION is not None:
                verts = self._get_data(prim.attributes.POSITION)
                num_verts = len(verts) // 3
                cmd, verts_pb = self._create_pb("GEOM", parent_id=part_dsg_id)
                verts_pb.payload_type = dynamic_scene_graph_pb2.UpdateGeom.ArrayType.COORDINATES
                verts_pb.flt_array.extend(verts)
                verts_pb.chunk_offset = 0
                verts_pb.total_array_size = len(verts)
                self._handle_update_command(cmd)

            # Connectivity
            if num_verts and (mode != pygltflib.POINTS):
                if prim.indices is not None:
                    conn = self._get_data(prim.indices, 0)
                else:
                    conn = numpy.array(list(range(num_verts)), dtype=numpy.uint32)
                cmd, conn_pb = self._create_pb("GEOM", parent_id=part_dsg_id)
                if mode == pygltflib.TRIANGLES:
                    conn_pb.payload_type = dynamic_scene_graph_pb2.UpdateGeom.ArrayType.TRIANGLES
                elif mode == pygltflib.TRIANGLE_STRIP:
                    conn_pb.payload_type = dynamic_scene_graph_pb2.UpdateGeom.ArrayType.TRIANGLES
                    conn = self._tri_strip_to_tris(conn)
                elif mode == pygltflib.TRIANGLE_FAN:
                    conn_pb.payload_type = dynamic_scene_graph_pb2.UpdateGeom.ArrayType.TRIANGLES
                    conn = self._tri_fan_to_tris(conn)
                elif mode == pygltflib.LINES:
                    conn_pb.payload_type = dynamic_scene_graph_pb2.UpdateGeom.ArrayType.LINES
                elif mode == pygltflib.LINE_LOOP:
                    conn_pb.payload_type = dynamic_scene_graph_pb2.UpdateGeom.ArrayType.LINES
                    conn = self._line_loop_to_lines(conn)
                elif mode == pygltflib.LINE_STRIP:
                    conn_pb.payload_type = dynamic_scene_graph_pb2.UpdateGeom.ArrayType.LINES
                    conn = self._line_strip_to_lines(conn)
                conn_pb.int_array.extend(conn)
                conn_pb.chunk_offset = 0
                conn_pb.total_array_size = len(conn)
                self._handle_update_command(cmd)

            # Normals
            if prim.attributes.NORMAL is not None:
                normals = self._get_data(prim.attributes.NORMAL)
                cmd, normals_pb = self._create_pb("GEOM", parent_id=part_dsg_id)
                normals_pb.payload_type = dynamic_scene_graph_pb2.UpdateGeom.ArrayType.NODE_NORMALS
                normals_pb.flt_array.extend(normals)
                normals_pb.chunk_offset = 0
                normals_pb.total_array_size = len(normals)
                self._handle_update_command(cmd)

            # Texture coords
            if prim.attributes.TEXCOORD_0 is not None:
                # Note: texture coords are stored as VEC2, so we get 2 components back
                texcoords = self._get_data(prim.attributes.TEXCOORD_0, components=2)
                # we only want the 's' component of an s,t pairing
                texcoords = texcoords[::2]
                cmd, texcoords_pb = self._create_pb("GEOM", parent_id=part_dsg_id)
                texcoords_pb.payload_type = (
                    dynamic_scene_graph_pb2.UpdateGeom.ArrayType.NODE_VARIABLE
                )
                texcoords_pb.flt_array.extend(texcoords)
                texcoords_pb.chunk_offset = 0
                texcoords_pb.total_array_size = len(texcoords)
                glb_varid = self._find_variable_from_glb_mat(glb_materialid)
                if glb_varid:
                    texcoords_pb.variable_id = glb_varid
                self._handle_update_command(cmd)

    @staticmethod
    def _tri_strip_to_tris(conn: numpy.ndarray) -> numpy.ndarray:
        """
        Convert GL_TRIANGLE_STRIP connectivity into GL_TRIANGLES

        Parameters
        ----------
        conn: numpy.ndarray
            The tri strip connectivity

        Returns
        -------
        numpy.array:
            Triangles connectivity
        """
        tris = []
        swap = False
        for i in range(len(conn) - 2):
            tris.append(conn[i])
            if swap:
                tris.append(conn[i + 2])
                tris.append(conn[i + 1])
            else:
                tris.append(conn[i + 1])
                tris.append(conn[i + 2])
            swap = not swap
        return numpy.array(tris, dtype=conn.dtype)

    @staticmethod
    def _tri_fan_to_tris(conn: numpy.ndarray) -> numpy.ndarray:
        """
        Convert GL_TRIANGLE_FAN connectivity into GL_TRIANGLES

        Parameters
        ----------
        conn: numpy.ndarray
            The fan connectivity

        Returns
        -------
        numpy.array:
            Triangles connectivity
        """
        tris = []
        for i in range(1, len(conn) - 1):
            tris.append(conn[0])
            tris.append(conn[i])
            tris.append(conn[i + 1])
        return numpy.array(tris, dtype=conn.dtype)

    @staticmethod
    def _line_strip_to_lines(conn) -> numpy.ndarray:
        """
        Convert GL_LINE_STRIP connectivity into GL_LINES

        Parameters
        ----------
        conn: numpy.ndarray
           The line strip connectivity

        Returns
        -------
        numpy.array:
           Lines connectivity
        """
        lines = []
        num_nodes = len(conn)
        for i in range(num_nodes - 1):
            lines.append(conn[i])
            lines.append(conn[i + 1])
        return numpy.array(lines, dtype=conn.dtype)

    @staticmethod
    def _line_loop_to_lines(conn) -> numpy.ndarray:
        """
        Convert GL_LINE_LOOP connectivity into GL_LINES

        Parameters
        ----------
        conn: numpy.ndarray
           The line loop connectivity

        Returns
        -------
        numpy.array:
           Lines connectivity
        """
        lines = []
        num_nodes = len(conn)
        for i in range(num_nodes):
            lines.append(conn[i])
            if i + 1 == num_nodes:
                lines.append(conn[0])
            else:
                lines.append(conn[i + 1])
        return numpy.array(lines, dtype=conn.dtype)

    def _get_data(
        self,
        accessorid: int,
        components: int = 3,
    ) -> numpy.ndarray:
        """
        Return the float buffer corresponding to the given accessorid.   The id
        is usually obtained from a primitive:  primitive.attributes.POSITION
        or primitive.attributes.NORMAL or primitive.attributes.TEXCOORD_0.
        It can also come from primitive.indices.  In that case, the number of
        components needs to be set to 0.

        Parameters
        ----------
        accessorid: int
            The accessor index of the primitive.

        components: int
            The number of floats per vertex for the values 1,2,3 if the number
            of components is 0, read integer indices.

        Returns
        -------
        numpy.ndarray
            The float buffer corresponding to the nodal data or an int buffer of connectivity.
        """
        dtypes = {}
        dtypes[pygltflib.BYTE] = numpy.int8
        dtypes[pygltflib.UNSIGNED_BYTE] = numpy.uint8
        dtypes[pygltflib.SHORT] = numpy.int16
        dtypes[pygltflib.UNSIGNED_SHORT] = numpy.uint16
        dtypes[pygltflib.UNSIGNED_INT] = numpy.uint32
        dtypes[pygltflib.FLOAT] = numpy.float32

        binary_blob = self._gltf.binary_blob()
        accessor = self._gltf.accessors[accessorid]
        buffer_view = self._gltf.bufferViews[accessor.bufferView]
        dtype = numpy.float32
        data_dtype = dtypes[accessor.componentType]
        count = accessor.count * components
        # connectivity
        if components == 0:
            dtype = numpy.uint32
            count = accessor.count
        offset = buffer_view.byteOffset + accessor.byteOffset
        blob = binary_blob[offset : offset + buffer_view.byteLength]
        ret = numpy.frombuffer(blob, dtype=data_dtype, count=count)
        if data_dtype != dtype:
            return ret.astype(dtype)
        return ret

    def _walk_node(self, nodeid: int, parentid: int) -> None:
        """
        Given a node id (likely from walking a scenes array), walk the mesh
        objects in the node.  A "node" has the keys "mesh" and "name".

        Each node has a single mesh object in it.

        Parameters
        ----------
        nodeid: int
            The node id to walk.

        parentid: int
            The DSG parent id.

        """
        node = self._gltf.nodes[nodeid]
        name = self._name(node)
        matrix = self._transform(node)

        # GLB node -> DSG Group
        cmd, group_pb = self._create_pb("GROUP", parent_id=parentid, name=name)
        group_pb.matrix4x4.extend(matrix)
        if node.mesh is not None:
            # This is a little ugly, but spheres have a size that is part of the PART
            # protobuffer.  So, if the current mesh has the "ANSYS_linewidth" extension,
            # we need to temporally change the line width.  However, if this is a lines
            # object, then we need to set the ANSYS_linewidth attribute.  Unfortunately,
            # this is only available on the GROUP protobuffer, thus we will try to set
            # both here.
            # Note: in the EnSight push, ANSYS_linewidth will only ever be set on the
            # top level node. In the GLB case, we will scope it to the group.  Thus,
            # every "mesh" protobuffer sequence will have an explicit line width in
            # the group above the part.

            # save/restore the current line_width
            orig_width = self._callback_handler._omni.line_width
            mesh = self._gltf.meshes[node.mesh]
            try:
                # check for line_width on the mesh object
                width = float(mesh.extensions["ANSYS_linewidth"]["linewidth"])
                # make sure spheres work
                self._callback_handler._omni.line_width = width
            except (KeyError, ValueError):
                pass
            # make sure lines work (via the group attributes map)
            group_pb.attributes["ANSYS_linewidth"] = str(self._callback_handler._omni.line_width)
            # send the group protobuffer
            self._handle_update_command(cmd)
            # Export the mesh
            self._parse_mesh(node.mesh, group_pb.id, name)
            # restore the old line_width
            self._callback_handler._omni.line_width = orig_width
        else:
            # send the group protobuffer
            self._handle_update_command(cmd)

        # Handle node.rotation, node.translation, node.scale, node.matrix
        for child_id in node.children:
            self._walk_node(child_id, group_pb.id)

    def start_uploads(self, timeline: List[float]) -> None:
        """
        Begin an upload process for a potential collection of files.

        Parameters
        ----------
        timeline : List[float]
            The time values for the files span this range of values.
        """
        self._scene_id = self._next_id()
        self._cur_timeline = timeline
        self._callback_handler.begin_update()
        self._update_status_file()

    def end_uploads(self) -> None:
        """
        The upload process for the current collection of files is complete.
        """
        self._reset()
        self._update_status_file()

    def _find_variable_from_glb_mat(self, glb_material_id: int) -> Optional[int]:
        """
        Given a glb_material id, find the corresponding dsg variable id

        Parameters
        ----------
        glb_material_id : int
            The material id from the glb file.

        Returns
        -------
        Optional[int]
            The dsg variable id or None, if no variable is found.
        """
        value = self._glb_textures.get(glb_material_id, None)
        if value is not None:
            return value["pb"].id
        return None

    def upload_file(self, glb_filename: str, timeline: List[float] = [0.0, 0.0]) -> bool:
        """
        Parse a GLB file and call out to the handler to present the data
        to another interface (e.g. Omniverse)

        Parameters
        ----------
        timeline : List[float]
            The first and last time value for which the content of this file should be
            visible.

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

            # check for GLTFWriter source
            if (self._gltf.asset.generator is None) or (
                ("GLTF Writer" not in self._gltf.asset.generator)
                and ("Ansys Ensight" not in self._gltf.asset.generator)
            ):
                self.error(
                    f"Unable to process: {glb_filename} : Not written by GLTF Writer library"
                )
                return False

            # Walk texture nodes -> DSG Variable buffers
            for tex_idx, texture in enumerate(self._gltf.textures):
                image = self._gltf.images[texture.source]
                if image.uri is None:
                    bv = self._gltf.bufferViews[image.bufferView]
                    raw_png = self._gltf.binary_blob()[
                        bv.byteOffset : bv.byteOffset + bv.byteLength
                    ]
                else:
                    raw_png = self._gltf.get_data_from_buffer_uri(image.uri)
                png_img = Image.open(io.BytesIO(raw_png))
                raw_rgba = png_img.tobytes()
                raw_rgba = raw_rgba[0 : len(raw_rgba) // png_img.size[1]]
                var_name = "Variable_" + str(tex_idx)
                cmd, var_pb = self._create_pb("VARIABLE", parent_id=self._scene_id, name=var_name)
                var_pb.location = dynamic_scene_graph_pb2.UpdateVariable.VarLocation.NODAL
                var_pb.dimension = dynamic_scene_graph_pb2.UpdateVariable.VarDimension.SCALAR
                var_pb.undefined_value = -1e38
                var_pb.pal_interp = (
                    dynamic_scene_graph_pb2.UpdateVariable.PaletteInterpolation.CONTINUOUS
                )
                var_pb.sub_levels = 0
                var_pb.undefined_display = (
                    dynamic_scene_graph_pb2.UpdateVariable.UndefinedDisplay.AS_ZERO
                )
                var_pb.texture = raw_rgba
                colors = numpy.frombuffer(raw_rgba, dtype=numpy.uint8)
                colors.shape = (-1, 4)
                num = len(colors)
                levels = []
                for i, c in enumerate(colors):
                    level = dynamic_scene_graph_pb2.VariableLevel()
                    level.value = float(i) / float(num - 1)
                    level.red = float(c[0]) / 255.0
                    level.green = float(c[1]) / 255.0
                    level.blue = float(c[2]) / 255.0
                    level.alpha = float(c[3]) / 255.0
                    levels.append(level)
                var_pb.levels.extend(levels)
                # create a map from GLB material index to glb
                d = dict(pb=var_pb, idx=tex_idx)
                # Find all the materials that map to this texture
                for mat_idx, mat in enumerate(self._gltf.materials):
                    if not hasattr(mat, "pbrMetallicRoughness"):
                        continue
                    if not hasattr(mat.pbrMetallicRoughness, "baseColorTexture"):
                        continue
                    if not hasattr(mat.pbrMetallicRoughness.baseColorTexture, "index"):
                        continue
                    if mat.pbrMetallicRoughness.baseColorTexture.index == tex_idx:
                        material_index = mat_idx
                    # does this Variable/texture already exist?
                    duplicate = None
                    saved_id = var_pb.id
                    saved_name = var_pb.name
                    for key, value in self._glb_textures.items():
                        var_pb.name = value["pb"].name
                        var_pb.id = value["pb"].id
                        if value["pb"] == var_pb:
                            duplicate = key
                            break
                    var_pb.id = saved_id
                    var_pb.name = saved_name
                    # if a new texture, add the Variable and create an index to the material
                    if duplicate is None:
                        self._handle_update_command(cmd)
                        self._glb_textures[material_index] = d
                    else:
                        # create an additional reference to this variable from this material
                        self._glb_textures[material_index] = self._glb_textures[duplicate]

            # GLB file: general layout
            # scene: "default_index"
            # scenes: [scene_index].nodes -> [node ids]
            # was scene_id = self._gltf.scene
            num_scenes = len(self._gltf.scenes)
            for scene_idx in range(num_scenes):
                # GLB Scene -> DSG View
                cmd, view_pb = self._create_pb("VIEW", parent_id=self._scene_id)
                view_pb.lookat.extend([0.0, 0.0, -1.0])
                view_pb.lookfrom.extend([0.0, 0.0, 0.0])
                view_pb.upvector.extend([0.0, 1.0, 0.0])
                view_pb.timeline.extend(self._build_scene_timeline(scene_idx, timeline))
                if len(self._gltf.cameras) > 0:
                    camera = self._gltf.cameras[0]
                    if camera.type == "orthographic":
                        view_pb.nearfar.extend(
                            [float(camera.orthographic.znear), float(camera.orthographic.zfar)]
                        )
                    else:
                        view_pb.nearfar.extend(
                            [float(camera.perspective.znear), float(camera.perspective.zfar)]
                        )
                        view_pb.fieldofview = camera.perspective.yfov
                        view_pb.aspectratio = camera.aspectratio.aspectRatio
                self._handle_update_command(cmd)
                # walk the scene nodes
                scene = self._gltf.scenes[scene_idx]
                try:
                    if self._callback_handler._omni.line_width == 0.0:
                        width = float(scene.extensions["ANSYS_linewidth"]["linewidth"])
                        self._callback_handler._omni.line_width = width
                except (KeyError, ValueError):
                    # in the case where the extension does not exist or is mal-formed
                    pass
                for node_id in scene.nodes:
                    self._walk_node(node_id, view_pb.id)
                self._finish_part()

            self._callback_handler.end_update()

        except Exception as e:
            import traceback

            self.error(f"Unable to process: {glb_filename} : {e}")
            traceback_str = "".join(traceback.format_tb(e.__traceback__))
            logging.debug(f"Traceback: {traceback_str}")
            ok = False

        return ok

    def _build_scene_timeline(self, scene_idx: int, input_timeline: List[float]) -> List[float]:
        """
        For a given scene and externally supplied timeline, compute the timeline for the scene.

        If the ANSYS_scene_time extension is present, use that value.
        If there is only a single scene, return the supplied timeline.
        If the supplied timeline is empty, use an integer timeline based on the number of scenes in the GLB file.
        Carve up the timeline into chunks, one per scene.

        Parameters
        ----------
        scene_idx: int
            The index of the scene to compute for.

        input_timeline: List[float]
            An externally supplied timeline.

        Returns
        -------
        List[float]
            The computed timeline.
        """
        num_scenes = len(self._gltf.scenes)
        # if ANSYS_scene_timevalue is used, time ranges will come from there
        try:
            t0 = self._gltf.scenes[scene_idx].extensions["ANSYS_scene_timevalue"]["timevalue"]
            idx = scene_idx + 1
            if idx < num_scenes:
                t1 = self._gltf.scenes[idx].extensions["ANSYS_scene_timevalue"]["timevalue"]
            else:
                t1 = t0
            return [t0, t1]
        except KeyError:
            # If we fail due to dictionary key issue, the extension does not exist or is
            # improperly formatted.
            pass
        # if there is only one scene, then use the input timeline
        if num_scenes == 1:
            return input_timeline
        # if the timeline has zero length, we make it the number of scenes
        timeline = input_timeline
        if timeline[1] - timeline[0] <= 0.0:
            timeline = [0.0, float(num_scenes - 1)]
        # carve time into the input timeline.
        delta = (timeline[1] - timeline[0]) / float(num_scenes - 1)
        output: List[float] = []
        output.append(float(scene_idx) * delta + timeline[0])
        if scene_idx < num_scenes - 1:
            output.append(output[0] + delta)
        else:
            output.append(output[0])
        return output

    @staticmethod
    def _transform(node: Any) -> List[float]:
        """
        Convert the node "matrix" or "translation", "rotation" and "scale" values into
        a 4x4 matrix representation.

        "nodes": [
             {
             "matrix": [
             1,0,0,0,
             0,1,0,0,
             0,0,1,0,
             5,6,7,1
             ],
             ...
             },
             {
             "translation":
             [ 0,0,0 ],
             "rotation":
             [ 0,0,0,1 ],
             "scale":
             [ 1,1,1 ]
             ...
             },
            ]

        Parameters
        ----------
        node: Any
            The node to compute the matrix transform for.

        Returns
        -------
        List[float]
            The 4x4 transformation matrix.

        """
        identity = numpy.identity(4)
        if node.matrix:
            tmp = numpy.array(node.matrix)
            tmp.shape = (4, 4)
            tmp = tmp.transpose()
            return list(tmp.flatten())
        if node.translation:
            identity[3][0] = node.translation[0]
            identity[3][1] = node.translation[1]
            identity[3][2] = node.translation[2]
        if node.rotation:
            # In GLB, the null quat is [0,0,0,1] so reverse the vector here
            q = [node.rotation[3], node.rotation[0], node.rotation[1], node.rotation[2]]
            rot = numpy.array(
                [
                    [q[0], -q[1], -q[2], -q[3]],
                    [q[1], q[0], -q[3], q[2]],
                    [q[2], q[3], q[0], -q[1]],
                    [q[3], -q[2], q[1], q[0]],
                ]
            )
            identity = numpy.multiply(identity, rot)
        if node.scale:
            s = node.scale
            scale = numpy.array(
                [
                    [s[0], 0.0, 0.0, 0.0],
                    [0.0, s[1], 0.0, 0.0],
                    [0.0, 0.0, s[2], 0.0],
                    [0.0, 0.0, 0.0, 1.0],
                ]
            )
            identity = numpy.multiply(identity, scale)
        return list(identity.flatten())

    def _name(self, node: Any) -> str:
        """
        Given a GLB node object, return the name of the node.  If the node does not
        have a name, give it a generated node.

        Parameters
        ----------
        node: Any
            The GLB node to get the name of.

        Returns
        -------
        str
            The name of the node.
        """
        if hasattr(node, "name") and node.name:
            return node.name
        self._node_idx += 1
        return f"Node_{self._node_idx}"

    def _create_pb(
        self, cmd_type: str, parent_id: int = -1, name: str = ""
    ) -> "dynamic_scene_graph_pb2.SceneUpdateCommand":
        cmd = dynamic_scene_graph_pb2.SceneUpdateCommand()
        if cmd_type == "PART":
            cmd.command_type = dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_PART
            subcmd = cmd.update_part
            subcmd.hash = str(uuid.uuid1())
        elif cmd_type == "GROUP":
            cmd.command_type = dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_GROUP
            subcmd = cmd.update_group
        elif cmd_type == "VARIABLE":
            cmd.command_type = dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_VARIABLE
            subcmd = cmd.update_variable
        elif cmd_type == "GEOM":
            cmd.command_type = dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_GEOM
            subcmd = cmd.update_geom
            subcmd.hash = str(uuid.uuid1())
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
