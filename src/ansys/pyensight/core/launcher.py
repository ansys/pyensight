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
import socket
from typing import TYPE_CHECKING, List, Optional
import warnings

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

    """

    def __init__(
        self,
        timeout: float = 120.0,
        use_egl: bool = False,
        use_sos: Optional[int] = None,
        enable_rest_api: bool = False,
    ) -> None:
        self._timeout = timeout
        self._use_egl_param_val: bool = use_egl
        self._use_sos = use_sos
        self._enable_rest_api = enable_rest_api

        self._sessions: List[Session] = []
        self._session_directory: str = "."

        self._is_egl_capable: Optional[bool] = None
        self._egl_env_val: Optional[bool] = None
        egl_env = os.environ.get("PYENSIGHT_FORCE_ENSIGHT_EGL")
        if egl_env is not None:
            if egl_env == "1":
                self._egl_env_val = True
            else:
                self._egl_env_val = False

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
        if session.secret_key:
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

    @staticmethod
    def _find_unused_ports(count: int, avoid: Optional[List[int]] = None) -> Optional[List[int]]:
        """Find "count" unused ports on the host system

        A port is considered unused if it does not respond to a "connect" attempt.  Walk
        the ports from 'start' to 'end' looking for unused ports and avoiding any ports
        in the 'avoid' list.  Stop once the desired number of ports have been
        found.  If an insufficient number of ports were found, return None.

        Parameters
        ----------
        count: int :
            Number of unused ports to find
        avoid: Optional[List[int]] :
            An optional list of ports not to check

        Returns
        -------
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

        if self._egl_env_val is not None:
            # if the environment variable was set, that overrides the constructor option
            return self._egl_env_val

        # otherwise, use the arg passed to the constructor
        return self._use_egl_param_val

    def _is_system_egl_capable(self) -> bool:
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
