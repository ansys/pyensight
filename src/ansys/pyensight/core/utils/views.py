"""Views module.

The Views module allows PyEnSight to control the view in the EnSight session.

Example to set an isometric view:

::
    (PyEnSight)
    from ansys.pyensight.core import LocalLauncher
    session = LocalLauncher().start()
    views = session.ensight.utils.views
    views.set_view_direction(1,1,1)

    (EnSight)
    from ensight.utils import views
    views.set_view_direction(1,1,1)


"""


import math
from types import ModuleType
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

import numpy as np

if TYPE_CHECKING:
    try:
        import ensight
    except ImportError:
        from ansys.api.pyensight import ensight_api


VIEW_DICT = {
    "x+": (1, 0, 0),
    "x-": (-1, 0, 0),
    "y+": (0, 1, 0),
    "y-": (0, -1, 0),
    "z+": (0, 0, 1),
    "z-": (0, 0, -1),
    "isometric": (1, 1, 1),
}


class _Simba:
    """Hidden class to manage the interactor layer in simba"""

    def __init__(self, ensight: Union["ensight_api.ensight", "ensight"], views: "Views"):
        self.ensight = ensight
        self.views = views
        self._original_look_at = None
        self._original_look_from = None
        self._original_parallel_scale = None
        self._original_view_angle = None
        self._original_view_up = None

    def _initialize_simba_view(self):
        """Initialize the data for resetting the camera."""
        vport = self.ensight.objs.core.VPORTS[0]
        near_clip = vport.ZCLIPLIMITS[0]
        view_angle = 2 * vport.PERSPECTIVEANGLE
        self._original_parallel_scale = near_clip * math.tan(math.radians(view_angle) / 2)
        self._original_view_angle = view_angle
        (
            self._original_look_from,
            self._original_look_at,
            self._original_view_up,
        ) = self.compute_camera_from_model_quaternion()

    def get_center_of_rotation(self):
        """Get EnSight center of rotation."""
        return self.ensight.objs.core.VPORTS[0].TRANSFORMCENTER

    def auto_scale(self):
        """Auto scale view."""
        self.ensight.view_transf.fit()
        self._initialize_simba_view()
        self.render()
        return self.get_camera()

    def set_perspective(self, value):
        """Set perspective or ortographic."""
        val = "OFF" if not value else "ON"
        self.ensight.view.perspective(val)
        self.ensight.objs.core.VPORTS[0].PERSPECTIVE = val == "ON"

    def set_view(self, value: str):
        """Set the view."""
        if value != "isometric":
            new_value = value[1].upper() + value[0]
            self.ensight.view_transf.view_recall(new_value)
        else:
            self.views.set_view_direction(
                1, 1, 1, perspective=self.ensight.objs.core.vports[0].PERSPECTIVE
            )
        self.auto_scale()
        return self.get_camera()

    def get_plane_clip(self):
        """Get the depth of the current focal point."""
        vport = self.ensight.objs.core.VPORTS[0]
        focal_point = self.compute_camera_from_model_quaternion()[1]
        plane_clip = (focal_point[2] - vport.ZCLIPLIMITS[0]) / vport.ZCLIPLIMITS[
            1
        ] - vport.ZCLIPLIMITS[0]
        return plane_clip

    def get_camera(self):
        """Get EnSight camera settings in VTK format."""
        vport = self.ensight.objs.core.VPORTS[0]
        position, focal_point, view_up = self.compute_camera_from_model_quaternion()
        near_clip = vport.ZCLIPLIMITS[0]
        vport = self.ensight.objs.core.VPORTS[0]
        view_angle = 2 * vport.PERSPECTIVEANGLE
        parallel_scale = near_clip * math.tan(math.radians(view_angle) / 2)
        return {
            "orthographic": not vport.PERSPECTIVE,
            "view_up": view_up,
            "position": position,
            "focal_point": focal_point,
            "view_angle": view_angle,
            "parallel_scale": parallel_scale,
            "reset_focal_point": self._original_look_at,
            "reset_position": self._original_look_from,
            "reset_parallel_scale": self._original_parallel_scale,
            "reset_view_up": self._original_view_up,
            "reset_view_angle": self._original_view_angle,
        }

    @staticmethod
    def normalize(v):
        """Normalize a numpy vector."""
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else v

    @staticmethod
    def rotation_matrix_to_quaternion(m):
        """Convert a numpy rotation matrix to a quaternion."""
        trace = np.trace(m)
        if trace > 0:
            s = 0.5 / np.sqrt(trace + 1.0)
            w = 0.25 / s
            x = (m[2, 1] - m[1, 2]) * s
            y = (m[0, 2] - m[2, 0]) * s
            z = (m[1, 0] - m[0, 1]) * s
        else:
            if m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
                s = 2.0 * np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2])
                w = (m[2, 1] - m[1, 2]) / s
                x = 0.25 * s
                y = (m[0, 1] + m[1, 0]) / s
                z = (m[0, 2] + m[2, 0]) / s
            elif m[1, 1] > m[2, 2]:
                s = 2.0 * np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2])
                w = (m[0, 2] - m[2, 0]) / s
                x = (m[0, 1] + m[1, 0]) / s
                y = 0.25 * s
                z = (m[1, 2] + m[2, 1]) / s
            else:
                s = 2.0 * np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1])
                w = (m[1, 0] - m[0, 1]) / s
                x = (m[0, 2] + m[2, 0]) / s
                y = (m[1, 2] + m[2, 1]) / s
                z = 0.25 * s
        return np.array([x, y, z, w])

    def compute_model_rotation_quaternion(self, camera_position, focal_point, view_up):
        """Compute the quaternion from the input camera."""
        forward = self.normalize(np.array(focal_point) - np.array(camera_position))
        right = self.normalize(np.cross(forward, view_up))
        true_up = np.cross(right, forward)
        camera_rotation = np.vstack([right, true_up, -forward]).T
        model_rotation = camera_rotation.T
        quat = self.rotation_matrix_to_quaternion(model_rotation)
        return quat

    @staticmethod
    def quaternion_multiply(q1, q2):
        x1, y1, z1, w1 = q1
        x2, y2, z2, w2 = q2
        w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
        x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
        y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
        z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
        return np.array([x, y, z, w])

    def quaternion_to_euler(self, q):
        q = self.normalize(q)
        x, y, z, w = q
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = np.arctan2(sinr_cosp, cosr_cosp)

        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = np.pi / 2 * np.sign(sinp)
        else:
            pitch = np.arcsin(sinp)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = np.arctan2(siny_cosp, cosy_cosp)

        return np.degrees([roll, pitch, yaw])

    def compute_camera_from_model_quaternion(self):
        """Simulate a rotating camera using the current quaternion."""
        if isinstance(self.ensight, ModuleType):
            data = self.ensight.objs.core.VPORTS[0].simba_camera()
        else:
            data = self.ensight._session.cmd("ensight.objs.core.VPORTS[0].simba_camera())")
        camera_position = [data[0], data[1], data[2]]
        focal_point = [data[3], data[4], data[5]]
        view_up = [data[6], data[7], data[8]]
        return camera_position, focal_point, self.views._normalize_vector(view_up)

    def set_camera(
        self,
        orthographic,
        view_up=None,
        position=None,
        focal_point=None,
        view_angle=None,
        parallel_scale=None,
    ):
        """Set the EnSight camera settings from the VTK input."""
        perspective = "OFF" if orthographic else "ON"
        if orthographic:
            self.ensight.view.perspective(perspective)
        vport = self.ensight.objs.core.VPORTS[0]
        if view_angle:
            vport.PERSPECTIVEANGLE = view_angle / 2
        if view_up and position and focal_point:
            q_current = self.normalize(np.array(vport.ROTATION.copy()))
            q_target = self.normalize(
                self.compute_model_rotation_quaternion(position, focal_point, view_up)
            )
            q_relative = self.quaternion_multiply(
                q_target, np.array([-q_current[0], -q_current[1], -q_current[2], q_current[3]])
            )
            angles = self.quaternion_to_euler(q_relative)
            self.ensight.view_transf.rotate(*angles)
        if parallel_scale:
            new_znear = parallel_scale / math.tan(math.radians(view_angle / 2))
            self.ensight.view_transf.zclip_front(new_znear)
        self.ensight.render()
        self.ensight.refresh(1)

    @staticmethod
    def transform_coretransform_to_threejs(model_point, coretransform):
        """Transforms a model-space point using the vport coretransform."""
        coretransform = np.array(coretransform, dtype=np.float64)
        model_point = np.array(list(model_point) + [1.0])
        rotation_matrix = coretransform[0:16].reshape((4, 4))
        translation_matrix = coretransform[16:32].reshape((4, 4))
        scale_matrix = coretransform[32:48].reshape((4, 4))

        model_matrix = translation_matrix.T @ rotation_matrix.T @ scale_matrix.T
        world_point = model_matrix @ model_point
        if world_point[3] != 1.0:
            world_point[0] /= world_point[3]
            world_point[1] /= world_point[3]
            world_point[2] /= world_point[3]
        world_point = world_point[:3]

        return world_point

    @staticmethod
    def transform_coretransform_to_threejs_inverse(model_point, coretransform):
        """Transforms a model-space point using the vport coretransform."""
        coretransform = np.array(coretransform, dtype=np.float64)
        model_point = np.array(list(model_point) + [1.0])
        rotation_matrix = coretransform[0:16].reshape((4, 4))
        translation_matrix = coretransform[16:32].reshape((4, 4))
        scale_matrix = coretransform[32:48].reshape((4, 4))

        model_matrix = translation_matrix.T @ rotation_matrix.T @ scale_matrix.T
        inverse = np.linalg.inv(model_matrix)
        world_point = inverse @ model_point
        if world_point[3] != 1.0:
            world_point[0] /= world_point[3]
            world_point[1] /= world_point[3]
            world_point[2] /= world_point[3]
        world_point = world_point[:3]

        return world_point

    def _common(self, x, y, depth_ndc, invert_y):
        mousex = int(x)
        mousey = int(y)
        if isinstance(self.ensight, ModuleType):
            model_point = self.ensight.objs.core.VPORTS[0].screen_to_coords(
                mousex, mousey, depth_ndc, invert_y
            )
        else:
            model_point = self.ensight._session.cmd(
                f"ensight.objs.core.VPORTS[0].screen_to_coords({mousex}, {mousey}, {depth_ndc}, {invert_y})"
            )
        self.ensight.tools.cursor("ON")
        self.ensight.view_transf.cursor(*model_point.copy())
        return model_point

    def screen_to_world(self, x, y, depth_ndc, invert_y=False):
        model_point = self._common(x, y, depth_ndc, invert_y)
        self.ensight.view_transf.center_of_transform(*model_point)
        return {"model_point": model_point, "camera": self.get_camera()}

    def screen_to_world2(self, x, y, depth_ndc, invert_y=False):
        vport = self.ensight.objs.core.VPORTS[0]
        model_point = self._common(x, y, depth_ndc, invert_y)
        coretransform = vport.CORETRANSFORM.copy()
        coretransform[48:51] = model_point.copy()
        coretransform[51:54] = model_point.copy()
        vport.CORETRANSFORM = coretransform
        world_point = self.transform_coretransform_to_threejs_inverse(
            model_point, vport.CORETRANSFORM.copy()
        )
        return world_point.tolist()

    def screen_to_world3(self, x, y, invert_y=False):
        position, focal_point, view_up = self.compute_camera_from_model_quaternion()
        width, height = tuple(self.ensight.objs.core.WINDOWSIZE)
        if invert_y:
            y = height - y
        model_point = self._common(x, y, 0, invert_y)
        vport = self.ensight.objs.core.VPORTS[0]
        depth = model_point[2]

        def look_at(eye, center, up):
            f = self.normalize(center - eye)
            s = self.normalize(np.cross(f, up))
            u = np.cross(s, f)
            view = np.identity(4)
            view[0, :3] = s
            view[1, :3] = u
            view[2, :3] = -f
            view[:3, 3] = -view[:3, :3] @ eye
            return view

        def perspective(fov_y, aspect, near, far):
            f = 1.0 / np.tan(np.radians(fov_y) / 2)
            proj = np.zeros((4, 4))
            proj[0, 0] = f / aspect
            proj[1, 1] = f
            proj[2, 2] = (far + near) / (near - far)
            proj[2, 3] = (2 * far * near) / (near - far)
            proj[3, 2] = -1.0
            return proj

        eye = np.array(position, dtype=np.float64)
        center = np.array(focal_point, dtype=np.float64)
        up = np.array(view_up, dtype=np.float64)
        aspect = width / height
        view_matrix = look_at(eye, center, up)
        near, far = tuple(vport.ZCLIPLIMITS.copy())
        projection_matrix = perspective(vport.PERSPECTIVEANGLE * 2, aspect, near, far)
        inv_proj_view = np.linalg.inv(projection_matrix @ view_matrix)
        x_ndc = (2.0 * x) / width - 1.0
        y_ndc = 1.0 - (2.0 * y) / height  # flip Y
        z_ndc = depth

        ndc = np.array([x_ndc, y_ndc, z_ndc, 1.0])
        world = inv_proj_view @ ndc
        world /= world[3]

        return world[:3]

    def render(self):
        self.ensight.render()
        self.ensight.refresh(1)


class Views:
    """Controls the view in the current EnSight ``Session`` instance."""

    def __init__(self, ensight: Union["ensight_api.ensight", "ensight"]):
        self.ensight = ensight
        self._views_dict: Dict[str, Tuple[int, List[float]]] = {}
        self._simba = _Simba(ensight, self)

    @staticmethod
    def _normalize_vector(direction: List[float]) -> List[float]:
        """Return the normalized input (3D) vector.

        Parameters
        ----------
        direction : list[float]
            List representing the vector to normalize.

        Returns
        -------
        list[float]
            List representing the normalized vector.

        """
        magnitude = math.sqrt(sum(v**2 for v in direction))
        if magnitude == 0.0:
            return [0] * len(direction)
        return [x / magnitude for x in direction]

    @staticmethod
    def _cross_product(vec1: List[float], vec2: List[float]) -> List[float]:
        """Get the cross product of two input vectors.

        Parameters
        ----------
        vec1 : list[float]
            List representing the first vector.
        vec2 : list[float]
            List representing the second vector.

        Returns
        -------
        list[float]
            List representing the cross product of the two input vectors.

        """
        return [
            vec1[1] * vec2[2] - vec1[2] * vec2[1],
            vec1[2] * vec2[0] - vec1[0] * vec2[2],
            vec1[0] * vec2[1] - vec1[1] * vec2[0],
        ]

    def _convert_view_direction_to_rotation_matrix(
        self, direction: List[float], up_axis: Tuple[float, float, float] = (0.0, 1.0, 0.0)
    ) -> Tuple[List[float], List[float], List[float]]:
        """Convert the input direction vector in a rotation matrix.

        The third row of the rotation matrix is the view direction.

        The first and second rows are computed to be orthogonal to the view direction,
        forming an orthogonal matrix. To get a specific view direction, a rotation matrix has
        the third column, which is the view direction itself (that is the view direction becomes the z
        axis after the rotation, while the transformed x and y axis are computed to be orthogonal to
        the z transformed axis). The rotation is defined as the matrix transpose of the
        defined rotation matrix because the aim is to have the view direction pointing towards the camera
        and not the contrary.

        Parameters
        ----------
        direction : list[float]
            List describing the desired direction view
        up_axis : tuple[float, float, float], optional
            Tuple describing the up direction. The default is ``(0.0, 1.0, 0.0)``,
            which assumes the Y axis.

        Returns
        -------
        tuple
            Tuple containing the three rows of the rotation matrix.

        """
        direction = self._normalize_vector(direction)
        xaxis = self._normalize_vector(self._cross_product(list(up_axis), direction))
        yaxis = self._normalize_vector(self._cross_product(direction, xaxis))
        return (xaxis, yaxis, direction)

    def _convert_view_direction_to_quaternion(
        self, direction: List[float], up_axis: Tuple[float, float, float] = (0.0, 1.0, 0.0)
    ) -> Tuple[float, float, float, float]:
        """Convert the input direction vector into a list of quaternions.

        Parameters
        ----------
        direction : list
            List describing the desired direction view.
        up_axis : tuple
            Tuple describing the up direction. The default is ``(0.0, 1.0, 0.0)``,
            which assumes the Y axis.

        Returns
        -------
        tuple
            Tuple containing the four quaternions describing the required rotation.

        """
        row0, row1, row2 = self._convert_view_direction_to_rotation_matrix(
            direction=direction,
            up_axis=up_axis,
        )
        return self._convert_rotation_matrix_to_quaternion(row0, row1, row2)

    def _convert_rotation_matrix_to_quaternion(
        self, row0: List[float], row1: List[float], row2: List[float]
    ) -> Tuple[float, float, float, float]:
        """Convert a rotation matrix to quaternions.

        Parameters
        ----------
        row0 : list[float]
            First row of the matrix.
        row1 : list[float]
            Second row of the matrix.
        row2 : list[float]
            Third row of the matrix.

        Returns
        -------
        tuple
            Four quaternions describing the rotation.

        """
        trace = row0[0] + row1[1] + row2[2]
        if trace > 0:
            s = math.sqrt(trace + 1)
            qw = s / 2
            s = 1 / (2 * s)
            qx = (row2[1] - row1[2]) * s
            qy = (row0[2] - row2[0]) * s
            qz = (row1[0] - row0[1]) * s
        elif row0[0] > row1[1] and row0[0] > row2[2]:
            s = math.sqrt(1 + row0[0] - row1[1] - row2[2])
            qx = s / 2
            s = 1 / (2 * s)
            qw = (row2[1] - row1[2]) * s
            qy = (row0[1] + row1[0]) * s
            qz = (row0[2] + row2[0]) * s
        elif row1[1] > row2[2]:
            s = math.sqrt(1 + row1[1] - row0[0] - row2[2])
            qy = s / 2
            s = 1 / (2 * s)
            qw = (row0[2] - row2[0]) * s
            qx = (row0[1] + row1[0]) * s
            qz = (row1[2] + row2[1]) * s
        else:
            s = math.sqrt(1 + row2[2] - row0[0] - row1[1])
            qz = s / 2
            if s != 0.0:
                s = 1 / (2 * s)
            qw = (row1[0] - row0[1]) * s
            qx = (row0[2] + row2[0]) * s
            qy = (row1[2] + row2[1]) * s
        list_of_quats = self._normalize_vector([qx, qy, qz, qw])
        return list_of_quats[0], list_of_quats[1], list_of_quats[2], list_of_quats[3]

    @property
    def views_dict(self) -> Dict[str, Tuple[int, List[float]]]:
        """Dictionary holding the stored views.

        Returns
        -------
        dict
            Dictionary containing the stored views.

        """
        return self._views_dict

    # Methods
    def set_center_of_transform(self, xc: float, yc: float, zc: float) -> None:
        """Change the center of transform of the current session.

        Parameters
        ----------
        xc : float
            x coordinate of the new center of the transform.
        yc : float
            y coordinate of the new center of the transform.
        zc : float
            z coordinate of the new center of the transform.

        """
        self.ensight.view_transf.center_of_transform(xc, yc, zc)

    def compute_model_centroid(self, vportindex: int = 0) -> List[float]:
        """Compute the model centroid using the model bounds.

        Parameters
        ----------
        vportindex : int, optional
            Viewport to compute the centroid for. The default is ``0``.

        Returns
        -------
        list
            Coordinates of the model centroid.

        """
        vport = self.ensight.objs.core.VPORTS[vportindex]
        try:
            # Available from release 24.1. The order is:
            # xmin,ymin,zmin,xmax,ymax,zmax
            bounds = vport.BOUNDINGBOX
            xmax = bounds[3]
            xmin = bounds[0]
            ymax = bounds[4]
            ymin = bounds[1]
            zmax = bounds[5]
            zmin = bounds[2]
        except AttributeError:  # pragma: no cover
            # Old method. It assumes autosize is set to True and
            # that the bounds have not been modified
            enabled = False  # pragma: no cover
            if self.ensight.objs.core.BOUNDS is False:  # pragma: no cover
                enabled = True  # pragma: no cover
                self.ensight.view.bounds("ON")  # pragma: no cover
            xmax = vport.AXISXMAX  # pragma: no cover
            xmin = vport.AXISXMIN  # pragma: no cover
            ymax = vport.AXISYMAX  # pragma: no cover
            ymin = vport.AXISYMIN  # pragma: no cover
            zmax = vport.AXISZMAX  # pragma: no cover
            zmin = vport.AXISZMIN  # pragma: no cover
            if enabled:  # pragma: no cover
                self.ensight.view.bounds("OFF")  # pragma: no cover
        xavg = (xmax + xmin) / 2
        yavg = (ymax + ymin) / 2
        zavg = (zmax + zmin) / 2
        values = [xavg, yavg, zavg]
        return values

    def set_view_direction(
        self,
        xdir: float,
        ydir: float,
        zdir: float,
        name: Optional[str] = None,
        perspective: Optional[bool] = False,
        up_axis: Tuple[float, float, float] = (0.0, 1.0, 0.0),
        vportindex: int = 0,
    ) -> None:
        """Set the view direction of the session.

        Parameters
        ----------
        xdir : float
            x component of the view direction.
        ydir : float
            y component of the view direction.
        zdir : float
            z component of the view direction.
        name : str, optional
            Name for the new view settings. The default is ``None``,
            in which case an incremental name is automatically assigned.
        perspective : bool, optional
            Whether to enable the perspective view. The default is ``False``.
        up_axis : tuple[float, float, float], optional
            Up direction for the view direction. The default is ``(0.0, 1.0, 0.0)``.
        vportindex : int, optional
            Viewport to set the view direction for. The default is ``0``.
        """
        vport = self.ensight.objs.core.VPORTS[vportindex]
        if not perspective:
            self.ensight.view.perspective("OFF")
            vport.PERSPECTIVE = False
        direction = [xdir, ydir, zdir]
        rots = vport.ROTATION.copy()
        rots[0:4] = self._convert_view_direction_to_quaternion(direction, up_axis=up_axis)
        vport.ROTATION = rots
        if perspective:
            self.ensight.view.perspective("ON")
            vport.PERSPECTIVE = True
        self.save_current_view(name=name, vportindex=vportindex)

    def save_current_view(
        self,
        name: Optional[str] = None,
        vportindex: int = 0,
    ) -> None:
        """Save the current view.

        Parameters
        ----------
        name : str, optional
            Name to give to the new view. The default is ``None``,
            in which case an incremental name is automatically assigned.
        vportindex : int, optional
            Viewport to set the view direction for. The default is ``0``.
        """
        vport = self.ensight.objs.core.VPORTS[vportindex]
        coretransform = vport.CORETRANSFORM
        if not name:
            count = 0
            while True and count < 100:
                if self.views_dict.get("view_{}".format(count)):
                    count += 1
                else:
                    self.views_dict["view_{}".format(count)] = (vportindex, coretransform)
                    break
        else:
            self.views_dict[name] = (vportindex, coretransform)

    def restore_view(self, name: str) -> None:
        """Restore a stored view.

        Parameters
        ----------
        name : str
            Name of the view to restore.

        """
        if not self.views_dict.get(name):
            raise KeyError("ERROR: view set not available")
        found = self.views_dict.get(name)
        if found:  # pragma: no cover
            viewport, coretransform = found
            vport = self.ensight.objs.core.VPORTS[viewport]
            vport.CORETRANSFORM = coretransform

    def restore_center_of_transform(self) -> None:
        """Restore the center of the transform to the model centroid."""
        original_model_centroid = self.compute_model_centroid()
        self.set_center_of_transform(*original_model_centroid)

    def reinitialize_view(self) -> None:
        """Reset the view."""
        self.ensight.view_transf.initialize_viewports()
