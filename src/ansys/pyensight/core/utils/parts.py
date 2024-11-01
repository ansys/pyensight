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
    from ansys.api.pyensight import ensight_api
    from ansys.api.pyensight.ens_part import ENS_PART
    from ansys.api.pyensight.ens_part_particle_trace import ENS_PART_PARTICLE_TRACE
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
) -> Optional[int]:
    if isinstance(var, str):
        return int(_ensight.objs.core.VARIABLES[var][0].ID)
    elif isinstance(var, int):
        return var
    elif hasattr(var, "ID"):
        return int(var.ID)
    return None  # pragma: no cover


class Parts:
    """Controls the parts in the current EnSight ``Session`` instance."""

    class _EnSEmitterPoint(ens_emitterobj):  # pragma: no cover
        def __init__(  # pragma: no cover
            self,
            ensight: "ensight",
            point1: Optional[List[float]] = [0, 0, 0],
        ):  # pragma: no cover
            if not isinstance(ensight, ModuleType):
                raise RuntimeError(
                    "The class cannot be used directly in PyEnSight. It should not be used directly even in EnSight"
                )
            super().__init__(ensight.objs.EMIT_CURSOR)
            self.ensight = ensight
            self.ensight.view_transf.cursor(*point1)
            self.CENTROID = point1

    class _EnSEmitterGrid(ens_emitterobj):  # pragma: no cover
        def __init__(  # pragma: no cover
            self,
            ensight: "ensight",
            point1: Optional[List[float]] = [0, 0, 0],
            point2: Optional[List[float]] = [0, 0, 0],
            point3: Optional[List[float]] = [0, 0, 0],
            point4: Optional[List[float]] = [0, 0, 0],
            num_points_x: Optional[int] = 25,
            num_points_y: Optional[int] = 25,
        ):  # pragma: no cover
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

    class _EnSEmitterLine(ens_emitterobj):  # pragma: no cover
        def __init__(  # pragma: no cover
            self,
            ensight: "ensight",
            point1: Optional[List[float]] = [0, 0, 0],
            point2: Optional[List[float]] = [0, 0, 0],
            num_points: Optional[int] = 100,
        ):  # pragma: no cover
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

    class _EnSEmitterPart(ens_emitterobj):  # pragma: no cover
        def __init__(  # pragma: no cover
            self,
            ensight: "ensight",
            part: Optional[Any] = None,
            part_kind: Optional[Any] = 0,
            num_points: Optional[int] = 100,
        ):  # pragma: no cover
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
            takes precedence over the values supplied for the ``tag`` and
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
            elif tag and not value:  # pragma: no cover
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

    _EMIT_POINT: int = 0
    _EMIT_LINE: int = 1
    _EMIT_PLANE: int = 2
    _EMIT_PART: int = 3
    PT_POS_TIME: str = "+"
    PT_NEG_TIME: str = "-"
    PT_POS_NEG_TIME: str = "+/-"
    PART_EMIT_FROM_NODES: int = 0
    PART_EMIT_FROM_AREA: int = 1

    def _create_emitters(
        self,
        emitter_type: int,
        points: Optional[List[List[float]]] = None,
        point1: Optional[List[float]] = None,
        point2: Optional[List[float]] = None,
        point3: Optional[List[float]] = None,
        parts: Optional[List["ENS_PART"]] = None,
        part_distribution_type: Optional[int] = 0,
        num_points: Optional[int] = 100,
        num_points_x: Optional[int] = 25,
        num_points_y: Optional[int] = 25,
    ) -> List[Any]:
        """Private routine to create emitter objects"""
        new_emitters: List[Any] = []
        if emitter_type == self._EMIT_POINT:
            if not points:  # pragma: no cover
                raise RuntimeError(
                    "list of points needed if particle trace emitted from points"
                )  # pragma: no cover
            for p in points:
                if isinstance(self.ensight, ModuleType):  # pragma: no cover
                    new_emitters.append(
                        self._EnSEmitterPoint(self.ensight, point1=p)
                    )  # pragma: no cover
                else:
                    new_emitters.append(
                        f"ensight.utils.parts._EnSEmitterPoint(ensight, point1={p})"
                    )
        elif emitter_type == self._EMIT_LINE:
            if not any([point1, point2]):
                raise RuntimeError("point1 and point2 needed if particle trace emitted from line")
            if isinstance(self.ensight, ModuleType):  # pragma: no cover
                new_emitters.append(  # pragma: no cover
                    self._EnSEmitterLine(
                        self.ensight, point1=point1, point2=point2, num_points=num_points
                    )
                )
            else:
                new_emitters.append(
                    f"ensight.utils.parts._EnSEmitterLine(ensight, point1={point1}, point2={point2}, num_points={num_points})"
                )
        elif emitter_type == self._EMIT_PLANE:
            if not any([point1, point2, point3]):
                raise RuntimeError(  # pragma: no cover
                    "point1, point2 and point3 needed if particle trace emitted from plane"
                )
            if isinstance(self.ensight, ModuleType):  # pragma: no cover
                new_emitters.append(  # pragma: no cover
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
        elif emitter_type == self._EMIT_PART:  # pragma: no cover
            if not parts:  # pragma: no cover
                raise RuntimeError(
                    "part and num_points needed if particle trace emitted from part"
                )  # pragma: no cover
            for p in parts:
                if isinstance(self.ensight, ModuleType):  # pragma: no cover
                    new_emitters.append(  # pragma: no cover
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
            raise RuntimeError(
                "No input provided to create the emitters for the particle trace"
            )  # pragma: no cover
        return new_emitters

    def _create_particle_trace_part(
        self,
        name: str,
        variable: Union[str, int, "ENS_VAR"],
        direction: str,
        source_parts: List["ENS_PART"],
        pathlines: Optional[bool] = False,
        emit_time: Optional[float] = None,
        total_time: Optional[float] = None,
        delta_time: Optional[float] = None,
        surface_restrict: Optional[bool] = False,
    ) -> "ENS_PART_PARTICLE_TRACE":
        """Private routine to create a particle trace part object"""
        current_timestep = None
        direction_map = {
            self.PT_POS_TIME: self.ensight.objs.enums.POS_TIME,
            self.PT_NEG_TIME: self.ensight.objs.enums.NEG_TIME,
            self.PT_POS_NEG_TIME: self.ensight.objs.enums.POS_NEG_TIME,
        }
        idx = self.ensight.objs.enums.PART_PARTICLE_TRACE
        def_part: "ENS_PART_PARTICLE_TRACE" = self.ensight.objs.core.DEFAULTPARTS[idx]
        def_part.TYPE = self.ensight.objs.enums.STREAMLINE
        if pathlines is True:
            def_part.TYPE = self.ensight.objs.enums.PATHLINE
            current_timestep = self.ensight.objs.core.TIMESTEP
            self.ensight.objs.core.TIMESTEP = self.ensight.objs.core.TIMESTEP_LIMITS[0]
        if total_time:
            def_part.TOTALTIME = total_time
        if delta_time:
            def_part.DELTATIME = delta_time
        if emit_time:  # pragma: no cover
            def_part.STARTTIME = emit_time
        def_part.DESCRIPTION = name
        def_part.VARIABLE = convert_variable(self.ensight, variable)
        def_part.SURFACERESTRICTED = False
        def_part.TRACEDIRECTION = direction_map.get(direction)
        if surface_restrict:
            def_part.SURFACERESTRICTED = True
        particle_trace_part: "ENS_PART_PARTICLE_TRACE" = def_part.createpart(
            sources=source_parts, name=name
        )[0]
        if current_timestep:
            self.ensight.objs.core.TIMESTEP = current_timestep
        return particle_trace_part

    def _add_emitters_to_particle_trace_part(
        self,
        particle_trace_part: "ENS_PART_PARTICLE_TRACE",
        new_emitters: List[Any],
        palette: Optional[str] = None,
        clean: Optional[bool] = False,
    ) -> "ENS_PART_PARTICLE_TRACE":
        """Private utility to add emitters to an existing particle trace part."""
        if isinstance(self.ensight, ModuleType):  # pragma: no cover
            if clean:  # pragma: no cover
                emitters = []  # pragma: no cover
            else:  # pragma: no cover
                emitters = particle_trace_part.EMITTERS.copy()  # pragma: no cover
            emitters.extend(new_emitters)  # pragma: no cover
            particle_trace_part.EMITTERS = emitters  # pragma: no cover
        else:
            if clean:
                self.ensight._session.cmd("enscl.emitters=[]", do_eval=False)
            else:
                self.ensight._session.cmd(
                    f"enscl.emitters=ensight.objs.wrap_id({particle_trace_part.objid}).EMITTERS.copy()",
                    do_eval=False,
                )
            text = "enscl.emitters.extend(["
            for emitter in new_emitters:
                text += emitter + ", "
            text = text[:-2]
            text += "])"
            self.ensight._session.cmd(text, do_eval=False)
            self.ensight._session.cmd(
                f"ensight.objs.wrap_id({particle_trace_part.objid}).setattr('EMITTERS', enscl.emitters.copy())"
            )
            self.ensight._session.cmd("del enscl.emitters", do_eval=False)
        if palette:
            particle_trace_part.COLORBYPALETTE = palette
        return particle_trace_part

    def _cure_particle_trace_part(
        self, particle_trace_part: Union[str, int, "ENS_PART_PARTICLE_TRACE"]
    ) -> "ENS_PART_PARTICLE_TRACE":
        """Private utility to cure an input particle trace part and convert it to an ``ENS_PART`"""

        # the add_emitter* functions were added in 2024 R2
        if not isinstance(self.ensight, ModuleType):  # pragma: no cover
            self.ensight._session.ensight_version_check("2024 R2")

        _particle_trace_part: "ENS_PART_PARTICLE_TRACE"
        if isinstance(particle_trace_part, (str, int)):  # pragma: no cover
            temp = self.ensight.objs.core.PARTS[particle_trace_part]  # pragma: no cover
            if not temp:  # pragma: no cover
                raise RuntimeError(
                    "particle_trace_part input is not a valid part"
                )  # pragma: no cover
            _particle_trace_part = temp[0]  # pragma: no cover
        else:
            _particle_trace_part = particle_trace_part
        return _particle_trace_part

    def _prepare_particle_creation(
        self,
        direction: Optional[str] = None,
        source_parts: Optional[List[Union[str, int, "ENS_PART"]]] = None,
    ) -> Tuple[str, List["ENS_PART"]]:
        """Private utility to set the direction if not provided, and to cure the list of source parts."""

        # the create_particle* functions were added in 2024 R2
        if not isinstance(self.ensight, ModuleType):  # pragma: no cover
            self.ensight._session.ensight_version_check("2024 R2")

        if not direction:
            direction = self.PT_POS_TIME
        if source_parts:  # pragma: no cover
            converted_source_parts = [convert_part(self.ensight, p) for p in source_parts]
        if not source_parts:  # pragma: no cover
            converted_source_parts = self.ensight.objs.core.selection(  # pragma: no cover
                name="ENS_PART"
            )
        if not converted_source_parts:  # pragma: no cover
            raise RuntimeError("No part selected for particle trace generation")  # pragma: no cover
        return direction, converted_source_parts

    def _find_palette(self, color_by: Optional[Union[str, int, "ENS_VAR"]] = None) -> Optional[str]:
        """Private utility to find the description of the input color_by variable"""
        palette: Optional[str] = None
        if color_by:
            try:
                _color_by_var: List["ENS_VAR"] = self.ensight.objs.core.VARIABLES.find(
                    [convert_variable(self.ensight, color_by)], attr="ID"
                )
                if _color_by_var:
                    palette = _color_by_var[0].DESCRIPTION
            except Exception:
                raise RuntimeError(
                    "The variable supplied to color the particle trace by does not exist"
                )
        return palette

    def create_particle_trace_from_points(
        self,
        name: str,
        variable: Union[str, int, "ENS_VAR"],
        points: List[List[float]],
        direction: Optional[str] = None,
        pathlines: Optional[bool] = False,
        source_parts: Optional[List[Union[str, int, "ENS_PART"]]] = None,
        emit_time: Optional[float] = None,
        total_time: Optional[float] = None,
        delta_time: Optional[float] = None,
        color_by: Optional[Union[str, int, "ENS_VAR"]] = None,
    ) -> "ENS_PART_PARTICLE_TRACE":
        """
        Create a particle trace part from a list o points.
        Returns the ``ENS_PART`` generated.

        Parameters
        ----------

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
        pathlines: bool
            True if the particle traces need to be pathlines
        points: list
            List of coordinates for the seed points.
        source_parts: list
            A list of parts to create the particle trace in. For instance, in a CFD
            simulation this might be the fluid zone.
            If not provided, the function will try to look for the selected parts.
        emit_time: float
            The emission time to start the particle trace from. If not provided,
            it will use the current time.
        total_time: float
            The total emission time. If not provided, EnSight will provide the end time
            for a transient simulation, an internal best time for steady state simulations.
        delta_time: float
            The interval for the emissions. If not provided, EnSight will provide
            a best estimate.
        color_by
            The optional variable to color the particle trace by.
            It can be the name, the ID or the ``ENS_VAR`` object.

        Examples
        --------
        >>> s = LocalLauncher().start()
        >>> cas_file = s.download_pyansys_example("mixing_elbow.cas.h5","pyfluent/mixing_elbow")
        >>> dat_file = s.download_pyansys_example("mixing_elbow.dat.h5","pyfluent/mixing_elbow")
        >>> s.load_data(cas_file, result_file=dat_file)
        >>> s.ensight.utils.parts.create_particle_trace_from_points("mytraces", "Velocity", points=[[-0.02,-0.123,0.01576],[0.109876,-0.123,0.0123]], source_parts=parts.select_parts_by_dimension(3))
        """
        emitter_type = self._EMIT_POINT
        direction, converted_source_parts = self._prepare_particle_creation(
            direction=direction, source_parts=source_parts
        )
        particle_trace_part = self._create_particle_trace_part(
            name,
            variable,
            direction,
            converted_source_parts,
            pathlines=pathlines,
            emit_time=emit_time,
            delta_time=delta_time,
            total_time=total_time,
        )
        new_emitters = self._create_emitters(emitter_type=emitter_type, points=points)
        palette = self._find_palette(color_by=color_by)
        return self._add_emitters_to_particle_trace_part(
            particle_trace_part, new_emitters=new_emitters, palette=palette, clean=True
        )

    def create_particle_trace_from_line(
        self,
        name: str,
        variable: Union[str, int, "ENS_VAR"],
        point1: List[float],
        point2: List[float],
        num_points: Optional[int] = 100,
        direction: Optional[str] = None,
        pathlines: Optional[bool] = False,
        source_parts: Optional[List[Union[str, int, "ENS_PART"]]] = None,
        emit_time: Optional[float] = None,
        total_time: Optional[float] = None,
        delta_time: Optional[float] = None,
        color_by: Optional[Union[str, int, "ENS_VAR"]] = None,
    ) -> "ENS_PART_PARTICLE_TRACE":
        """
        Create a particle trace part from a line.
        Returns the ``ENS_PART`` generated.

        Parameters
        ----------

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
        pathlines: bool
            True if the particle traces need to be pathlines
        point1: list
            List of coordinates for point 1.
        point2: list
            List of coordinates for point 2.
        source_parts: list
            A list of parts to create the particle trace in. For instance, in a CFD
            simulation this might be the fluid zone.
            If not provided, the function will try to look for the selected parts.
        num_points: int
            The number of points to emit from. Defaults to 100.
        emit_time: float
            The emission time to start the particle trace from. If not provided,
            it will use the current time.
        total_time: float
            The total emission time. If not provided, EnSight will provide the end time
            for a transient simulation, an internal best time for steady state simulations.
        delta_time: float
            The interval for the emissions. If not provided, EnSight will provide
            a best estimate.
        color_by
            The optional variable to color the particle trace by.
            It can be the name, the ID or the ``ENS_VAR`` object.

        Examples
        --------
        >>> s = LocalLauncher().start()
        >>> cas_file = s.download_pyansys_example("mixing_elbow.cas.h5","pyfluent/mixing_elbow")
        >>> dat_file = s.download_pyansys_example("mixing_elbow.dat.h5","pyfluent/mixing_elbow")
        >>> s.load_data(cas_file, result_file=dat_file)
        >>> parts = s.ensight.utils.parts
        >>> parts.create_particle_trace_from_line("mytraces", "Velocity", point1=[-0.02,-0.123,0.01576], point2=[0.109876,-0.123,0.0123], num_points=10, source_parts=parts.select_parts_by_dimension(3))
        """
        emitter_type = self._EMIT_LINE
        direction, converted_source_parts = self._prepare_particle_creation(
            direction=direction, source_parts=source_parts
        )
        particle_trace_part = self._create_particle_trace_part(
            name,
            variable,
            direction,
            converted_source_parts,
            pathlines=pathlines,
            emit_time=emit_time,
            delta_time=delta_time,
            total_time=total_time,
        )
        new_emitters = self._create_emitters(
            emitter_type=emitter_type, point1=point1, point2=point2, num_points=num_points
        )
        palette = self._find_palette(color_by=color_by)
        return self._add_emitters_to_particle_trace_part(
            particle_trace_part, new_emitters=new_emitters, palette=palette, clean=True
        )

    def create_particle_trace_from_plane(
        self,
        name: str,
        variable: Union[str, int, "ENS_VAR"],
        point1: List[float],
        point2: List[float],
        point3: List[float],
        num_points_x: Optional[int] = 25,
        num_points_y: Optional[int] = 25,
        direction: Optional[str] = None,
        pathlines: Optional[bool] = False,
        source_parts: Optional[List[Union[str, int, "ENS_PART"]]] = None,
        emit_time: Optional[float] = None,
        total_time: Optional[float] = None,
        delta_time: Optional[float] = None,
        color_by: Optional[Union[str, int, "ENS_VAR"]] = None,
    ) -> "ENS_PART_PARTICLE_TRACE":
        """
        Create a particle trace part from a plane.
        Returns the ``ENS_PART`` generated.

        Parameters
        ----------

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
        pathlines: bool
            True if the particle traces need to be pathlines
        point1: list
            List of coordinates for point 1, being a corner of the plane.
        point2: list
            List of coordinates for point 2, being a corner of the plane.
        point3: list
            List of coordinates for point 3, being a corner of the plane.
        source_parts: list
            A list of parts to create the particle trace in. For instance, in a CFD
            simulation this might be the fluid zone.
            If not provided, the function will try to look for the selected parts.
        num_points_x: int
            The number of points on the ``X`` direction of the emission plane.
            Defaults to 25.
        num_points_y: int
            The number of points on the ``Y`` direction of the emission plane.
            Defaults to 25.
        emit_time: float
            The emission time to start the particle trace from. If not provided,
            it will use the current time.
        total_time: float
            The total emission time. If not provided, EnSight will provide the end time
            for a transient simulation, an internal best time for steady state simulations.
        delta_time: float
            The interval for the emissions. If not provided, EnSight will provide
            a best estimate.
        color_by
            The optional variable to color the particle trace by.
            It can be the name, the ID or the ``ENS_VAR`` object.

        Examples
        --------
        >>> s = LocalLauncher().start()
        >>> cas_file = s.download_pyansys_example("mixing_elbow.cas.h5","pyfluent/mixing_elbow")
        >>> dat_file = s.download_pyansys_example("mixing_elbow.dat.h5","pyfluent/mixing_elbow")
        >>> s.load_data(cas_file, result_file=dat_file)
        >>> parts = s.ensight.utils.parts
        >>> parts.create_particle_trace_from_plane("mytraces", "Velocity", point1=[-0.02,-0.123,0.01576], point2=[0.109876,-0.123,0.0123], point3=[0.1, 0, 0.05] ,num_points_x=10, num_points_y=10, source_parts=parts.select_parts_by_dimension(3))
        """
        emitter_type = self._EMIT_PLANE
        direction, converted_source_parts = self._prepare_particle_creation(
            direction=direction, source_parts=source_parts
        )
        particle_trace_part = self._create_particle_trace_part(
            name,
            variable,
            direction,
            converted_source_parts,
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
            num_points_x=num_points_x,
            num_points_y=num_points_y,
        )
        palette = self._find_palette(color_by=color_by)
        return self._add_emitters_to_particle_trace_part(
            particle_trace_part, new_emitters=new_emitters, palette=palette, clean=True
        )

    def create_particle_trace_from_parts(
        self,
        name: str,
        variable: Union[str, int, "ENS_VAR"],
        parts: List[Union[str, int, "ENS_PART"]],
        part_distribution_type: Optional[int] = 0,
        num_points: Optional[int] = 100,
        direction: Optional[str] = None,
        pathlines: Optional[bool] = False,
        source_parts: Optional[List[Union[str, int, "ENS_PART"]]] = None,
        emit_time: Optional[float] = None,
        total_time: Optional[float] = None,
        delta_time: Optional[float] = None,
        color_by: Optional[Union[str, int, "ENS_VAR"]] = None,
        surface_restrict: Optional[bool] = False,
    ) -> "ENS_PART_PARTICLE_TRACE":
        """
        Create a particle trace part from a list of seed parts.
        Returns the ``ENS_PART`` generated.

        Parameters
        ----------

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
        pathlines: bool
            True if the particle traces need to be pathlines
        source_parts: list
            A list of parts to create the particle trace in. For instance, in a CFD
            simulation this might be the fluid zone.
            If not provided, the function will try to look for the selected parts.
        parts: list
            A list of parts to emit the particle traces from.
            They can be their names, their IDs or the respective ``ENS_PART`` objects.
        part_distribution_type: int
            The distribution of emitters in case of emission from a part.
            This table describes the options:

            ====================   =================================================
            Name                   Query type
            ====================   =================================================
            PART_EMIT_FROM_NODES   Emit from the nodes of the part
            PART_EMIT_FROM_AREA    Create an area of equidistant points for emission
            ====================   =================================================

            If not provided, it will default to ``PART_EMIT_FROM_NODES``
        num_points: int
            The number of points to emit from.
            Defaults to 100.
        emit_time: float
            The emission time to start the particle trace from. If not provided,
            it will use the current time.
        total_time: float
            The total emission time. If not provided, EnSight will provide the end time
            for a transient simulation, an internal best time for steady state simulations.
        delta_time: float
            The interval for the emissions. If not provided, EnSight will provide
            a best estimate.
        color_by
            The optional variable to color the particle trace by.
            It can be the name, the ID or the ``ENS_VAR`` object.
        surface_restrict: bool
            True if the particle trace needs to be restricted to the input parts.
            Defaults to False. The flag will be applied to any additional emitter
            appended to the particle trace created.

        Examples
        --------
        >>> s = LocalLauncher().start()
        >>> cas_file = s.download_pyansys_example("mixing_elbow.cas.h5","pyfluent/mixing_elbow")
        >>> dat_file = s.download_pyansys_example("mixing_elbow.dat.h5","pyfluent/mixing_elbow")
        >>> s.load_data(cas_file, result_file=dat_file)
        >>> parts = s.ensight.utils.parts
        >>> parts.create_particle_trace_from_parts("mytraces", "Velocity", parts=["hot-inlet", "cold-inlet"], num_points=100 source_parts=parts.select_parts_by_dimension(3))
        """
        emitter_type = self._EMIT_PART
        direction, converted_source_parts = self._prepare_particle_creation(
            direction=direction, source_parts=source_parts
        )
        particle_trace_part = self._create_particle_trace_part(
            name,
            variable,
            direction,
            converted_source_parts,
            pathlines=pathlines,
            emit_time=emit_time,
            delta_time=delta_time,
            total_time=total_time,
            surface_restrict=surface_restrict,
        )
        new_parts = [convert_part(self.ensight, p) for p in parts]
        new_emitters = self._create_emitters(
            emitter_type=emitter_type,
            parts=new_parts,
            part_distribution_type=part_distribution_type,
            num_points=num_points,
        )
        palette = self._find_palette(color_by=color_by)
        return self._add_emitters_to_particle_trace_part(
            particle_trace_part, new_emitters=new_emitters, palette=palette, clean=True
        )

    def add_emitter_points_to_particle_trace_part(
        self,
        particle_trace_part: Union[str, int, "ENS_PART"],
        points: List[List[float]],
    ) -> "ENS_PART_PARTICLE_TRACE":
        """
        Add point emitters to an existing particle trace. The function will return the updated
        ``ENS_PART`` object.

        Parameters
        ----------

        particle_trace_part:
            The particle trace part to be added emitters to.
            Can be the name, the ID or the ``ENS_PART`` object
        points: list
            List of list containing the coordinates for the seed points.

        Examples
        --------
        >>> s = LocalLauncher().start()
        >>> cas_file = s.download_pyansys_example("mixing_elbow.cas.h5","pyfluent/mixing_elbow")
        >>> dat_file = s.download_pyansys_example("mixing_elbow.dat.h5","pyfluent/mixing_elbow")
        >>> s.load_data(cas_file, result_file=dat_file)
        >>> p = s.ensight.utils.parts.create_particle_trace_from_points("mytraces", "Velocity", points=[[-0.02, -0.123, 0.01576]], source_parts=parts.select_parts_by_dimension(3))
        >>> p = s.ensight.utils.parts.add_emitter_points_to_particle_trace_part(p, points=[[0.109876, -0.123, 0.0123]])
        """
        emitter_type = self._EMIT_POINT
        particle_trace_part = self._cure_particle_trace_part(particle_trace_part)
        new_emitters = self._create_emitters(emitter_type=emitter_type, points=points)
        return self._add_emitters_to_particle_trace_part(particle_trace_part, new_emitters)

    def add_emitter_line_to_particle_trace_part(
        self,
        particle_trace_part: Union[str, int, "ENS_PART"],
        point1: List[float],
        point2: List[float],
        num_points: Optional[int] = 100,
    ) -> "ENS_PART_PARTICLE_TRACE":
        """
        Add a line emitter to an existing particle trace. The function will return the updated
        ``ENS_PART`` object.

        Parameters
        ----------

        particle_trace_part:
            The particle trace part to be added emitters to.
            Can be the name, the ID or the ``ENS_PART`` object.
        point1: list
            The coordinates for point 1.
        point2: list
            The coordinates for point 2.
        num_points: int
            The number of seed points. Defaults to 100.

        Examples
        --------
        >>> s = LocalLauncher().start()
        >>> cas_file = s.download_pyansys_example("mixing_elbow.cas.h5","pyfluent/mixing_elbow")
        >>> dat_file = s.download_pyansys_example("mixing_elbow.dat.h5","pyfluent/mixing_elbow")
        >>> s.load_data(cas_file, result_file=dat_file)
        >>> p = s.ensight.utils.parts.create_particle_trace_from_points("mytraces", "Velocity", points=[[-0.02,-0.123,0.01576]], source_parts=parts.select_parts_by_dimension(3))
        >>> p = s.ensight.utils.parts.add_emitter_line_to_particle_trace_part(p, point1=[-0.02, -0.123, 0.01576], point2=[0.109876, -0.123, 0.0123], num_points=10)
        """
        emitter_type = self._EMIT_LINE
        particle_trace_part = self._cure_particle_trace_part(particle_trace_part)
        new_emitters = self._create_emitters(
            emitter_type=emitter_type, point1=point1, point2=point2, num_points=num_points
        )
        return self._add_emitters_to_particle_trace_part(particle_trace_part, new_emitters)

    def add_emitter_plane_to_particle_trace_part(
        self,
        particle_trace_part: Union[str, int, "ENS_PART"],
        point1: List[float],
        point2: List[float],
        point3: List[float],
        num_points_x: Optional[int] = 25,
        num_points_y: Optional[int] = 25,
    ) -> "ENS_PART_PARTICLE_TRACE":
        """
        Add a plane emitter to an existing particle trace. The function will return the updated
        ``ENS_PART`` object.

        Parameters
        ----------

        particle_trace_part:
            The particle trace part to be added emitters to.
            Can be the name, the ID or the ``ENS_PART`` object.
        point1: list
            The coordinates for point 1, being a corner of the plane.
        point2: list
            The coordinates for point 2, being a corner of the plane.
        point3: list
            The coordinates for point 3, being a corner of the plane.
        num_points_x: int
            The number of points on the ``X`` direction of the emission plane.
            Defaults to 25.
        num_points_y: int
            The number of points on the ``Y`` direction of the emission plane.
            Defaults to 25.

        Examples
        --------
        >>> s = LocalLauncher().start()
        >>> cas_file = s.download_pyansys_example("mixing_elbow.cas.h5","pyfluent/mixing_elbow")
        >>> dat_file = s.download_pyansys_example("mixing_elbow.dat.h5","pyfluent/mixing_elbow")
        >>> s.load_data(cas_file, result_file=dat_file)
        >>> p = s.ensight.utils.parts.create_particle_trace_from_points("mytraces", "Velocity", points=[[-0.02,-0.123,0.01576]], source_parts=parts.select_parts_by_dimension(3))
        >>> p = s.ensight.utils.parts.add_emitter_plane_to_particle_trace_part(p, point1=[-0.02, -0.123, 0.01576], point2=[0.109876, -0.123, 0.0123], point3=[0.1, 0, 0.05], num_points_x=10, num_points_y=10)
        """
        emitter_type = self._EMIT_PLANE
        particle_trace_part = self._cure_particle_trace_part(particle_trace_part)
        new_emitters = self._create_emitters(
            emitter_type=emitter_type,
            point1=point1,
            point2=point2,
            point3=point3,
            num_points_x=num_points_x,
            num_points_y=num_points_y,
        )
        return self._add_emitters_to_particle_trace_part(particle_trace_part, new_emitters)

    def add_emitter_parts_to_particle_trace_part(
        self,
        particle_trace_part: Union[str, int, "ENS_PART"],
        parts: List[Union[str, int, "ENS_PART"]],
        part_distribution_type: Optional[int] = 0,
        num_points: Optional[int] = 100,
    ) -> "ENS_PART_PARTICLE_TRACE":
        """
        Add a list of part emitters to an existing particle trace. The function will return the updated
        ``ENS_PART`` object.

        Parameters
        ----------

        particle_trace_part:
            The particle trace part to be added emitters to.
            Can be the name, the ID or the ``ENS_PART`` object.
        parts: list
            A list of parts to emit the particle traces from.
            They can be their names, their IDs or the respective ``ENS_PART`` objects.
        part_distribution_type: int
            The distribution of emitters in case of emission from a part.
            This table describes the options:

            ====================   =================================================
            Name                   Query type
            ====================   =================================================
            PART_EMIT_FROM_NODES   Emit from the nodes of the part
            PART_EMIT_FROM_AREA    Create an area of equidistant points for emission
            ====================   =================================================

            If not provided, it will default to ``PART_EMIT_FROM_NODES``
        num_points: int
            The number of points to emit from.
            Defaults to 100.

        Examples
        --------
        >>> s = LocalLauncher().start()
        >>> cas_file = s.download_pyansys_example("mixing_elbow.cas.h5","pyfluent/mixing_elbow")
        >>> dat_file = s.download_pyansys_example("mixing_elbow.dat.h5","pyfluent/mixing_elbow")
        >>> s.load_data(cas_file, result_file=dat_file)
        >>> p = s.ensight.utils.parts.create_particle_trace_from_points("mytraces", "Velocity", points=[[-0.02, -0.123, 0.01576]], source_parts=parts.select_parts_by_dimension(3))
        >>> p = s.ensight.utils.parts.add_emitter_parts_to_particle_trace_part(p, parts=["cold-inlet", "hot-inlet"], num_points=25)
        """
        emitter_type = self._EMIT_PART
        particle_trace_part = self._cure_particle_trace_part(particle_trace_part)
        new_parts = [convert_part(self.ensight, p) for p in parts]
        new_emitters = self._create_emitters(
            emitter_type=emitter_type,
            parts=new_parts,
            part_distribution_type=part_distribution_type,
            num_points=num_points,
        )
        return self._add_emitters_to_particle_trace_part(particle_trace_part, new_emitters)

    def select_parts(
        self,
        p_list: Optional[List[Union[str, int, "ENS_PART"]]] = None,
        rec_flag: Optional[bool] = True,
    ) -> Optional[List["ENS_PART"]]:
        """
        Select the parts string, or int, or ensight.objs.ENS_PART, or list
        and record the selection (by default) honoring the
        EnSight preference to record command language by part id or by name.
        It creates a list of part objects and selects the parts, and records the
        selection by default.

        Parameters
        ----------
        p_list: list
            The list of part objects to compute the forces on. It can either be a list of names
            a list of IDs (integers or strings) or directly a list of ENS_PART objects
        rec_flag: bool
            True if the selection needs to be recorded

        Returns
        -------
        list
            A list of part objects selected or None if error.


        NOTE: If you do not want a measured part in your
                selection, then don't include it in the list
                e.g. if
                core.PARTS[0].PARTTYPE == ensight.objs.enums.PART_DISCRETE_PARTICLE == 3
                then it is a measured part
        """
        #
        pobj_list = self.get_part_id_obj_name(p_list, "obj")

        if not pobj_list:
            raise RuntimeError("Error, select_parts: part list is empty")
        else:
            # This was formerly used to record command lang 10.1.6(c)
            #  using part ids:
            #  ensight.part.select_begin(pid_list,record=1)
            # Now records selection, honoring the the preference
            #   part selection of by part id or by name (2024R1)
            record = 1 if rec_flag else 0
            self.ensight.objs.core.selection(name="ENS_PART").addchild(
                pobj_list, replace=1, record=record
            )
            # This is essential to synchronize cmd lang with the GUI, C++
            self.ensight.part.get_mainpartlist_select()

        return pobj_list

    def get_part_id_obj_name(
        self,
        plist: Optional[Union[str, int, "ENS_PART", List[str], List[int], List["ENS_PART"]]] = None,
        ret_flag="id",
    ) -> Union[Optional[List[int]], Optional[List[str]], Optional[List["ENS_PART"]]]:
        """
        Input a part or a list of parts and return an id, object, or name
        or a list of ids, objects, or names.

        Parameters
        ----------
        p_list: list
            The list of part objects to compute the forces on. It can either be a list of names
            a list of IDs (integers or strings) or directly a list of ENS_PART objects

        ret_flag: str
            A string that determines what is returned

        Returns
        -------
        list
            Either a list of part IDs, or a list of names or a list of ENS_PART objects
            depending on the requested ret_flag value
        """
        # To not change the interface I didn't move ret_flag to be a required argument,
        # so I need to check its value now
        if not ret_flag:
            return None
        if not plist:
            plist = [p for p in self.ensight.objs.core.PARTS]
        pobj_list: List["ENS_PART"] = []
        #
        #  Basically figure out what plist is, then convert it to a list of ENS_PARTs
        #
        if (
            isinstance(plist, self.ensight.objs.ENS_PART)
            or isinstance(plist, int)
            or isinstance(plist, str)
        ):
            p_list = [plist]
        elif isinstance(plist, list) or isinstance(plist, ensobjlist):
            p_list = [p for p in plist]
        else:  # pragma: no cover
            raise RuntimeError(  # pragma: no cover
                "Unknown type of input var plist {}".format(type(plist))
            )
        #
        #  p_list must now be a list
        #

        if not p_list:
            return None
        if not isinstance(p_list[0], (str, int, self.ensight.objs.ENS_PART)):  # pragma: no cover
            error = "First member is neither ENS_PART, int, nor string"  # pragma: no cover
            error += f"{p_list[0]} type = {type(p_list[0])}; aborting"  # pragma: no cover
            raise RuntimeError(error)  # pragma: no cover
        pobjs: List["ENS_PART"]
        if isinstance(p_list[0], int):
            # list of ints must be part ids
            for pid in p_list:
                pobjs = [p for p in self.ensight.objs.core.PARTS if p.PARTNUMBER == pid]
                for prt in pobjs:
                    pobj_list.append(prt)
        elif isinstance(p_list[0], str):
            if not p_list[0].isdigit():
                for pname in p_list:
                    pobjs = [p for p in self.ensight.objs.core.PARTS if p.DESCRIPTION == pname]
                    for prt in pobjs:
                        pobj_list.append(prt)
            else:  # digits, must be a string list of part ids?
                for pid_str in p_list:
                    pobjs = [
                        p for p in self.ensight.objs.core.PARTS if p.PARTNUMBER == int(pid_str)
                    ]
                    for prt in pobjs:
                        pobj_list.append(prt)
        else:
            for prt in p_list:
                pobj_list.append(prt)
        if ret_flag == "name":
            val_strings = [str(p.DESCRIPTION) for p in pobj_list]
            return val_strings
        if ret_flag == "obj":
            val_objs = [p for p in pobj_list]
            return val_objs
        val_ints = [int(p.PARTNUMBER) for p in pobj_list]
        return val_ints
