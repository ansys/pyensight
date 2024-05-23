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

import argparse
import logging
import math
import os
import queue
import shutil
import sys
import threading
from typing import Any, List, Optional

from ansys.api.pyensight.v0 import dynamic_scene_graph_pb2
from ansys.pyensight.core import ensight_grpc
import numpy
import omni.client
import png
from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdShade


class OmniverseWrapper:
    verbose = 0

    @staticmethod
    def logCallback(threadName: None, component: Any, level: Any, message: str) -> None:
        if OmniverseWrapper.verbose:
            logging.info(message)

    @staticmethod
    def connectionStatusCallback(
        url: Any, connectionStatus: "omni.client.ConnectionStatus"
    ) -> None:
        if connectionStatus is omni.client.ConnectionStatus.CONNECT_ERROR:
            sys.exit("[ERROR] Failed connection, exiting.")

    def __init__(
        self,
        live_edit: bool = False,
        path: str = "omniverse://localhost/Users/test",
        verbose: int = 0,
    ):
        self._cleaned_index = 0
        self._cleaned_names: dict = {}
        self._connectionStatusSubscription = None
        self._stage = None
        self._destinationPath = path
        self._old_stages: list = []
        self._stagename = "dsg_scene.usd"
        self._live_edit = live_edit
        if self._live_edit:
            self._stagename = "dsg_scene.live"
        OmniverseWrapper.verbose = verbose

        omni.client.set_log_callback(OmniverseWrapper.logCallback)
        if verbose > 1:
            omni.client.set_log_level(omni.client.LogLevel.DEBUG)

        if not omni.client.initialize():
            sys.exit("[ERROR] Unable to initialize Omniverse client, exiting.")

        self._connectionStatusSubscription = omni.client.register_connection_status_callback(
            OmniverseWrapper.connectionStatusCallback
        )

        if not self.isValidOmniUrl(self._destinationPath):
            self.log("Note technically the Omniverse URL {self._destinationPath} is not valid")

    def log(self, msg: str) -> None:
        if OmniverseWrapper.verbose:
            logging.info(msg)

    def shutdown(self) -> None:
        omni.client.live_wait_for_pending_updates()
        self._connectionStatusSubscription = None
        omni.client.shutdown()

    @staticmethod
    def isValidOmniUrl(url: str) -> bool:
        omniURL = omni.client.break_url(url)
        if omniURL.scheme == "omniverse" or omniURL.scheme == "omni":
            return True
        return False

    def stage_url(self, name: Optional[str] = None) -> str:
        if name is None:
            name = self._stagename
        return self._destinationPath + "/" + name

    def delete_old_stages(self) -> None:
        while self._old_stages:
            stage = self._old_stages.pop()
            omni.client.delete(stage)

    def create_new_stage(self) -> None:
        self.log(f"Creating Omniverse stage: {self.stage_url()}")
        if self._stage:
            self._stage.Unload()
            self._stage = None
        self.delete_old_stages()
        self._stage = Usd.Stage.CreateNew(self.stage_url())
        self._old_stages.append(self.stage_url())
        UsdGeom.SetStageUpAxis(self._stage, UsdGeom.Tokens.y)
        # in M
        UsdGeom.SetStageMetersPerUnit(self._stage, 1.0)
        self.log(f"Created stage: {self.stage_url()}")

    def save_stage(self) -> None:
        self._stage.GetRootLayer().Save()  # type:ignore
        omni.client.live_process()

    # This function will add a commented checkpoint to a file on Nucleus if:
    #   Live mode is disabled (live checkpoints are ill-supported)
    #   The Nucleus server supports checkpoints
    def checkpoint(self, comment: str = "") -> None:
        if self._live_edit:
            return
        result, serverInfo = omni.client.get_server_info(self.stage_url())
        if result and serverInfo and serverInfo.checkpoints_enabled:
            bForceCheckpoint = True
            self.log(f"Adding checkpoint comment <{comment}> to stage <{self.stage_url()}>")
            omni.client.create_checkpoint(self.stage_url(), comment, bForceCheckpoint)

    def username(self, display: bool = True) -> Optional[str]:
        result, serverInfo = omni.client.get_server_info(self.stage_url())
        if serverInfo:
            if display:
                self.log(f"Connected username:{serverInfo.username}")
            return serverInfo.username
        return None

    h = 50.0
    boxVertexIndices = [
        0,
        1,
        2,
        1,
        3,
        2,
        4,
        5,
        6,
        4,
        6,
        7,
        8,
        9,
        10,
        8,
        10,
        11,
        12,
        13,
        14,
        12,
        14,
        15,
        16,
        17,
        18,
        16,
        18,
        19,
        20,
        21,
        22,
        20,
        22,
        23,
    ]
    boxVertexCounts = [3] * 12
    boxNormals = [
        (0, 0, -1),
        (0, 0, -1),
        (0, 0, -1),
        (0, 0, -1),
        (0, 0, 1),
        (0, 0, 1),
        (0, 0, 1),
        (0, 0, 1),
        (0, -1, 0),
        (0, -1, 0),
        (0, -1, 0),
        (0, -1, 0),
        (1, 0, 0),
        (1, 0, 0),
        (1, 0, 0),
        (1, 0, 0),
        (0, 1, 0),
        (0, 1, 0),
        (0, 1, 0),
        (0, 1, 0),
        (-1, 0, 0),
        (-1, 0, 0),
        (-1, 0, 0),
        (-1, 0, 0),
    ]
    boxPoints = [
        (h, -h, -h),
        (-h, -h, -h),
        (h, h, -h),
        (-h, h, -h),
        (h, h, h),
        (-h, h, h),
        (-h, -h, h),
        (h, -h, h),
        (h, -h, h),
        (-h, -h, h),
        (-h, -h, -h),
        (h, -h, -h),
        (h, h, h),
        (h, -h, h),
        (h, -h, -h),
        (h, h, -h),
        (-h, h, h),
        (h, h, h),
        (h, h, -h),
        (-h, h, -h),
        (-h, -h, h),
        (-h, h, h),
        (-h, h, -h),
        (-h, -h, -h),
    ]
    boxUVs = [
        (0, 0),
        (0, 1),
        (1, 1),
        (1, 0),
        (0, 0),
        (0, 1),
        (1, 1),
        (1, 0),
        (0, 0),
        (0, 1),
        (1, 1),
        (1, 0),
        (0, 0),
        (0, 1),
        (1, 1),
        (1, 0),
        (0, 0),
        (0, 1),
        (1, 1),
        (1, 0),
        (0, 0),
        (0, 1),
        (1, 1),
        (1, 0),
    ]

    def createBox(self, box_number: int = 0) -> "UsdGeom.Mesh":
        rootUrl = "/Root"
        boxUrl = rootUrl + "/Boxes/box_%d" % box_number
        xformPrim = UsdGeom.Xform.Define(self._stage, rootUrl)  # noqa: F841
        # Define the defaultPrim as the /Root prim
        rootPrim = self._stage.GetPrimAtPath(rootUrl)  # type:ignore
        self._stage.SetDefaultPrim(rootPrim)  # type:ignore
        boxPrim = UsdGeom.Mesh.Define(self._stage, boxUrl)
        boxPrim.CreateDisplayColorAttr([(0.463, 0.725, 0.0)])
        boxPrim.CreatePointsAttr(OmniverseWrapper.boxPoints)
        boxPrim.CreateNormalsAttr(OmniverseWrapper.boxNormals)
        boxPrim.CreateFaceVertexCountsAttr(OmniverseWrapper.boxVertexCounts)
        boxPrim.CreateFaceVertexIndicesAttr(OmniverseWrapper.boxVertexIndices)
        # USD 22.08 changed the primvar API
        if hasattr(boxPrim, "CreatePrimvar"):
            texCoords = boxPrim.CreatePrimvar(
                "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.varying
            )
        else:
            primvarsAPI = UsdGeom.PrimvarsAPI(boxPrim)
            texCoords = primvarsAPI.CreatePrimvar(
                "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.varying
            )
        texCoords.Set(OmniverseWrapper.boxUVs)
        texCoords.SetInterpolation("vertex")
        if not boxPrim:
            sys.exit("[ERROR] Failure to create box")
        self.save_stage()
        return boxPrim

    def clear_cleaned_names(self) -> None:
        """Clear the list of cleaned names"""
        self._cleaned_names = {}
        self._cleaned_index = 0

    def clean_name(self, name: str, id_name: Any = None) -> str:
        """Generate a vais USD name

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
        # return any previously generated name
        if (name, id_name) in self._cleaned_names:
            return self._cleaned_names[(name, id_name)]
        # replace invalid characters
        name = name.replace("+", "_").replace("-", "_")
        name = name.replace(".", "_").replace(":", "_")
        name = name.replace("[", "_").replace("]", "_")
        name = name.replace("(", "_").replace(")", "_")
        name = name.replace("<", "_").replace(">", "_")
        name = name.replace("/", "_").replace("=", "_")
        name = name.replace(",", "_").replace(" ", "_")
        name = name.replace("\\", "_")
        if id_name is not None:
            name = name + "_" + str(id_name)
        if name in self._cleaned_names.values():
            # Make the name unique
            while f"{name}_{self._cleaned_index}" in self._cleaned_names.values():
                self._cleaned_index += 1
            name = f"{name}_{self._cleaned_index}"
        # store off the cleaned name
        self._cleaned_names[(name, id_name)] = name
        return name

    @staticmethod
    def decompose_matrix(values: Any) -> Any:
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
        parent_prim,
        verts,
        conn,
        normals,
        tcoords,
        matrix=[1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        diffuse=[1.0, 1.0, 1.0, 1.0],
        variable=None,
    ):
        # 1D texture map for variables https://graphics.pixar.com/usd/release/tut_simple_shading.html
        # create the part usd object
        partname = self.clean_name(name, id)
        stage_name = "/Parts/" + partname + ".usd"
        part_stage_url = self.stage_url(stage_name)
        omni.client.delete(part_stage_url)
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
        # sphere = part_stage.DefinePrim('/' + partname + '/sphere', 'Sphere')
        part_prim = part_stage.GetPrimAtPath("/" + partname)
        part_stage.SetDefaultPrim(part_prim)

        # Currently, this will never happen, but it is a setup for rigid body transforms
        # At present, the group transforms have been cooked into the vertices so this is not needed
        matrixOp = xform.AddXformOp(UsdGeom.XformOp.TypeTransform, UsdGeom.XformOp.PrecisionDouble)
        matrixOp.Set(Gf.Matrix4d(*matrix).GetTranspose())

        self.create_dsg_material(
            part_stage, mesh, "/" + partname, diffuse=diffuse, variable=variable
        )
        part_stage.GetRootLayer().Save()

        # glue it into our stage
        path = parent_prim.GetPath().AppendChild("part_ref_" + partname)
        part_ref = self._stage.OverridePrim(path)
        part_ref.GetReferences().AddReference("." + stage_name)

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
        # make folder:   scratch/Textures/{palette_*.png}
        shutil.rmtree("scratch", ignore_errors=True, onerror=None)
        os.makedirs("scratch/Textures", exist_ok=True)
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
            with open(f"scratch/Textures/palette_{name}.png", "wb") as fp:
                io.write(fp, rows)
        uriPath = self._destinationPath + "/Parts/Textures"
        omni.client.delete(uriPath)
        omni.client.copy("scratch/Textures", uriPath)

    def create_dsg_root(self, camera=None):
        root_name = "/Root"
        root_prim = UsdGeom.Xform.Define(self._stage, root_name)
        # Define the defaultPrim as the /Root prim
        root_prim = self._stage.GetPrimAtPath(root_name)
        self._stage.SetDefaultPrim(root_prim)

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
        return root_prim

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
        group_prim = UsdGeom.Xform.Define(self._stage, path)
        # At present, the group transforms have been cooked into the vertices so this is not needed
        matrixOp = group_prim.AddXformOp(
            UsdGeom.XformOp.TypeTransform, UsdGeom.XformOp.PrecisionDouble
        )
        matrixOp.Set(Gf.Matrix4d(*matrix).GetTranspose())
        self.log(f"Created group:'{name}' {str(obj_type)}")
        return group_prim

    def uploadMaterial(self):
        uriPath = self._destinationPath + "/Materials"
        omni.client.delete(uriPath)
        omni.client.copy("resources/Materials", uriPath)

    def createMaterial(self, mesh):
        # Create a material instance for this in USD
        materialName = "Fieldstone"
        newMat = UsdShade.Material.Define(self._stage, "/Root/Looks/Fieldstone")

        matPath = "/Root/Looks/Fieldstone"

        # MDL Shader
        # Create the MDL shader
        mdlShader = UsdShade.Shader.Define(self._stage, matPath + "/Fieldstone")
        mdlShader.CreateIdAttr("mdlMaterial")

        mdlShaderModule = "./Materials/Fieldstone.mdl"
        mdlShader.SetSourceAsset(mdlShaderModule, "mdl")
        # mdlShader.GetPrim().CreateAttribute("info:mdl:sourceAsset:subIdentifier",
        #                                    Sdf.ValueTypeNames.Token, True).Set(materialName)
        # mdlOutput = newMat.CreateSurfaceOutput("mdl")
        # mdlOutput.ConnectToSource(mdlShader, "out")
        mdlShader.SetSourceAssetSubIdentifier(materialName, "mdl")
        shaderOutput = mdlShader.CreateOutput("out", Sdf.ValueTypeNames.Token)
        shaderOutput.SetRenderType("material")
        newMat.CreateSurfaceOutput("mdl").ConnectToSource(shaderOutput)
        newMat.CreateDisplacementOutput("mdl").ConnectToSource(shaderOutput)
        newMat.CreateVolumeOutput("mdl").ConnectToSource(shaderOutput)

        # USD Preview Surface Shaders

        # Create the "USD Primvar reader for float2" shader
        primStShader = UsdShade.Shader.Define(self._stage, matPath + "/PrimST")
        primStShader.CreateIdAttr("UsdPrimvarReader_float2")
        primStShader.CreateOutput("result", Sdf.ValueTypeNames.Float2)
        primStShader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")

        # Create the "Diffuse Color Tex" shader
        diffuseColorShader = UsdShade.Shader.Define(self._stage, matPath + "/DiffuseColorTex")
        diffuseColorShader.CreateIdAttr("UsdUVTexture")
        texInput = diffuseColorShader.CreateInput("file", Sdf.ValueTypeNames.Asset)
        texInput.Set("./Materials/Fieldstone/Fieldstone_BaseColor.png")
        texInput.GetAttr().SetColorSpace("RGB")
        diffuseColorShader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
            primStShader.CreateOutput("result", Sdf.ValueTypeNames.Float2)
        )
        diffuseColorShaderOutput = diffuseColorShader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)

        # Create the "Normal Tex" shader
        normalShader = UsdShade.Shader.Define(self._stage, matPath + "/NormalTex")
        normalShader.CreateIdAttr("UsdUVTexture")
        normalTexInput = normalShader.CreateInput("file", Sdf.ValueTypeNames.Asset)
        normalTexInput.Set("./Materials/Fieldstone/Fieldstone_N.png")
        normalTexInput.GetAttr().SetColorSpace("RAW")
        normalShader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
            primStShader.CreateOutput("result", Sdf.ValueTypeNames.Float2)
        )
        normalShaderOutput = normalShader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)

        # Create the USD Preview Surface shader
        usdPreviewSurfaceShader = UsdShade.Shader.Define(self._stage, matPath + "/PreviewSurface")
        usdPreviewSurfaceShader.CreateIdAttr("UsdPreviewSurface")
        diffuseColorInput = usdPreviewSurfaceShader.CreateInput(
            "diffuseColor", Sdf.ValueTypeNames.Color3f
        )
        diffuseColorInput.ConnectToSource(diffuseColorShaderOutput)
        normalInput = usdPreviewSurfaceShader.CreateInput("normal", Sdf.ValueTypeNames.Normal3f)
        normalInput.ConnectToSource(normalShaderOutput)

        # Set the linkage between material and USD Preview surface shader
        # usdPreviewSurfaceOutput = newMat.CreateSurfaceOutput()
        # usdPreviewSurfaceOutput.ConnectToSource(usdPreviewSurfaceShader, "surface")
        # UsdShade.MaterialBindingAPI(mesh).Bind(newMat)

        usdPreviewSurfaceShaderOutput = usdPreviewSurfaceShader.CreateOutput(
            "surface", Sdf.ValueTypeNames.Token
        )
        usdPreviewSurfaceShaderOutput.SetRenderType("material")
        newMat.CreateSurfaceOutput().ConnectToSource(usdPreviewSurfaceShaderOutput)

        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(newMat)

        # self.save_stage()

    # Create a distant light in the scene.
    def createDistantLight(self):
        newLight = UsdLux.DistantLight.Define(self._stage, "/Root/DistantLight")
        newLight.CreateAngleAttr(0.53)
        newLight.CreateColorAttr(Gf.Vec3f(1.0, 1.0, 0.745))
        newLight.CreateIntensityAttr(500.0)

        # self.save_stage()

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

        # self.save_stage()

    def createEmptyFolder(self, emptyFolderPath):
        folder = self._destinationPath + emptyFolderPath
        self.log(f"Creating new folder: {folder}")
        result = omni.client.create_folder(folder)
        self.log(f"Finished creating: {result.name}")
        return result.name


class Part(object):
    def __init__(self, link: "DSGOmniverseLink"):
        self._link = link
        self.cmd: Optional[Any] = None
        self.reset()

    def reset(self, cmd: Any = None) -> None:
        self.conn_tris = numpy.array([], dtype="int32")
        self.conn_lines = numpy.array([], dtype="int32")
        self.coords = numpy.array([], dtype="float32")
        self.normals = numpy.array([], dtype="float32")
        self.normals_elem = False
        self.tcoords = numpy.array([], dtype="float32")
        self.tcoords_var = None
        self.tcoords_elem = False
        self.cmd = cmd

    def update_geom(self, cmd: dynamic_scene_graph_pb2.UpdateGeom) -> None:
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
            if cmd.variable_id in self._link._variables:
                self.tcoords_var = cmd.variable_id
                self.tcoords_elem = (
                    cmd.payload_type == dynamic_scene_graph_pb2.UpdateGeom.ELEM_VARIABLE
                )
                if self.tcoords.size != cmd.total_array_size:
                    self.tcoords = numpy.resize(self.tcoords, cmd.total_array_size)
                self.tcoords[
                    cmd.chunk_offset : cmd.chunk_offset + len(cmd.flt_array)
                ] = cmd.flt_array
            else:
                self.tcoords_var = None

    def build(self):
        if self.cmd is None:
            return
        if self.conn_lines.size:
            self._link.log(
                f"Note, part '{self.cmd.name}' has lines which are not currently supported."
            )
            self.cmd = None
            return
        verts = self.coords
        if self._link._normalize_geometry and self._link._scene_bounds is not None:
            midx = (self._link._scene_bounds[3] + self._link._scene_bounds[0]) * 0.5
            midy = (self._link._scene_bounds[4] + self._link._scene_bounds[1]) * 0.5
            midz = (self._link._scene_bounds[5] + self._link._scene_bounds[2]) * 0.5
            dx = self._link._scene_bounds[3] - self._link._scene_bounds[0]
            dy = self._link._scene_bounds[4] - self._link._scene_bounds[1]
            dz = self._link._scene_bounds[5] - self._link._scene_bounds[2]
            s = dx
            if dy > s:
                s = dy
            if dz > s:
                s = dz
            if s == 0:
                s = 1.0
            num_verts = int(verts.size / 3)
            for i in range(num_verts):
                j = i * 3
                verts[j + 0] = (verts[j + 0] - midx) / s
                verts[j + 1] = (verts[j + 1] - midy) / s
                verts[j + 2] = (verts[j + 2] - midz) / s

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
                    print("Warning: zero length normals!")
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

        var = None
        # texture coords need transformation from variable value to [ST]
        if tcoords is not None:
            var_id = self.cmd.color_variableid
            var = self._link._variables[var_id]
            v_min = None
            v_max = None
            for lvl in var.levels:
                if (v_min is None) or (v_min > lvl.value):
                    v_min = lvl.value
                if (v_max is None) or (v_max < lvl.value):
                    v_max = lvl.value
            var_minmax = [v_min, v_max]
            # build a power of two x 1 texture
            num_texels = int(len(var.texture) / 4)
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

        parent = self._link._groups[self.cmd.parent_id]
        color = [
            self.cmd.fill_color[0] * self.cmd.diffuse,
            self.cmd.fill_color[1] * self.cmd.diffuse,
            self.cmd.fill_color[2] * self.cmd.diffuse,
            self.cmd.fill_color[3],
        ]
        obj_id = self._link._mesh_block_count
        # prim =
        _ = self._link._omni.create_dsg_mesh_block(
            self.cmd.name,
            obj_id,
            parent[1],
            verts,
            conn,
            normals,
            tcoords,
            matrix=self.cmd.matrix4x4,
            diffuse=color,
            variable=var,
        )
        self._link.log(
            f"Part '{self.cmd.name}' defined: {self.coords.size/3} verts, {self.conn_tris.size/3} tris, {self.conn_lines.size/2} lines."
        )
        self.cmd = None


class DSGOmniverseLink(object):
    def __init__(
        self,
        omni: OmniverseWrapper,
        port: int = 12345,
        host: str = "127.0.0.1",
        security_code: str = "",
        verbose: int = 0,
        normalize_geometry: bool = False,
        vrmode: bool = False,
    ):
        super().__init__()
        self._grpc = ensight_grpc.EnSightGRPC(port=port, host=host, secret_key=security_code)
        self._verbose = verbose
        self._thread: Optional[threading.Thread] = None
        self._message_queue: queue.Queue = queue.Queue()  # Messages coming from EnSight
        self._dsg_queue: Optional[queue.SimpleQueue] = None  # Outgoing messages to EnSight
        self._shutdown = False
        self._dsg = None
        self._omni = omni
        self._normalize_geometry = normalize_geometry
        self._vrmode = vrmode
        self._mesh_block_count = 0
        self._variables: dict = {}
        self._groups: dict = {}
        self._part: Part = Part(self)
        self._scene_bounds: Optional[List] = None

    def log(self, s: str) -> None:
        """Log a string to the logging system

        If verbosity is set, log the string.
        """
        if self._verbose > 0:
            logging.info(s)

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
            logging.info(
                f"Unable to establish gRPC connection to: {self._grpc.host()}:{self._grpc.port()}"
            )
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
        self._thread = threading.Thread(target=self.poll_messages)
        if self._thread is not None:
            self._thread.start()
        return 0

    def end(self):
        """Stop a gRPC connection to the EnSight instance"""
        self._grpc.stop_server()
        self._shutdown = True
        self._thread.join()
        self._grpc.shutdown()
        self._dsg = None
        self._thread = None
        self._dsg_queue = None

    def is_shutdown(self):
        """Check the service shutdown request status"""
        return self._shutdown

    def request_an_update(self, animation: bool = False) -> None:
        """Start a DSG update
        Send a command to the DSG protocol to "init" an update.

        Parameters
        ----------
        animation:
            if True, export all EnSight timesteps.
        """
        # Send an INIT command to trigger a stream of update packets
        cmd = dynamic_scene_graph_pb2.SceneClientCommand()
        cmd.command_type = dynamic_scene_graph_pb2.SceneClientCommand.INIT
        # Allow EnSight push commands, but full scene only for now...
        cmd.init.allow_spontaneous = True
        cmd.init.include_temporal_geometry = animation
        cmd.init.allow_incremental_updates = False
        cmd.init.maximum_chunk_size = 1024 * 1024
        self._dsg_queue.put(cmd)  # type:ignore
        # Handle the update messages
        self.handle_one_update()

    def poll_messages(self) -> None:
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
                logging.info("DSG connection broken, calling exit")
                os._exit(0)

    def get_next_message(self, wait: bool = True) -> Any:
        """Get the next queued up protobuffer message

        Called by the main thread to get any messages that were pulled in from the
        dsg stream and placed here by poll_messages()
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
        cmd = self.get_next_message()
        while (cmd is not None) and (
            cmd.command_type != dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_SCENE_BEGIN
        ):
            # Look for a begin command
            cmd = self.get_next_message()
        self.log("Begin update ------------------------")

        # Start anew
        self._variables = {}
        self._groups = {}
        self._part = Part(self)
        self._scene_bounds = None
        self._mesh_block_count = 0  # reset when a new group shows up
        self._omni.clear_cleaned_names()

        # handle the various commands until UPDATE_SCENE_END
        cmd = self.get_next_message()
        while (cmd is not None) and (
            cmd.command_type != dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_SCENE_END
        ):
            self.handle_update_command(cmd)
            cmd = self.get_next_message()

        # Flush the last part
        self.finish_part()

        # Stage update complete
        self._omni.save_stage()

        self.log("End update --------------------------")

    # handle an incoming gRPC update command
    def handle_update_command(self, cmd: dynamic_scene_graph_pb2.SceneUpdateCommand) -> None:
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
            self.handle_part(tmp)
        elif cmd.command_type == dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_GROUP:
            name = "Group update"
            tmp = cmd.update_group
            self.handle_group(tmp)
        elif cmd.command_type == dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_GEOM:
            name = "Geom update"
            tmp = cmd.update_geom
            self._part.update_geom(tmp)
        elif cmd.command_type == dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_VARIABLE:
            name = "Variable update"
            tmp = cmd.update_variable
            self.handle_variable(tmp)
        elif cmd.command_type == dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_VIEW:
            name = "View update"
            tmp = cmd.update_view
            self.handle_view(tmp)
        elif cmd.command_type == dynamic_scene_graph_pb2.SceneUpdateCommand.UPDATE_TEXTURE:
            name = "Texture update"
        self.log(f"{name} --------------------------")

    def finish_part(self) -> None:
        """Complete the current part

        There is always a part being modified.  This method completes the current part, commits
        it to the Omniverse USD, and sets up the next part.
        """
        self._part.build()
        self._mesh_block_count += 1

    def handle_part(self, part: Any) -> None:
        """Handle a DSG UPDATE_GROUP command
        Parameters
        ----------
        part:
            The command coming from the EnSight stream.
        """
        self.finish_part()
        self._part.reset(part)

    def handle_group(self, group: Any) -> None:
        """Handle a DSG UPDATE_GROUP command
        Parameters
        ----------
        group:
            The command coming from the EnSight stream.
        """
        # reset current mesh (part) count for unique "part" naming in USD
        self._mesh_block_count = 0
        # get the parent group or view
        parent = self._groups[group.parent_id]
        obj_type = group.attributes.get("ENS_OBJ_TYPE", None)
        matrix = group.matrix4x4
        # The Case matrix is basically the camera transform.  In vrmode, we only want
        # the raw geometry, so use the identity matrix.
        if (obj_type == "ENS_CASE") and self._vrmode:
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
        prim = self._omni.create_dsg_group(group.name, parent[1], matrix=matrix, obj_type=obj_type)
        # record the scene bounds in case they are needed later
        self._groups[group.id] = [group, prim]
        bounds = group.attributes.get("ENS_SCENE_BOUNDS", None)
        if bounds:
            minmax = []
            for v in bounds.split(","):
                try:
                    minmax.append(float(v))
                except Exception:
                    pass
            if len(minmax) == 6:
                self._scene_bounds = minmax

    def handle_variable(self, var: Any) -> None:
        """Handle a DSG UPDATE_VARIABLE command

        Save off the EnSight variable DSG command object.

        Parameters
        ----------
        var:
            The command coming from the EnSight stream.
        """
        self._variables[var.id] = var

    def handle_view(self, view: Any) -> None:
        """Handle a DSG UPDATE_VIEW command

        Map a view command into a new Omniverse stage and populate it with materials/lights.

        Parameters
        ----------
        view:
            The command coming from the EnSight stream.
        """
        self._scene_bounds = None
        # Create a new root stage in Omniverse
        self._omni.create_new_stage()
        # Create the root group/camera
        camera_info = view
        if self._vrmode:
            camera_info = None
        root = self._omni.create_dsg_root(camera=camera_info)
        self._omni.checkpoint("Created base scene")
        # Create a distance and dome light in the scene
        # self._omni.createDistantLight()
        # self._omni.createDomeLight("./Materials/kloofendal_48d_partly_cloudy.hdr")
        self._omni.createDomeLight("./Materials/000_sky.exr")
        self._omni.checkpoint("Added lights to stage")
        # Upload a material and textures to the Omniverse server
        self._omni.uploadMaterial()
        self._omni.create_dsg_variable_textures(self._variables)
        # record
        self._groups[view.id] = [view, root]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Python Omniverse EnSight Dynamic Scene Graph Client",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--path",
        action="store",
        default="omniverse://localhost/Users/test",
        help="Omniverse pathname. Default=omniverse://localhost/Users/test",
    )
    parser.add_argument(
        "--port",
        metavar="ensight_grpc_port",
        nargs="?",
        default=12345,
        type=int,
        help="EnSight gRPC port number",
    )
    parser.add_argument(
        "--host",
        metavar="ensight_grpc_host",
        nargs="?",
        default="127.0.0.1",
        type=str,
        help="EnSight gRPC hostname",
    )
    parser.add_argument(
        "--security",
        metavar="ensight_grpc_security_code",
        nargs="?",
        default="",
        type=str,
        help="EnSight gRPC security code",
    )
    parser.add_argument(
        "--verbose",
        metavar="verbose_level",
        default=0,
        type=int,
        help="Enable debugging information",
    )
    parser.add_argument(
        "--animation", dest="animation", action="store_true", help="Save all timesteps (default)"
    )
    parser.add_argument(
        "--no-animation",
        dest="animation",
        action="store_false",
        help="Save only the current timestep",
    )
    parser.set_defaults(animation=False)
    parser.add_argument(
        "--log_file",
        metavar="log_filename",
        default="",
        type=str,
        help="Save program output to the named log file instead of stdout",
    )
    parser.add_argument(
        "--live",
        dest="live",
        action="store_true",
        default=False,
        help="Enable continuous operation",
    )
    parser.add_argument(
        "--normalize_geometry",
        dest="normalize",
        action="store_true",
        default=False,
        help="Spatially normalize incoming geometry",
    )
    parser.add_argument(
        "--vrmode",
        dest="vrmode",
        action="store_true",
        default=False,
        help="In this mode do not include a camera or the case level matrix.  Geometry only.",
    )
    args = parser.parse_args()

    log_args = dict(format="DSG/Omniverse: %(message)s", level=logging.INFO)
    if args.log_file:
        log_args["filename"] = args.log_file
    logging.basicConfig(**log_args)  # type: ignore

    destinationPath = args.path
    loggingEnabled = args.verbose

    # Make the OmniVerse connection
    target = OmniverseWrapper(path=destinationPath, verbose=loggingEnabled)

    # Print the username for the server
    target.username()

    if loggingEnabled:
        logging.info("OmniVerse connection established.")

    dsg_link = DSGOmniverseLink(
        omni=target,
        port=args.port,
        host=args.host,
        vrmode=args.vrmode,
        security_code=args.security,
        verbose=loggingEnabled,
        normalize_geometry=args.normalize,
    )
    if loggingEnabled:
        logging.info(f"Make DSG connection to: {args.host}:{args.port}")

    # Start the DSG link
    err = dsg_link.start()
    if err < 0:
        sys.exit(err)

    # Simple pull request
    dsg_link.request_an_update(animation=args.animation)

    # Live operation
    if args.live:
        if loggingEnabled:
            logging.info("Waiting for remote push operations")
        while not dsg_link.is_shutdown():
            dsg_link.handle_one_update()

    # Done...
    if loggingEnabled:
        logging.info("Shutting down DSG connection")
    dsg_link.end()

    # Add a material to the box
    # target.createMaterial(boxMesh)

    # Add a Nucleus Checkpoint to the stage
    # target.checkpoint("Add material to the box")

    target.shutdown()
