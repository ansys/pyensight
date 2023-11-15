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

from typing import TYPE_CHECKING, Dict, Optional, Union

try:
    import ensight
    from ensight.objs import ensobjlist, ens_emitterobj  # type: ignore
except ImportError:
    from ansys.pyensight.core.listobj import ensobjlist
    from ansys.api.pyensight.ens_emitterobj import ens_emitterobj

if TYPE_CHECKING:
    try:
        from ensight.objs import ENS_PART  # type: ignore
    except ImportError:
        from ansys.api.pyensight import ensight_api
        from ansys.api.pyensight.ens_part import ENS_PART

PARTICLE_TRACE_EMITTER_PART = """
class EnSEmitterPart(ensight.objs.ens_emitterobj):
    def __init__(
        self,
        repr
    ):
        super().__init__(ensight.objs.EMIT_PART, repr)
"""
PARTICLE_TRACE_EMITTER_LINE = """
class EnSEmitterPart(ensight.objs.ens_emitterobj):
    def __init__(
        self,
        repr
    ):
        super().__init__(ensight.objs.EMIT_LINE, repr)
"""
PARTICLE_TRACE_EMITTER_CURSOR = """
class EnSEmitterPart(ensight.objs.ens_emitterobj):
    def __init__(
        self,
        repr
    ):
        super().__init__(ensight.objs.EMIT_CURSOR, repr)
"""
PARTICLE_TRACE_EMITTER_PLANE = """
class EnSEmitterPart(ensight.objs.ens_emitterobj):
    def __init__(
        self,
        repr
    ):
        super().__init__(ensight.objs.EMIT_PLANE, repr)
"""

class EnSEmitterPart(ensight.objs.ens_emitterobj):
    def __init__(
        self,
        session,
        objid,
        repr
    ):
        self.repr = repr
        super().__init__(session, objid, ensight.objs.EMIT_PART)

class Parts:
    """Controls the parts in the current EnSight ``Session`` instance."""

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

    def _create_particle_trace(
        self,
        point1,
        point2,
        point3,
        num_points,
        num_points_x,
        num_points_y,
        part
    ):
        point4 = self._create_fourth_point(point1, point2, point3)
        _repr = f"P11={point1[0]} P12={point1[1]} P13={point1[2]} "
        _repr += f"P21={point2[0]} P22={point2[1]} P23={point2[2]} "
        _repr += f"P31={point3[0]} P32={point3[1]} P33={point3[2]} "
        _repr += f"P41={point4[0]} P42={point4[1]} P43={point4[2]} "
        additional = ""
        if num_points > 0:
            additional += f"NX={num_points} NY=1"
        elif (num_points_x > 0 and num_points_y > 0):
            additional += f"NX={num_points_x} NY={num_points_y}"
        if part:
            additional += f" DT={part}"
        self.ensight._session.cmd(PARTICLE_TRACE_EMITTER_CURSOR)
