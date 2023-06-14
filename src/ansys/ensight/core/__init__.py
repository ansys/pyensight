from ._version import DEFAULT_ANSYS_VERSION, VERSION

__version__ = VERSION

# Ansys version number that this release is associated with
__ansys_version__ = DEFAULT_ANSYS_VERSION
__ansys_version_str__ = f"{2000+(int(__ansys_version__) // 10)} R{int(__ansys_version__) % 10}"

from ansys.ensight.core.launcher import Launcher
from ansys.ensight.core.listobj import ensobjlist
from ansys.ensight.core.locallauncher import LocalLauncher
from ansys.ensight.core.session import Session

try:
    from ansys.ensight.core.dockerlauncher import DockerLauncher
except Exception:
    pass

try:
    from ansys.ensight.core.dockerlauncherenshell import DockerLauncherEnShell
except Exception:
    pass

from ansys.ensight.core.launch_ensight import launch_ensight
