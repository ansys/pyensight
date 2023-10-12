from typing import TYPE_CHECKING, Any, ContextManager, Union

if TYPE_CHECKING:
    try:
        import ensight
    except ImportError:
        from ansys.api.pyensight import ensight_api


class Support:
    """Provides the ``ensight.utils.support`` interface.

    This class provides a collection of general utility functions and objects
    that can be used to simplify various issues that come up when using EnSight
    and PyEnSight.

    This class is instantiated as ``ensight.utils.support`` in EnSight Python
    and as ``Session.ensight.utils.support`` in PyEnSight. The constructor is
    passed the interface, which serves as the ``ensight`` module for either
    case. As a result, the methods can be accessed as ``ensight.utils.support.*``
    in EnSight Python or ``session.ensight.utils.support.*`` in PyEnSight.

    Parameters
    ----------
    interface :
        Entity that provides the ``ensight`` namespace. In the case of
        EnSight Python, the ``ensight`` module is passed. In the case
        of PyEnSight, ``Session.ensight`` is passed.
    """

    def __init__(self, interface: Union["ensight_api.ensight", "ensight"]):
        self._ensight = interface

    def scoped_name(self, obj: Any, native_exceptions: bool = False) -> ContextManager:
        """Allow for the use of ``with`` to shorten APIs.

        In the EnSight and PyEnsight APIs, the interfaces can become lengthy.
        This class makes it possible to shorten APIs for modules, classes,
        and namespaces.  The native_exceptions keyword can be used to enable
        exceptions for EnSight native Python API.  By default, an invalid
        native API call like ``ensight.part.select_begin(-9999)`` will return
        -1.  If native_exceptions is True, a Python exception will be thrown.
        The scope of this operational change parallels the scoped_name()
        instance.

        Parameters
        ----------
        obj: Any
            The object for which to generate a simplified namespace.
        native_exceptions: bool
            If True, then EnSight native Python API exceptions are enabled.
            The default is False.

        Returns
        -------
        The passed object wrapped in a context manager that can be used as a
        simplified namespace.

        Examples
        --------
        >>> sn = s.ensight.utils.support.scoped_name
        >>> with sn(s.ensight.objs.core) as core, sn(s.ensight.objs.enums) as enums:
        >>>     print(core.PARTS.find(True, enums.VISIBLE))

        >>> sn = ensight.utils.support.scoped_name
        >>> with sn(ensight.objs.core) as core, sn(ensight.objs.enums) as enums:
        >>>     print(core.PARTS.find(True, enums.VISIBLE))

        >>> sn = ensight.utils.support.scoped_name
        >>> with sn(ensight.part, native_exceptions=True) as part:
        >>>     part.select_begin(-9999)
        """
        return ScopedName(self._ensight, obj, native_exceptions=native_exceptions)


class ScopedName:
    """Allow for the use of ``with`` to shorten APIs.

    In the EnSight and PyEnsight APIs, the interfaces can become lengthy.
    This class makes it possible to shorten APIs for modules, classes,
    and namespaces.
    """

    def __init__(
        self,
        interface: Union["ensight_api.ensight", "ensight"],
        obj: Any,
        native_exceptions: bool = False,
    ):
        self._obj = obj
        self._ensight = interface
        self._old_raise = None
        if native_exceptions:
            # if we are being asked to enable exceptions, record what to restore it to
            self._old_raise = self._ensight.query("SENDMESG_RAISE")

    def __enter__(self) -> Any:
        if self._old_raise is not None:
            # if a restore value is set, enable them
            self._ensight.sendmesgoptions(exception=1)
        return self._obj

    def __exit__(self, exc_type, exc_value, exc_trace):
        if self._old_raise is not None:
            # if the restore value is set, restore it here
            self._ensight.sendmesgoptions(exception=self._old_raise)
