import importlib.metadata as importlib_metadata

DEFAULT_ANSYS_VERSION = "241"
VERSION = importlib_metadata.version(__name__.replace(".", "-"))
