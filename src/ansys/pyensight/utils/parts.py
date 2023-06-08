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
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from ansys.pyensight.session import Session

    
class Parts:
    """A class to handle the parts in the current EnSight session."""

    def __init__(self, ensight: "Session.ensight"):
        self.ensight = ensight

    def select_parts_by_dimension(self, dimension: int) -> None:
        parts = self.ensight.objs.core.PARTS
        parts[0].
