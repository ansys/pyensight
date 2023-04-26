"""dockerlauncherenshell module

The docker launcher enshell module provides pyensight with the ability to launch an
EnSight session using a local Docker installation via EnShell.

Examples:
    ::

        from ansys.pyensight import DockerLauncherEnShell
        launcher = DockerLauncherEnShell(data_directory="D:\\data")
        launcher.pull()
        session = launcher.start()
        session.close()

"""
import os.path
import re
import subprocess
from typing import Any, Optional
import uuid

try:
    import grpc
except ModuleNotFoundError:
    raise RuntimeError("The grpc module must be installed for DockerLauncherEnShell")
except Exception:
    raise RuntimeError("Cannot initialize grpc")

from ansys import pyensight

try:
    from enshell_remote import enshell_grpc
except ModuleNotFoundError:
    raise RuntimeError("The enshell_remote module must be installed for DockerLauncherEnShell")
except Exception:
    raise RuntimeError("Cannot initialize grpc")

pim_is_available = False
try:
    import ansys.platform.instancemanagement as pypim

    pim_is_available = True
except:
    pass


class DockerLauncherEnShell(pyensight.Launcher):
    """Create a Session instance by launching a local Docker copy of EnSight via EnShell

    Launch a Docker copy of EnSight locally via EnShell that supports the gRPC interface.  Create and
    bind a Session instance to the created gRPC session from EnSight (not EnShell).  Return that session.

    Args:
        data_directory:
            Host directory to make into the container at /data
        docker_image_name:
            Optional Docker Image name to use
        use_dev:
            Option to use the latest ensight_dev Docker Image; overridden by docker_image_name if specified.
        timeout:
            In some cases where the EnSight session can take a significant amount of
            timme to start up, this is the number of seconds to wait before failing
            the connection.  The default is 120.0.
        channel:
            Existing gRPC channel to a running EnShell instance such as provided by PIM
        ports:
            List of TCP ports to use by a running EnShell instance such a provided by PIM.
            Must be length 3 for: EnSight gRPC, HTTP, WSS
        pim_instance:
            The PyPIM instance if using PIM (internal)

    Examples:
        ::

            from ansys.pyensight import DockerLauncherEnShell
            launcher = DockerLauncherEnShell(data_directory="D:\\data")
            launcher.pull()
            session = launcher.start()
            session.close()

    """

    def __init__(
        self,
        data_directory: Optional[str] = None,
        docker_image_name: Optional[str] = None,
        use_dev: Optional[bool] = False,
        timeout: Optional[float] = 120.0,
        channel: Optional[grpc.Channel] = None,
        ports: Optional[list[int]] = None,
        pim_instance: Optional[Any] = None,
    ) -> None:
        super().__init__()

        self._data_directory = data_directory
        self._timeout = timeout
        self._enshell_grpc_channel = channel

        self._ports = None
        self._image_name = None
        self._docker_client = None
        self._container = None
        self._enshell = None
        self._pim_instance = pim_instance

        # EnSight session secret key
        self._secret_key: str = str(uuid.uuid1())
        # temporary directory
        # it's in the ephemeral container, so just use "ensight's"
        # home directory within the container
        self._session_directory: str = "/home/ensight"
        # the Ansys / EnSight version we found in the container
        # to be reassigned later
        self._ansys_version = None

        if self._enshell_grpc_channel:
            if not pim_is_available:
                raise RuntimeError("pim is not available")
            if len(ports) != 3:
                raise RuntimeError(
                    "If channel is specified, ports must be a list of 3 unused TCP port numbers."
                )
            # this is all we need to do if channel and ports are provided
            # EnShell gRPC port, EnSight gRPC port, HTTP port, WSS port
            self._ports = [-1, ports[0], ports[1], ports[2]]
            return

        # EnShell gRPC port, EnSight gRPC port, HTTP port, WSS port
        # skip 1999 as we'll use that internal to the Container for the VNC connection
        self._ports = self._find_unused_ports(4, avoid=[1999])
        if self._ports is None:
            raise RuntimeError("Unable to allocate local ports for EnSight session")

        # get the optional user specified image name
        self._image_name = "ghcr.io/ansys/ensight"
        if use_dev:
            self._image_name = "ghcr.io/ansys/ensight_dev"
        if docker_image_name:
            self._image_name = docker_image_name

        # Load up Docker from the user's environment
        try:
            import docker

            self._docker_client = docker.from_env()
        except ModuleNotFoundError:
            raise RuntimeError("The pyansys-docker module must be installed for DockerLauncher")
        except Exception:
            raise RuntimeError("Cannot initialize Docker")

    def ansys_version(self) -> str:
        """Returns the Ansys version as a 3 digit number string as found in the Docker container.

        Returns:
            Ansys 3-digit version as a string, or None if not found or not start()'ed

        """
        return self._ansys_version

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

    def start(
        self, use_egl: bool = False, use_sos: Optional[bool] = False, nservers: Optional[int] = 2
    ) -> "pyensight.Session":
        """Start EnShell by running a local Docker EnSight Image.
        Then, connect to the EnShell in the Container over gRPC.  Once connected,
        have EnShell launch a copy of EnSight and WSS in the Container.
        Create and bind a Session instance to the created EnSight gRPC connection.
        Return the Session.

        Args:
            use_egl:
                If True, EGL hardware accelerated graphics will be used. The platform
                must be able to support it.
            use_sos:
                If True, EnSight will use SOS.
            nservers:
                The number of EnSight Servers to use if using SOS.

        Returns:
            pyensight Session object instance

        Raises:
            RuntimeError:
                variety of error conditions.
        """

        # Launch the EnSight Docker container locally as a detached container
        # initially running EnShell over the first gRPC port. Then launch EnSight
        # and other apps.

        # Create the environmental variables
        local_env = os.environ.copy()
        local_env["ENSIGHT_SECURITY_TOKEN"] = self._secret_key
        local_env["WEBSOCKETSERVER_SECURITY_TOKEN"] = self._secret_key
        # local_env["ENSIGHT_SESSION_TEMPDIR"] = self._session_directory

        # Environment to pass into the container
        container_env = {
            "ENSIGHT_SECURITY_TOKEN": self._secret_key,
            "WEBSOCKETSERVER_SECURITY_TOKEN": self._secret_key,
            "ENSIGHT_SESSION_TEMPDIR": self._session_directory,
            "ANSYSLMD_LICENSE_FILE": os.environ["ANSYSLMD_LICENSE_FILE"],
        }

        # Ports to map between the host and the container
        ports_to_map = {
            str(self._ports[0]) + "/tcp": str(self._ports[0]),
            str(self._ports[1]) + "/tcp": str(self._ports[1]),
            str(self._ports[2]) + "/tcp": str(self._ports[2]),
            str(self._ports[3]) + "/tcp": str(self._ports[3]),
        }

        # The data directory to map into the container
        data_volume = None
        if self._data_directory:
            data_volume = {self._data_directory: {"bind": "/data", "mode": "rw"}}

        # FIXME_MFK: probably need a unique name for our container
        # in case the user launches multiple sessions
        egl_env = os.environ.get("PYENSIGHT_FORCE_ENSIGHT_EGL")
        self._use_egl = use_egl or egl_env or self._has_egl()
        # FIXME_MFK: fix egl and remove the next line
        self._use_egl = False

        # Start the container in detached mode with EnShell as a
        # gRPC server as the command
        #
        import docker

        enshellCmd = "-app -grpc_server " + str(self._ports[0])

        # print("Starting Container...\n")
        if data_volume:
            if self._use_egl:
                self._container = self._docker_client.containers.run(
                    self._image_name,
                    command=enshellCmd,
                    volumes=data_volume,
                    environment=container_env,
                    device_requests=[docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])],
                    ports=ports_to_map,
                    tty=True,
                    detach=True,
                )
            else:
                # print(f"Running container {self._image_name} with cmd {enshellCmd}\n")
                # print(f"ports to map: {self._ports}\n")
                self._container = self._docker_client.containers.run(
                    self._image_name,
                    command=enshellCmd,
                    volumes=data_volume,
                    environment=container_env,
                    ports=ports_to_map,
                    tty=True,
                    detach=True,
                )
                # print(f"_container = {str(self._container)}\n")
        else:
            if self._use_egl:
                self._container = self._docker_client.containers.run(
                    self._image_name,
                    command=enshellCmd,
                    environment=container_env,
                    device_requests=[docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])],
                    ports=ports_to_map,
                    tty=True,
                    detach=True,
                )
            else:
                # print(f"Running container {self._image_name} with cmd {enshellCmd}\n")
                # print(f"ports to map: {self._ports}\n")
                self._container = self._docker_client.containers.run(
                    self._image_name,
                    command=enshellCmd,
                    environment=container_env,
                    ports=ports_to_map,
                    tty=True,
                    detach=True,
                )
                # print(f"_container = {str(self._container)}\n")
        # print("Container started.\n")
        return self.connect(use_egl, use_sos, nservers)

    def connect(
        self, use_egl: bool = False, use_sos: Optional[bool] = False, nservers: Optional[int] = 2
    ):
        """Internal method. Create and bind a Session instance to the created gRPC EnSight
           session as started by EnShell.  Return that session.

        Args:
            use_egl:
                If True, EGL hardware accelerated graphics will be used. The platform
                must be able to support it.
            use_sos:
                If True, EnSight will use SOS.
            nservers:
                The number of EnSight Servers to use if using SOS.

        Returns:
            pyensight Session object instance

        Raises:
            RuntimeError:
                variety of error conditions.
        """
        #
        #
        # Start up the EnShell gRPC interface
        # print(f"Connecting to EnShell over gRPC port: {self._ports[0]}...\n")
        self._enshell = enshell_grpc.EnShellGRPC(port=self._ports[0])
        if self._enshell_grpc_channel:
            self._enshell.connect_existing_channel(self._enshell_grpc_channel)
        else:
            self._enshell.connect()
        if not self._enshell.is_connected():
            self.stop()
            raise RuntimeError("Can't connect to EnShell over gRPC.")

        # print("Connected to EnShell.  Getting CEI_HOME and Ansys version...\n")

        # Build up the command to run ensight via the EnShell gRPC interface

        self._cei_home = self._enshell.cei_home()
        self._ansys_version = self._enshell.ansys_version()
        # print("CEI_HOME=", self._cei_home)
        # print("Ansys Version=", self._ansys_version)

        # print("Got them.  Starting EnSight...\n")

        # Run EnSight
        ensight_env = None
        if self._use_egl:
            ensight_env = (
                "export LD_PRELOAD=/usr/local/lib64/libGL.so.1:/usr/local/lib64/libEGL.so.1 ;"
            )

        ensight_args = "-batch -v 3"

        if self._use_egl:
            ensight_args += " -egl"

        ensight_args += " -grpc_server " + str(self._ports[1])

        vnc_url = f"vnc://%%3Frfb_port=1999%%26use_auth=0"
        ensight_args += " -vnc " + vnc_url

        # print(f"Starting EnSight with args: {ensight_args}\n")
        ret = self._enshell.start_ensight(ensight_args, ensight_env)
        if ret[0] != 0:
            raise RuntimeError(f"Error starting EnSight with args: {ensight_args}")

        # print("EnSight started.  Starting wss...\n")

        # Run websocketserver
        wss_cmd = "cpython /ansys_inc/v" + self._ansys_version + "/CEI/nexus"
        wss_cmd += self._ansys_version + "/nexus_launcher/websocketserver.py"
        wss_cmd += " --http_directory " + self._session_directory
        # http port
        wss_cmd += " --http_port " + str(self._ports[2])
        # vnc port
        wss_cmd += " --client_port 1999"
        # EnVision sessions
        wss_cmd += " --local_session envision 5"
        # websocket port
        wss_cmd += " " + str(self._ports[3])

        # print(f"Starting WSS: {wss_cmd}\n")
        ret = self._enshell.start_other(wss_cmd)
        if ret[0] != 0:
            raise RuntimeError(f"Error starting WSS: {wss_cmd}\n")

        # print("wss started.  Making session...\n")

        # build the session instance
        session = pyensight.Session(
            host="127.0.0.1",
            grpc_port=self._ports[1],
            html_port=self._ports[2],
            ws_port=self._ports[3],
            install_path=None,
            secret_key=self._secret_key,
            timeout=self._timeout,
        )
        session.launcher = self
        self._sessions.append(session)

        # print("Return session.\n")

        return session

    def stop(self) -> None:
        """Release any additional resources allocated during launching"""
        if self._enshell.is_connected():
            self._enshell.stop_server()
            self._enshell = None
        #
        if self._container:
            self._container.stop()
            self._container.remove()
            self._container = None

        if self._pim_instance is not None:
            self._pim_instance.delete()
            self._pim_instance = None

    def _has_egl(self) -> bool:
        if self._is_windows():
            return False
        try:
            subprocess.check_output("nvidia-smi")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
