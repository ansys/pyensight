"""Session module

The Session module allows pyensight to control the EnSight session

Examples:

>>> from ansys.pyensight import LocalLauncher
>>> session = LocalLauncher().start()
>>> type(session)
ansys.pyensight.Session

"""
from typing import Any
from typing import Literal
from typing import Optional

import requests


class Session:
    """Class to access an EnSight instance

    The Session object wraps the various connections to an EnSight instance.  It includes
    the location of the installation, the gRPC, HTML and WS ports used to talk to the
    EnSight session. In most cases, a Session instance is created using the Launcher
    class methods, but if the EnSight session is already running, an instance can be
    created directly to wrap the running EnSight.

    A gRPC connection is required to interact with an EnSight session. The host, grpc
    port number and secret key must be specified.  The html and ws ports are used to
    enable the show() method and require an instance of websocketserver to be running
    as well.

    Args:
        host: Name of the host on which the EnSight gRPC service is running
        grpc_port: Port number of the EnSight gRPC service
        html_port: Port number of the websocketserver HTTP server
        ws_port: Port number of the websocketserver WS server
        install_path: Pathname to the 'CEI" directory from which EnSight was launched
        secret_key: Shared session secret used to validate gRPC communication

    Returns:
        None

    Examples:

        >>> from ansys.pyensight import Session
        >>> session = Session(host="127.0.0.1", grpc_port=12345, http_port=8000, ws_port=8100)

        >>> from ansys.pyensight import LocalLauncher
        >>> session = LocalLauncher(ansys_installation='/opt/ansys_inc/v222').start()

    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        install_path: Optional[str] = None,
        secret_key: str = "",
        grpc_port: int = 12345,
        html_port: Optional[int] = None,
        ws_port: Optional[int] = None,
    ) -> None:

        self._hostname = host
        self._install_path = install_path
        self._launcher = None
        self._html_port = html_port
        self._ws_port = ws_port
        self._secret_key = secret_key
        self._grpc_port = grpc_port

        # Connect to the EnSight instance
        from ansys.pyensight import ensight_grpc  # pylint: disable=import-outside-toplevel

        self._grpc = ensight_grpc.EnSightGRPC(
            host=self._hostname, port=self._grpc_port, secret_key=self._secret_key
        )
        self._grpc.connect()

    @property
    def launcher(self) -> "pyensight.Launcher":
        """
        If a launcher was used to instantiate this session, a reference to the launcher instance.
        """
        return self._launcher

    @launcher.setter
    def launcher(self, value: "pyensight.Launcher"):
        self._launcher = value

    def show(self, what: Literal["image", "webgl", "remote"] = "image") -> Optional[str]:
        """
        Cause the current EnSight scene to be captured or otherwise made available for
        display in a web browser.  The appropriate visuals are generated and the HTML
        for viewing is returned.

        Args:
            what: The type of scene display to generate

        Returns:
            HTML source code for the renderable.

        Raises:
            RuntimeError if it is not possible to generate the content

        """
        if self._html_port is None:
            raise RuntimeError("No websocketserver has been associated with this Session")

        return ""

    def cmd(self, value: str) -> Any:
        """Run a command in EnSight and return the results

        Args:
            value: string of the command to run

        Returns:
            result of the string being executed as Python inside EnSight

        Examples:

            >>> print(session.cmd("10+4"))
            14

        """
        return self._grpc.command(value)

    def geometry(self, what: Literal["glb"] = "glb") -> bytes:
        """Return the current EnSight scene as a geometry file

        Args:
            what: the file format to return (as a bytes object)

        Returns:
            the generated geometry file as a bytes object

        Examples:

            >>> data = session.geometry()
            >>> with open("file.glb", "wb") as fp:
            ...     fp.write(data)

        """
        return self._grpc.geometry()

    def render(self, width: int, height: int, aa: int = 1) -> bytes:
        """Render the current EnSight scene and return a PNG image

        Args:
            width: width of the rendered image in pixels
            height: height of the rendered image in pixels
            aa: number of antialiasing passes to use

        Returns:
            a bytes object that is a PNG image stream

        Examples:

            >>> data = session.render(1920, 1080, aa=4)
            >>> with open("file.png", "wb") as fp:
            ...     fp.write(data)

        """
        return self._grpc.render(width=width, height=height, aa=aa)

    def close(self, shutdown: bool = True) -> None:
        """Close this session

        Termination the current session and its gRPC connection.

        Args:
            shutdown: if True, terminate the EnSight session as well.
        """
        if not shutdown:
            # lightweight shutdown, just close the gRPC connection
            self._grpc.shutdown(stop_ensight=False)
            if self._launcher:
                self._launcher.close(self)
        else:
            # shutdown the gRPC connection and EnSight
            self._grpc.shutdown(stop_ensight=True)
            # stop the websocketserver process
            url = f"http://{self._hostname}:{self._html_port}/v1/stop"
            if self._secret_key:
                url += f"?security_token={self._secret_key}"
            _ = requests.get(url)
        # Tell the launcher that we are no longer talking to the session
        if self._launcher:
            self._launcher.close(self)
            self._launcher = None
