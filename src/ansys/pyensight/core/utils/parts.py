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
    from ensight.objs import ensobjlist  # type: ignore
except ImportError:
    from ansys.pyensight.core.listobj import ensobjlist

if TYPE_CHECKING:
    try:
        from ensight.objs import ENS_PART  # type: ignore
    except ImportError:
        from ansys.api.pyensight import ensight_api
        from ansys.api.pyensight.ens_part import ENS_PART


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
