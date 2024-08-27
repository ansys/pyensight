#
# This file borrows heavily from the Omniverse Example Connector which
# contains the following notice:
#
###############################################################################
# Copyright 2020 NVIDIA Corporation
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
###############################################################################

import logging
import math
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional

from ansys.pyensight.core.utils.dsg_server import Part, UpdateHandler
import png
from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdShade


class OmniverseWrapper(object):
    def __init__(self, live_edit: bool = False, destination: str = "") -> None:
        self._cleaned_index = 0
        self._cleaned_names: dict = {}
        self._connectionStatusSubscription = None
        self._stage = None
        self._destinationPath: str = ""
        self._old_stages: list = []
        self._stagename = "dsg_scene.usd"
        self._live_edit: bool = live_edit
        if self._live_edit:
            self._stagename = "dsg_scene.live"
        # USD time slider will have 120 tick marks per second of animation time
        self._time_codes_per_second = 120.0

        if destination:
            self.destination = destination

    @property
    def destination(self) -> str:
        """The current output directory."""
        return self._destinationPath

    @destination.setter
    def destination(self, directory: str) -> None:
        self._destinationPath = directory
        if not self.is_valid_destination(directory):
            logging.warning(f"Invalid destination path: {directory}")

    def shutdown(self) -> None:
        """
        Shutdown the connection to Omniverse cleanly.
        """
        self._connectionStatusSubscription = None

    @staticmethod
    def is_valid_destination(path: str) -> bool:
        """
        Verify that the target path is a writeable directory.

        Parameters
        ----------
        path
            The path to check

        Returns
        -------
            True if the path is a writeable directory, False otherwise.
        """
        return os.access(path, os.W_OK)

    def stage_url(self, name: Optional[str] = None) -> str:
        """
        For a given object name, create the URL for the item.
        Parameters
        ----------
        name: the name of the object to generate the URL for. If None, it will be the URL for the
              stage name.

        Returns
        -------
        The URL for the object.
        """
        if name is None:
            name = self._stagename
        return os.path.join(self._destinationPath, name)

    def delete_old_stages(self) -> None:
        """
        Remove all the stages included in the "_old_stages" list.
        If a stage is in use and cannot be removed, keep its name in _old_stages
        to retry later.
        """
        stages_unremoved = list()
        while self._old_stages:
            stage = self._old_stages.pop()
            try:
                if os.path.isfile(stage):
                    os.remove(stage)
                else:
                    shutil.rmtree(stage, ignore_errors=True, onerror=None)
            except OSError:
                stages_unremoved.append(stage)
        self._old_stages = stages_unremoved

    def create_new_stage(self) -> None:
        """
        Create a new stage. using the current stage name.
        """
        logging.info(f"Creating Omniverse stage: {self.stage_url()}")
        if self._stage:
            self._stage.Unload()
            self._stage = None
        self.delete_old_stages()
        self._stage = Usd.Stage.CreateNew(self.stage_url())
        # record the stage in the "_old_stages" list.
        self._old_stages.append(self.stage_url())
        UsdGeom.SetStageUpAxis(self._stage, UsdGeom.Tokens.y)
        # in M
        UsdGeom.SetStageMetersPerUnit(self._stage, 1.0)
        logging.info(f"Created stage: {self.stage_url()}")

    def save_stage(self, comment: str = "") -> None:
        """
        For live connections, save the current edit and allow live processing.

        Presently, live connections are disabled.
        """
        self._stage.GetRootLayer().Save()  # type:ignore

    def clear_cleaned_names(self) -> None:
        """
        Clear the list of cleaned names
        """
        self._cleaned_names = {}
        self._cleaned_index = 0

    def clean_name(self, name: str, id_name: Any = None) -> str:
        """Generate a valid USD name

        From a base (EnSight) varname, partname, etc. and the DSG id, generate
        a unique, valid USD name.  Save the names so that if the same name
        comes in again, the previously computed name is returned and if the
        manipulation results in a conflict, the name can be made unique.

        Parameters
        ----------
        name:
            The name to generate a USD name for.

        id_name:
            The DSG id associated with the DSG name, if any.

        Returns
        -------
            A unique USD name.
        """
        orig_name = name
        # return any previously generated name
        if (name, id_name) in self._cleaned_names:
            return self._cleaned_names[(name, id_name)]
        # replace invalid characters.  EnSight uses a number of characters that are illegal in USD names.
        replacements = {
            ord("+"): "_",
            ord("-"): "_",
            ord("."): "_",
            ord(":"): "_",
            ord("["): "_",
            ord("]"): "_",
            ord("("): "_",
            ord(")"): "_",
            ord("<"): "_",
            ord(">"): "_",
            ord("/"): "_",
            ord("="): "_",
            ord(","): "_",
            ord(" "): "_",
            ord("\\"): "_",
        }
        name = name.translate(replacements)
        if name[0].isdigit():
            name = f"_{name}"
        if id_name is not None:
            name = name + "_" + str(id_name)
        if name in self._cleaned_names.values():
            # Make the name unique
            while f"{name}_{self._cleaned_index}" in self._cleaned_names.values():
                self._cleaned_index += 1
            name = f"{name}_{self._cleaned_index}"
        # store off the cleaned name
        self._cleaned_names[(orig_name, id_name)] = name
        return name

    @staticmethod
    def decompose_matrix(values: Any) -> Any:
        """
        Decompose an array of floats (representing a 4x4 matrix) into scale, rotation and translation.
        Parameters
        ----------
        values:
            16 values (input to Gf.Matrix4f CTOR)

        Returns
        -------
        (scale, rotation, translation)
        """
        # ang_convert = 180.0/math.pi
        ang_convert = 1.0
        trans_convert = 1.0
        m = Gf.Matrix4f(*values)
        m = m.GetTranspose()

        s = math.sqrt(m[0][0] * m[0][0] + m[0][1] * m[0][1] + m[0][2] * m[0][2])
        # cleanup scale
        m = m.RemoveScaleShear()
        # r = m.ExtractRotation()
        R = m.ExtractRotationMatrix()
        r = [
            math.atan2(R[2][1], R[2][2]) * ang_convert,
            math.atan2(-R[2][0], 1.0) * ang_convert,
            math.atan2(R[1][0], R[0][0]) * ang_convert,
        ]
        t = m.ExtractTranslation()
        t = [t[0] * trans_convert, t[1] * trans_convert, t[2] * trans_convert]
        return s, r, t

    def create_dsg_mesh_block(
        self,
        name,
        id,
        part_hash,
        parent_prim,
        verts,
        conn,
        normals,
        tcoords,
        matrix=[1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        diffuse=[1.0, 1.0, 1.0, 1.0],
        variable=None,
        timeline=[0.0, 0.0],
        first_timestep=False,
    ):
        # 1D texture map for variables https://graphics.pixar.com/usd/release/tut_simple_shading.html
        # create the part usd object
        partname = self.clean_name(name + part_hash.hexdigest())
        stage_name = "/Parts/" + partname + ".usd"
        part_stage_url = self.stage_url(os.path.join("Parts", partname + ".usd"))
        part_stage = None

        if not os.path.exists(part_stage_url):
            part_stage = Usd.Stage.CreateNew(part_stage_url)
            self._old_stages.append(part_stage_url)
            xform = UsdGeom.Xform.Define(part_stage, "/" + partname)
            mesh = UsdGeom.Mesh.Define(part_stage, "/" + partname + "/Mesh")
            # mesh.CreateDisplayColorAttr()
            mesh.CreateDoubleSidedAttr().Set(True)
            mesh.CreatePointsAttr(verts)
            mesh.CreateNormalsAttr(normals)
            mesh.CreateFaceVertexCountsAttr([3] * int(conn.size / 3))
            mesh.CreateFaceVertexIndicesAttr(conn)
            if (tcoords is not None) and variable:
                # USD 22.08 changed the primvar API
                if hasattr(mesh, "CreatePrimvar"):
                    texCoords = mesh.CreatePrimvar(
                        "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.varying
                    )
                else:
                    primvarsAPI = UsdGeom.PrimvarsAPI(mesh)
                    texCoords = primvarsAPI.CreatePrimvar(
                        "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.varying
                    )
                texCoords.Set(tcoords)
                texCoords.SetInterpolation("vertex")
            part_prim = part_stage.GetPrimAtPath("/" + partname)
            part_stage.SetDefaultPrim(part_prim)

            # Currently, this will never happen, but it is a setup for rigid body transforms
            # At present, the group transforms have been cooked into the vertices so this is not needed
            matrixOp = xform.AddXformOp(
                UsdGeom.XformOp.TypeTransform, UsdGeom.XformOp.PrecisionDouble
            )
            matrixOp.Set(Gf.Matrix4d(*matrix).GetTranspose())

            self.create_dsg_material(
                part_stage, mesh, "/" + partname, diffuse=diffuse, variable=variable
            )

        timestep_prim = self.add_timestep_group(parent_prim, timeline, first_timestep)

        # glue it into our stage
        path = timestep_prim.GetPath().AppendChild("part_ref_" + partname)
        part_ref = self._stage.OverridePrim(path)
        part_ref.GetReferences().AddReference("." + stage_name)

        if part_stage is not None:
            part_stage.GetRootLayer().Save()

        return part_stage_url

    def add_timestep_group(
        self, parent_prim: UsdGeom.Xform, timeline: List[float], first_timestep: bool
    ) -> UsdGeom.Xform:
        # add a layer in the group hierarchy for the timestep
        timestep_group_path = parent_prim.GetPath().AppendChild(
            self.clean_name("t" + str(timeline[0]), None)
        )
        timestep_prim = UsdGeom.Xform.Define(self._stage, timestep_group_path)
        visibility_attr = UsdGeom.Imageable(timestep_prim).GetVisibilityAttr()
        if first_timestep:
            visibility_attr.Set("inherited", Usd.TimeCode.EarliestTime())
        else:
            visibility_attr.Set("invisible", Usd.TimeCode.EarliestTime())
        visibility_attr.Set("inherited", timeline[0] * self._time_codes_per_second)
        # Final timestep has timeline[0]==timeline[1].  Leave final timestep visible.
        if timeline[0] < timeline[1]:
            visibility_attr.Set("invisible", timeline[1] * self._time_codes_per_second)
        return timestep_prim

    def create_dsg_points(
        self,
        name,
        id,
        part_hash,
        parent_prim,
        verts,
        sizes,
        colors,
        matrix=[1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        default_size=1.0,
        default_color=[1.0, 1.0, 1.0, 1.0],
        timeline=[0.0, 0.0],
        first_timestep=False,
    ):
        # create the part usd object
        partname = self.clean_name(name + part_hash.hexdigest())
        stage_name = "/Parts/" + partname + ".usd"
        part_stage_url = self.stage_url(os.path.join("Parts", partname + ".usd"))
        part_stage = None

        if not os.path.exists(part_stage_url):
            part_stage = Usd.Stage.CreateNew(part_stage_url)
            self._old_stages.append(part_stage_url)
            xform = UsdGeom.Xform.Define(part_stage, "/" + partname)

            points = UsdGeom.Points.Define(part_stage, "/" + partname + "/Points")
            # points.GetPointsAttr().Set(Vt.Vec3fArray(verts.tolist()))
            points.GetPointsAttr().Set(verts)
            if sizes is not None and sizes.size == (verts.size // 3):
                points.GetWidthsAttr().Set(sizes)
            else:
                points.GetWidthsAttr().Set([default_size] * (verts.size // 3))

            colorAttr = points.GetPrim().GetAttribute("primvars:displayColor")
            colorAttr.SetMetadata("interpolation", "vertex")
            if colors is not None and colors.size == verts.size:
                colorAttr.Set(colors)
            else:
                colorAttr.Set([default_color[0:3]] * (verts.size // 3))

            part_prim = part_stage.GetPrimAtPath("/" + partname)
            part_stage.SetDefaultPrim(part_prim)

            # Currently, this will never happen, but it is a setup for rigid body transforms
            # At present, the group transforms have been cooked into the vertices so this is not needed
            matrixOp = xform.AddXformOp(
                UsdGeom.XformOp.TypeTransform, UsdGeom.XformOp.PrecisionDouble
            )
            matrixOp.Set(Gf.Matrix4d(*matrix).GetTranspose())

        timestep_prim = self.add_timestep_group(parent_prim, timeline, first_timestep)

        # glue it into our stage
        path = timestep_prim.GetPath().AppendChild("part_ref_" + partname)
        part_ref = self._stage.OverridePrim(path)
        part_ref.GetReferences().AddReference("." + stage_name)

        if part_stage is not None:
            part_stage.GetRootLayer().Save()

        return part_stage_url

    def create_dsg_material(
        self, stage, mesh, root_name, diffuse=[1.0, 1.0, 1.0, 1.0], variable=None
    ):
        # https://graphics.pixar.com/usd/release/spec_usdpreviewsurface.html
        material = UsdShade.Material.Define(stage, root_name + "/Material")
        pbrShader = UsdShade.Shader.Define(stage, root_name + "/Material/PBRShader")
        pbrShader.CreateIdAttr("UsdPreviewSurface")
        pbrShader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0)
        pbrShader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
        pbrShader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(diffuse[3])
        pbrShader.CreateInput("useSpecularWorkflow", Sdf.ValueTypeNames.Int).Set(1)
        if variable:
            stReader = UsdShade.Shader.Define(stage, root_name + "/Material/stReader")
            stReader.CreateIdAttr("UsdPrimvarReader_float2")
            diffuseTextureSampler = UsdShade.Shader.Define(
                stage, root_name + "/Material/diffuseTexture"
            )
            diffuseTextureSampler.CreateIdAttr("UsdUVTexture")
            name = self.clean_name(variable.name)
            filename = self._destinationPath + f"/Parts/Textures/palette_{name}.png"
            diffuseTextureSampler.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(filename)
            diffuseTextureSampler.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
                stReader.ConnectableAPI(), "result"
            )
            diffuseTextureSampler.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
            pbrShader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
                diffuseTextureSampler.ConnectableAPI(), "rgb"
            )
            stInput = material.CreateInput("frame:stPrimvarName", Sdf.ValueTypeNames.Token)
            stInput.Set("st")
            stReader.CreateInput("varname", Sdf.ValueTypeNames.Token).ConnectToSource(stInput)
        else:
            scale = 1.0
            color = Gf.Vec3f(diffuse[0] * scale, diffuse[1] * scale, diffuse[2] * scale)
            pbrShader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(color)

        material.CreateSurfaceOutput().ConnectToSource(pbrShader.ConnectableAPI(), "surface")
        UsdShade.MaterialBindingAPI(mesh).Bind(material)

        return material

    def create_dsg_variable_textures(self, variables):
        with tempfile.TemporaryDirectory() as tempdir:
            # make folder:   {tempdir}/scratch/Textures/{palette_*.png}
            os.makedirs(f"{tempdir}/scratch/Textures", exist_ok=True)
            for var in variables.values():
                data = bytearray(var.texture)
                n_pixels = int(len(data) / 4)
                row = []
                for i in range(n_pixels):
                    row.append(data[i * 4 + 0])
                    row.append(data[i * 4 + 1])
                    row.append(data[i * 4 + 2])
                io = png.Writer(width=n_pixels, height=2, bitdepth=8, greyscale=False)
                rows = [row, row]
                name = self.clean_name(var.name)
                with open(f"{tempdir}/scratch/Textures/palette_{name}.png", "wb") as fp:
                    io.write(fp, rows)
            uriPath = self._destinationPath + "/Parts/Textures"
            shutil.rmtree(uriPath, ignore_errors=True, onerror=None)
            shutil.copytree(f"{tempdir}/scratch/Textures", uriPath)

    def create_dsg_root(self):
        root_name = "/Root"
        root_prim = UsdGeom.Xform.Define(self._stage, root_name)
        # Define the defaultPrim as the /Root prim
        root_prim = self._stage.GetPrimAtPath(root_name)
        self._stage.SetDefaultPrim(root_prim)
        return root_prim

    def update_camera(self, camera):
        if camera is not None:
            cam_name = "/Root/Cam"
            cam_prim = UsdGeom.Xform.Define(self._stage, cam_name)
            cam_pos = Gf.Vec3d(camera.lookfrom[0], camera.lookfrom[1], camera.lookfrom[2])
            target_pos = Gf.Vec3d(camera.lookat[0], camera.lookat[1], camera.lookat[2])
            up_vec = Gf.Vec3d(camera.upvector[0], camera.upvector[1], camera.upvector[2])
            cam_prim = self._stage.GetPrimAtPath(cam_name)
            geom_cam = UsdGeom.Camera(cam_prim)
            if not geom_cam:
                geom_cam = UsdGeom.Camera.Define(self._stage, cam_name)
            # Set camera values
            # center of interest attribute unique for Kit defines the pivot for tumbling the camera
            # Set as an attribute on the prim
            coi_attr = cam_prim.GetAttribute("omni:kit:centerOfInterest")
            if not coi_attr.IsValid():
                coi_attr = cam_prim.CreateAttribute(
                    "omni:kit:centerOfInterest", Sdf.ValueTypeNames.Vector3d
                )
            coi_attr.Set(target_pos)
            # get the camera
            cam = geom_cam.GetCamera()
            # LOL, not sure why is might be correct, but so far it seems to work???
            cam.focalLength = camera.fieldofview
            cam.clippingRange = Gf.Range1f(0.1, 10)
            look_at = Gf.Matrix4d()
            look_at.SetLookAt(cam_pos, target_pos, up_vec)
            trans_row = look_at.GetRow(3)
            trans_row = Gf.Vec4d(-trans_row[0], -trans_row[1], -trans_row[2], trans_row[3])
            look_at.SetRow(3, trans_row)
            # print(look_at)
            cam.transform = look_at

            # set the updated camera
            geom_cam.SetFromCamera(cam)

    def create_dsg_group(
        self,
        name: str,
        parent_prim,
        obj_type: Any = None,
        matrix: List[float] = [
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
        ],
    ):
        path = parent_prim.GetPath().AppendChild(self.clean_name(name))
        group_prim = UsdGeom.Xform.Get(self._stage, path)
        if not group_prim:
            group_prim = UsdGeom.Xform.Define(self._stage, path)
            # At present, the group transforms have been cooked into the vertices so this is not needed
            matrixOp = group_prim.AddXformOp(
                UsdGeom.XformOp.TypeTransform, UsdGeom.XformOp.PrecisionDouble
            )
            matrixOp.Set(Gf.Matrix4d(*matrix).GetTranspose())
            logging.info(f"Created group:'{name}' {str(obj_type)}")
        return group_prim

    def uploadMaterial(self):
        uriPath = self._destinationPath + "/Materials"
        shutil.rmtree(uriPath, ignore_errors=True, onerror=None)
        fullpath = os.path.join(os.path.dirname(__file__), "resources", "Materials")
        shutil.copytree(fullpath, uriPath)

    # Create a dome light in the scene.
    def createDomeLight(self, texturePath):
        newLight = UsdLux.DomeLight.Define(self._stage, "/Root/DomeLight")
        newLight.CreateIntensityAttr(2200.0)
        newLight.CreateTextureFileAttr(texturePath)
        newLight.CreateTextureFormatAttr("latlong")

        # Set rotation on domelight
        xForm = newLight
        rotateOp = xForm.AddXformOp(UsdGeom.XformOp.TypeRotateZYX, UsdGeom.XformOp.PrecisionFloat)
        rotateOp.Set(Gf.Vec3f(270, 0, 0))


class OmniverseUpdateHandler(UpdateHandler):
    """
    Implement the Omniverse glue to a DSGSession instance
    """

    def __init__(self, omni: OmniverseWrapper):
        super().__init__()
        self._omni = omni
        self._group_prims: Dict[int, Any] = dict()
        self._root_prim = None
        self._sent_textures = False

    def add_group(self, id: int, view: bool = False) -> None:
        super().add_group(id, view)
        group = self.session.groups[id]
        if not view:
            parent_prim = self._group_prims[group.parent_id]
            obj_type = self.get_dsg_cmd_attribute(group, "ENS_OBJ_TYPE")
            matrix = self.group_matrix(group)
            prim = self._omni.create_dsg_group(
                group.name, parent_prim, matrix=matrix, obj_type=obj_type
            )
            self._group_prims[id] = prim
        else:
            # Map a view command into a new Omniverse stage and populate it with materials/lights.
            # Create a new root stage in Omniverse

            # Create or update the root group/camera
            if not self.session.vrmode:
                self._omni.update_camera(camera=group)

            # record
            self._group_prims[id] = self._root_prim

            if self._omni._stage is not None:
                self._omni._stage.SetStartTimeCode(
                    self.session.time_limits[0] * self._omni._time_codes_per_second
                )
                self._omni._stage.SetEndTimeCode(
                    self.session.time_limits[1] * self._omni._time_codes_per_second
                )
                self._omni._stage.SetTimeCodesPerSecond(self._omni._time_codes_per_second)

            # Send the variable textures.  Safe to do so once the first view is processed.
            if not self._sent_textures:
                self._omni.create_dsg_variable_textures(self.session.variables)
                self._sent_textures = True

    def add_variable(self, id: int) -> None:
        super().add_variable(id)

    def finalize_part(self, part: Part) -> None:
        # generate an Omniverse compliant mesh from the Part
        if part is None or part.cmd is None:
            return
        parent_prim = self._group_prims[part.cmd.parent_id]
        obj_id = self.session.mesh_block_count
        matrix = part.cmd.matrix4x4
        name = part.cmd.name
        color = [
            part.cmd.fill_color[0] * part.cmd.diffuse,
            part.cmd.fill_color[1] * part.cmd.diffuse,
            part.cmd.fill_color[2] * part.cmd.diffuse,
            part.cmd.fill_color[3],
        ]

        if part.cmd.render == part.cmd.CONNECTIVITY:
            command, verts, conn, normals, tcoords, var_cmd = part.nodal_surface_rep()
            if command is not None:
                # Generate the mesh block
                _ = self._omni.create_dsg_mesh_block(
                    name,
                    obj_id,
                    part.hash,
                    parent_prim,
                    verts,
                    conn,
                    normals,
                    tcoords,
                    matrix=matrix,
                    diffuse=color,
                    variable=var_cmd,
                    timeline=self.session.cur_timeline,
                    first_timestep=(self.session.cur_timeline[0] == self.session.time_limits[0]),
                )

        elif part.cmd.render == part.cmd.NODES:
            command, verts, sizes, colors, var_cmd = part.point_rep()
            if command is not None:
                _ = self._omni.create_dsg_points(
                    name,
                    obj_id,
                    part.hash,
                    parent_prim,
                    verts,
                    sizes,
                    colors,
                    matrix=matrix,
                    default_size=part.cmd.node_size_default,
                    default_color=color,
                    timeline=self.session.cur_timeline,
                    first_timestep=(self.session.cur_timeline[0] == self.session.time_limits[0]),
                )
        super().finalize_part(part)

    def start_connection(self) -> None:
        super().start_connection()

    def end_connection(self) -> None:
        super().end_connection()

    def begin_update(self) -> None:
        super().begin_update()
        # restart the name tables
        self._omni.clear_cleaned_names()
        # clear the group Omni prims list
        self._group_prims = dict()

        self._omni.create_new_stage()
        self._root_prim = self._omni.create_dsg_root()
        # Create a distance and dome light in the scene
        self._omni.createDomeLight("./Materials/000_sky.exr")
        # Upload a material to the Omniverse server
        self._omni.uploadMaterial()
        self._sent_textures = False

    def end_update(self) -> None:
        super().end_update()
        # Stage update complete
        self._omni.save_stage()
