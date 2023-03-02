import os
import shutil
import time

from ansys.pyensight import DockerLauncher, LocalLauncher


def test_remote_execution(tmpdir):
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
    shutil.copytree(
        os.path.join(os.path.dirname(__file__), "test_data", "guard_rail"),
        os.path.join(data_dir, "cube"),
    )
    try:
        launcher = DockerLauncher(data_directory=data_dir, use_dev=True)
    except Exception:
        launcher = LocalLauncher()
    session = launcher.start()
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
