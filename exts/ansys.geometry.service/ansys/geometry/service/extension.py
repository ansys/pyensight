import logging

import carb.settings
import omni.ext
import omni.kit.pipapi
# import omni.client
# from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdShade

try:
    import ansys.pyensight.core
except ModuleNotFoundError:
    omni.kit.pipapi.install("ansys-pyensight-core")


class AnsysGeometryServiceServerExtension(omni.ext.IExt):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        ext_name = __name__.rsplit(".", 1)[0]
        self._logger = logging.getLogger(ext_name)
        self._dsg_uri = self.setting("dsgUrl")
        self._omni_uri = self.setting("omniUrl")
        self._security_token = self.setting("securityCode")
        self._temporal = self.setting("temporal") != "0"
        self._vrmode = self.setting("vrmode") != "0"
        self._normalizeGeometry = self.setting("normalizeGeometry") != "0"
        self._version = "unknown"
        self._thread = None

    @classmethod
    def setting(cls, name: str) -> str:
        settings = carb.settings.get_settings()
        ext_name = __name__.rsplit(".", 1)[0]
        s = f"/exts/{ext_name}/{name}"
        return str(settings.get(s))

    def info(self, text: str) -> None:
        self._logger.info(text)

    def warning(self, text: str) -> None:
        self._logger.warning(text)

    def error(self, text: str) -> None:
        self._logger.error(text)

    def on_startup(self, ext_id: str) -> None:
        self._version = ext_id
        self.info(f"ANSYS geometry service server startup: {self._version}")
        if self.setting("help"):
            self.help()
        elif self.setting("run"):
            self.launch_server()

    def on_shutdown(self) -> None:
        self.info("ANSYS geometry service server shutdown")
        if self._thread:
            pass

    def help(self):
        self.info(f"ANSYS Omniverse Geometry Service: {self._version}")
        self.info("  --/exts/ansys.geometry.service/omniUrl URL")
        self.info("    Omniverse pathname (default: omniverse://localhost/Users/test )")
        self.info("  --/exts/ansys.geometry.service/dsgUrl URL")
        self.info("    Dynamic Scene Graph connection URL.  (default: grpc://127.0.0.1:12345 )")
        self.info("  --/exts/ansys.geometry.service/securityCode TOKEN")
        self.info("    Dynamic Scene Graph security token.  (default: '' )")
        self.info("  --/exts/ansys.geometry.service/temporal 0|1")
        self.info("    If non-zero, include all timeseteps in the scene.  (default: 0 )")
        self.info("  --/exts/ansys.geometry.service/vrmode 0|1")
        self.info("    If non-zero, do not include a camera in the scene.  (default: 0 )")
        self.info("  --/exts/ansys.geometry.service/normalizeGeometry 0|1")
        self.info("    If non-zero, remap the geometry to the domain [-1,-1,-1]-[1,1,1].  (default: 0 )")

    def launch_server(self, thread=False):
        pass
