from inspect import getfullargspec
import os
import re

from ansys.pyensight import ensight_api


def test_ensight_api(mocked_session):
    assets = []
    for line in open(os.path.join(os.path.dirname(__file__), "ensigth_api_test_assets.txt")):
        split = re.search(r"(.*?,)(.*?,)(.*?,)(.*)", line)
        split = [x.replace(",", "").strip() for x in split.groups()[:-1]] + [split.group(4).strip()]
        assets.append((split[0], split[1], split[2], split[3]))
    for asset in assets:
        class_name = asset[0]
        method_name = asset[1]
        submethod_name = asset[2]
        output = asset[3]
        if output == "None":  # functions with no return
            output = None
        mocked_session.cmd = lambda command: command
        class_instance = getattr(ensight_api, class_name)(mocked_session)
        method = getattr(class_instance, method_name)
        if submethod_name:
            subinstance = method(mocked_session, 1)
            submethod = getattr(subinstance, submethod_name)
            if output == "EMPTY":  # properties
                submethod
            else:
                sig = getfullargspec(submethod)
                num_args = len(sig.args)
                if "self" in sig.args or "cls" in sig.args:
                    num_args -= 1
                if sig.varargs:
                    num_args += 1
                args = [1] * num_args
                num_kwargs = len(sig.kwonlyargs)
                if sig.varkw:
                    num_kwargs += 1
                kwargs = {"{}".format(i): i for i in range(num_kwargs)}
                assert submethod(*args, **kwargs) == output
        else:
            sig = getfullargspec(method)
            num_args = len(sig.args)
            if "self" in sig.args or "cls" in sig.args:
                num_args -= 1
            if sig.varargs:
                num_args += 1
            args = [1] * num_args
            num_kwargs = len(sig.kwonlyargs)
            if sig.varkw:
                num_kwargs += 1
            kwargs = {"{}".format(i): i for i in range(num_kwargs)}
            assert method(*args, **kwargs) == output
