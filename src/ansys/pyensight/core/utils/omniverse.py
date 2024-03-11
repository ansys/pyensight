import os
import subprocess
import sys
from typing import TYPE_CHECKING, Union

import psutil

if TYPE_CHECKING:
    try:
        import ensight
    except ImportError:
        from ansys.api.pyensight import ensight_api


class Omniverse:
    """Provides the ``ensight.utils.omniverse`` interface.

    The omniverse class methods provide an interface between an EnSight session
    and an Omniverse instance.

    Note
    ----
    This interface is only available when using pyensight (they do not work with
    the ensight Python interpreter) and the module must be used in an interpreter
    that includes the Omniverse Python modules (e.g. omni and pxr).  Only a single
    Omniverse connection can be established within a single pyensight session.

    Parameters
    ----------
    interface :
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
        ov.push_scene()
        ov.close_connection()

    """

    def __init__(self, interface: Union["ensight_api.ensight", "ensight"]):
        self._ensight = interface
        self._server_pid = None

    @staticmethod
    def _check_modules() -> None:
        """Verify that the Python interpreter is correct

        Check for omni and pxr modules. If not present, raise an exception.

        Raises
        ------
        RuntimeError if the necessary modules are missing.

        """
        try:
            # Note: the EnSight embedded interpreter will not have these
            import omni  # noqa: F401
            import pxr  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "The module requires the omni and pxr modules to be installed."
            ) from None

    def _is_running_omniverse(self):
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
        temporal: bool = False,
        debug_filename: str = "",
    ) -> None:
        """Ensure that an EnSight dsg -> omniverse server is running

        pathname = "omniverse://localhost/Users/test"
        verbose = ..
        temporal = False
        live = True
        normalize_geometry = False
        store_camera = False

        """
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
            sys.executable,
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
        if temporal:
            cmd.extend(["--animation"])
        else:
            cmd.extend(["--no-animation"])
        if debug_filename:
            cmd.extend(["--log_file", debug_filename])
            cmd.extend(["--verbose", "1"])
        if normalize_geometry:
            cmd.extend(["--normalize_geometry"])
        env_vars = os.environ.copy()
        process = subprocess.Popen(cmd, close_fds=True, env=env_vars, cwd=working_dir)
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

    def push_scene(self) -> None:
        """Update the geometry in Omniverse"""
        self._check_modules()
        if not self._is_running_omniverse():
            raise RuntimeError("No Omniverse server connection is currently active.")
        update_cmd = "dynamicscenegraph://localhost/client/update"
        cmd = f'enspyqtgui_int.dynamic_scene_graph_command("{update_cmd}")'
        self._ensight._session.cmd(cmd, do_eval=False)
