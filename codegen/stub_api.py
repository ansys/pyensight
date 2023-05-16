"""Generate .py files from current EnSight API .xml description

Usage
-----

`python generate_stub_api.py`
"""
import datetime
import fnmatch
import glob
import os.path
import re
import sys
from typing import Any, List, Optional
from xml.etree import ElementTree

import requests


class XMLOverrides:
    """Provide a mechanism for attribute override
    Walk a directory of XML files.  Find the 'override' tags of the form:
    <override namespace="{name}">
        <{attribute}>{value}</attribute>
    </override>
    For a given object namespace, it records a collection of text blocks that
    should be used to override attributes for objects of that namespace.

    Common tags include:
    <description> - the doc string text for the namespace
    <signature> - the typehint for a function:  "(foo: int, bar: str = "") -> "ENSOBJ"
    <paramnames> - the names used in <signature> ('=' is a keyword):  "['foo', 'bar=']"
    <code> - a custom binding implementation

    Args:
        directory_list:
            A list of directories to scan for .xml files.  Parse them, extracting
            the attribute substitutions accessed via the replace method.
    """

    def __init__(self, directory_list: Optional[List[str]] = None) -> None:
        self._replacements = dict()
        self._expressions = list()
        if directory_list is None:
            return
        for directory in directory_list:
            files = glob.glob(os.path.join(directory, "**/*.xml"), recursive=True)
            for filename in files:
                try:
                    with open(filename, "r") as f:
                        data = f.read()
                    root = ElementTree.fromstring(data)
                except Exception as e:
                    raise RuntimeError(f"Unable to read override file: {filename} : {e}")
                for override in root.findall(".//override"):
                    namespace = override.get("namespace", "")
                    if namespace:
                        for child in override:
                            attribute = child.tag
                            text = child.text
                            key = f"{namespace}:{attribute}"
                            globlist = "?*[]"
                            # break up the items into a hash dict and a list of re expressions
                            if any(c in key for c in globlist):
                                exp = fnmatch.translate(key)
                                reobj = re.compile(exp)
                                self._expressions.append((reobj, text))
                            else:
                                self._replacements[key] = text

    def replace(self, namespace: str, attribute: str, default: Optional[str] = None) -> str:
        """Find the replacement for an attribute
        For a given namespace and attribute, get the replacement string (or return
        the default value).

        Wildcards are supported in the replacement XML, one could specify:

        <override namespace="ensight.objs.ENS_PART.ENS_PLIST_KEY_SEL_*">
        <description>
        </description>
        </override>

        That would match ensight.objs.ENS_PART.ENS_PLIST_KEY_SEL_3 description
        attribute.  Other common replacements include "paramnames" and "signature".

        Args:
            namespace:
                The namespace to perform replacement for
            attribute:
                The XML attribute to look up a replacement string for,
                for example "description"
            default:
                In the case of no known replacement, return this value
        Returns:
            The replacement string or the default parameter
        """
        # The keys in the replacement dictionary may include fnmatch wildcards.
        # So, we walk the keys, looking for the first match.
        target = f"{namespace}:{attribute}"
        value = self._replacements.get(target, None)
        if value is not None:
            return value
        for reobj, value in self._expressions:
            if reobj.match(target):
                return value
        return default


class ProcessAPI:
    """Convert an XML API representation into classes

    Args:
        data:
            XML string
        overrides:
            An XMLOverrides instance used to replace XML fields from other XML files
    """

    def __init__(self, data: str, overrides: XMLOverrides = None) -> None:
        self._root: ElementTree.Element = ElementTree.fromstring(data)
        self._overrides: XMLOverrides = overrides
        self._dirname: str = ""
        self._imports: str = ""
        self._custom_names = []
        self._custom_names.append("getattr")
        self._custom_names.append("getattrs")
        self._custom_names.append("setattr")
        self._custom_names.append("setattrs")
        self._custom_names.append("attrinfo")
        self._custom_names.append("attrissensitive")
        self._custom_names.append("attrtree")
        self._custom_names.append("setattr_begin")
        self._custom_names.append("setattr_end")
        self._custom_names.append("setattr_status")
        self._custom_names.append("setmetatag")
        self._custom_names.append("hasmetatag")
        self._custom_names.append("getmetatag")
        self._custom_names.append("destroy")
        self._custom_names.append("__init__")
        self._custom_names.append("pyref")
        self._custom_names.append("pyunref")
        self._custom_names.append("cmdfromattr")
        # This one is odd.  The problem is that ENS_GLOBALS.create_group() returns
        # a proxy object that owns the C++ object.  What happens is that the object
        # is created in the EnSight Python, the proxy binding is passed back to
        # pyensight and then the object goes out of scope in EnSight and is destroyed.
        # For the present, we do not allow this method to be exposed.
        self._custom_names.append("create_group")
        # api_assets_file is the string holding the text that will be written
        # in the assets file for unit testing
        self.api_assets_file = ""

    def _replace(
        self,
        namespace: str,
        attribute: str = "description",
        default: Optional[str] = None,
        indent: str = "",
        simple: bool = False,
    ) -> Any:
        """Allow replacement of a given attribute for a given namespace
        When looking up an attribute for a given node namespace, allow for
        external replacement of a specific attribute.  Note: this is presently
        only used for 'description' attributes.

        Args:
            namespace:
                The namespace for the query
            attribute:
                The name of the attribute to be considered
            default:
                The default value to be returned if no replacement is to be made
            indent:
                This prefix should be used for all lines after the first line.
            simple:
                If True, no post-processing will be performed.
        Returns:
            The attribute replacement
        """
        if self._overrides is None:
            return default
        value = self._overrides.replace(namespace, attribute, default)
        if type(value) == str:
            if simple:
                return value.strip().replace("\r", "").replace("\n", "")
            lines = value.strip().replace("\r", "").split("\n")
            tmp_indent = ""
            value = ""
            for line in lines:
                value += tmp_indent
                value += line + "\n"
                tmp_indent = indent
        return value

    @staticmethod
    def _cap1(s: Optional[str]) -> Optional[str]:
        if s:
            return s[0].upper() + s[1:]
        return s

    @staticmethod
    def _process_variable(node: ElementTree.Element, indent: str = "") -> str:
        """Process <variable> tag

        Variable tags are converted into class members
        """
        var_type = node.get("type", "Any")
        if var_type.startswith("ENS_"):
            var_type = f"Type[{var_type}]"
        s = f"{indent}self.{node.get('name')}: {var_type}"
        if node.text:
            if var_type == "str":
                s += f" = '{node.text}'"
            else:
                s += f" = {node.text}"
        return s + "\n"

    @staticmethod
    def _process_argument(node: ElementTree.Element) -> str:
        """Process <argument> tag

        Argument tags are placed inside of member function bindings
        """
        arg_type = node.get("type", "Any")
        if arg_type == "var":
            arg_type = "Any"
        name = node.get("name")
        s = f"{name}: {arg_type}"
        if node.text:
            if arg_type == "str":
                s += f" = '{node.text}'"
            else:
                s += f" = {node.text}"
        return s

    @staticmethod
    def _is_unknown_function(node) -> Optional[str]:
        """Handle unknown functions like ensight.query_xy_create()

        Definition: one arg named "args" of type "any" and no return
        arg. In this case, generate *args, **kwargs generic bindings.

        """
        num_args = 0
        for child in node:
            if child.tag == "return":
                return False
            elif child.tag == "argument":
                if child.get("type") != "Any":
                    return False
                num_args += 1
                if num_args > 1:
                    return False
        return True

    def _process_method(
        self, node: ElementTree.Element, indent: str = "", classname: str = ""
    ) -> str:
        """Process <method> tag

        Map a method tag to a 'def' member function
        """
        # if the method is an "end" method, suppress it as the Python
        # bindings only use the "begin" methods
        if node.get("tbl", "") == "0e":
            return ""

        # if it is a "begin" method, the parse structure is different (similar to the "end"
        # suppression case).  Anyway, treat these like the "unknown" case and allow *args
        if node.get("tbl", "") == "0b":
            return self._process_undefined_callable(node, indent=indent, classname=classname)

        # if this is not command language and unknown, then it can be handled by
        # _process_undefined_callable().
        if (node.get("tbl", None) is None) and self._is_unknown_function(node):
            return self._process_undefined_callable(node, indent=indent, classname=classname)

        # regular processing, using the argument and return child nodes
        s = "\n"
        s += f"{indent}def {node.get('name')}(self"
        ret = ""
        arg_names = []
        add_kwargs = False
        if node.get("tbl", None):
            for child in node:
                if child.tag == "return":
                    ret = child.get("type")
                elif child.tag == "argument":
                    arg = self._process_argument(child)
                    arg_names.append(f"{{repr({child.get('name')})}}")
                    s += ", "
                    s += f"{arg}"
            if ret:
                s += f") -> {ret}:\n"
            else:
                s += "):\n"
            indent += "    "
            desc = node.get("description", "")
            desc = self._replace(node.get("ns"), default=desc, indent=indent)
            if desc:
                desc = self._cap1(desc)
                s += f'{indent}"""{desc}\n'
                s += f'{indent}"""\n'
            s += f"{indent}cmd = f'''"
            s += node.get("ns") + "("
            s += ",".join(arg_names)
            s += ")'''\n"
            s += f"{indent}return self._session.cmd(cmd)\n"
        method_name = node.get("name")
        arg_string = ""
        if arg_names:
            arg_string = "1"
        for _ in range(len(arg_names) - 1):
            arg_string += ",1"
        if add_kwargs is True:
            arg_string += ",0=0"
        api_name = node.get("ns") + "(" + arg_string + ")"
        self.api_assets_file += f"{classname},{method_name},,{api_name}\n"
        return s

    def _process_undefined_callable(
        self,
        node: ElementTree.Element,
        indent: str = "",
        classname: str = "",
        object_method: bool = False,
    ) -> str:
        """Generate bindings for a callable w/o explicit parameter description

        The callable can be an object method or a general function (which is mapped to an
        object method in the pyensight scheme for mapping modules into classes).

        Args:
            node:
                The node in the XML API description
            indent:
                The current output text indent string
            classname:
                If a specific class, the name of the class
            object_method:
                If True, this is a method on an ENS_OBJ subclass and may reference
                self._remote_obj() to generate a "wrap_id()" string at runtime.

        Returns:
            The generated Python binding source code or an empty string (on failure).
        """
        name = node.get("name")
        if name in self._custom_names:
            # if not object_method:
            #    self.api_assets_file += f",{name},ensight.objs.wrap_id(1).{name}{1}"
            return ""
        new_indent = indent + "    "
        # get the namespace for the function
        namespace = node.get("ns")
        # get the description, potentially with substitution
        desc = node.get("description", "")
        desc = self._replace(namespace, default=desc, indent=new_indent)
        # signature is '(param:type, param2:type, ...) -> type'
        # paramnames is '[param, param2 ...]' if a param name ends with '=' it is a keyword
        signature = "(*args, **kwargs) -> Any"
        paramnames = self._replace(namespace, "paramnames", None, simple=True)
        if paramnames is not None:
            signature = self._replace(namespace, "signature", signature, simple=True)
            paramnames = eval(paramnames)
        signature = "(self, " + signature[1:]
        code = self._replace(namespace, "code", default=None, indent=new_indent)
        # Start recording
        s = "\n"
        s += f"{indent}def {name}{signature}:\n"
        if desc:
            desc = self._cap1(desc)
            s += f'{new_indent}"""{desc}\n'
            s += f'{new_indent}"""\n'
        if code:
            s += new_indent + code
            return s  # TODO: for the moment, code replacement blocks are not auto-tested
        else:
            if object_method:
                s += f'{new_indent}arg_obj = f"{{self._remote_obj()}}"\n'
            s += f"{new_indent}arg_list = []\n"
            # arguments
            if paramnames is not None:
                for p in [s for s in paramnames if not s.endswith("=")]:
                    s += f"{new_indent}arg_list.append({p}.__repr__())\n"
            else:
                s += f"{new_indent}for arg in args:\n"
                s += f"{new_indent}    arg_list.append(arg.__repr__())\n"
            # keywords
            if paramnames is not None:
                for p in [s for s in paramnames if s.endswith("=")]:
                    s += f'{new_indent}arg_list.append(f"{p[:-1]}={{{p[:-1]}.__repr__()}}")\n'
            else:
                s += f"{new_indent}for key, value in kwargs.items():\n"
                s += f'{new_indent}    arg_list.append(f"{{key}}={{value.__repr__()}}")\n'
            # build the command
            s += f'{new_indent}arg_string = ",".join(arg_list)\n'
            if object_method:
                s += f'{new_indent}cmd = f"{{arg_obj}}.{name}({{arg_string}})"\n'
            else:
                s += f'{new_indent}cmd = f"{namespace}({{arg_string}})"\n'
            s += f"{new_indent}return self._session.cmd(cmd)\n"

        if object_method:
            if "__init__" not in name:
                api_name = f"ensight.objs.wrap_id(1).{name}(1,0=0)"
                if paramnames is not None:
                    api_name = f"ensight.objs.wrap_id(1).{name}("
                    for _ in [s for s in paramnames if not s.endswith("=")]:
                        api_name += "1,"
                    for p in [s for s in paramnames if s.endswith("=")]:
                        api_name += f"{p}0,"
                    if api_name.endswith(","):
                        api_name = api_name[:-1]
                    api_name += ")"
                self.api_assets_file += f"{classname},{name},{api_name}\n"
        else:
            api_name = f"{namespace}(1,0=0)"
            if paramnames is not None:
                api_name = f"{namespace}("
                for _ in [s for s in paramnames if not s.endswith("=")]:
                    api_name += "1,"
                for p in [s for s in paramnames if s.endswith("=")]:
                    api_name += f"{p}0,"
                if api_name.endswith(","):
                    api_name = api_name[:-1]
                api_name += ")"
            self.api_assets_file += f"{classname},{name},,{api_name}\n"

        return s

    def _process_property(
        self, node: ElementTree.Element, indent: str = "", classname: str = ""
    ) -> str:
        """Process a <property> tag

        Generate the property getter/setter for the class property
        """
        name = node.get("name")
        desc = node.get("description")
        value_type = node.get("type")
        # use the actual class (this is correct for Python 3.9 and higher)
        if sys.version_info >= (3, 10, 0):
            value_type = value_type.replace("'ensobjlist'", "ensobjlist")
        else:
            # for 3.7 and 3.8, make do with "List"
            value_type = value_type.replace("'ensobjlist'", "List")
            value_type = value_type.replace("ensobjlist", "List")
        read_only = node.get("ro", "0")
        indent2 = indent + "    "
        # Check for enum values
        enums = None
        for child in node:
            if child.tag == "enums":
                entry = dict(
                    name=child.get("name"), desc=child.get("description"), value=child.get("value")
                )
                if enums is None:
                    enums = []
                enums.append(entry)
        # range string
        limits = ["[inf", "inf]"]
        has_limits = False
        for child in node:
            # <minvalue strict="1" value="0.0"/>
            if child.tag == "minvalue":
                strict = child.get("strict", "0")
                value = child.get("value", "inf")
                s = "["
                if strict != "0":
                    s = "("
                limits[0] = s + value
                has_limits = True
            # <maxvalue strict="1" value="0.0"/>
            if child.tag == "maxvalue":
                strict = child.get("strict", "0")
                value = child.get("value", "inf")
                s = "]"
                if strict != "0":
                    s = ")"
                limits[1] = value + s
                has_limits = True
        # Add parenthetical comment
        if (read_only == "1") or has_limits:
            desc += " ("
            if read_only == "1":
                desc += "read-only"
                if has_limits:
                    desc += ","
            if has_limits:
                desc += "Range: " + ", ".join(limits)
            desc += ")"
        # Add enums to the description
        if enums is not None:
            enums = sorted(enums, key=lambda d: d["value"])
            desc += "\n\n"
            desc += f"{indent2}Valid values include:\n"
            desc += "\n"
            for enum in enums:
                desc += f"{indent2}* ensight.objs.enums.{enum['name']} "
                desc += f"({enum['value']}) - {enum['desc']}\n"
            desc += "\n"
        # Allow override
        desc = self._replace(node.get("ns"), default=desc, indent=indent2)
        desc = self._cap1(desc)
        # Ok, Sphinx refuses to document an attribute in all caps and EnSight uses them a lot
        # Also, the EnSight API allows both upper and lower.  So, we register both the upper
        # and lower property names if the incoming name is uppercase.  Sphinx will document
        # the lowercase one, but both work.
        s = ""
        num_loops = 1
        if name.isupper():
            num_loops = 2
        enum_name = f"self._session.ensight.objs.enums.{name}"
        comment = ""
        for _ in range(num_loops):
            s += "\n"
            s += f"{indent}@property\n"
            s += f"{indent}def {name}(self) -> {value_type}:\n"
            s += f'{indent2}"""{desc}\n'
            if comment:
                s += f"{indent2}{comment}\n"
            s += f'{indent2}"""\n'
            s += f"{indent2}return self.getattr({enum_name})\n"
            if read_only == "0":
                s += "\n"
                s += f"{indent}@{name}.setter\n"
                s += f"{indent}def {name}(self, value: {value_type}) -> None:\n"
                s += f"{indent2}self.setattr({enum_name}, value)\n"
            name = name.lower()
            comment = (
                f"Note: both '{name.lower()}' and '{name.upper()}' property names are supported."
            )
        self.api_assets_file += f"objs,{classname},{name.upper()},EMPTY\n"
        if num_loops > 1:
            self.api_assets_file += f"objs,{classname},{name.lower()},EMPTY\n"
        if read_only == "0":
            self.api_assets_file += f"objs,{classname},{name.upper()},SETTER\n"
            if num_loops > 1:
                self.api_assets_file += f"objs,{classname},{name.lower()},SETTER\n"
        return s

    def _process_class(self, node: ElementTree.Element, indent: str = "") -> str:
        """Process a <class> tag

        Generate the proxy class object for the ENSOBJ subclass
        """
        classname = node.get("name")
        superclass = node.get("super", "ENSOBJ")
        # the new class
        s = f'"""{classname.lower()} module\n'
        s += "\n"
        s += f"The {classname.lower()} module provides a proxy interface to EnSight {classname} "
        s += "instances\n"
        s += "\n"
        s += '"""\n'
        s += "from ansys.pyensight.session import Session\n"
        s += "from ansys.pyensight.ensobj import ENSOBJ\n"
        s += "from ansys.pyensight import ensobjlist\n"
        if superclass != "ENSOBJ":
            s += f"from ansys.pyensight.{superclass.lower()} import {superclass}\n"
        s += "from typing import Any, List, Type, Union, Optional, Tuple\n"
        s += "\n\n"
        s += f"{indent}class {classname}({superclass}):\n"
        indent += "    "
        s += f'{indent}"""'
        s += f"This class acts as a proxy for the EnSight Python class {node.get('ns')}\n"
        s += "\n"
        s += f"{indent}Args:\n"
        s += f"{indent}    \\*args:\n"
        s += f"{indent}        Superclass ({superclass}) arguments\n"
        s += f"{indent}    \\**kwargs:\n"
        s += f"{indent}        Superclass ({superclass}) keyword arguments\n"
        # s += "__ATTRIBUTES__"
        s += "\n"
        s += f'{indent}"""\n'
        s += "\n"
        s += f"{indent}def __init__(self, *args, **kwargs) -> None:\n"
        s += f"{indent}    super().__init__(*args, **kwargs)\n"
        s += f"{indent}    self._update_attr_list(self._session, self._objid)\n"
        s += "\n"
        s += f"{indent}@classmethod\n"
        s += f"{indent}def _update_attr_list(cls, session: 'Session', id: int) -> None:\n"
        s += f"{indent}    if hasattr(cls, 'attr_list'):\n"
        s += f"{indent}        return\n"
        s += f"{indent}    cmd = session.remote_obj(id) + '.__ids__'\n"
        s += f"{indent}    cls.attr_list = session.cmd(cmd)\n"
        s += "\n"
        s += f"{indent}@property\n"
        s += f"{indent}def objid(self) -> int:  # noqa: N802\n"
        s += f'{indent}    """\n'
        s += f"{indent}    Return the EnSight object proxy ID (__OBJID__).\n"
        s += f'{indent}    """\n'
        s += f"{indent}    return self._objid\n"
        self.api_assets_file += f"objs,{classname},objid,EMPTY\n"
        self.api_assets_file += f"objs,{classname},_update_attr_list,None\n"
        self.api_assets_file += f"objs,{classname},_remote_obj,ensight.objs.wrap_id(1)\n"
        attributes = ""
        for child in node:
            if child.tag == "property":
                name = child.get("name")
                desc = child.get("description")
                desc = self._cap1(desc)
                prop_type = child.get("type", "Any")
                if name == "__class__":
                    # this is actually a bug in the ENSOBJ EnSight bindings, don't propagate it
                    continue
                elif name == "__ids__":
                    desc = "A list of the attribute ids supported by this class"
                attributes += f"{indent}    {name} ({prop_type}):\n"
                attributes += f"{indent}        {desc}\n"
                attributes += "\n"
                # __class__ is a legacy bug and __OBJID__ handled in superclass
                if name not in ("__class__", "__OBJID__", "__ids__"):
                    s += self._process_property(child, indent, classname=classname)
            elif child.tag == "method":
                if child.get("unknownsignature", "0") == "1":
                    # in some cases, we have no information about the method
                    s += self._process_undefined_callable(
                        child, indent=indent, classname="objs," + classname, object_method=True
                    )
                else:
                    # TODO: handle class specific methods
                    s += self._process_undefined_callable(
                        child, indent=indent, classname="objs," + classname, object_method=True
                    )
        if attributes:
            attributes = f"\n{indent}Attributes:\n" + attributes + "\n"
        s = s.replace("__ATTRIBUTES__", attributes)
        filename = classname.lower() + ".py"
        pathname = os.path.join(self._dirname, filename)
        with open(pathname, "w", encoding="utf-8") as fp:
            fp.write(s)
        return f"from ansys.pyensight.{classname.lower()} import {classname}\n"

    def _process_module(self, node: ElementTree.Element, indent: str = "") -> str:
        """Process a <module> tag

        Module tags are converted into classes
        """
        s = "\n\n"
        s += f"{indent}class {node.get('name')}:\n"
        indent += "    "
        desc = node.get("description", f"class wrapper for EnSight {node.get('name')} module")
        desc = self._replace(node.get("ns"), default=desc, indent=indent)
        desc = self._cap1(desc)
        s += f'{indent}"""{desc}\n'
        s += f"{indent}This class acts as a proxy for the EnSight Python module {node.get('ns')}\n"
        s += "__ATTRIBUTES__"
        s += f'{indent}"""\n'
        s += f"{indent}def __init__(self, session: Session):\n"
        s += f"{indent}    self._session = session\n"
        attributes = ""
        # walk the children
        methods = ""
        classes = ""
        for child in node:
            if child.tag == "variable":
                s += self._process_variable(child, indent=f"{indent}    ")
                prop_type = child.get("type", "Any")
                attributes += f"{indent}    {child.get('name')} ({prop_type}):\n"
                attributes += f"{indent}        Instance specific constant\n\n"
            elif child.tag == "module":
                # Prepend the submodule
                classname = node.get("name")
                name = child.get("name")
                s = self._process_module(child) + s
                # add an instance of the class to the current class
                s += f"{indent}    self.{name}: '{name}' = {name}(self._session)\n"
                attributes += f"{indent}    {name}:\n"
                attributes += f"{indent}        EnSight module instance class\n\n"
            elif child.tag == "method":
                if child.get("unknownsignature", "0") == "1":
                    classname = node.get("name")
                    methods += self._process_undefined_callable(
                        child, indent=indent, classname=classname
                    )
                else:
                    # Likely a command language method
                    classname = node.get("name")
                    methods += self._process_method(child, indent=indent, classname=classname)
            elif child.tag == "class":
                classname = child.get("name")
                # ENSOBJ and ensobjlist are hand-crafted
                if classname not in ["ENSOBJ", "ensobjlist"]:
                    attributes += f"{indent}    {classname} ({classname}):\n"
                    attributes += f"{indent}        EnSight {classname} proxy class\n\n"
                    self._imports += self._process_class(child)
                    classes += f"{indent}    self.{classname}: Type[{classname}] = {classname}\n"

        s += classes
        s += methods
        if attributes:
            attributes = f"\n{indent}Attributes:\n" + attributes + "\n"
        return s.replace("__ATTRIBUTES__", attributes)

    def process(self, dirname: str, filename: str) -> None:
        self._dirname = dirname
        self._imports = ""
        (name, _) = os.path.splitext(os.path.basename(filename))
        s = f'"""Module {name}\n'
        s += f"Autogenerated from: {name}.xml at {datetime.datetime.now().isoformat()}\n"
        s += '"""\n'
        s += "from ansys.pyensight import Session\n"
        s += "from ansys.pyensight.ensobj import ENSOBJ\n"
        s += "from ansys.pyensight import ensobjlist\n"
        s += "ENSIMPORTS"
        s += "from typing import Any, List, Type, Union, Optional, Tuple\n"
        for child in self._root:
            if child.tag == "module":
                s += self._process_module(child)
                s += "\n\n"
        s = s.replace("ENSIMPORTS", self._imports)
        with open(filename, "w") as f:
            f.write(s)
        root = os.path.dirname(os.path.dirname(__file__))
        assets_file_name = os.path.join(root, "tests", "unit_tests", "ensight_api_test_assets.txt")
        with open(assets_file_name, "w") as assets_file:
            assets_file.write(self.api_assets_file)


def generate_stub_api() -> None:
    """Build the EnSight API bindings

    Pull the .xml file from the archive and run the tool on it.
    """
    root = os.path.dirname(__file__)
    os.chdir(root)

    # Get the default Ansys version number
    sys.path.append("../src")
    from ansys.pyensight._version import DEFAULT_ANSYS_VERSION, VERSION

    version = DEFAULT_ANSYS_VERSION

    print(f"Generating API v{DEFAULT_ANSYS_VERSION} bindings for release {VERSION}")

    # cleanup old files
    for filename in glob.glob("*.xml"):
        os.unlink(filename)
    target_dir = "../src/ansys/pyensight"

    # get the API file(s)
    api_uris = [f"https://s3.amazonaws.com/www3.ensight.com/build/v{version}/ensight_api.xml"]
    for uri in api_uris:
        result = requests.get(uri)
        if not result.ok:
            raise RuntimeError(f"URL fetch error: {result.status_code} ({uri})")
        api_name = os.path.basename(uri)
        with open(api_name, "w", encoding="utf8") as fp:
            fp.write(result.text)
        overrides = XMLOverrides(["../doc/replacements"])
        generator = ProcessAPI(result.text, overrides=overrides)
        outname = os.path.join(target_dir, api_name.replace(".xml", ".py"))
        generator.process(target_dir, outname)


def generate() -> None:
    generate_stub_api()


if __name__ == "__main__":
    generate()
