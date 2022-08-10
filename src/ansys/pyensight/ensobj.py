"""ensobj module

The ensobj module provides the base class to all EnSight proxy objects

"""
from typing import Any, Optional


class ENSOBJ:
    def __init__(
        self,
        session: "Session",
        objid: int,
        attr_id: Optional[int] = None,
        attr_value: Optional[int] = None,
    ):
        self._session = session
        self._objid = objid
        self._attr_id = attr_id
        self._attr_value = attr_value
        self._session.add_ensobj_instance(self)

    @property
    def __OBJID__(self):
        return self._objid

    def _remote_obj(self):
        return self._session.remote_obj(self._objid)

    def getattr(self, attrid: Any) -> Any:
        return self._session.cmd(f"{self._remote_obj()}.getattr({attrid})")

    def getattrs(self, attrid: Optional[list] = None, text: int = 0):
        if attrid is None:
            cmd = f"{self._remote_obj()}.getattrs(text={text})"
        else:
            cmd = f"{self._remote_obj()}.getattrs({attrid},text={text})"
        return self._session.cmd(cmd)

    def setattr(self, attrid: Any, value: Any):
        self._session.cmd(f"{self._remote_obj()}.setattr({attrid}, {value})")

    def setattrs(self, attrid: Any, value: dict, all_errors: int = 0):
        cmd = f"{self._remote_obj()}.setattrs({attrid}, {value}, all_errors={all_errors})"
        self._session.cmd(cmd)

    def attrinfo(self, attrid: list, text: int = 0):
        return self._session.cmd(f"{self._remote_obj()}.attrinfo({attrid},text={text})")

    def setattr_begin(self):
        return self._session.cmd(f"{self._remote_obj()}.setattr_begin()")

    def setattr_end(self):
        return self._session.cmd(f"{self._remote_obj()}.setattr_end()")

    def setattr_status(self):
        return self._session.cmd(f"{self._remote_obj()}.setattr_status()")

    def setmetatag(self, tag: str, value: Optional[Any]):
        if value is None:
            cmd = f"{self._remote_obj()}.setmetatag({tag})"
        else:
            cmd = f"{self._remote_obj()}.setmetatag({tag}, {value})"
        return self._session.cmd(cmd)

    def hasmetatag(self, tag: str):
        return self._session.cmd(f"{self._remote_obj()}.hasmetatag({tag})")

    def getmetatag(self, tag: str):
        return self._session.cmd(f"{self._remote_obj()}.getmetatag({tag})")

    def __repr__(self):
        desc = ""
        if self._session.ensight.objs.enums.DESCRIPTION in self.attr_list:
            try:
                desc_text = self.DESCRIPTION
            except RuntimeError:
                # self.DESCRIPTION is a gRPC call that can fail for default objects
                desc_text = ""
            desc = f", desc: '{desc_text}'"
        return f"Class: {self.__class__}{desc}, CvfObjID: {self._objid}, cached:no"
