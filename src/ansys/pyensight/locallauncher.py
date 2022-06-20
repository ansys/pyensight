"""locallauncher module

The local launcher module provides pyensight with the ability to launch an
EnSight session using a local Ansys installation.

Examples:
    >>> from ansys.pyensight import LocalLauncher
    >>> session = LocalLauncher().start()
"""
import glob
import os.path
import platform
import shutil
import subprocess
import tempfile
import time
from typing import Optional
import uuid

from ansys import pyensight


class LocalLauncher(pyensight.Launcher):
    """Create a Session instance by launching a local copy of EnSight

    Launch a copy of EnSight locally that supports the gRPC interface.  Create and
    bind a Session instance to the created gRPC session.  Return that session.

    Args:
        ansys_installation:
            Location of the ANSYS installation, including the version
            directory Default: None (causes common locations to be scanned)
        application:
            The application to be launched. By default, "ensight", but
            "envision" is also available.

    Examples:
        >>> from ansys.pyensight import LocalLauncher
        >>> session = LocalLauncher(ansys_installation='/ansys_inc/v222').start()
    """

    def __init__(
        self, ansys_installation: Optional[str] = None, application: str = "ensight"
    ) -> None:
        super().__init__()

        # get the user selected installation directory
        self._install_path: str = self.get_cei_install_directory(ansys_installation)
        # Will this be ensight or envision
        self._application = application
        # EnSight session secret key
        self._secret_key: str = str(uuid.uuid1())
        # temporary directory served by websocketserver
        self._session_directory = tempfile.mkdtemp(prefix="pyensight_")
        # launched process ids
        self._ensight_pid = None
        self._websocketserver_pid = None

    @property
    def application(self):
        """Type of application to launch
        The application can be "ensight" or "envision"
        """
        return self._application

    def start(self) -> "pyensight.Session":
        """Start an EnSight session using the local ensight install
        Launch a copy of EnSight locally that supports the gRPC interface.  Create and
        bind a Session instance to the created gRPC session.  Return that session.

        Returns:
            pyensight Session object instance

        Raises:
            RuntimeError:
                if the necessary number of ports could not be allocated.
        """
        # gRPC port, VNC port, websocketserver ws, websocketserver html
        ports = self._find_unused_ports(4)
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
        exe = os.path.join(self._install_path, "bin", self._application)
        cmd = [exe, "-batch", "-grpc_server", str(ports[0])]
        vnc_url = f"vnc://%%3Frfb_port={ports[1]}%%26use_auth=0"
        cmd.extend(["-vnc", vnc_url])
        if is_windows:
            cmd[0] += ".bat"
        # cmd.append("-minimize_console")
        self._ensight_pid = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            cwd=self._session_directory,
            env=local_env,
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
            self._websocketserver_pid = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=self._session_directory,
                env=local_env,
                startupinfo=startupinfo,
            ).pid
        else:
            self._websocketserver_pid = subprocess.Popen(
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
        maximum_wait_secs = 120.0
        start_time = time.time()
        while (time.time() - start_time) < maximum_wait_secs:
            try:
                shutil.rmtree(self.session_directory)
                return
            except PermissionError:
                pass
            except Exception:
                raise
        raise RuntimeError(f"Unable to remove {self.session_directory} in {maximum_wait_secs}s")

    @staticmethod
    def get_cei_install_directory(ansys_installation: Optional[str]) -> str:
        """Compute the Ansys distribution CEI directory to use

        The returned directory will be the 'CEI' directory such that
        bin/ensight exists in that directory.  If the input is None,
        the PYENSIGHT_ANSYS_INSTALLATION environmental variable will
        be checked first.

        Args:
            ansys_installation:
                This is the pathname of the Ansys distribution to use.
                None will result in common locations to be scanned for a viable distribution.

        Returns:
            The validated installation directory (contains bin/ensight)

        Raises:
            RuntimeError:
                if the installation directory does not point to a
                valid EnSight installation
        """
        dirs_to_check = []
        if ansys_installation:
            dirs_to_check.append(os.path.join(ansys_installation, "CEI"))
            dirs_to_check.append(ansys_installation)
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
