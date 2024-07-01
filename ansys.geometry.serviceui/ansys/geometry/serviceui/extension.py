import logging
from typing import Any


import omni.ext
import omni.ui as ui
import ansys.geometry.service


class AnsysGeometryServiceUIExtension(omni.ext.IExt):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._window: Any = None
        self._label_w: Any = None
        self._logger = logging.getLogger(__name__.rsplit(".", 1)[0])
        self._dsg_uri_w = None
        self._dsg_token_w = None
        self._omni_uri_w = None
        self._temporal_w = None
        self._vrmode_w = None
        self._connect_w = None
        self._update_w = None
        self._connected = False

    @classmethod
    def setting(cls, name: str) -> str:
        return ansys.geometry.service.AnsysGeometryServiceServerExtension.setting(name)

    def info(self, text: str) -> None:
        self._logger.info(text)

    def error(self, text: str) -> None:
        self._logger.error(text)

    def connect_cb(self) -> None:
        self.error("Connect")

    def update_cb(self) -> None:
        self.error("Update")

    def on_startup(self, ext_id: str) -> None:
        self.info(f"ANSYS geometry service GUI startup: {ext_id}")
        self.build_ui()
        self.update_ui()

    def update_ui(self) -> None:
        if self._connected:
            self._connect_w.text = "Disconnect from DSG Server"
        else:
            self._connect_w.text = "Connect to DSG Server"
        self._update_w.enabled = self._connected
        self._temporal_w.enabled = self._connected
        self._vrmode_w.enabled = self._connected
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
                    self._dsg_uri_w.model.as_string = self.setting("dsgUrl")

                with ui.HStack(spacing=5):
                    ui.Label("DSG security code:", alignment=ui.Alignment.RIGHT_CENTER, width=0)
                    self._dsg_token_w = ui.StringField(password_mode=True)
                    self._dsg_token_w.model.as_string = self.setting("securityCode")

                with ui.HStack(spacing=5):
                    ui.Label("Omniverse URI:", alignment=ui.Alignment.RIGHT_CENTER, width=0)
                    self._omni_uri_w = ui.StringField()
                    self._omni_uri_w.model.as_string = self.setting("omniUrl")

                with ui.HStack(spacing=5):
                    with ui.HStack(spacing=5):
                        self._temporal_w = ui.CheckBox(width=0)
                        ui.Label("Temporal", alignment=ui.Alignment.LEFT_CENTER)

                    with ui.HStack(spacing=5):
                        self._vrmode_w = ui.CheckBox(width=0)
                        ui.Label("VR Mode", alignment=ui.Alignment.LEFT_CENTER)

                with ui.HStack():
                    self._connect_w = ui.Button("Connect to DSG Server", clicked_fn=self.connect_cb)
                    self._update_w = ui.Button("Request Update", clicked_fn=self.update_cb)

    def on_shutdown(self) -> None:
        self.info("ANSYS geometry service shutdown")
        self._window = None
        self._label_w = None
        self._dsg_uri_w = None
        self._dsg_token_w = None
        self._omni_uri_w = None
        self._temporal_w = None
        self._vrmode_w = None
        self._connect_w = None
        self._update_w = None
