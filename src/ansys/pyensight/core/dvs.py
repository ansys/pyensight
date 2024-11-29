from ansys.api.pyensight.dvs_api import dvs_base

from typing import Optional, TYPE_CHECKING
import glob
import os
import platform
import re
import sys

if TYPE_CHECKING:
    from ansys.pyensight.core import Session


class DVS(dvs_base):

    def __init__(self, session: Optional["Session"]=None, ansys_installation: Optional[str]=None) -> None:
        super().__init__(session=session)
        self._ansys_installation = ansys_installation
        if self._session:
            if not self._ansys_installation:
                self._ansys_installation = os.path.dirname(self._session._launcher._install_path)
        if not self._session and not self._ansys_installation:
            raise RuntimeError("Either a PyEnSight session or an ansys installation path need to be provided.")
        self._build_python_path()

    @staticmethod
    def _is_windows():
        return "Win" in platform.system()

    def _build_python_path(self):
        cei_install = os.path.join(self._ansys_installation, "CEI")
        apex_path = glob.glob(os.path.join(cei_install, "apex???"))
        if not apex_path:
            raise RuntimeError("Cannot find a valid EnSight install")
        apex_path = apex_path[-1]
        arch = "win64" if self._is_windows() else "linux_2.6_64"
        apex_libs = os.path.join(apex_path, "machines", arch)
        python_path = glob.glob(os.path.join(apex_libs, "Python-*"))[-1]
        apex_py_version = re.search("Python-3.([0-9]+).([0-9]+)", os.path.basename(python_path))
        apex_py_major_version = apex_py_version.group(1)
        lib_path = os.path.join(python_path, "lib", f"python3.{apex_py_major_version}")
        if self._is_windows():
            lib_path = os.path.join(python_path, "DLLs")
        sys.path.append(lib_path)
        try:
            import dynamic_visualization_store
            self._dvs_module = dynamic_visualization_store
        except (ModuleNotFoundError, ImportError):
            raise RuntimeError("Cannot import DVS module")






    