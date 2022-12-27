"""embeddedlauncher module

The embedded launcher module provides pyensight with the ability to connect
to an EnSight session from within that EnSight session.

Examples:
    >>> from ansys.pyensight import EmbeddedLauncher
    >>> session = EmbeddedLauncher().start()
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


class EmbeddedLauncher(pyensight.Launcher):
    """Create a Session instance connected to the hosting EnSight instance

    This class can only be used from the python interpreter embedded in an EnSight instance.
    The object will build a pyensight session that connects directly to the hosting instance.
    Note: the 'remote', image-based viewer is not available in this mode.

    Examples:
        ::

            from ansys.pyensight import EmbeddedLauncher
            session = EmbeddedLauncher().start()

    """

    def __init__(self, vnc_port: Optional[int] = None, secret_key: str = "") -> None:
        super().__init__()

        # Verify that we are running inside EnSight
        try:
            import ensight

            self._cei_home = ensight.version("home")
            self._cei_suffx = ensight.version("suffix")
        except ModuleNotFoundError:
            raise RuntimeError("This class can only be used from an EnSight embedded interpreter")

        # EnSight session secret key
        self._secret_key: str = secret_key
        # temporary directory served by websocketserver
        self._session_directory = None
        # launched process ids
        self._websocketserver_pid = None
        # If provided by the caller, the VNC port EnSight was launched with
        self._vnc_port = vnc_port
        # we will ask EnSight for this port or dynamically allocate one
        self._grpc_port = None
        # and websocketserver ports
        self._ws_ports = None

        # Is this EnSight running gRPC already?
        state, port, security_string = ensight.objs.core.grpc_server()
        if state:
            # gRPC is already running
            self._grpc_port = port
            self._secret_key = security_string
        else:
            # if VNC is specified and we are generating the secret, that cannot work
            if (not self._secret_key) and self._vnc_port:
                raise RuntimeError(
                    "A secret key must be specified if VNC option is used before gRPC is started"
                )
            self._secret_key = str(uuid.uuid1())
            # Start the gRPC server with secret key and get a new port
            state, port, _ = ensight.objs.core.grpc_server(
                start=1, port=0, security_string=self._secret_key
            )
            if not state:
                raise RuntimeError("Unable to start gRPC service")
            self._grpc_port = port

    def start(self) -> "pyensight.Session":
        """Start an EnSight session
        Connect a pyensight Session to the hosting EnSight instance.  If needed,
        start the gRPC instance and start a websocketserver instance.  Return that session.

        Returns:
            pyensight Session object instance

        Raises:
            RuntimeError:
                if the necessary number of ports could not be allocated or the hosting
                python instance is not EnSight.
        """
        if self._grpc_port is None:
            raise RuntimeError("No gRPC service running")
        if self._ws_ports is None:
            # session directory
            self.session_directory = tempfile.mkdtemp(prefix="pyensight_")

            # Two ports for websocketserver ws, websocketserver html
            # allocate them (0=HTTP, 1=WS)
            self._ws_ports = self._find_unused_ports(2)
            if self._ws_ports is None:
                raise RuntimeError("Unable to allocate local ports for EnSight session")
            is_windows = platform.system() == "Windows"

            # create the environmental variables
            local_env = os.environ.copy()
            local_env["ENSIGHT_SECURITY_TOKEN"] = self._secret_key
            local_env["WEBSOCKETSERVER_SECURITY_TOKEN"] = self._secret_key
            local_env["ENSIGHT_SESSION_TEMPDIR"] = self.session_directory

            # EnSight is already running, remember where...
            self._ensight_pid = os.getpid()

            # Launch websocketserver
            # find websocketserver script
            found_scripts = glob.glob(
                os.path.join(
                    self._cei_home,
                    f"nexus{self._cei_suffx}",
                    "nexus_launcher",
                    "websocketserver.py",
                )
            )
            if not found_scripts:
                raise RuntimeError("Unable to find websocketserver script")
            websocket_script = found_scripts[0]

            # build the commandline
            cmd = [
                os.path.join(self._cei_home, "bin", f"cpython{self._cei_suffx}"),
                websocket_script,
            ]
            if is_windows:
                cmd[0] += ".bat"
            cmd.extend(["--http_directory", self.session_directory])
            # http port
            cmd.extend(["--http_port", str(self._ws_ports[0])])
            # vnc port is optional
            if self._vnc_port:
                cmd.extend(["--client_port", str(self._vnc_port)])
            # EnVision sessions
            cmd.extend(["--local_session", "envision", "5"])
            # websocket port
            cmd.append(str(self._ws_ports[1]))
            if is_windows:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                self._websocketserver_pid = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=self.session_directory,
                    env=local_env,
                    startupinfo=startupinfo,
                ).pid
            else:
                self._websocketserver_pid = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=self.session_directory,
                    close_fds=True,
                    env=local_env,
                ).pid

        # build the session instance
        session = pyensight.Session(
            host="127.0.0.1",
            grpc_port=self._grpc_port,
            html_port=self._ws_ports[0],
            ws_port=self._ws_ports[1],
            install_path=self._cei_home,
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
                self._ws_ports = None
                return
            except PermissionError:
                pass
            except Exception:
                raise
        raise RuntimeError(f"Unable to remove {self.session_directory} in {maximum_wait_secs}s")
