"""Launcher module

The Launcher module allows pyensight to control the enshell launcher
capabilities to launch EnSight in multiple configurations, and to
connect to an existing EnSight session

Examples
--------
>>> from ansys.pyensight import Launcher
>>> session = Launcher.launch_session()

"""
import platform
from typing import Optional
import os.path
from ansys import pyensight


class Launcher:
    """Class to access EnSight Launcher

    The Launcher instance allows the user to launch an EnSight session
    or to connect to an existing one

    Examples
    --------

    >>> from ansys.pyensight import Launcher
    >>> session = Launcher.launch_session(ansys_installation='/ansys_inc/v222')

    """

    def __init__(self):
        """Initialize a Launcher object

        Notes
        -----
        Do not include the `self` parameter in the ``Parameters`` section.

        Examples
        --------
        >>> from ansys.pyensight import Launcher
        >>> example = Launcher()
        obj

        """
        self.session = None
        return None

    @staticmethod
    def get_install_directory(ansys_installation: Optional[str]) -> str:
        """Compute the Ansys distribution directory to use

        Args:
            ansys_installation (:obj:`str`, optional): None will default to
                the pre-built, default base directory.

        Returns:
            The validated installation directory

        Raises:
            RuntimeError: if the installation directory does not point to a
                valid EnSight installation
        """
        version = pyensight.__ansys_version__
        install_dir = f"/ansys_inc/v{version}"
        if platform.system().startswith("Wind"):
            install_dir = rf"C:\Program Files\ANSYS Inc\v{version}"
        if ansys_installation:
            install_dir = ansys_installation
        launch_file = os.path.join(install_dir, "CEI", "bin", "ensight")
        if not os.path.exists(launch_file):
            raise RuntimeError(f"Unable to detect an EnSight installation in: {install_dir}")
        return install_dir

    def launch_session(self, ansys_installation: Optional[str] = None) -> "pyensight.Session":
        """Initialize a Launcher object

        Args:
            ansys_installation (:obj:`str`, optional):
                Location of the ANSYS installation, including the version directory
                Default:  "C:\\Program Files\\ANSYS Inc\\v222"

        Returns:
            pyensight Session object

        """
        if self.session is None:
            self.session = pyensight.Session()

        # get the user selected installation directory
        ansys_installation = self.get_install_directory(ansys_installation)

        return self.session

    def close(self) -> bool:
        """Close the EnSight session that is connected to this Launcher instance

        Returns:
            True if successful, False otherwise

        """
        return True
