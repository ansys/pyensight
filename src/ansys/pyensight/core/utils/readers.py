"""Readers module.

This module contains utilities to do readers specific operations.
"""

from threading import Thread
from typing import Optional, Union

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
    def dvs(self):
        return self._dvs


class DVS:
    """A namespace to access specific DVS interfaces"""

    def __init__(self, interface: Union["ensight_api.ensight", "ensight"]):
        self._ensight = interface

    MONITOR_NEW_TIMESTEPS_STAY_AT_CURRENT = "stay_at_current"
    MONITOR_NEW_TIMESTEPS_JUMP_TO_END = "jump_to_end"

    def launch_live_dvs(
        self,
        port: int,
        secret_key: Optional[str] = None,
        monitor_new_timesteps: str = MONITOR_NEW_TIMESTEPS_STAY_AT_CURRENT,
        start_thread: bool = True,
    ) -> Thread:
        """To provide an interface to launch an in-situ EnSight DVS session.

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
        indent = "    "
        cmd = "def dvs_callback():\n"
        cmd += f'{indent}command_string = f"set_server_port={port}"\n'
        if secret_key is not None:
            secret_string = f'{indent}command_string += f"&set_secret_key='
            secret_string += "'" + secret_key + "'" + '"\n'
            cmd += secret_string
        cmd += f"{indent}reply = ensight.objs.core.CURRENTCASE[0].client_command(command_string)\n"
        cmd += f'{indent}return f"{port}" in str(reply)\n\n'
        cmd += "ensight.objs.core.CURRENTCASE[0].client_command_callback(dvs_callback)\n"
        cmd += f'ensight.solution_time.monitor_for_new_steps("{monitor_new_timesteps}")\n'
        cmd += 'ensight.data.replace("notexisting.dvs")\n'
        cmd += "ensight.objs.core.CURRENTCASE[0].client_command_callback(None)"
        t = Thread(target=load_dvs)
        if start_thread:
            t.start()
        return t
