"""locallauncher module

The local launcher module provides pyensight with the ability to launch an
EnSight session using a local Ansys installation.

Examples:
    >>> from ansys.pyensight.core import LocalLauncher
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

import ansys.pyensight.core as pyensight
from ansys.pyensight.core import Launcher


class LocalLauncher(Launcher):
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
        batch:
            By default, the EnSight/EnVision instance will run in batch mode.
            If batch is set to True, the full GUI will not be presented.
        timeout:
            In some cases where the EnSight session can take a significant amount of
            timme to start up, this is the number of seconds to wait before failing
            the connection.  The default is 120.0.
        use_egl:
            If True, EGL hardware accelerated graphics will be used. The platform
            must be able to support it.
        use_sos:
            If None, don't use SOS. Otherwise, it's the number of EnSight Servers to use (int).

    Examples:
        ::

            from ansys.pyensight.core import LocalLauncher
            # Create one EnSight session
            session1 = LocalLauncher(ansys_installation='/ansys_inc/v232').start()
            # Create a second session (a new LocalLauncher instance is required)
            session2 = LocalLauncher(ansys_installation='/ansys_inc/v232').start()
    """

    def __init__(
        self,
        ansys_installation: Optional[str] = None,
        application: Optional[str] = "ensight",
        batch: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        # get the user selected installation directory
        self._install_path: str = self.get_cei_install_directory(ansys_installation)
        # Will this be ensight or envision
        self._application = application
        # EnSight session secret key
        self._secret_key: str = ""
        # temporary directory served by websocketserver
        self._session_directory = None
        # launched process ids
        self._ensight_pid = None
        self._websocketserver_pid = None
        # and ports
        self._ports = None
        # Are we running the instance in batch
        self._batch = batch

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

        Args:
            host:
                Optional hostname on which the EnSight gRPC service is running

        Returns:
            pyensight Session object instance

        Raises:
            RuntimeError:
                if the necessary number of ports could not be allocated.
        """
        tmp_session = super().start()
        if tmp_session:
            return tmp_session
        if self._ports is None:
            # session directory and UUID
            self._secret_key = str(uuid.uuid1())
            self.session_directory = tempfile.mkdtemp(prefix="pyensight_")

            # gRPC port, VNC port, websocketserver ws, websocketserver html
            self._ports = self._find_unused_ports(4)
            if self._ports is None:
                raise RuntimeError("Unable to allocate local ports for EnSight session")
            is_windows = self._is_windows()

            # Launch EnSight
            # create the environmental variables
            local_env = os.environ.copy()
            local_env["ENSIGHT_SECURITY_TOKEN"] = self._secret_key
            local_env["WEBSOCKETSERVER_SECURITY_TOKEN"] = self._secret_key
            local_env["ENSIGHT_SESSION_TEMPDIR"] = self.session_directory

            # build the EnSight command
            exe = os.path.join(self._install_path, "bin", self.application)
            cmd = [exe]
            if self._batch:
                cmd.append("-batch")
            else:
                cmd.append("-no_start_screen")
            cmd.extend(["-grpc_server", str(self._ports[0])])
            vnc_url = f"vnc://%%3Frfb_port={self._ports[1]}%%26use_auth=0"
            cmd.extend(["-vnc", vnc_url])

            use_egl = self._use_egl()

            if is_windows:
                cmd[0] += ".bat"
            if use_egl:
                cmd.append("-egl")
            if self._use_sos:
                cmd.append("-sos")
                cmd.append("-nservers")
                cmd.append(str(int(self._use_sos)))
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
            cmd.extend(["--http_directory", self.session_directory])
            # http port
            cmd.extend(["--http_port", str(self._ports[2])])
            # vnc port
            cmd.extend(["--client_port", str(self._ports[1])])
            if self._enable_rest_api:
                # grpc port
                cmd.extend(["--grpc_port", str(self._ports[0])])
            # EnVision sessions
            cmd.extend(["--local_session", "envision", "5"])
            # websocket port
            cmd.append(str(self._ports[3]))
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
            grpc_port=self._ports[0],
            html_port=self._ports[2],
            ws_port=self._ports[3],
            install_path=self._install_path,
            secret_key=self._secret_key,
            timeout=self._timeout,
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
                self._ports = None
                super().stop()
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
            # User passed directory
            dirs_to_check.append(os.path.join(ansys_installation, "CEI"))
            dirs_to_check.append(ansys_installation)
        else:
            # Environmental variable
            if "PYENSIGHT_ANSYS_INSTALLATION" in os.environ:
                dirs_to_check.append(os.environ["PYENSIGHT_ANSYS_INSTALLATION"])
            # 'enve' home directory (running in local distro)
            try:
                import enve

                dirs_to_check.append(enve.home())
            except ModuleNotFoundError:
                pass
            # Look for Ansys install using target version number
            version = pyensight.__ansys_version__
            if f"AWP_ROOT{version}" in os.environ:
                dirs_to_check.append(os.path.join(os.environ[f"AWP_ROOT{version}"], "CEI"))
            # Common, default install locations
            install_dir = f"/ansys_inc/v{version}/CEI"
            if platform.system().startswith("Wind"):
                install_dir = rf"C:\Program Files\ANSYS Inc\v{version}\CEI"
            dirs_to_check.append(install_dir)

        for install_dir in dirs_to_check:
            launch_file = os.path.join(install_dir, "bin", "ensight")
            if os.path.exists(launch_file):
                return install_dir

        raise RuntimeError(f"Unable to detect an EnSight installation in: {dirs_to_check}")

    def _is_system_egl_capable(self) -> bool:
        """Return True if the system supports the EGL launch.

        Returns:
            A bool value that is True if the system supports the EGL launch.
        """
        if self._is_windows():
            return False
        egl_test_path = os.path.join(self._install_path, "bin", "cei_egltest")
        egl_proc = subprocess.Popen([egl_test_path], stdout=subprocess.PIPE)
        _, _ = egl_proc.communicate()
        if egl_proc.returncode == 0:
            return True
        return False
