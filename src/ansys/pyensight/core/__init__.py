try:
    import importlib.metadata as importlib_metadata  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    import importlib_metadata  # type: ignore
__version__ = importlib_metadata.version(__name__.replace(".", "-"))

VERSION = __version__
DEFAULT_ANSYS_VERSION = "242"

# Ansys version number that this release is associated with
__ansys_version__ = DEFAULT_ANSYS_VERSION
__ansys_version_str__ = f"{2000+(int(__ansys_version__) // 10)} R{int(__ansys_version__) % 10}"

from ansys.pyensight.core.dockerlauncher import DockerLauncher
from ansys.pyensight.core.launch_ensight import launch_ensight, launch_libuserd
from ansys.pyensight.core.launcher import Launcher
from ansys.pyensight.core.listobj import ensobjlist
from ansys.pyensight.core.locallauncher import LocalLauncher
from ansys.pyensight.core.session import Session
