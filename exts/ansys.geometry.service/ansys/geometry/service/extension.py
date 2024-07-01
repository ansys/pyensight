import logging
from typing import Any

import carb.settings
import omni.ext
import omni.kit.pipapi
import omni.client
from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdShade

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

    @classmethod
    def setting(cls, name: str) -> str:
        settings = carb.settings.get_settings()
        ext_name = __name__.rsplit(".", 1)[0]
        s = f"/exts/{ext_name}/{name}"
        return str(settings.get(s))

    def info(self, text: str) -> None:
        self._logger.info(text)

    def error(self, text: str) -> None:
        self._logger.error(text)

    def on_startup(self, ext_id: str) -> None:
        self.info(f"ANSYS geometry service server startup: {ext_id}")

    def on_shutdown(self) -> None:
        self.info("ANSYS geometry service server shutdown")
