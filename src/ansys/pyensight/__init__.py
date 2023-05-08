from ._version import DEFAULT_ANSYS_VERSION, VERSION

__version__ = VERSION

# Ansys version number that this release is associated with
__ansys_version__ = DEFAULT_ANSYS_VERSION
__ansys_version_str__ = f"{2000+(int(__ansys_version__) // 10)} R{int(__ansys_version__) % 10}"

from ansys.pyensight.launcher import Launcher
from ansys.pyensight.listobj import ensobjlist
from ansys.pyensight.locallauncher import LocalLauncher
from ansys.pyensight.session import Session

try:
    from ansys.pyensight.dockerlauncher import DockerLauncher
except Exception:
    pass

try:
    from ansys.pyensight.dockerlauncherenshell import DockerLauncherEnShell
except Exception:
    pass

from ansys.pyensight.launch_ensight import launch_ensight
