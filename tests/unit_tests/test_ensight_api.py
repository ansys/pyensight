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

import inspect
import re
from typing import List

from ansys.api.pyensight import ensight_api, ensight_api_test_assests
from ansys.pyensight.core import ensobj


def test_ensight_api(mocked_session, mocker):
    assets = []
    # The assets file contains the objects to be checked during the test.
    # This is generated when the API itself is generated
    file_contents = ensight_api_test_assests()
    file_contents_lines = file_contents.split("\n")
    for line in file_contents_lines:
        split = re.search(r"(.*?,)(.*?,)(.*?,)(.*)", line)
        if split is not None:
            split = [x.replace(",", "").strip() for x in split.groups()[:-1]] + [
                split.group(4).strip()
            ]
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
        class_object = getattr(ensight_api, class_name)
        if issubclass(ensobj.ENSOBJ, class_object):
            mocker.patch.object(getattr(ensight_api, class_name), "attrinfo", return_value={})
        class_instance = getattr(ensight_api, class_name)(mocked_session)
        # The second operation is to get an eventual "method" of the class.
        # It might be not a method, but another class, and this is set by the
        # asset having a "submethod_name" value
        method = getattr(class_instance, method_name)
        if hasattr(method, "attrinfo"):
            mocker.patch.object(method, "attrinfo", return_value={})
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
                s_args, s_kwargs = get_args_kwargs(submethod)
                # args are passed as 1
                args = [1] * len(s_args)
                # kwargs are passed as 0
                kwargs = {}
                for kw in s_kwargs:
                    kwargs[kw] = 0

                assert submethod(*args, **kwargs) == output
        else:
            # In this case we are actually calling a method.
            # The session cmd function has been mocked to return the
            # arguments it receives. The arguments are being inspected
            # using the signature module. The args are all set to 1,
            # the kwargs all to dictionaries of kind 1=1, where the key
            # is of course a string. This is just to check that they can
            # be called.
            s_args, s_kwargs = get_args_kwargs(method)
            # args are passed as 1
            args = [1] * len(s_args)
            # kwargs are passed as 0
            kwargs = {}
            for kw in s_kwargs:
                kwargs[kw] = 0

            assert method(*args, **kwargs) == output


def get_args_kwargs(method: callable) -> (List, List):
    """
    Parse the signature of a callable and return lists of the
    args and kwargs using the inspect signature.
    Rules:
        1) skip 'self' and 'cls'
        2) if both '*args' and '**kwargs' set, return [1], ["0"] for backward compatibility
        3) something is a keyword if it has a default value, otherwise it is an arg.

    Args:
        method:
            The callable to parse

    Returns:
        A tuple of the args name list and the kwargs name list.  Note: either list can
        be empty.
    """
    sig = inspect.signature(method)
    # backward compatibility with getfullargspec for *args, **kwargs only cases
    if ("args" in sig.parameters) and ("kwargs" in sig.parameters):
        return [1], ["0"]
    # more complete method
    a_list = []
    kw_list = []
    for p in sig.parameters.values():
        # skip these special cases
        if p.name in ("self", "cls"):
            continue
        # treat no-default as arg and default as keyword for this case
        if p.default == inspect.Parameter.empty:
            a_list.append(p.name)
        else:
            kw_list.append(p.name)
    return a_list, kw_list
