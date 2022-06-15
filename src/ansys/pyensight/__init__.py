from ._version import DEFAULT_ANSYS_VERSION, VERSION

__version__ = VERSION

# Default Ansys version number
__ansys_version__ = DEFAULT_ANSYS_VERSION

from ansys.pyensight.launcher import Launcher
from ansys.pyensight.locallauncher import LocalLauncher
from ansys.pyensight.session import Session
