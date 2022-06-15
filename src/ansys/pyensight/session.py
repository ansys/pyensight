"""Session module

The Session module allows pyensight to control the EnSight session

Examples:
    >>> from ansys.pyensight import LocalLauncher
    >>> session = LocalLauncher().start()
    >>> type(session)
    ansys.pyensight.Session
"""
from typing import Any, Optional

from ansys.pyensight.renderable import Renderable


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
        host:
            Name of the host on which the EnSight gRPC service is running
        grpc_port:
            Port number of the EnSight gRPC service
        html_port:
            Port number of the websocketserver HTTP server
        ws_port:
            Port number of the websocketserver WS server
        install_path:
            Pathname to the 'CEI' directory from which EnSight was launched
        secret_key:
            Shared session secret used to validate gRPC communication

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
        # are we in a jupyter notebook?
        try:
            _ = get_ipython()
            self._jupyter_notebook = True
        except NameError:
            self._jupyter_notebook = False

        # Connect to the EnSight instance
        from ansys.pyensight import ensight_grpc  # pylint: disable=import-outside-toplevel

        self._grpc = ensight_grpc.EnSightGRPC(
            host=self._hostname, port=self._grpc_port, secret_key=self._secret_key
        )
        self._grpc.connect()

    @property
    def jupyter_notebook(self) -> bool:
        """
        True if the session is running in a jupyter notebook and should use
        display features of that interface
        """
        return self._jupyter_notebook

    @jupyter_notebook.setter
    def jupyter_notebook(self, value: bool):
        self._jupyter_notebook = value

    @property
    def grpc(self) -> "ensight_grpc.EnSightGRPC":
        """
        The gRPC wrapper instance used by this session to access EnSight
        """
        return self._grpc

    @property
    def secret_key(self) -> str:
        """
        The secret key used for communication validation in the gRPC instance
        """
        return self._secret_key

    @property
    def html_port(self) -> int:
        """
        The port supporting HTML interaction with EnSight
        """
        return self._html_port

    @property
    def ws_port(self) -> int:
        """
        The port supporting WS interaction with EnSight
        """
        return self._ws_port

    @property
    def hostname(self) -> str:
        """
        The hostname of the system hosting the EnSight instance
        """
        return self._hostname

    @property
    def launcher(self) -> "pyensight.Launcher":
        """
        If a launcher was used to instantiate this session, a reference to the launcher instance.
        """
        return self._launcher

    @launcher.setter
    def launcher(self, value: "pyensight.Launcher"):
        self._launcher = value

    def show(
        self, what: str = "image", width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[str]:
        """
        Cause the current EnSight scene to be captured or otherwise made available for
        display in a web browser.  The appropriate visuals are generated and the HTML
        for viewing is returned.

        Legal values for the 'what' argument include:

        * 'image' is a simple rendered png image
        * 'webgl' is an interactive webgl-based browser viewer
        * 'remote' is a remote rendering based interactive EnSight viewer

        Args:
            what:
                The type of scene display to generate.  Three values are supported: 'image',
                'webgl', 'remote'.
            width:
                The width of the rendered entity
            height:
                The height of the rendered entity

        Returns:
            HTML source code for the renderable.

        Raises:
            RuntimeError:
                if it is not possible to generate the content
        """
        if self._html_port is None:
            raise RuntimeError("No websocketserver has been associated with this Session")
        url = None
        render = Renderable(self)
        if what == "image":
            url = render.image(width, height, aa=4)
        elif what == "webgl":
            url = render.webgl()
        elif what == "remote":
            url = render.vnc()

        if url is None:
            raise RuntimeError("Unable to generate requested visualization")

        if not self.jupyter_notebook:
            return url

        if width is None:
            width = 800
        if height is None:
            height = 600
        from IPython.display import IFrame, display

        return display(IFrame(src=url, width=width, height=height))

    def cmd(self, value: str) -> Any:
        """Run a command in EnSight and return the results

        Args:
            value:
                String of the command to run

        Returns:
            result of the string being executed as Python inside EnSight

        Examples:
            >>> print(session.cmd("10+4"))
            14
        """
        return self._grpc.command(value)

    def geometry(self, what: str = "glb") -> bytes:
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

    def close(self) -> None:
        """Close this session

        Terminate the current session and its gRPC connection.
        """
        if self._launcher:
            self._launcher.close(self)
        else:
            # lightweight shutdown, just close the gRPC connection
            self._grpc.shutdown(stop_ensight=False)
        self._launcher = None

    def load_data(
        self,
        data_file: str,
        result_file: str = None,
        file_format: str = None,
        reader_options: Optional[dict] = None,
    ) -> None:
        """Load a dataset into the EnSight instance

        Given the name of a file, load the data from that file into EnSight.  The new data will
        replace any currently loaded data in the session.

        Args:
            data_file:
                Filename to load
            result_file:
                For dual-file datasets, the second data file
            file_format:
                The name of the EnSight reader to be used to read.  If None, ask
                EnSight to select a reader.
            reader_options:
                Dictionary of reader specific option/value pairs which can be used
                to customize the reader behavior.

        Raises:
            RuntimeError:
                if EnSight cannot guess the file format or an error occurs while the
                data is being read.

        Examples:
            >>> from ansys.pyensight import LocalLauncher
            >>> session = LocalLauncher().start()
            >>> session.load_data(r'D:\data\CFX\example_data.res')
        """
        if file_format is None:
            try:
                cmd = "ensight.objs.core.CURRENTCASE[0]"
                cmd += f'.queryfileformat(r"""{data_file}""")["reader"]'
                file_format = self.cmd(cmd)
            except RuntimeError:
                raise RuntimeError(f"Unable to determine file format for {data_file}")
        cmds = [
            "ensight.part.select_default()",
            "ensight.part.modify_begin()",
            'ensight.part.elt_representation("3D_feature_2D_full")',
            "ensight.part.modify_end()",
            'ensight.data.binary_files_are("native")',
            f'ensight.data.format("{file_format}")',
        ]
        if reader_options:
            for key, value in reader_options:
                option = f"""ensight.data.reader_option("'{key}' '{value}'")"""
                cmds.append(option)
        if result_file:
            cmds.append(f'ensight.data.result(r"""{result_file}""")')
        cmds.append("ensight.data.shift_time(1.000000, 0.000000, 0.000000)")
        cmds.append('ensight.solution_time.monitor_for_new_steps("off")')
        cmds.append(f'ensight.data.replace(r"""{data_file}""")')
        for cmd in cmds:
            if self.cmd(cmd) != 0:
                raise RuntimeError("Unable to load the dataset.")
