from typing import TYPE_CHECKING, Any, Optional, Tuple

if TYPE_CHECKING:
    from ansys.pyensight.core import Session

import requests


def test_rest_apis(launch_pyensight_session: Tuple["Session", Any, Optional[str]]):
    s, _, _ = launch_pyensight_session
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
