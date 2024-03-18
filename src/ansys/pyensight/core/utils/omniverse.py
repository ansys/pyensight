import os
import subprocess
import sys
from types import ModuleType
from typing import TYPE_CHECKING, List, Optional, Union

import psutil

if TYPE_CHECKING:
    try:
        import ensight
    except ImportError:
        from ansys.api.pyensight import ensight_api


class Omniverse:
    """Provides the ``ensight.utils.omniverse`` interface.

    The omniverse class methods provide an interface between an EnSight session
    and an Omniverse instance.  See :ref:`omniverse_info` for additional details.

    Note
    ----
    This interface is only available when using pyensight (they do not work with
    the ensight Python interpreter) and the module must be used in an interpreter
    that includes the Omniverse Python modules (e.g. omni and pxr).  Only a single
    Omniverse connection can be established within a single pyensight session.

    Parameters
    ----------
    interface:
        Entity that provides the ``ensight`` namespace. In the case of
        EnSight Python, the ``ensight`` module is passed. In the case
        of PyEnSight, ``Session.ensight`` is passed.

    Example
    -------
    ::
        from ansys.pyensight.core import LocalLauncher
        session = LocalLauncher().start()
        ov = session.ensight.utils.omniverse
        ov.create_connection()
        ov.update()
        ov.close_connection()

    """

    def __init__(self, interface: Union["ensight_api.ensight", "ensight"]):
        self._ensight = interface
        self._server_pid: Optional[int] = None
        self._interpreter: List[str] = []

    def _check_modules(self) -> None:
        """Verify that the Python interpreter is correct

        Check for omni module. If not present, raise an exception.
        If pxr is there as well, then we can just use sys.executable.
        If not, check to see if 'kit.bat' or 'kit.sh' can be found and
        arrange to use those instead.

        Raises
        ------
        RuntimeError if the necessary modules are missing.

        """
        # One time check for this
        if len(self._interpreter):
            return
        try:
            # Note: the EnSight embedded interpreter will not have these
            import omni.client  # noqa: F401
        except ImportError:
            raise RuntimeError("The module requires the omni module to be installed.") from None

        try:
            # if we can import pxr, then we can just use sys.executable
            from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdShade  # noqa: F401

            if os.path.basename(sys.executable).startswith("kit"):
                # we are running inside of an Omniverse app like Create, use the 'kit' script
                raise ImportError("Internal retry")

            self._interpreter = [sys.executable]
            return
        except ImportError:
            # Can we find 'kit.bat' or 'kit.sh' (we may be running in it)?
            # Interesting cases:  something/kit/python/python.exe,
            # something/kit/kit.exe.  All mapped to something/kit.{bat,sh} if found.
            ov_dir = os.path.dirname(sys.executable)
            for _ in range(3):
                for name in ("kit.bat", "kit.sh"):
                    exe_name = os.path.join(ov_dir, name)
                    if os.path.exists(exe_name):
                        self._interpreter = [
                            exe_name,
                            "--enable",
                            "omni.client",
                            "--enable",
                            "omni.usd",
                            "--exec",
                        ]
                        return
                ov_dir = os.path.dirname(ov_dir)
            raise RuntimeError("Unable to detect a copy of the Omniverse kit executable.") from None

    def _is_running_omniverse(self) -> bool:
        """Check that an Omniverse connection is active
        Returns
        -------
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
        live: bool = True,
        debug_filename: str = "",
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
        live : bool
            If True, one can call 'update()' to send updated geometry to Omniverse.
            If False, the Omniverse connection will push a single update and then
            disconnect.  Defaults to True.
        debug_filename : str
            If the name of a file is provided, it will be used to save logging information on
            the connection between EnSight and Omniverse.

        """
        if not isinstance(self._ensight, ModuleType):
            self._ensight._session.ensight_version_check("2023 R2")
        self._check_modules()
        if self._is_running_omniverse():
            raise RuntimeError("An Omniverse server connection is already active.")
        # Make sure the internal ui module is loaded
        self._ensight._session.cmd("import enspyqtgui_int", do_eval=False)
        # Get the gRPC connection details and use them to launch the service
        port = self._ensight._session.grpc.port()
        hostname = self._ensight._session.grpc.host
        token = self._ensight._session.grpc.security_token
        script_name = "omniverse_dsg_server.py"
        working_dir = os.path.dirname(__file__)
        cmd = [
            script_name,
            "--host",
            hostname,
            "--port",
            str(port),
            "--path",
            omniverse_path,
        ]
        if live:
            cmd.extend(["--live"])
        if include_camera:
            cmd.extend(["--vrmode"])
        if token:
            cmd.extend(["--security", token])
        # if temporal:
        #     cmd.extend(["--animation"])
        # else:
        #     cmd.extend(["--no-animation"])
        if debug_filename:
            cmd.extend(["--log_file", debug_filename])
            cmd.extend(["--verbose", "1"])
        if normalize_geometry:
            cmd.extend(["--normalize_geometry"])
        # if using kit.bat, convert args into a string, otherwise, just use them
        cmdline = []
        cmdline.extend(self._interpreter)
        if len(self._interpreter) > 1:
            cmd = [" ".join(cmd)]
        cmdline.extend(cmd)
        env_vars = os.environ.copy()
        process = subprocess.Popen(cmdline, close_fds=True, env=env_vars, cwd=working_dir)
        self._server_pid = process.pid

    def close_connection(self) -> None:
        """Shut down the open EnSight dsg -> omniverse server

        Break the connection between the EnSight instance and Omniverse.

        """
        self._check_modules()
        if not self._is_running_omniverse():
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

    def update(self) -> None:
        """Update the geometry in Omniverse

        Push the current EnSight scene to the current Omniverse connection.

        """
        if not isinstance(self._ensight, ModuleType):
            self._ensight._session.ensight_version_check("2023 R2")
        self._check_modules()
        if not self._is_running_omniverse():
            raise RuntimeError("No Omniverse server connection is currently active.")
        update_cmd = "dynamicscenegraph://localhost/client/update"
        cmd = f'enspyqtgui_int.dynamic_scene_graph_command("{update_cmd}")'
        self._ensight._session.cmd(cmd, do_eval=False)
