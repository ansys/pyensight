# Copyright (C) 2022 - 2025 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

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
import warnings

import ansys.pyensight.core as pyensight
from ansys.pyensight.core.common import GRPC_WARNING_MESSAGE, find_unused_ports, grpc_version_check
from ansys.pyensight.core.launcher import Launcher
import ansys.pyensight.core.session
import psutil


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
    grpc_use_tcp_sockets :
        If using gRPC, and if True, then allow TCP Socket based connections
        instead of only local connections.
    grpc_allow_network_connections :
        If using gRPC and using TCP Socket based connections, listen on all networks.
    grpc_disable_tls :
        If using gRPC and using TCP Socket based connections, disable TLS.
    grpc_uds_pathname :
        If using gRPC and using Unix Domain Socket based connections, explicitly
        set the pathname to the shared UDS file instead of using the default.
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

    WARNING:
    Overriding the default values for these options: grpc_use_tcp_sockets, grpc_allow_network_connections,
    and grpc_disable_tls
    can possibly permit control of this computer and any data which resides on it.
    Modification of this configuration is not recommended.  Please see the
    documentation for your installed product for additional information.
    """

    def __init__(
        self,
        ansys_installation: Optional[str] = None,
        application: Optional[str] = "ensight",
        batch: bool = True,
        grpc_use_tcp_sockets: Optional[bool] = False,
        grpc_allow_network_connections: Optional[bool] = False,
        grpc_disable_tls: Optional[bool] = False,
        grpc_uds_pathname: Optional[str] = None,
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
        self._grpc_use_tcp_sockets = grpc_use_tcp_sockets
        self._grpc_allow_network_connections = grpc_allow_network_connections
        self._grpc_disable_tls = grpc_disable_tls
        self._grpc_uds_pathname = grpc_uds_pathname

    @property
    def application(self):
        """Type of app to launch. Options are ``ensight`` and ``envision``."""
        return self._application

    def launch_webui(self, version, popen_common):
        if os.environ.get("PYENSIGHT_FLUIDSONE_PATH"):
            fluids_one_path = os.environ["PYENSIGHT_FLUIDSONE_PATH"]
        else:
            awp_path = os.path.dirname(self._install_path)
            platf = "winx64" if self._is_windows() else "linx64"
            fluids_one_path = os.path.join(awp_path, "FluidsOne", "server", platf, "fluids_one")
            if self._is_windows():
                fluids_one_path += ".exe"
        cmd = [fluids_one_path, "--main-run-mode", "post"]
        path_to_webui = self._install_path
        # Dev environment
        path_to_webui_internal = os.path.join(
            path_to_webui, f"nexus{version}", f"ansys{version}", "ensight", "WebUI", "web", "ui"
        )
        # Ansys environment
        path_to_webui_ansys = os.path.join(os.path.dirname(path_to_webui), "FluidsOne", "web", "ui")
        path_to_webui = path_to_webui_internal
        if os.path.exists(path_to_webui_ansys):
            path_to_webui = path_to_webui_ansys
        cmd += ["--server-listen-port", str(self._ports[5])]
        cmd += ["--server-web-roots", path_to_webui]
        cmd += ["--ensight-grpc-port", str(self._ports[0])]
        cmd += ["--ensight-html-port", str(self._ports[2])]
        cmd += ["--ensight-ws-port", str(self._ports[3])]
        cmd += ["--ensight-session-directory", self._session_directory]
        cmd += ["--ensight-secret-key", self._secret_key]
        cmd += ["--main-show-gui", "'False'"]
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

    def _grpc_version_check(self):
        """Check if the gRPC security options apply to the EnSight install."""
        buildinfo = os.path.join(self._install_path, "BUILDINFO.txt")
        if not os.path.exists(buildinfo):
            if not os.path.exists(
                os.path.join(os.path.dirname(self._install_path), "licensingclient")
            ):
                # Dev installation. Assume the gRPC security options are available
                return True
            raise RuntimeError("Couldn't find BUILDINFO file, cannot check installation.")
        with open(buildinfo, "r") as buildinfo_file:
            text = buildinfo_file.read()
        internal_version, ensight_full_version = self._get_versionfrom_buildinfo(text)
        return grpc_version_check(internal_version, ensight_full_version)

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
        self._has_grpc_changes = self._grpc_version_check()
        if not self._has_grpc_changes:
            warnings.warn(GRPC_WARNING_MESSAGE)
        tmp_session = super().start()
        if tmp_session:
            return tmp_session
        if self._ports is None:
            # session directory and UUID
            self._secret_key = str(uuid.uuid1())
            self.session_directory = tempfile.mkdtemp(prefix="pyensight_")
            if (
                not self._grpc_uds_pathname
                and not self._grpc_use_tcp_sockets
                and not self._is_windows()
            ):
                self._grpc_uds_pathname = os.path.join(self.session_directory, "pyensight")

            # gRPC port, VNC port, websocketserver ws, websocketserver html
            to_avoid = self._find_ports_used_by_other_pyensight_and_ensight()
            num_ports = 5
            if self._launch_webui:  # port 6
                num_ports += 1
            if self._vtk_ws_port:  # port 6 or 7 depending on launch_webui
                num_ports += 1
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
            if self._has_grpc_changes:
                if self._grpc_use_tcp_sockets:
                    cmd.append("-grpc_use_tcp_sockets")
                if self._grpc_allow_network_connections:
                    cmd.append("-grpc_allow_network_connections")
                if self._grpc_disable_tls:
                    cmd.append("-grpc_disable_tls")
                if self._grpc_uds_pathname:
                    cmd.append("-grpc_uds_pathname")
                    cmd.append(self._grpc_uds_pathname)
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
                if not self._use_mpi:
                    cmd.append("-nservers")
                    cmd.append(str(int(self._use_sos)))
                else:
                    cmd.append(f"--np={int(self._use_sos)+1}")
                    cmd.append(f"--mpi={self._use_mpi}")
                    cmd.append(f"--ic={self._interconnect}")
                    hosts = ",".join(self._server_hosts)
                    cmd.append(f"--cnf={hosts}")
            if self._liben_rest:
                cmd.extend(["-rest_server", str(self._ports[2])])

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
            version = re.findall(r"nexus(\d+)", websocket_script)[0]
            # build the commandline
            if not self._liben_rest:
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
                    if self._has_grpc_changes:
                        if self._grpc_use_tcp_sockets:
                            cmd.append("--grpc_use_tcp_sockets")
                        if self._grpc_allow_network_connections:
                            cmd.append("--grpc_allow_network_connections")
                        if self._grpc_disable_tls:
                            cmd.append("--grpc_disable_tls")
                        if self._grpc_uds_pathname:
                            cmd.append("--grpc_uds_pathname")
                            cmd.append(self._grpc_uds_pathname)
                # EnVision sessions
                cmd.extend(["--local_session", "envision", "5"])
                if int(version) > 252 and self._rest_ws_separate_loops:
                    cmd.append("--separate_loops")
                cmd.extend(["--security_token", self._secret_key])
                # websocket port
                if int(version) > 252 and self._do_not_start_ws:
                    cmd.append("-1")
                else:
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
            grpc_use_tcp_sockets=self._grpc_use_tcp_sockets,
            grpc_allow_network_connections=self._grpc_allow_network_connections,
            grpc_disable_tls=self._grpc_disable_tls,
            grpc_uds_pathname=self._grpc_uds_pathname,
            html_port=self._ports[2],
            ws_port=self._ports[3],
            install_path=self._install_path,
            secret_key=self._secret_key,
            timeout=self._timeout,
            sos=use_sos,
            rest_api=self._enable_rest_api,
            webui_port=self._ports[5] if self._launch_webui else None,
            disable_grpc_options=not self._has_grpc_changes,
        )
        session.launcher = self
        self._sessions.append(session)
        if self._launch_webui:
            self.launch_webui(version, popen_common)
        return session

    @staticmethod
    def _kill_process_unix(pid):
        external_kill = ["kill", "-9", str(pid)]
        process = psutil.Popen(external_kill, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        process.wait()

    @staticmethod
    def _kill_process_windows(pid):
        external_kill = ["taskkill", "/F", "/PID", str(pid)]
        process = psutil.Popen(external_kill, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        process.wait()

    def _kill_process_by_pid(self, pid):
        if self._is_windows():
            self._kill_process_windows(pid)
        else:
            self._kill_process_unix(pid)

    def _kill_process_tree(self, pid):
        try:
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True):
                try:
                    self._kill_process_by_pid(child.pid)
                    child.kill()
                except (psutil.AccessDenied, psutil.ZombieProcess, OSError, psutil.NoSuchProcess):
                    continue
            self._kill_process_by_pid(parent.pid)
            parent.kill()
        except (psutil.AccessDenied, psutil.ZombieProcess, OSError, psutil.NoSuchProcess):
            pass

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
            except FileNotFoundError:
                pass
            except Exception:
                raise
        raise RuntimeError(f"Unable to remove {self.session_directory} in {maximum_wait_secs}s")

    def close(self, session):
        """Shut down the launched EnSight session.

        This method closes all associated sessions and then stops the
        launched EnSight instance.

        Parameters
        ----------
        session : ``pyensight.Session``
            Session to close.

        Raises
        ------
        RuntimeError
            If the session was not launched by this launcher.

        """
        if self._websocketserver_pid:
            self._kill_process_tree(self._websocketserver_pid)
        return super().close(session)

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
