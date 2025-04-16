"""Readers module.

This module contains utilities to do readers specific operations.
"""
import os
import re
from threading import Thread
import time
from types import ModuleType
from typing import Optional, Tuple, Union
import uuid

try:
    import ensight
except ImportError:
    from ansys.api.pyensight import ensight_api


class Readers:
    """A namespace to access the interfaces of specific readers"""

    def __init__(self, interface: Union["ensight_api.ensight", "ensight"]):
        self._ensight = interface
        self._dvs = DVS(self._ensight)

    @property
    def dvs(self) -> "DVS":
        """The ensight interface"""
        return self._dvs


class DVS:
    """A namespace to access specific DVS interfaces"""

    def __init__(self, interface: Union["ensight_api.ensight", "ensight"]):
        self._ensight: Union["ensight_api.ensight", "ensight"] = interface
        self._dvs_port: Optional[int] = None

    MONITOR_NEW_TIMESTEPS_STAY_AT_CURRENT = "stay_at_current"
    MONITOR_NEW_TIMESTEPS_JUMP_TO_END = "jump_to_end"

    def _launch_live_dvs_242_cmd(
        self,
        tmp_name: str,
        port: int = 0,
        secret_key: Optional[str] = None,
        monitor_new_timesteps: str = MONITOR_NEW_TIMESTEPS_STAY_AT_CURRENT,
    ):
        """Launch a live DVS session from PyEnSight for EnSight 242 and onward"""
        indent = "    "
        cmd = "import re\n"
        cmd += "def dvs_callback():\n"
        cmd += f'{indent}command_string = f"set_server_port={port}"\n'
        if secret_key is not None:
            secret_string = f'{indent}command_string += f"&set_secret_key='
            secret_string += secret_key + '"\n'
            cmd += secret_string
        tmp_name = tmp_name.replace("\\", "\\\\")
        cmd += f"{indent}reply = ensight.objs.core.CURRENTCASE[0].client_command(command_string)\n"
        cmd += f"{indent}dvs_port_string = ensight.objs.core.CURRENTCASE[0].client_command('get_server_port')\n"
        cmd += (
            f"{indent}dvs_port = int(re.search(r':([0-9]{{4,5}})', dvs_port_string).groups(1)[0])\n"
        )
        cmd += f"{indent}with open('{tmp_name}', 'w') as temp_file:\n"
        cmd += f"{2*indent}temp_file.write(str(dvs_port))\n"
        cmd += f"{indent}return True\n\n"
        cmd += "reply = ensight.objs.core.CURRENTCASE[0].client_command_callback(dvs_callback)\n"
        if monitor_new_timesteps:
            cmd += f'ensight.solution_time.monitor_for_new_steps("{monitor_new_timesteps}")\n'
        cmd += 'ensight.part.elt_representation("3D_feature_2D_full")\n'
        cmd += 'ensight.data.format("DVS")\n'
        cmd += 'err = ensight.data.replace("notexisting.dvs")\n'
        return cmd

    def _launch_live_dvs_241_cmd(
        self,
        port: int = 0,
        secret_key: Optional[str] = None,
        monitor_new_timesteps: str = MONITOR_NEW_TIMESTEPS_STAY_AT_CURRENT,
    ):
        """Launch a live DVS session from PyEnSight for EnSight 241"""
        if port == 0:
            ports = self._ensight._session.find_remote_unused_ports(1)
            if ports:
                self._dvs_port = ports[0]
                port = ports[0]
        indent = "    "
        cmd = "import os\n"
        cmd += f"try:\n{indent}os.remove('remote.dvs')\n"
        cmd += f"except (FileNotFoundError, OSError):\n{indent}pass\n"
        cmd += "path = os.path.join(os.getcwd(), 'remote.dvs')\n"
        cmd += "with open(path, 'w') as dvsfile:\n"
        cmd += f"{indent}dvsfile.write('#!DVS_CASE 1.0\\n')\n"
        cmd += f"{indent}dvsfile.write(f'SERVER_PORT_BASE={port}\\n')\n"
        cmd += f"{indent}dvsfile.write('SERVER_PORT_MULT=1\\n')\n"
        if secret_key:
            cmd += f"{indent}dvsfile.write(f'SERVER_SECURITY_SECRET={secret_key}\\n')\n"
        cmd += f'ensight.solution_time.monitor_for_new_steps("{monitor_new_timesteps}")\n'
        cmd += 'ensight.part.elt_representation("3D_feature_2D_full")\n'
        cmd += 'ensight.data.format("DVS")\n'
        cmd += "ensight.data.replace(path)\n"
        return cmd

    def _find_dvs_port(self, tmp_name: Optional[str] = None):
        """Find the dvs port allocated from the input temporary name"""
        if not tmp_name:
            raise RuntimeError("Temporary name for dvs port file not available")
        try_local = True
        if self._ensight._session._launcher:
            if hasattr(self._ensight._session._launcher, "_enshell"):
                try_local = False
                log_content = self._ensight._session._launcher.enshell_log_contents()
                dvs_port_match = re.search(r"\(0.0.0.0\):([0-9]{4,5})\n", log_content)
                if dvs_port_match:
                    self._dvs_port = int(str(dvs_port_match.groups(1)[0]).strip())
        if try_local:
            try:
                with open(tmp_name) as dvs_port_file:
                    self._dvs_port = int(dvs_port_file.read().strip())
            except Exception:
                raise RuntimeError("Cannot retrieve DVS Port")

    @staticmethod
    def _launch_dvs_callback_in_ensight(
        port: int,
        filename: Optional[str],
        secret_key: Optional[str],
        monitor_new_timesteps: str = MONITOR_NEW_TIMESTEPS_STAY_AT_CURRENT,
    ) -> None:  # pragma: no cover
        """Launch a live DVS session in EnSight"""
        from ceiversion import ensight_suffix  # pylint: disable=import-outside-toplevel

        if int(ensight_suffix) < 242:
            from cei import find_unused_ports  # pylint: disable=import-outside-toplevel

            if port == 0:
                ports = find_unused_ports(1)
                if ports:
                    port = ports[0]
            try:
                os.remove("remote.dvs")
            except (FileNotFoundError, OSError):
                pass
            path = os.path.join(os.getcwd(), "remote.dvs")
            with open(path, "w") as dvsfile:
                dvsfile.write("#!DVS_CASE 1.0\n")
                dvsfile.write(f"SERVER_PORT_BASE={port}\n")
                dvsfile.write("SERVER_PORT_MULT=1\n")
                if secret_key is not None:
                    dvsfile.write(f"SERVER_SECURITY_SECRET={secret_key}\n")
            if filename:
                try:
                    with open(filename, "w") as dvs_port_file:
                        dvs_port_file.write(str(port))
                except Exception:
                    raise RuntimeError(f"Couldn't write allocated DVS port to {filename}")
            ensight.part.elt_representation("3D_feature_2D_full")
            ensight.solution_time.monitor_for_new_steps(f"{monitor_new_timesteps}")
            ensight.data.format("DVS")
            ensight.data.replace(path)
        else:

            def dvs_callback():
                command_string = f"set_server_port={port}"
                if secret_key is not None:
                    command_string += f"&set_secret_key={secret_key}"
                ensight.objs.core.CURRENTCASE[0].client_command(command_string)
                dvs_port_string = ensight.objs.core.CURRENTCASE[0].client_command("get_server_port")
                dvs_port_match = re.search(r":([0-9]{4,5})", dvs_port_string)
                dvs_port = None
                if dvs_port_match:
                    dvs_port = int(dvs_port_match.groups(1)[0])
                if not dvs_port:
                    raise RuntimeError("DVS couldn't allocate a port")
                if filename:
                    try:
                        with open(filename, "w") as dvs_port_file:
                            dvs_port_file.write(str(dvs_port))
                    except Exception:
                        raise RuntimeError(f"Couldn't write allocated DVS port to {filename}")
                return True

            ensight.objs.core.CURRENTCASE[0].client_command_callback(dvs_callback)
            ensight.solution_time.monitor_for_new_steps(f"{monitor_new_timesteps}")
            ensight.part.elt_representation("3D_feature_2D_full")
            ensight.data.format("DVS")
            ensight.data.replace("notexisting.dvs")

    def launch_live_dvs(
        self,
        port: int = 0,
        secret_key: Optional[str] = None,
        monitor_new_timesteps: str = MONITOR_NEW_TIMESTEPS_STAY_AT_CURRENT,
        start_thread: bool = True,
        filename: Optional[str] = None,
    ) -> Tuple[Optional[Thread], Optional[int]]:
        """To provide an interface to launch an in-situ EnSight DVS session.
        If in PyEnSight, the function will return a thread which will launch the DVS reader
        in EnSight, hence the DVS servers, and will also return the port allocated by DVS, to
        cover the case the port 0 was asked for.
        If instead the function will be used directly in EnSight via the utils interface, since
        the reader launch will block the interpreter waiting for new data, the port cannot be returned
        and cannot be printed up until the first update happens.
        So, if you need to access the port number in a script and you cannot check the EnSight console,
        please supply a filename to store the dvs port into.

        Parameters
        ----------
        port: int
            the port number where the first DVS server will be started. In case of a
            SOS EnSight session, on the following server the DVS servers will be started on the
            next port, e.g. if the first server starts at port 50055, the second will start
            at port 50056 and so on
        secret_key: str
            an optional secret key to pass in case the DVS clients have been started with a secret key
            for the underlying gRPC connections. An empty string can be provided if needed
        monitor_new_timesteps: str
            set the way EnSight will monitor for new timesteps. Defaults to MONITOR_NEW_TIMESTEPS_STAY_AT_CURRENT.
            The allowed values are MONITOR_NEW_TIMESTEPS_STAY_AT_CURRENT
            and MONITOR_NEW_TIMESTEPS_JUMP_TO_END
        start_thread: bool
            True if the thread to be returned needs to be started already. Default is True
        filename: str
            An optional path to store the port number in. It will be used only if the utils is being
            called directly in EnSight.

        Returns
        -------
        Thread:
            a python Thread which holds the dvs load
        """

        def load_dvs():
            self._ensight._session.cmd(cmd, do_eval=False)

        if monitor_new_timesteps not in [
            self.MONITOR_NEW_TIMESTEPS_JUMP_TO_END,
            self.MONITOR_NEW_TIMESTEPS_STAY_AT_CURRENT,
        ]:
            raise RuntimeError(
                f"{monitor_new_timesteps} value not allowed for an in-situ DVS session"
            )
        if not isinstance(self._ensight, ModuleType):  # pragma: no cover
            self._ensight._session.ensight_version_check("2024 R1")
        else:
            self._launch_dvs_callback_in_ensight(
                port=port,
                secret_key=secret_key,
                monitor_new_timesteps=monitor_new_timesteps,
                filename=filename,
            )
            return None, None
        cmd = ""
        path = None
        if int(self._ensight._session.cei_suffix) < 242:
            cmd = self._launch_live_dvs_241_cmd(
                port=port, secret_key=secret_key, monitor_new_timesteps=monitor_new_timesteps
            )
        else:
            tmp_name = str(uuid.uuid4())
            path = os.path.join(self._ensight._session._launcher.session_directory, tmp_name)
            cmd = self._launch_live_dvs_242_cmd(
                port=port,
                secret_key=secret_key,
                monitor_new_timesteps=monitor_new_timesteps,
                tmp_name=path,
            )
        t = Thread(target=load_dvs)
        if start_thread:
            t.start()
        start = time.time()
        while not self._dvs_port and time.time() - start < 60:
            try:
                self._find_dvs_port(path)
            except Exception:
                pass
            time.sleep(0.5)
        return t, self._dvs_port
