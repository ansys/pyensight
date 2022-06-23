"""dockerlauncher module

The docker launcher module provides pyensight with the ability to launch an
EnSight session using a local Docker installation.

Examples:
    >>> from ansys.pyensight import DockerLauncher
    >>> launcher = DockerLauncher(data_directory="D:\\data")
    >>> launcher.pull()
    >>> session = launcher.start()
    >>> launcher.stop()
"""
import atexit
import glob
import os.path
import platform
import shutil
import subprocess
import tempfile
from typing import Optional
import uuid

import docker

from ansys import pyensight

class DockerLauncher(pyensight.Launcher):
    """Create a Session instance by launching a local Docker copy of EnSight

    Launch a Docker copy of EnSight locally that supports the gRPC interface.  Create and
    bind a Session instance to the created gRPC session.  Return that session.

    Args:
        ansys_installation:
            Location of the ANSYS installation, including the version
            directory Default: None (causes common locations to be scanned)

    Examples:
        >>> from ansys.pyensight import DockerLauncher
        >>> launcher = DockerLauncher(data_directory="D:\\data")
        >>> launcher.pull()
        >>> session = launcher.start()
        >>> launcher.stop()
    """

    def __init__(self, data_directory: str, docker_image_name: Optional[str] = None,
        use_dev: Optional[bool] = False) -> None:
        super().__init__()

        self._data_directory = data_directory

        # get the optional user specified image name
        self._image_name: str = "ghcr.io/ansys/ensight"
        if use_dev:
            self._image_name: str = "ghcr.io/ansys/ensight_dev"
        if docker_image_name:
            self._image_name: str = docker_image_name

        # Load up Docker from the user's environment
        try:
            self._docker_client: docker.client.DockerClient = docker.from_env()
        except Exception:
            raise RuntimeError(f"Can't initialize Docker")
            
        # EnSight session secret key
        self._secret_key: str = str(uuid.uuid1())
        # temporary directory
        self._session_directory: str = "/home/ensight"

    def pull(self) -> None:
        """Pulls the Docker image.

        Returns:
            None

        Raises:
            RuntimeError:
                if Docker couldn't pull the image.
        """
        try:
            self._docker_client.images.pull(self._image_name)
        except Exception:
            raise RuntimeError(f"Can't pull Docker image: {self._image_name}")


    def start(self) -> "pyensight.Session":
        """Start an EnSight session using the local Docker ensight image
        Launch a copy of EnSight in the container that supports the gRPC interface.  Create and
        bind a Session instance to the created gRPC session.  Return that session.

        Returns:
            pyensight Session object instance

        Raises:
            RuntimeError:
                if the necessary number of ports could not be allocated.
        """
        # gRPC port, VNC port, websocketserver ws, websocketserver html
        ports = self._find_unused_ports(4)
        if ports is None:
            raise RuntimeError("Unable to allocate local ports for EnSight session")
        #is_windows = platform.system() == "Windows"

        # Launch the EnSight Docker container locally as a detached container
        # initially not running any apps so we can launch the three needed
        # apps

        # create the environmental variables
        local_env = os.environ.copy()
        local_env["ENSIGHT_SECURITY_TOKEN"] = self._secret_key
        local_env["WEBSOCKETSERVER_SECURITY_TOKEN"] = self._secret_key
        #local_env["ENSIGHT_SESSION_TEMPDIR"] = self._session_directory

        # environment to pass into the container
        container_env = {"ENSIGHT_SECURITY_TOKEN":self._secret_key,
            "WEBSOCKETSERVER_SECURITY_TOKEN":self._secret_key,
            "ENSIGHT_SESSION_TEMPDIR":self._session_directory,
            "ANSYSLMD_LICENSE_FILE":os.environ["ANSYSLMD_LICENSE_FILE"]}

        # ports to map between the host and the container
        ports_to_map = { \
            str(ports[0])+'/tcp':str(ports[0]),
            str(ports[2])+'/tcp':str(ports[2]),
            str(ports[3])+'/tcp':str(ports[3]) \
            }

        # the data directory to map into the container
        data_volume = {self._data_directory:{'bind':'/data', 'mode':'rw'}}

        # Start the container in detached mode and override
        # the default entrypoint so we can run multiple commands
        # within the container.

        # FIXME_MFK: probably need a unique name for our container
        # in case the user launches multiple sessions
        self._container = self._docker_client.containers.run(self._image_name,
            entrypoint="/bin/bash", volumes=data_volume,
            environment=container_env, ports=ports_to_map, 
            name="ensight", tty=True, detach=True)

        # build up the command to run ensight and send it to the container
        # as a detached command

        cmd = ["bash", "--login", "-c"]
        cmd2 = "ensight -batch -v 3"

        cmd2 += " -grpc_server " + str(ports[0]) 

        vnc_url = f"vnc://%%3Frfb_port={ports[1]}%%26use_auth=0"
        cmd2 += " -vnc " + vnc_url

        cmd.extend([cmd2])

        print("Run: ", str(cmd))

        self._container.exec_run(cmd, user="ensight", detach=True)

        """
        # Launch websocketserver
        # find websocketserver script
        found_scripts = glob.glob(
            os.path.join(self._install_path, "nexus*", "nexus_launcher", "websocketserver.py")
        )
        if not found_scripts:
            raise RuntimeError("Unable to find websocketserver script")
        websocket_script = found_scripts[0]

        # build the commandline
        cmd = [os.path.join(self._install_path, "bin", "cpython"), websocket_script]
        """

        cmd = ["bash", "--login", "-c"]
        #cmd2 = "cpython /home/ensight/websocketserver.py"
        cmd2 = "cpython /ansys_inc/v231/CEI/nexus231/nexus_launcher/websocketserver.py"

        cmd2 += " --http_directory " + self._session_directory
        # http port
        cmd2 += " --http_port " + str(ports[2])
        # vnc port
        cmd2 += " --client_port " + str(ports[1])
        # websocket port
        cmd2 += " " + str(ports[3])

        cmd.extend([cmd2])

        print("Run: ", str(cmd))

        self._container.exec_run(cmd, user="ensight", detach=True)

        # build the session instance
        session = pyensight.Session(
            host="127.0.0.1",
            grpc_port=ports[0],
            html_port=ports[2],
            ws_port=ports[3],
            install_path=None,
            secret_key=self._secret_key,
        )
        session.launcher = self
        self._sessions.append(session)
        return session

    def stop(self) -> None:
        """Release any additional resources allocated during launching"""
        #atexit.register(shutil.rmtree, self._session_directory)
        self._container.stop()
        self._container.remove()


