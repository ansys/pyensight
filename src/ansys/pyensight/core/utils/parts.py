"""Parts module.

This module allows PyEnSight to control the parts in the EnSight session.

Example for selecting all 3D parts:

(PyEnSight)
>>> from ansys.pyensight.core import LocalLauncher
>>> session = LocalLauncher().start()
>>> parts = session.ensight.utils.parts
>>> parts.select_by_dimension(3)

(EnSight)
>>> from ensight.utils import parts
>>> parts.select_by_dimension(3)

"""
from types import ModuleType
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

try:
    import ensight
    from ensight.objs import ens_emitterobj, ensobjlist  # type: ignore
except ImportError:
    from ansys.api.pyensight.ens_emitterobj import ens_emitterobj
    from ansys.pyensight.core.listobj import ensobjlist

if TYPE_CHECKING:
    try:
        from ensight.objs import ENS_PART, ENS_VAR  # type: ignore
    except ImportError:
        from ansys.api.pyensight import ensight_api
        from ansys.api.pyensight.ens_part import ENS_PART
        from ansys.api.pyensight.ens_var import ENS_VAR


def convert_part(
    _ensight: Union["ensight_api.ensight", "ensight"], part: Union[str, int, "ENS_PART"]
):
    if isinstance(part, str):
        return _ensight.objs.core.PARTS[part][0].PARTNUMBER
    elif isinstance(part, int):
        return part
    elif hasattr(part, "PARTNUMBER"):
        return part.PARTNUMBER


def convert_variable(
    _ensight: Union["ensight_api.ensight", "ensight"], var: Union[str, int, "ENS_VAR"]
):
    if isinstance(var, str):
        return _ensight.objs.core.VARIABLES[var][0].ID
    elif isinstance(var, int):
        return var
    elif hasattr(var, "ID"):
        return var.ID


class Parts:
    """Controls the parts in the current EnSight ``Session`` instance."""

    class _EnSEmitterPoint(ens_emitterobj):
        def __init__(
            self,
            ensight: "ensight",
            point1: Optional[List[float]] = [0, 0, 0],
        ):
            if not isinstance(ensight, ModuleType):
                raise RuntimeError(
                    "The class cannot be used directly in PyEnSight. It should not be used directly even in EnSight"
                )
            super().__init__(ensight.objs.EMIT_CURSOR)
            self.ensight = ensight
            self.ensight.view_transf.cursor(*point1)
            self.CENTROID = point1

    class _EnSEmitterGrid(ens_emitterobj):
        def __init__(
            self,
            ensight: "ensight",
            point1: Optional[List[float]] = [0, 0, 0],
            point2: Optional[List[float]] = [0, 0, 0],
            point3: Optional[List[float]] = [0, 0, 0],
            point4: Optional[List[float]] = [0, 0, 0],
            num_points_x: Optional[int] = 25,
            num_points_y: Optional[int] = 25,
        ):
            if not isinstance(ensight, ModuleType):
                raise RuntimeError(
                    "The class cannot be used directly in PyEnSight. It should not be used directly even in EnSight"
                )
            super().__init__(ensight.objs.EMIT_PLANE)
            self.ensight = ensight
            self.ensight.view_transf.plane(1, *point1)
            self.ensight.view_transf.plane(2, *point2)
            self.ensight.view_transf.plane(3, *point3)
            self.POINT1 = point1
            self.POINT2 = point2
            self.POINT3 = point3
            self.POINT4 = point4
            self.NUM_POINTS_X = num_points_x
            self.NUM_POINTS_Y = num_points_y

    class _EnSEmitterLine(ens_emitterobj):
        def __init__(
            self,
            ensight: "ensight",
            point1: Optional[List[float]] = [0, 0, 0],
            point2: Optional[List[float]] = [0, 0, 0],
            num_points: Optional[int] = 100,
        ):
            if not isinstance(ensight, ModuleType):
                raise RuntimeError(
                    "The class cannot be used directly in PyEnSight. It should not be used directly even in EnSight"
                )
            super().__init__(ensight.objs.EMIT_LINE)
            self.ensight = ensight
            self.ensight.view_transf.line(1, *point1)
            self.ensight.view_transf.line(2, *point2)
            self.POINT1 = point1
            self.POINT2 = point2
            self.NUM_POINTS = num_points

    class _EnSEmitterPart(ens_emitterobj):
        def __init__(
            self,
            ensight: "ensight",
            part: Optional[Any] = None,
            part_kind: Optional[Any] = 0,
            num_points: Optional[int] = 100,
        ):
            if not isinstance(ensight, ModuleType):
                raise RuntimeError(
                    "The class cannot be used directly in PyEnSight. It should not be used directly even in EnSight"
                )
            super().__init__(ensight.objs.EMIT_PART)
            self.ensight = ensight
            if not part:
                raise RuntimeError("part is a required input")
            self.PART = convert_part(self.ensight, part)
            self.NUM_POINTS = num_points
            self.DISTRIB_TYPE = part_kind

    def __init__(self, ensight: Union["ensight_api.ensight", "ensight"]):
        self.ensight = ensight

    def select_parts_by_dimension(self, dimension: int) -> ensobjlist["ENS_PART"]:
        """Select parts by the input dimension and return the parts found.

        Parameters
        ----------
        dimension : int
            Dimension for selecting parts.

        Returns
        -------
        ensobjlist["ENS_PART"]
            found (ensobjlist): List of parts found.

        """
        parts = self.ensight.objs.core.PARTS
        parts.set_attr("SELECTED", False)
        found = parts.find(True, f"HAS{dimension}DELEMENTS")
        found.set_attr("SELECTED", True)
        return found

    def select_parts_invert(self) -> ensobjlist["ENS_PART"]:
        """Select parts currently not selected, deselecting the previously selected parts.

        Returns
        -------
        ensobjlist["ENS_PART"]
            Updated list of parts selected.

        """
        self.ensight.part.select_invert()
        parts = self.ensight.objs.core.PARTS
        return parts.find(True, "SELECTED")

    def select_parts_by_tag(
        self,
        tag: Optional[str] = None,
        value: Optional[str] = None,
        tagdict: Optional[Dict[str, str]] = None,
    ) -> ensobjlist["ENS_PART"]:
        """Select parts by the input dimension and return the parts found.

        Parameters
        ----------
        tag : str, optional
            Tag for finding the parts.
        value : str, optional
            Value for finding the parts.
        tagdict : dict, optional
            Dictionary containing the key and value pairs for finding
            the parts. Only the parts that have all the keys and corresponding
            values are returned. If a value for this parameter is supplied, it
            takes precedence over the valeus supplied for the ``tag`` and
            ``value`` parameters.

        Returns
        -------
        ensobjlist["ENS_PART"]
            List of parts found. If no arguments are given, all parts are returned.

        """
        parts = self.ensight.objs.core.PARTS
        metadata = {p: p.METADATA for p in parts}
        found = ensobjlist()
        if not tag and not value and not tagdict:
            self.ensight.part.select_all()
            return parts
        if not tagdict:
            if tag and value:
                found = ensobjlist([p for p, met in metadata.items() if met.get(tag) == value])
            elif value and not tag:
                found = ensobjlist([p for p, met in metadata.items() if value in met.values()])
            elif tag and not value:
                found = ensobjlist([p for p, met in metadata.items() if tag in met.keys()])
        else:
            found = ensobjlist(
                [
                    p
                    for p, met in metadata.items()
                    if all(met.get(k) == v for k, v in tagdict.items())
                ]
            )
        if found:
            found.set_attr("SELECTED", True)
        return found

    EMIT_POINT: int = 0
    EMIT_LINE: int = 1
    EMIT_PLANE: int = 2
    EMIT_PART: int = 3
    PT_POS_TIME: str = "+"
    PT_NEG_TIME: str = "-"
    PT_POS_NEG_TIME: str = "+/-"
    PART_EMIT_FROM_NODES: int = 0
    PART_EMIT_FROM_AREA: int = 1

    def _create_emitters(
        self,
        emitter_type: int,
        point1: Optional[List[float]] = None,
        point2: Optional[List[float]] = None,
        point3: Optional[List[float]] = None,
        parts: Optional[List[Union[str, int, "ENS_PART"]]] = None,
        part_distribution_type: Optional[int] = 0,
        num_points: Optional[int] = 100,
        num_points_x: Optional[int] = 25,
        num_points_y: Optional[int] = 25,
    ) -> List[Any]:
        """Private routine to create emitter objects"""
        new_emitters: List[Any] = []
        if emitter_type == self.EMIT_POINT:
            if not point1:
                raise RuntimeError("point1 needed if particle trace emitted from point")
            if isinstance(self.ensight, ModuleType):
                new_emitters.append(self._EnSEmitterPoint(self.ensight, point1=point1))
            else:
                new_emitters.append(
                    self.ensight._session.cmd(
                        f"ensight.utils.parts._EnSEmitterPoint(ensight, point1={point1})"
                    )
                )
        elif emitter_type == self.EMIT_LINE:
            if not any([point1, point2]):
                raise RuntimeError("point1 and point2 needed if particle trace emitted from line")
            if isinstance(self.ensight, ModuleType):
                new_emitters.append(
                    self._EnSEmitterLine(
                        self.ensight, point1=point1, point2=point2, num_points=num_points
                    )
                )
            else:
                new_emitters.append(
                    self.ensight._session.cmd(
                        f"ensight.utils.parts._EnSEmitterLine(ensight, point1={point1}, point2={point2}, num_points={num_points})"
                    )
                )
        elif emitter_type == self.EMIT_PLANE:
            if not any([point1, point2, point3]):
                raise RuntimeError(
                    "point1, point2 and point3 needed if particle trace emitted from plane"
                )
            if isinstance(self.ensight, ModuleType):
                new_emitters.append(
                    self._EnSEmitterGrid(
                        self.ensight,
                        point1=point1,
                        point2=point2,
                        point3=point3,
                        num_points_x=num_points_x,
                        num_points_y=num_points_y,
                    )
                )
            else:
                new_emitters.append(
                    f"ensight.utils.parts._EnSEmitterGrid(ensight, point1={point1}, point2={point2}, point3={point3}, num_points_x={num_points_x}, num_points_y={num_points_y})"
                )
        elif emitter_type == self.EMIT_PART:
            if not parts:
                raise RuntimeError("part and num_points needed if particle trace emitted from part")
            for p in parts:
                if isinstance(self.ensight, ModuleType):
                    new_emitters.append(
                        self._EnSEmitterPart(
                            self.ensight,
                            part=p,
                            num_points=num_points,
                            part_kind=part_distribution_type,
                        )
                    )
                else:
                    new_emitters.append(
                        f"ensight.utils.parts._EnSEmitterPart(ensight, part={convert_part(self.ensight ,p)}, num_points={num_points}, part_kind={part_distribution_type})"
                    )
        else:
            raise RuntimeError("No input provided to create the emitters for the particle trace")
        return new_emitters

    def _create_pathline_part(
        self,
        name: str,
        variable: Union[str, int, "ENS_VAR"],
        direction: str,
        source_parts: List[Union[str, int, "ENS_PART"]],
        pathlines: Optional[bool] = False,
        emit_time: Optional[float] = None,
        total_time: Optional[float] = None,
        delta_time: Optional[float] = None,
    ) -> Tuple["ENS_PART", "ENS_PART"]:
        """Private routine to create a pathline part object"""
        direction_map = {
            self.PT_POS_TIME: self.ensight.objs.enums.POS_TIME,
            self.PT_NEG_TIME: self.ensight.objs.enums.NEG_TIME,
            self.PT_POS_NEG_TIME: self.ensight.objs.enums.POS_NEG_TIME,
        }
        converted_source_parts = [convert_part(self.ensight, p) for p in source_parts]
        idx = self.ensight.objs.enums.PART_PARTICLE_TRACE
        def_part = self.ensight.objs.core.DEFAULTPARTS[idx]
        def_part.TYPE = self.ensight.objs.enums.STREAMLINE
        if pathlines is True:
            def_part.TYPE = self.ensight.objs.enums.PATHLINE
        if total_time:
            def_part.TOTALTIME = total_time
        if delta_time:
            def_part.DELTATIME = delta_time
        if emit_time:
            def_part.STARTTIME = emit_time
        def_part.DESCRIPTION = name
        def_part.VARIABLE = convert_variable(self.ensight, variable)
        def_part.SURFACERESTRICTED = False
        def_part.TRACEDIRECTION = direction_map.get(direction)
        pathline_part = def_part.createpart(sources=converted_source_parts, name=name)[0]
        return pathline_part, def_part

    def create_particle_trace(
        self,
        name: str,
        variable: Union[str, int, "ENS_VAR"],
        direction: Optional[str] = None,
        emitter_type: Optional[int] = None,
        pathlines: Optional[bool] = False,
        point1: Optional[List[float]] = None,
        point2: Optional[List[float]] = None,
        point3: Optional[List[float]] = None,
        source_parts: Optional[List[Union[str, int, "ENS_PART"]]] = None,
        parts: Optional[List[Union[str, int, "ENS_PART"]]] = None,
        part_distribution_type: Optional[int] = 0,
        num_points: Optional[int] = 100,
        num_points_x: Optional[int] = 25,
        num_points_y: Optional[int] = 25,
        emit_time: Optional[float] = None,
        total_time: Optional[float] = None,
        delta_time: Optional[float] = None,
    ) -> "ENS_PART":
        """
        Create a particle trace part. The particle trace can be generated after a point, a line,
        a plane or a list of parts depending on the input. Returns the ``ENS_PART`` generated.

        Parameters:
        -----------

        name: str
            The name of part to be generated
        variable:
            The variable to compute the particle traces with.
            It can be the name, the ID or the ``ENS_VAR`` object. It must be a vector variable.
        direction: str
            The direction for the particle traces to be generated.
            This table describes the options:

            ================== ==============================================
            Name               Query type
            ================== ==============================================
            PT_POS_TIME        Follow the vector direction
            PT_NEG_TIME        Go contrary to the vector direction
            PT_POS_NEG_TIME    Follow and go contrary to the vector direction
            ================== ==============================================

            If not provided, it will default to ``PT_POS_TIME``
        emitter_type: int
            The kind of emitter for the particle trace.
            This table describes the options:

            ================== =======================================
            Name               Query type
            ================== =======================================
            EMIT_POINT         Emit the particle traces from a point
            EMIT_LINE          Emit the particle traces from a line
            EMIT_PLANE         Emit the particle traces from a plane
            EMIT_PART          Emit the particle traces from a part
            ================== =======================================

            If not provided, it will default to ``EMIT_POINT``
        pathlines: bool
            True if the particle traces need to be pathlines
        point1: list
            List of coordinates for point 1.
            Needed for ``EMIT_POINT``, ``EMIT_LINE`` and ``EMIT_PLANE``
        point2: list
            List of coordinates for point 2.
            Needed for ``EMIT_LINE`` and ``EMIT_PLANE``
        point3: list
            List of coordinates for point 3.
            Needed for ``EMIT_PLANE``
        source_parts: list
            A list of parts to create the particle trace in. For instance, in a CFD
            simulation this might be the fluid zone.
            If not provided, the function will try to look for the selected parts.
        parts: list
            A list of parts to emit the particle traces from.
            They can be their names, their IDs or the respective ``ENS_PART`` objects.
            Needed for ``EMIT_PART``
        part_distribution_type: int
            The distribution of emitters in case of emission from a part.
            This table describes the options:

            ====================   =================================================
            Name                   Query type
            ====================   =================================================
            PART_EMIT_FROM_NODES   Emit from the nodes of the part
            PART_EMIT_FROM_AREA    Create an area of equidistant points for emission
            ==================     =================================================

            If not provided, it will default to ``PART_EMIT_FROM_NODES``
        num_points: int
            The number of points to emit from. Needed for ``EMIT_LINE`` and ``EMIT_PART``.
            Defaults to 100.
        num_points_x: int
            The number of points on the ``X`` direction of the emission plane.
            Needed for ``EMIT_PLANE``. Defaults to 25.
        num_points_y: int
            The number of points on the ``Y`` direction of the emission plane.
            Needed for ``EMIT_PLANE``. Defaults to 25.
        emit_time: float
            The emission time to start the particle trace from. If not provided,
            it will use the current time.
        total_time: float
            The total emission time. If not provided, EnSight will provide the end time
            for a transient simulation, an internal best time for steady state simulations.
        delta_time: float
            The interval for the emissions. If not provided, EnSight will provide
            a best estimate.
        """
        if not direction:
            direction = self.PT_POS_TIME
        if not emitter_type:
            emitter_type = self.EMIT_POINT
        if not source_parts:
            source_parts = self.ensight.objs.core.selection(self.ensight.objs.ENS_PART)
        if not source_parts:
            raise RuntimeError("No part selected for particle trace generation")
        pathline_part, def_part = self._create_pathline_part(
            name,
            variable,
            direction,
            source_parts,
            pathlines=pathlines,
            emit_time=emit_time,
            delta_time=delta_time,
            total_time=total_time,
        )
        new_emitters = self._create_emitters(
            emitter_type=emitter_type,
            point1=point1,
            point2=point2,
            point3=point3,
            parts=parts,
            part_distribution_type=part_distribution_type,
            num_points=num_points,
            num_points_x=num_points_x,
            num_points_y=num_points_y,
        )
        if isinstance(self.ensight, ModuleType):
            pathline_part.EMITTERS = new_emitters
        else:
            text = f"ensight.objs.wrap_id({pathline_part.objid}).setattr('EMITTERS', ["
            for emitter in new_emitters:
                text += emitter + ", "
            text = text[:-2]
            text += "])"
            self.ensight._session.cmd(text)
        pathline_part.COLORBYPALETTE = def_part.VARIABLE.DESCRIPTION
        return pathline_part

    def add_emitters_to_pathline_part(
        self,
        pathline_part: Union[str, int, "ENS_PART"],
        emitter_type: Optional[int] = None,
        point1: Optional[List[float]] = None,
        point2: Optional[List[float]] = None,
        point3: Optional[List[float]] = None,
        parts: Optional[List[Union[str, int, "ENS_PART"]]] = None,
        part_distribution_type: Optional[int] = 0,
        num_points: Optional[int] = 100,
        num_points_x: Optional[int] = 25,
        num_points_y: Optional[int] = 25,
    ) -> "ENS_PART":
        """
        Add emitters to an existing particle trace. The function will return the updated
        ``ENS_PART`` object. They can be added a point emitter, a line emitter, a plane emitter
        or a list of parts to emit from.

        Parameters:
        -----------

        pathline:
            The particle trace part to be added emitters to.
            Can be the name, the ID or the ``ENS_PART`` object
        emitter_type: int
            The kind of emitter for the particle trace.
            This table describes the options:

            ================== =======================================
            Name               Query type
            ================== =======================================
            EMIT_POINT         Emit the particle traces from a point
            EMIT_LINE          Emit the particle traces from a line
            EMIT_PLANE         Emit the particle traces from a plane
            EMIT_PART          Emit the particle traces from a part
            ================== =======================================

            If not provided, it will default to ``EMIT_POINT``
        point1: list
            List of coordinates for point 1.
            Needed for ``EMIT_POINT``, ``EMIT_LINE`` and ``EMIT_PLANE``
        point2: list
            List of coordinates for point 2.
            Needed for ``EMIT_LINE`` and ``EMIT_PLANE``
        point3: list
            List of coordinates for point 3.
            Needed for ``EMIT_PLANE``
        parts: list
            A list of parts to emit the particle traces from.
            They can be their names, their IDs or the respective ``ENS_PART`` objects.
            Needed for ``EMIT_PART``
        part_distribution_type: int
            The distribution of emitters in case of emission from a part.
            This table describes the options:

            ====================   =================================================
            Name                   Query type
            ====================   =================================================
            PART_EMIT_FROM_NODES   Emit from the nodes of the part
            PART_EMIT_FROM_AREA    Create an area of equidistant points for emission
            ==================     =================================================

            If not provided, it will default to ``PART_EMIT_FROM_NODES``
        num_points: int
            The number of points to emit from. Needed for ``EMIT_LINE`` and ``EMIT_PART``.
            Defaults to 100.
        num_points_x: int
            The number of points on the ``X`` direction of the emission plane.
            Needed for ``EMIT_PLANE``. Defaults to 25.
        num_points_y: int
            The number of points on the ``Y`` direction of the emission plane.
            Needed for ``EMIT_PLANE``. Defaults to 25.
        """
        if not emitter_type:
            emitter_type = self.EMIT_POINT
        if isinstance(pathline_part, (str, int)):
            temp = self.ensight.objs.core.PARTS[pathline_part]
            if not temp:
                raise RuntimeError("pathline_part input is not a valid part")
            pathline_part = temp[0]
        new_emitters = self._create_emitters(
            emitter_type=emitter_type,
            point1=point1,
            point2=point2,
            point3=point3,
            parts=parts,
            part_distribution_type=part_distribution_type,
            num_points=num_points,
            num_points_x=num_points_x,
            num_points_y=num_points_y,
        )
        if isinstance(self.ensight, ModuleType):
            emitters = pathline_part.EMITTERS.copy()
            emitters.extend(new_emitters)
            pathline_part.EMITTERS = emitters
        else:
            self.ensight._session.cmd(
                f"enscl.emitters=ensight.objs.wrap_id({pathline_part.objid}).EMITTERS.copy()",
                do_eval=False,
            )
            text = "enscl.emitters.extend(["
            for emitter in new_emitters:
                text += emitter + ", "
            text = text[:-2]
            text += "])"
            self.ensight._session.cmd(text, do_eval=False)
            self.ensight._session.cmd(
                f"ensight.objs.wrap_id({pathline_part.objid}).setattr('EMITTERS', enscl.emitters.copy())"
            )
            self.ensight._session.cmd("del enscl.emitters", do_eval=False)
