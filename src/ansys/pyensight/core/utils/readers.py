from types import ModuleType
from typing import Optional, Union

try:
    import ensight
except ImportError:
    from ansys.api.pyensight import ensight_api


class Readers:
    def __init__(self, interface: Union["ensight_api.ensight", "ensight"]):
        self._ensight = interface
        self._dvs = DVS(self._ensight)
    
    @property
    def dvs(self):
        return self._dvs


class DVS:
    def __init__(self, interface: Union["ensight_api.ensight", "ensight"]):
        self._ensight = interface
        
    def launch_live_dvs(self, port: int = 0, secret_key: Optional[str] = None):
        indent = "    "
        cmd = "def dvs_callback():\n"
        cmd += f'{indent}command_string = f"set_server_port={port}"\n'
        if secret_key:
            secret_string = f'{indent}command_string += f"&set_secret_key='
            secret_string += "'" + secret_key + "'" + '"\n'
            cmd += secret_string
        cmd += f"{indent}reply = ensight.objs.core.CURRENTCASE[0].client_command(command_string)"
        cmd += f'{indent}return f"{port}" in str(reply)'
        cmd += "ensight.objs.core.CURRENTCASE[0].client_command_callback(dvs_callback)"
        cmd += 'ensight.solution_time.monitor_for_new_steps("stay_at_current")'
        cmd += 'ensight.data.replace("notexisting.dvs")'
        cmd += "ensight.objs.core.CURRENTCASE[0].client_command_callback(None)"
        self._ensight._session.cmd(cmd)

