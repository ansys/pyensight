# Copyright (C) 2022 - 2025 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

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
            data_directory=data_dir, use_dev=True, grpc_disable_tls=True, grpc_use_tcp_sockets=True
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
