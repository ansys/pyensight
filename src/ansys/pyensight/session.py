"""Session module

The Session module allows pyensight to control the EnSight session

Examples
--------
>>> from ansys.pyensight import Launcher
>>> session = Launcher.launch_session()
>>> type(session)
ansys.pyensight.Session

"""


class Session:
    """Class to access EnSight session

    An EnSight session is connected to each Session instance
    The Launcher class returns a Session instance when connected to
    a running EnSight

    Examples
    --------

    >>> from ansys.pyensight import Launcher
    >>> session = Launcher.launch_session(ansys_installation = '/opt/ansys_inc/v222')

    """

    def __init__(self):
        """Initialize a Session object

        Parameters
        ----------
        param1 : str
            The first parameter.
        param2 : str
            The second parameter.

        Returns
        -------
        bool
            True if successful, False otherwise.

        Notes
        -----
        Do not include the `self` parameter in the ``Parameters`` section.

        Examples
        --------
        >>> from ansys.pyensight import Launcher
        >>> session = Launcher.launch_session()

        """
        return None

    def dummy_method(self):
        """Useless dummy method for now

        Parameters
        ----------
        param1 : str
            The first parameter.
        param2 : str
            The second parameter.

        Returns
        -------
        bool
            True if successful, False otherwise.

        Notes
        -----
        Do not include the `self` parameter in the ``Parameters`` section.
        """
        return True
