"""Session module.

The ``Session`` module allows PyEnSight to control the EnSight session.

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
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse
from urllib.request import url2pathname
import uuid
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
    RenderableVNCAngular,
    RenderableWebGL,
)
import requests

if TYPE_CHECKING:
    from ansys.api.pyensight import ensight_api
    from ansys.pyensight.core import enscontext, ensight_grpc, renderable
    from ansys.pyensight.core.ensobj import ENSOBJ


class InvalidEnSightVersion(Exception):
    pass


class Session:
    """Provides for accessing an EnSight ``Session`` instance.

    The ``Session`` object wraps the various connections to an EnSight instance. It includes
    the location of the installation and the gRPC, HTML and WS ports used to talk to the
    EnSight session. In most cases, a ``Session`` instance is created using Launcher
    class methods, but if the EnSight session is already running, an instance can be
    created directly to wrap this running EnSight session.

    If the ``Session`` object is created via a Launcher ``start()`` method call, when the
    session object is garbage collected, the EnSight instance is automatically stopped.
    To prevent this behavior (and leave the EnSight instance running), set the
    ``halt_ensight_on_close`` property to ``False``.

    A gRPC connection is required to interact with an EnSight session. The host, gRPC
    port number, and secret key must be specified. The HTML and WS ports, which are used to
    enable the :func:`show<ansys.pyensight.core.Session.show>`) method, also require that
    an instance of the websocket server is running.

    Parameters
    ----------
    host : str, optional
        Name of the host that the EnSight gRPC service is running on.
        The default is ``"127.0.0.1"``, which is the localhost.
    install_path : str, optional
        Path to the CEI directory to launch EnSight from.
        The default is ``None``.
    secret_key : str, optional
        Shared session secret key for validating the gRPC communication.
        The default is ``""``.
    grpc_port : int, optional
        Port number of the EnSight gRPC service. The default is ``12345``.
    html_host : str, optional
        Optional hostname for html connections if different than host
        Used by Ansys Lab and reverse proxy servers
    html_port : int, optional
        Port number of the websocket server's HTTP server. The default is
        ``None``.
    ws_port : int, optional
        Port number of the websocket server's WS server. The default is
        ``None``.
    session_directory : str, optional
        Directory on the server for local data storage. The default is
        ``None``.
    timeout : float, optional
        Number of seconds to try a gRPC connection before giving up.
        The default is ``120``.
    rest_api : bool, optional
        Whether to enable the EnSight REST API for the remote EnSight instance.
        The default is ``False``.
    sos : bool, optional
        Whether the remote EnSight instance is to use the SOS (Server
        of Servers) feature. The default is ``False``.

    Examples
    --------

    >>> from ansys.pyensight.core import Session
    >>> session = Session(host="127.0.0.1", grpc_port=12345, http_port=8000, ws_port=8100)

    >>> from ansys.pyensight.core import LocalLauncher
    >>> session = LocalLauncher().start()

    >>> # Launch an instance of EnSight, then create a second connection to the instance
    >>> from ansys.pyensight.core import LocalLauncher, Session
    >>> launched_session = LocalLauncher().start()
    >>> # Get a string that can be used to create a second connection
    >>> session_string = str(launched_session)
    >>> # Create a second connection to the same EnSight instance
    >>> connected_session = eval(session_string)

    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        install_path: Optional[str] = None,
        secret_key: str = "",
        grpc_port: int = 12345,
        html_hostname: Optional[str] = None,
        html_port: Optional[int] = None,
        ws_port: Optional[int] = None,
        session_directory: Optional[str] = None,
        timeout: float = 120.0,
        rest_api: bool = False,
        sos: bool = False,
    ) -> None:
        # every session instance needs a unique name that can be used as a cache key
        self._session_name = str(uuid.uuid1())
        # when objects come into play, we can reuse them, so hash ID to instance here
        self._ensobj_hash: Dict[int, "ENSOBJ"] = {}
        self._language = "en"
        self._rest_api_enabled = rest_api
        self._sos_enabled = sos
        self._timeout = timeout
        self._cei_home = ""
        self._cei_suffix = ""
        self._hostname = host
        self._install_path = install_path
        self._launcher = None
        if html_hostname == "" or html_hostname is None:
            # if we weren't given an html host, use the hostname
            self._html_hostname = self._hostname
        else:
            self._html_hostname = html_hostname
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
        self._grpc.session_name = self._session_name

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

        # Because this session can have allocated significant external resources
        # we very much want a chance to close it up cleanly. It is legal to
        # call close() twice on this class if needed.
        atexit.register(self.close)

        # Speed up subtype lookups:
        self._subtype_tables = {}
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
        self._subtype_tables["ENS_PART"] = part_lookup_dict
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
        self._subtype_tables["ENS_ANNOT"] = annot_lookup_dict
        tool_lookup_dict = dict()
        tool_lookup_dict[0] = "ENS_TOOL_CURSOR"
        tool_lookup_dict[1] = "ENS_TOOL_LINE"
        tool_lookup_dict[2] = "ENS_TOOL_PLANE"
        tool_lookup_dict[3] = "ENS_TOOL_BOX"
        tool_lookup_dict[4] = "ENS_TOOL_CYLINDER"
        tool_lookup_dict[5] = "ENS_TOOL_CONE"
        tool_lookup_dict[6] = "ENS_TOOL_SPHERE"
        tool_lookup_dict[7] = "ENS_TOOL_REVOLUTION"
        self._subtype_tables["ENS_TOOL"] = tool_lookup_dict

    def __repr__(self):
        # if this is called from in the ctor, self.launcher might be None.
        session_dir = ""
        if self.launcher:
            session_dir = self.launcher.session_directory
        s = f"Session(host='{self.hostname}', secret_key='{self.secret_key}', "
        s += f"sos={self.sos}, rest_api={self.rest_api}, "
        s += f"html_hostname='{self.html_hostname}', html_port={self.html_port}, "
        s += f"grpc_port={self._grpc_port}, "
        s += f"ws_port={self.ws_port}, session_directory=r'{session_dir}')"
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
                    self._check_rest_connection()
                    return
                except OSError:
                    pass
            self._grpc.connect(timeout=self._timeout)
        raise RuntimeError("Unable to establish a gRPC connection to EnSight.")

    def _check_rest_connection(self) -> None:
        """Validate the REST API connection works

        Use requests to see if the REST API is up and running (it takes time
        for websocketserver to make a gRPC connection as well).

        """
        if not self.rest_api:
            return
        #
        #
        # even when using PIM and a proxy server (Ansys Lab) this connects
        # directly from the python running in the Notebook (the front-end)
        # to the EnSight Docker Container and not the proxy server.
        # Thus, here we use 'http', the private hostname, and the html port
        # (which is the same on the proxy server).
        url = f"http://{self._hostname}:{self.html_port}/ensight/v1/session/exec"
        time_start = time.time()
        while time.time() - time_start < self._timeout:
            try:
                _ = requests.put(
                    url,
                    json="enscl.rest_test = 30*20",
                    headers=dict(Authorization=f"Bearer {self.secret_key}"),
                )
                return
            except Exception:
                pass
            time.sleep(0.5)
        raise RuntimeError("Unable to establish a REST connection to EnSight.")  # pragma: no cover

    @property
    def name(self) -> str:
        """The session name is a unique identifier for this Session instance.  It
        is used by EnSight to maintain session specific data values within the
        EnSight instance."""
        return self._session_name

    @property
    def language(self) -> str:
        """Current language specification for the EnSight session. Various
        information calls return their information in the target language
        if possible. The default is ``"en"``.

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
        """Flag for indicating whether to halt EnSight on close. If this property
        is ``True`` and the session was created via a launcher, when the session
        is closed, the EnSight instance is stopped.

        .. Note::
           While this flag prevents the :func:`close<ansys.pyensight.core.Session.close>`
           method from shutting down EnSight, depending on how the host Python interpreter is configured,
           the EnSight session may still be halted. For example, this behavior can
           occur in Jupyter Lab.
        """
        return self._halt_ensight_on_close

    @halt_ensight_on_close.setter
    def halt_ensight_on_close(self, value: bool) -> None:
        self._halt_ensight_on_close = value

    @property
    def timeout(self) -> float:
        """Amount of time in seconds to try a gRPC connection before giving up."""
        return self._timeout

    @timeout.setter
    def timeout(self, value: float) -> None:
        self._timeout = value

    @property
    def cei_home(self) -> str:
        """Value of ``CEI_HOME`` for the connected EnSight session."""
        return self._cei_home

    @property
    def cei_suffix(self) -> str:
        """Suffix string of the connected EnSight session. For example, ``222``."""
        return self._cei_suffix

    @property
    def jupyter_notebook(self) -> bool:
        """Flag indicating if the session is running in a Jupyter notebook and should use
        the display features of that interface.

        """
        return self._jupyter_notebook

    @jupyter_notebook.setter
    def jupyter_notebook(self, value: bool) -> None:
        self._jupyter_notebook = value

    @property
    def ensight(self) -> "ensight_api.ensight":
        """Core EnSight API wrapper."""
        return self._ensight

    @property
    def grpc(self) -> "ensight_grpc.EnSightGRPC":
        """The gRPC wrapper instance used by this session to access EnSight."""
        return self._grpc

    @property
    def secret_key(self) -> str:
        """Secret key used for communication validation in the gRPC instance."""
        return self._secret_key

    @property
    def html_port(self) -> Optional[int]:
        """Port supporting HTML interaction with EnSight."""
        return self._html_port

    @property
    def ws_port(self) -> Optional[int]:
        """Port supporting WS interaction with EnSight."""
        return self._ws_port

    @property
    def hostname(self) -> str:
        """Hostname of the system hosting the EnSight instance."""
        return self._hostname

    @property
    def html_hostname(self) -> str:
        """Hostname of the system hosting the EnSight web server instance."""
        return self._html_hostname

    @property
    def launcher(self) -> "Launcher":
        """Reference to the launcher instance if a launcher was used to instantiate the session."""
        return self._launcher

    @launcher.setter
    def launcher(self, value: "Launcher"):
        self._launcher = value

    @property
    def sos(self) -> bool:
        """
        Flag indicating if the remote EnSight session is running in SOS (Server of Server) mode.
        """
        return self._sos_enabled

    @property
    def rest_api(self) -> bool:
        """
        Flag indicating if the remote EnSight session supports the REST API.
        """
        return self._rest_api_enabled

    @staticmethod
    def help():
        """Open the documentation for PyEnSight in a web browser."""
        url = "https://ensight.docs.pyansys.com/"
        webbrowser.open(url)

    def copy_to_session(
        self,
        local_prefix: str,
        filelist: List[str],
        remote_prefix: Optional[str] = None,
        progress: bool = False,
    ) -> list:
        """Copy a collection of files into the EnSight session.

        Copy files from the local filesystem into the filesystem that is hosting
        the EnSight instance.

        .. note::
           For a :class:`LocalLauncheransys.pyensight.core.LocalLauncher>`
           instance, these are the same filesystems.

        Parameters
        ----------
        local_prefix : str
            URL prefix to use for all files specified for the ``filelist``
            parameter. The only protocol supported is ``'file://'``, which
            is the local filesystem.
        filelist : list
            List of files to copy. These files are prefixed with ``local_prefix``
            and written relative to the ``remote_prefix`` parameter appended to
            ``session.launcher.session_directory``.
        remote_prefix : str
            Directory on the remote (EnSight) filesystem, which is the
            destination for the files. This prefix is appended to
            ``session.launcher.session_directory``.
        progress : bool, optional
            Whether to show a progress bar. The default is ``False``. If ``True`` and
            the ``tqdm`` module is available, a progress bar is shown.

        Returns
        -------
        list
            List of the filenames that were copied and their sizes.

        Examples
        --------
        >>> the_files = ["fluent_data_dir", "ensight_script.py"]
        >>> session.copy_to_session("file:///D:/data", the_files, progress=True)

        >>> the_files = ["fluent_data_dir", "ensight_script.py"]
        >>> session.copy_to_session("file:///scratch/data", the_files, remote_prefix="data")

        """
        uri = urlparse(local_prefix)
        if uri.scheme != "file":
            raise RuntimeError("Only the file:// protocol is supported for the local_prefix")
        localdir = url2pathname(uri.path)

        remote_functions = textwrap.dedent(
            """\
                import os
                def copy_write_function__(filename: str, data: bytes) -> None:
                    os.makedirs(os.path.dirname(filename), exist_ok=True)
                    with open(filename, "ab") as fp:
                        fp.write(data)
            """
        )

        self.cmd(remote_functions, do_eval=False)

        out = []
        dirlen = 0
        if localdir:
            # we use dirlen + 1 here to remove the '/' inserted by os.path.join()
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
            out_dir = self.launcher.session_directory.replace("\\", "/")
            if remote_prefix:
                out_dir += f"/{remote_prefix}"
            name = out_dir + f"/{item[0]}"
            name = name.replace("\\", "/")
            # Walk the file in chunk size blocks
            chunk_size = 1024 * 1024
            with open(filename, "rb") as fp:
                while True:
                    data = fp.read(chunk_size)
                    if data == b"":
                        break
                    self.cmd(f"copy_write_function__(r'{name}', {data!r})", do_eval=False)
        return out

    def copy_from_session(
        self,
        local_prefix: str,
        filelist: List[str],
        remote_prefix: Optional[str] = None,
        progress: bool = False,
    ) -> list:
        """Copy a collection of files out of the EnSight session.

        Copy files from the filesystem of the remote EnSight instance to the
        filesystem of the local PyEnsight instance.

        .. note::
           For a :class:`LocalLauncheransys.pyensight.core.LocalLauncher>`
           instance, these are the same filesystems.

        Parameters
        ----------
        local_prefix : str
            URL prefix of the location to save the files to. The only
            protocol currently supported is ``'file://'``, which is the
            local filesystem.
        filelist : list
            List of the files to copy. These files are prefixed
                with ``session.launcher.session_directory/remote_prefix`` and written
                relative to URL prefix specified for the ``local_prefix`` parameter.
        remote_prefix : str, optional
            Directory on the remote (EnSight) filesystem that is the source
            for the files. This prefix is appended to ``session.launcher.session_directory``.
        progress : bool, optional
            Whether to show a progress bar. The default is ``False``. If ``True`` and
            the ``tqdm`` module is available, a progress bar is shown.

        Returns
        -------
        list
            List of the files that were copied.

        Examples
        --------
        >>> the_files = ["fluent_data_dir", "ensight_script.py"]
        >>> session.copy_from_session("file:///D:/restored_data", the_files, progress=True)

        >>> the_files = ["fluent_data_dir", "ensight_script.py"]
        >>> session.copy_from_session("file:///scratch/restored_data", the_files,
                remote_prefix="data")
        """

        uri = urlparse(local_prefix)
        if uri.scheme != "file":
            raise RuntimeError("Only the file:// protocol is supported for the local_prefix")
        localdir = url2pathname(uri.path)

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
                def copy_read_function__(filename: str, offset: int, numbytes: int) -> bytes:
                    with open(filename, "rb") as fp:
                        fp.seek(offset)
                        data = fp.read(numbytes)
                    return data
            """
        )

        self.cmd(remote_functions, do_eval=False)

        remote_directory = self.launcher.session_directory
        if remote_prefix:
            remote_directory = f"{remote_directory}/{remote_prefix}"
        remote_directory = remote_directory.replace("\\", "/")
        names = self.cmd(f"copy_walk_function__(r'{remote_directory}', {filelist})", do_eval=True)
        if progress:
            try:
                from tqdm.auto import tqdm
            except ImportError:
                tqdm = list
        else:
            tqdm = list
        for item in tqdm(names):
            name = f"{remote_directory}/{item[0]}".replace("\\", "/")
            full_name = os.path.join(localdir, item[0])
            os.makedirs(os.path.dirname(full_name), exist_ok=True)
            with open(full_name, "wb") as fp:
                offset = 0
                chunk_size = 1024 * 1024
                while True:
                    data = self.cmd(
                        f"copy_read_function__(r'{name}', {offset}, {chunk_size})", do_eval=True
                    )
                    if len(data) == 0:
                        break
                    fp.write(data)
                    offset += chunk_size
        return names

    def run_script(self, filename: str) -> Optional[types.ModuleType]:
        """Run an EnSight Python script file.

        In EnSight, there is a notion of a Python *script* that is normally run line by
        line in EnSight. In such scripts, the ``ensight`` module is assumed to be preloaded.
        This method runs such scripts by importing them as modules and running the commands
        through the PyEnSight interface. This is done by installing the PyEnsight ``Session``
        object into the module before it is imported. This makes it possible to use a
        Python debugger with an EnSight Python script, using the PyEnSight interface.

        .. note::

            Because the Python script is imported as a module, the script filename must
            have a ``.py`` extension.


        Parameters
        ----------
        filename : str
            Filename of the Python script to run, which is loaded as a module by PyEnSight.

        Returns
        -------
        types.ModuleType
            Imported module.

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
        """Run a function containing EnSight API calls locally or in the EnSight interpreter.

        The function is in this form::

            def myfunc(ensight, *args, **kwargs):
                ...
                return value

        The ``exec()`` method allows for the function to be executed in the PyEnSight Python
        interpreter or the (remote) EnSight interpreter. Thus, a function making a large
        number of RPC calls can run much faster than if it runs solely in the PyEnSight
        interpreter.

        These constraints exist on this capability:

        - The function may only use arguments passed to the ``exec()`` method and can only
          return a single value.
        - The function cannot modify the input arguments.
        - The input arguments must be serializable and the PyEnSight Python interpreter
          version must match the version in EnSight.

        Parameters
        ----------
        remote : bool, optional
            Whether to execute the function in the (remote) EnSight interpreter.

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
        """Capture the current EnSight scene or otherwise make it available for
        display in a web browser.

        This method generates the appropriate visuals and returns the renderable
        object for viewing. If the session is in a Jupyter notebook, the cell
        in which the ``show()`` method is issued is updated with the renderable display.

        Parameters
        ----------
        what : str, optional
            Type of scene display to generate. The default is ``"image"``.
            Options are:

            * ``image``: Simple rendered PNG image
            * ``deep_pixel``: EnSight deep pixel image
            * ``animation``: MPEG4 movie
            * ``webgl``: Interactive WebGL-based browser viewer
            * ``remote``: Remote rendering-based interactive EnSight viewer
            * ``remote_scene``: Remote rendering-based interactive EnSight viewer

        width : int, optional
            Width of the rendered entity. The default is ``None``.
        height : int, optional
            Height of the rendered entity. The default is ``None``.
        temporal : bool, optional
            Whether to include all timesteps in WebGL views. The default is ``False``.
        aa : int, optional
            Number of antialiasing passes to use when rendering images. The
            default is ``4``.
        fps : float, optional
            Number of frames per second to use for animation playback. The default
            is ``30``.
        num_frames : int, optional
            Number of frames of static timestep to record for animation playback.

        Returns
        -------
        renderable.Renderable

        Raises
        ------
        RuntimeError
            If it is not possible to generate the content.

        Examples
        --------
        Render an image and display it in a browser. Rotate the scene and update the display.

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
        if self._jupyter_notebook:  # pragma: no cover
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
        # Undocumented. Available only internally
        elif what == "webensight":
            render = RenderableVNCAngular(self, **kwargs)

        if render is None:
            raise RuntimeError("Unable to generate requested visualization")

        return render

    def cmd(self, value: str, do_eval: bool = True) -> Any:
        """Run a command in EnSight and return the results.

        Parameters
        ----------
        value : str
            String of the command to run
        do_eval : bool, optional
            Whether to perform an evaluation. The default is ``True``.


        Returns
        -------
        result
            Result of the string being executed as Python inside EnSight.

        Examples
        --------

        >>> print(session.cmd("10+4"))
            14
        """
        self._establish_connection()
        ret = self._grpc.command(value, do_eval=do_eval)
        if do_eval:
            ret = self._convert_ctor(ret)
            value = eval(ret, dict(session=self, ensobjlist=ensobjlist))
            return value
        return ret

    def geometry(self, what: str = "glb") -> bytes:
        """Return the current EnSight scene as a geometry file.

        Parameters
        ----------
        what : str, optional
            File format to return. The default is ``"glb"``.

        Returns
        -------
        obj
            Generated geometry file as a bytes object.

        Examples
        --------
        >>> data = session.geometry()
        >>> with open("file.glb", "wb") as fp:
        >>> fp.write(data)

        """
        self._establish_connection()
        return self._grpc.geometry()

    def render(self, width: int, height: int, aa: int = 1) -> bytes:
        """Render the current EnSight scene and return a PNG image.

        Parameters
        ----------
        width : int
            Width of the rendered image in pixels.
        height : int
            Height of the rendered image in pixels.
        aa : int, optional
            Number of antialiasing passes to use. The default is ``1``.

        Returns
        -------
        obj
            PNG image as a bytes object.

        Examples
        --------
        >>> data = session.render(1920, 1080, aa=4)
        >>> with open("file.png", "wb") as fp:
        >>> fp.write(data)

        """
        self._establish_connection()
        return self._grpc.render(width=width, height=height, aa=aa)

    def _release_remote_objects(self, object_id: Optional[int] = None):
        """
        Send a command to the remote EnSight session to drop a specific object
        or all objects from the remote object cache.

        Parameters
        ----------
        object_id: int, optional
            The specific object to drop from the cache.  If no objects are specified,
            then all remote objects associated with this session will be dropped.

        """
        obj_str = ""
        if object_id:
            obj_str = f", id={object_id}"
        cmd = f"ensight.objs.release_id('{self.name}'{obj_str})"
        _ = self.cmd(cmd, do_eval=False)

    def close(self) -> None:
        """Close the session.

        Close the current session and its gRPC connection.
        """
        # if version 242 or higher, free any objects we have cached there
        if self.cei_suffix >= "242":
            try:
                self._release_remote_objects()
            except RuntimeError:  # pragma: no cover
                # handle some intermediate EnSight builds.
                pass
        if self._launcher and self._halt_ensight_on_close:
            self._launcher.close(self)
        else:
            # lightweight shtudown, just close the gRC connection
            self._grpc.shutdown(stop_ensight=False)
        self._launcher = None

    def _build_utils_interface(self) -> None:
        """Build the ``ensight.utils`` interface.

        This method Walk the PY files in the ``utils`` directory, creating instances
        of the classes in those files and placing them in the
        ``Session.ensight.utils`` namespace.
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
                    f"ansys.pyensight.core.utils.{_name}", _filename
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
            except Exception as e:  # pragma: no cover
                # Warn on import errors
                print(f"Error loading ensight.utils from: '{_filename}' : {e}")

    MONITOR_NEW_TIMESTEPS_OFF = "off"
    MONITOR_NEW_TIMESTEPS_STAY_AT_CURRENT = "stay_at_current"
    MONITOR_NEW_TIMESTEPS_JUMP_TO_END = "jump_to_end"

    def load_data(
        self,
        data_file: str,
        result_file: Optional[str] = None,
        file_format: Optional[str] = None,
        reader_options: Optional[dict] = None,
        new_case: bool = False,
        representation: str = "3D_feature_2D_full",
        monitor_new_timesteps: str = MONITOR_NEW_TIMESTEPS_OFF,
    ) -> None:
        """Load a dataset into the EnSight instance.

        Load the data from a given file into EnSight. The new data
        replaces any currently loaded data in the session.

        Parameters
        ----------
        data_file : str
            Name of the data file to load.
        result_file : str, optional
            Name of the second data file for dual-file datasets.
        file_format : str, optional
            Name of the EnSight reader to use. The default is ``None``,
            in which case EnSight selects a reader.
        reader_options : dict, optional
            Dictionary of reader-specific option-value pairs that can be used
            to customize the reader behavior. The default is ``None``.
        new_case : bool, optional
            Whether to load the dataset in another case. The default is ``False``,
            in which case the dataset replaces the one (if any) loaded in the existing
            current case.
        representation : str, optional
            Default representation for the parts loaded. The default is
            ``"3D_feature_2D_full"``.
        monitor_new_timesteps: str, optional
            Defaulted to off, if changed EnSight will monitor for new timesteps.
            The allowed values are MONITOR_NEW_TIMESTEPS_OFF, MONITOR_NEW_TIMESTEPS_STAY_AT_CURRENT
            and MONITOR_NEW_TIMESTEPS_JUMP_TO_END

        Raises
        ------
        RuntimeError
            If EnSight cannot guess the file format or an error occurs while the
            data is being read.

        Examples
        --------
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
        cmds.append(f'ensight.solution_time.monitor_for_new_steps("{monitor_new_timesteps}")')
        cmds.append(f'ensight.data.replace(r"""{data_file}""")')
        for cmd in cmds:
            if self.cmd(cmd) != 0:
                raise RuntimeError("Unable to load the dataset.")

    def download_pyansys_example(
        self,
        filename: str,
        directory: Optional[str] = None,
        root: Optional[str] = None,
        folder: Optional[bool] = None,
    ) -> str:
        """Download an example dataset from the ansys/example-data repository.
        The dataset is downloaded local to the EnSight server location, so that it can
        be downloaded even if running from a container.

        Parameters
        ----------
        filename: str
            The filename to download
        directory: str
            The directory to download the filename from
        root: str
            If set, the download will happen from another location
        folder: bool
            If set to True, it marks the filename to be a directory rather
            than a single file

        Returns
        -------
        pathname: str
            The download location, local to the EnSight server directory.
            If folder is set to True, the download location will be a folder containing
            all the items available in the repository location under that folder.

        Examples
        --------
        >>> from ansys.pyensight.core import DockerLauncher
        >>> session = DockerLauncher().start(data_directory="D:\\")
        >>> cas_file = session.download_pyansys_example("mixing_elbow.cas.h5","pyfluent/mixing_elbow")
        >>> dat_file = session.download_pyansys_example("mixing_elbow.dat.h5","pyfluent/mixing_elbow")
        >>> session.load_data(cas_file, result_file=dat_file)
        >>> remote = session.show("remote")
        >>> remote.browser()
        """
        base_uri = "https://github.com/ansys/example-data/raw/master"
        base_api_uri = "https://api.github.com/repos/ansys/example-data/contents"
        if not folder:
            if root is not None:
                base_uri = root
        else:
            base_uri = base_api_uri
        uri = f"{base_uri}/{filename}"
        if directory:
            uri = f"{base_uri}/{directory}/{filename}"
        pathname = f"{self.launcher.session_directory}/{filename}"
        if not folder:
            script = "import requests\n"
            script += "import shutil\n"
            script += "import os\n"
            script += f'url = "{uri}"\n'
            script += f'outpath = r"""{pathname}"""\n'
            script += "with requests.get(url, stream=True) as r:\n"
            script += "    with open(outpath, 'wb') as f:\n"
            script += "        shutil.copyfileobj(r.raw, f)\n"
            self.cmd(script, do_eval=False)
        else:
            script = "import requests\n"
            script += "import shutil\n"
            script += "import os\n"
            script += f'url = "{uri}"\n'
            script += "with requests.get(url) as r:\n"
            script += "    data = r.json()\n"
            script += f'    output_directory = r"""{pathname}"""\n'
            script += "    os.makedirs(output_directory, exist_ok=True)\n"
            script += "    for item in data:\n"
            script += "        if item['type'] == 'file':\n"
            script += "            file_url = item['download_url']\n"
            script += "            filename = os.path.join(output_directory, item['name'])\n"
            script += "            r = requests.get(file_url, stream=True)\n"
            script += "            with open(filename, 'wb') as f:\n"
            script += "                f.write(r.content)\n"
            self.cmd(script, do_eval=False)
        return pathname

    def load_example(
        self, example_name: str, uncompress: bool = False, root: Optional[str] = None
    ) -> str:
        """Load an example dataset.

        This method downloads an EnSight session file from a known location and loads
        it into the current EnSight instance. The URL for the dataset is formed by
        combining the value given for the ``example_name`` parameter with a root URL.
        The default base URL is provided by Ansys, but it can be overridden by specifying
        a value for the ``root`` parameter.

        Parameters
        ----------
        example_name : str
            Name of the EnSight session file (``.ens``) to download and load.
        uncompress : bool, optional
            Whether to unzip the downloaded file into the returned directory name.
            The default is ``False``.
        root : str, optional
            Base URL for the download.

        Returns
        -------
        str
            Path to the downloaded file in the EnSight session.

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
        pathname = self.download_pyansys_example(example_name, root=base_uri)
        script = f'outpath = r"""{pathname}"""\n'
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
        """Register a callback with an event tuple.

        For a given target object (such as ``"ensight.objs.core"``) and a list
        of attributes (such as ``["PARTS", "VARIABLES"]``), this method sets up a
        callback to be made when any of those attribute change on the target object.
        The target can also be an EnSight (not PyEnSight) class name, for example
        "ENS_PART".  In this latter form, all objects of that type are watched for
        specified attribute changes.

        The callback is made with a single argument, a string encoded in URL format
        with the supplied tag, the name of the attribute that changed and the UID
        of the object that changed.  The string passed to the callback is in this form:
        ``grpc://{sessionguid}/{tag}?enum={attribute}&uid={objectid}``.

        Only one callback with the noted tag can be used in the session.

        Parameters
        ----------
        target : obj, str
            Name of the target object or name of a class as a string to
            match all objects of that class. A proxy class reference is
            also allowed. For example, ``session.ensight.objs.core``.
        tag : str
            Unique name for the callback. A tag can end with macros of
            the form ``{{attrname}}`` to return the value of an attribute of the
            target object. The macros should take the form of URI queries to
            simplify parsing.
        attr_list : list
            List of attributes of the target that are to result in the callback
            being called if changed.
        method : Callable
            Callable that is called with the returned URL.
        compress : bool, optional
            Whether to call only the last event if a repeated event is generated
            as a result of an action. The default is ``True``. If ``False``, every
            event results in a callback.

        Examples
        --------
        A string similar to this is printed when the dataset is loaded and the part list
        changes:

        ``    Event : grpc://f6f74dae-f0ed-11ec-aa58-381428170733/partlist?enum=PARTS&uid=221``

        >>> from ansys.pyensight.core import LocalLauncher
        >>> s = LocalLauncher().start()
        >>> def cb(v: str):
        >>>     print("Event:", v)
        >>> s.add_callback("ensight.objs.core", "partlist", ["PARTS"], cb)
        >>> s.load_data(r"D:\ANSYSDev\data\CFX\HeatingCoil_001.res")
        """
        self._establish_connection()
        # shorten the tag up to the query block. Macros are only legal in the query block.
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
        """Remove a callback that the :func`add_callback<ansys.pyensight.core.Session.add_callback>`
        method started.

        Given a tag used to register a previous callback (``add_callback()``), remove
        this callback from the EnSight callback system.

        Parameters
        ----------
        tag : str
            Callback string tag.

        Raises
        ------
        RuntimeError
            If an invalid tag is supplied.

        """
        if tag not in self._callbacks:
            raise RuntimeError(f"A callback for tag '{tag}' does not exist")
        callback_id = self._callbacks[tag][0]
        del self._callbacks[tag]
        cmd = f"ensight.objs.removecallback({callback_id})"
        _ = self.cmd(cmd, do_eval=False)

    def _event_callback(self, cmd: str) -> None:
        """Pass the URL back to the registered callback.

        This method matches the ``cmd`` URL with the registered callback and then
        makes the callback.

        Parameters
        ----------
        cmd : str
            URL callback from the gRPC event stream. The URL has this
            form: ``grpc://{sessionguid}/{tag}?enum={attribute}&uid={objectid}``.

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
        """Generate a string that, for a given ``ENSOBJ`` object ID, returns
        a proxy object instance.

        Parameters
        ----------
        ensobjid: int
            ID of the ``ENSOBJ`` object.

        Returns
        -------
        str
            String for the proxy object instance.
        """
        return f"ensight.objs.wrap_id({ensobjid})"

    def _prune_hash(self) -> None:
        """Prune the ``ENSOBJ`` hash table.

        The ``ENSOBJ`` hash table may need flushing if it gets too big. Do that here."""
        if len(self._ensobj_hash) > 1000000:
            self._ensobj_hash = {}

    def add_ensobj_instance(self, obj: "ENSOBJ") -> None:
        """Add a new ``ENSOBJ`` object instance to the hash table.

        Parameters
        ----------
        obj : ENSOBJ
           ``ENSOBJ`` object instance.
        """
        self._ensobj_hash[obj.__OBJID__] = obj

    def obj_instance(self, ensobjid: int) -> Optional["ENSOBJ"]:
        """Get any existing proxy object associated with an ID.

        Parameters
        ----------
        ensobjid: int
            ID of the ``ENSOBJ`` object.

        """
        return self._ensobj_hash.get(ensobjid, None)

    def _obj_attr_subtype(self, classname: str) -> Tuple[Optional[int], Optional[dict]]:
        """Get subtype information for a given class.

        For an input class name, this method returns the proper Python proxy class name and,
        if the class supports subclasses, the attribute ID of the differentiating attribute.

        Parameters
        ----------
        classname : str
            Root class name to look up.

        Returns
        -------
        Tuple[Optional[int], Optional[dict]]
            (attr_id, subclassnamedict): Attribute used to differentiate between classes
            and a dictionary of the class names for each value of the attribute.

        """
        if classname == "ENS_PART":
            return self.ensight.objs.enums.PARTTYPE, self._subtype_tables[classname]

        elif classname == "ENS_ANNOT":
            return self.ensight.objs.enums.ANNOTTYPE, self._subtype_tables[classname]

        elif classname == "ENS_TOOL":
            return self.ensight.objs.enums.TOOLTYPE, self._subtype_tables[classname]

        return None, None

    def _convert_ctor(self, s: str) -> str:
        """Convert ENSOBJ object references into executable code in __repl__ strings.

        The __repl__() implementation for an ENSOBJ subclass generates strings like these::

            Class: ENS_GLOBALS, CvfObjID: 221, cached:yes
            Class: ENS_PART, desc: 'Sphere', CvfObjID: 1078, cached:no
            Class: ENS_PART, desc: 'engine', PartType: 0, CvfObjID: 1097, cached:no
            Class: ENS_GROUP, desc: '', Owned, CvfObjID: 1043, cached:no

        This method detects strings like those and converts them into strings like these::

            session.ensight.objs.ENS_GLOBALS(session, 221)
            session.ensight.objs.ENS_PART_MODEL(session, 1078, attr_id=1610612792, attr_value=0)

        where:

        1610612792 is ensight.objs.enums.PARTTYPE.

        If a proxy object for the ID already exists, it can also generate strings like this::

            session.obj_instance(221)


        Parameters
        ----------
        s : str
            String to convert.

        """
        self._prune_hash()
        offset = 0
        while True:
            # Find the object repl block to replace
            id = s.find("CvfObjID:", offset)
            if id == -1:
                break
            start = s.find("Class: ", offset)
            if (start == -1) or (start > id):
                break
            tail_len = 11
            tail = s.find(", cached:no", offset)
            if tail == -1:
                tail_len = 12
                tail = s.find(", cached:yes", offset)
            if tail == -1:
                break
            # just this object substring
            tmp = s[start + 7 : tail]
            # Subtype (PartType:, AnnotType:, ToolType:)
            subtype = None
            for name in ("PartType:", "AnnotType:", "ToolType:"):
                location = tmp.find(name)
                if location != -1:
                    subtype = int(tmp[location + len(name) :].split(",")[0])
                    break
            # Owned flag
            owned_flag = "Owned," in tmp
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
                    if subtype is not None:
                        # the 2024 R2 interface includes the subtype
                        if (classname_lookup is not None) and (subtype in classname_lookup):
                            classname = classname_lookup[subtype]
                            subclass_info = f",attr_id={attr_id}, attr_value={subtype}"
                    elif classname_lookup is not None:
                        # if a "subclass" case and no subclass attrid value, ask for it...
                        remote_name = self.remote_obj(objid)
                        cmd = f"{remote_name}.getattr({attr_id})"
                        attr_value = self.cmd(cmd)
                        if attr_value in classname_lookup:
                            classname = classname_lookup[attr_value]
                            subclass_info = f",attr_id={attr_id}, attr_value={attr_value}"
                if owned_flag:
                    subclass_info += ",owned=True"
                replace_text = f"session.ensight.objs.{classname}(session, {objid}{subclass_info})"
            if replace_text is None:
                break
            offset = start + len(replace_text)
            s = prefix + replace_text + suffix
        s = s.strip()
        if s.startswith("[") and s.endswith("]"):
            s = f"ensobjlist({s}, session=session)"
        return s

    def capture_context(self, full_context: bool = False) -> "enscontext.EnsContext":
        """Capture the current EnSight instance state.

        This method causes the EnSight instance to save a context and return an ``EnsContext``
        object representing that saved state.

        Parameters
        ----------
        full_context : bool, optional
            Whether to include all aspects of the Ensight instance. The default is ``False``.

        Returns
        -------
        enscontext.EnsContext

        Examples
        --------
        >>> ctx = session.capture_context()
        >>> ctx.save("session_context.ctxz")

        """
        self.cmd("import ansys.pyensight.core.enscontext", do_eval=False)
        data_str = self.cmd(
            f"ansys.pyensight.core.enscontext._capture_context(ensight,{full_context})",
            do_eval=True,
        )
        context = EnsContext()
        context._from_data(data_str)
        return context

    def restore_context(self, context: "enscontext.EnsContext") -> None:
        """Restore the current EnSight instance state.

        This method restores EnSight to the state stored in an ``EnsContext``
        object that was either read from disk or returned by the
        :func:`capture_context<ansys.pyensight.core.Session.capture_context>` method.

        Parameters
        ----------
        context : enscontext.EnsContext
            Context to set the current EnSight instance to.

        Examples
        --------
        >>> tmp_ctx = session.capture_context()
        >>> session.restore_context(EnsContext("session_context.ctxz"))
        >>> session.restore_context(tmp_ctx)
        """
        data_str = context._data(b64=True)
        self.cmd("import ansys.pyensight.core.enscontext", do_eval=False)
        self.cmd(
            f"ansys.pyensight.core.enscontext._restore_context(ensight,'{data_str}')", do_eval=False
        )

    def ensight_version_check(
        self,
        version: Union[int, str],
        message: str = "",
        exception: bool = True,
        strict: bool = False,
    ) -> bool:
        """Check if the session is a specific version.

        Different versions of pyensight Sessions may host different versions of EnSight.
        This method compares the version of the remote EnSight session to a specific version
        number.  If the remote EnSight version is at least the specified version, then
        this method returns True.  If the version of EnSight is earlier than the specified
        version, this method  will raise an exception.  The caller can specify the
        error string to be included.  They may also specify if the version check should
        be for a specific version vs the specified version or higher.  It is also possible
        to avoid the exception and instead just return True or False for cases when an
        alternative implementation might be used.

        Parameters
        ----------
        version : Union[int, str]
            The version number to compare the EnSight version against.
        message : str
            The message string to be used as the text for any raised exception.
        exception : bool
            If True, and the version comparison fails, an InvalidEnSightVersion is raised.
            Otherwise, the result of the comparison is returned.
        strict : bool
            If True, the comparison of the two versions will only pass if they
            are identical.  If False, if the EnSight version is greater than or
            equal to the specified version the comparison will pass.

        Returns
        -------
            True if the comparison succeeds, False otherwise.

        Raises
        ------
            InvalidEnSightVersion if the comparison fails and exception is True.
        """
        ens_version = int(self.ensight.version("suffix"))
        # handle various input formats
        target = version
        if isinstance(target, str):
            # could be 'year RX' or the suffix as a string
            if "R" in target:
                tmp = [int(x) for x in target.split("R")]
                target = (tmp[0] - 2000) * 10 + tmp[1]
            else:
                target = int(target)
        # check validity
        valid = ens_version == target
        at_least = ""
        if not strict:
            at_least = "at least "
            valid = ens_version >= target
        if (not valid) and exception:
            ens_version = self.ensight.version("version-full")
            base_msg = f" ({at_least}'{version}' required, '{ens_version}' current)"
            if message:
                message += base_msg
            else:
                message = f"A newer version of EnSight is required to use this API:{base_msg}"
            raise InvalidEnSightVersion(message)
        return valid
