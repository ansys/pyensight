"""parts module

The parts module allows pyensight to control the parts in the EnSight session

Example to select all the 3D parts:

::
    (PyEnSight)
    from ansys.pyensight.core import LocalLauncher
    session = LocalLauncher().start()
    parts = session.ensight.utils.parts
    parts.select_by_dimension(3)

    (EnSight)
    from ensight.utils import parts
    parts.select_by_dimension(3)

"""

from typing import TYPE_CHECKING, Dict, Optional, Union

try:
    import ensight
    from ensight.objs import ensobjlist  # type: ignore
except ImportError:
    from ansys.pyensight.core.listobj import ensobjlist

if TYPE_CHECKING:
    try:
        from ensight.objs import ENS_PART  # type: ignore
    except ImportError:
        from ansys.pyensight.core import ensight_api
        from ansys.pyensight.core.ens_query import ENS_PART


class Parts:
    """A class to handle the parts in the current EnSight session."""

    def __init__(self, ensight: Union["ensight_api.ensight", "ensight"]):
        self.ensight = ensight

    def select_parts_by_dimension(self, dimension: int) -> ensobjlist["ENS_PART"]:
        """Select parts by the input dimension and return
        the parts found.

        Args:
            dimension (int): the dimension to use for finding parts.

        Return:
            found (ensobjlist): the list of parts found and selected.
        """
        parts = self.ensight.objs.core.PARTS
        parts.set_attr("SELECTED", False)
        found = parts.find(True, f"HAS{dimension}DELEMENTS")
        found.set_attr("SELECTED", True)
        return found

    def select_parts_invert(self) -> ensobjlist["ENS_PART"]:
        """Select the parts currently not selected and deselect the currently
        selected ones.

        Return:
            found (ensobjlist): the updated list of parts selected.
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
        """Select parts by the input dimension and return
        the parts found.

        Args:
            tag (str): the tag to be used to find the parts.
            value (str): the value to be used to find the parts.
            tagdict (dict): a dictionary containing keys and values to be used in pair
                for finding the parts. Only the parts that have all the keys and the corresponding
                values will be returned. If a tagdict is supplied, this takes precedence
                with respect to the other arguments.
        Return:
            found (ensobjlist): the list of parts found and selected. If no arguments are given, all the
            parts are returned.
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
