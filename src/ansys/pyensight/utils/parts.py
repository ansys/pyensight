"""parts module

The parts module allows pyensight to control the parts in the EnSight session

Example to select all the 3D parts:

::

    from ansys.pyensight import LocalLauncher
    session = LocalLauncher().start()
    parts = session.ensight.utils.parts
    parts.select_by_dimension(3)
"""

from typing import TYPE_CHECKING, List, Optional, Union

from ansys.pyensight.ens_part import ENS_PART
from ansys.pyensight.listobj import ensobjlist

if TYPE_CHECKING:
    try:
        import ensight
    except ImportError:
        from ansys.pyensight import ensight_api


class Parts:
    """A class to handle the parts in the current EnSight session."""

    def __init__(self, ensight: Union["ensight_api.ensight", "ensight"]):
        self.ensight = ensight

    def select_parts_by_dimension(
        self, dimension: int
    ) -> Optional[Union[ensobjlist["ENS_PART"], "ENS_PART"]]:
        parts = self.ensight.objs.core.PARTS
        parts.set_attr("SELECTED", False)
        found = parts.find(True, f"HAS{dimension}DELEMENTS")
        found.set_attr("SELECTED", True)
        return found

    def select_parts_invert(self) -> Optional[Union[ensobjlist["ENS_PART"], "ENS_PART"]]:
        self.ensight.part.select_invert()
        parts = self.ensight.objs.core.PARTS
        return parts.find(True, "SELECTED")

    def select_parts_by_tag(
        self, tag: Optional[str] = None, value: Optional[Union[str, List[str]]] = None
    ) -> Optional[Union[ensobjlist["ENS_PART"], "ENS_PART"]]:
        parts = self.ensight.objs.core.PARTS
        metadata = {p: p.METADATA for p in parts}
        found = ensobjlist()
        if not tag and not value:
            self.ensight.part.select_all()
            return parts
        if tag and value:
            found = ensobjlist([p for p, met in metadata.items() if met.get(tag) == value])
        elif value and not tag:
            found = ensobjlist([p for p, met in metadata.items() if value in met.values()])
        elif tag and not value:
            found = ensobjlist([p for p, met in metadata.items() if tag in met.keys()])
        if found:
            found.set_attr("SELECTED", True)
        return found
