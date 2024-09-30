"""
Global fixtures go here.
"""
import atexit
import math
import subprocess
from typing import List, Optional
from unittest import mock

import ansys.pyensight.core
from ansys.pyensight.core import enshell_grpc, ensight_grpc
from ansys.pyensight.core.dockerlauncher import DockerLauncher
from ansys.pyensight.core.locallauncher import LocalLauncher
from ansys.pyensight.core.session import Session
import numpy
import pygltflib
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    This let's you specify the install path when you run pytest:
    $ pytest tests --install-path "/ansys_inc/v231/CEI/bin/ensight"
    TODO: Default must be set to the one on the CI/CD server.
    """
    parser.addoption(
        "--install-path",
        action="store",
        default=f"/ansys_inc/v{ansys.pyensight.core.__ansys_version__}/",
    )
    parser.addoption("--use-local-launcher", default=False, action="store_true")


@pytest.fixture
def local_launcher_session(pytestconfig: pytest.Config) -> "ansys.pyensight.Session":
    session = LocalLauncher(ansys_installation=pytestconfig.getoption("install_path")).start()
    yield session
    session.close()


def cleanup_docker(request) -> None:
    # Stop and remove 'ensight' and 'ensight_dev' containers. This needs to be deleted
    # once we address the issue in the pyensight code by giving unique names to the containers
    try:
        subprocess.run(["docker", "stop", "ensight"])
        subprocess.run(["docker", "rm", "ensight"])
    except Exception:
        # There might not be a running ensight container. That is fine, just continue
        pass
    try:
        subprocess.run(["docker", "stop", "ensight_dev"])
        subprocess.run(["docker", "rm", "ensight_dev"])
    except Exception:
        # There might not be a running ensight_dev container. That is fine, just continue
        pass


@pytest.fixture
def docker_launcher_session() -> "Session":
    cleanup_docker()
    launcher = DockerLauncher(data_directory=".", use_dev=True)
    launcher.pull()
    session = launcher.start()
    yield session
    session.close()


@pytest.fixture
def enshell_mock():
    mocked_grpc = mock.MagicMock("GRPC")
    mocked_grpc.command = mock.MagicMock("command")
    mocked_grpc.is_connected = lambda: True
    mocked_grpc.connect = mock.MagicMock("execute_connection")
    values_run_command = [
        [0, "set_no_reroute_log"],  # first run, to find the ensight version
        [0, "set_debug_log"],  # second run
        [0, "verbose 3"],
    ]
    mocked_grpc.run_command = mock.MagicMock("enshell run command")
    mocked_grpc.run_command.side_effect = values_run_command.copy()
    path = "/ansys_inc/v345/CEI/bin/ensight"
    cei_home = path.encode("utf-8")
    mocked_grpc.cei_home = lambda: cei_home
    mocked_grpc.ansys_version = lambda: "345"
    mocked_grpc.start_ensight = lambda cmd, env: [0, cmd]
    mocked_grpc.start_other = lambda cmd, extra_env: [0, cmd]
    return mocked_grpc, values_run_command


enve = mock.MagicMock("enve")
ensight = mock.MagicMock("ensight")
_file = mock.MagicMock("ensight_file")
_file.image_format = lambda x: ""
_file.image_file = lambda x: ""
_file.image_window_size = lambda x: ""
_file.image_window_xy = lambda x, y: ""
_file.image_rend_offscreen = lambda x: ""
_file.image_numpasses = lambda x: ""
_file.image_stereo = lambda x: ""
_file.image_screen_tiling = lambda x, y: ""
_file.raytracer_options = lambda x: ""
_file.image_raytrace_it = lambda x: ""
_file.save_image = lambda: ""

ensight.file = _file
img = mock.MagicMock("img")
img.metadata = []
img.variabledata = numpy.zeros(shape=(1, 1))
img.pickdata = numpy.zeros(shape=(1, 1))
img.pixeldata = numpy.zeros(shape=(1, 1))
img.load = mock.MagicMock("load")
ensight.render = lambda x, y, num_samples, enhanced: img
enve.image = lambda: img


@pytest.fixture
@mock.patch.dict("sys.modules", {"ensight": ensight, "enve": enve})
def mocked_session(mocker, tmpdir, enshell_mock) -> "Session":
    cmd_mock = mock.MagicMock("cmd_mock")
    mock_dict = {"a": 1, "b": 2, "c": 3}
    cmd_mock.items = lambda: mock_dict.items()
    mocked_grpc = mock.MagicMock("GRPC")
    mocked_grpc.command = mock.MagicMock("command")
    mocked_grpc.is_connected = lambda: True
    mocked_grpc.connect = mock.MagicMock("execute_connection")
    mocker.patch.object(ensight_grpc, "EnSightGRPC", return_value=mocked_grpc)
    mocker.patch.object(enshell_grpc, "EnShellGRPC", return_value=enshell_mock[0])
    mocker.patch.object(ansys.pyensight.core.Session, "cmd", return_value=cmd_mock)
    session_dir = tmpdir.mkdir("test_dir")
    remote = session_dir.join("remote_filename")
    remote.write("test_html")
    mocker.patch.object(atexit, "register")
    session = Session(
        host="superworkstation",
        install_path="/path/to/darkness",
        secret_key="abcd1234-5678efgh",
        grpc_port=12345,
        html_port=23456,
        ws_port=34567,
        session_directory=session_dir,
        timeout=120.0,
    )
    session._build_utils_interface()
    session._cei_suffix = "345"
    return session


@pytest.fixture
def launch_pyensight_session(tmpdir, pytestconfig: pytest.Config):
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    root = None
    if use_local:
        root = "http://s3.amazonaws.com/www3.ensight.com/PyEnSight/ExampleData"
    if use_local:
        launcher = LocalLauncher(enable_rest_api=True)
    else:
        launcher = DockerLauncher(data_directory=data_dir, use_dev=True, enable_rest_api=True)
    counter = 0
    working = False
    session = None
    while not working and counter < 4:
        try:
            session = launcher.start()
            working = True
            break
        except Exception:
            counter += 1
    return session, data_dir, root


class GLBUtils:
    """General utility functions for working with GLB files"""

    @staticmethod
    def create_glb_file(
        filename: str,
        num_triangles: int = 12,
        size: float = 1.0,
        offset: Optional[List[float]] = None,
        axis_angle: Optional[List[float]] = None,
    ) -> List[float]:
        """Create a simple GLB file of a cube

        Create a simple cube geometry with an arbitrary number of triangles. It is
        centered around 0,0,0 by default and has an edge length of 1.0.   The size
        of the cube can be adjusted using the size arg. After applying the scale
        and rotation, the offset is added to each coordinate.

        Args:
            filename:
                The name of the file (.glb) to be saved.
            num_triangles:
                The target number of triangles for the file.  Default: 12 (simple cube)
            size:
                The length of an edge of the cube. Default: 1.0
            offset:
                An offset to be added to the coordinates of the cube (after the size is applied).
            axis_angle:
                Rotate the cube over the specific axis by an angle in radians: [nx,ny,nz,angle]

        Returns:
            The bounds of the geometry: [minx,miny,minz,maxx,maxy,maxz]
        """
        # n is the number of quads along one axis of the cube.  The number of
        # triangles is then 2 (per quad) * 6 (faces) * n*n (number of quads on a face)
        # Find the smallest N that results in at least num_triangles triangles.
        n = 1
        while (n * n * 2 * 6) < num_triangles:
            n += 1

        # Coordinates + normals
        # 6 faces of n+1 * n+1 points
        points = numpy.zeros([(n + 1) * (n + 1) * 6, 3], dtype="float32")
        normals = numpy.zeros([(n + 1) * (n + 1) * 6, 3], dtype="float32")
        idx = 0
        delta = size / float(n)
        start = -(size * 0.5)
        # bottom face
        z = start
        for j in range(n + 1):
            y = start + j * delta
            for i in range(n + 1):
                x = start + i * delta
                points[idx] = [x, y, z]
                normals[idx] = [0.0, 0.0, 1.0]
                idx += 1
        # top face
        z = start + size
        for j in range(n + 1):
            y = start + j * delta
            for i in range(n + 1):
                x = start + i * delta
                points[idx] = [x, y, z]
                normals[idx] = [0.0, 0.0, -1.0]
                idx += 1
        # left face
        x = start
        for k in range(n + 1):
            z = start + k * delta
            for j in range(n + 1):
                y = start + j * delta
                points[idx] = [x, y, z]
                normals[idx] = [1.0, 0.0, 0.0]
                idx += 1
        # right face
        x = start + size
        for k in range(n + 1):
            z = start + k * delta
            for j in range(n + 1):
                y = start + j * delta
                points[idx] = [x, y, z]
                normals[idx] = [-1.0, 0.0, 0.0]
                idx += 1
        # back face
        y = start
        for k in range(n + 1):
            z = start + k * delta
            for i in range(n + 1):
                x = start + i * delta
                points[idx] = [x, y, z]
                normals[idx] = [0.0, 1.0, 0.0]
                idx += 1
        # front face
        y = start + size
        for k in range(n + 1):
            z = start + k * delta
            for i in range(n + 1):
                x = start + i * delta
                points[idx] = [x, y, z]
                normals[idx] = [0.0, -1.0, 0.0]
                idx += 1
        # Rotate
        if axis_angle:
            m = GLBUtils.rot_from_axis_angle(axis_angle[0:3], axis_angle[3])
            points = numpy.dot(points, m)
        # Translate
        if offset:
            points = points + numpy.array([offset[0], offset[1], offset[2]], dtype="float32")
        # get the bounding box
        vertex_mins = points.min(axis=0)
        vertex_maxs = points.max(axis=0)
        bbox = [
            vertex_mins[0],
            vertex_mins[1],
            vertex_mins[2],
            vertex_maxs[0],
            vertex_maxs[1],
            vertex_maxs[2],
        ]

        # Connectivity
        # 6 faces of n * n * 2 triangles
        triangles = numpy.zeros([n * n * 2 * 6, 3], dtype="uint32")
        idx = 0
        off = 0
        row = n + 1
        # bottom face
        for j in range(n):
            for i in range(n):
                triangles[idx] = [off + i, off + i + row, off + i + row + 1]
                idx += 1
                triangles[idx] = [off + i, off + i + row + 1, off + i + 1]
                idx += 1
            off += row
        off += row
        # top face
        for j in range(n):
            for i in range(n):
                triangles[idx] = [off + i, off + i + 1, off + i + row + 1]
                idx += 1
                triangles[idx] = [off + i, off + i + row + 1, off + i + row]
                idx += 1
            off += row
        off += row
        # left face
        for j in range(n):
            for i in range(n):
                triangles[idx] = [off + i, off + i + row, off + i + row + 1]
                idx += 1
                triangles[idx] = [off + i, off + i + row + 1, off + i + 1]
                idx += 1
            off += row
        off += row
        # right face
        for j in range(n):
            for i in range(n):
                triangles[idx] = [off + i, off + i + 1, off + i + row + 1]
                idx += 1
                triangles[idx] = [off + i, off + i + row + 1, off + i + row]
                idx += 1
            off += row
        off += row
        # back face
        for j in range(n):
            for i in range(n):
                triangles[idx] = [off + i, off + i + 1, off + i + row + 1]
                idx += 1
                triangles[idx] = [off + i, off + i + row + 1, off + i + row]
                idx += 1
            off += row
        off += row
        # front face
        for j in range(n):
            for i in range(n):
                triangles[idx] = [off + i, off + i + row, off + i + row + 1]
                idx += 1
                triangles[idx] = [off + i, off + i + row + 1, off + i + 1]
                idx += 1
            off += row
        off += row

        # Note: this was taken largely from the pygltflib docs
        triangles_binary_blob = triangles.flatten().tobytes()
        points_binary_blob = points.tobytes()
        normals_binary_blob = normals.tobytes()
        blob_size = len(triangles_binary_blob) + len(points_binary_blob) + len(normals_binary_blob)
        gltf = pygltflib.GLTF2(
            scene=0,
            scenes=[pygltflib.Scene(nodes=[0])],
            nodes=[pygltflib.Node(mesh=0)],
            meshes=[
                pygltflib.Mesh(
                    primitives=[
                        pygltflib.Primitive(
                            attributes=pygltflib.Attributes(POSITION=1, NORMAL=2), indices=0
                        )
                    ]
                )
            ],
            accessors=[
                pygltflib.Accessor(
                    bufferView=0,
                    componentType=pygltflib.UNSIGNED_INT,
                    count=triangles.size,
                    type=pygltflib.SCALAR,
                    max=[int(triangles.max())],
                    min=[int(triangles.min())],
                ),
                pygltflib.Accessor(
                    bufferView=1,
                    componentType=pygltflib.FLOAT,
                    count=len(points),
                    type=pygltflib.VEC3,
                    max=points.max(axis=0).tolist(),
                    min=points.min(axis=0).tolist(),
                ),
                pygltflib.Accessor(
                    bufferView=2,
                    componentType=pygltflib.FLOAT,
                    count=len(normals),
                    type=pygltflib.VEC3,
                    max=normals.max(axis=0).tolist(),
                    min=normals.min(axis=0).tolist(),
                ),
            ],
            bufferViews=[
                pygltflib.BufferView(
                    buffer=0,
                    byteLength=len(triangles_binary_blob),
                    target=pygltflib.ELEMENT_ARRAY_BUFFER,
                ),
                pygltflib.BufferView(
                    buffer=0,
                    byteOffset=len(triangles_binary_blob),
                    byteLength=len(points_binary_blob),
                    target=pygltflib.ARRAY_BUFFER,
                ),
                pygltflib.BufferView(
                    buffer=0,
                    byteOffset=len(triangles_binary_blob) + len(points_binary_blob),
                    byteLength=len(normals_binary_blob),
                    target=pygltflib.ARRAY_BUFFER,
                ),
            ],
            buffers=[pygltflib.Buffer(byteLength=blob_size)],
        )
        gltf.set_binary_blob(triangles_binary_blob + points_binary_blob + normals_binary_blob)

        # save as glb or gltf
        gltf.save(filename)

        return bbox

    @staticmethod
    def rot_from_axis_angle(axis: List[float], angle: float) -> numpy.array:
        """Generate a 3x3 rotation matrix from an axis and angle

        Given an axis and an angle, generate the 3x3 rotation matrix it specifies.
        This can be used as:  numpy.dot(points, m)

        Args:
            axis:
                The normalized vector to rotate over (e.g. [0,0,1])
            angle:
                The angle to rotate in radians.

        Returns:
            A 3x3 numpy array.
        """
        matrix = numpy.zeros([3, 3], dtype="float32")

        cost = math.cos(angle)
        sint = math.sin(angle)
        om_cost = 1.0 - cost

        x = axis[0]
        y = axis[1]
        z = axis[2]

        # Update the rotation matrix.
        matrix[0, 0] = cost + x * x * om_cost
        matrix[0, 1] = x * y * om_cost - z * sint
        matrix[0, 2] = x * z * om_cost + y * sint
        matrix[1, 0] = x * y * om_cost + z * sint
        matrix[1, 1] = cost + y * y * om_cost
        matrix[1, 2] = y * z * om_cost - x * sint
        matrix[2, 0] = x * z * om_cost - y * sint
        matrix[2, 1] = y * z * om_cost + x * sint
        matrix[2, 2] = cost + z * z * om_cost

        return matrix


@pytest.fixture
def glb_utilities() -> "GLBUtils":
    return GLBUtils()
