"""launch_ensight module

The launch_ensight module provides pyensight with the ability to launch an
EnSight session using PyPIM.  This leverages the DockerLauncher module.

Examples
--------
>>> from ansys.pyensight.core import launch_ensight
>>> session = launch_ensight()
>>> # do pyensight stuff with the session
>>> session.close()
"""

import logging
from typing import Optional

from ansys.pyensight.core.locallauncher import LocalLauncher
from ansys.pyensight.core.session import Session

pim_is_available = False  # pragma: no cover
try:
    import ansys.platform.instancemanagement as pypim

    pim_is_available = True  # pragma: no cover
except Exception:  # pragma: no cover
    pass  # pragma: no cover
logging.debug(f"pim_is_available: {pim_is_available}\n")

docker_is_available = False
try:
    from ansys.pyensight.core.dockerlauncher import DockerLauncher

    docker_is_available = True
except Exception:  # pragma: no cover
    pass  # pragma: no cover
logging.debug(f"docker_is_available: {docker_is_available}\n")


if pim_is_available:  # pragma: no cover

    def _prepare_pim(  # pragma: no cover
        product_version: Optional[str] = None,
    ):
        """Create a PIM instance and gRPC channel for the input version of EnSight.

        Parameters
        ----------
        product_version : str, optional
            Version of the product. For example, "232". The default is "None"

        """
        pim = pypim.connect()
        instance = pim.create_instance(
            product_name="ensight",
            product_version=product_version,
        )
        instance.wait_for_ready()
        # use defaults as specified by PIM
        channel = instance.build_grpc_channel(
            options=[
                ("grpc.max_receive_message_length", -1),
                ("grpc.max_send_message_length", -1),
                ("grpc.testing.fixed_reconnect_backoff_ms", 1100),
            ]
        )
        return instance, channel

    def _launch_ensight_with_pim(  # pragma: no cover
        product_version: Optional[str] = None,
        **kwargs,
    ) -> "Session":
        """Internal function.
        Start via PyPIM the EnSight Docker container with EnShell as the ENTRYPOINT.
        Create and bind a Session instance to the created gRPC session.  Return that session.

        Parameters
        ----------
        product_version : str, optional
            Version of the product. For example, "232". The default is "None"
        use_egl : bool, optional
            If True, EGL hardware accelerated graphics will be used. The platform
            must be able to support it.
        use_sos : int, optional
            If None, don't use SOS. Otherwise, it's the number of EnSight Servers to use (int).

        Returns
        -------
        Session
            pyensight Session object instance

        """
        instance, channel = _prepare_pim(product_version=product_version)
        launcher = DockerLauncher(channel=channel, pim_instance=instance, **kwargs)
        return launcher.connect()

    def _launch_libuserd_with_pim(
        product_version: Optional[str] = None, **kwargs
    ):  # pragma: no cover
        from ansys.pyensight.core.libuserd import LibUserd

        instance, channel = _prepare_pim(product_version=product_version)
        libuserd = LibUserd(channel=channel, pim_instance=instance, **kwargs)
        libuserd.initialize()
        return libuserd


def launch_ensight(
    product_version: Optional[str] = None,
    use_pim: bool = True,
    use_docker: bool = True,
    data_directory: Optional[str] = None,
    docker_image_name: Optional[str] = None,
    use_dev: bool = False,
    ansys_installation: Optional[str] = None,
    application: str = "ensight",
    batch: bool = True,
    **kwargs,
) -> "Session":
    """Start an EnSight session via EnShell using the Docker EnSight Image.
    Return that session.

    Parameters
    ----------
    product_version : str, optional
        Select an installed version of ANSYS. The string must be in a format like
        "232" (for 2023 R2). The default is "None", in which case the newest installed
        version is used.
    use_pim : bool, optional
        If True, then PyPIM is used to launch EnSight.
    use_docker : bool, optional
        If True, use DockerLaucher. If use_pim is True, this option is ignored.
    data_directory: str, optional
        Host directory to make into the Docker container at /data
        Only used if use_docker is True.
    docker_image_name: str, optional
        Optional Docker Image name to use
    use_dev: bool, optional
        Option to use the latest ensight_dev Docker Image; overridden by docker_image_name if specified.
    ansys_installation: str, optional
        Location of the ANSYS installation, including the version.
        directory Default: None (causes common locations to be scanned).
        If use_pim is True, this option is ignored.  If use_docker is True, this option is ignored.
    application: str, optional
        The application to be launched. By default, "ensight", but
        "envision" is also available.
    batch: bool, optional
        By default, the EnSight/EnVision instance will run in batch mode.
        If batch is set to False, the full GUI will be presented.
        Only used if use_pim and use_docker are False.
    use_egl: bool, optional
        If True, EGL hardware accelerated graphics will be used. The platform
        must be able to support it.
    use_sos: int, optional
        If None, don't use SOS. Otherwise, it's the number of EnSight Servers to use (int).
    timeout: float, optional
        In some cases where the EnSight session can take a significant amount of
        time to start up, this is the number of seconds to wait before failing
        the connection.  The default is 120.0.

    Returns
    -------
    type
        pyensight Session object instance

    Raises
    ------
    RuntimeError
        variety of error conditions

    """

    logging.debug(f"pim_is_available: {pim_is_available}  use_pim: {use_pim}\n")  # pragma: no cover
    if pim_is_available and use_pim:  # pragma: no cover
        if pypim.is_configured():
            return _launch_ensight_with_pim(product_version=product_version, **kwargs)

    # not using PIM, but use Docker
    logging.debug(f"docker_is_available: {docker_is_available}  use_docker: {use_docker}\n")
    if docker_is_available and use_docker:
        launcher = DockerLauncher(
            data_directory=data_directory,
            docker_image_name=docker_image_name,
            use_dev=use_dev,
            **kwargs,
        )
        return launcher.start()

    # use local installation of EnSight
    launcher = LocalLauncher(  # pragma: no cover
        ansys_installation=ansys_installation,  # pragma: no cover
        application=application,  # pragma: no cover
        batch=batch,  # pragma: no cover
        **kwargs,  # pragma: no cover
    )  # pragma: no cover
    return launcher.start()  # pragma: no cover


def launch_libuserd(  # pragma: no cover
    product_version: Optional[str] = None,
    use_pim: bool = True,
    use_docker: bool = True,
    data_directory: Optional[str] = None,
    docker_image_name: Optional[str] = None,
    use_dev: bool = False,
    ansys_installation: Optional[str] = None,
    timeout: float = 120.0,
    pull_image_if_not_available: bool = False,
):
    """Start an EnSight session via EnShell using the Docker EnSight Image.
    Return that session.

    Parameters
    ----------
    product_version : str, optional
        Select an installed version of ANSYS. The string must be in a format like
        "232" (for 2023 R2). The default is "None", in which case the newest installed
        version is used.
    use_pim : bool, optional
        If True, then PyPIM is used to launch the EnSight image.
    use_docker : bool, optional
        If True, use DockerLaucher. If use_pim is True, this option is ignored.
    data_directory: str, optional
        Host directory to make into the Docker container at /data
        Only used if use_docker is True.
    docker_image_name: str, optional
        Optional Docker Image name to use
    use_dev: bool, optional
        Option to use the latest ensight_dev Docker Image; overridden by docker_image_name if specified.
    ansys_installation: str, optional
        Location of the ANSYS installation, including the version.
        directory Default: None (causes common locations to be scanned).
        If use_pim is True, this option is ignored.  If use_docker is True, this option is ignored.
    application: str, optional
        The application to be launched. By default, "ensight", but
        "envision" is also available.
    timeout: float, optional
        In some cases where the EnSight session can take a significant amount of
        time to start up, this is the number of seconds to wait before failing
        the connection.  The default is 120.0.
    pull_image_if_not_available: bool
        If True, the image will be pulled using Docker. If use_pim is True this option
        is ignored.
    Returns
    -------
    type
        LibUserd object instance

    Raises
    ------
    RuntimeError
        variety of error conditions

    """
    from ansys.pyensight.core.libuserd import LibUserd

    logging.debug(f"pim_is_available: {pim_is_available}  use_pim: {use_pim}\n")  # pragma: no cover
    if pim_is_available and use_pim:  # pragma: no cover
        if pypim.is_configured():
            return _launch_libuserd_with_pim(product_version=product_version, timeout=timeout)
    logging.debug(f"docker_is_available: {docker_is_available}  use_docker: {use_docker}\n")
    if docker_is_available and use_docker:
        libuserd = LibUserd(
            data_directory=data_directory,
            docker_image_name=docker_image_name,
            use_dev=use_dev,
            use_docker=use_docker,
            timeout=timeout,
            pull_image_if_not_available=pull_image_if_not_available,
        )
        libuserd.initialize()
        return libuserd
    libuserd = LibUserd(ansys_installation=ansys_installation, timeout=timeout)
    libuserd.initialize()
    return libuserd
