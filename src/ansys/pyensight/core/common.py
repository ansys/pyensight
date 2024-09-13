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
            sock.close()
        if len(ports) >= count:
            return ports
    # in case we failed...
    if len(ports) < count:  # pragma: no cover
        return None  # pragma: no cover
    return ports  # pragma: no cover


def get_host_port(uri: str) -> Tuple[str, int]:
    """Get the host port for the input uri"""
    parse_results = urllib3.util.parse_url(uri)
    port = (
        parse_results.port
        if parse_results.port
        else (443 if re.search("^https|wss$", parse_results.scheme) else None)
    )
    return (parse_results.host, port)


def get_file_service(pim_instance: Any) -> Optional[Any]:
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


def populate_service_host_port(
    pim_instance: Any, service_host_port: Dict[str, Tuple[str, int]]
) -> Dict[str, Tuple[str, int]]:
    if not set(("grpc_private", "http", "ws")).issubset(pim_instance.services):
        raise RuntimeError(
            "If channel is specified, the PIM instance must have a list of length 3 "
            + "containing the appropriate service URIs. It does not."
        )
    service_host_port["grpc_private"] = get_host_port(pim_instance.services["grpc_private"].uri)
    service_host_port["http"] = get_host_port(pim_instance.services["http"].uri)
    service_host_port["ws"] = get_host_port(pim_instance.services["ws"].uri)
    service_host_port["grpc"] = ("127.0.0.1", -1)
    return service_host_port


def launch_enshell_interface(
    enshell_grpc_channel: Any, grpc_port: int, timeout: float
) -> enshell_grpc.EnShellGRPC:
    if enshell_grpc_channel:
        enshell = enshell_grpc.EnShellGRPC()
        enshell.connect_existing_channel(enshell_grpc_channel)
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
    """Pull the input docker image using the input Docker Client"""
    try:
        if docker_client is not None:  # pragma: no cover
            docker_client.images.pull(image_name)
    except Exception:
        raise RuntimeError(f"Can't pull Docker image: {image_name}")
