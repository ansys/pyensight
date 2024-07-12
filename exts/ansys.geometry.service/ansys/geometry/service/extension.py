import logging
import os
import subprocess
import sys
from typing import Optional
from urllib.parse import urlparse

import carb.settings
import omni.ext
import omni.kit.app
import omni.kit.pipapi
import psutil

try:
    import ansys.pyensight.core
    import ansys.pyensight.core.utils.dsg_server as tmp_dsg_server  # noqa: F401
    import ansys.pyensight.core.utils.omniverse_dsg_server as tmp_ov_dsg_server  # noqa: F401
except ModuleNotFoundError:
    logging.warning("ansys.geometry.server - Installing ansys-pyensight-core")
    omni.kit.pipapi.install("ansys-pyensight-core")


def find_kit_filename() -> Optional[str]:
    """
    Use a combination of the current omniverse application and the information
    in the local .nvidia-omniverse/config/omniverse.toml file to come up with
    the pathname of a kit executable suitable for hosting another copy of the
    ansys.geometry.server kit.

    Returns
    -------
        The pathname of a kit executable or None

    """
    # get the current application
    app = omni.kit.app.get_app()
    app_name = app.get_app_filename().split(".")[-1]
    app_version = app.get_app_version().split("-")[0]

    # parse the toml config file for the location of the installed apps
    try:
        import tomllib
    except ModuleNotFoundError:
        import pip._vendor.tomli as tomllib

    homedir = os.path.expanduser("~")
    ov_config = os.path.join(homedir, ".nvidia-omniverse", "config", "omniverse.toml")
    with open(ov_config, "r") as ov_file:
        ov_data = ov_file.read()
    config = tomllib.loads(ov_data)
    appdir = config.get("paths", {}).get("library_root", None)
    appdir = os.path.join(appdir, f"{app_name}-{app_version}")

    # Windows: 'kit.bat' in '.' or 'kit' followed by 'kit.exe' in '.' or 'kit'
    # Linux: 'kit.sh' in '.' or 'kit' followed by 'kit' in '.' or 'kit'
    exe_names = ["kit.sh", "kit"]
    if sys.platform.startswith("win"):
        exe_names = ["kit.bat", "kit.exe"]

    # look in 4 places...
    for dir_name in [appdir, os.path.join(appdir, "kit")]:
        for name in exe_names:
            if os.path.exists(os.path.join(dir_name, name)):
                return os.path.join(dir_name, name)

    return None


class AnsysGeometryServiceServerExtension(omni.ext.IExt):
    """
    This class is an Omniverse kit.  The kit is capable of creating a
    connection to an Ansys Distributed Scene Graph service and pushing
    the graph into an Omniverse Nucleus.
    """

    _service_instance = None

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        ext_name = __name__.rsplit(".", 1)[0]
        self._logger = logging.getLogger(ext_name)
        self._dsg_uri = self._setting("dsgUrl", "ENSIGHT_GRPC_URI")
        self._omni_uri = self._setting("omniUrl", "ENSIGHT_OMNI_URI")
        self._security_token = self._setting("securityCode", "ENSIGHT_SECURITY_TOKEN")
        self._temporal = self._setting("temporal") != "0"
        self._vrmode = self._setting("vrmode") != "0"
        try:
            scale = float(self._setting("timeScale"))
        except ValueError:
            scale = 1.0
        self._time_scale = scale
        self._normalize_geometry = self._setting("normalizeGeometry") != "0"
        self._version = "unknown"
        self._shutdown = False
        self._server_process = None

    @property
    def dsg_uri(self) -> str:
        """The endpoint of a Dynamic Scene Graph service:  grpc://{hostname}:{port}"""
        return self._dsg_uri

    @dsg_uri.setter
    def dsg_uri(self, uri: str) -> None:
        self._dsg_uri = uri

    @property
    def omni_uri(self) -> str:
        """The endpoint of an Omniverse Nucleus service:  omniverse://{hostname}/{path}"""
        return self._omni_uri

    @omni_uri.setter
    def omni_uri(self, value: str) -> None:
        self._omni_uri = value

    @property
    def security_token(self) -> str:
        """The security token of the DSG service instance."""
        return self._security_token

    @security_token.setter
    def security_token(self, value: str) -> None:
        self._security_token = value

    @property
    def temporal(self) -> bool:
        """If True, the DSG update should include all timesteps."""
        return self._temporal

    @temporal.setter
    def temporal(self, value: bool) -> None:
        self._temporal = bool(value)

    @property
    def vrmode(self) -> bool:
        """If True, the DSG update should not include camera transforms."""
        return self._vrmode

    @vrmode.setter
    def vrmode(self, value: bool) -> None:
        self._vrmode = bool(value)

    @property
    def normalize_geometry(self) -> bool:
        """If True, the DSG geometry should be remapped into normalized space."""
        return self._normalize_geometry

    @normalize_geometry.setter
    def normalize_geometry(self, val: bool) -> None:
        self._normalize_geometry = val

    @property
    def time_scale(self) -> float:
        """Value to multiply DSG time values by before passing to Omniverse"""
        return self._time_scale

    @time_scale.setter
    def time_scale(self, value: float) -> None:
        self._time_scale = value

    @classmethod
    def get_instance(cls) -> Optional["AnsysGeometryServiceServerExtension"]:
        return cls._service_instance

    @classmethod
    def _setting(cls, name: str, env_varname: str = "") -> str:
        """
        Get a CLI option value. First check if any specified
        environment variable is present and if so, return that value.
        Next, check to see if a command line value is set and return
        that.  Finally, fall back to the value (if any) specified in
        the kit toml file.

        Parameters
        ----------
        name
            The name of the command line flag to check the value of.
        env_varname
            Optional name of the environment variable to check the value of.

        Returns
        -------
            A string or None.
        """
        # any environmental variable trumps them all.
        if env_varname:
            value = os.environ.get(env_varname, None)
            if value:
                return value
        settings = carb.settings.get_settings()
        ext_name = __name__.rsplit(".", 1)[0]
        s = f"/exts/{ext_name}/{name}"
        return settings.get(s)

    def info(self, text: str) -> None:
        """
        Send message to the logger at the info level.

        Parameters
        ----------
        text
            The message to send.
        """
        self._logger.info(text)

    def warning(self, text: str) -> None:
        """
        Send message to the logger at the warning level.

        Parameters
        ----------
        text
            The message to send.
        """
        self._logger.warning(text)

    def error(self, text: str) -> None:
        """
        Send message to the logger at the error level.

        Parameters
        ----------
        text
            The message to send.
        """
        self._logger.error(text)

    def on_startup(self, ext_id: str) -> None:
        """
        Called by Omniverse when the kit instance is started.

        Parameters
        ----------
        ext_id
            The specific version of the kit.
        """
        self._version = ext_id
        self.info(f"ANSYS geometry service server startup: {self._version}")
        AnsysGeometryServiceServerExtension._service_instance = self
        if self._setting("help") is not None:
            self.help()
        elif self._setting("run") is not None:
            self.run_server()

    def on_shutdown(self) -> None:
        """
        Called by Omniverse when the kit instance is shutting down.
        """
        self.info("ANSYS geometry service server shutdown")
        self.shutdown()
        AnsysGeometryServiceServerExtension._service_instance = None

    def help(self) -> None:
        """
        Send the CLI help output to logging.
        """
        self.warning(f"ANSYS Omniverse Geometry Service: {self._version}")
        self.warning("  --/exts/ansys.geometry.service/help=1")
        self.warning("     Display this help.")
        self.warning("  --/exts/ansys.geometry.service/run=1")
        self.warning("     Run the server.")
        self.warning("  --/exts/ansys.geometry.service/omniUrl=URL")
        self.warning(f"    Omniverse pathname.  (default: {self.omni_uri})")
        self.warning("  --/exts/ansys.geometry.service/dsgUrl=URL")
        self.warning(f"    Dynamic Scene Graph connection URL.  (default: {self.dsg_uri})")
        self.warning("  --/exts/ansys.geometry.service/securityCode=TOKEN")
        self.warning(f"    Dynamic Scene Graph security token.  (default: {self.security_token})")
        self.warning("  --/exts/ansys.geometry.service/temporal=0|1")
        self.warning(
            f"    If non-zero, include all timeseteps in the scene.  (default: {self.temporal})"
        )
        self.warning("  --/exts/ansys.geometry.service/vrmode=0|1")
        self.warning(
            f"    If non-zero, do not include a camera in the scene.  (default: {self.vrmode})"
        )
        self.warning("  --/exts/ansys.geometry.service/normalizeGeometry=0|1")
        self.warning(
            f"    If non-zero, remap the geometry to the domain [-1,-1,-1]-[1,1,1].  (default: {self.normalize_geometry})"
        )
        self.warning("  --/exts/ansys.geometry.service/timeScale=FLOAT")
        self.warning(
            f"    Multiply all DSG time values by this value.  (default: {self.time_scale})"
        )

    def is_server_running(self) -> bool:
        """
        Returns True if the server is running.

        Returns
        -------
        bool
            True if the server is running.
        """
        if self._server_process:
            if psutil.pid_exists(self._server_process.pid):
                return True
        return False

    def stop_server(self) -> None:
        """
        If a DSG server connection has been started, stop it.  It could be in
        process or a subprocess.
        """
        try:
            self._shutdown = True
            if self._server_process:
                for child in psutil.Process(self._server_process.pid).children(recursive=True):
                    child.kill()
                self._server_process.kill()
        except psutil.NoSuchProcess:
            pass
        self._server_process = None
        self._shutdown = False

    def launch_server(self) -> None:
        """
        Launch a DSG to Omniverse server as a subprocess.
        """
        if self._server_process:
            self.warning("Only a single subprocess server is supported.")
            return
        kit_name = find_kit_filename()
        if kit_name is None:
            self.warning("Unable to determine a kit executable pathname.")
            return
        self.info(f"Using {kit_name} to launch the server")
        cmd = [kit_name]
        # kit extension location
        kit_dir = __file__
        for _ in range(5):
            kit_dir = os.path.dirname(kit_dir)
        cmd.extend(["--ext-folder", kit_dir])
        cmd.extend(["--enable", "ansys.geometry.service"])
        if self.security_token:
            cmd.append(f"--/exts/ansys.geometry.service/securityCode={self.security_token}")
        if self.temporal:
            cmd.append("--/exts/ansys.geometry.service/temporal=1")
        if self.vrmode:
            cmd.append("--/exts/ansys.geometry.service/vrmode=1")
        if self.normalize_geometry:
            cmd.append("--/exts/ansys.geometry.service/normalizeGeometry=1")
        if self.time_scale != 1.0:
            cmd.append(f"--/exts/ansys.geometry.service/timeScale={self.time_scale}")
        cmd.append(f"--/exts/ansys.geometry.service/omniUrl={self.omni_uri}")
        cmd.append(f"--/exts/ansys.geometry.service/dsgUrl={self.dsg_uri}")
        cmd.append("--/exts/ansys.geometry.service/run=1")
        env_vars = os.environ.copy()
        working_dir = os.path.join(os.path.dirname(ansys.pyensight.core.__file__), "utils")
        self._server_process = subprocess.Popen(cmd, close_fds=True, env=env_vars, cwd=working_dir)

    def run_server(self) -> None:
        """
        Run a DSG to Omniverse server in process.

        Note: this method does not return until the DSG connection is dropped or
        self.stop_server() has been called.
        """
        try:
            import ansys.pyensight.core.utils.dsg_server as dsg_server
            import ansys.pyensight.core.utils.omniverse_dsg_server as ov_dsg_server
        except ImportError as e:
            self.error(f"Unable to load DSG service core: {str(e)}")
            return

        # Note: This is temporary.  The correct fix will be included in
        # the pyensight 0.8.5 wheel.  The OmniverseWrapper assumes the CWD
        # to be the directory with the "resource" directory.
        os.chdir(os.path.dirname(ov_dsg_server.__file__))

        # Build the Omniverse connection
        omni_link = ov_dsg_server.OmniverseWrapper(path=self._omni_uri, verbose=1)
        self.info("Omniverse connection established.")

        # parse the DSG USI
        parsed = urlparse(self.dsg_uri)
        port = parsed.port
        host = parsed.hostname

        # link it to a DSG session
        update_handler = ov_dsg_server.OmniverseUpdateHandler(omni_link)
        dsg_link = dsg_server.DSGSession(
            port=port,
            host=host,
            vrmode=self.vrmode,
            security_code=self.security_token,
            verbose=1,
            normalize_geometry=self.normalize_geometry,
            time_scale=self.time_scale,
            handler=update_handler,
        )

        # Start the DSG link
        self.info(f"Making DSG connection to: {self.dsg_uri}")
        err = dsg_link.start()
        if err < 0:
            self.error("Omniverse connection failed.")
            return

        # Initial pull request
        dsg_link.request_an_update(animation=self.temporal)

        # until the link is dropped, continue
        while not dsg_link.is_shutdown() and not self._shutdown:
            dsg_link.handle_one_update()

        self.info("Shutting down DSG connection")
        dsg_link.end()
        omni_link.shutdown()
