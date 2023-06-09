"""parts module

The parts module allows pyensight to control the parts in the EnSight session

Example to select all the 3D parts:

::

    from ansys.pyensight import LocalLauncher
    session = LocalLauncher().start()
    parts = session.ensight.utils.parts
    parts.select_by_dimension(3) 
"""

import math
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

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

    def select_parts_by_dimension(self, dimension: int) -> None:
        parts = self.ensight.objs.core.PARTS
        return ensobjlist([p for p in parts if getattr(p, f"HAS{dimension}DELEMENTS") == True])
