from inspect import getfullargspec
import os
import re

import pytest

from ansys.pyensight import ensight_api

# This function has been used for finding all the classes in ensight_api.py
# def classesinmodule(module):
#    md = module.__dict__
#    return [md[c] for c in md if (isinstance(md[c], type) and md[c].__module__ == module.__name__)]


# The test function test_api has been then modified to get the list of classes,
# walk it, and generate the mocked output. The mocked output for each class method
# has been set to be the argument received by the method itself. The output has been
# dumped into a file which is now part of the unit tests distribution


# def test_generate_assets_api(mocked_session):
#    list_of_classes = classesinmodule(ensight_api)
#    text = open("input_output.txt", "w")
#    for _class in list_of_classes:
#        instance = _class(mocked_session)
#        method_list = [
#            method
#            for method in dir(instance)
#            if method.startswith("__") is False and hasattr(getattr(instance, method), "__call__")
#        ]
#        for method in method_list:
#            _method = getattr(instance, method)
#            sig = getfullargspec(_method)
#            num_args = len(sig.args)
#            if "self" in sig.args or "cls" in sig.args:
#                num_args -= 1
#            if sig.varargs:
#                num_args += 1
#            args = [1] * num_args
#            num_kwargs = len(sig.kwonlyargs)
#            if sig.varkw:
#                num_kwargs += 1
#            kwargs = {"{}".format(i): i for i in range(num_kwargs)}
#            mocked_session.cmd = lambda command: command
#            if not isinstance(instance, ansys.pyensight.ensight_api.objs):
#                value = _method(*args, **kwargs)
#                text.write(f"{_class},{method},,{value}\n")
#            else:
#                try:
#                    value = _method(*args, **kwargs)
#                    text.write(f"{_class},{method},,{value}\n")
#                except (AttributeError, TypeError):
#                    subinstance = _method(mocked_session, 1)
#                    submethod_list = [
#                        submethod
#                        for submethod in dir(subinstance)
#                        if submethod.startswith("__") is False
#                        and hasattr(getattr(subinstance, submethod), "__call__")
#                    ]
#                    for submethod in submethod_list:
#                        _submethod = getattr(subinstance, submethod)
#                        sig = getfullargspec(_submethod)
#                        num_args = len(sig.args)
#                        if "self" in sig.args or "cls" in sig.args:
#                            num_args -= 1
#                        if sig.varargs:
#                            num_args += 1
#                        args = [1] * num_args
#                        num_kwargs = len(sig.kwonlyargs)
#                        if sig.varkw:
#                            num_kwargs += 1
#                        kwargs = {"{}".format(i): i for i in range(num_kwargs)}
#                        mocked_session.cmd = lambda command: command
#                        try:
#                            value = _submethod(*args, **kwargs)
#                            text.write(f"{_class},{method},{submethod},{value}\n")
#                        except AttributeError:
#                            # _repr_pretty_ method, which needs a objlist input
#                            pass
#    text.close()


assets = []
for line in open(os.path.join(os.path.dirname(__file__), "ensigth_api_test_assets.txt")):
    split = re.search(r"(.*?,)(.*?,)(.*?,)(.*)", line)
    split = [x.replace(",", "").strip() for x in split.groups()[:-1]] + [split.group(4).strip()]
    assets.append((split[0], split[1], split[2], split[3]))


@pytest.mark.parametrize("class_name,method_name,submethod_name,output", assets)
def test_ensight_api(mocked_session, class_name, method_name, submethod_name, output):
    if output == "None":
        output = None
    mocked_session.cmd = lambda command: command
    class_instance = getattr(ensight_api, class_name)(mocked_session)
    method = getattr(class_instance, method_name)
    if submethod_name:
        subinstance = method(mocked_session, 1)
        submethod = getattr(subinstance, submethod_name)
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
