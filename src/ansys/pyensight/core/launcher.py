"""Launcher module.

The Launcher module provides a base class responsible for managing an EnSight
:class:`Session<ansys.pyensight.core.Session>` instance. Subclasses of the
class implement specific launching paradigms.

Examples:
    ::

        from ansys.pyensight.core import LocalLauncher
        session = LocalLauncher().start()

"""
import os.path
import platform
import re
from typing import TYPE_CHECKING, Dict, List, Optional
import warnings

import psutil
import requests

if TYPE_CHECKING:
    from ansys.pyensight.core import Session

# Don't remove this line.  The idna encoding
# is used by getaddrinfo when dealing with unicode hostnames,
# and in some cases, there appears to be a race condition
# where threads will get a LookupError on getaddrinfo() saying
# that the encoding doesn't exist. Using the idna encoding before
# running any CLI code (and any threads it may create) ensures that
# the encodings.idna is imported and registered in the codecs registry,
# which will stop the LookupErrors from happening.
# See: https://bugs.python.org/issue29288
"".encode("idna")

# The user doesn't know "eth" and "ib" what they mean. Use more meaningful
# keywords.
INTERCONNECT_MAP = {"ethernet": "eth", "infiniband": "ib"}

MPI_TYPES = ["intel2018", "intel2021", "openmpi"]


class Launcher:
    """Provides the EnSight ``Launcher`` base class.

    A ``Launcher`` instance is used to start and end an EnSight session.
    Specific subclasses handle different types of launching semantics.
    A launcher can create only a single EnSight instance. If you  need to
    have more than one EnSight instance, a new launcher instance is required.

    Parameters
    ----------
    timeout : float, optional
        Number of seconds to try a gRPC connection before giving up.
        The default is ``120``.
    use_egl : bool, optional
        Whether to use EGL hardware for accelerated graphics. The platform
        must be able to support this hardware. The default is ``False``.
    use_sos : int, optional
        Number of EnSight servers to use for SOS (Server of Server) mode.
        The default is ``None``, in which case SOS mode is not used.
    enable_rest_api : bool, optional
        Whether to enable the EnSight REST API. The default is ``False``.
        This parameter is supported in EnSight 2024 R1 and later.
    additional_command_line_options: list, optional
        Additional command line options to be used to launch EnSight.
        Please note, when using DockerLauncher, arguments that contain spaces
        are not supported.
    launch_web_ui : bool, optional
        Whether to launch the webUI from EnSight
    use_mpi: str, optional
        If set, EnSight will be launched with the MPI type selected. The valid
        values depend on the EnSight version to be used. The user can see
        the specific list starting the EnSight Launcher manually and specifying the options
        to launch EnSight in parallel and MPI. Here are reported the values for releases
        2024R2 and 2025R1.

        =================== =========================================
        Release             Valid MPI Types
        =================== =========================================
        2024R2              intel2021, intel2018, openmpi
        2025R1              intel2021, intel2018, openmpi
        =================== =========================================

        The remote nodes must be Linux nodes.
        This option is valid only if a LocalLauncher is used.
    interconnet: str, optional
        If set, EnSight will be launched with the MPI Interconnect selected. Valid values
        are "ethernet", "infiniband". It requires use_mpi to be set.
        If use_mpi is set and interconnect is not, "ethernet" will be used.
        This option is valid only if a LocalLauncher is used.
    server_hosts: List[str], optional
        A list of hostnames where the server processes should be spawned on when MPI is selected.
        If use_mpi is set and server_hosts not, it will default to "localhost".
        This option is valid only if a LocalLauncher is used.
    """

    def __init__(
        self,
        timeout: float = 120.0,
        use_egl: bool = False,
        use_sos: Optional[int] = None,
        enable_rest_api: bool = False,
        additional_command_line_options: Optional[List] = None,
        launch_webui: bool = False,
        use_mpi: Optional[str] = None,
        interconnect: Optional[str] = None,
        server_hosts: Optional[List[str]] = None,
    ) -> None:
        self._timeout = timeout
        self._use_egl_param_val: bool = use_egl
        self._use_sos = use_sos
        self._use_mpi = use_mpi
        self._interconnect = interconnect
        if self._use_mpi and self._use_mpi not in MPI_TYPES:
            raise RuntimeError(f"{self._use_mpi} is not a valid MPI option.")
        if self._use_mpi and not self._interconnect:
            self._interconnect = "ethernet"
        if self._interconnect:
            if self._interconnect not in list(INTERCONNECT_MAP.values()):
                raise RuntimeError(f"{self._interconnect} is not a valid MPI interconnect option.")
            self._interconnect = INTERCONNECT_MAP.get(self._interconnect)
        self._server_hosts = server_hosts
        if self._use_mpi and not self._server_hosts:
            self._server_hosts = ["localhost"]
        self._enable_rest_api = enable_rest_api

        self._sessions: List[Session] = []
        self._session_directory: str = "."

        self._is_egl_capable: Optional[bool] = None
        self._egl_env_val: Optional[bool] = None
        egl_env = os.environ.get("PYENSIGHT_FORCE_ENSIGHT_EGL")
        if egl_env is not None:
            if egl_env == "1":  # pragma: no cover
                self._egl_env_val = True  # pragma: no cover
            else:
                self._egl_env_val = False
        # a dict of any optional launcher specific query parameters for URLs
        self._query_parameters: Dict[str, str] = {}
        self._additional_command_line_options = additional_command_line_options
        self._launch_webui = launch_webui

    @property
    def session_directory(self) -> str:
        """Root directory for HTML files.

        The contents of this directory can be accessed at ``hostname:port``.
        """
        return self._session_directory

    @session_directory.setter
    def session_directory(self, value: str):
        self._session_directory = value

    def close(self, session: "Session") -> None:
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
        if session not in self._sessions:
            raise RuntimeError("Session not associated with this Launcher")
        self._sessions.remove(session)
        if self._sessions:
            # stop the grpc session interface
            session.grpc.shutdown(stop_ensight=False)
            return

        # if the session list is empty, stop the EnSight instance (via session grpc interface)
        session.grpc.shutdown(stop_ensight=True, force=True)

        # stop the websocketserver instance
        url = f"http://{session.hostname}:{session.html_port}/v1/stop"
        if session.secret_key:  # pragma: no cover
            url += f"?security_token={session.secret_key}"
        _ = requests.get(url)

        # Stop the launcher instance
        self.stop()

    def start(self) -> Optional["Session"]:
        """Start a session using the current launcher

        The start() method will only allocate a single instance of
        a Session object.  If called a second time, return the
        result of the first call.

        Returns
        -------
        If start() has been called previously, return that session
        and emit a warning.   If start() has not been called, return None.

        """
        if len(self._sessions):
            msg = "The launcher start() method may only be called once. "
            msg += "Create a new launcher instance to start a new EnSight instance."
            warnings.warn(msg, RuntimeWarning)
            return self._sessions[0]
        return None

    def stop(self) -> None:
        """Base method for stopping a session initiated by start()

        Notes
        -----
            The session object is responsible for making the EnSight 'Exit' and websocketserver
            calls. This method can be used to clean up any additional resources being used
            by the launching method.
        """
        return

    def _find_ports_used_by_other_pyensight_and_ensight(self):
        """Find ports to avoid when looking for empty ports.

        The ports are found iterating the current processes and
        looking for PyEnSight/EnSight sessions and their command
        lines.
        """
        pyensight_found = []
        ensight_found = []
        for process in psutil.process_iter():
            try:
                process_cmdline = process.cmdline()
            except (psutil.AccessDenied, psutil.ZombieProcess, OSError, psutil.NoSuchProcess):
                continue
            if not process_cmdline:
                continue
            if len(process_cmdline) > 1:
                if "websocketserver.py" in os.path.basename(process_cmdline[1]):
                    pyensight_found.append(process_cmdline)
            if any(["ensight" in os.path.basename(x) for x in process_cmdline]):
                if any([x == "-ports" for x in process_cmdline]):
                    ensight_found.append(process_cmdline)
        ports = []
        for command_line in pyensight_found:
            for command in command_line:
                if re.match(r"^\d{4,5}$", command):
                    ports.append(int(command))
        for command_line in ensight_found:
            idx = command_line.index("-ports") + 1
            ports.append(int(command_line[idx]))
        return list(set(ports))

    def _use_egl(self) -> bool:
        """Return True if the system supports the EGL and if EGL was desired.

        Returns
        -------
        bool
            A bool value that is True if we should use EGL.

        """
        if self._is_egl_capable is None:
            # if we haven't checked with the subclasss if the system can do EGL
            self._is_egl_capable = self._is_system_egl_capable()

        if self._is_egl_capable is False:
            # if the system can't do it, return False now
            return False

        if self._egl_env_val is not None:  # pragma: no cover
            # if the environment variable was set, that overrides the constructor option
            return self._egl_env_val

        # otherwise, use the arg passed to the constructor
        return self._use_egl_param_val  # pragma: no cover

    def _is_system_egl_capable(self) -> bool:  # pragma: no cover
        """Return True if the system supports the EGL launch.

        Returns
        -------
        bool
            A bool value that is True if the system supports the EGL launch.

        """
        raise RuntimeError("Unsupported method for this configuration")

    def _is_windows(self) -> bool:
        """Return True if it is Windows

        Returns
        -------
        bool
            a bool that is True if the platform is Windows

        """
        return platform.system() == "Windows"

    def _get_query_parameters(self) -> Dict[str, str]:
        """Return optional http query parameters as a dict.
        It may be empty if there are None.
        If query parameters exist, they should be added to any
        http/https URL intended for the WSS web server.
        This is used by things such as Ansys Lab.

        Returns
        -------
        dict
            query parameters that should be appended to any queries
        """
        return self._query_parameters

    def _add_query_parameters(self, params: Dict[str, str]) -> None:
        """Add query parameters supplied by params to the
        overall dict of query parameters.

        Parameters
        ----------
        params: dict :
            query parameters to add to overall dict
        """
        for item, value in params.items():  # pragma: no cover
            self._query_parameters[item] = value  # pragma: no cover

    def _delete_query_parameters(self, params: List[str]) -> None:
        """Delete query parameters supplied by params from the
        overall dict of query parameters.

        Parameters
        ----------
        params: list :
            query parameters to delete from the overall dict
        """
        for item in params:  # pragma: no cover
            try:  # pragma: no cover
                del self._query_parameters[item]  # pragma: no cover
            except Exception:  # pragma: no cover
                pass  # pragma: no cover
