import gc
from typing import TYPE_CHECKING, Any, Optional, Tuple

if TYPE_CHECKING:
    from ansys.pyensight.core import Session


def test_remote_objects(launch_pyensight_session: Tuple["Session", Any, Optional[str]]):
    session, _, _ = launch_pyensight_session
    session.load_data(f"{session.cei_home}/ensight{session.cei_suffix}/data/guard_rail/crash.case")

    # call __str__ on an ENSOBJ object w/o DESCRIPTION attribute (for coverage)
    print(session.ensight.objs.core)

    if session.cei_suffix >= "242":
        # Create an ENS_GROUP object (a remote object)
        g = session.ensight.objs.core.PARTS.find("*rail*", wildcard=1, group=1)
        assert "ENS_GROUP" in g.__str__(), "ensobjlist.find() did not return an ENS_GROUP instance"
        assert "Owned" in g.__str__(), "Remote ENS_GROUP is not 'Owned'"
        assert "Owned" not in g.CHILDREN.__str__(), "Objects in ENS_GROUP are incorrectly 'Owned'"

        # Exercise the custom __del__() method
        g = None
        gc.collect()

    session.close()
