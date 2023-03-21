from inspect import getfullargspec
import os
import re

from ansys.pyensight import ensight_api


def test_ensight_api(mocked_session):
    assets = []
    # The assets file contains the objects to be checked during the test.
    # This is generated when the API itself is generated
    for line in open(os.path.join(os.path.dirname(__file__), "ensight_api_test_assets.txt")):
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
        # As first operation, I get an instance of the class. This might be,
        # for example, a class inside a module, like vortexcore
        class_instance = getattr(ensight_api, class_name)(mocked_session)
        # The second operation is to get an eventual "method" of the class.
        # It might be not a method, but another class, and this is set by the
        # asset having a "submethod_name" value
        method = getattr(class_instance, method_name)
        if submethod_name:
            subinstance = method(mocked_session, 1)
            submethod = getattr(subinstance, submethod_name)
            # The first two branches are properties. The properties
            # might be getter or setters. The getters are flagged by
            # the output string being set to EMPTY, while the setter
            # by the string SETTER. If it is a getter, just call it,
            # if it is a setter, set the property to a value
            if output == "SETTER":
                submethod = setattr(subinstance, submethod_name, 1)
            elif output == "EMPTY":  # properties
                submethod
            else:
                # In this case we are actually calling a submethod.
                # The session cmd function has been mocked to return the
                # arguments it receives. The arguments are being inspected
                # using the signature module. The args are all set to 1,
                # the kwargs all to dictionaries of kind 1=1, where the key
                # is of course a string. This is just to check that they can
                # be called.
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
            # In this case we are actually calling a method.
            # The session cmd function has been mocked to return the
            # arguments it receives. The arguments are being inspected
            # using the signature module. The args are all set to 1,
            # the kwargs all to dictionaries of kind 1=1, where the key
            # is of course a string. This is just to check that they can
            # be called.
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
