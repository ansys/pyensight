import glob
import json
import os
import platform
import subprocess
import sys
import tempfile
import threading
from types import ModuleType
from typing import TYPE_CHECKING, List, Optional, Union
import uuid

import psutil

if TYPE_CHECKING:
    try:
        import ensight
    except ImportError:
        from ansys.api.pyensight import ensight_api


def _handle_fluids_one(install_path):
    cei_path = install_path
    interpreter = os.path.join(cei_path, "bin", "cpython")
    if platform.system() == "Windows":
        interpreter += ".bat"
    return interpreter


class OmniverseKitInstance:
    """Interface to an Omniverse application instance

    Parameters
    ----------
    pid : int
        The process id of the launched instance
    """

    def __init__(self, proc: subprocess.Popen) -> None:
        self._proc: subprocess.Popen = proc
        self._returncode: Optional[int] = None
        self._rendering = False
        self._lines_read = 0
        self._scanner_thread = threading.Thread(
            target=OmniverseKitInstance._scan_stdout, args=(self,)
        )
        self._scanner_thread.start()

    def __del__(self) -> None:
        """Close down the instance on delete"""
        self.close()

    def close(self) -> None:
        """Shutdown the Omniverse instance

        If the instance associated with this object is still running,
        shut it down.
        """
        if not self.is_running():
            return
        proc = psutil.Process(self._proc.pid)
        for child in proc.children(recursive=True):
            if psutil.pid_exists(child.pid):
                # This can be a race condition, so it is ok if the child is dead already
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
        # Same issue, this process might already be shutting down, so NoSuchProcess is ok.
        try:
            proc.terminate()
        except psutil.NoSuchProcess:
            pass
        self._scanner_thread.join()

        # On a forced close, set a return code of 0
        self._returncode = 0

    @staticmethod
    def _scan_stdout(oki: "OmniverseKitInstance"):
        while oki._proc and oki._proc.poll() is None:
            if oki._proc.stdout is not None:
                output_line = oki._proc.stdout.readline().decode("utf-8")
                oki._lines_read = oki._lines_read + 1
                if "RTX ready" in output_line:
                    oki._rendering = True

    def is_rendering(self) -> bool:
        """Check if the instance has finished launching and is ready to render

        Returns
        -------
        bool
            True if the instance is ready to render.
        """
        return self.is_running() and self._rendering

    def is_running(self) -> bool:
        """Check if the instance is still running

        Returns
        -------
        bool
            True if the instance is still running.
        """
        if self._proc is None:
            return False
        if self._proc.poll() is None:
            return True
        return False

    def returncode(self) -> Optional[int]:
        """Get the return code if the process has stopped, or None if still running

        Returns
        -------
        int or None
            Get the return code if the process has stopped, or None if still running
        """
        if self._returncode is not None:
            return self._returncode
        if self.is_running():
            return None
        self._returncode = self._proc.returncode
        return self._returncode


# Deprecated
def find_kit_filename(fallback_directory: Optional[str] = None) -> Optional[str]:
    """
    Use a combination of the current omniverse application and the information
    in the local .nvidia-omniverse/config/omniverse.toml file to come up with
    the pathname of a kit executable suitable for hosting another copy of the
    ansys.geometry.server kit.

    Returns
    -------
    Optional[str]
        The pathname of a kit executable or None

    """
    # parse the toml config file for the location of the installed apps
    try:
        import tomllib
    except ModuleNotFoundError:
        import pip._vendor.tomli as tomllib

    homedir = os.path.expanduser("~")
    ov_config = os.path.join(homedir, ".nvidia-omniverse", "config", "omniverse.toml")
    if not os.path.exists(ov_config):
        return None
    # read the Omniverse configuration toml file
    with open(ov_config, "r") as ov_file:
        ov_data = ov_file.read()
    config = tomllib.loads(ov_data)
    appdir = config.get("paths", {}).get("library_root", fallback_directory)

    # If we are running inside an Omniverse app, use that information
    try:
        import omni.kit.app

        # get the current application
        app = omni.kit.app.get_app()
        app_name = app.get_app_filename().split(".")[-1]
        app_version = app.get_app_version().split("-")[0]
        # and where it is installed
        appdir = os.path.join(appdir, f"{app_name}-{app_version}")
    except ModuleNotFoundError:
        # Names should be like: "C:\\Users\\foo\\AppData\\Local\\ov\\pkg\\create-2023.2.3\\launcher.toml"
        target = None
        target_version = None
        for d in glob.glob(os.path.join(appdir, "*", "launcher.toml")):
            test_dir = os.path.dirname(d)
            # the name will be something like "create-2023.2.3"
            name = os.path.basename(test_dir).split("-")
            if len(name) != 2:
                continue
            if name[0] not in ("kit", "create", "view"):
                continue
            if (target_version is None) or (name[1] > target_version):
                target = test_dir
                target_version = name[1]
        if target is None:
            return None
        appdir = target

    # Windows: 'kit.bat' in '.' or 'kit' followed by 'kit.exe' in '.' or 'kit'
    # Linux: 'kit.sh' in '.' or 'kit' followed by 'kit' in '.' or 'kit'
    exe_names = ["kit.sh", "kit"]
    if sys.platform.startswith("win"):
        exe_names = ["kit.bat", "kit.exe"]

    # look in 4 places...
    for dir_name in [appdir, os.path.join(appdir, "kit")]:
        for exe_name in exe_names:
            if os.path.exists(os.path.join(dir_name, exe_name)):
                return os.path.join(dir_name, exe_name)

    return None


# Deprecated
def launch_kit_instance(
    kit_path: Optional[str] = None,
    extension_paths: Optional[List[str]] = None,
    extensions: Optional[List[str]] = None,
    cli_options: Optional[List[str]] = None,
    log_file: Optional[str] = None,
    log_level: str = "warn",
) -> "OmniverseKitInstance":
    """Launch an Omniverse application instance

    Parameters
    ----------
    kit_path : Optional[str]
        The full pathname of to a binary capable of serving as a kit runner.
    extension_paths : Optional[List[str]]
        List of directory names to include the in search for kits.
    extensions : Optional[List[str]]
        List of kit extensions to be loaded into the launched kit instance.
    log_file : Optional[str]
        The name of a text file where the logging information for the instance will be saved.
    log_level : str
        The level of the logging information to record: "verbose", "info", "warn", "error", "fatal",
        the default is "warn".

    Returns
    -------
    OmniverseKitInstance
        The object interface for the launched instance

    Examples
    --------
    Run a simple, empty GUI kit instance.

    >>> from ansys.pyensight.core.utils import omniverse
    >>> ov = omniverse.launch_kit_instance(extensions=['omni.kit.uiapp'])

    """
    # build the command line
    if not kit_path:
        kit_path = find_kit_filename()
    if not kit_path:
        raise RuntimeError("Unable to find a suitable Omniverse kit install")
    cmd = [kit_path]
    if extension_paths:
        for path in extension_paths:
            cmd.extend(["--ext-folder", path])
    if extensions:
        for ext in extensions:
            cmd.extend(["--enable", ext])
    if cli_options:
        for opt in cli_options:
            cmd.append(opt)
    if log_level not in ("verbose", "info", "warn", "error", "fatal"):
        raise RuntimeError(f"Invalid logging level: {log_level}")
    cmd.append(f"--/log/level={log_level}")
    if log_file:
        cmd.append(f"--/log/file={log_file}")
        cmd.append("--/log/enabled=true")
    # Launch the process
    env_vars = os.environ.copy()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env_vars)
    return OmniverseKitInstance(p)


def find_app(ansys_installation: Optional[str] = None) -> Optional[str]:
    dirs_to_check = []
    if ansys_installation:
        # Given a different Ansys install
        local_tp = os.path.join(os.path.join(ansys_installation, "tp", "omni_viewer"))
        if os.path.exists(local_tp):
            dirs_to_check.append(local_tp)
        # Dev Folder
        local_dev_omni = os.path.join(ansys_installation, "omni_build")
        if os.path.exists(local_dev_omni):
            dirs_to_check.append(local_dev_omni)
    if "PYENSIGHT_ANSYS_INSTALLATION" in os.environ:
        env_inst = os.environ["PYENSIGHT_ANSYS_INSTALLATION"]
        dirs_to_check.append(os.path.join(env_inst, "tp", "omni_viewer"))

    # Look for most recent Ansys install, 25.2 or later
    awp_roots = []
    for env_name in dict(os.environ).keys():
        if env_name.startswith("AWP_ROOT") and int(env_name[len("AWP_ROOT") :]) >= 252:
            awp_roots.append(env_name)
    awp_roots.sort(reverse=True)
    for env_name in awp_roots:
        dirs_to_check.append(os.path.join(os.environ[env_name], "tp", "omni_viewer"))

    # check all the collected locations in order
    for install_dir in dirs_to_check:
        launch_file = os.path.join(install_dir, "ansys_tools_omni_core.py")
        if os.path.isfile(launch_file):
            return launch_file
    return None


def launch_app(
    usd_file: Optional[str] = "",
    layout: Optional[str] = "default",
    streaming: Optional[bool] = False,
    offscreen: Optional[bool] = False,
    log_file: Optional[str] = None,
    log_level: Optional[str] = "warn",
    cli_options: Optional[List[str]] = None,
    ansys_installation: Optional[str] = None,
    interpreter: Optional[str] = None,
) -> "OmniverseKitInstance":
    """Launch the Ansys Omniverse application

    Parameters
    ----------
    # usd_file : Optional[str]
    #    A .usd file to open on startup
    # layout : Optional[str]
    #    A UI layout.  viewer, composer, or composer_slim
    # streaming : Optional[bool]
    #    Enable webrtc streaming to enable the window in a web page
    # offscreen : Optional[str]
    #    Run the app offscreen.  Useful when streaming.
    # log_file : Optional[str]
    #    The name of a text file where the logging information for the instance will be saved.
    # log_level : Optional[str]
    #    The level of the logging information to record: "verbose", "info", "warn", "error", "fatal",
    #    the default is "warn".
    # cli_options : Optional[List[str]]
    #    Other command line options

    Returns
    -------
    OmniverseKitInstance
        The object interface for the launched instance

    Examples
    --------
    Run the app with default options

    >>> from ansys.pyensight.core.utils import omniverse
    >>> ov = omniverse.launch_app()

    """
    cmd = [sys.executable]
    if interpreter:
        cmd = [interpreter]
    app = find_app(ansys_installation=ansys_installation)
    if not app:
        raise RuntimeError("Unable to find the Ansys Omniverse app")
    cmd.extend([app])
    if usd_file:
        cmd.extend(["-f", usd_file])
    if layout:
        cmd.extend(["-l", layout])
    if streaming:
        cmd.extend(["-s"])
    if offscreen:
        cmd.extend(["-o"])
    if cli_options:
        cmd.extend(cli_options)
    if log_level:
        if log_level not in ("verbose", "info", "warn", "error", "fatal"):
            raise RuntimeError(f"Invalid logging level: {log_level}")
        cmd.extend([f"--/log/level={log_level}"])
    if log_file:
        cmd.extend(["--/log/enabled=true", f"--/log/file={log_file}"])

    # Launch the process
    env_vars = os.environ.copy()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env_vars)
    return OmniverseKitInstance(p)


class Omniverse:
    """Provides the ``ensight.utils.omniverse`` interface.

    The omniverse class methods provide an interface between an EnSight session
    and an Omniverse instance.  See :ref:`omniverse_info` for additional details.

    Parameters
    ----------
    interface: Union["ensight_api.ensight", "ensight"]
        Entity that provides the ``ensight`` namespace. In the case of
        EnSight Python, the ``ensight`` module is passed. In the case
        of PyEnSight, ``Session.ensight`` is passed.

    Notes
    -----
    This interface is only available when using pyensight (they do not work with
    the ensight Python interpreter) and the module must be used in an interpreter
    that includes the Omniverse Python modules (e.g. omni and pxr).  Only a single
    Omniverse connection can be established within a single pyensight session.

    Examples
    --------

    >>> from ansys.pyensight.core import LocalLauncher
    >>> session = LocalLauncher().start()
    >>> ov = session.ensight.utils.omniverse
    >>> ov.create_connection("D:\\Omniverse\\Example")
    >>> ov.update()
    >>> ov.close_connection()

    """

    def __init__(self, interface: Union["ensight_api.ensight", "ensight"]):
        self._ensight = interface
        self._server_pid: Optional[int] = None
        self._interpreter: str = ""
        self._status_filename: str = ""

    def _check_modules(self) -> None:
        """Verify that the Python interpreter is correct

        Check for module dependencies. If not present, raise an exception.

        Raises
        ------
        RuntimeError
            if the necessary modules are missing.

        """
        # One time check for this
        if len(self._interpreter):
            return

        # if a module, then we are inside EnSight
        if isinstance(self._ensight, ModuleType):  # pragma: no cover
            # in this case, we can just use cpython
            import ceiversion
            import enve

            cei_home = os.environ.get("CEI_HOME", enve.home())
            self._interpreter = os.path.join(cei_home, "bin", f"cpython{ceiversion.apex_suffix}")
            if platform.system() == "Windows":
                self._interpreter += ".bat"
            return
        # Check if the python interpreter is kit itself
        is_omni = False
        try:
            import omni  # noqa: F401

            is_omni = "kit" in os.path.basename(sys.executable)
        except ModuleNotFoundError:
            pass
        # Using the python interpreter running this code
        self._interpreter = sys.executable
        if "fluids_one" in self._interpreter:  # compiled simba-app
            self._interpreter = _handle_fluids_one(self._ensight._session._install_path)
        if is_omni:
            kit_path = os.path.dirname(sys.executable)
            self._interpreter = os.path.join(kit_path, "python")
            if platform.system() == "Windows":
                self._interpreter += ".bat"
            else:
                self._interpreter += ".sh"

        # in the future, these will be part of the pyensight wheel
        # dependencies, but for now we include this check.
        try:
            import pxr  # noqa: F401
            import pygltflib  # noqa: F401
        except Exception:
            raise RuntimeError("Unable to detect omniverse dependencies: usd-core, pygltflib.")

    def is_running_omniverse(self) -> bool:
        """Check that an Omniverse connection is active

        Returns
        -------
        bool
            True if the connection is active, False otherwise.
        """
        if self._server_pid is None:
            return False
        if psutil.pid_exists(self._server_pid):
            return True
        self._server_pid = None
        return False

    def create_connection(
        self,
        omniverse_path: str,
        include_camera: bool = False,
        normalize_geometry: bool = False,
        temporal: bool = False,
        live: bool = True,
        debug_filename: str = "",
        time_scale: float = 1.0,
        line_width: float = 0.0,
        options: dict = {},
    ) -> None:
        """Ensure that an EnSight dsg -> omniverse server is running

        Connect the current EnSight session to an Omniverse server.
        This is done by launching a new service that makes a dynamic scene graph
        connection to the EnSight session and pushes updates to the Omniverse server.
        The initial EnSight scene will be pushed after the connection is established.

        Parameters
        ----------
        omniverse_path : str
            The directory name where the USD files should be saved. For example:
            "C:/Users/test/OV/usdfiles"
        include_camera : bool
            If True, apply the EnSight camera to the Omniverse scene.  This option
            should be used if the target viewer is in AR/VR mode.  Defaults to False.
        normalize_geometry : bool
            Omniverse units are in meters.  If the source dataset is not in the correct
            unit system or is just too large/small, this option will remap the geometry
            to a unit cube.  Defaults to False.
        temporal : bool
            If True, save all timesteps.
        live : bool
            If True, one can call 'update()' to send updated geometry to Omniverse.
            If False, the Omniverse connection will push a single update and then
            disconnect.  Defaults to True.
        time_scale : float
            Multiply all EnSight time values by this factor before exporting to Omniverse.
            The default is 1.0.
        debug_filename : str
            If the name of a file is provided, it will be used to save logging information on
            the connection between EnSight and Omniverse.  This option is no longer supported,
            but the API remains for backwards compatibility.
        line_width : float
            If set, line objects will be represented as "tubes" of the size specified by
            this factor.  The default is 0.0 and causes lines not to be exported.
        options : dict
            Allows for a fallback for the grpc host/port and the security token.
        """
        if not isinstance(self._ensight, ModuleType):
            self._ensight._session.ensight_version_check("2023 R2")
        self._check_modules()
        if self.is_running_omniverse():
            raise RuntimeError("An Omniverse server connection is already active.")
        if not isinstance(self._ensight, ModuleType):
            # Make sure the internal ui module is loaded
            self._ensight._session.cmd("import enspyqtgui_int", do_eval=False)
            # Get the gRPC connection details and use them to launch the service
            port = self._ensight._session.grpc.port()
            hostname = self._ensight._session.grpc.host
            token = self._ensight._session.grpc.security_token
        else:
            hostname = options.get("host", "127.0.0.1")
            port = options.get("port", 12345)
            token = options.get("security", "")

        # Launch the server via the 'ansys.pyensight.core.utils.omniverse_cli' module
        dsg_uri = f"grpc://{hostname}:{port}"
        cmd = [self._interpreter]
        cmd.extend(["-m", "ansys.pyensight.core.utils.omniverse_cli"])
        cmd.append(omniverse_path)
        if token:
            cmd.extend(["--security_token", token])
        if temporal:
            cmd.extend(["--temporal", "true"])
        if not include_camera:
            cmd.extend(["--include_camera", "false"])
        if normalize_geometry:
            cmd.extend(["--normalize_geometry", "true"])
        if time_scale != 1.0:
            cmd.extend(["--time_scale", str(time_scale)])
        if line_width != 0.0:
            cmd.extend(["--line_width", str(line_width)])
        if not live:
            cmd.extend(["--oneshot", "1"])
        cmd.extend(["--dsg_uri", dsg_uri])
        env_vars = os.environ.copy()
        # we are launching the kit from EnSight or PyEnSight.  In these cases, we
        # inform the kit instance of:
        # (1) the name of the "server status" file, if any
        self._new_status_file()
        env_vars["ANSYS_OV_SERVER_STATUS_FILENAME"] = self._status_filename
        process = subprocess.Popen(cmd, close_fds=True, env=env_vars)
        self._server_pid = process.pid

    def _new_status_file(self, new=True) -> None:
        """
        Remove any existing status file and create a new one if requested.

        Parameters
        ----------
        new : bool
            If True, create a new status file.
        """
        if self._status_filename:
            try:
                os.remove(self._status_filename)
            except OSError:
                pass
        self._status_filename = ""
        if new:
            self._status_filename = os.path.join(
                tempfile.gettempdir(), str(uuid.uuid1()) + "_gs_status.txt"
            )

    def read_status_file(self) -> dict:
        """Read the status file and return its contents as a dictionary.

        Note: this can fail if the file is being written to when this call is made, so expect
        failures.

        Returns
        -------
        Optional[dict]
            A dictionary with the fields 'status', 'start_time', 'processed_buffers', 'total_buffers' or empty
        """
        if not self._status_filename:
            return {}
        try:
            with open(self._status_filename, "r") as status_file:
                data = json.load(status_file)
        except Exception:
            return {}
        return data

    def close_connection(self) -> None:
        """Shut down the open EnSight dsg -> omniverse server

        Break the connection between the EnSight instance and Omniverse.

        """
        self._check_modules()
        if not self.is_running_omniverse():
            return
        proc = psutil.Process(self._server_pid)
        for child in proc.children(recursive=True):
            if psutil.pid_exists(child.pid):
                # This can be a race condition, so it is ok if the child is dead already
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
        # Same issue, this process might already be shutting down, so NoSuchProcess is ok.
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            pass
        self._server_pid = None
        self._new_status_file(new=False)

    def update(self, temporal: bool = False, line_width: float = 0.0) -> None:
        """Update the geometry in Omniverse

        Export the current EnSight scene to the current Omniverse connection.

        Parameters
        ----------
        temporal : bool
            If True, export all timesteps.
        line_width : float
            If set to a non-zero value, lines will be exported with this thickness.
            This feature is only available in 2025 R2 and later.
        """
        update_cmd = "dynamicscenegraph://localhost/client/update"
        prefix = "?"
        if temporal:
            update_cmd += f"{prefix}timesteps=1"
            prefix = "&"
        if line_width != 0.0:
            add_linewidth = False
            if isinstance(self._ensight, ModuleType):
                add_linewidth = True
            else:
                # only in 2025 R2 and beyond
                if self._ensight._session.ensight_version_check("2025 R2", exception=False):
                    add_linewidth = True
            if add_linewidth:
                update_cmd += f"{prefix}ANSYS_linewidth={line_width}"
                prefix = "&"
        self._check_modules()
        if not self.is_running_omniverse():
            raise RuntimeError("No Omniverse server connection is currently active.")
        if not isinstance(self._ensight, ModuleType):
            self._ensight._session.ensight_version_check("2023 R2")
            cmd = f'enspyqtgui_int.dynamic_scene_graph_command("{update_cmd}")'
            self._ensight._session.cmd(cmd, do_eval=False)
        else:
            import enspyqtgui_int

            enspyqtgui_int.dynamic_scene_graph_command(f"{update_cmd}")
