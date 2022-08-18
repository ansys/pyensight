"""session module

The session module allows pyensight to control the EnSight session

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
        # when objects come into play, we can reuse them, so hash ID to instance here
        self._ensobj_hash = {}
        self._timeout = 120.0
        self._cei_home = ""
        self._cei_suffix = ""
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

        # establish the connection with retry
        self._establish_connection(validate=True)

        # update the enums to match current EnSight instance
        cmd = "{key: getattr(ensight.objs.enums, key) for key in dir(ensight.objs.enums)}"
        new_enums = self.cmd(cmd)
        for key, value in new_enums.items():
            if key.startswith("__") and (key != "__OBJID__"):
                continue
            setattr(self._ensight.objs.enums, key, value)

        # create ensight.core
        self._ensight.objs.core = self.cmd("ensight.objs.core")

    def __repr__(self):
        s = f"Session(host='{self.hostname}', secret_key='{self.secret_key}', "
        s += f"html_port={self.html_port}, grpc_port={self._grpc_port},"
        s += f"ws_port={self.ws_port}, session_directory=r'{self.launcher.session_directory}')"
        return s

    def __del__(self):
        self.close()

    def _establish_connection(self, validate: bool = False) -> None:
        """Establish a gRPC connection to the EnSight instance.
        Args:
            validate: If true, actually try to communicate with EnSight
        """
        time_start = time.time()
        while time.time() - time_start < self._timeout:
            if self._grpc.is_connected():
                try:
                    if validate:
                        self._cei_home = self.cmd("ensight.version('CEI_HOME')")
                        self._cei_suffix = self.cmd("ensight.version('suffix')")
                    return
                except OSError:
                    pass
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
    def timeout(self) -> float:
        """
        The amount of time in seconds before a gRPC call is considered to have failed.
        """
        return self._timeout

    @timeout.setter
    def timeout(self, value: float) -> None:
        self._timeout = value

    @property
    def cei_home(self) -> str:
        """
        The value of CEI_HOME for the connected EnSight session.
        """
        return self._cei_home

    @property
    def cei_suffix(self) -> str:
        """
        The suffix string, 222 for example, of the connected EnSight session.
        """
        return self._cei_suffix

    @property
    def jupyter_notebook(self) -> bool:
        """
        True if the session is running in a jupyter notebook and should use
        display features of that interface.
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
        self,
        what: str = "image",
        width: Optional[int] = None,
        height: Optional[int] = None,
        temporal: bool = False,
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
                'webgl', 'remote', 'deep_pixel'.
            width:
                The width of the rendered entity
            height:
                The height of the rendered entity
            temporal:
                If True, include all timesteps in 'webgl' views

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
            url = render.webgl(temporal=temporal)
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
        ret = self._grpc.command(value, do_eval=do_eval)
        if do_eval:
            ret = self._convert_ctor(ret)
            return eval(ret, dict(session=self))
        return ret

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
        callback_id = self.cmd(cmd)
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
        _ = self.cmd(cmd, do_eval=False)

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

    # Object API helper functions
    @staticmethod
    def remote_obj(ensobjid: int) -> str:
        """Generate a string that, for a given ENSOBJ ID, returns a proxy object instance"""
        return f"ensight.objs.wrap_id({ensobjid})"

    def _prune_hash(self) -> None:
        """The ensobj hash table may need flushing if it gets too big, do that here"""
        if len(self._ensobj_hash) > 1000000:
            self._ensobj_hash = {}

    def add_ensobj_instance(self, obj: "ENSOBJ") -> None:
        """Add a new ENSOBJ instance to the hash table"""
        self._ensobj_hash[obj.__OBJID__] = obj

    def obj_instance(self, ensobjid: int) -> Optional["ENSOBJ"]:
        """Get any existing proxy object associated with a given ID"""
        return self._ensobj_hash.get(ensobjid, None)

    def _obj_attr_subtype(self, classname: str) -> (int, dict):
        """Get subtype information for a given class
        For the input classname, return the proper Python proxy classname and if the
        class supports subclasses, the attribute id number of the differentiating
        attribute.

        Args:
            classname:
                The root classname to lookup

        Return:
            (attr_id, subclassnamedict): the attribute used to differentiate between classes
                and a dictionary of the classnames for each value of the attribute.
        """
        if classname == "ENS_PART":
            part_lookup_dict = dict()
            part_lookup_dict[0] = "ENS_PART_MODEL"
            part_lookup_dict[1] = "ENS_PART_CLIP"
            part_lookup_dict[2] = "ENS_PART_CONTOUR"
            part_lookup_dict[3] = "ENS_PART_DISCRETE_PARTICLE"
            part_lookup_dict[4] = "ENS_PART_FRAME"
            part_lookup_dict[5] = "ENS_PART_ISOSURFACE"
            part_lookup_dict[6] = "ENS_PART_PARTICLE_TRACE"
            part_lookup_dict[7] = "ENS_PART_PROFILE"
            part_lookup_dict[8] = "ENS_PART_VECTOR_ARROW"
            part_lookup_dict[9] = "ENS_PART_ELEVATED_SURFACE"
            part_lookup_dict[10] = "ENS_PART_DEVELOPED_SURFACE"
            part_lookup_dict[15] = "ENS_PART_BUILTUP"
            part_lookup_dict[16] = "ENS_PART_TENSOR_GLYPH"
            part_lookup_dict[17] = "ENS_PART_FX_VORTEX_CORE"
            part_lookup_dict[18] = "ENS_PART_FX_SHOCK"
            part_lookup_dict[19] = "ENS_PART_FX_SEP_ATT"
            part_lookup_dict[20] = "ENS_PART_MAT_INTERFACE"
            part_lookup_dict[21] = "ENS_PART_POINT"
            part_lookup_dict[22] = "ENS_PART_AXISYMMETRIC"
            part_lookup_dict[24] = "ENS_PART_VOF"
            part_lookup_dict[25] = "ENS_PART_AUX_GEOM"
            part_lookup_dict[26] = "ENS_PART_FILTER"
            return self.ensight.objs.enums.PARTTYPE, part_lookup_dict

        elif classname == "ENS_ANNOT":
            annot_lookup_dict = dict()
            annot_lookup_dict[0] = "ENS_ANNOT_TEXT"
            annot_lookup_dict[1] = "ENS_ANNOT_LINE"
            annot_lookup_dict[2] = "ENS_ANNOT_LOGO"
            annot_lookup_dict[3] = "ENS_ANNOT_LGND"
            annot_lookup_dict[4] = "ENS_ANNOT_MARKER"
            annot_lookup_dict[5] = "ENS_ANNOT_ARROW"
            annot_lookup_dict[6] = "ENS_ANNOT_DIAL"
            annot_lookup_dict[7] = "ENS_ANNOT_GAUGE"
            annot_lookup_dict[8] = "ENS_ANNOT_SHAPE"
            return self.ensight.objs.enums.PARTTYPE, annot_lookup_dict

        elif classname == "ENS_TOOL":
            tool_lookup_dict = dict()
            tool_lookup_dict[0] = "ENS_TOOL_CURSOR"
            tool_lookup_dict[1] = "ENS_TOOL_LINE"
            tool_lookup_dict[2] = "ENS_TOOL_PLANE"
            tool_lookup_dict[3] = "ENS_TOOL_BOX"
            tool_lookup_dict[4] = "ENS_TOOL_CYLINDER"
            tool_lookup_dict[5] = "ENS_TOOL_CONE"
            tool_lookup_dict[6] = "ENS_TOOL_SPHERE"
            tool_lookup_dict[7] = "ENS_TOOL_REVOLUTION"
            return self.ensight.objs.enums.TOOLTYPE, tool_lookup_dict

        return None, None

    def _convert_ctor(self, s: str) -> str:
        """Convert ENSOBJ references into executable code in __repl__ strings
        The __repl__() implementation for an ENSOBJ subclass will generate strings like these::

            Class: ENS_GLOBALS, CvfObjID: 221, cached:yes
            Class: ENS_PART, desc: 'Sphere', CvfObjID: 1078, cached:no

        This method will detect strings like those and convert them into strings like this::

            session.ensight.objs.ENS_GLOBALS(session, 221)
            session.ensight.objs.ENS_PART_MODEL(session, 1078, attr_id=1610612792, attr_value=0)

        Where 1610612792 is ensight.objs.enums.PARTTYPE.

        It can also generate strings like this::

            session.obj_instance(221)

        If a proxy object for the id already exists.
        """
        self._prune_hash()
        while True:
            # Find the object repl block to replace
            id = s.find("CvfObjID:")
            if id == -1:
                break
            start = s.find("Class: ")
            if (start == -1) or (start > id):
                break
            tail_len = 11
            tail = s.find(", cached:no")
            if tail == -1:
                tail_len = 12
                tail = s.find(", cached:yes")
            if tail == -1:
                break
            # isolate the block to replace
            prefix = s[:start]
            suffix = s[tail + tail_len :]
            # parse out the object id and classname
            objid = int(s[id + 9 : tail])
            classname = s[start + 7 : tail]
            comma = classname.find(",")
            classname = classname[:comma]
            # pick the subclass based on the classname
            attr_id, classname_lookup = self._obj_attr_subtype(classname)
            # generate the replacement text
            if objid in self._ensobj_hash:
                replace_text = f"session.obj_instance({objid})"
            else:
                subclass_info = ""
                if attr_id is not None:
                    # if a "subclass" case and no subclass attrid value, ask for it...
                    if classname_lookup is not None:
                        remote_name = self.remote_obj(objid)
                        cmd = f"{remote_name}.getattr({attr_id})"
                        attr_value = self.cmd(cmd)
                        if attr_value in classname_lookup:
                            classname = classname_lookup[attr_value]
                            subclass_info = f",attr_id={attr_id}, attr_value={attr_value}"
                replace_text = f"session.ensight.objs.{classname}(session, {objid}{subclass_info})"
            if replace_text is None:
                break
            s = prefix + replace_text + suffix
        return s
