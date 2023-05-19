"""views module

The views module allows pyensight to control the view in the EnSight session

Example to set an isometric view:
    >>> from ansys.pyensight import LocalLauncher
    >>> session = LocalLauncher().start()
    >>> views = session.ensight.utils.views
    >>> views.set_view_direct(1,1,1)
"""

import math
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from ansys.pyensight.session import Session


class Views:
    """A class to handle the view in the current EnSight session."""

    def __init__(self, ensight: "Session.ensight"):
        self.ensight = ensight
        self._views_dict = {}

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
            return [0, 0, 0]
        return [
            direction[0] / magnitude,
            direction[1] / magnitude,
            direction[2] / magnitude,
        ]

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

    def _convert_rotation_vector_to_rotation_matrix(
        self, direction: List[float], up_axis: Tuple[float] = (0, 1, 0)
    ) -> Tuple[List[float]]:
        """Convert the input direction vector in a rotation matrix.
        The third row of the rotation matrix will be the view direction.
        The first and second rows define the rotation with the respect to the
        up axis and the rotated x axis to rotate towards the view direction.
        """
        direction = self._normalize_vector(direction)
        xaxis = self._normalize_vector(self._cross_product(up_axis, direction))
        yaxis = self._normalize_vector(self._cross_product(direction, xaxis))
        # Handle the case where up direction and view direction are parallel
        if xaxis == [0.0, 0.0, 0.0] and yaxis == [0.0, 0.0, 0.0]:
            raise ValueError("Cannot set the up direction and the view direction to be parallel")
        return xaxis, yaxis, direction

    @property
    def views_dict(self) -> Dict[str, List[float]]:
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

    def compute_model_centroid(self, vport: int = 0) -> List[float]:
        """Computes the model centroid using the model BOUNDS.

        Args:
            vport (int): the viewport to compute the centroid for

        Returns:
            (list): the coordinates of the model centroid
        """
        enabled = False
        if self.ensight.objs.core.BOUNDS is False:
            enabled = True
            self.ensight.view.bounds("ON")
        vport = self.ensight.objs.core.VPORTS[vport]
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
        up_axis: Tuple[float] = (0, 1, 0),
        vport: int = 0,
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
            vport (int): the viewport to set the view direction for
        """
        self.ensight.view.perspective("OFF")
        direction = [xdir, ydir, zdir]
        vport = self.ensight.objs.core.VPORTS[vport]
        coretransform = vport.CORETRANSFORM.copy()
        rots = self._convert_rotation_vector_to_rotation_matrix(direction, up_axis=up_axis)
        column1 = [rots[0][0], rots[1][0], rots[2][0], 0]
        column2 = [rots[0][1], rots[1][1], rots[2][1], 0]
        column3 = [rots[0][2], rots[1][2], rots[2][2], 0]
        coretransform[0:4] = column1
        coretransform[4:8] = column2
        coretransform[8:12] = column3
        vport.CORETRANSFORM = coretransform
        if perspective:
            self.ensight.view.perspective("ON")
        if not name:
            count = 0
            while True and count < 100:
                if self.views_dict.get("view_{}".format(count)):
                    count += 1
                else:
                    self.views_dict["view_{}".format(count)] = (vport, coretransform)
                    break
        else:
            self.views_dict[name] = (vport, coretransform)

    def restore_view(self, name: str) -> None:
        """Restore a stored view by its name.

        Args:
            name (str): the name of the view to restore
        """
        if not self.views_dict.get(name):
            print("ERROR: view set not available")
        viewport, coretransform = self.views_dict.get(name)
        vport = self.ensight.objs.core.VPORTS[viewport]
        vport.CORETRANSFORM = coretransform

    def restore_center_of_transform(self) -> None:
        """Restore the center of transform to the model centroid."""
        original_model_centroid = self.compute_model_centroid()
        self.set_center_of_transform(*original_model_centroid)

    def reinitialize_view(self) -> None:
        """Reset the view."""
        self.ensight.view_transf.initialize_viewports()
