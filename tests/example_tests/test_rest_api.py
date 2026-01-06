# Copyright (C) 2022 - 2026 ANSYS, Inc. and/or its affiliates.
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

from ansys.pyensight.core.dockerlauncher import DockerLauncher
from ansys.pyensight.core.locallauncher import LocalLauncher
import pytest
import requests


def run_test(s):
    s.load_data(f"{s.cei_home}/ensight{s.cei_suffix}/data/cube/cube.case")
    uri_base = f"http://{s.hostname}:{s.html_port}/ensight/v1/{s.secret_key}"

    # Simple attempt to do some math, store it and get the value back

    ret = requests.put(f"{uri_base}/exec", json="enscl.rest_test = 30*20")
    assert ret.status_code == 200

    value = requests.put(f"{uri_base}/eval", json="enscl.rest_test").json()
    assert value == 600, "Unable to check computed value"

    # grab some helpful object ids
    js_part_name = requests.put(f"{uri_base}/eval", json="ensight.objs.core.PARTS[0]").json()
    part_id = requests.put(
        f"{uri_base}/eval", json="ensight.objs.core.PARTS[0]", params=dict(returns="__OBJID__")
    ).json()
    # check for '@ENSOBJ={id}@' name
    assert js_part_name == f"@ENSOBJ={part_id}@"

    # Simple command language example
    ret = requests.put(f"{uri_base}/cmd/ensight.view_transf.rotate", json=[5.2, 10.4, 0]).json()
    assert ret == 0

    # Alternate API for getting part object references
    ret = requests.get(f"{uri_base}/ensobjs/ensight.objs.core/PARTS").json()
    assert ret[0] == js_part_name

    # Manipulate the VISIBLE attribute in various ways
    # Start by the ensobjs API
    ret = requests.get(f"{uri_base}/ensobjs/{part_id}/VISIBLE").json()
    assert ret is True
    ret = requests.put(f"{uri_base}/ensobjs/{part_id}/VISIBLE", json=False)
    assert ret.status_code == 200
    # Verify via getattrs API
    ret = requests.put(
        f"{uri_base}/ensobjs/getattrs", json=[part_id], params=dict(returns="DESCRIPTION,VISIBLE")
    ).json()
    assert ret[f"{part_id}"][1] is False
    # try via the setatts API
    ret = requests.put(
        f"{uri_base}/ensobjs/setattrs", json=dict(objects=[f"{part_id}"], values=dict(VISIBLE=True))
    )
    assert ret.status_code == 200
    # Verify the result
    ret = requests.get(f"{uri_base}/ensobjs/{part_id}/VISIBLE").json()
    assert ret is True

    # Simple remote function test
    foo_src = "def foo(n:int = 1):\n return list(numpy.random.rand(n))\n"
    ret = requests.put(
        f"{uri_base}/def_func/rest_test/foo", json=foo_src, params=dict(imports="numpy")
    )
    assert ret.status_code == 200
    ret = requests.put(uri_base + "/call_func/rest_test/foo", json=dict(n=3)).json()
    assert len(ret) == 3
    assert type(ret[0]) == float

    s.close()


def test_rest_apis(tmpdir, pytestconfig: pytest.Config):
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    install_path = pytestconfig.getoption("install_path")
    if use_local:
        launcher = LocalLauncher(ansys_installation=install_path, enable_rest_api=True)
    else:
        launcher = DockerLauncher(
            data_directory=data_dir,
            use_dev=True,
            enable_rest_api=True,
            grpc_disable_tls=True,
            grpc_use_tcp_sockets=True,
        )
    s = launcher.start()
    run_test(s)


def test_rest_apis_liben(tmpdir, pytestconfig: pytest.Config):
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    install_path = pytestconfig.getoption("install_path")
    if use_local:
        launcher = LocalLauncher(ansys_installation=install_path, enable_rest_api=True)
    else:
        launcher = DockerLauncher(
            data_directory=data_dir,
            use_dev=True,
            enable_rest_api=True,
            grpc_disable_tls=True,
            grpc_use_tcp_sockets=True,
            liben_rest=True,
        )
    s = launcher.start()
    run_test(s)
