import glob
import os
import subprocess
import sys
from types import ModuleType
from typing import TYPE_CHECKING, Optional, Union

import psutil

if TYPE_CHECKING:
    try:
        import ensight
    except ImportError:
        from ansys.api.pyensight import ensight_api

import ansys.pyensight.core


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
    >>> ov.create_connection()
    >>> ov.update()
    >>> ov.close_connection()

    """

    def __init__(self, interface: Union["ensight_api.ensight", "ensight"]):
        self._ensight = interface
        self._server_pid: Optional[int] = None
        self._interpreter: str = ""

    @staticmethod
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

    def _check_modules(self) -> None:
        """Verify that the Python interpreter is correct

        Check for omni module. If not present, raise an exception.
        If pxr is there as well, then we can just use sys.executable.
        If not, check to see if 'kit.bat' or 'kit.sh' can be found and
        arrange to use those instead.

        Raises
        ------
        RuntimeError
            if the necessary modules are missing.

        """
        # One time check for this
        if len(self._interpreter):
            return

        kit_exe = self.find_kit_filename()
        if kit_exe:
            self._interpreter = kit_exe
            return
        raise RuntimeError("Unable to detect a copy of the Omniverse kit executable.") from None

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
            The URI to the Omniverse server. It will look like this:
            "omniverse://localhost/Users/test"
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
        debug_filename : str
            If the name of a file is provided, it will be used to save logging information on
            the connection between EnSight and Omniverse.
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

        # Launch the server via the 'ansys.geometry.service' kit
        dsg_uri = f"grpc://{hostname}:{port}"
        kit_dir = os.path.join(os.path.dirname(ansys.pyensight.core.__file__), "exts")
        cmd = [self._interpreter]
        cmd.extend(["--ext-folder", kit_dir])
        cmd.extend(["--enable", "ansys.geometry.service"])
        if token:
            cmd.append(f"--/exts/ansys.geometry.service/securityCode={token}")
        if temporal:
            cmd.append("--/exts/ansys.geometry.service/temporal=1")
        if not include_camera:
            cmd.append("--/exts/ansys.geometry.service/vrmode=1")
        if normalize_geometry:
            cmd.append("--/exts/ansys.geometry.service/normalizeGeometry=1")
        cmd.append(f"--/exts/ansys.geometry.service/omniUrl={omniverse_path}")
        cmd.append(f"--/exts/ansys.geometry.service/dsgUrl={dsg_uri}")
        cmd.append("--/exts/ansys.geometry.service/run=1")
        env_vars = os.environ.copy()
        working_dir = os.path.join(os.path.dirname(ansys.pyensight.core.__file__), "utils")
        process = subprocess.Popen(cmd, close_fds=True, env=env_vars, cwd=working_dir)
        self._server_pid = process.pid

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

    def update(self, temporal: bool = False) -> None:
        """Update the geometry in Omniverse

        Export the current EnSight scene to the current Omniverse connection.

        Parameters
        ----------
        temporal : bool
            If True, export all timesteps.
        """
        update_cmd = "dynamicscenegraph://localhost/client/update"
        if temporal:
            update_cmd += "?timesteps=1"
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
