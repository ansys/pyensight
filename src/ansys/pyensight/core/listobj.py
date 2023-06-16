"""ensobjlist module

Emulation of the EnSight ensobjlist class

"""
from collections.abc import Iterable
import fnmatch
from typing import Any, List, Optional, TypeVar, no_type_check, overload

from ansys.pyensight.core.ensobj import ENSOBJ
from typing_extensions import SupportsIndex

T = TypeVar("T")


class ensobjlist(List[T]):  # noqa: N801
    """Class used when returning lists of EnSight proxy objects.  A subclass of 'list'.

    In the EnSight object Python bindings, whenever a list is returned that
    is known to exclusively contain ENSOBJ subclass objects, the ensobjlist
    (list subclass) is returned instead.  This class simply adds a few
    ENSOBJ specific methods and some functionality to the list object.

    One additional feature of the ensobjlist is that the __getitem__()
    interface supports strings and lists of strings.  In that situation,
    the object acts as if the find() method is called.

    These are equivalent

    >>> a = objlist["Hello"]
    >>> a = objlist.find("Hello", attr="DESCRIPTION")

    These are as well

    >>> a = objlist[("Hello", "Goodbye")]
    >>> a = objlist.find(("Hello", "Goodbye"), attr="DESCRIPTION")

    Parameters
    ----------
    \*args :
        Superclass (list) arguments
    \**kwargs :
        Superclass (list) keyword arguments


    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    @staticmethod
    def _is_iterable(arg: Any) -> bool:
        """Check if the arg is iterable, but not a string.

        Parameters
        ----------
        arg: Any
            Argument to check.

        """
        return isinstance(arg, Iterable) and not isinstance(arg, str)

    def find(
        self, value: Any, attr: Any = "DESCRIPTION", group: int = 0, wildcard: int = 0
    ) -> "ensobjlist[T]":
        """Find objects in the list using the ENSOBJ interface.

        This method will scan the ENSOBJ subclass objects in the list and return
        an ensobjlist of those matching the search criteria.

        Parameters
        ----------
        value: Any
            A single object or a tuple of objects that will be compared to the value of
            an attribute accessed via the getattr() ENSOBJ interface.
        attr: Any
            The specific attribute (id or string) to look up using getattr().
        group: int
            Currently unimplemented.
        wildcard: int
            Instead of the comparison being done via the equals test, it will be done using
            fnmatch between the string representation of the item and the value.  This allows
            values to be specified using glob wildcard specifications.  If wildcard is set
            to 1, this is a case-sensitive wildcard operation.  If set to 2, the comparison
            is case-insensitive.  The default is not to use wildcard comparisons (0).

        Returns
        -------
        ensobjlist[T]
            An ensobjlist of the items that matched the search criteria.

        """
        value_list = value
        if not self._is_iterable(value):
            value_list = [value]
        out_list: ensobjlist[Any] = ensobjlist()
        for item in self:
            if isinstance(item, ENSOBJ):
                try:
                    item_value = item.getattr(attr)
                    for check_value in value_list:
                        if wildcard == 2:
                            if fnmatch.fnmatch(str(item_value), str(check_value)):
                                out_list.append(item)
                                break
                        elif wildcard > 0:
                            if fnmatch.fnmatchcase(str(item_value), str(check_value)):
                                out_list.append(item)
                                break
                        else:
                            if item_value == check_value:
                                out_list.append(item)
                                break
                except RuntimeError:
                    pass
        # TODO: handle group
        return out_list

    def set_attr(self, attr: Any, value: Any) -> int:
        """Set an attribute value on all contained objects

        Walk the items in this object.  If they are ENSOBJ subclasses, attempt to set
        the specified attribute id to the specified value.  Count the number of times
        that operation was successful and return that number.

        Parameters
        ----------
        attr: Any
            The specific attribute (id or string) to change using setattr().
        value: Any
            The value to attempt to set the specified attribute to.

        Returns
        -------
        int
            The number of successful set operations.

        Examples
        --------
        >>> session.ensight.objs.core.PARTS.set_attr("VISIBLE", True)

        """
        count: int = 0
        for item in self:
            if isinstance(item, ENSOBJ):
                try:
                    item.setattr(attr, value)
                    count += 1
                except RuntimeError:
                    pass
        return count

    def get_attr(self, attr: Any, default: Optional[Any] = None):
        """Query a specific attribute for all ENSOBJ objects in the list

        Walk the items in this object.  If they are ENSOBJ subclasses, query the value of
        the passed attribute id.  If the item is not an ENSOBJ subclass or the attribute
        query fails, the returned list will have the specified default value for that item.

        Parameters
        ----------
        attr: Any
            The specific attribute (id or string) to look up using getattr().
        default: Any, optional
            The value to return for objects that are not ENSOBJ subclasses or do not
            support the specified attribute.

        Returns
        -------
        List
            A list of the attribute values for each item in this object

        Examples
        --------
        >>> state = session.ensight.core.PARTS.get_attr(session.ensight.objs.enums.VISIBLE)

        """
        out_list = []
        for item in self:
            item_value = default
            if isinstance(item, ENSOBJ):
                try:
                    item_value = item.getattr(attr)
                except RuntimeError:
                    item_value = default
            out_list.append(item_value)
        return out_list

    @overload
    def __getitem__(self, index: SupportsIndex) -> T:
        ...

    @overload
    def __getitem__(self, index: slice) -> List[T]:
        ...

    def __getitem__(self, index):
        """Overload the getitem operator to allow for tuple and string DESCRIPTION queries"""
        if isinstance(index, str) or isinstance(index, tuple):
            return self.find(index)
        return super().__getitem__(index)

    def __str__(self):
        ret_str = ", ".join([str(x) for x in self])
        return f"[{ret_str}]"

    @no_type_check
    def _repr_pretty_(self, p: "pretty", cycle: bool) -> None:
        """Support the pretty module for better IPython support

        Parameters
        ----------
        p: "pretty" :
            pretty flag.
        cycle: bool :
            cycle flag.

        """
        name = self.__class__.__name__
        if cycle:
            p.text(f"{name}(...)")
        else:
            with p.group(len(name) + 2, f"{name}([", "])"):
                for idx, item in enumerate(self):
                    if idx:
                        p.text(",")
                        p.breakable()
                    p.pretty(item)
