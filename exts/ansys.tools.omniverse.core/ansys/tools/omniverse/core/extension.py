import json
import logging
import os
import platform
import subprocess
import sys
import tempfile
from typing import Optional
import uuid

import carb.settings
import omni.ext
import omni.kit.app
import omni.kit.pipapi

"""
The current kit leverages an EnSight installation.  It can find this via
environmental variable/directory scanning (looking for an Ansys installation)
or by looking at CEI_HOME. CEI_HOME is tried first.
"""


def find_kit_filename() -> Optional[str]:
    """
    Use a combination of the current omniverse application and the information
    in the local .nvidia-omniverse/config/omniverse.toml file to come up with
    the pathname of a kit executable suitable for hosting another copy of the
    ansys.tools.omniverse.core kit.

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


class AnsysToolsOmniverseCoreServerExtension(omni.ext.IExt):
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
        if self._omni_uri.startswith("omniverse://"):
            self._omni_uri = "~"
        self._omni_uri = os.path.expanduser(self._omni_uri)
        self._security_token = self._setting("securityCode", "ENSIGHT_SECURITY_TOKEN")
        self._temporal = self._setting("temporal") != "0"
        self._vrmode = self._setting("vrmode") != "0"
        try:
            scale = float(self._setting("timeScale"))
        except ValueError:
            scale = 1.0
        self._time_scale: float = scale
        self._normalize_geometry = self._setting("normalizeGeometry") != "0"
        self._version: str = ""
        self._shutdown: bool = False
        self._server_process = None
        self._status_filename: str = ""
        self._interpreter = self._find_ensight_cpython()

    @property
    def version(self) -> str:
        return self._version

    @property
    def dsg_uri(self) -> str:
        """The endpoint of a Dynamic Scene Graph service:  grpc://{hostname}:{port}"""
        return self._dsg_uri

    @dsg_uri.setter
    def dsg_uri(self, uri: str) -> None:
        self._dsg_uri = uri

    @property
    def destination(self) -> str:
        """The output USD directory name"""
        return self._omni_uri

    @destination.setter
    def destination(self, value: str) -> None:
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

    @property
    def interpreter(self) -> str:
        """Fully qualified path to the python.exe or .bat wrapper in which pyensight is installed."""
        return self._interpreter

    @interpreter.setter
    def interpreter(self, value: str) -> None:
        self._interpreter = value

    @classmethod
    def get_instance(cls) -> Optional["AnsysToolsOmniverseCoreServerExtension"]:
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

    def _find_ensight_cpython(self) -> Optional[str]:
        """
        Scan the current system, looking for EnSight installations, specifically, cpython.
        Check: PYENSIGHT_ANSYS_INSTALLATION, CEI_HOME, AWP_ROOT* in that order

        Returns
        -------
            The first cpython found or None

        """

        cpython = "cpython"
        if platform.system() == "Windows":
            cpython += ".bat"

        dirs_to_check = []
        if "PYENSIGHT_ANSYS_INSTALLATION" in os.environ:
            env_inst = os.environ["PYENSIGHT_ANSYS_INSTALLATION"]
            dirs_to_check.append(env_inst)
            # Note: PYENSIGHT_ANSYS_INSTALLATION is designed for devel builds
            # where there is no CEI directory, but for folks using it in other
            # ways, we'll add that one too, just in case.
            dirs_to_check.append(os.path.join(env_inst, "CEI"))

        # Look for most recent Ansys install, 25.1 or later
        awp_roots = []
        for env_name in dict(os.environ).keys():
            if env_name.startswith("AWP_ROOT") and int(env_name[len("AWP_ROOT") :]) >= 251:
                awp_roots.append(env_name)
        awp_roots.sort(reverse=True)
        for env_name in awp_roots:
            dirs_to_check.append(os.path.join(os.environ[env_name], "CEI"))

        # check all the collected locations in order
        for install_dir in dirs_to_check:
            launch_file = os.path.join(install_dir, "bin", cpython)
            if os.path.isfile(launch_file):
                if self.validate_interpreter(launch_file):
                    return launch_file
        return ""

    def on_startup(self, ext_id: str) -> None:
        """
        Called by Omniverse when the kit instance is started.

        Parameters
        ----------
        ext_id
            The specific version of the kit.
        """
        self._version = ext_id.split("-")[-1]
        self.info(f"ANSYS tools omniverse core server startup: {self._version}")
        AnsysToolsOmniverseCoreServerExtension._service_instance = self

    def on_shutdown(self) -> None:
        """
        Called by Omniverse when the kit instance is shutting down.
        """
        self.info("ANSYS tools omniverse core server shutdown")
        self.shutdown()
        AnsysToolsOmniverseCoreServerExtension._service_instance = None

    def validate_interpreter(self, launch_file: str) -> bool:
        if len(launch_file) == 0:
            return False
        has_ov_module = False
        try:
            cmd = [launch_file, "-m", "ansys.pyensight.core.utils.omniverse_cli", "-h"]
            env_vars = os.environ.copy()
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env_vars)
            proc.wait(timeout=60)
            has_ov_module = proc.communicate()[0].decode("utf-8").startswith("usage: omniverse_cli")
        except Exception as error:
            self.warning(f"Exception thrown while testing python {str(launch_file)}: {str(error)}")
            has_ov_module = False
        return has_ov_module

    def dsg_export(self) -> None:
        """
        Use the oneshot feature of the pyensight omniverse_cli to push the current
        EnSight scene to the supplied directory in USD format.
        """
        if self._interpreter is None:
            self.warning("Unable to determine a kit executable pathname.")
            return
        self.info(f"Using {self._interpreter} to run the server")
        cmd = [self._interpreter]
        cmd.extend(["-m", "ansys.pyensight.core.utils.omniverse_cli"])
        cmd.append(self.destination)
        if self.security_token:
            cmd.extend(["--security_token", self.security_token])
        if self.temporal:
            cmd.extend(["--temporal", "true"])
        if self.vrmode:
            cmd.extend(["--include_camera", "false"])
        if self.normalize_geometry:
            cmd.extend(["--normalize_geometry", "true"])
        if self.time_scale != 1.0:
            cmd.extend(["--time_scale", str(self.time_scale)])
        cmd.extend(["--dsg_uri", self.dsg_uri])
        cmd.extend(["--oneshot", "true"])
        env_vars = os.environ.copy()
        # we are launching the kit from an Omniverse app.  In this case, we
        # inform the kit instance of:
        # (1) the name of the "server status" file, if any
        self._new_status_file()
        env_vars["ANSYS_OV_SERVER_STATUS_FILENAME"] = self._status_filename
        try:
            self.info(f"Running {' '.join(cmd)}")
            self._server_process = subprocess.Popen(cmd, close_fds=True, env=env_vars)
        except Exception as error:
            self.warning(f"Error running translator: {error}")
        self._new_status_file(new=False)

    def _new_status_file(self, new=True) -> None:
        """
        Remove any existing status file and create a new one if requested.

        Parameters
        ----------
        new : bool
            If True, create a new status file.
        """
        if self._status_filename:
            if os.path.exists(self._status_filename):
                try:
                    os.remove(self._status_filename)
                except OSError:
                    self.warning(f"Unable to delete the status file: {self._status_filename}")
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
