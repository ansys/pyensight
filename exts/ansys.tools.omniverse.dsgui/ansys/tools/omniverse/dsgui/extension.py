import logging
import threading
import time
from typing import Any, Optional

import ansys.tools.omniverse.core
import omni.ext
import omni.ui as ui


class AnsysToolsOmniverseDSGUIExtension(omni.ext.IExt):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._window: Any = None
        self._label_w: Any = None
        self._logger = logging.getLogger(__name__.rsplit(".", 1)[0])
        self._grpc = None
        self._dsg_uri_w = None
        self._dsg_token_w = None
        self._interpreter_w = None
        self._destination_w = None
        self._temporal_w = None
        self._vrmode_w = None
        self._normalize_w = None
        self._time_scale_w = None
        self._connect_w = None
        self._update_w = None
        self._connected = False
        self._error_msg = ""

    @property
    def service(self) -> Optional["AnsysToolsOmniverseDSGUIExtension"]:
        return ansys.tools.omniverse.core.AnsysToolsOmniverseCoreServerExtension.get_instance()

    def info(self, text: str) -> None:
        self._logger.info(text)

    def warning(self, text: str) -> None:
        self._logger.warning(text)

    def error(self, text: str) -> None:
        self._logger.error(text)

    def start_server(self) -> None:
        if self._connected:
            return
        self.service.dsg_uri = self._dsg_uri_w.model.as_string
        self.service.security_token = self._dsg_token_w.model.as_string
        self.service.interpreter = self._interpreter_w.model.as_string
        self.service.destination = self._destination_w.model.as_string
        self.service.temporal = self._temporal_w.model.as_bool
        self.service.vrmode = self._vrmode_w.model.as_bool
        self.service.normalize_geometry = self._normalize_w.model.as_bool
        scale = self._time_scale_w.model.as_float
        if scale <= 0.0:
            scale = 1.0
        self.service.time_scale = scale
        self.info("Connected to DSG service")
        self._connected = True

    def stop_server(self) -> None:
        if not self._connected:
            return
        self.info("Disconnect from DSG service")
        self._connected = False

    def connect_cb(self) -> None:
        if self.service is None:
            self.error("Unable to find ansys.tools.omniverse.core instance")
            return
        if self._connected:
            self.stop_server()
        else:
            pypath = self._interpreter_w.model.as_string
            if not self.service.validate_interpreter(pypath):
                self._error_msg = ".  Invalid Python path."
            else:
                self._error_msg = ""
                self.start_server()
        self.update_ui()

    def update_cb(self) -> None:
        if not self._connected:
            self.error("No DSG service connected")
            return
        self.service.dsg_export()

    def on_startup(self, ext_id: str) -> None:
        self.info(f"ANSYS tools omniverse DSG GUI startup: {ext_id}")
        if self.service is None:
            self.error("Unable to find ansys.tools.omniverse.core instance")
        self.build_ui()
        self._update_callback()

    def _update_callback(self) -> None:
        self.update_ui()
        threading.Timer(0.5, self._update_callback).start()

    def update_ui(self) -> None:
        status = self.service.read_status_file()
        if self._connected:
            self._connect_w.text = "Disconnect from DSG Server"
            tmp = f"Connected to: {self.service.dsg_uri}"
            if status.get("status", "idle") == "working":
                count = status.get("processed_buffers", 0)
                total = status.get("total_buffers", 0)
                dt = time.time() - status.get("start_time", 0.0)
                percent = 0
                if total > 0:
                    percent = int((count / total) * 100)
                tmp = f"Transfer: {percent}% : {dt:.2f}s"
            self._label_w.text = tmp
        else:
            self._connect_w.text = "Connect to DSG Server"
            self._label_w.text = "No connected DSG server" + self._error_msg
        self._update_w.enabled = self._connected and (status.get("status", "idle") == "idle")
        self._connect_w.enabled = status.get("status", "idle") == "idle"
        self._temporal_w.enabled = True
        self._vrmode_w.enabled = not self._connected
        self._normalize_w.enabled = not self._connected
        self._time_scale_w.enabled = not self._connected
        self._dsg_uri_w.enabled = not self._connected
        self._dsg_token_w.enabled = not self._connected
        self._interpreter_w.enabled = not self._connected
        self._destination_w.enabled = not self._connected

    def build_ui(self) -> None:
        self._window = ui.Window(f"ANSYS Tools Omniverse DSG ({self.service.version})")
        with self._window.frame:
            with ui.VStack(height=0, spacing=5):
                self._label_w = ui.Label("No connected DSG server" + self._error_msg)

                with ui.HStack(spacing=5):
                    ui.Label(
                        "DSG Service URI:",
                        alignment=ui.Alignment.RIGHT_CENTER,
                        width=0,
                    )
                    self._dsg_uri_w = ui.StringField()
                    self._dsg_uri_w.model.as_string = self.service.dsg_uri

                with ui.HStack(spacing=5):
                    ui.Label(
                        "DSG security code:",
                        alignment=ui.Alignment.RIGHT_CENTER,
                        width=0,
                    )
                    self._dsg_token_w = ui.StringField(password_mode=True)
                    self._dsg_token_w.model.as_string = self.service.security_token

                with ui.HStack(spacing=5):
                    ui.Label(
                        "Python path:",
                        alignment=ui.Alignment.RIGHT_CENTER,
                        width=0,
                    )
                    self._interpreter_w = ui.StringField()
                    self._interpreter_w.model.as_string = str(self.service.interpreter)

                with ui.HStack(spacing=5):
                    ui.Label(
                        "Export directory:",
                        alignment=ui.Alignment.RIGHT_CENTER,
                        width=0,
                    )
                    self._destination_w = ui.StringField()
                    self._destination_w.model.as_string = self.service.destination

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
                        "Temporal scaling factor:",
                        alignment=ui.Alignment.RIGHT_CENTER,
                        width=0,
                    )
                    self._time_scale_w = ui.FloatField()
                    self._time_scale_w.model.as_float = self.service.time_scale

                with ui.HStack():
                    self._connect_w = ui.Button("Connect to DSG Server", clicked_fn=self.connect_cb)
                    self._update_w = ui.Button("Request Update", clicked_fn=self.update_cb)

    def on_shutdown(self) -> None:
        self.info("ANSYS Tools Omniverse DSG shutdown")
        self.stop_server()
        self._window = None
        self._label_w = None
        self._dsg_uri_w = None
        self._dsg_token_w = None
        self._interpreter_w = None
        self._destination_w = None
        self._temporal_w = None
        self._vrmode_w = None
        self._normalize_w = None
        self._time_scale_w = None
        self._connect_w = None
        self._update_w = None
