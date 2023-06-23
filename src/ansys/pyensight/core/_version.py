import os

import toml

root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
toml_file = os.path.join(root, "pyproject.toml")
VERSION = toml.load(toml_file)["project"]["version"]
DEFAULT_ANSYS_VERSION = "241"
