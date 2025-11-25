import gc

from ansys.pyensight.core import DockerLauncher, LocalLauncher
import pytest


def test_remote_objects(tmpdir, pytestconfig: pytest.Config):
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    if use_local:
        launcher = LocalLauncher()
    else:
        launcher = DockerLauncher(
            data_directory=data_dir, use_dev=True, grpc_disable_tls=True, grpc_uds_pathname=True
        )
    session = launcher.start()
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
