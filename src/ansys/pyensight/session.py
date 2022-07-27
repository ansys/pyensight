"""Session module

The Session module allows pyensight to control the EnSight session

Examples:
    >>> from ansys.pyensight import LocalLauncher
    >>> session = LocalLauncher().start()
    >>> type(session)
    ansys.pyensight.Session
"""
import time
from typing import Any, Callable, Optional
from urllib.parse import urlparse
import webbrowser

from ansys import pyensight
from ansys.pyensight.renderable import Renderable


class Session:
    """Class to access an EnSight instance

    The Session object wraps the various connections to an EnSight instance.  It includes
    the location of the installation, the gRPC, HTML and WS ports used to talk to the
    EnSight session. In most cases, a Session instance is created using the Launcher
    class methods, but if the EnSight session is already running, an instance can be
    created directly to wrap the running EnSight.

    If the session object was created via a Launcher .start() method call, when the
    session object is garbage collected, the EnSight instance will be automatically stopped.
    To prevent this behavior (and leave the EnSight instance running), set the
    halt_ensight_on_close property to False.

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
        ::

            from ansys.pyensight import Session
            session = Session(host="127.0.0.1", grpc_port=12345, http_port=8000, ws_port=8100)

        ::

            from ansys.pyensight import LocalLauncher
            session = LocalLauncher().start()

    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        install_path: Optional[str] = None,
        secret_key: str = "",
        grpc_port: int = 12345,
        html_port: Optional[int] = None,
        ws_port: Optional[int] = None,
        session_directory: Optional[str] = None,
    ) -> None:
        self._hostname = host
        self._install_path = install_path
        self._launcher = None
        self._html_port = html_port
        self._ws_port = ws_port
        self._secret_key = secret_key
        self._grpc_port = grpc_port
        self._halt_ensight_on_close = True
        self._callbacks = dict()
        # if the caller passed a session directory we will assume they are
        # creating effectively a proxy Session and create a (stub) launcher
        if session_directory is not None:
            self._launcher = pyensight.Launcher()
            self._launcher.session_directory = session_directory
            # The stub will not know about us
            self._halt_ensight_on_close = False

        # are we in a jupyter notebook?
        try:
            _ = get_ipython()
            self._jupyter_notebook = True
        except NameError:
            self._jupyter_notebook = False

        # Connect to the EnSight instance
        from ansys.pyensight import ensight_api  # pylint: disable=import-outside-toplevel
        from ansys.pyensight import ensight_grpc  # pylint: disable=import-outside-toplevel

        self._ensight = ensight_api.ensight(self)
        self._grpc = ensight_grpc.EnSightGRPC(
            host=self._hostname, port=self._grpc_port, secret_key=self._secret_key
        )

        # update the enums to match current EnSight instance
        cmd = "{key: getattr(ensight.objs.enums, key) for key in dir(ensight.objs.enums)}"
        new_enums = self.cmd(cmd)
        for key, value in new_enums.items():
            if key.startswith("__") and (key != "__OBJID__"):
                continue
            setattr(self._ensight.objs.enums, key, value)

    def __repr__(self):
        s = f"Session(host='{self.hostname}', secret_key='{self.secret_key}', "
        s += f"html_port={self.html_port}, grpc_port={self._grpc_port},"
        s += f"ws_port={self.ws_port}, session_directory=r'{self.launcher.session_directory}')"
        return s

    def __del__(self):
        self.close()

    def _establish_connection(self, timeout: float = 120.0) -> None:
        """Establish a gRPC connection to the EnSight instance."""
        time_start = time.time()
        while time.time() - time_start < timeout:
            if self._grpc.is_connected():
                return
            self._grpc.connect()
        raise RuntimeError("Unable to establish a gRPC connection to EnSight.")

    @property
    def halt_ensight_on_close(self) -> bool:
        """
        If True and this session was created via a launcher, then when the session
        is closed, the EnSight instance will be stopped.  Note: while this flag prevents
        close() from shutting down EnSight, depending on how the host Python interpreter
        is configured, the EnSight session may still be halted (e.g. Jupyter Lab).
        """
        return self._halt_ensight_on_close

    @halt_ensight_on_close.setter
    def halt_ensight_on_close(self, value: bool) -> None:
        self._halt_ensight_on_close = value

    @property
    def jupyter_notebook(self) -> bool:
        """
        True if the session is running in a jupyter notebook and should use
        display features of that interface
        """
        return self._jupyter_notebook

    @jupyter_notebook.setter
    def jupyter_notebook(self, value: bool) -> None:
        self._jupyter_notebook = value

    @property
    def ensight(self) -> "ensight_api.ensight":
        """
        Core EnSight API wrapper
        """
        return self._ensight

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

    @staticmethod
    def help():
        """Open the help pages for the pyansys project in a webbrowser"""
        url = "https://furry-waffle-422870de.pages.github.io/"
        webbrowser.open(url)

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
        * 'deep_pixel' is an EnSight deep pixel image

        Args:
            what:
                The type of scene display to generate.  Three values are supported: 'image',
                'webgl', 'remote'.
            width:
                The width of the rendered entity
            height:
                The height of the rendered entity

        Returns:
            URL for the renderable.

        Raises:
            RuntimeError:
                if it is not possible to generate the content
        """
        self._establish_connection()
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
        elif what == "deep_pixel":
            url = render.deep_pixel(width, height, aa=1)

        if url is None:
            raise RuntimeError("Unable to generate requested visualization")

        if self.jupyter_notebook:
            if width is None:
                width = 800
            if height is None:
                height = 600
            from IPython.display import IFrame, display

            display(IFrame(src=url, width=width, height=height))

        return url

    def cmd(self, value: str, do_eval: bool = True) -> Any:
        """Run a command in EnSight and return the results

        Args:
            value:
                String of the command to run
            do_eval:
                If True, a return value will be computed and returned
        Returns:
            result of the string being executed as Python inside EnSight

        Examples:
            >>> print(session.cmd("10+4"))
            14
        """
        self._establish_connection()
        return self._grpc.command(value, do_eval=do_eval)

    def geometry(self, what: str = "glb") -> bytes:
        """Return the current EnSight scene as a geometry file

        Args:
            what: the file format to return (as a bytes object)

        Returns:
            the generated geometry file as a bytes object

        Examples:
            ::

                data = session.geometry()
                with open("file.glb", "wb") as fp:
                    fp.write(data)

        """
        self._establish_connection()
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
            ::

                data = session.render(1920, 1080, aa=4)
                with open("file.png", "wb") as fp:
                    fp.write(data)

        """
        self._establish_connection()
        return self._grpc.render(width=width, height=height, aa=aa)

    def close(self) -> None:
        """Close this session

        Terminate the current session and its gRPC connection.
        """
        if self._launcher and self._halt_ensight_on_close:
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
            ::

                from ansys.pyensight import LocalLauncher
                session = LocalLauncher().start()
                session.load_data(r'D:\data\CFX\example_data.res')

        """
        self._establish_connection()
        # what application are we talking to?
        target = self.cmd("ensight.version('product').lower()")
        if target == "envision":
            cmd = f'ensight.data.replace(r"""{data_file}""")'
            if self.cmd(cmd) != 0:
                raise RuntimeError("Unable to load the dataset.")
            return

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

    def add_callback(
        self, target: str, tag: str, attr_list: list, method: Callable, compress: bool = True
    ) -> None:
        """Register a callback with an event tuple

        For a given target object (e.g. "ensight.objs.core") and a list
        of attributes (e.g. ["PARTS", "VARIABLES"]) set up a callback
        (method) to be called with a URL encoded with the supplied (tag)
        whenever one of the listed attributes change.  The callback is
        in a URL of the form: grpc://{sessionguid}/{tag}?enum={attribute}&uid={objectid}
        Only one callback with the noted tag can be used in the session.

        Args:
            target:
                The name of the target object or the name of a class as a string to
                match all objects of that class.
            tag:
                The unique name for the callback. A tag can end with macros of
                the form {{attrname}} to return the value of an attribute of the
                target object.  The macros should take the form of URI queries to
                simplify parsing.
            attr_list:
                The list of attributes of "target" that will result in the callback
                being called if it changes.
            method:
                A callable that is called with the returned URL.
            compress:
                By default, if as a result of an action, a repeated event is
                generated, only the last event will be called back.  If compress
                is False, every event will result in a callback.

        Examples:
            A string like this:
            'Event: grpc://f6f74dae-f0ed-11ec-aa58-381428170733/partlist?enum=PARTS&uid=221'
            will be printed when the dataset is loaded and the partlist changes::

                from ansys.pyensight import LocalLauncher
                s = LocalLauncher().start()
                def cb(v: str):
                    print("Event:", v)

                s.add_callback("ensight.objs.core", "partlist", ["PARTS"], cb)
                s.load_data(r"D:\ANSYSDev\data\CFX\HeatingCoil_001.res")


            ::

                from urllib.parse import urlparse, parse_qsl
                def vp_callback(uri):
                    p = urlparse(uri)
                    q = parse_qsl(p.query)
                    print("Viewport:", q)

                tag = "vport?w={{WIDTH}}&h={{HEIGHT}}&x={{ORIGINX}}&y={{ORIGINY}}"
                session.add_callback("'ENS_VPORT'", tag, [session.ensight.objs.enums.ORIGINX,
                        session.ensight.objs.enums.ORIGINY, session.ensight.objs.enums.WIDTH,
                        session.ensight.objs.enums.HEIGHT], vp_callback)

        """
        self._establish_connection()
        # shorten the tag up to the query block.  Macros only legal in the query block
        try:
            idx = tag.index("?")
            short_tag = tag[:idx]
        except ValueError:
            short_tag = tag
        if short_tag in self._callbacks:
            raise RuntimeError(f"A callback for tag '{short_tag}' already exists")
        # Build the addcallback string against the full tag
        flags = ""
        if compress:
            flags = ",flags=ensight.objs.EVENTMAP_FLAG_COMP_GLOBAL"
        cmd = f"ensight.objs.addcallback({target},None,"
        cmd += f"'{self._grpc.prefix()}{tag}',attrs={repr(attr_list)}{flags})"
        callback_id = self._grpc.command(cmd)
        # if this is the first callback, start the event stream
        if len(self._callbacks) == 0:
            self._grpc.event_stream_enable(callback=self._event_callback)
        # record the callback id along with the callback
        # if the callback URL starts with the short_tag, we make the callback
        self._callbacks[short_tag] = (callback_id, method)

    def remove_callback(self, tag: str) -> None:
        """Remove a callback started with add_callback

        Given a tag used to register a previous callback (add_callback), remove
        that callback from the EnSight callback system.

        Args:
            tag:
                The callback string tag

        Raises:
            RuntimeError:
                If an invalid tag is supplied
        """
        if tag not in self._callbacks:
            raise RuntimeError(f"A callback for tag '{tag}' does not exist")
        callback_id = self._callbacks[tag][0]
        del self._callbacks[tag]
        cmd = f"ensight.objs.removecallback({callback_id})"
        self._grpc.command(cmd, do_eval=False)

    def _event_callback(self, cmd: str) -> None:
        """Pass the URL back to the registered callback
        Match the cmd URL with the registered callback and make the callback.

        Args:
            cmd:
                The URL callback from the gRPC event stream.  The URL has the
                form:  grpc://{sessionguid}/{tag}?enum={attribute}&uid={objectid}
        """
        # EnSight will always tack on '?enum='.  If our tag uses ?macro={{attr}},
        # you will get too many '?' in the URL, making it difficult to parse.
        # So, we look for "?..." and a following "?enum=".  If we see this, convert
        # "?enum=" into "&enum=".
        idx_question = cmd.find("?")
        idx_enum = cmd.find("?enum=")
        if idx_question < idx_enum:
            cmd = cmd.replace("?enum=", "&enum=")
        parse = urlparse(cmd)
        tag = parse.path[1:]
        for key, value in self._callbacks.items():
            # remember "key" is a shortened version of tag
            if tag.startswith(key):
                value[1](cmd)
                return
        print(f"Unhandled event: {cmd}")
