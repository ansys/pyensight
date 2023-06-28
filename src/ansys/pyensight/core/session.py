"""session module

The session module allows pyensight to control the EnSight session

Examples:

>>> from ansys.pyensight.core import LocalLauncher
>>> session = LocalLauncher().start()
>>> type(session)
ansys.pyensight.Session

"""
import atexit
import importlib.util
from os import listdir
import os.path
import platform
import sys
import textwrap
import time
import types
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import webbrowser

from ansys.pyensight.core.enscontext import EnsContext
from ansys.pyensight.core.launcher import Launcher
from ansys.pyensight.core.listobj import ensobjlist
from ansys.pyensight.core.renderable import (
    RenderableDeepPixel,
    RenderableEVSN,
    RenderableImage,
    RenderableMP4,
    RenderableSGEO,
    RenderableVNC,
    RenderableWebGL,
)

if TYPE_CHECKING:
    from ansys.pyensight.core import enscontext, ensight_api, ensight_grpc, renderable
    from ansys.pyensight.core.ensobj import ENSOBJ


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

    Parameters
    ----------
    host :
        Name of the host on which the EnSight gRPC service is running.
    install_path :
        Pathname to the 'CEI' directory from which EnSight was launched.
    secret_key :
        Shared session secret used to validate gRPC communication.
    grpc_port :
        Port number of the EnSight gRPC service.
    html_port :
        Port number of the websocketserver HTTP server.
    ws_port :
        Port number of the websocketserver WS server.
    session_directory :
        The directory used for local data storage on the server.
    timeout :
        The number of seconds to retry a gRPC connection before giving up.
        The default is 120.

    Examples
    --------

    >>> from ansys.pyensight.core import Session
    >>> session = Session(host="127.0.0.1", grpc_port=12345, http_port=8000, ws_port=8100)

    >>> from ansys.pyensight.core import LocalLauncher
    >>> session = LocalLauncher().start()

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
        timeout: float = 120.0,
    ) -> None:
        # when objects come into play, we can reuse them, so hash ID to instance here
        self._ensobj_hash: Dict[int, "ENSOBJ"] = {}
        self._language = "en"
        self._timeout = timeout
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
        self._callbacks: Dict[str, Tuple[int, Any]] = dict()
        # if the caller passed a session directory we will assume they are
        # creating effectively a proxy Session and create a (stub) launcher
        if session_directory is not None:
            self._launcher = Launcher()
            self._launcher.session_directory = session_directory
            # The stub will not know about us
            self._halt_ensight_on_close = False

        # are we in a jupyter notebook?
        try:
            _ = get_ipython()  # type: ignore
            self._jupyter_notebook = True
        except NameError:
            self._jupyter_notebook = False

        # Connect to the EnSight instance
        from ansys.api.pyensight import ensight_api  # pylint: disable=import-outside-toplevel
        from ansys.pyensight.core import ensight_grpc  # pylint: disable=import-outside-toplevel

        self._ensight = ensight_api.ensight(self)
        self._build_utils_interface()
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

        # get the remote Python interpreter version
        self.cmd("import platform", do_eval=False)
        self._ensight_python_version = self.cmd("platform.python_version_tuple()")

        # Since this session can have allocated significant external resources
        # we very much want a chance to close it up cleanly.  It is legal to
        # call close() twice on this class if needed.
        atexit.register(self.close)

    def __repr__(self):
        s = f"Session(host='{self.hostname}', secret_key='{self.secret_key}', "
        s += f"html_port={self.html_port}, grpc_port={self._grpc_port},"
        s += f"ws_port={self.ws_port}, session_directory=r'{self.launcher.session_directory}')"
        return s

    def _establish_connection(self, validate: bool = False) -> None:
        """Establish a gRPC connection to the EnSight instance.

        Parameters
        ----------
        validate : bool
            If true, actually try to communicate with EnSight. By default false.
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
            self._grpc.connect(timeout=self._timeout)
        raise RuntimeError("Unable to establish a gRPC connection to EnSight.")

    @property
    def language(self) -> str:
        """The current language specification for the EnSight session.  Various
        information calls will return their information in the target language
        if possible. The default is: 'en'.

        Examples
        --------

        >>> session.language = "en"
        >>> session.ensight.objs.core.attrinfo(session.ensight.objs.enums.PREDEFINEDPALETTES)
        >>> session.language = "zh"
        >>> session.ensight.objs.core.attrinfo(session.ensight.objs.enums.PREDEFINEDPALETTES)

        """
        return self._language

    @language.setter
    def language(self, value: str) -> None:
        self._language = value
        self.cmd(f"ensight.core.tr.changelang(lin='{self._language}')", do_eval=False)

    @property
    def halt_ensight_on_close(self) -> bool:
        """If True and this session was created via a launcher, then when the session
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
        """The amount of time in seconds before a gRPC call is considered to have failed."""
        return self._timeout

    @timeout.setter
    def timeout(self, value: float) -> None:
        self._timeout = value

    @property
    def cei_home(self) -> str:
        """The value of CEI_HOME for the connected EnSight session."""
        return self._cei_home

    @property
    def cei_suffix(self) -> str:
        """The suffix string, 222 for example, of the connected EnSight session."""
        return self._cei_suffix

    @property
    def jupyter_notebook(self) -> bool:
        """True if the session is running in a jupyter notebook and should use
        display features of that interface.

        """
        return self._jupyter_notebook

    @jupyter_notebook.setter
    def jupyter_notebook(self, value: bool) -> None:
        self._jupyter_notebook = value

    @property
    def ensight(self) -> "ensight_api.ensight":
        """Core EnSight API wrapper"""
        return self._ensight

    @property
    def grpc(self) -> "ensight_grpc.EnSightGRPC":
        """The gRPC wrapper instance used by this session to access EnSight"""
        return self._grpc

    @property
    def secret_key(self) -> str:
        """The secret key used for communication validation in the gRPC instance"""
        return self._secret_key

    @property
    def html_port(self) -> Optional[int]:
        """The port supporting HTML interaction with EnSight"""
        return self._html_port

    @property
    def ws_port(self) -> Optional[int]:
        """The port supporting WS interaction with EnSight"""
        return self._ws_port

    @property
    def hostname(self) -> str:
        """The hostname of the system hosting the EnSight instance"""
        return self._hostname

    @property
    def launcher(self) -> "Launcher":
        """If a launcher was used to instantiate this session, a reference to the launcher instance."""
        return self._launcher

    @launcher.setter
    def launcher(self, value: "Launcher"):
        self._launcher = value

    @staticmethod
    def help():
        """Open the help pages for the pyansys project in a webbrowser"""
        url = "https://ensight.docs.pyansys.com/"
        webbrowser.open(url)

    def copy_to_session(
        self, localdir: str, filelist: List[str], remotedir: str, progress: bool = False
    ) -> list:
        """Copy a collection of files into the EnSight session

        Copy files from the local filesystem into the filesystem that is hosting
        the EnSight instance.  Note: for LocalLauncher, these are the same filesystems.

        Args:
            localdir:
                The directory on the local filesystem, the source of the files.
            filelist:
                The list of files to copy.  Note: these files will be sourced
                relative to ``localdir`` and written relative to ``remotedir``.
            remotedir:
                The directory on the remote (EnSight) filesystem, the destination
                for the files.
            progress:
                If True and the tqdm module is available, it will be used to
                present a progress bar.
        Returns:
            The list of filenames and sizes that were copied.
        """

        remote_functions = textwrap.dedent(
            """\
                import os
                def copy_write_function__(filename: str, data: bytes) -> None:
                    os.makedirs(os.path.dirname(filename), exist_ok=True)
                    with open(filename, "wb") as fp:
                        fp.write(data)
            """
        )

        self.cmd(remote_functions, do_eval=False)
        out = []
        dirlen = 0
        if localdir:
            dirlen = len(localdir) + 1
        for item in filelist:
            try:
                name = os.path.join(localdir, item)
                if os.path.isfile(name):
                    out.append((name[dirlen:], os.stat(name).st_size))
                else:
                    for root, _, files in os.walk(name):
                        for filename in files:
                            fullname = os.path.join(root, filename)
                            out.append((fullname[dirlen:], os.stat(fullname).st_size))
            except Exception:
                pass
        if progress:
            try:
                from tqdm.auto import tqdm
            except ImportError:
                tqdm = list
        else:
            tqdm = list
        for item in tqdm(out):
            filename = os.path.join(localdir, item[0])
            with open(filename, "rb") as fp:
                data = fp.read()
            name = os.path.join(remotedir, item[0]).replace("\\", "/")
            self.cmd(f"copy_write_function__(r'{name}', {data!r})", do_eval=False)
        return out

    def copy_from_session(
        self, remotedir: str, filelist: List[str], localdir: str, progress: bool = False
    ) -> list:
        """Copy a collection of files out of the EnSight session

        Copy files from the remote, EnSight instance,  filesystem to the local, pyensight
        filesystem.  Note: for LocalLauncher, these are the same filesystems.

        Args:
            remotedir:
                The directory on the remote (EnSight) filesystem, the source
                of the files.
            filelist:
                The list of files to copy.  Note: these files will be sourced
                relative to ``remotedir`` and written relative to ``localdir``.
            localdir:
                The directory on the local filesystem, the destination of the files.
            progress:
                If True and the tqdm module is available, it will be used to
                present a progress bar.
        Returns:
            The list of files that were copied.
        """

        remote_functions = textwrap.dedent(
            """\
                import os
                def copy_walk_function__(remotedir: str, filelist: list) -> None:
                    out = []
                    dirlen = 0
                    if remotedir:
                        dirlen = len(remotedir) + 1
                    for item in filelist:
                        try:
                            name = os.path.join(remotedir, item)
                            if os.path.isfile(name):
                                out.append((name[dirlen:], os.stat(name).st_size))
                            else:
                                for root, _, files in os.walk(name):
                                    for filename in files:
                                        fullname = os.path.join(root, filename)
                                        out.append((fullname[dirlen:], os.stat(fullname).st_size))
                        except Exception:
                            pass
                    return out
                # (needed for flake8)
                def copy_read_function__(filename: str) -> bytes:
                    with open(filename, "rb") as fp:
                        data = fp.read()
                    return data
            """
        )

        self.cmd(remote_functions, do_eval=False)
        names = self.cmd(f"copy_walk_function__(r'{remotedir}', {filelist})", do_eval=True)
        if progress:
            try:
                from tqdm.auto import tqdm
            except ImportError:
                tqdm = list
        else:
            tqdm = list
        for item in tqdm(names):
            name = os.path.join(remotedir, item[0].replace("\\", "/"))
            data = self.cmd(f"copy_read_function__(r'{name}')", do_eval=True)
            full_name = os.path.join(localdir, item[0])
            os.makedirs(os.path.dirname(full_name), exist_ok=True)
            with open(full_name, "wb") as fp:
                fp.write(data)
        return names

    def run_script(self, filename: str) -> Optional[types.ModuleType]:
        """Execute an EnSight Python 'script' file

        In EnSight, there is a notion of a Python 'script' that is normally executed line by
        line in EnSight.  In such scripts, the 'ensight' module is assumed to be preloaded.
        This function runs such scripts by importing them as modules and running the commands
        through the PyEnSight interface.  This is done by installing the session ensight
        object into the module before it is imported.  This makes it possible to use a
        Python debugger with an EnSight Python script, using the pyensight interface.

        Note: the script filename must end with '.py' since it will be imported as a module.

        Parameters
        ----------
        filename : str
            The filename of the Python script to be run (loaded as a module by pyensight).

        Returns
        -------
        types.ModuleType
            The imported module.

        """
        dirname = os.path.dirname(filename)
        if not dirname:
            dirname = "."
        if dirname not in sys.path:
            sys.path.append(dirname)
        module_name, _ = os.path.splitext(os.path.basename(filename))
        # get the module reference
        spec = importlib.util.find_spec(module_name)
        if spec:
            module = importlib.util.module_from_spec(spec)
            # insert an ensight interface into the module
            if self.ensight:
                module.ensight = self.ensight  # type: ignore
                # load (run) the module
                if spec.loader:
                    spec.loader.exec_module(module)
            return module
        return None

    def exec(self, function: Callable, *args, remote: bool = False, **kwargs) -> Any:
        """Run a function containing 'ensight' API calls locally or in the EnSight interpreter
        Given a function of the form::

            def myfunc(ensight, *args, **kwargs):
                ...
                return value

        The exec method allows for the function to be executed in the PyEnSight Python
        interpreter or the (remote) EnSight interpreter.  Thus, a function making a large
        number of RPC calls can run much faster than if run solely in the PyEnSight
        interpreter.

        There are a number of constraints on this capability.
        The function may only use arguments passed to the exec method and can only return a
        single value.  It cannot modify the input arguments.  The input arguments must be
        serializable and the PyEnSight Python interpreter version must match the version in
        EnSight.

        Examples
        --------
        >>> from ansys.pyensight.core import LocalLauncher
        >>> session = LocalLauncher().start()
        >>> options = dict()
        >>> options['Verbose mode'] = 'OFF'
        >>> options['Use ghost elements'] = 'OFF'
        >>> options['Long names'] = 'OFF'
        >>> options['Compatibility mode'] = 'ON'
        >>> options['Move Transient Parts'] = 'ON'
        >>> options['Element type'] = 'Tri 3'
        >>> options['Boundary ghosts'] = 'None'
        >>> options['Spread out parts'] = 'Legacy'
        >>> options['Number of spheres'] = 100
        >>> options['Number of cubes'] = 100
        >>> options['Number of planes'] = 0
        >>> options['Number of elements start'] = 1000
        >>> options['Number of elements end'] = 1000
        >>> options['Number of timesteps'] = 1
        >>> options['Part scaling factor'] = 1.000000e+00
        >>> options['Random number seed'] = 0
        >>> options['Number of scalars'] = 3
        >>> options['Number of vectors'] = 3
        >>> options['Number of constants'] = 3
        >>> session.load_data("dummy", file_format="Synthetic", reader_options=options)

        >>> def count(ensight, attr, value):
        >>>     import time
        >>>     start = time.time()
        >>>     count = 0
        >>>     for p in ensight.objs.core.PARTS:
        >>>         if p.getattr(attr) == value:
        >>>             count += 1
        >>> print(count(session.ensight, "VISIBLE", True))
        >>> print(session.exec(count, "VISIBLE", True))
        >>> print(session.exec(count, "VISIBLE", True, remote=True))

        """
        if remote:
            # remote execution only supported in 2023 R1 or later
            if int(self._cei_suffix) < 231:
                raise RuntimeError("Remote function execution only supported in 2023 R1 and later")
            local_python_version = platform.python_version_tuple()
            if self._ensight_python_version[0:2] != local_python_version[0:2]:
                vers = "Local and remote Python versions must match: "
                vers += ".".join(local_python_version)
                vers += " vs "
                vers += ".".join(self._ensight_python_version)
                raise RuntimeError(vers)
            import dill  # pylint: disable=import-outside-toplevel

            # Create a bound object that allows for direct encoding of the args/kwargs params
            # The new function would be bound_function(ensight) where the args are captured
            # in the lambda.
            bound_function = lambda ens: function(ens, *args, **kwargs)  # noqa: E731
            # Serialize the bound function
            serialized_function = dill.dumps(bound_function, recurse=True)
            self.cmd("import dill", do_eval=False)
            # Run it remotely, passing the instance ensight instead of self._ensight
            cmd = f"dill.loads(eval(repr({serialized_function})))(ensight)"
            return self.cmd(cmd)
        else:
            return function(self._ensight, *args, **kwargs)

    def show(
        self,
        what: str = "image",
        width: Optional[int] = None,
        height: Optional[int] = None,
        temporal: bool = False,
        aa: int = 4,
        fps: float = 30.0,
        num_frames: Optional[int] = None,
    ) -> "renderable.Renderable":
        """Cause the current EnSight scene to be captured or otherwise made available for
        display in a web browser.  The appropriate visuals are generated and the renderable
        object for viewing is returned.  If the session is in a Jupyter notebook, the cell
        in which the show() command is issued will be updated with the renderable display.

        Legal values for the 'what' argument include:

        * 'image' simple rendered png image
        * 'deep_pixel' EnSight deep pixel image
        * 'animation' renders an mpeg4 movie
        * 'webgl' interactive webgl-based browser viewer
        * 'sgeo' webgl-based renderer using an incremental scene graph transport mechanism
        * 'remote' remote rendering based interactive EnSight viewer
        * 'remote_scene' remote rendering based interactive EnSight viewer

        Parameters
        ----------
        what :
            The type of scene display to generate.
        width :
            The width of the rendered entity
        height :
            The height of the rendered entity
        temporal :
            If True, include all timesteps in 'webgl' views
        aa :
            The number of antialiasing passes to use when rendering images
        fps :
            For animation playback, the number of frames per second to use
        num_frames :
            For animation playback, number of frames of static timestep to record

        Returns
        -------
        renderable.Renderable
            The Renderable object instance

        Raises
        ------
        RuntimeError
            if it is not possible to generate the content

        Examples
        --------
        Render an image and display it in a browser.  Rotate the scene and update the display

        >>> image = session.show('image', width=800, height=600)
        >>> image.browser()
        >>> session.ensight.view_transf.rotate(30, 30, 0)
        >>> image.update()
        >>> image.browser()

        """
        self._establish_connection()
        if self._html_port is None:
            raise RuntimeError("No websocketserver has been associated with this Session")

        kwargs = dict(
            height=height, width=width, temporal=temporal, aa=aa, fps=fps, num_frames=num_frames
        )
        if self._jupyter_notebook:
            from IPython.display import display

            # get the cell DisplayHandle instance
            kwargs["cell_handle"] = display("", display_id=True)

        render = None
        if what == "image":
            render = RenderableImage(self, **kwargs)
        elif what == "deep_pixel":
            render = RenderableDeepPixel(self, **kwargs)
        elif what == "animation":
            render = RenderableMP4(self, **kwargs)
        elif what == "webgl":
            render = RenderableWebGL(self, **kwargs)
        elif what == "sgeo":
            # the SGEO protocol is only supported in 2023 R1 and higher
            if int(self._cei_suffix) < 231:
                # Use the AVZ viewer in older versions of EnSight
                render = RenderableWebGL(self, **kwargs)
            else:
                render = RenderableSGEO(self, **kwargs)
        elif what == "remote":
            render = RenderableVNC(self, **kwargs)
        elif what == "remote_scene":
            render = RenderableEVSN(self, **kwargs)

        if render is None:
            raise RuntimeError("Unable to generate requested visualization")

        return render

    def cmd(self, value: str, do_eval: bool = True) -> Any:
        """Run a command in EnSight and return the results

        Parameters
        ----------
        value :
            String of the command to run
        do_eval :

        value: str :

        do_eval: bool :
             (Default value = True)

        Returns
        -------
            result of the string being executed as Python inside EnSight

        Examples
        --------

        >>> print(session.cmd("10+4"))
            14
        """
        self._establish_connection()
        ret = self._grpc.command(value, do_eval=do_eval)
        if do_eval:
            ret = self._convert_ctor(ret)
            return eval(ret, dict(session=self, ensobjlist=ensobjlist))
        return ret

    def geometry(self, what: str = "glb") -> bytes:
        """Return the current EnSight scene as a geometry file

        Parameters
        ----------
        what : str
            the file format to return

        Returns
        -------
        type
            the generated geometry file as a bytes object

        Examples
        --------
        >>> data = session.geometry()
        >>> with open("file.glb", "wb") as fp:
        >>> fp.write(data)

        """
        self._establish_connection()
        return self._grpc.geometry()

    def render(self, width: int, height: int, aa: int = 1) -> bytes:
        """Render the current EnSight scene and return a PNG image

        Parameters
        ----------
        width : int
            width of the rendered image in pixels
        height : int
            height of the rendered image in pixels
        aa : int
            number of antialiasing passes to use

        Returns
        -------
            PNG image

        Examples
        --------
        >>> data = session.render(1920, 1080, aa=4)
        >>> with open("file.png", "wb") as fp:
        >>> fp.write(data)

        """
        self._establish_connection()
        return self._grpc.render(width=width, height=height, aa=aa)

    def close(self) -> None:
        """Close this session.

        Terminate the current session and its gRPC connection.
        """
        if self._launcher and self._halt_ensight_on_close:
            self._launcher.close(self)
        else:
            # lightweight shutdown, just close the gRPC connection
            self._grpc.shutdown(stop_ensight=False)
        self._launcher = None

    def _build_utils_interface(self) -> None:
        """Build the ensight.utils interface.

        Walk the .py files in the utils directory.  Create instances
        of the classes in those files and place them in the
        Session.ensight.utils namespace.
        """
        self._ensight.utils = types.SimpleNamespace()
        _utils_dir = os.path.join(os.path.dirname(__file__), "utils")
        if _utils_dir not in sys.path:
            sys.path.insert(0, _utils_dir)
        onlyfiles = [f for f in listdir(_utils_dir) if os.path.isfile(os.path.join(_utils_dir, f))]
        for _filename in onlyfiles:
            _filename = os.path.join(_utils_dir, _filename)
            try:
                # get the module and class names
                _name = os.path.splitext(os.path.basename(_filename))[0]
                if _name == "__init__":
                    continue
                _cap_name = _name[0].upper() + _name[1:]
                # import the module
                spec = importlib.util.spec_from_file_location(
                    f"ansys.pyensight.utils.{_name}", _filename
                )
                if spec:
                    _module = importlib.util.module_from_spec(spec)
                    if spec.loader:
                        spec.loader.exec_module(_module)
                    # get the class from the module (query.py filename -> Query() object)
                    _the_class = getattr(_module, _cap_name)
                    # Create an instance, using ensight as the EnSight interface
                    # and place it in this module.
                    setattr(self._ensight.utils, _name, _the_class(self._ensight))
            except Exception as e:
                # Warn on import errors
                print(f"Error loading ensight.utils from: '{_filename}' : {e}")

    def load_data(
        self,
        data_file: str,
        result_file: Optional[str] = None,
        file_format: Optional[str] = None,
        reader_options: Optional[dict] = None,
        new_case: bool = False,
        representation: str = "3D_feature_2D_full",
    ) -> None:
        """Load a dataset into the EnSight instance

        Given the name of a file, load the data from that file into EnSight.  The new data will
        replace any currently loaded data in the session.

        Parameters
        ----------
        data_file : str
            Filename to load.
        result_file :
            For dual-file datasets, the second data file.
        file_format : str
            The name of the EnSight reader to be used to read.  If None, ask
            EnSight to select a reader.
        reader_options : dict
            Dictionary of reader specific option/value pairs which can be used
            to customize the reader behavior.
        new_case : bool
            If True, the dataset will be loaded into another case.  If False, the
            dataset will replace the one (if any) loaded in the existing current case.
        representation : str
            The representation for parts loaded by default.  The default value is
            "3D_feature_2D_full".

        Raises
        ------
        RuntimeError
            if EnSight cannot guess the file format or an error occurs while the
            data is being read.

        Examples
        -------

        >>> from ansys.pyensight.core import LocalLauncher
        >>> session = LocalLauncher().start()
        >>> session.load_data(r'D:\data\CFX\example_data.res')

        """
        self._establish_connection()
        # what application are we talking to?
        target = self.cmd("ensight.version('product').lower()")
        if target == "envision":
            cmd = f'ensight.data.replace(r"""{data_file}""")'
            if self.cmd(cmd) != 0:
                raise RuntimeError("Unable to load the dataset.")
            return

        # Handle case changes...
        cmds = [
            'ensight.case.link_modelparts_byname("OFF")',
            'ensight.case.create_viewport("OFF")',
            'ensight.case.apply_context("OFF")',
            "ensight.case.reflect_model_in(\"'none'\")",
        ]
        for cmd in cmds:
            self.cmd(cmd, do_eval=False)

        if new_case:
            # New case
            new_case_name = None
            for case in self.ensight.objs.core.CASES:
                if case.ACTIVE == 0:
                    new_case_name = case.DESCRIPTION
                    break
            if new_case_name is None:
                raise RuntimeError("No cases available for adding.")
            cmd = f'ensight.case.add("{new_case_name}")'
            self.cmd(cmd, do_eval=False)
            cmd = f'ensight.case.select("{new_case_name}")'
            self.cmd(cmd, do_eval=False)
        else:
            # Case replace
            current_case_name = self.ensight.objs.core.CURRENTCASE[0].DESCRIPTION
            cmd = f'ensight.case.replace("{current_case_name}", "{current_case_name}")'
            self.cmd(cmd, do_eval=False)
            cmd = f'ensight.case.select("{current_case_name}")'
            self.cmd(cmd, do_eval=False)

        # Attempt to find the file format if none is specified
        if file_format is None:
            try:
                cmd = "ensight.objs.core.CURRENTCASE[0]"
                cmd += f'.queryfileformat(r"""{data_file}""")["reader"]'
                file_format = self.cmd(cmd)
            except RuntimeError:
                raise RuntimeError(f"Unable to determine file format for {data_file}")

        # Load the data
        cmds = [
            "ensight.part.select_default()",
            "ensight.part.modify_begin()",
            f'ensight.part.elt_representation("{representation}")',
            "ensight.part.modify_end()",
            'ensight.data.binary_files_are("native")',
            f'ensight.data.format("{file_format}")',
        ]
        if reader_options:
            for key, value in reader_options.items():
                option = f"""ensight.data.reader_option("{repr(key)} {repr(value)}")"""
                cmds.append(option)
        if result_file:
            cmds.append(f'ensight.data.result(r"""{result_file}""")')
        cmds.append("ensight.data.shift_time(1.000000, 0.000000, 0.000000)")
        cmds.append('ensight.solution_time.monitor_for_new_steps("off")')
        cmds.append(f'ensight.data.replace(r"""{data_file}""")')
        for cmd in cmds:
            if self.cmd(cmd) != 0:
                raise RuntimeError("Unable to load the dataset.")

    def load_example(
        self, example_name: str, uncompress: bool = False, root: Optional[str] = None
    ) -> str:
        """Load an example dataset
        Download an EnSight session file from a known location and load it into
        the current EnSight instance.  The url for the dataset is formed by
        combining the example_name with a root url.  The default based url is
        provided by Ansys, but can be overridden with the root argument.

        Parameters
        ----------
        example_name:
            The name of the EnSight session file (.ens) to download and load.
        uncompress:
            If True, unzip the downloaded file into the returned directory name.
        root:
            The base url for the download.

        Returns
        -------
        type
            The pathname to the downloaded file in the EnSight session.

        Examples
        --------
        >>> from ansys.pyensight.core import LocalLauncher
        >>> session = LocalLauncher().start()
        >>> session.load_example("fluent_wing_example.ens")
        >>> remote = session.show("remote")
        >>> remote.browser()

        """
        base_uri = "https://s3.amazonaws.com/www3.ensight.com/PyEnSight/ExampleData"
        if root is not None:
            base_uri = root
        uri = f"{base_uri}/{example_name}"
        pathname = f"{self.launcher.session_directory}/{example_name}"
        script = "import requests\n"
        script += "import shutil\n"
        script += "import os\n"
        script += f'url = "{uri}"\n'
        script += f'outpath = r"""{pathname}"""\n'
        script += "with requests.get(url, stream=True) as r:\n"
        script += "    with open(outpath, 'wb') as f:\n"
        script += "        shutil.copyfileobj(r.raw, f)\n"
        if uncompress:
            # in this case, remove the extension and unzip the file
            pathname_dir = os.path.splitext(pathname)[0]
            script += "outpath_dir = os.path.splitext(outpath)[0]\n"
            script += "os.mkdir(outpath_dir)\n"
            script += "shutil.unpack_archive(outpath, outpath_dir, 'zip')\n"
            # return the directory name
            pathname = pathname_dir
        else:
            script += "ensight.objs.ensxml_restore_file(outpath)\n"
        self.cmd(script, do_eval=False)
        return pathname

    def add_callback(
        self, target: Any, tag: str, attr_list: list, method: Callable, compress: bool = True
    ) -> None:
        """Register a callback with an event tuple

        For a given target object (e.g. "ensight.objs.core") and a list
        of attributes (e.g. ["PARTS", "VARIABLES"]) set up a callback
        (method) to be called with a URL encoded with the supplied (tag)
        whenever one of the listed attributes change.  The callback is
        in a URL of the form: grpc://{sessionguid}/{tag}?enum={attribute}&uid={objectid}
        Only one callback with the noted tag can be used in the session.

        Parameters
        ----------
        target:
            The name of the target object or the name of a class as a string to
            match all objects of that class.  Note: a proxy class reference is
            also allowed (e.g. session.ensight.objs.core).
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

        Examples
        --------
        A string like this :

        'Event :
            grpc://f6f74dae-f0ed-11ec-aa58-381428170733/partlist?enum=PARTS&uid=221'
        will be printed when the dataset is loaded and the partlist changes.

        >>> from ansys.pyensight.core import LocalLauncher
        >>> s = LocalLauncher().start()
        >>> def cb(v: str):
        >>> print("Event:", v)
        >>>     s.add_callback("ensight.objs.core", "partlist", ["PARTS"], cb)
        >>> s.load_data(r"D:\ANSYSDev\data\CFX\HeatingCoil_001.res")
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
        if hasattr(target, "__OBJID__"):
            target = self.remote_obj(target.__OBJID__)
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

        Parameters
        ----------
        tag : str
            The callback string tag

        Raises
        ------
        RuntimeError
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

        Parameters
        ----------
        cmd : str
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
        """Generate a string that, for a given ENSOBJ ID, returns a proxy object instance

        Parameters
        ----------
        ensobjid: int
            ID if ENSOBJ

        Returns
        -------
        str
            string with the proxy instance
        """
        return f"ensight.objs.wrap_id({ensobjid})"

    def _prune_hash(self) -> None:
        """The ensobj hash table may need flushing if it gets too big, do that here"""
        if len(self._ensobj_hash) > 1000000:
            self._ensobj_hash = {}

    def add_ensobj_instance(self, obj: "ENSOBJ") -> None:
        """Add a new ENSOBJ instance to the hash table

        Parameters
        ----------
        obj: "ENSOBJ"

        """
        self._ensobj_hash[obj.__OBJID__] = obj

    def obj_instance(self, ensobjid: int) -> Optional["ENSOBJ"]:
        """Get any existing proxy object associated with a given ID

        Parameters
        ----------
        ensobjid: int
            ID if ENSOBJ

        """
        return self._ensobj_hash.get(ensobjid, None)

    def _obj_attr_subtype(self, classname: str) -> Tuple[Optional[int], Optional[dict]]:
        """Get subtype information for a given class
        For the input classname, return the proper Python proxy classname and if the
        class supports subclasses, the attribute id number of the differentiating
        attribute.

        Parameters
        ----------
        classname : str
            The root classname to lookup

        Returns
        -------
        Tuple[Optional[int], Optional[dict]]
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
            part_lookup_dict[15] = "ENS_PART_BUILT_UP"
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
            return self.ensight.objs.enums.ANNOTTYPE, annot_lookup_dict

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

        Parameters
        ----------
        s: str :
            string to convert.

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
        s = s.strip()
        if s.startswith("[") and s.endswith("]"):
            s = "ensobjlist(" + s + ")"
        return s

    def capture_context(self, full_context: bool = False) -> "enscontext.EnsContext":
        """Capture the current EnSight instance state

        Cause the EnSight instance to save a context and return an EnsContext object
        representing that saved state.

        Parameters
        ----------
        full_context : bool
            If True, the saved context will include all aspects of the EnSight

        Returns
        -------
        enscontext.EnsContext

        Examples
        --------
        >>> ctx = session.capture_context()
        >>> ctx.save("session_context.ctxz")

        """
        self.cmd("import ansys.api.pyensight.enscontext", do_eval=False)
        data_str = self.cmd(
            f"ansys.api.pyensight.enscontext._capture_context(ensight,{full_context})", do_eval=True
        )
        context = EnsContext()
        context._from_data(data_str)
        return context

    def restore_context(self, context: "enscontext.EnsContext") -> None:
        """Restore the current EnSight instance state

        Restore EnSight to the state stored in an EnsContext object that was either
        read from disk or returned by the capture_context() method.

        Parameters
        ----------
        context :
            The context to set the current EnSight instance to.

        Example
        -------
        >>> tmp_ctx = session.capture_context()
        >>> session.restore_context(EnsContext("session_context.ctxz"))
        >>> session.restore_context(tmp_ctx)
        """
        data_str = context._data(b64=True)
        self.cmd("import ansys.pyensight.core.enscontext", do_eval=False)
        self.cmd(
            f"ansys.pyensight.enscontext._restore_context(ensight,'{data_str}')", do_eval=False
        )
