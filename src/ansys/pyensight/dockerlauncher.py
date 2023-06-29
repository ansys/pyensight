"""dockerlauncher module

The docker launcher module provides pyensight with the ability to launch an
EnSight session using a local Docker installation or a PIM launched Docker installation.

Examples:
    ::

        from ansys.pyensight import DockerLauncher
        launcher = DockerLauncher(data_directory="D:\\data")
        launcher.pull()
        session = launcher.start()
        session.close()

"""
import logging
import os.path
import subprocess
import time
from typing import Any, Dict, Optional
import uuid

import urllib3

try:
    import grpc
except ModuleNotFoundError:
    raise RuntimeError("The grpc module must be installed for DockerLauncher")
except Exception:
    raise RuntimeError("Cannot initialize grpc")

from ansys import pyensight

try:
    from ansys.pyensight import enshell_grpc
except ModuleNotFoundError:
    raise RuntimeError("The enshell_grpc must be installed for DockerLauncher")
except Exception:
    raise RuntimeError("Cannot initialize enshell_grpc")


try:
    from simple_upload_server.client import Client

    simple_upload_server_is_available = True
except Exception:
    simple_upload_server_is_available = False


class DockerLauncher(pyensight.Launcher):
    """Create a Session instance using a Docker Container hosted copy of EnSight

    Either attach to a PIM launched Docker Container hosting EnSight, or launch a local Docker Container
    hosting EnSight.  gRPC connections to EnShell and EnSight are established.  A PyEnSight Session is
    returned upon successful launch and connection.

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
        use_egl:
            If True, EGL hardware accelerated graphics will be used. The platform
            must be able to support it.
        use_sos:
            If None, don't use SOS. Otherwise, it's the number of EnSight Servers to use (int).
        channel:
            Existing gRPC channel to a running EnShell instance such as provided by PIM
        pim_instance:
            The PyPIM instance if using PIM (internal)

    Examples:
        ::

            from ansys.pyensight import DockerLauncher
            launcher = DockerLauncher(data_directory="D:\\data")
            launcher.pull()
            session = launcher.start()
            session.close()

    """

    def __init__(
        self,
        data_directory: Optional[str] = None,
        docker_image_name: Optional[str] = None,
        use_dev: bool = False,
        channel: Optional[grpc.Channel] = None,
        pim_instance: Optional[Any] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        self._data_directory = data_directory
        self._enshell_grpc_channel = channel
        self._service_uris: Dict[Any, str] = {}
        self._image_name: Optional[str] = None
        self._docker_client: Optional[Any] = None
        self._container = None
        self._enshell: Optional[Any] = None
        self._pim_instance: Optional[Any] = pim_instance

        # EnSight session secret key
        self._secret_key: str = str(uuid.uuid1())
        # temporary directory
        # it's in the ephemeral container, so just use "ensight's"
        # home directory within the container
        self._session_directory: str = "/home/ensight"
        # the Ansys / EnSight version we found in the container
        # to be reassigned later
        self._ansys_version: Optional[str] = None
        # EnShell's log file
        self._enshell_log_file = None
        # pointer to the file service object if available
        self._pim_file_service = None

        logging.debug(
            f"DockerLauncher data_dir={self._data_directory}\n"
            + f"  image_name={self._image_name}\n"
            + f"  use_dev={use_dev}\n"
        )

        if self._enshell_grpc_channel and self._pim_instance:
            if not set(("grpc_private", "http", "ws")).issubset(self._pim_instance.services):
                raise RuntimeError(
                    "If channel is specified, the PIM instance must have a list of length 3 "
                    + "containing the appropriate service URIs. It does not."
                )
            self._service_host_port = {}
            # grab the URIs for the 3 required services passed in from PIM
            self._service_host_port["grpc_private"] = self._get_host_port(
                self._pim_instance.services["grpc_private"].uri
            )
            self._service_host_port["http"] = self._get_host_port(
                self._pim_instance.services["http"].uri
            )
            self._service_host_port["ws"] = self._get_host_port(
                self._pim_instance.services["ws"].uri
            )
            # for parity, add 'grpc' as a placeholder even though pim use sets up the grpc channel.
            # this isn't used in this situation.
            self._service_host_port["grpc"] = ("127.0.0.1", -1)
            # attach to the file service if available
            self._get_file_service()
            return

        # EnShell gRPC port, EnSight gRPC port, HTTP port, WSS port
        # skip 1999 as we'll use that internal to the Container for the VNC connection
        ports = self._find_unused_ports(4, avoid=[1999])
        if ports is None:
            raise RuntimeError("Unable to allocate local ports for EnSight session")
        self._service_host_port = {}
        self._service_host_port["grpc"] = ("127.0.0.1", ports[0])
        self._service_host_port["grpc_private"] = ("127.0.0.1", ports[1])
        self._service_host_port["http"] = ("127.0.0.1", ports[2])
        self._service_host_port["ws"] = ("127.0.0.1", ports[3])

        # get the optional user specified image name
        # Note: the default name will need to change over time...  TODO
        self._image_name = "ghcr.io/ansys-internal/ensight"
        if use_dev:
            self._image_name = "ghcr.io/ansys-internal/ensight_dev"
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

    def ansys_version(self) -> Optional[str]:
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
            if self._docker_client is not None:
                self._docker_client.images.pull(self._image_name)
        except Exception:
            raise RuntimeError(f"Can't pull Docker image: {self._image_name}")

    def start(self) -> "pyensight.Session":
        """Start EnShell by running a local Docker EnSight Image.
        Then, connect to the EnShell in the Container over gRPC.  Once connected,
        have EnShell launch a copy of EnSight and WSS in the Container.
        Create and bind a Session instance to the created EnSight gRPC connection.
        Return the Session.

        Args:

        Returns:
            pyensight Session object instance

        Raises:
            RuntimeError:
                variety of error conditions.
        """
        tmp_session = super().start()
        if tmp_session:
            return tmp_session

        # Launch the EnSight Docker container locally as a detached container
        # initially running EnShell over the first gRPC port. Then launch EnSight
        # and other apps.

        # Create the environmental variables
        local_env = os.environ.copy()
        local_env["ENSIGHT_SECURITY_TOKEN"] = self._secret_key
        local_env["WEBSOCKETSERVER_SECURITY_TOKEN"] = self._secret_key
        # If for some reason, the ENSIGHT_ANSYS_LAUNCH is set previously,
        # honor that value, otherwise set it to "pyensight".  This allows
        # for an environmental setup to set the value to something else
        # (e.g. their "app").
        if "ENSIGHT_ANSYS_LAUNCH" not in local_env:
            local_env["ENSIGHT_ANSYS_LAUNCH"] = "container"

        # Environment to pass into the container
        container_env = {
            "ENSIGHT_SECURITY_TOKEN": self._secret_key,
            "WEBSOCKETSERVER_SECURITY_TOKEN": self._secret_key,
            "ENSIGHT_SESSION_TEMPDIR": self._session_directory,
            "ANSYSLMD_LICENSE_FILE": os.environ["ANSYSLMD_LICENSE_FILE"],
            "ENSIGHT_ANSYS_LAUNCH": local_env["ENSIGHT_ANSYS_LAUNCH"],
        }
        if "ENSIGHT_ANSYS_APIP_CONFIG" in local_env:
            container_env["ENSIGHT_ANSYS_APIP_CONFIG"] = local_env["ENSIGHT_ANSYS_APIP_CONFIG"]

        # Ports to map between the host and the container
        # If we're here in the code, then we're not using PIM
        # and we're not really using URIs where the hostname
        # is anything other than 127.0.0.1, so, we only need
        # to grab the port numbers.
        grpc_port = self._service_host_port["grpc"][1]
        ports_to_map = {
            str(self._service_host_port["grpc"][1])
            + "/tcp": str(self._service_host_port["grpc"][1]),
            str(self._service_host_port["grpc_private"][1])
            + "/tcp": str(self._service_host_port["grpc_private"][1]),
            str(self._service_host_port["http"][1])
            + "/tcp": str(self._service_host_port["http"][1]),
            str(self._service_host_port["ws"][1]) + "/tcp": str(self._service_host_port["ws"][1]),
        }

        # The data directory to map into the container
        data_volume = None
        if self._data_directory:
            data_volume = {self._data_directory: {"bind": "/data", "mode": "rw"}}

        # Start the container in detached mode with EnShell as a
        # gRPC server as the command
        #
        enshell_cmd = "-app -v 3 -grpc_server " + str(grpc_port)

        try:
            import docker
        except ModuleNotFoundError:
            raise RuntimeError("The pyansys-docker module must be installed for DockerLauncher")
        except Exception:
            raise RuntimeError("Cannot initialize Docker")

        use_egl = self._use_egl()

        logging.debug("Starting Container...\n")
        if data_volume:
            if use_egl:
                if self._docker_client:
                    self._container = self._docker_client.containers.run(
                        self._image_name,
                        command=enshell_cmd,
                        volumes=data_volume,
                        environment=container_env,
                        device_requests=[
                            docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])
                        ],
                        ports=ports_to_map,
                        tty=True,
                        detach=True,
                        auto_remove=True,
                        remove=True,
                    )
            else:
                logging.debug(f"Running container {self._image_name} with cmd {enshell_cmd}\n")
                logging.debug(f"ports to map: {ports_to_map}\n")
                if self._docker_client:
                    self._container = self._docker_client.containers.run(
                        self._image_name,
                        command=enshell_cmd,
                        volumes=data_volume,
                        environment=container_env,
                        ports=ports_to_map,
                        tty=True,
                        detach=True,
                        auto_remove=True,
                        remove=True,
                    )
                logging.debug(f"_container = {str(self._container)}\n")
        else:
            if use_egl:
                if self._docker_client:
                    self._container = self._docker_client.containers.run(
                        self._image_name,
                        command=enshell_cmd,
                        environment=container_env,
                        device_requests=[
                            docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])
                        ],
                        ports=ports_to_map,
                        tty=True,
                        detach=True,
                        auto_remove=True,
                        remove=True,
                    )
            else:
                logging.debug(f"Running container {self._image_name} with cmd {enshell_cmd}\n")
                logging.debug(f"ports to map: {ports_to_map}\n")
                if self._docker_client:
                    self._container = self._docker_client.containers.run(
                        self._image_name,
                        command=enshell_cmd,
                        environment=container_env,
                        ports=ports_to_map,
                        tty=True,
                        detach=True,
                        auto_remove=True,
                        remove=True,
                    )
                # logging.debug(f"_container = {str(self._container)}\n")
        logging.debug("Container started.\n")
        return self.connect()

    def connect(self):
        """Internal method. Create and bind a Session instance to the created gRPC EnSight
           session as started by EnShell.  Return that session.

        Args:

        Returns:
            pyensight Session object instance

        Raises:
            RuntimeError:
                variety of error conditions.
        """
        #
        #
        # Start up the EnShell gRPC interface
        log_dir = "/data"
        if self._enshell_grpc_channel:
            self._enshell = enshell_grpc.EnShellGRPC()
            self._enshell.connect_existing_channel(self._enshell_grpc_channel)
            log_dir = "/work"
        else:
            logging.debug(
                f"Connecting to EnShell over gRPC port: {self._service_host_port['grpc'][1]}...\n"
            )
            self._enshell = enshell_grpc.EnShellGRPC(port=self._service_host_port["grpc"][1])
            time_start = time.time()
            while time.time() - time_start < self._timeout:
                if self._enshell.is_connected():
                    break
                try:
                    self._enshell.connect(timeout=self._timeout)
                except OSError:
                    pass

        if not self._enshell.is_connected():
            self.stop()
            raise RuntimeError("Can't connect to EnShell over gRPC.")

        cmd = "set_no_reroute_log"
        ret = self._enshell.run_command(cmd)
        logging.debug(f"enshell cmd: {cmd} ret: {ret}\n")
        if ret[0] != 0:
            self.stop()
            raise RuntimeError(f"Error sending EnShell command: {cmd} ret: {ret}")

        files_to_try = [log_dir + "/enshell.log", "/home/ensight/enshell.log"]
        for f in files_to_try:
            cmd = "set_debug_log " + f
            ret = self._enshell.run_command(cmd)
            if ret[0] == 0:
                self._enshell_log_file = f
                break
            else:
                logging.debug(f"enshell error; cmd: {cmd} ret: {ret}\n")

        if self._enshell_log_file is not None:
            logging.debug(f"enshell log file {self._enshell_log_file}\n")

        cmd = "verbose 3"
        ret = self._enshell.run_command(cmd)
        logging.debug(f"enshell cmd: {cmd} ret: {ret}\n")
        if ret[0] != 0:
            self.stop()
            raise RuntimeError(f"Error sending EnShell command: {cmd} ret: {ret}")

        logging.debug("Connected to EnShell.  Getting CEI_HOME and Ansys version...\n")
        logging.debug(f"  _enshell: {self._enshell}\n\n")
        # Build up the command to run ensight via the EnShell gRPC interface

        self._cei_home = self._enshell.cei_home()
        self._ansys_version = self._enshell.ansys_version()
        print("CEI_HOME=", self._cei_home)
        print("Ansys Version=", self._ansys_version)

        logging.debug("Got them.  Starting EnSight...\n")

        use_egl = self._use_egl()

        # Run EnSight
        ensight_env = None
        if use_egl:
            ensight_env = (
                "export LD_PRELOAD=/usr/local/lib64/libGL.so.1:/usr/local/lib64/libEGL.so.1 ;"
            )

        ensight_args = "-batch -v 3"

        if use_egl:
            ensight_args += " -egl"

        if self._use_sos:
            ensight_args += " -sos -nservers " + str(int(self._use_sos))

        ensight_args += " -grpc_server " + str(self._service_host_port["grpc_private"][1])

        vnc_url = "vnc://%%3Frfb_port=1999%%26use_auth=0"
        ensight_args += " -vnc " + vnc_url

        logging.debug(f"Starting EnSight with args: {ensight_args}\n")
        ret = self._enshell.start_ensight(ensight_args, ensight_env)
        if ret[0] != 0:
            self.stop()
            raise RuntimeError(f"Error starting EnSight with args: {ensight_args}")

        logging.debug("EnSight started.  Starting wss...\n")

        # Run websocketserver
        wss_cmd = "cpython /ansys_inc/v" + self._ansys_version + "/CEI/nexus"
        wss_cmd += self._ansys_version + "/nexus_launcher/websocketserver.py"
        wss_cmd += " --http_directory " + self._session_directory
        # http port
        wss_cmd += " --http_port " + str(self._service_host_port["http"][1])
        # vnc port
        wss_cmd += " --client_port 1999"

        if self._enable_rest_api:
            # grpc port
            wss_cmd += " --grpc_port " + str(self._service_host_port["grpc_private"][1])

        # EnVision sessions
        wss_cmd += " --local_session envision 5"
        # websocket port
        wss_cmd += " " + str(self._service_host_port["ws"][1])

        logging.debug(f"Starting WSS: {wss_cmd}\n")
        ret = self._enshell.start_other(wss_cmd)
        if ret[0] != 0:
            self.stop()
            raise RuntimeError(f"Error starting WSS: {wss_cmd}\n")

        logging.debug("wss started.  Making session...\n")

        # build the session instance
        # WARNING: assuming the host is the same for grpc_private, http, and ws
        # This may not be true in the future if using PIM.
        # revise Session to handle three different hosts if necessary.
        session = pyensight.Session(
            host=self._service_host_port["grpc_private"][0],
            grpc_port=self._service_host_port["grpc_private"][1],
            html_port=self._service_host_port["http"][1],
            ws_port=self._service_host_port["ws"][1],
            install_path=None,
            secret_key=self._secret_key,
            timeout=self._timeout,
        )
        session.launcher = self
        self._sessions.append(session)

        logging.debug("Return session.\n")

        return session

    def stop(self) -> None:
        """Release any additional resources allocated during launching"""
        if self._enshell:
            if self._enshell.is_connected():
                try:
                    logging.debug("Stopping EnShell.\n")
                    self._enshell.stop_server()
                except Exception:
                    pass
                self._enshell = None
        #
        if self._container:
            try:
                logging.debug("Stopping the Docker Container.\n")
                self._container.stop()
            except Exception:
                pass
            try:
                logging.debug("Removing the Docker Container.\n")
                self._container.remove()
            except Exception:
                pass
            self._container = None

        if self._pim_instance is not None:
            logging.debug("Deleting the PIM instance.\n")
            self._pim_instance.delete()
            self._pim_instance = None
        super().stop()

    def _get_file_service(self) -> None:
        if simple_upload_server_is_available is False:
            return
        if self._pim_instance is None:
            return

        if "http-simple-upload-server" in self._pim_instance.services:
            self._pim_file_service = Client(
                token="token",
                url=self._pim_instance.services["http-simple-upload-server"].uri,
                headers=self._pim_instance.services["http-simple-upload-server"].headers,
            )

    def file_service(self) -> Optional[Any]:
        """Return PIM file service object if available"""
        return self._pim_file_service

    def _get_host_port(self, uri: str) -> tuple:
        parse_results = urllib3.util.parse_url(uri)
        return (parse_results.host, parse_results.port)

    def _is_system_egl_capable(self) -> bool:
        if self._is_windows():
            return False

        # FIXME: MFK, need to figure out how we'd do this
        # with a PIM managed system such as Ansys Lab
        if self._pim_instance is not None:
            return False

        try:
            subprocess.check_output("nvidia-smi")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def enshell_log_contents(self) -> Optional[str]:
        """Return the contents of the EnShell log if possible.

        Returns:
            string or None
        """
        if self._enshell_log_file is None:
            return None

        if self._container is not None:
            try:
                # docker containers allow copying from a container to the host
                # a file, files, or a directory.  it arrives as a tar file.
                # we're grabbing just the log file, but we still need to
                # extract it from the tar file and then put the contents
                # in the string we're returning
                from io import BytesIO
                import tarfile

                bits, stat = self._container.get_archive(self._enshell_log_file)
                file_obj = BytesIO()
                for chunk in bits:
                    file_obj.write(chunk)
                file_obj.seek(0)
                tar = tarfile.open(mode="r", fileobj=file_obj)
                member = tar.getmembers()
                text = tar.extractfile(member[0])
                s = text.read().decode("utf-8")
                text.close()
                return s
            except Exception:
                return None

        fs = self.file_service()
        if fs is not None:
            try:
                fs.download_file("enshell.log", ".")
                f = open("enshell.log")
                s = f.read()
                f.close()
                return s
            except Exception:
                return None
