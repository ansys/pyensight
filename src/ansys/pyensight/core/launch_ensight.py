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

pim_is_available = False
try:
    import ansys.platform.instancemanagement as pypim

    pim_is_available = True
except Exception:
    pass
logging.debug(f"pim_is_available: {pim_is_available}\n")

docker_is_available = False
try:
    from ansys.pyensight.core.dockerlauncher import DockerLauncher

    docker_is_available = True
except Exception:
    pass
logging.debug(f"docker_is_available: {docker_is_available}\n")


if pim_is_available:

    def _launch_ensight_with_pim(
        product_version: Optional[str] = None,
        **kwargs,
    ) -> "Session":
        """Internal function.
        Start via PyPIM the EnSight Docker container with EnShell as the ENTRYPOINT.
        Create and bind a Session instance to the created gRPC session.  Return that session.

        Parameters
        ----------
        product_version : str, optional
            Version of the product. For example, "232". The default is "None", in which case
        use_egl : bool, optional
            If True, EGL hardware accelerated graphics will be used. The platform
            must be able to support it.
        use_sos : int, optional
            If None, don't use SOS. Otherwise, it's the number of EnSight Servers to use (int).

        Returns
        -------

            pyensight Session object instance

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

        launcher = DockerLauncher(
            channel=channel,
            pim_instance=instance,
        )
        return launcher.connect()


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

    logging.debug(f"pim_is_available: {pim_is_available}  use_pim: {use_pim}\n")
    if pim_is_available and use_pim:
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
    launcher = LocalLauncher(
        ansys_installation=ansys_installation,
        application=application,
        batch=batch,
        **kwargs,
    )
    return launcher.start()
