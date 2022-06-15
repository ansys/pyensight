"""Generate .py files from current EnSight .proto files

Usage
-----

`python grpc_bindings.py`
"""
import glob
import os.path
import sys

import requests


def generate_bindings() -> None:
    """Build the EnSight gRPC interface

    Pull the .proto file(s) from the archive and run the grpc tools on it.
    """
    root = os.path.dirname(__file__)
    os.chdir(root)

    # Get the default Ansys version number
    sys.path.append("../src")
    from ansys import pyensight  # pylint: disable=import-outside-toplevel

    version = pyensight.__ansys_version__

    # cleanup old files
    for filename in glob.glob("*.proto"):
        os.unlink(filename)
    target_dir = "../src/ansys/api/ensight/v0"
    os.makedirs(target_dir, exist_ok=True)
    for filename in glob.glob(target_dir + "/ensight_pb2*.py"):
        os.unlink(filename)

    # get the URI
    proto_uris = [
        f"https://s3.amazonaws.com/www3.ensight.com/build/v{version}/ensight.proto"
    ]
    proto_files = []
    for uri in proto_uris:
        result = requests.get(uri)
        if not result.ok:
            raise RuntimeError(f"URL fetch error: {result.status_code} ({uri})")
        proto_name = os.path.basename(uri)
        with open(proto_name, "w", encoding="utf8") as fp:
            fp.write(result.text)
        proto_files.append(proto_name)

    # verify proto tools are installed
    try:
        import grpc_tools  # noqa: F401, E501 # pylint: disable=unused-import, import-outside-toplevel
    except ImportError:
        raise ImportError(
            "Missing ``grpcio-tools`` package. "
            "Install with `pip install grpcio-tools`"
        )

    # Build the Python gRPC bindings
    os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "cpp"
    cmd = f'"{sys.executable}" -m grpc_tools.protoc -I. '
    cmd += f"--python_out={target_dir} "
    cmd += f"--grpc_python_out={target_dir} "
    cmd += " ".join(proto_files)
    if os.system(cmd):
        raise RuntimeError(f"Failed to run:\n\n{cmd}")

    # The protoc command generates *grpc.py files with lines like:
    # import ensight_pb2 as ensight__pb2.  This is a problem as the
    # apis are located in the ansys.api.ensight.v0 namespace.  We
    # will rewrite the file(s) to correct this.
    for grpc_filename in glob.glob(target_dir + "/*_grpc.py"):
        with open(grpc_filename, "rb") as fp:
            data = fp.read()
        data = data.replace(
            b"import ensight_pb2", b"import ansys.api.ensight.v0.ensight_pb2"
        )
        with open(grpc_filename, "wb") as fp:
            fp.write(data)


def generate() -> None:
    generate_bindings()


if __name__ == "__main__":
    generate()
