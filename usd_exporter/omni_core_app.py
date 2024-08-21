import os
import sys

if getattr(sys, "frozen", False):
    os.environ["OMNI_KIT_ACCEPT_EULA"] = "yes"

import argparse
import logging
from typing import Optional
from urllib.parse import urlparse

from omni.kit_app import KitApp


class AnsysToolsOmniverseCoreServerExtension:
    """
    This class is an Omniverse kit.  The kit is capable of creating a
    connection to an Ansys Distributed Scene Graph service and pushing
    the graph into an Omniverse Nucleus.
    """

    _service_instance = None

    def __init__(
        self,
        app=None,
        dsg_uri=None,
        omni_uri=None,
        security_token=None,
        temporal=False,
        vrmode=False,
        timescale=1.0,
        normalize_geometry=False,
    ) -> None:
        ext_name = __name__.rsplit(".", 1)[0]
        self._app = app
        self._logger = logging.getLogger(ext_name)
        self._dsg_uri = dsg_uri
        self._omni_uri = omni_uri
        self._security_token = security_token
        self._temporal = temporal
        self._vrmode = vrmode
        self._time_scale = timescale
        self._normalize_geometry = normalize_geometry
        self._version = "unknown"
        self._shutdown = False

    @property
    def dsg_uri(self) -> str:
        """The endpoint of a Dynamic Scene Graph service:  grpc://{hostname}:{port}"""
        return self._dsg_uri

    @dsg_uri.setter
    def dsg_uri(self, uri: str) -> None:
        self._dsg_uri = uri

    @property
    def omni_uri(self) -> str:
        """The endpoint of an Omniverse Nucleus service:  omniverse://{hostname}/{path}"""
        return self._omni_uri

    @omni_uri.setter
    def omni_uri(self, value: str) -> None:
        self._omni_uri = value

    @property
    def security_token(self) -> str:
        """The security token of the DSG service instance."""
        return self._security_token

    @security_token.setter
    def security_token(self, value: str) -> None:
        self._security_token = value

    @property
    def temporal(self) -> bool:
        """If True, the DSG update should include all timesteps."""
        return self._temporal

    @temporal.setter
    def temporal(self, value: bool) -> None:
        self._temporal = bool(value)

    @property
    def vrmode(self) -> bool:
        """If True, the DSG update should not include camera transforms."""
        return self._vrmode

    @vrmode.setter
    def vrmode(self, value: bool) -> None:
        self._vrmode = bool(value)

    @property
    def normalize_geometry(self) -> bool:
        """If True, the DSG geometry should be remapped into normalized space."""
        return self._normalize_geometry

    @normalize_geometry.setter
    def normalize_geometry(self, val: bool) -> None:
        self._normalize_geometry = val

    @property
    def time_scale(self) -> float:
        """Value to multiply DSG time values by before passing to Omniverse"""
        return self._time_scale

    @time_scale.setter
    def time_scale(self, value: float) -> None:
        self._time_scale = value

    @classmethod
    def get_instance(cls) -> Optional["AnsysToolsOmniverseCoreServerExtension"]:
        return cls._service_instance

    def info(self, text: str) -> None:
        """
        Send message to the logger at the info level.

        Parameters
        ----------
        text
            The message to send.
        """
        self._logger.info(text)

    def warning(self, text: str) -> None:
        """
        Send message to the logger at the warning level.

        Parameters
        ----------
        text
            The message to send.
        """
        self._logger.warning(text)

    def error(self, text: str) -> None:
        """
        Send message to the logger at the error level.

        Parameters
        ----------
        text
            The message to send.
        """
        self._logger.error(text)

    def on_startup(self) -> None:
        """
        Called by Omniverse when the kit instance is started.

        Parameters
        ----------
        ext_id
            The specific version of the kit.
        """
        AnsysToolsOmniverseCoreServerExtension._service_instance = self
        self.run_server()

    def on_shutdown(self) -> None:
        """
        Called by Omniverse when the kit instance is shutting down.
        """
        self.info("ANSYS tools omniverse core server shutdown")
        self._app.shutdown()
        AnsysToolsOmniverseCoreServerExtension._service_instance = None

    def run_server(self) -> None:
        """
        Run a DSG to Omniverse server in process.

        Note: this method does not return until the DSG connection is dropped or
        self.stop_server() has been called.
        """
        import ansys.pyensight.core.utils.dsg_server as dsg_server  # noqa: E402
        import ansys.pyensight.core.utils.omniverse_dsg_server as ov_dsg_server  # noqa: E402

        # Build the Omniverse connection
        omni_link = ov_dsg_server.OmniverseWrapper(path=self._omni_uri, verbose=1)
        self.info("Omniverse connection established.")

        # parse the DSG USI
        parsed = urlparse(self.dsg_uri)
        port = parsed.port
        host = parsed.hostname

        # link it to a DSG session
        update_handler = ov_dsg_server.OmniverseUpdateHandler(omni_link)
        dsg_link = dsg_server.DSGSession(
            port=port,
            host=host,
            vrmode=self.vrmode,
            security_code=self.security_token,
            verbose=1,
            normalize_geometry=self.normalize_geometry,
            time_scale=self.time_scale,
            handler=update_handler,
        )

        # Start the DSG link
        self.info(f"Making DSG connection to: {self.dsg_uri}")
        err = dsg_link.start()
        if err < 0:
            self.error("Omniverse connection failed.")
            return

        # Initial pull request
        dsg_link.request_an_update(animation=self.temporal)

        # until the link is dropped, continue
        while not dsg_link.is_shutdown() and not self._shutdown:
            dsg_link.handle_one_update()

        self.info("Shutting down DSG connection")
        dsg_link.end()
        omni_link.shutdown()


def visualize_in_omniverse(kit_app: str, on_startup):
    app = KitApp()
    app.startup([kit_app] + sys.argv[1:])
    on_startup(app=app)

    while app.is_running():
        app.update()
    sys.exit(app.shutdown())


def parser():
    parser = argparse.ArgumentParser("Extension parser")
    parser.add_argument("--secret-key", type=str)
    parser.add_argument("--grpc-port", type=int)
    parser.add_argument("--omni-uri", type=str)
    parser.add_argument("--temporal", action="store_true", default=False)
    parser.add_argument("--vr-mode", action="store_true", default=False)
    parser.add_argument("--normalize-geometry", action="store_true", default=False)
    parser.add_argument("--time-scale", type=float, default=1.0)
    return parser


def launch_server(service, args) -> None:
    service.dsg_uri = f"http://127.0.0.1:{args.grpc_port}"
    service.security_token = args.secret_key
    service.omni_uri = args.omni_uri
    service.temporal = args.temporal
    service.vrmode = args.vr_mode
    service.normalize_geometry = args.normalize_geometry
    scale = args.time_scale
    if scale <= 0.0:
        scale = 1.0
    service.time_scale = scale
    parsed = urlparse(service.dsg_uri)
    port = parsed.port
    host = parsed.hostname

    # make a direct grpc connection to the DSG server
    from ansys.pyensight.core import ensight_grpc  # pylint: disable=import-outside-toplevel

    _grpc = ensight_grpc.EnSightGRPC(host=host, port=port, secret_key=service.security_token)
    _grpc.connect()
    if not _grpc.is_connected():
        print(f"Failed to connect to DSG service {host}:{port}")
        return

    print("Connected to DSG service")


def main(args):
    def on_startup(app=None):
        """
        Generate USD content directly in the Kit runtime USD stage
        """
        instance = AnsysToolsOmniverseCoreServerExtension(app=app)
        launch_server(instance, args)
        instance.on_startup()

    if getattr(sys, "frozen", False):
        root_path = sys._MEIPASS
    else:
        root_path = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
    visualize_in_omniverse(os.path.join(root_path, "omni.ansys.tools.core.kit"), on_startup)


if __name__ == "__main__":
    args = sys.argv[1:]
    _parser = parser()
    _args = _parser.parse_args(args)
    main(_args)
