"""views module

The views module allows pyensight to control the view in the EnSight session

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
        from ansys.pyensight.core import ensight_api


class Views:
    """A class to handle the view in the current EnSight session."""

    def __init__(self, ensight: Union["ensight_api.ensight", "ensight"]):
        self.ensight = ensight
        self._views_dict: Dict[str, Tuple[int, List[float]]] = {}

    # Utilities
    @staticmethod
    def _normalize_vector(direction: List[float]) -> List[float]:
        """Return the normalized input (3D) vector.

        Args:
            direction: a list representing the vector to normalize

        Returns:
            (list): a list representing the normalized vector

        """
        magnitude = math.sqrt(sum(v**2 for v in direction))
        if magnitude == 0.0:
            return [0] * len(direction)
        return [x / magnitude for x in direction]

    @staticmethod
    def _cross_product(vec1: List[float], vec2: List[float]) -> List[float]:
        """Return the cross product of the two input vector.

        Args:
            vec1: a list representing the first vector
            vec2: a list representing the second vector

        Returns:
            (list): a list representing the cross product of the two input vectors
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
        The third row of the rotation matrix will be the view direction.
        The first and second rows are computed to be orthogonal to the view direction,
        to form an orthogonal matrix.
        This is because a rotation matrix to get a specific view direction has got
        the third column to be the view direction itself (i.e. the view direction becomes the z
        axis after the rotation, while the transformed x and y axis are computed to be orthogonal to
        the z transformed axis). The rotation is defined as the matrix transpose of the
        defined rotation matrix since the aim is to have the view direction pointing towards the camera
        and not the contrary.

        Args:
            direction (list): a list describing the desired direction view
            up_axis (tuple): a tuple describing the up_direction. The Y axis is assumed by default

        Returns:
            (tuple) a tuple containing the three rows of the rotation matrix
        """
        direction = self._normalize_vector(direction)
        xaxis = self._normalize_vector(self._cross_product(list(up_axis), direction))
        yaxis = self._normalize_vector(self._cross_product(direction, xaxis))
        return (xaxis, yaxis, direction)

    def _convert_view_direction_to_quaternion(
        self, direction: List[float], up_axis: Tuple[float, float, float] = (0.0, 1.0, 0.0)
    ) -> Tuple[float, float, float, float]:
        """Convert the input direction vector into a list of quaternions.

        Args:
            direction (list): a list describing the desired direction view
            up_axis (tuple): a tuple describing the up_direction. The Y axis is assumed by default

        Returns:
            (tuple) a tuple containing the 4 quaternions describing the required rotation
        """
        row0, row1, row2 = self._convert_view_direction_to_rotation_matrix(
            direction=direction,
            up_axis=up_axis,
        )
        return self._convert_rotation_matrix_to_quaternion(row0, row1, row2)

    def _convert_rotation_matrix_to_quaternion(
        self, row0: List[float], row1: List[float], row2: List[float]
    ) -> Tuple[float, float, float, float]:
        """Convert a rotation matrix to quaternions

        Args:
            row0: the first row of the matrix
            row1: the second row of the matrix
            row2: the third row of the matrix

        Returns:
            (tuple): the four quaternions describing the rotation
        """
        trace = row0[0] + row1[1] + row2[2]
        if trace > 0:
            s = math.sqrt(trace + 1)
            print(s)
            qw = s / 2
            s = 1 / (2 * s)
            print(s)
            qx = (row2[1] - row1[2]) * s
            qy = (row0[2] - row2[0]) * s
            qz = (row1[0] - row0[1]) * s
            print(qx, qy, qz, qw)
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
        """Getter for the views_dict dictionary holding the stored views

        Returns:
            (dict): A dictionary containing the stored views

        """
        return self._views_dict

    # Methods
    def set_center_of_transform(self, xc: float, yc: float, zc: float) -> None:
        """Change the center of transform of the current session.

        Args:
            xc (float): x coordinate of the new center of transform
            yc (float): y coordinate of the new center of transform
            zc (float): z coordinate of the new center of transform
        """
        self.ensight.view_transf.center_of_transform(xc, yc, zc)

    def compute_model_centroid(self, vportindex: int = 0) -> List[float]:
        """Computes the model centroid using the model BOUNDS.

        Args:
            vport (int): the viewport to compute the centroid for

        Returns:
            (list): the coordinates of the model centroid
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
        except AttributeError:
            # Old method. It assumes autosize is set to True and
            # that the bounds have not been modified
            enabled = False
            if self.ensight.objs.core.BOUNDS is False:
                enabled = True
                self.ensight.view.bounds("ON")
            xmax = vport.AXISXMAX
            xmin = vport.AXISXMIN
            ymax = vport.AXISYMAX
            ymin = vport.AXISYMIN
            zmax = vport.AXISZMAX
            zmin = vport.AXISZMIN
            if enabled:
                self.ensight.view.bounds("OFF")
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
        """Sets the view direction of the session.
        A name can be given as input to save the new view settings;
        a default incremental name will be given otherwise.
        The perspective can be enabled or disabled, by default it will be disabled.

        Args:
            xdir (float): the x component of the view direction
            ydir (float): the y component of the view direction
            zdir (float): the z component of the view direction
            name (str): the name to give to the new direction
            perspective (bool): Enable the perspective view if True
            up_axis (list): the up direction for the view direction
            vportindex (int): the viewport to set the view direction for
        """
        self.ensight.view.perspective("OFF")
        direction = [xdir, ydir, zdir]
        vport = self.ensight.objs.core.VPORTS[vportindex]
        rots = vport.ROTATION.copy()
        rots[0:4] = self._convert_view_direction_to_quaternion(direction, up_axis=up_axis)
        vport.ROTATION = rots
        if perspective:
            self.ensight.view.perspective("ON")
        self.save_current_view(name=name, vportindex=vportindex)

    def save_current_view(
        self,
        name: Optional[str] = None,
        vportindex: int = 0,
    ) -> None:
        """Save the current view with an optional name.
        If not provided, a default incremental name will be given otherwise

        Args:
            name (str): the name to give to the new direction
            vportindex (int): the viewport to set the view direction for
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
        """Restore a stored view by its name.

        Args:
            name (str): the name of the view to restore
        """
        if not self.views_dict.get(name):
            raise KeyError("ERROR: view set not available")
        found = self.views_dict.get(name)
        if found:
            viewport, coretransform = found
            vport = self.ensight.objs.core.VPORTS[viewport]
            vport.CORETRANSFORM = coretransform

    def restore_center_of_transform(self) -> None:
        """Restore the center of transform to the model centroid."""
        original_model_centroid = self.compute_model_centroid()
        self.set_center_of_transform(*original_model_centroid)

    def reinitialize_view(self) -> None:
        """Reset the view."""
        self.ensight.view_transf.initialize_viewports()
