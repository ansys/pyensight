"""Launcher module

The Launcher module provides a base class responsible for managing an EnSight
instance.  Subclasses of the class implement specific launching paradighms.

Examples:
>>> from ansys.pyensight import LocalLauncher
>>> session = LocalLauncher().start()
"""
import abc
import os.path
import socket
from typing import List, Optional

import requests

from ansys import pyensight


class Launcher:
    """EnSight Launcher base class

    A Launcher instance is used to start/end an EnSight session.  Specific subclasses
    handle different types of launching semantics.
    """

    def __init__(self) -> None:
        self._sessions = []
        self._session_directory: str = "."

    @property
    def session_directory(self):
        """The root directory for HTML files
        This directory contents can be accessed as http://hostname:port/...
        """
        return self._session_directory

    def close(self, session: "pyensight.Session") -> None:
        """Shutdown the launched EnSight session

        Close all the associated sessions and then stop the launched EnSight instance.

        Raises:
            RuntimeError:
                if the session was not launched by this launcher.
        """
        if session not in self._sessions:
            raise RuntimeError("Session not associated with this Launcher")
        self._sessions.remove(session)
        if self._sessions:
            # stop the grpc session interface
            session.grpc.shutdown(stop_ensight=False)
            return

        # if the session list is empty, stop the EnSight instance (via session grpc interface)
        session.grpc.shutdown(stop_ensight=True)

        # stop the websocketserver instance
        url = f"http://{session.hostname}:{session.html_port}/v1/stop"
        if session.secret_key:
            url += f"?security_token={session.secret_key}"
        _ = requests.get(url)

        # Stop the launcher instance
        self.stop()

    @abc.abstractmethod
    def start(self) -> "pyensight.Session":
        """Base method for starting the actual session"""
        return pyensight.Session()

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
            count:
                Number of unused ports to find
            avoid:
                An optional list of ports not to check

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
