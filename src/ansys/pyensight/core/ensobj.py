"""ensobj module

The ensobj module provides the base class to all EnSight proxy objects

"""
from typing import TYPE_CHECKING, Any, Optional, no_type_check

if TYPE_CHECKING:
    from ansys.pyensight.core import Session


class ENSOBJ(object):
    """Bass class for all EnSight proxy objects

    The ENSOBJ class is the base class for the EnSight object proxy interface.
    Note: this interface is internal and applications should not attempt to
    create ENSOBJ instances directly.

    Parameters
    ----------
    session :
        The session object associated with this object instance.
    objid :
        The EnSight CvfObjID of the object instance that this instance will
        serve as the proxy for.
    attr_id :
        For subclasses that differentiate classes by an attribute value,
        this is the attribute ID to use as the differentiator.  Example
        classes are ENS_TOOL, ENS_PART and ENS_ANNOT.
    attr_value :
        The attribute value associated with any specified attr_id.
    owned : bool
        If True, the object is assumed to be "owned" by this interpreter.
        This means that the lifecycle of the ENSOBJ instance in EnSight is
        dictated by the lifecycle of this proxy object.

    """

    def __init__(
        self,
        session: "Session",
        objid: int,
        attr_id: Optional[int] = None,
        attr_value: Optional[int] = None,
        owned: Optional[bool] = None,
    ) -> None:
        self._session = session
        self._objid = objid
        self._attr_id = attr_id
        self._attr_value = attr_value

        # True if this Python instance "owns" the ENSOBJ instance (via EnSight proxy cache)
        if owned:
            self._is_owned = True
        else:
            self._is_owned = False
            # do not put this object in the cache if it is owned, allow gc
            self._session.add_ensobj_instance(self)

    def __eq__(self, obj):
        return self._objid == obj._objid

    def __lt__(self, obj):
        return self._objid < obj._objid

    def __hash__(self):
        return self._objid

    def __del__(self):
        # release the session to allow for garbage collection
        tmp_session = self._session
        self._session = None
        if self._is_owned:
            try:
                cmd = f"ensight.objs.release_id('{tmp_session.name}', {self.__OBJID__})"
                tmp_session.cmd(cmd, do_eval=False)
            except Exception:  # pragma: no cover
                # This could happen at any time, including outside
                # the scope of the session, so we need to be
                # ready for any error.
                pass

    @property
    def __OBJID__(self) -> int:  # noqa: N802
        return self._objid

    def _remote_obj(self) -> str:
        """Convert the object into a string appropriate for use in the
        remote EnSight session.   Usually, this is some form of
        ensight.objs.wrap_id()."""
        return self._session.remote_obj(self._objid)

    def getattr(self, attrid: Any) -> Any:
        """Query the value of the specified attribute

        Parameters
        ----------
        attrid: Any
            The attribute to query

        Returns
        -------
        Any
            The current value of the attribute.

        Examples
        --------
        These commands are equivalent

        >>> v = part.VISIBLE
        >>> v = part.getattr("VISIBLE")
        >>> v = part.getattr(session.ensight.objs.enums.VISIBLE)
        """
        return self._session.cmd(f"{self._remote_obj()}.getattr({attrid.__repr__()})")

    def getattrs(self, attrid: Optional[list] = None, text: int = 0) -> dict:
        """Query the value of a collection of attributes

        This method queries a collection of attributes in a single call and
        returns the attribute values in a dictionary keyed by the attribute ids.

        Parameters
        ----------
        attrid : Optional[list]
            If this value is a list (of attribute ids as strings or enum values),
            then the returned dictionary will only include values for the specified
            attributes.  Otherwise, the returned dictionary will include values for
            all attributes of the target object.
        text : int
            By default, the returned dictionary keys are the attribute ID enum
            values.  If text is set to 1, the dictionary keys will be strings.
            Return:

        Returns
        -------
            Session CMD.

        Examples
        --------
        To copy some attributes from one part to another.

        >>> tmp = part0.getattrs(["VISIBLE", session.ensight.objs.enums.OPAQUENESS])
        >>> part1.setattrs(tmp)

        """
        if attrid is None:
            cmd = f"{self._remote_obj()}.getattrs(text={text})"
        else:
            cmd = f"{self._remote_obj()}.getattrs({attrid.__repr__()},text={text})"
        return self._session.cmd(cmd)

    def setattr(self, attrid: Any, value: Any) -> None:
        """Set the value of the specified attribute

        Parameters
        ----------
        attrid : Any
            The attribute to set.  This can be an integer (enum) or string.
        value : Any
            The value to set the attribute to.

        Returns
        -------
            Session CMD.

        Examples
        --------
        These commands are equivalent

        >>> part.setattr("VISIBLE", True)
        >>> part.getattr(session.ensight.objs.enums.VISIBLE, True)

        """
        return self._session.cmd(
            f"{self._remote_obj()}.setattr({attrid.__repr__()}, {value.__repr__()})"
        )

    def setattrs(self, values: dict, all_errors: int = 0) -> None:
        """Set the values of a collection of attributes

        Parameters
        ----------
        values : Dict
            The values to set.  The keys are the attribute IDs.
        all_errors : int
            If non-zero, raise a RuntimeError exception if any attribute set
            operation fails. By default, 0.

        Examples
        --------
        These commands are equivalent

        >>> part.VISIBLE = True
        >>> part.setattrs(dict(VISIBLE=True))
        >>> part.setattrs({session.ensight.objs.enums.VISIBLE: True})

        """
        cmd = f"{self._remote_obj()}.setattrs({values.__repr__()}, all_errors={all_errors})"
        return self._session.cmd(cmd)

    def attrinfo(self, attrid: Optional[Any] = None) -> dict:
        """For a given attribute id, return type information

        The dictionary returned by will always have the following keys:
            - `type` the high-level type. This can include any of the values noted in the next
              section

            - `basetype` the low-level type. Only types starting with `CVF` are allowed.

            - `numvals` the number of values of the `basetype`.

            - `desc` string description for the attr

            - `name` the python legal name for the attr

            - `flags` this integer is formed by or-ing values from the table below

        Optional keys:
            - `range` if selected in the flags, this key will be a list of two floats or
              ints: [min,max]. see `flags` below

            - `enums` if selected in the flags, this key will be list of lists. Each list has
              three values: [int_value, description, python_name]. The integer value is the number
              for the enum (see `flags` below), while the other two values are human and Python
              strings. The python_name will also be available as an integer in the
              ensight.objs.enums module.

            - `dependencies` if present, this key is a list of dictionaries that describe the
              fact that this attr is dependent on another attr. The dictionary is described below.

        Parameters
        ----------
        attrid : Optional[Any]
            The attribute to query

        Returns
        -------
        dict
            A dictionary that describes type information for the attribute.

        Examples
        --------
        >>> part.attrinfo(session.ensight.objs.enums.VISIBLE)

        """
        if not attrid:
            return self._session.cmd(f"{self._remote_obj()}.attrinfo()")
        return self._session.cmd(f"{self._remote_obj()}.attrinfo({attrid.__repr__()})")

    def attrissensitive(self, attrid: Any) -> bool:
        """Check to see if a given attribute is 'sensitive'

        Given the current state of the target object, return True if it makes sense to
        allow the specified attribute to change.   Return False if the object is currently
        ignoring the value of a given attribute due to the state of other attributes.

        Parameters
        ----------
        attrid : Any
            The attribute to query

        Returns
        -------
        bool
            True or False

        """
        return self._session.cmd(f"{self._remote_obj()}.attrissensitive({attrid.__repr__()})")

    def attrtree(
        self,
        all: int = 0,
        filter: Optional[list] = None,
        exclude: Optional[list] = None,
        include: Optional[list] = None,
        group_exclude: Optional[list] = None,
        group_include: Optional[list] = None,
        insensitive: int = 1,
    ) -> dict:
        """Get detailed GUI information for attributes of this object.

        This method is on MOST of the intrinsic objects, but not all of them. This method is used
        to generate a "visual" tree of an object's attributes. The most common use would be to
        dynamically generate labels and hierarchy for a "property sheet" editor.

        The method returns an object tree that describes the way attribute should be laid out.
        Each object has three attributes: `attr`, 'hasdeps' and `name`. All objects will have names
        and group objects will have an attr of -1. All objects can also be iterated for children
        objects of the same type. Only objects with an `attr` of -1 will have children. len() can
        be used to get the number of child objects. The top level object always has the name
        `root`. The 'hasdeps' attribute is the number of attributes in this attrtree() that have
        a dependency on this attr.  This can be used to decide if a new sensitivity check is needed
        if a given attribute changes.

        Parameters
        ----------
        all : int
            If set to 1 will include all attrs for the object, even if they are not in the group
            tables.
        filter : Optional[list]
            Should be set to an optional list of EnSight objects. The output will be filtered
            to include only the attributes in common between all of the objects (they do not
            need to be of the same type).
        include : Optional[list]
            Should be set to a list of attribute enums. Only the enums in the list will be
            included in the output object tree. Note: passing an empty list via this keyword,
            all the enums will be initially excluded.  This is useful with the
            group_include= keyword.
        exclude : Optional[list]
            Should be set to a list of attribute enums. Any enums in the list will be
            removed from the output object tree.
        group_exclude : Optional[list]
            Should be set to a list of attribute enums. For any enum in this list, exclude
            the enum and all the other enums in the same groups as the passed enums. Think
            of this as a shortcut for exclude= that requires you to only pass a single enum
            in the group you want to suppress.
        group_include : Optional[list]
            Should be set to a list of attribute enums. For any enum in this list, include
            the enum and all the other enums in the same groups as the passed enums. Think
            of this as a shortcut for include= that requires you to only pass a single enum
            in the group you want to include. Note: it may be necessary to pass include=[]
            (the empty list) to start with an empty list of enums.
        insensitive : int
            If this keyword is set to 0, attrtree() will call foo.issensitive() on each
            filtered attr and if the attr is not currently sensitive, it will remove it
            from the output.  The default value for this keyword is 1 which disables all
            sensitivity filtering.

        Examples
        --------

        >>> def walk_tree(part,obj,s):
        >>>     a = obj.attr
        >>>     if (a == -1):
        >>>         print("{}Group={}".format(s, obj.name)))
        >>>     else:
        >>>         = part.attrinfo(a)
        >>>         t = enum_to_name(a)
        >>>         d = info['desc']
        >>>         print("{}Attr={} - '{}' ({:d} deps)".format(s, t, d, obj.hasdeps))
        >>>     for i in obj:
        >>>         walk_tree(part,i,s+"  ")
        >>> walk_tree(session.ensight.core.PARTS[0],session.ensight.core.PARTS[0].attrtree(),"")
        """
        obj = f"{self._remote_obj()}"
        options = f"all={all}"
        options += f",insensitive={insensitive}"
        if filter:
            options += f",filter={filter.__repr__()}"
        if include:
            options += f",include={include.__repr__()}"
        if exclude:
            options += f",exclude={exclude.__repr__()}"
        if group_exclude:
            options += f",group_exclude={group_exclude.__repr__()}"
        if group_include:
            options += f",group_include={group_include.__repr__()}"
        return self._session.cmd(f"{obj}.attrgroupinfo({options})")

    def setattr_begin(self) -> None:
        """Signal bulk attribute update begin

        By default, EnSight will update the display with every attribute change.  If a lot of
        changes are to be made, this can slow execution down.  Putting a collection of changes
        inside of a setattr_begin()/setattr_end() pair of calls will defer the update until the
        setattr_end() call is made.

        """
        return self._session.cmd(f"{self._remote_obj()}.setattr_begin()")

    def setattr_end(self) -> None:
        """Signal bulk attribute update end

        By default, EnSight will update the display with every attribute change.  If a lot of
        changes are to be made, this can slow execution down.  Putting a collection of changes
        inside of a setattr_begin()/setattr_end() pair of calls will defer the update until the
        setattr_end() call is made.

        """
        return self._session.cmd(f"{self._remote_obj()}.setattr_end()")

    def setattr_status(self) -> int:
        """ """
        return self._session.cmd(f"{self._remote_obj()}.setattr_status()")

    def setmetatag(self, tag: str, value: Optional[Any]) -> None:
        """Change a value in the METADATA attribute

        All ENSOBJ subclasses have a METADATA read only attribute that is viewed as a Python
        dictionary.  A value can be set in that dictionary using this call:

        Parameters
        ----------
        tag : str
            The string name of the METADATA tag to add/change.
        value : Any, optional
            The value to change to tag to.  Note: this can be a string, int or float.

        Examples
        --------
        >>> session.ensight.objs.core.PARTS[0].setmetatag("FOO", "HELLO")
        >>> print(session.ensight.objs.core.PARTS[0].METADATA)

        """
        if value is None:
            cmd = f"{self._remote_obj()}.setmetatag({tag.__repr__()})"
        else:
            cmd = f"{self._remote_obj()}.setmetatag({tag.__repr__()}, {value.__repr__()})"
        return self._session.cmd(cmd)

    def hasmetatag(self, tag: str) -> bool:
        """Check to see if a tag exists in the METADATA attribute

        Parameters
        ----------
        tag : str
            The string name of the METADATA tag to check

        Returns
        -------
        bool
            True if the named tag exists in the METADATA attribute.

        """
        return self._session.cmd(f"{self._remote_obj()}.hasmetatag({tag.__repr__()})")

    def getmetatag(self, tag: str) -> Any:
        """Get the value of a tag in the METADATA attribute

        Parameters
        ----------
        tag : str

        The string name of the METADATA tag to get

        Returns
        -------
        Any
            The value assigned to the tag in the METADATA attribute.

        Examples
        --------
        >>> session.ensight.objs.core.PARTS[0].setmetatag("FOO", "HELLO")
        >>> print(session.ensight.objs.core.PARTS[0].getmetatag("FOO"))

        """
        return self._session.cmd(f"{self._remote_obj()}.getmetatag({tag.__repr__()})")

    def destroy(self) -> None:
        """Destroy the EnSight object associated with this proxy object"""
        self._session.cmd(f"{self._remote_obj()}.destroy()")

    def __str__(self) -> str:
        desc = ""
        if hasattr(self.__class__, "attr_list"):  # pragma: no cover
            if self._session.ensight.objs.enums.DESCRIPTION in self.__class__.attr_list:
                try:
                    if hasattr(self, "DESCRIPTION"):  # pragma: no cover
                        desc_text = self.DESCRIPTION
                    else:
                        desc_text = ""
                except RuntimeError:  # pragma: no cover
                    # self.DESCRIPTION is a gRPC call that can fail for default objects
                    desc_text = ""  # pragma: no cover
                desc = f", desc: '{desc_text}'"
        owned = ""
        if self._is_owned:
            owned = ", Owned"
        return f"Class: {self.__class__.__name__}{desc}{owned}, CvfObjID: {self._objid}, cached:no"

    def __repr__(self) -> str:
        """Custom __repr__ method used by the stub API.

        In some cases, we need to specify the object representation in the EnSight
        instance.  For ENSOBJ instances, this means using the wrap_id() mechanism
        instead of the built-in __repr__.  So the generated API uses this interface.
        """
        return f"ensight.objs.wrap_id({self._objid})"

    @no_type_check
    def _repr_pretty_(self, p: "pretty", cycle: bool) -> None:
        """Support the pretty module for better IPython support.

        Parameters
        ----------
        p: str
            pretty flag.

        cycle: bool :
            cycle flag.

        """
        p.text(self.__str__())
