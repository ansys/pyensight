import logging
from typing import Any, Optional
from urllib.parse import urlparse

import ansys.geometry.service
import omni.ext
import omni.ui as ui


class AnsysGeometryServiceUIExtension(omni.ext.IExt):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._window: Any = None
        self._label_w: Any = None
        self._logger = logging.getLogger(__name__.rsplit(".", 1)[0])
        self._grpc = None
        self._dsg_uri_w = None
        self._dsg_token_w = None
        self._omni_uri_w = None
        self._temporal_w = None
        self._vrmode_w = None
        self._normalize_w = None
        self._time_scale_w = None
        self._connect_w = None
        self._update_w = None
        self._connected = False

    @property
    def service(self) -> Optional["AnsysGeometryServiceUIExtension"]:
        return ansys.geometry.service.AnsysGeometryServiceServerExtension.get_instance()

    def info(self, text: str) -> None:
        self._logger.info(text)

    def warning(self, text: str) -> None:
        self._logger.warning(text)

    def error(self, text: str) -> None:
        self._logger.error(text)

    def launch_server(self) -> None:
        if self.service.is_server_running():
            return
        self.service.dsg_uri = self._dsg_uri_w.model.as_string
        self.service.security_token = self._dsg_token_w.model.as_string
        self.service.omni_uri = self._omni_uri_w.model.as_string
        self.service.temporal = self._temporal_w.model.as_bool
        self.service.vrmode = self._vrmode_w.model.as_bool
        self.service.normalize_geometry = self._normalize_w.model.as_bool
        scale = self._time_scale_w.model.as_float
        if scale <= 0.0:
            scale = 1.0
        self.service.time_scale = scale
        self.service.launch_server()
        if not self.service.is_server_running():
            self.error("Failed to launch omniverse service.")
            return

        # parse the DSG USI
        parsed = urlparse(self.service.dsg_uri)
        port = parsed.port
        host = parsed.hostname

        # make a direct grpc connection to the DSG server
        from ansys.pyensight.core import ensight_grpc  # pylint: disable=import-outside-toplevel

        self._grpc = ensight_grpc.EnSightGRPC(
            host=host, port=port, secret_key=self.service.security_token
        )
        self._grpc.connect()
        if not self._grpc.is_connected():
            self.error(f"Failed to connect to DSG service {host}:{port}")
            return

        self.info("Connected to DSG service")
        self._connected = True

    def stop_server(self) -> None:
        if not self._connected:
            return
        self.service.stop_server()
        self._grpc.shutdown()
        self._grpc = None

        self.info("Disconnect from DSG service")
        self._connected = False

    def connect_cb(self) -> None:
        if self.service is None:
            self.error("Unable to find ansys.geometry.service instance")
            return
        if self._connected:
            self.stop_server()
        else:
            self.launch_server()
        self.update_ui()

    def update_cb(self) -> None:
        if not self._connected:
            self.error("No DSG service connected")
            return
        self._grpc.command("import enspyqtgui_int", do_eval=False)
        update_cmd = "dynamicscenegraph://localhost/client/update"
        if self._temporal_w.model.as_bool:
            update_cmd += "?timesteps=1"
        cmd = f'enspyqtgui_int.dynamic_scene_graph_command("{update_cmd}")'
        self._grpc.command(cmd, do_eval=False)

    def on_startup(self, ext_id: str) -> None:
        self.info(f"ANSYS geometry service GUI startup: {ext_id}")
        if self.service is None:
            self.error("Unable to find ansys.geometry.service instance")
        self.build_ui()
        self.update_ui()

    def update_ui(self) -> None:
        if self._connected:
            self._connect_w.text = "Disconnect from DSG Server"
            self._label_w.text = f"Connected to: {self.service.dsg_uri}"
        else:
            self._connect_w.text = "Connect to DSG Server"
            self._label_w.text = "No connected DSG server"
        self._update_w.enabled = self._connected
        self._temporal_w.enabled = True
        self._vrmode_w.enabled = not self._connected
        self._normalize_w.enabled = not self._connected
        self._time_scale_w.enabled = not self._connected
        self._dsg_uri_w.enabled = not self._connected
        self._dsg_token_w.enabled = not self._connected
        self._omni_uri_w.enabled = not self._connected

    def build_ui(self) -> None:
        self._window = ui.Window("ANSYS Geometry Service")
        with self._window.frame:
            with ui.VStack(height=0, spacing=5):
                self._label_w = ui.Label("No connected DSG server")

                with ui.HStack(spacing=5):
                    ui.Label("DSG Service URI:", alignment=ui.Alignment.RIGHT_CENTER, width=0)
                    self._dsg_uri_w = ui.StringField()
                    self._dsg_uri_w.model.as_string = self.service.dsg_uri

                with ui.HStack(spacing=5):
                    ui.Label("DSG security code:", alignment=ui.Alignment.RIGHT_CENTER, width=0)
                    self._dsg_token_w = ui.StringField(password_mode=True)
                    self._dsg_token_w.model.as_string = self.service.security_token

                with ui.HStack(spacing=5):
                    ui.Label("Omniverse URI:", alignment=ui.Alignment.RIGHT_CENTER, width=0)
                    self._omni_uri_w = ui.StringField()
                    self._omni_uri_w.model.as_string = self.service.omni_uri

                with ui.HStack(spacing=5):
                    with ui.HStack(spacing=5):
                        self._temporal_w = ui.CheckBox(width=0)
                        self._temporal_w.model.set_value(self.service.temporal)
                        ui.Label("Temporal", alignment=ui.Alignment.LEFT_CENTER)

                    with ui.HStack(spacing=5):
                        self._vrmode_w = ui.CheckBox(width=0)
                        self._vrmode_w.model.set_value(self.service.vrmode)
                        ui.Label("VR Mode", alignment=ui.Alignment.LEFT_CENTER)

                    with ui.HStack(spacing=5):
                        self._normalize_w = ui.CheckBox(width=0)
                        self._normalize_w.model.set_value(self.service.normalize_geometry)
                        ui.Label("Normalize", alignment=ui.Alignment.LEFT_CENTER)

                with ui.HStack(spacing=5):
                    ui.Label(
                        "Temporal scaling factor:", alignment=ui.Alignment.RIGHT_CENTER, width=0
                    )
                    self._time_scale_w = ui.FloatField()
                    self._time_scale_w.model.as_float = self.service.time_scale

                with ui.HStack():
                    self._connect_w = ui.Button("Connect to DSG Server", clicked_fn=self.connect_cb)
                    self._update_w = ui.Button("Request Update", clicked_fn=self.update_cb)

    def on_shutdown(self) -> None:
        self.info("ANSYS geometry service shutdown")
        self.stop_server()
        self._window = None
        self._label_w = None
        self._dsg_uri_w = None
        self._dsg_token_w = None
        self._omni_uri_w = None
        self._temporal_w = None
        self._vrmode_w = None
        self._normalize_w = None
        self._time_scale_w = None
        self._connect_w = None
        self._update_w = None
