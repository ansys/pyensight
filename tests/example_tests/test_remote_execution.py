import time

from ansys.pyensight.core import DockerLauncher, LocalLauncher
import pytest


def test_remote_execution(tmpdir, pytestconfig: pytest.Config):
    def myfunc(ensight):
        names = []
        for p in ensight.objs.core.PARTS:
            names.append(p.DESCRIPTION)
        return names

    def count(ensight, attr, value):
        import time  # time must be imported on the EnSight side as well

        start = time.time()
        count = 0
        for p in ensight.objs.core.PARTS:
            if p.getattr(attr) == value:
                count += 1
        return count, time.time() - start

    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    install_path = pytestconfig.getoption("install_path")
    if use_local:
        launcher = LocalLauncher(ansys_installation=install_path)
    else:
        launcher = DockerLauncher(data_directory=data_dir, use_dev=True)
    session = launcher.start()
    session.load_data(f"{session.cei_home}/ensight{session.cei_suffix}/data/guard_rail/crash.case")
    start = time.time()
    names = myfunc(session.ensight)
    print(f"Remote: {time.time()-start}")
    print(names)

    cmd = "def myfunc():\n"
    cmd += "    names = []\n"
    cmd += "    for p in ensight.objs.core.PARTS:\n"
    cmd += "        names.append(p.DESCRIPTION)\n"
    cmd += "    return names.__repr__()\n"
    session.cmd(cmd, do_eval=False)
    start = time.time()
    names = session.cmd("myfunc()")
    print(f"Remote: {time.time()-start}")
    print(names)
    print(count(session.ensight, "VISIBLE", True))
    _grpc = session.exec(count, "VISIBLE", True)
    print(_grpc)
    try:
        remote = session.exec(count, "VISIBLE", True)
        print(remote)
    except RuntimeError:  # case of mismatch between python versions
        pass
    session.close()
