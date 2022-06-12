"""Session module

The Session module allows pyensight to control the EnSight session

Examples
--------
>>> from ansys.pyensight import Launcher
>>> session = Launcher.launch_session()
>>> type(session)
ansys.pyensight.Session

"""
from typing import Literal
from typing import Optional


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

        >>> from ansys.pyensight import Launcher
        >>> session = Launcher.launch_local_session(ansys_installation='/opt/ansys_inc/v222')

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
        self._kill_on_close = False
        self._html_port = html_port
        self._ws_port = ws_port
        self._secret_key = secret_key
        self._grpc_port = grpc_port

    @property
    def shutdown(self) -> bool:
        """
        If closing this Session, should the EnSight instance be shutdown.

        Set to True if closing this session should stop the EnSight instance.
        """
        return self._kill_on_close

    @shutdown.setter
    def shutdown(self, value: bool):
        self._kill_on_close = value

    def show(self, what: Literal["image", "webgl", "remote"] = "image") -> Optional[str]:
        """
        Cause the current EnSight scene to be captured or otherwise made available for
        display in a web browser.  The appropriate visuals are generated and the HTML
        for viewing is returned.

        Args:
            what: The type of scene display to generate

        Return:
            HTML source code for the renderable.

        Raises:
            RuntimeError if it is not possible to generate the content

        """
        if self._html_port is None:
            raise RuntimeError("No websocketserver has been associated with this Session")

        return ""

    def close(self) -> bool:
        """Close the EnSight instance that is connected to this Session

        Returns:
            True if successful, False otherwise
        """
        if self._kill_on_close:
            pass

        return True
