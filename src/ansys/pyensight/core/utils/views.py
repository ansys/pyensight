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
            self._original_parallel_scale,
        ) = self.compute_camera_from_ensight_opengl()
        self.ensight.annotation.axis_global("off")
        self.ensight.annotation.axis_local("off")
        self.ensight.annotation.axis_model("off")

    def get_center_of_rotation(self):
        """Get EnSight center of rotation."""
        return self.ensight.objs.core.VPORTS[0].TRANSFORMCENTER

    def auto_scale(self):
        """Auto scale view."""
        self.ensight.view_transf.function("global")
        self.ensight.view_transf.fit()
        self._initialize_simba_view()
        self.render()
        return self.get_camera()

    def set_view(self, value: str):
        """Set the view."""
        self.ensight.view_transf.function("global")
        if value != "isometric":
            new_value = value[1].upper() + value[0]
            self.ensight.view_transf.view_recall(new_value)
        else:
            self.views.set_view_direction(
                1, 1, 1, perspective=self.ensight.objs.core.vports[0].PERSPECTIVE
            )
        return self.auto_scale()

    def get_camera(self):
        """Get EnSight camera settings in VTK format."""
        vport = self.ensight.objs.core.VPORTS[0]
        position, focal_point, view_up, parallel_scale = self.compute_camera_from_ensight_opengl()
        vport = self.ensight.objs.core.VPORTS[0]
        view_angle = 2 * vport.PERSPECTIVEANGLE
        # The parameter parallel scale is the actual parallel scale only
        # if the vport is in orthographic mode. If not, it is defined as the
        # inverge of the tangent of half of the field of view
        parallel_scale = parallel_scale
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

    def compute_camera_from_ensight_opengl(self):
        """Simulate a rotating camera using the current quaternion."""
        if isinstance(self.ensight, ModuleType):
            data = self.ensight.objs.core.VPORTS[0].simba_camera()
        else:
            data = self.ensight._session.cmd("ensight.objs.core.VPORTS[0].simba_camera())")
        camera_position = [data[0], data[1], data[2]]
        focal_point = [data[3], data[4], data[5]]
        view_up = [data[6], data[7], data[8]]
        parallel_scale = 1 / data[9]
        return camera_position, focal_point, self.views._normalize_vector(view_up), parallel_scale

    def get_camera_axes(self):
        """
        Returns the camera's local axes: right, up, and forward vectors.
        These are useful for applying transformations in view space.

        Parameters:
            camera (dict): A dictionary with keys 'position', 'focal_point', and 'view_up'.

        Returns:
            right (np.ndarray): Right vector (X axis in view space).
            up (np.ndarray): Up vector (Y axis in view space).
        forw    ard (np.ndarray): Forward vector (Z axis in view space, pointing from position to focal point).
        """
        camera = self.get_camera()
        position = np.array(camera["position"])
        focal_point = np.array(camera["focal_point"])
        view_up = np.array(camera["view_up"])

        # Forward vector: from camera position to focal point
        forward = focal_point - position
        forward /= np.linalg.norm(forward)

        # Right vector: cross product of forward and view_up
        right = np.cross(forward, view_up)
        right /= np.linalg.norm(right)

        # Recompute up vector to ensure orthogonality
        up = np.cross(right, forward)
        up /= np.linalg.norm(up)

        return right, up, forward

    def set_camera(
        self,
        orthographic,
        view_up=None,
        position=None,
        focal_point=None,
        view_angle=None,
        pan=None,
        mousex=None,
        mousey=None,
        invert_y=False,
    ):
        """Set the EnSight camera settings from the VTK input."""
        self.ensight.view_transf.function("global")
        perspective = "OFF" if orthographic else "ON"
        if orthographic:
            self.ensight.view.perspective(perspective)
        vport = self.ensight.objs.core.VPORTS[0]
        if view_angle:
            vport.PERSPECTIVEANGLE = view_angle / 2
        if view_up and position and focal_point:
            if not pan:
                q_current = self.normalize(np.array(vport.ROTATION.copy()))
                q_target = self.normalize(
                    self.compute_model_rotation_quaternion(position, focal_point, view_up)
                )
                q_relative = self.quaternion_multiply(
                    q_target, np.array([-q_current[0], -q_current[1], -q_current[2], q_current[3]])
                )
                angles = self.quaternion_to_euler(q_relative)
                self.ensight.view_transf.rotate(*angles)
            else:
                if mousex and mousey:
                    self.screen_to_world(
                        mousex=mousex, mousey=mousey, invert_y=invert_y, set_center=True
                    )
                current_camera = self.get_camera()
                right, up, _ = self.get_camera_axes()
                translation_vector = np.array(position) - np.array(current_camera["position"])
                dx = np.dot(translation_vector, right)
                dy = np.dot(translation_vector, up)
                self.ensight.view_transf.translate(-dx, -dy, 0)

        self.render()

    def set_perspective(self, value):
        self.ensight.view_transf.function("global")
        vport = self.ensight.objs.core.VPORTS[0]
        self.ensight.view.perspective(value)
        vport.PERSPECTIVE = value == "ON"
        self.ensight.view_transf.zoom(1)
        self.ensight.view_transf.rotate(0, 0, 0)
        self.render()
        return self.get_camera()

    def screen_to_world(self, mousex, mousey, invert_y=False, set_center=False):
        mousex = int(mousex)
        mousey = int(mousey)
        if isinstance(self.ensight, ModuleType):
            model_point = self.ensight.objs.core.VPORTS[0].screen_to_coords(
                mousex, mousey, invert_y, set_center
            )
        else:
            model_point = self.ensight._session.cmd(
                f"ensight.objs.core.VPORTS[0].screen_to_coords({mousex}, {mousey}, {invert_y}, {set_center})"
            )
        self.render()
        return {"model_point": model_point, "camera": self.get_camera()}

    def render(self):
        """Force render update in EnSight."""
        self.ensight.view_transf.zoom(1)
        self.ensight.render()
        self.ensight.refresh(1)

    def _probe_setup(self, part_obj, get_probe_data=False):
        self.ensight.query_interact.number_displayed(100)
        self.ensight.query_interact.query("surface")
        self.ensight.query_interact.display_id("OFF")
        self.ensight.query_interact.label_always_on_top("ON")
        self.ensight.query_interact.marker_size_normalized(2)
        if get_probe_data:
            variable_string = """Coordinates 'X' 'Y' 'Z'"""
            variable_list = [variable_string]
            variable_name = part_obj.COLORBYPALETTE
            if variable_name:
                if isinstance(variable_name, str):
                    variable_list.append(variable_name)
                else:
                    if isinstance(variable_name, list):
                        if variable_name[0]:
                            variable_name = variable_name[0].DESCRIPTION
                            variable_list.append(variable_name)
                        else:
                            variable_name = None
            if isinstance(self.ensight, ModuleType):
                self.ensight.query_interact.select_varname_begin(*variable_list)
            else:
                command = "ensight.query_interact.select_varname_begin("
                for var in variable_list:
                    command += var + ","
                command = command[:-1] + ")"
                self.ensight._session.cmd(command)
        self.render()

    def drag_allowed(self, mousex, mousey, invert_y=False, probe=False, get_probe_data=False):
        """Return True if the picked object is allowed dragging in the interactor."""
        mousex = int(mousex)
        mousey = int(mousey)
        if isinstance(self.ensight, ModuleType):
            part_id, tool_id = self.ensight.objs.core.VPORTS[0].simba_what_is_picked(
                mousex, mousey, invert_y
            )
        else:
            part_id, tool_id = self.ensight._session.cmd(
                f"ensight.objs.core.VPORTS[0].simba_what_is_picked({mousex}, {mousey}, {invert_y})"
            )
        coords = [None, None, None]
        if probe:
            screen_to_world = self.screen_to_world(
                mousex=mousex, mousey=mousey, invert_y=invert_y, set_center=False
            )
            coords = screen_to_world["model_point"]
        if tool_id > -1:
            return True, coords[0], coords[1], coords[2], False
        part_types_allowed = [
            self.ensight.objs.enums.PART_CLIP_PLANE,
            self.ensight.objs.enums.PART_ISO_SURFACE,
            self.ensight.objs.enums.PART_CONTOUR,
        ]
        if part_id > -1:
            part_obj = self.ensight.objs.core.PARTS.find(part_id, "PARTNUMBER")[0]
            if probe:
                width, height = tuple(self.ensight.objs.core.WINDOWSIZE)
                if invert_y:
                    mousey = height - mousey
                self.ensight.query_interact.number_displayed(100)
                self.ensight.query_interact.query("surface")
                self.ensight.query_interact.display_id("OFF")
                self.ensight.query_interact.create(mousex / width, mousey / height)
                self._probe_setup(part_obj, get_probe_data=get_probe_data)
            return part_obj.PARTTYPE in part_types_allowed, coords[0], coords[1], coords[2], True
        if (
            get_probe_data and self.ensight.objs.core.PROBES[0].PROBE_DATA
        ):  # In case we have picked a probe point
            for part in self.ensight.objs.core.PARTS:
                self._probe_setup(part, get_probe_data=get_probe_data)
        return False, coords[0], coords[1], coords[2], False


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
