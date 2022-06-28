"""Generate .py files from current EnSight API .xml description

Usage
-----

`python generate_stub_api.py`
"""
import datetime
import glob
import os.path
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

    Args:
        directory_list:
            A list of directories to scan for .xml files.  Parse them, extracting
            the attribute substitutions accessed via the replace method.
    """

    def __init__(self, directory_list: Optional[List[str]] = None) -> None:
        self._replacements = dict()
        if directory_list is None:
            return
        for directory in directory_list:
            files = glob.glob(os.path.join(directory, "**/*.xml"), recursive=True)
            for filename in files:
                with open(filename, "r") as f:
                    data = f.read()
                root = ElementTree.fromstring(data)
                for override in root.findall(".//override"):
                    namespace = override.get("namespace", "")
                    if namespace:
                        for child in override:
                            attribute = child.tag
                            text = child.text
                            self._replacements[f"{namespace}:{attribute}"] = text

    def replace(self, namespace: str, attribute: str, default: Optional[str] = None) -> str:
        """Find the replacement for an attribute
        For a given namespace and attribute, get the replacement string (or return
        the default value).
        Args:
            namespace:
                The namespace to perform replacement for
            attribute:
                The attribute to look up a replacement string for
            default:
                In the case of no known replacement, return this value
        Returns:
            The replacement string or the default parameter
        """
        return self._replacements.get(f"{namespace}:{attribute}", default)


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
        self._overrides = overrides

    def _replace(
        self,
        namespace: str,
        attribute: str = "description",
        default: Optional[str] = None,
        indent: str = "",
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
        Returns:
            The attribute replacement
        """
        if self._overrides is None:
            return default
        value = self._overrides.replace(namespace, attribute, default)
        if type(value) == str:
            lines = value.strip().replace("\r", "").split("\n")
            tmp_indent = ""
            value = ""
            for line in lines:
                value += tmp_indent
                value += line + "\n"
                tmp_indent = indent
        return value

    @staticmethod
    def _cap1(s: str):
        return s[0].upper() + s[1:]

    @staticmethod
    def _process_variable(node: ElementTree.Element, indent: str = ""):
        """Process <variable> tag

        Variable tags are converted into class members
        """
        var_type = node.get("type", "Any")
        s = f"{indent}self.{node.get('name')}: {var_type}"
        if node.text:
            if var_type == "str":
                s += f" = '{node.text}'"
            else:
                s += f" = {node.text}"
        return s + "\n"

    @staticmethod
    def _process_argument(node: ElementTree.Element):
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

    def _process_method(self, node: ElementTree.Element, indent: str = ""):
        """Process <method> tag

        Map a method tag to a 'def' member function
        """
        # if the method is an "end" method, suppress it as the Python
        # bindings only use the "begin" methods
        if node.get("tbl", "") == "0e":
            return ""
        # regular processing
        s = "\n"
        s += f"{indent}def {node.get('name')}(self"
        ret = ""
        arg_names = []
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
        return s

    def _process_module(self, node: ElementTree.Element, indent: str = ""):
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
        for child in node:
            if child.tag == "variable":
                s += self._process_variable(child, indent=f"{indent}    ")
                attributes += f"{indent}    {child.get('name')}:\n"
                attributes += f"{indent}        Instance specific constant\n"
            elif child.tag == "module":
                # Prepend the submodule
                name = child.get("name")
                s = self._process_module(child) + s
                # add an instance of the class to the current class
                s += f"{indent}    self.{name}: '{name}' = {name}(self._session)\n"
                attributes += f"{indent}    {name}:\n"
                attributes += f"{indent}        EnSight module instance clas\n"
            elif child.tag == "method":
                methods += self._process_method(child, indent=indent)
        s += methods
        if attributes:
            attributes = f"\n{indent}Attributes:\n" + attributes + "\n"
        return s.replace("__ATTRIBUTES__", attributes)

    def process(self, filename: str) -> None:
        (name, _) = os.path.splitext(os.path.basename(filename))
        s = f'"""Module {name}\n'
        s += f"Autogenerated from: {name}.xml at {datetime.datetime.now().isoformat()}\n"
        s += '"""\n'
        s += "from ansys.pyensight import Session\n"
        s += "from typing import Any\n"
        for child in self._root:
            if child.tag == "module":
                s += self._process_module(child)
                s += "\n\n"
        with open(filename, "w") as f:
            f.write(s)


def generate_stub_api() -> None:
    """Build the EnSight API bindings

    Pull the .xml file from the archive and run the tool on it.
    """
    root = os.path.dirname(__file__)
    os.chdir(root)

    # Get the default Ansys version number
    sys.path.append("../src")
    from ansys import pyensight  # pylint: disable=import-outside-toplevel

    version = pyensight.__ansys_version__

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
        generator.process(outname)


def generate() -> None:
    generate_stub_api()


if __name__ == "__main__":
    generate()
