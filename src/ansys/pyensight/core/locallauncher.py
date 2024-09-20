"""Local Launcher module.

The Local Launcher module provides PyEnSight with the ability to launch an
EnSight :class:`Session<ansys.pyensight.core.Session>` instance using a
local Ansys installation.

Examples:
>>> from ansys.pyensight.core import LocalLauncher
>>> session = LocalLauncher().start()
"""
import glob
import logging
import os.path
import platform
import re
import shutil
import subprocess
import tempfile
import time
from typing import Optional
import uuid

import ansys.pyensight.core as pyensight
from ansys.pyensight.core.common import find_unused_ports
from ansys.pyensight.core.launcher import Launcher
import ansys.pyensight.core.session


class LocalLauncher(Launcher):
    """Creates a ``Session`` instance by launching a local copy of EnSight.

    This class allows you to launch locally a copy of EnSight that supports the
    gRPC interface.  It creates and binds a :class:`Session<ansys.pyensight.core.Session>`
    instance to the created gRPC session and returns that instance.

    Parameters
    ----------
    ansys_installation : str, optional
        Path to the local Ansys installation, including the version
        directory. The default is ``None``, in which case common locations
        are scanned to detect the latest local Ansys installation. The
        ``PYENSIGHT_ANSYS_INSTALLATION`` environmental variable is checked first.
    application : str, optional
        App to launch. The default is ``ensight``, but ``envision`` is
        also an option.
    batch : bool, optional
        Whether to run EnSight (or EnVision) in batch mode. The default
        is ``True``, in which case the full GUI is not presented.
    timeout : float, optional
        Number of seconds to try a gRPC connection before giving up.
        This parameter is defined on the parent ``Launcher`` class,
        where the default is ``120``.
    use_egl : bool, optional
        Whether to use EGL hardware for accelerated graphics. The platform
        must be able to support this hardware. This parameter is defined on
        the parent ``Launcher`` class, where the default is ``False``.
    use_sos : int, optional
        Number of EnSight servers to use for SOS (Server of Server) mode.
        This parameter is defined on the parent ``Launcher`` class, where
        the default is ``None``, in which case SOS mode is not used.
    additional_command_line_options: list, optional
        Additional command line options to be used to launch EnSight.

    Examples
    --------
    >>> from ansys.pyensight.core import LocalLauncher
    >>> # Create one EnSight session
    >>> session1 = LocalLauncher(ansys_installation='/ansys_inc/v232').start()
    >>> # Create a second session (a new LocalLauncher instance is required)
    >>> session2 = LocalLauncher(ansys_installation='/ansys_inc/v232').start()

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
        self._webui_pid = None
        # and ports
        self._ports = None
        # Are we running the instance in batch
        self._batch = batch

    @property
    def application(self):
        """Type of app to launch. Options are ``ensight`` and ``envision``."""
        return self._application

    def launch_webui(self, cpython, webui_script, popen_common):
        cmd = [cpython]
        cmd += [webui_script]
        version = re.findall(r"nexus(\d+)", webui_script)[0]
        path_to_webui = self._install_path
        path_to_webui = os.path.join(
            path_to_webui, f"nexus{version}", f"ansys{version}", "ensight", "WebUI", "web", "ui"
        )
        cmd += ["--server-listen-port", str(self._ports[5])]
        cmd += ["--server-web-roots", path_to_webui]
        cmd += ["--ensight-grpc-port", str(self._ports[0])]
        cmd += ["--ensight-html-port", str(self._ports[2])]
        cmd += ["--ensight-ws-port", str(self._ports[3])]
        cmd += ["--ensight-session-directory", self._session_directory]
        cmd += ["--ensight-secret-key", self._secret_key]
        if "PYENSIGHT_DEBUG" in os.environ:
            try:
                if int(os.environ["PYENSIGHT_DEBUG"]) > 0:
                    del popen_common["stdout"]
                    del popen_common["stderr"]
            except (ValueError, KeyError):
                pass
        popen_common["env"].update(
            {
                "SIMBA_WEBSERVER_TOKEN": self._secret_key,
                "FLUENT_WEBSERVER_TOKEN": self._secret_key,
            }
        )
        self._webui_pid = subprocess.Popen(cmd, **popen_common).pid

    def start(self) -> "pyensight.Session":
        """Start an EnSight session using the local EnSight installation.

        This method launches a copy of EnSight locally that supports the
        gRPC interface. It creates and binds a ``Session`` instance to the
        created gRPC session and returns that session.

        Returns
        -------
        obj
            PyEnSight ``Session`` object instance.

        Raises
        ------
        RuntimeError:
            If the necessary number of ports could not be allocated.
        """
        tmp_session = super().start()
        if tmp_session:
            return tmp_session
        if self._ports is None:
            # session directory and UUID
            self._secret_key = str(uuid.uuid1())
            self.session_directory = tempfile.mkdtemp(prefix="pyensight_")

            # gRPC port, VNC port, websocketserver ws, websocketserver html
            to_avoid = self._find_ports_used_by_other_pyensight_and_ensight()
            num_ports = 5
            if self._launch_webui:
                num_ports = 6
            self._ports = find_unused_ports(num_ports, avoid=to_avoid)
            if self._ports is None:
                raise RuntimeError("Unable to allocate local ports for EnSight session")
            is_windows = self._is_windows()

            # Launch EnSight
            # create the environmental variables
            local_env = os.environ.copy()
            if not local_env.get("ENSIGHT_GRPC_DISABLE_SECURITY_TOKEN"):
                local_env["ENSIGHT_SECURITY_TOKEN"] = self._secret_key
            local_env["WEBSOCKETSERVER_SECURITY_TOKEN"] = self._secret_key
            local_env["ENSIGHT_SESSION_TEMPDIR"] = self.session_directory
            # If for some reason, the ENSIGHT_ANSYS_LAUNCH is set previously,
            # honor that value, otherwise set it to "pyensight".  This allows
            # for an environmental setup to set the value to something else
            # (e.g. their "app").
            if "ENSIGHT_ANSYS_LAUNCH" not in local_env:
                local_env["ENSIGHT_ANSYS_LAUNCH"] = "pyensight"

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
            cmd.extend(["-ports", str(self._ports[4])])
            if self._additional_command_line_options:
                cmd.extend(self._additional_command_line_options)

            use_egl = self._use_egl()

            # to aid in debugging, PYENSIGHT_DEBUG can be set to a non-zero integer
            popen_common = dict(
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=self.session_directory,
                env=local_env,
            )
            if "PYENSIGHT_DEBUG" in os.environ:
                try:
                    if int(os.environ["PYENSIGHT_DEBUG"]) > 0:
                        del popen_common["stdout"]
                        del popen_common["stderr"]
                except ValueError:
                    pass

            if is_windows:
                cmd[0] += ".bat"
            if use_egl:
                cmd.append("-egl")
            if self._use_sos:
                cmd.append("-sos")
                cmd.append("-nservers")
                cmd.append(str(int(self._use_sos)))
            # cmd.append("-minimize_console")
            logging.debug(f"Starting EnSight with : {cmd}\n")
            self._ensight_pid = subprocess.Popen(cmd, **popen_common).pid

            # Launch websocketserver

            # find websocketserver script
            found_scripts = glob.glob(
                os.path.join(self._install_path, "nexus*", "nexus_launcher", "websocketserver.py")
            )
            if not found_scripts:
                raise RuntimeError("Unable to find websocketserver script")
            # If more than one nexus directory is found, find the one that corresponds
            # to the version that should be used. Otherwise, just take the first one found.
            # This is likely to only happen for developer installations or build areas.
            idx = 0
            try:
                found_scripts_len = len(found_scripts)
                if found_scripts_len > 1:
                    version_str = str(pyensight.__ansys_version__)
                    for i in range(found_scripts_len):
                        if version_str in found_scripts[i]:
                            idx = i
                            break
            except Exception:
                pass
            websocket_script = found_scripts[idx]
            webui_script = websocket_script.replace("websocketserver.py", "webui_launcher.py")
            # build the commandline
            cmd = [os.path.join(self._install_path, "bin", "cpython"), websocket_script]
            if is_windows:
                cmd[0] += ".bat"
            ensight_python = cmd[0]
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
            logging.debug(f"Starting WSS: {cmd}\n")
            if is_windows:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                popen_common["startupinfo"] = startupinfo
            self._websocketserver_pid = subprocess.Popen(cmd, **popen_common).pid

        # build the session instance
        logging.debug(
            f"Creating session with ports for grpc:{self._ports[0]}\n"
            + f"html:{self._ports[2]} ws:{self._ports[3]}\n"
            + f"key:{self._secret_key}\n"
        )
        use_sos = False
        if self._use_sos:
            use_sos = True

        # need to use Session like this for mock testing this class
        session = ansys.pyensight.core.session.Session(
            host="127.0.0.1",
            grpc_port=self._ports[0],
            html_port=self._ports[2],
            ws_port=self._ports[3],
            install_path=self._install_path,
            secret_key=self._secret_key,
            timeout=self._timeout,
            sos=use_sos,
            rest_api=self._enable_rest_api,
            webui_port=self._ports[5] if self._launch_webui else None,
        )
        session.launcher = self
        self._sessions.append(session)

        if self._launch_webui:
            self.launch_webui(ensight_python, webui_script, popen_common)
        return session

    def stop(self) -> None:
        """Release any additional resources allocated during launching."""
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
        """Get the Ansys distribution CEI directory to use.

        Parameters
        ----------
        ansys_installation : str, optional
            Path to the local Ansys installation, including the version
            directory. The default is ``None``, in which case common locations
            are scanned to detect the latest local Ansys installation. The
            ``PYENSIGHT_ANSYS_INSTALLATION`` environmental variable is checked first.

        Returns
        -------
        str
            Validated installation directory, which contains ``bin/ensight``.

        Raises
        ------
        RuntimeError:
            If the installation directory does not point to a
            valid EnSight installation.
        """
        dirs_to_check = []
        if ansys_installation:
            # User passed directory
            dirs_to_check.append(os.path.join(ansys_installation, "CEI"))
            dirs_to_check.append(ansys_installation)
        else:
            # Environmental variable
            if "PYENSIGHT_ANSYS_INSTALLATION" in os.environ:
                env_inst = os.environ["PYENSIGHT_ANSYS_INSTALLATION"]
                dirs_to_check.append(env_inst)
                # Note: PYENSIGHT_ANSYS_INSTALLATION is designed for devel builds
                # where there is no CEI directory, but for folks using it in other
                # ways, we'll add that one too, just in case.
                dirs_to_check.append(os.path.join(env_inst, "CEI"))
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
        """Check if the system supports the EGL launch.

        Returns
        -------
        bool
            ``True`` if the system supports the EGL launch, ``False`` otherwise.
        """
        if self._is_windows():
            return False
        egl_test_path = os.path.join(self._install_path, "bin", "cei_egltest")
        egl_proc = subprocess.Popen([egl_test_path], stdout=subprocess.PIPE)
        _, _ = egl_proc.communicate()
        if egl_proc.returncode == 0:
            return True
        return False
