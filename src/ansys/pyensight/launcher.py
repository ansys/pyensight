"""Launcher module

The Launcher module allows pyensight to control the enshell launcher
capabilities to launch EnSight in multiple configurations, and to
connect to an existing EnSight session

Examples
--------
>>> from ansys.pyensight import Launcher
>>> session = Launcher.launch_local_session()

"""
import os.path
import platform
import socket
import subprocess
import uuid
from typing import Optional, List

from ansys import pyensight


class Launcher:
    """Class to access EnSight Launcher

    The Launcher instance allows the user to launch an EnSight session
    or to connect to an existing one

    Examples
    --------

    >>> from ansys.pyensight import Launcher
    >>> session = Launcher.launch_local_session(ansys_installation='/ansys_inc/v222')

    """

    def __init__(self) -> None:
        self._sessions = []

    @staticmethod
    def get_cei_install_directory(ansys_installation: Optional[str]) -> str:
        """Compute the Ansys distribution CEI directory to use

        The returned directory will be the 'CEI' directory such that
        bin/ensight exists in that directory.  If the input is None,
        the PYENSIGHT_ANSYS_INSTALLATION environmental variable will
        be checked first.

        Args:
            ansys_installation: This is the pathname of the Ansys distribution to use.
                None will result in common locations to be scanned for a viable distribution.

        Returns:
            The validated installation directory (contains bin/ensight)

        Raises:
            RuntimeError: if the installation directory does not point to a
                valid EnSight installation
        """
        dirs_to_check = []
        if ansys_installation:
            dirs_to_check.append(os.path.join(ansys_installation, "CEI"))
        else:
            if "PYENSIGHT_ANSYS_INSTALLATION" in os.environ:
                dirs_to_check.append(os.environ["PYENSIGHT_ANSYS_INSTALLATION"])
            version = pyensight.__ansys_version__
            if f"AWP_ROOT{version}" in os.environ:
                dirs_to_check.append(os.path.join(os.environ[f"AWP_ROOT{version}"], "CEI"))
            install_dir = f"/ansys_inc/v{version}/CEI"
            if platform.system().startswith("Wind"):
                install_dir = rf"C:\Program Files\ANSYS Inc\v{version}\CEI"
            dirs_to_check.append(install_dir)

        for install_dir in dirs_to_check:
            launch_file = os.path.join(install_dir, "bin", "ensight")
            if os.path.exists(launch_file):
                return install_dir

        raise RuntimeError(f"Unable to detect an EnSight installation in: {dirs_to_check}")

    @staticmethod
    def launch_local_session(ansys_installation: Optional[str] = None) -> "pyensight.Session":
        """Create a Session instance by launching a local copy of EnSight

        Launch a copy of EnSight locally that supports the gRPC interface.  Create and
        bind a Session instance to the created gRPC session.  Return that session.

        Args:
            ansys_installation: Location of the ANSYS installation, including the version
                directory Default:  None (causes common locations to be scanned)

        Returns:
            pyensight Session object instance

        Raises:
            RuntimeError: if the necessary number of ports could not be allocated.
        """
        # get the user selected installation directory
        install_path = Launcher.get_cei_install_directory(ansys_installation)

        # gRPC port, VNC port, websocketserver ws, websocketserver html
        ports = Launcher._find_unused_ports(4)
        if ports is None:
            raise RuntimeError("Unable to allocate local ports for EnSight session")
        secret_key = str(uuid.uuid1())

        # Launch EnSight
        local_env = os.environ.copy()
        local_env["ENSIGHT_SECURITY_TOKEN"] = secret_key
        exe = os.path.join("bin", "ensight")
        cmd = [exe, "-batch", "-grpc_server", str(ports[0])]
        vnc_url = f"vnc://%%3Frfb_port={ports[1]}%%26use_auth=0"
        cmd.extend(["-vnc", vnc_url])
        if platform.system() == "Windows":
            cmd[0] += ".bat"
            cmd.append("-minimize_console")
            pid = subprocess.Popen(cmd, creationflags=8, close_fds=True, env=local_env).pid
        else:
            pid = subprocess.Popen(exe, close_fds=True, env=local_env).pid

        # Launch websocketserver

        # build the session instance
        session = pyensight.Session(
            host="127.0.0.1",
            grpc_port=ports[0],
            html_port=ports[2],
            ws_port=ports[3],
            install_path=install_path,
            secret_key=secret_key,
        )
        session.shutdown = True
        return session

    @staticmethod
    def _find_unused_ports(count: int, avoid: Optional[List[int]] = None) -> Optional[List[int]]:
        """Find "count" unused ports on the host system

        A port is considered unused if it does not respond to a "connect" attempt.  Walk
        the ports from 'start' to 'end' looking for unused ports and avoiding any ports
        in the 'avoid' list.  Stop once the desired number of ports have been
        found.  If an insufficient number of ports were found, return None.

        Args:
            count: number of unused ports to find
            avoid: an optional list of ports not to check

        Returns:
            the detected ports or None on failure
        """
        if avoid is None:
            avoid = []
        ports = list()

        # pick a starting port number
        start = (os.getpid() % 64000)
        # We will scan for 65530 ports unless end is specified
        port_mod = 65530
        end = start + port_mod - 1
        # walk the "virtual" port range
        for base_port in range(start, end+1):
            # Map to physical port range
            # There have been some issues with 65534+ so we stop at 65530
            port = base_port % port_mod
            # port 0 is special
            if port == 0:
                continue
            # avoid admin ports
            if port < 1024:
                continue
            # are we supposed to skip this one?
            if port in avoid:
                continue
            # is anyone listening?
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', port))
            if result != 0:
                ports.append(port)
            else:
                sock.close()
            if len(ports) >= count:
                return ports
        # in case we failed...
        if len(ports) < count:
            return None
        return ports
