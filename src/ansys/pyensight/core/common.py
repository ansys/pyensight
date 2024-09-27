""" This module provides a list of common utilities shared between different PyEnSight modules."""

import random
import re
import socket
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from ansys.pyensight.core import enshell_grpc
import urllib3

try:
    from simple_upload_server.client import Client

    simple_upload_server_is_available = True  # pragma: no cover
except Exception:
    simple_upload_server_is_available = False

if TYPE_CHECKING:
    from docker import DockerClient


def find_unused_ports(count: int, avoid: Optional[List[int]] = None) -> Optional[List[int]]:
    """Find "count" unused ports on the host system

    A port is considered unused if it does not respond to a "connect" attempt.  Walk
    the ports from 'start' to 'end' looking for unused ports and avoiding any ports
    in the 'avoid' list.  Stop once the desired number of ports have been
    found.  If an insufficient number of ports were found, return None.

    Parameters
    ----------
    count: int :
        Number of unused ports to find
    avoid: Optional[List[int]] :
        An optional list of ports not to check

    Returns
    -------
        The detected ports or None on failure

    """
    if avoid is None:
        avoid = []
    ports = list()

    # pick a starting port number
    start = random.randint(1024, 64000)
    # We will scan for 65530 ports unless end is specified
    port_mod = 65530
    end = start + port_mod - 1
    # walk the "virtual" port range
    for base_port in range(start, end + 1):
        # Map to physical port range
        # There have been some issues with 65534+ so we stop at 65530
        port = base_port % port_mod
        # port 0 is special
        if port == 0:  # pragma: no cover
            continue  # pragma: no cover
        # avoid admin ports
        if port < 1024:  # pragma: no cover
            continue  # pragma: no cover
        # are we supposed to skip this one?
        if port in avoid:  # pragma: no cover
            continue  # pragma: no cover
        # is anyone listening?
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("127.0.0.1", port))
        if result != 0:
            ports.append(port)
        else:
            sock.close()  # pragma: no cover
        if len(ports) >= count:
            return ports
    # in case we failed...
    if len(ports) < count:  # pragma: no cover
        return None  # pragma: no cover
    return ports  # pragma: no cover


def get_host_port(uri: str) -> Tuple[str, int]:
    """Get the host port for the input uri

    Parameters
    ----------

    uri: str
        The Uri to inspect

    Returns
    -------
    (tuple):
        A tuple containing the host and the port of the input uri
    """
    parse_results = urllib3.util.parse_url(uri)
    port = (
        parse_results.port
        if parse_results.port
        else (443 if re.search("^https|wss$", parse_results.scheme) else None)
    )
    return (parse_results.host, port)


def get_file_service(pim_instance: Any) -> Optional[Any]:  # pragma: no cover
    """Get the file service object for the input pim instance.

    Parameters
    ----------

    pim_instance:
        the PIM instance to get the service from.

    Returns
    -------

    pim_file_service:
        the PIM file service object
    """
    if simple_upload_server_is_available is False:
        return None
    if pim_instance is None:
        return None

    if "http-simple-upload-server" in pim_instance.services:
        pim_file_service = Client(
            token="token",
            url=pim_instance.services["http-simple-upload-server"].uri,
            headers=pim_instance.services["http-simple-upload-server"].headers,
        )
        return pim_file_service
    return None


def populate_service_host_port(  # pragma: no cover
    pim_instance: Any, service_host_port: Dict[str, Tuple[str, int]], webui: bool = False
) -> Dict[str, Tuple[str, int]]:
    """Populate the service host port dictionary with the services available in the PIM instance.

    Parameters
    ----------
    pim_instance:
        the PIM instance to get the servicea from.
    service_host_port: dict
        the dictionary to be updated with the services from the PIM instance
    webui: bool
        if True retrieve also the webUI service

    Returns
    -------
    service_host_port: dict
        the dictionary updated with the services from the PIM instance
    """
    if not set(("grpc_private", "http", "ws")).issubset(pim_instance.services):
        raise RuntimeError(
            "If channel is specified, the PIM instance must have a list of length 3 "
            + "containing the appropriate service URIs. It does not."
        )
    service_host_port["grpc_private"] = get_host_port(pim_instance.services["grpc_private"].uri)
    service_host_port["http"] = get_host_port(pim_instance.services["http"].uri)
    service_host_port["ws"] = get_host_port(pim_instance.services["ws"].uri)
    service_host_port["grpc"] = ("127.0.0.1", -1)
    if webui:
        service_host_port["webui"] = get_host_port(pim_instance.services["webui"].uri)
    return service_host_port


def launch_enshell_interface(
    enshell_grpc_channel: Any, grpc_port: int, timeout: float
) -> enshell_grpc.EnShellGRPC:
    """Launch the EnShell gRPC Interface.

    Parameters
    ----------
    enshell_grpc_channel:
        An eventual gRPC channel already available, like in the PIM case
    grpc_port: int
        the gRPC port to connect to
    timeout: float
        a timeout to wait for the gRPC connection

    Returns
    -------
    enshell: enshell_grpc.EnShellGRPC
        the enshell gRPC interface
    """
    if enshell_grpc_channel:  # pragma: no cover
        enshell = enshell_grpc.EnShellGRPC()  # pragma: no cover
        enshell.connect_existing_channel(enshell_grpc_channel)  # pragma: no cover
    else:
        enshell = enshell_grpc.EnShellGRPC(port=grpc_port)
        time_start = time.time()
        while time.time() - time_start < timeout:  # pragma: no cover
            if enshell.is_connected():
                break
            try:
                enshell.connect(timeout=timeout)
            except OSError:  # pragma: no cover
                pass  # pragma: no cover
    return enshell


def pull_image(docker_client: "DockerClient", image_name: str) -> None:
    """Pull the input docker image using the input Docker Client

    Parameters
    ----------
    docker_client: DockerClient
        the current DockerClient to pull the image with
    image_name: str
        the image to pull
    """
    try:
        if docker_client is not None:  # pragma: no cover
            docker_client.images.pull(image_name)
    except Exception:
        raise RuntimeError(f"Can't pull Docker image: {image_name}")
