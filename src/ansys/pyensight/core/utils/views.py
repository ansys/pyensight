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
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

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

DEF_CAMERA = "C0: -Z View"


class Views:
    """Controls the view in the current EnSight ``Session`` instance."""

    def __init__(self, ensight: Union["ensight_api.ensight", "ensight"]):
        self.ensight = ensight
        self._views_dict: Dict[str, Tuple[int, List[float]]] = {}
        self._original_look_at = None
        self._original_look_from = None
        self._original_parallel_scale = None
        self._original_view_angle = None
        self._original_view_up = None

    def _initialize_simba_view(self):
        vport = self.ensight.objs.core.VPORTS[0]
        self._original_look_at = vport.LOOKATPOINT
        self._original_look_from = vport.LOOKFROMPOINT
        near_clip = vport.ZCLIPLIMITS[0]
        view_angle = 2 * vport.PERSPECTIVEANGLE
        self._original_parallel_scale = near_clip * math.tan(math.radians(view_angle) / 2)
        self._original_view_angle = view_angle
        self._original_view_up = self._get_view_up_from_quaternion(vport.ROTATION)

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

    def get_center_of_rotation(self):
        """Get EnSight center of rotation."""
        self.ensight.objs.core.VPORTS[0].TRANSFORMCENTER

    def auto_scale(self):
        """Auto scale view."""
        vport = self.ensight.objs.core.VPORTS[0]
        bounds = vport.BOUNDINGBOX
        xmax = bounds[3]
        xmin = bounds[0]
        ymax = bounds[4]
        ymin = bounds[1]
        zmax = bounds[5]
        zmin = bounds[2]
        low_left = [xmin, ymin, zmin]
        up_right = [xmax, ymax, zmax]
        dif_vec = [up_right[i] - low_left[i] for i in range(3)]
        win_max = max(dif_vec)
        look_at = [low_left[i] + dif_vec[i] * 0.5 for i in range(3)]
        zdist = 3 * win_max / math.cos(math.radians(vport.PERSPECTIVEANGLE))
        look_from = [look_at[0], look_at[1], look_at[2] + zdist]
        near_clip = vport.ZCLIPLIMITS[0]
        vport = self.ensight.objs.core.VPORTS[0]
        view_angle = 2 * vport.PERSPECTIVEANGLE
        parallel_scale = near_clip * math.tan(math.radians(view_angle) / 2)
        self.set_camera(
            not vport.PERSPECTIVE,
            self._get_view_up_from_quaternion(vport.ROTATION),
            look_from,
            look_at,
            view_angle,
            parallel_scale,
        )
        # self.ensight.view_transf.center_of_transform(*look_from)
        # self.ensight.view_transf.fit(0)
        self._initialize_simba_view()
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
            self.set_view_direction(
                1, 1, 1, perspective=self.ensight.objs.core.vports[0].PERSPECTIVE
            )
        self.auto_scale()
        return self.get_camera()

    def _get_view_direction_from_quaternion(self, quaternion):
        """Convert quaternion to view direction vector."""
        x, y, z, w = quaternion
        view_direction = [2 * x * z - 2 * y * w, 2 * y * z + 2 * x * w, 1 - 2 * x**2 - 2 * y**2]
        return self._normalize_vector(view_direction)

    def _get_view_up_from_quaternion(self, quaternion):
        """Convert quaternion to view up vector."""
        x, y, z, w = quaternion
        view_up = [2 * x * y + 2 * z * w, 1 - 2 * x**2 - 2 * z**2, 2 * y * z - 2 * x * w]
        return self._normalize_vector(view_up)

    @staticmethod
    def _get_view_up_vtk_style(view_direction):
        world_up = [0, 1, 0]
        dot = sum(a * b for a, b in zip(view_direction, world_up))
        if abs(dot) > 0.999:
            return [0, 0, 1]
        return world_up

    def get_plane_clip(self):
        vport = self.ensight.objs.core.VPORTS[0]
        focal_point = vport.LOOKATPOINT
        mid_point = (vport.ZCLIPLIMITS[1] - vport.ZCLIPLIMITS[0]) / 2
        plane_clip = (focal_point[2] - mid_point) / abs(vport.ZCLIPLIMITS[0] - vport.ZCLIPLIMITS[1])
        return plane_clip

    def get_camera(self):
        """Get EnSight camera settings in VTK format."""
        vport = self.ensight.objs.core.VPORTS[0]
        position = vport.LOOKFROMPOINT
        focal_point = vport.LOOKATPOINT
        view_up = self._get_view_up_from_quaternion(vport.ROTATION)
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
        if view_up:
            view_dir_list = self._get_view_direction_from_quaternion(vport.ROTATION.copy())
            direction = self._normalize_vector([*view_dir_list])
            dot = abs(sum([view_up[i] * direction[i] for i in range(3)]))
            if dot > 0.999:
                view_up = [0, 1, 0] if abs(direction[1]) < 0.99 else [1, 0, 0]
            right = self._cross_product(direction, view_up)
            view_dir = self._normalize_vector(self._cross_product(view_up, right))
            self.set_view_direction(*view_dir, perspective=not orthographic)
        if focal_point:
            self.ensight.view_transf.look_at(*focal_point)
        if position:
            self.ensight.view_transf.look_from(*position)
        if parallel_scale:
            old_limits = vport.ZCLIPLIMITS.copy()
            new_znear = parallel_scale / math.tan(math.radians(vport.PERSPECTIVEANGLE))
            self.ensight.view_transf.zclip_float("OFF")
            self.ensight.view_transf.zclip_front(new_znear)
            self.ensight.view_transf.zclip_back(old_limits[1])
            self.ensight.view_transf.zclip_float("ON")
