"""Launcher module

The Launcher module allows pyensight to control the enshell launcher
capabilities to launch EnSight in multiple configurations, and to
connect to an existing EnSight session

Examples
--------
>>> from ansys.pyensight import Launcher
>>> session = Launcher.launch_session()

"""


class Launcher:
    """Class to access EnSight Launcher

    The Launcher instance allows the user to launch an EnSight session
    or to connect to an existing one

    Examples
    --------

    >>> from ansys.pyensight import Launcher
    >>> session = Launcher.launch_session(ansys_installation = '/opt/ansys_inc/v222')

    """

    def __init__(self):
        """Initialize a Launcher object

        Parameters
        ----------
        session : pyensight.Session
            If connected, an EnSight session. None otherwise
        param1 : str
            The first parameter.
        param2 : str
            The second parameter.

        Notes
        -----
        Do not include the `self` parameter in the ``Parameters`` section.

        Examples
        --------
        >>> from ansys.pyensight import Launcher
        >>> example = Launcher()
        obj

        """
        self.session = None
        return None

    def launch_session(self, ansys_installation=r"C:\Program Files\ANSYS Inc\v222"):
        """Initialize a Launcher object

        Parameters
        ----------
        ansys_installation: str
            Location of the ANSYS installation, including the version directory
            Default:  C:\\Program Files\\ANSYS Inc\\v222

        Returns
        -------
        pyensight.Session
            pyensight Session object

        """
        if self.session is None:
            from ansys.pyensight import Session

            self.session = Session()
        return self.session

    def close(self):
        """Close the EnSight session that is connected to this Launcher instance

        Returns
        -------
        bool
            True is successful, False otherwise
        """
        return True
