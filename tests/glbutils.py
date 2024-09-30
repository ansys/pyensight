import math
from typing import List, Optional

import numpy
import pygltflib


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
