from types import ModuleType
from typing import Optional, Union

try:
    import ensight
except ImportError:
    from ansys.api.pyensight import ensight_api


class Adr:
    """Provides the ``ensight.utils.adr`` interface.

    The methods in this class implement simplified interfaces connect EnSight
    to an existing ADR report.
    With connect_to_existing_adr_report() the connection is done, while with
    generate_adr_report() the report is generated.

    Parameters
    ----------
    interface :
        Entity that provides the ``ensight`` namespace. In the case of
        EnSight Python, the ``ensight`` module is passed. In the case
        of PyEnSight, ``Session.ensight`` is passed.
    """

    def __init__(self, interface: Union["ensight_api.ensight", "ensight"]):
        self._ensight = interface
        self._adr_report_connected = False
        self._url: Optional[str] = None

    def connect_to_existing_adr_report(
        self, url: str, username: str = "nexus", password: str = "cei"
    ) -> None:
        """Connect to an existing ADR report

        Parameters
        ----------
        url: string
            the url of the ADR report
        username: string
            the username to connect to the ADR report
        password: string
            the password to connect to the ADR report
        """
        ret = None
        if self._adr_report_connected is True:
            raise RuntimeError(
                f"The PyEnSight session is already connected to the ADR server {self._url}."
            )
        if isinstance(self._ensight, ModuleType):
            self._ensight.core.nexus.ReportServer.get_server().set_URL(url)
            self._ensight.core.nexus.ReportServer.get_server().set_username(username)
            self._ensight.core.nexus.ReportServer.get_server().set_password(password)
            ret = self._ensight.core.nexus.ReportServer.get_server().validate() == 1.0
        else:
            self._ensight._session.cmd(
                f"ensight.core.nexus.ReportServer.get_server().set_URL('{url}')"
            )
            self._ensight._session.cmd(
                f"ensight.core.nexus.ReportServer.get_server().set_username('{username}')"
            )
            self._ensight._session.cmd(
                f"ensight.core.nexus.ReportServer.get_server().set_password('{password}')"
            )
            ret = self._ensight._session.cmd(
                "ensight.core.nexus.ReportServer.get_server().validate() == 1.0"
            )
        if ret is True:
            self._adr_report_connected = True
            self._url = url
        else:
            raise RuntimeError("Couldn't connect to the ADR report server.")

    def generate_adr_report(self):
        """Generate the ADR report with the current states."""
        if self._adr_report_connected is False:
            raise RuntimeError(
                "No ADR report is connected to the PyEnSight session. Please generated one and connect with connect_to_existing_adr_report()"
            )
        if len(self._ensight.objs.core.STATES) > 0:
            self._ensight.objs.core.STATES[0].generate_report()
        else:
            raise RuntimeError("No states are available to generate the report with.")

    def is_connected_to_adr_report(self):
        """True if the PyEnSight session is already connected to an ADR report server."""
        if self._adr_report_connected is True:
            print(f"The PyEnSight session is connected to the ADR report server {self._url}")
        return self._adr_report_connected
