"""Launcher module

The Launcher module allows pyensight to control the enshell launcher
capabilities to launch EnSight in multiple configurations, and to
connect to an existing EnSight session

Examples:

>>> from ansys.pyensight import LocalLauncher
>>> session = LocalLauncher().start()

"""
import abc
import atexit
import glob
import os.path
import platform
import shutil
import socket
import subprocess
import tempfile
import uuid
from typing import List
from typing import Optional

from ansys import pyensight


class Launcher:
    """EnSight Launcher base class

    A Launcher instance is used to start/end an EnSight session.  Specific subclasses
    handle different types of launching semantics.

    """

    def __init__(self) -> None:
        self._sessions = []

    def close(self, session: "pyensight.Session") -> None:
        """Shutdown the launched EnSight session

        Close all the associated sessions and then stop the launched EnSight instance.

        Raises:
            RuntimeError if the session was not launched by this launcher.
        """
        if session not in self._sessions:
            raise RuntimeError("Session not associated with this Launcher")
        self._sessions.remove(session)
        if self._sessions:
            return
        # if the session list is empty, stop the launcher
        self.stop()

    @abc.abstractmethod
    def start(self) -> "pyensight.session":
        """Base method for starting the actual session"""
        return

    @abc.abstractmethod
    def stop(self) -> None:
        """Base method for stopping a session initiated by start()

        Notes:
            The session object is responsible for making the EnSight 'Exit' and websocketserver
            calls.  This method can be used to clean up any additional resources being used
            by the launching method.
        """
        return

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
            The detected ports or None on failure
        """
        if avoid is None:
            avoid = []
        ports = list()

        # pick a starting port number
        start = os.getpid() % 64000
        # We will scan for 65530 ports unless end is specified
        port_mod = 65530
        end = start + port_mod - 1
        # walk the "virtual" port range
        for base_port in range(start, end + 1):
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
            result = sock.connect_ex(("127.0.0.1", port))
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


class LocalLauncher(Launcher):
    """Create a Session instance by launching a local copy of EnSight

    Launch a copy of EnSight locally that supports the gRPC interface.  Create and
    bind a Session instance to the created gRPC session.  Return that session.

    Args:
        ansys_installation: Location of the ANSYS installation, including the version
            directory Default:  None (causes common locations to be scanned)

    Examples:

    >>> from ansys.pyensight import LocalLauncher
    >>> session = LocalLauncher(ansys_installation='/ansys_inc/v222').start()

    """

    def __init__(self, ansys_installation: Optional[str] = None) -> None:
        super().__init__()

        # get the user selected installation directory
        self._install_path: str = self.get_cei_install_directory(ansys_installation)
        # EnSight session secret key
        self._secret_key: str = str(uuid.uuid1())
        # temporary directory
        self._session_directory: str = tempfile.mkdtemp(prefix="pyensight_")

    def start(self) -> "pyensight.Session":
        """Start an EnSight session using the local ensight install
        Launch a copy of EnSight locally that supports the gRPC interface.  Create and
        bind a Session instance to the created gRPC session.  Return that session.

        Returns:
            pyensight Session object instance

        Raises:
            RuntimeError: if the necessary number of ports could not be allocated.
        """
        # gRPC port, VNC port, websocketserver ws, websocketserver html
        ports = Launcher._find_unused_ports(4)
        if ports is None:
            raise RuntimeError("Unable to allocate local ports for EnSight session")
        is_windows = platform.system() == "Windows"

        # Launch EnSight
        # create the environmental variables
        local_env = os.environ.copy()
        local_env["ENSIGHT_SECURITY_TOKEN"] = self._secret_key
        local_env["WEBSOCKETSERVER_SECURITY_TOKEN"] = self._secret_key
        local_env["ENSIGHT_SESSION_TEMPDIR"] = self._session_directory

        # build the EnSight command
        exe = os.path.join(self._install_path, "bin", "ensight")
        cmd = [exe, "-batch", "-grpc_server", str(ports[0])]
        vnc_url = f"vnc://%%3Frfb_port={ports[1]}%%26use_auth=0"
        cmd.extend(["-vnc", vnc_url])
        if is_windows:
            cmd[0] += ".bat"
            cmd.append("-minimize_console")
            _ = subprocess.Popen(
                cmd, creationflags=8, close_fds=True, cwd=self._session_directory, env=local_env
            ).pid
        else:
            _ = subprocess.Popen(
                cmd, close_fds=True, cwd=self._session_directory, env=local_env
            ).pid

        # Launch websocketserver
        # find websocketserver script
        found_scripts = glob.glob(
            os.path.join(self._install_path, "nexus*", "nexus_launcher", "websocketserver.py")
        )
        if not found_scripts:
            raise RuntimeError("Unable to find websocketserver script")
        websocket_script = found_scripts[0]

        # build the commandline
        cmd = [os.path.join(self._install_path, "bin", "cpython"), websocket_script]
        if is_windows:
            cmd[0] += ".bat"
        cmd.extend(["--http_directory", self._session_directory])
        # http port
        cmd.extend(["--http_port", str(ports[2])])
        # vnc port
        cmd.extend(["--client_port", str(ports[1])])
        # websocket port
        cmd.append(str(ports[3]))
        if is_windows:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            _ = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=self._session_directory,
                env=local_env,
                startupinfo=startupinfo,
            ).pid
        else:
            _ = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=self._session_directory,
                close_fds=True,
                env=local_env,
            ).pid

        # build the session instance
        session = pyensight.Session(
            host="127.0.0.1",
            grpc_port=ports[0],
            html_port=ports[2],
            ws_port=ports[3],
            install_path=self._install_path,
            secret_key=self._secret_key,
        )
        session.launcher = self
        self._sessions.append(session)
        return session

    def stop(self) -> None:
        """Release any additional resources allocated during launching"""
        atexit.register(shutil.rmtree, self._session_directory)

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
