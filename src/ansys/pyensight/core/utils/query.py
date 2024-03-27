from typing import TYPE_CHECKING, Any, List, Optional, Union

if TYPE_CHECKING:
    try:
        import ensight
        from ensight.objs import ENS_QUERY  # type: ignore
    except ImportError:
        from ansys.api.pyensight import ensight_api
        from ansys.api.pyensight.ens_query import ENS_QUERY


class Query:
    """Provides the ``ensight.utils.query`` interface.

    The methods in this class implement simplified interfaces to common
    query-orientated operations, such as creating a temporal or temporal query.

    This class is instantiated as ``ensight.utils.query`` in EnSight Python
    and as ``Session.ensight.utils.query`` in PyEnSight. The constructor is
    passed the interface, which serves as the ``ensight`` module for either
    case. As a result, the methods can be accessed as ``ensight.utils.query.create_distance()``
    in EnSight Python or ``session.ensight.utils.query.create_distance()`` in PyEnSight.

    Parameters
    ----------
    interface :
        Entity that provides the ``ensight`` namespace. In the case of
        EnSight Python, the ``ensight`` module is passed. In the case
        of PyEnSight, ``Session.ensight`` is passed.
    """

    def __init__(self, interface: Union["ensight_api.ensight", "ensight"]):
        self._ensight = interface

    DISTANCE_PART1D: str = "1d_part"
    DISTANCE_LINE: str = "line_tool"
    DISTANCE_SPLINE: str = "spline"

    DIST_TYPE_LENGTH: str = "arc_length"
    DIST_TYPE_LENGTH_X: str = "x_arc_length"
    DIST_TYPE_LENGTH_Y: str = "y_arc_length"
    DIST_TYPE_LENGTH_Z: str = "z_arc_length"
    DIST_TYPE_ORIGIN: str = "from_origin"
    DIST_TYPE_ORIGIN_X: str = "x_from_origin"
    DIST_TYPE_ORIGIN_Y: str = "y_from_origin"
    DIST_TYPE_ORIGIN_Z: str = "z_from_origin"

    DIST_SEG_ACCUMULATION: str = "accumulation"
    DIST_SEG_RESET_EACH: str = "reset_each"

    def create_distance(
        self,
        name: str,
        query_type: str,
        part_list: List[Any],
        variable1: Any,
        variable2: Optional[Any] = None,
        num_samples: int = 20,
        point1: Optional[List[float]] = None,
        point2: Optional[List[float]] = None,
        distance_type: str = DIST_TYPE_LENGTH,
        segments_by: str = DIST_SEG_ACCUMULATION,
        spline_name: Optional[str] = None,
        new_plotter: bool = False,
    ) -> "ENS_QUERY":
        """Create an EnSight query over a distance object.

        Create an EnSight distance query using the passed parameters. Return
        the newly generated ``ENS_QUERY`` object.

        Parameters
        ----------
        name : str
            Name for the query.
        query_type : str
            Type of the query. This table describes the options:

            ================== ========================================
            Name               Query type
            ================== ========================================
            DISTANCE_PART1D    Samples along the points of a 1D part
            DISTANCE_LINE      Samples along the length of a line
            DISTANCE_SPLINE    Samples along the length of a spline
            ================== ========================================


        part_list: list
            List of parts to use as the source for the query. Part numbers,
            part names, and part objects are supported.
        variable1 :
            Variable to sample as the "y" value.
        variable2 : optional
            Variable to sample as the "x" value. The default is ``None``,
            in which case the "x" value is the distance along the sampling
            domain.
        num_samples : int, optional
            For a spline or line query, the number of samples to use along
            the length of the spline or line. The default is ``20``.
        point1 : list[float], optional
            For a line query, the ``x,y,z`` location of the start of the line.
            The default is ``None``.
        point2: : list[float], optional
            For a line query, the x,y,z location of the end of the line.
            The default is ``None``.
        distance_type : str, optional
            For a query over a distance (no second variable), how to compute
            distance. The default is ``"arc_length"``, in which case
            ``DIST-TYPE_LENGTH_X`` is used. This table describes
            the options:

            =================== =========================================
            Name                Query type
            =================== =========================================
            DIST_TYPE_LENGTH    Length along path
            DIST_TYPE_LENGTH_X  X component along path
            DIST_TYPE_LENGTH_Y  Y component along path
            DIST_TYPE_LENGTH_Z  Z component along path
            DIST_TYPE_ORIGIN    Distance from the origin
            DIST_TYPE_ORIGIN_X  X component of distance from the origin
            DIST_TYPE_ORIGIN_Y  Y component of distance from the origin
            DIST_TYPE_ORIGIN_Z  Z component of distance from the origin
            =================== =========================================


        segments_by : str, optional
            For a 1D part query, how to compute distance for the
            segments of the 1D part. The default is ``"accumulation"``,
            in which case ``DIST_SEG_ACCUMULATION`` is used.
            This table describes the options:

            ====================== ==========================================
            Name                   Segment handling
            ====================== ==========================================
            DIST_SEG_ACCUMULATION  Accumulate distance over segments
            DIST_SEG_RESET_EACH    Reset the distance value for each segment
            ====================== ==========================================


        spline_name : str, optional
            For a spline query, the name of the spline to sample along. The
            default is ``None``.
        new_plotter : bool, optional
            Whether to add the query to a newly created plotter. The default is
            ``False``.

        Returns
        -------
        ENS_QUERY
            ``ENS_QUERY`` instance on success or raises an exception on error.

        Examples
        --------
        >>> s = LocalLauncher().start()
        >>> s.load_data(f"{s.cei_home}/ensight{s.cei_suffix}/data/cube/cube.case")
        >>> parts = s.ensight.objs.core.PARTS["Computational mesh"]
        >>> pnt1 = [-1.0, 0.5, 1.0]
        >>> pnt2 = [2.0, 0.5, 1.0]
        >>> query = s.ensight.utils.query.create_distance("Temperature vs Distance",
        >>>             s.ensight.utils.query.DISTANCE_LINE, parts, "temperature",
        >>>             point1=pnt1, point2=pnt2, new_plotter=True)

        """
        if query_type not in [
            self.DISTANCE_PART1D,
            self.DISTANCE_LINE,
            self.DISTANCE_SPLINE,
        ]:  # pragma: no cover
            raise RuntimeError(f"Invalid query type: {query_type} specified.")  # pragma: no cover

        var1 = self._get_variable(variable1)
        var2 = self._get_variable(variable2, "DISTANCE")

        if query_type == self.DISTANCE_LINE:
            if (point1 is None) or (point2 is None):  # pragma: no cover
                raise RuntimeError("Both point1 and point2 must be specified.")  # pragma: no cover
            self._create_query_core_begin(name, part_list)
            self._ensight.query_ent_var.number_of_sample_pts(num_samples)
            self._ensight.query_ent_var.constrain("line_tool")
            self._ensight.query_ent_var.line_loc(1, *point1)
            self._ensight.query_ent_var.line_loc(2, *point2)

        elif query_type == self.DISTANCE_PART1D:  # pragma: no cover
            self._create_query_core_begin(name, part_list, single=True)
            self._ensight.query_ent_var.constrain("1d_part")
            self._ensight.query_ent_var.multiple_segments_by(segments_by)

        elif query_type == self.DISTANCE_SPLINE:  # pragma: no cover
            if spline_name is None:
                raise RuntimeError("A spline_name must be specified.")
            self._create_query_core_begin(name, part_list)
            self._ensight.query_ent_var.number_of_sample_pts(num_samples)
            self._ensight.query_ent_var.constrain("spline")
            self._ensight.query_ent_var.spline_name(spline_name)

        self._ensight.query_ent_var.distance(distance_type)
        self._ensight.query_ent_var.variable_1(var1)
        self._ensight.query_ent_var.generate_over("distance")
        self._ensight.query_ent_var.variable_2(var2)

        query = self._create_query_core_end()
        if new_plotter:
            plot = self._ensight.objs.core.DEFAULTPLOT[0].createplotter()
            query.addtoplot(plot)
        return query

    TEMPORAL_NODE: str = "node"
    TEMPORAL_ELEMENT: str = "element"
    TEMPORAL_IJK: str = "ijk"
    TEMPORAL_XYZ: str = "cursor"
    TEMPORAL_MINIMUM: str = "min"
    TEMPORAL_MAXIMUM: str = "max"

    def create_temporal(
        self,
        name: str,
        query_type: str,
        part_list: List[Any],
        variable1: Any,
        variable2: Optional[Any] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        num_samples: Optional[int] = None,
        node_id: Optional[int] = None,
        element_id: Optional[int] = None,
        xyz: Optional[List[float]] = None,
        ijk: Optional[List[int]] = None,
        new_plotter: bool = False,
    ) -> "ENS_QUERY":
        """Create an EnSight query over time.

        Parameters
        ----------
        name : str
            Name for the query.
        query_type:
            Type of the query. Descriptions of options follow.

            ================= =========================================================
            Name              Query type
            ================= =========================================================
            TEMPORAL_NODE     At a node number over time
            TEMPORAL_ELEMENT  At an element number over time
            TEMPORAL_IJK      At an ijk element over time
            TEMPORAL_XYZ      At some x,y,z location over time
            TEMPORAL_MINIMUM  Minimum value on the selected parts at each point in time
            TEMPORAL_MAXIMUM  Maximum value on the selected parts at each point in time
            ================= =========================================================


        part_list : list
            List of parts to use as the source for the query.
        variable1 :
            Variable to sample as the "y" value.
        variable2 : optional
            Variable to sample as the "x" value. The default is ``None``, in which
            case the "x" value is the distance along the sampling domain.
        start_time : float, optional
            Simulation time to start sampling at. The default is ``None``, in which
            case the first timestep, ``ENS_GLOBALS.SOLUTIONTIME_LIMITS[0]``, is used.
        end_time : float, optional
            The simulation time to end sampling at. The default is ``None``, in which
            case the last timestep, ``ENS_GLOBALS.SOLUTIONTIME_LIMITS[1]``, is used.
        num_samples : int, optional
            Number of samples to take along the selected timestep range. The default
            is ``None``, in which case the number of defined timesteps,
            ``ENS_GLOBALS.TIMESTEP_LIMITS[1] - ENS_GLOBALS.TIMESTEP_LIMITS[0] + 1``,
            is used.
        node_id : int, optional
            For a ``TEMPORAL_NODE`` query, the ID of the node to query. The default is
            ``None``.
        element_id : int, optional
            For a ``TEMPORAL_ELEMENT`` query, the ID of the element to query. The
            default is ``None``.
        xyz : list[float], optional
            For a ``TEMPORRAL_XYZ`` query, the ``[x,y,z]`` location in data space
            to query. The default is ``None``.
        ijk : list[int], optional
            For a ``TEMPORAL_IJK`` query, the ``[i,j,k]`` value for the structured
            mesh node to query.  The default is ``None``.
        new_plotter : bool, optional
            Whether to add the query to a newly created plotter. The default is
            ``False``.

        Returns
        -------
        ENS_QUERY
            ````ENS_QUERY`` instance on success or raises an exception on error.

        Examples
        --------
        >>> s = LocalLauncher().start()
        >>> s.load_data(f"{s.cei_home}/ensight{s.cei_suffix}/data/guard_rail/crash.case")
        >>> parts = s.ensight.objs.core.PARTS
        >>> s.ensight.utils.query.create_temporal("Maximum plastic",
        >>> s.ensight.utils.query.TEMPORAL_MAXIMUM, parts, "plastic", new_plotter=True)

        """
        if query_type not in [  # pragma: no cover
            self.TEMPORAL_NODE,
            self.TEMPORAL_ELEMENT,
            self.TEMPORAL_IJK,
            self.TEMPORAL_XYZ,
            self.TEMPORAL_MINIMUM,
            self.TEMPORAL_MAXIMUM,
        ]:
            raise RuntimeError(f"Invalid query type: {query_type} specified.")  # pragma: no cover

        var1 = self._get_variable(variable1)
        var2 = self._get_variable(variable2, "TIME")

        # default the time range
        if start_time is None:  # pragma: no cover
            start_time = self._ensight.objs.core.SOLUTIONTIME_LIMITS[0]
        if end_time is None:  # pragma: no cover
            end_time = self._ensight.objs.core.SOLUTIONTIME_LIMITS[1]

        # default the number of timesteps
        if num_samples is None:  # pragma: no cover
            num_samples = (
                self._ensight.objs.core.TIMESTEP_LIMITS[1]
                - self._ensight.objs.core.TIMESTEP_LIMITS[0]
                + 1
            )

        if query_type == self.TEMPORAL_NODE:
            if node_id is None:  # pragma: no cover
                raise RuntimeError("node_id must be specified.")  # pragma: no cover
            self._create_query_core_begin(name, part_list)
            self._ensight.query_ent_var.constrain("node")
            self._ensight.query_ent_var.node_id(node_id)

        elif query_type == self.TEMPORAL_ELEMENT:
            if element_id is None:  # pragma: no cover
                raise RuntimeError("element_id must be specified.")  # pragma: no cover
            self._create_query_core_begin(name, part_list)
            self._ensight.query_ent_var.constrain("element")
            self._ensight.query_ent_var.elem_id(element_id)

        elif query_type == self.TEMPORAL_XYZ:
            if xyz is None:  # pragma: no cover
                raise RuntimeError("xyz must be specified.")  # pragma: no cover
            self._create_query_core_begin(name, part_list)
            self._ensight.query_ent_var.constrain("cursor")
            self._ensight.query_ent_var.cursor_loc(*xyz)

        elif query_type == self.TEMPORAL_IJK:
            if ijk is None:  # pragma: no cover
                raise RuntimeError("ijk must be specified.")  # pragma: no cover
            self._create_query_core_begin(name, part_list)  # pragma: no cover
            self._ensight.query_ent_var.constrain("ijk")  # pragma: no cover
            self._ensight.query_ent_var.ijk(*ijk)  # pragma: no cover

        elif query_type == self.TEMPORAL_MINIMUM:
            self._create_query_core_begin(name, part_list)
            self._ensight.query_ent_var.constrain("min")

        elif query_type == self.TEMPORAL_MAXIMUM:  # pragma: no cover
            self._create_query_core_begin(name, part_list)
            self._ensight.query_ent_var.constrain("max")

        self._ensight.query_ent_var.number_of_sample_pts(num_samples)
        self._ensight.query_ent_var.begin_simtime(start_time)
        self._ensight.query_ent_var.end_simtime(end_time)
        self._ensight.query_ent_var.sample_by("value")
        self._ensight.query_ent_var.update_with_newtimesteps("ON")
        self._ensight.query_ent_var.variable_1(var1)
        self._ensight.query_ent_var.generate_over("time")
        self._ensight.query_ent_var.variable_2(var2)

        query = self._create_query_core_end()
        if new_plotter:
            plot = self._ensight.objs.core.DEFAULTPLOT[0].createplotter()
            query.addtoplot(plot)
        return query

    def _create_query_core_end(self) -> "ENS_QUERY":
        """Complete a query operation.

        Execute the "end()" and "query()" calls to finalize the query.  Return the latest
        ENS_QUERY object.

        Returns
        -------
        "ENS_QUERY"
            The last created ENS_QUERY object or raise an exception if query creation fails.

        """
        nextid = self._ensight.objs.next_id()
        self._ensight.query_ent_var.end()
        self._ensight.query_ent_var.query()
        error_msg = None
        try:
            query = max(self._ensight.objs.core.QUERIES)
            # no new id allocated
            if query.__OBJID__ < nextid:  # pragma: no cover
                error_msg = "Unable to create the specified query."  # pragma: no cover
        except ValueError:  # pragma: no cover
            error_msg = "Unable to create the specified query."  # pragma: no cover
        if error_msg:  # pragma: no cover
            raise RuntimeError(error_msg)  # pragma: no cover
        return query

    def _create_query_core_begin(self, name: str, parts: Optional[List[int]], single=False) -> None:
        """Common query setup

        Make the common calls for all queries.  Select the appropriate source parts, set the
        query name and "generated" type.

        Parameters
        ----------
        name : str
            The name for the query.
        parts : List
            The list of source parts for the query.
        single : bool
            If true, then this is a 1D part query and emit the appropriate output.  Otherwise,
            ensure that the proper parts are selected. (Default value = False)

        """
        part_list = []
        if parts:  # pragma: no cover
            for p in parts:
                if type(p) == str:  # pragma: no cover
                    part_list.append(
                        self._ensight.objs.core.PARTS[p][0].PARTNUMBER
                    )  # pragma: no cover
                elif type(p) == int:  # pragma: no cover
                    part_list.append(p)  # pragma: no cover
                else:
                    if hasattr(p, "PARTNUMBER"):  # pragma: no cover
                        part_list.append(p.PARTNUMBER)
        if not single:
            self._ensight.part.select_begin(part_list)
        self._ensight.query_ent_var.begin()
        self._ensight.query_ent_var.description(name)
        self._ensight.query_ent_var.query_type("generated")
        if single:
            self._ensight.query_ent_var.part_id(part_list[0])

    def _get_variable(self, v: Any, default: Optional[str] = None) -> Optional[str]:
        """Convert a generic argument into a variable name string

        Convert a generic object into a variable name. Valid inputs
        include a string or an ENS_VARIABLE object.

        Parameters
        ----------
        v: Any
            The object to be converted into a variable name.
        default: str, optional
            The value to return if the input variable is None.

        Returns
        -------
            The string name of the variable or None.

        """
        if v is None:
            return default
        elif type(v) is str:
            if v not in self._ensight.objs.core.VARIABLES.get_attr("DESCRIPTION"):
                raise ValueError("The variable supplied does not exist.")
            return v
        else:
            return v.DESCRIPTION
