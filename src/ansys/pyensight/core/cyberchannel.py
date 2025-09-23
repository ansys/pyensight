"""Module to create gRPC channels with different transport modes.

This module provides functions to create gRPC channels based on the specified
transport mode, including insecure, Unix Domain Sockets (UDS), Windows Named User
Authentication (WNUA), and Mutual TLS (mTLS).

Example
-------
    channel = create_channel(
        host="localhost",
        port=50051,
        transport_mode="mtls",
        certs_dir="path/to/certs",
        grpc_options=[('grpc.max_receive_message_length', 50 * 1024 * 1024)],
    )
    stub = hello_pb2_grpc.GreeterStub(channel)

"""

# Only the create_channel function is exposed for external use
__all__ = ["create_channel"]

import logging
import os
from pathlib import Path
from typing import Optional, Union, cast
from warnings import warn

import grpc

_IS_WINDOWS = os.name == "nt"
LOOPBACK_HOSTS = ("localhost", "127.0.0.1")

logger = logging.getLogger(__name__)


def create_channel(
    host: str,
    port: Union[int, str],
    transport_mode: Optional[str] = None,
    uds_service: Optional[str] = None,
    uds_dir: Optional[str] = None,
    uds_id: Optional[str] = None,
    certs_dir: Optional[str] = None,
    grpc_options: Optional[list[tuple[str, object]]] = None,
) -> grpc.Channel:
    """Create a gRPC channel based on the host and the transport mode.

    Parameters
    ----------
    host : str
        Hostname or IP address of the server
    port : int | str
        Port in which the server is running
    transport_mode : str | None
        Transport mode selected, by default `None` and thus it will be selected
        for you based on the connection criteria. Options are: "insecure", "uds", "wnua", "mtls"
    uds_service : str | None
        Optional service name for the UDS socket.
        By default `None` - however, if UDS is selected, it will
        be requested.
    uds_dir : str | None
        Directory to use for Unix Domain Sockets (UDS) transport mode.
        By default `None` and thus it will use the "~/.conn" folder.
    uds_id : str | None
        Optional ID to use for the UDS socket filename.
        By default `None` and thus it will use "<uds_service>.sock".
        Otherwise, the socket filename will be "<uds_service>-<uds_id>.sock".
    certs_dir : str | None
        Directory to use for TLS certificates.
        By default `None` and thus search for the "ANSYS_GRPC_CERTIFICATES" environment variable.
        If not found, it will use the "certs" folder assuming it is in the current working
        directory.
    grpc_options: list[tuple[str, object]] | None
        gRPC channel options to pass when creating the channel.
        Each option is a tuple of the form ("option_name", value).
        By default `None` and thus no extra options are added.

    Returns
    -------
    grpc.Channel
        The created gRPC channel

    """
    if transport_mode:
        return custom_channel_selection(
            host, port, transport_mode, uds_service, uds_dir, uds_id, certs_dir, grpc_options
        )
    else:
        return default_channel_selection(
            host, port, uds_service, uds_dir, uds_id, certs_dir, grpc_options
        )


def custom_channel_selection(
    host: str,
    port: Union[int, str],
    transport_mode: str,
    uds_service: Optional[str] = None,
    uds_dir: Optional[str] = None,
    uds_id: Optional[str] = None,
    certs_dir: Optional[str] = None,
    grpc_options: Optional[list[tuple[str, object]]] = None,
) -> grpc.Channel:
    """Select the transport mode based on user preference.

    Parameters
    ----------
    host : str
        Hostname or IP address of the server.
    port : int | str
        Port in which the server is running.
    transport_mode : str
        Transport mode selected by the user.
        Options are: "insecure", "uds", "wnua", "mtls"
    uds_service : str | None
        Optional service name for the UDS socket.
        By default `None` - however, if UDS is selected, it will
        be requested.
    uds_dir : str | None
        Directory to use for Unix Domain Sockets (UDS) transport mode.
        By default `None` and thus it will use the "~/.conn" folder.
    uds_id : str | None
        Optional ID to use for the UDS socket filename.
        By default `None` and thus it will use "<uds_service>.sock".
        Otherwise, the socket filename will be "<uds_service>-<uds_id>.sock".
    certs_dir : str | None
        Directory to use for TLS certificates.
        By default `None` and thus search for the "ANSYS_GRPC_CERTIFICATES" environment variable.
        If not found, it will use the "certs" folder assuming it is in the current working
        directory.
    grpc_options: list[tuple[str, object]] | None
        gRPC channel options to pass when creating the channel.
        Each option is a tuple of the form ("option_name", value).
        By default `None` and thus no extra options are added.

    Returns
    -------
    grpc.Channel
        The created gRPC channel

    """
    case = transport_mode.lower()
    if case == "insecure":
        return create_insecure_channel(host, port, grpc_options)
    if case == "uds":
        return create_uds_channel(uds_service, uds_dir, uds_id, grpc_options)
    if case == "wnua":
        return create_wnua_channel(host, port, grpc_options)
    if case == "mtls":
        return create_mtls_channel(host, port, certs_dir, grpc_options)
    raise ValueError(
        f"Unknown transport mode: {transport_mode}. "
        "Valid options are: 'insecure', 'uds', 'wnua', 'mtls'."
    )


def default_channel_selection(
    host: str,
    port: Union[int, str],
    uds_service: Optional[str],
    uds_dir: Optional[str],
    uds_id: Optional[str],
    certs_dir: Optional[str],
    grpc_options: Optional[list[tuple[str, object]]] = None,
) -> grpc.Channel:
    """Select the best transport mode based on the host and port.

    Parameters
    ----------
    host : str
        Hostname or IP address of the server.
    port : int | str
        Port in which the server is running.
    uds_service : str | None
        Optional service name for the UDS socket.
        By default `None` - however, if UDS is selected, it will
        be requested.
    uds_dir : str | None
        Directory to use for Unix Domain Sockets (UDS) transport mode.
        By default `None` and thus it will use the "~/.conn" folder.
    uds_id : str | None
        Optional ID to use for the UDS socket filename.
        By default `None` and thus it will use "<uds_service>.sock".
        Otherwise, the socket filename will be "<uds_service>-<uds_id>.sock".

    Returns
    -------
    grpc.Channel
        The created gRPC channel

    """
    # Priority order:
    # 1) UDS if host is localhost and UDS is supported
    # 2) WNUA if host is localhost and on Windows
    # 3) mTLS if host is localhost or remote
    #
    # Insecure is not selected by default for security reasons
    if host in LOOPBACK_HOSTS and is_uds_supported():
        return create_uds_channel(uds_service, uds_dir, uds_id, grpc_options)
    elif host in LOOPBACK_HOSTS and _IS_WINDOWS:
        return create_wnua_channel(host, port, grpc_options)
    else:
        return create_mtls_channel(host, port, certs_dir, grpc_options)


def create_insecure_channel(
    host: str, port: Union[int, str], grpc_options: Optional[list[tuple[str, object]]] = None
) -> grpc.Channel:
    """Create an insecure gRPC channel without TLS.

    Parameters
    ----------
    host : str
        Hostname or IP address of the server.
    port : int | str
        Port in which the server is running.
    grpc_options: list[tuple[str, object]] | None
        gRPC channel options to pass when creating the channel.
        Each option is a tuple of the form ("option_name", value).
        By default `None` and thus no extra options are added.

    Returns
    -------
    grpc.Channel
        The created gRPC channel

    """
    target = f"{host}:{port}"
    warn(
        f"Starting gRPC client without TLS on {target}. This is INSECURE. "
        "Consider using a secure connection."
    )
    logger.info(f"Connecting using INSECURE -> {target}")
    return grpc.insecure_channel(target, options=grpc_options)


def create_uds_channel(
    uds_service: Optional[str],
    uds_dir: Optional[str] = None,
    uds_id: Optional[str] = None,
    grpc_options: Optional[list[tuple[str, object]]] = None,
) -> grpc.Channel:
    """Create a gRPC channel using Unix Domain Sockets (UDS).

    Parameters
    ----------
    uds_service : str
        Service name for the UDS socket.
    uds_dir : str | None
        Directory to use for Unix Domain Sockets (UDS) transport mode.
        By default `None` and thus it will use the "~/.conn" folder.
    uds_id : str | None
        Optional ID to use for the UDS socket filename.
        By default `None` and thus it will use "<uds_service>.sock".
        Otherwise, the socket filename will be "<uds_service>-<uds_id>.sock".
    grpc_options: list[tuple[str, object]] | None
        gRPC channel options to pass when creating the channel.
        Each option is a tuple of the form ("option_name", value).
        By default `None` and thus only the default authority option is added.

    Returns
    -------
    grpc.Channel
        The created gRPC channel

    """
    if not is_uds_supported():
        raise RuntimeError(
            "Unix Domain Sockets are not supported on this platform or gRPC version."
        )

    if not uds_service:
        raise ValueError("When using UDS transport mode, 'uds_service' must be provided.")

    # If no directory is provided, use default based on OS
    if uds_dir:
        uds_folder = Path(uds_dir)
    else:
        if _IS_WINDOWS:
            uds_folder = Path(os.environ["USERPROFILE"]) / ".conn"
        else:
            # Linux/POSIX
            uds_folder = Path(os.environ["HOME"], ".conn")

    # Make sure the folder exists
    uds_folder.mkdir(parents=True, exist_ok=True)

    # Generate socket filename with optional ID
    socket_filename = f"{uds_service}-{uds_id}.sock" if uds_id else f"{uds_service}.sock"
    target = f"unix:{uds_folder / socket_filename}"
    # Set default authority to "localhost" for UDS connection
    # This is needed to avoid issues with some gRPC implementations,
    # see https://github.com/grpc/grpc/issues/34305
    options: list[tuple[str, object]] = [
        ("grpc.default_authority", "localhost"),
    ]
    if grpc_options:
        options.extend(grpc_options)
    logger.info(f"Connecting using UDS -> {target}")
    return grpc.insecure_channel(target, options=options)


def create_wnua_channel(
    host: str,
    port: Union[int, str],
    grpc_options: Optional[list[tuple[str, object]]] = None,
) -> grpc.Channel:
    """Create a gRPC channel using Windows Named User Authentication (WNUA).

    Parameters
    ----------
    host : str
        Hostname or IP address of the server.
    port : int | str
        Port in which the server is running.
    grpc_options: list[tuple[str, object]] | None
        gRPC channel options to pass when creating the channel.
        Each option is a tuple of the form ("option_name", value).
        By default `None` and thus only the default authority option is added.

    Returns
    -------
    grpc.Channel
        The created gRPC channel

    """
    if not _IS_WINDOWS:
        raise ValueError("Windows Named User Authentication (WNUA) is only supported on Windows.")
    if host not in LOOPBACK_HOSTS:
        raise ValueError("Remote host connections are not supported with WNUA.")

    target = f"{host}:{port}"
    # Set default authority to "localhost" for WNUA connection
    # This is needed to avoid issues with some gRPC implementations,
    # see https://github.com/grpc/grpc/issues/34305
    options: list[tuple[str, object]] = [
        ("grpc.default_authority", "localhost"),
    ]
    if grpc_options:
        options.extend(grpc_options)
    logger.info(f"Connecting using WNUA -> {target}")
    return grpc.insecure_channel(target, options=options)


def create_mtls_channel(
    host: str,
    port: Union[int, str],
    certs_dir: Optional[str] = None,
    grpc_options: Optional[list[tuple[str, object]]] = None,
) -> grpc.Channel:
    """Create a gRPC channel using Mutual TLS (mTLS).

    Parameters
    ----------
    host : str
        Hostname or IP address of the server.
    port : int | str
        Port in which the server is running.
    certs_dir : str | None
        Directory to use for TLS certificates.
        By default `None` and thus search for the "ANSYS_GRPC_CERTIFICATES" environment variable.
        If not found, it will use the "certs" folder assuming it is in the current working
        directory.
    grpc_options: list[tuple[str, object]] | None
        gRPC channel options to pass when creating the channel.
        Each option is a tuple of the form ("option_name", value).
        By default `None` and thus no extra options are added.

    Returns
    -------
    grpc.Channel
        The created gRPC channel

    """
    # Determine certificates folder
    if certs_dir:
        certs_folder = Path(certs_dir)
    elif os.environ.get("ANSYS_GRPC_CERTIFICATES"):
        certs_folder = Path(cast(str, os.environ.get("ANSYS_GRPC_CERTIFICATES")))
    else:
        certs_folder = Path("certs")

    # Load certificates
    try:
        with (certs_folder / "ca.crt").open("rb") as f:
            trusted_certs = f.read()
        with (certs_folder / "client.crt").open("rb") as f:
            client_cert = f.read()
        with (certs_folder / "client.key").open("rb") as f:
            client_key = f.read()
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Certificate file not found: {e.filename}. "
            f"Ensure that the certificates are present in the '{certs_folder}' folder or "
            "set the 'ANSYS_GRPC_CERTIFICATES' environment variable."
        ) from e

    # Create SSL credentials
    credentials = grpc.ssl_channel_credentials(
        root_certificates=trusted_certs, private_key=client_key, certificate_chain=client_cert
    )

    target = f"{host}:{port}"
    logger.info(f"Connecting using mTLS -> {target}")
    return grpc.secure_channel(target, credentials, options=grpc_options)


def version_tuple(version_str: str) -> tuple[int, ...]:
    """Convert a version string into a tuple of integers for comparison.

    Parameters
    ----------
    version_str : str
        The version string to convert.

    Returns
    -------
    tuple[int, ...]
        A tuple of integers representing the version.

    """
    return tuple(int(x) for x in version_str.split("."))


def check_grpc_version():
    """Check if the installed gRPC version meets the minimum requirement.

    Returns
    -------
    bool
        True if the gRPC version is sufficient, False otherwise.

    """
    min_version = "1.63.0"
    current_version = grpc.__version__

    try:
        return version_tuple(current_version) >= version_tuple(min_version)
    except ValueError:
        logger.warning("Unable to parse gRPC version.")
        return False


def is_uds_supported():
    """Check if Unix Domain Sockets (UDS) are supported on the current platform.

    Returns
    -------
    bool
        True if UDS is supported, False otherwise.

    """
    is_grpc_version_ok = check_grpc_version()
    return is_grpc_version_ok if _IS_WINDOWS else True
