"""
The ``libuserd`` module allows PyEnSight to directly access EnSight
user-defined readers (USERD).  Any file format for which EnSight
uses a USERD interface can be read using this API

Examples
--------

>>> from ansys.pyensight.core import libuserd
>>> userd = libuserd.LibUserd()
>>> userd.initialize()
>>> print(userd.library_version())
>>> datafile = "/example/data/CFX/Axial_001.res"
>>> readers = userd.query_format(datafile)
>>> data = readers[0].read_dataset(datafile)
>>> print(data.parts())
>>> print(data.variables())
>>> userd.shutdown()

"""
import enum
import logging
import os
import platform
import shutil
import subprocess
import tempfile
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union
import uuid
import warnings

from ansys.api.pyensight.v0 import libuserd_pb2, libuserd_pb2_grpc
from ansys.pyensight.core.common import (
    find_unused_ports,
    get_file_service,
    launch_enshell_interface,
    populate_service_host_port,
    pull_image,
)
import grpc
import numpy
import psutil
import requests

try:
    import docker
except ModuleNotFoundError:  # pragma: no cover
    raise RuntimeError("The docker module must be installed for DockerLauncher")
except Exception:  # pragma: no cover
    raise RuntimeError("Cannot initialize Docker")


if TYPE_CHECKING:
    from docker import DockerClient
    from docker.models.containers import Container
    from enshell_grpc import EnShellGRPC

# This code is currently in development/beta state
warnings.warn(
    "The libuserd interface/API is still under active development and should be considered beta.",
    stacklevel=2,
)


class LibUserdError(Exception):
    """
    This class is an exception object raised from the libuserd
    library itself (not the gRPC remote interface).  The associated
    numeric LibUserd.ErrorCode is available via the 'code' attribute.

    Parameters
    ----------
    msg : str
        The message text to be included in the exception.

    Attributes
    ----------
    code : int
        The LibUserd ErrorCodes enum value for this error.
    """

    def __init__(self, msg) -> None:
        super(LibUserdError, self).__init__(msg)
        self._code = libuserd_pb2.ErrorCodes.UNKNOWN
        if msg.startswith("LibUserd("):
            try:
                self._code = int(msg[len("LibUserd(") :].split(")")[0])
            except Exception:
                pass

    @property
    def code(self) -> int:
        """The numeric error code: LibUserd.ErrorCodes"""
        return self._code


class Query(object):
    """
    The class represents a reader "query" instance.  It includes
    the query name as well as the preferred titles.  The ``data``
    method may be used to access the X,Y plot values.

    Parameters
    ----------
    userd
        The LibUserd instance this query is associated with.
    pb
        The protobuffer that represents this object.

    Attributes
    ----------
    id : int
        The id of this query.
    name : str
        The name of this query.
    x_title : str
        String to use as the x-axis title.
    y_title : str
        String to use as the y-axis title.
    metadata : Dict[str, str]
        The metadata for this query.
    """

    def __init__(self, userd: "LibUserd", pb: libuserd_pb2.QueryInfo) -> None:
        self._userd = userd
        self.id = pb.id
        self.name = pb.name
        self.x_title = pb.xTitle
        self.y_title = pb.yTitle
        self.metadata = {}
        for key in pb.metadata.keys():
            self.metadata[key] = pb.metadata[key]

    def __str__(self) -> str:
        return f"Query id: {self.id}, name: '{self.name}'"

    def __repr__(self):
        return f"<{self.__class__.__name__} object, id: {self.id}, name: '{self.name}'>"

    def data(self) -> List["numpy.array"]:
        """
        Get the X,Y values for this query.

        Returns
        -------
        List[numpy.array]
            A list of two numpy arrays [X, Y].
        """
        self._userd.connect_check()
        pb = libuserd_pb2.Query_dataRequest()
        try:
            reply = self._userd.stub.Query_data(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        return [numpy.array(reply.x), numpy.array(reply.y)]


class Variable(object):
    """
    The class represents a reader "variable" instance.  It includes
    information about the variable, including it type (vector, scalar, etc)
    location (nodal, elemental, etc), name and units.

    Parameters
    ----------
    userd
        The LibUserd instance this query is associated with.
    pb
        The protobuffer that represents this object.

    Attributes
    ----------
    id : int
        The id of this variable.
    name : str
        The name of this variable.
    unitLabel : str
        The unit label of this variable, "Pa" for example.
    unitDims : str
        The dimensions of this variable, "L/S" for distance per second.
    location : "LibUserd.LocationType"
        The location of this variable.
    type : "LibUserd.VariableType"
        The type of this variable.
    timeVarying : bool
        True if the variable is time-varying.
    isComplex : bool
        True if the variable is complex.
    numOfComponents : int
        The number of components of this variable.  A scalar is 1 and
        a vector is 3.
    metadata : Dict[str, str]
        The metadata for this query.
    """

    def __init__(self, userd: "LibUserd", pb: libuserd_pb2.VariableInfo) -> None:
        self._userd = userd
        self.id = pb.id
        self.name = pb.name
        self.unitLabel = pb.unitLabel
        self.unitDims = pb.unitDims
        self.location = self._userd.VariableLocation(pb.varLocation)
        self.type = self._userd.VariableType(pb.type)
        self.timeVarying = pb.timeVarying
        self.isComplex = pb.isComplex
        self.interleaveFlag = pb.interleaveFlag
        self.numOfComponents = pb.numOfComponents
        self.metadata = {}
        for key in pb.metadata.keys():
            self.metadata[key] = pb.metadata[key]

    def __str__(self) -> str:
        return f"Variable id: {self.id}, name: '{self.name}', type: {self.type.name}, location: {self.location.name}"

    def __repr__(self):
        return f"<{self.__class__.__name__} object, id: {self.id}, name: '{self.name}'>"


class Part(object):
    """
    This class represents the EnSight notion of a part.  A part is a single mesh consisting
    of a nodal array along with a collection of element specifications.  Methods are provided
    to access the nodes and connectivity as well as any variables that might be defined
    on the nodes or elements of this mesh.

    Parameters
    ----------
    userd
        The LibUserd instance this query is associated with.
    pb
        The protobuffer that represents this object.

    Attributes
    ----------
    id : int
        The id of this part.
    name : str
        The name of this part.
    reader_id : int
        The id of the Reader this part is associated with.
    hints : int
        See: `LibUserd.PartHints`.
    reader_api_version : float
        The API version number of the USERD reader this part was read with.
    metadata : Dict[str, str]
        The metadata for this query.
    """

    def __init__(self, userd: "LibUserd", pb: libuserd_pb2.PartInfo):
        self._userd = userd
        self.index = pb.index
        self.id = pb.id
        self.name = pb.name
        self.reader_id = pb.reader_id
        self.hints = pb.hints
        self.reader_api_version = pb.reader_api_version
        self.metadata = {}
        for key in pb.metadata.keys():
            self.metadata[key] = pb.metadata[key]

    def __str__(self):
        return f"Part id: {self.id}, name: '{self.name}'"

    def __repr__(self):
        return f"<{self.__class__.__name__} object, id: {self.id}, name: '{self.name}'>"

    def nodes(self) -> "numpy.array":
        """
        Return the vertex array for the part.

        Returns
        -------
        numpy.array
            A numpy array of packed values: x,y,z,z,y,z, ...

        Examples
        --------

        >>> part = reader.parts()[0]
        >>> nodes = part.nodes()
        >>> nodes.shape = (len(nodes)//3, 3)
        >>> print(nodes)

        """
        self._userd.connect_check()
        pb = libuserd_pb2.Part_nodesRequest()
        pb.part_id = self.id
        try:
            stream = self._userd.stub.Part_nodes(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        nodes = numpy.empty(0, dtype=numpy.float32)
        for chunk in stream:
            if len(nodes) < chunk.total_size:
                nodes = numpy.empty(chunk.total_size, dtype=numpy.float32)
            offset = chunk.offset
            values = numpy.array(chunk.xyz)
            nodes[offset : offset + len(values)] = values
        return nodes

    def num_elements(self) -> dict:
        """
        Get the number of elements of a given type in the current part.

        Returns
        -------
        dict
            A dictionary with keys being the element type and the values being the number of
            such elements.  Element types with zero elements are not included in the dictionary.

        Examples
        --------

        >>> part = reader.parts()[0]
        >>> elements = part.elements()
        >>> for etype, count in elements.items():
        ...  print(libuserd_instance.ElementType(etype).name, count)

        """
        self._userd.connect_check()
        pb = libuserd_pb2.Part_num_elementsRequest()
        pb.part_id = self.id
        try:
            reply = self._userd.stub.Part_num_elements(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        elements = {}
        for key in reply.elementCount.keys():
            if reply.elementCount[key] > 0:
                elements[key] = reply.elementCount[key]
        return elements

    def element_conn(self, elem_type: int) -> "numpy.array":
        """
        For "zoo" element types, return the part element connectivity for the specified
        element type.

        Parameters
        ----------
        elem_type : int
            The element type.  All but NFACED and NSIDED element types are allowed.

        Returns
        -------
        numpy.array
            A numpy array of the node indices.

        Examples
        --------

        >>> part = reader.parts()[0]
        >>> conn = part.element_conn(libuserd_instance.ElementType.HEX08)
        >>> nodes_per_elem = libuserd_instance.nodes_per_element(libuserd_instance.ElementType.HEX08)
        >>> conn.shape = (len(conn)//nodes_per_elem, nodes_per_elem)
        >>> for element in conn:
        ...  print(element)

        """
        if elem_type >= self._userd.ElementType.NSIDED:
            raise RuntimeError(f"Element type {elem_type} is not valid for this call")
        pb = libuserd_pb2.Part_element_connRequest()
        pb.part_id = self.id
        pb.elemType = elem_type
        try:
            stream = self._userd.stub.Part_element_conn(pb, metadata=self._userd.metadata())
            conn = numpy.empty(0, dtype=numpy.uint32)
            for chunk in stream:
                if len(conn) < chunk.total_size:
                    conn = numpy.empty(chunk.total_size, dtype=numpy.uint32)
                offset = chunk.offset
                values = numpy.array(chunk.connectivity)
                conn[offset : offset + len(values)] = values
        except grpc.RpcError as e:
            error = self._userd.libuserd_exception(e)
            # if we get an "UNKNOWN" error, then return an empty array
            if isinstance(error, LibUserdError):
                if error.code == self._userd.ErrorCodes.UNKNOWN:  # type: ignore
                    return numpy.empty(0, dtype=numpy.uint32)
            raise error
        return conn

    def element_conn_nsided(self, elem_type: int) -> List["numpy.array"]:
        """
        For an N-Sided element type (regular or ghost), return the connectivity information
        for the elements of that type in this part at this timestep.

        Two arrays are returned in a list:

        - num_nodes_per_element : one number per element that represent the number of nodes in that element
        - nodes : the actual node indices

        Arrays are packed sequentially.  Walking the elements sequentially, if the number of
        nodes for an element is 4, then there are 4 entries added to the nodes array
        for that element.

        Parameters
        ----------
        elem_type: int
            NSIDED or NSIDED_GHOST.

        Returns
        -------
        List[numpy.array]
            Two numpy arrays: num_nodes_per_element, nodes
        """
        self._userd.connect_check()
        pb = libuserd_pb2.Part_element_conn_nsidedRequest()
        pb.part_id = self.id
        pb.elemType = elem_type
        try:
            stream = self._userd.stub.Part_element_conn_nsided(pb, metadata=self._userd.metadata())
            nodes = numpy.empty(0, dtype=numpy.uint32)
            indices = numpy.empty(0, dtype=numpy.uint32)
            for chunk in stream:
                if len(nodes) < chunk.nodes_total_size:
                    nodes = numpy.empty(chunk.nodes_total_size, dtype=numpy.uint32)
                if len(indices) < chunk.indices_total_size:
                    indices = numpy.empty(chunk.indices_total_size, dtype=numpy.uint32)
                if len(chunk.nodesPerPolygon):
                    offset = chunk.nodes_offset
                    values = numpy.array(chunk.nodesPerPolygon)
                    nodes[offset : offset + len(values)] = values
                if len(chunk.nodeIndices):
                    offset = chunk.indices_offset
                    values = numpy.array(chunk.nodeIndices)
                    indices[offset : offset + len(values)] = values
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        return [nodes, indices]

    def element_conn_nfaced(self, elem_type: int) -> List["numpy.array"]:
        """
        For an N-Faced element type (regular or ghost), return the connectivity information
        for the elements of that type in this part at this timestep.

        Three arrays are returned in a list:

        - num_faces_per_element : one number per element that represent the number of faces in that element
        - num_nodes_per_face : for each face, the number of nodes in the face.
        - face_nodes : the actual node indices

        All arrays are packed sequentially.  Walking the elements sequentially, if the number of
        faces for an element is 4, then there are 4 entries added to the num_nodes_per_face array
        for that element.  Likewise, the nodes for each face are appended in order to the
        face_nodes array.

        Parameters
        ----------
        elem_type: int
            NFACED or NFACED_GHOST.

        Returns
        -------
        List[numpy.array]
            Three numpy arrays: num_faces_per_element, num_nodes_per_face, face_nodes
        """
        self._userd.connect_check()
        pb = libuserd_pb2.Part_element_conn_nfacedRequest()
        pb.part_id = self.id
        pb.elemType = elem_type
        try:
            stream = self._userd.stub.Part_element_conn_nfaced(pb, metadata=self._userd.metadata())
            face = numpy.empty(0, dtype=numpy.uint32)
            npf = numpy.empty(0, dtype=numpy.uint32)
            nodes = numpy.empty(0, dtype=numpy.uint32)
            for chunk in stream:
                if len(face) < chunk.face_total_size:
                    face = numpy.empty(chunk.face_total_size, dtype=numpy.uint32)
                if len(npf) < chunk.npf_total_size:
                    npf = numpy.empty(chunk.npf_total_size, dtype=numpy.uint32)
                if len(nodes) < chunk.nodes_total_size:
                    nodes = numpy.empty(chunk.nodes_total_size, dtype=numpy.uint32)
                if len(chunk.facesPerElement):
                    offset = chunk.face_offset
                    values = numpy.array(chunk.facesPerElement)
                    face[offset : offset + len(values)] = values
                if len(chunk.nodesPerFace):
                    offset = chunk.npf_offset
                    values = numpy.array(chunk.nodesPerFace)
                    npf[offset : offset + len(values)] = values
                if len(chunk.nodeIndices):
                    offset = chunk.nodes_offset
                    values = numpy.array(chunk.nodeIndices)
                    nodes[offset : offset + len(values)] = values
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        return [face, npf, nodes]

    def variable_values(
        self, variable: "Variable", elem_type: int = 0, imaginary: bool = False, component: int = 0
    ) -> "numpy.array":
        """
        Return a numpy array containing the value(s) of a variable.  If the variable is a
        part variable, a single float value is returned.  If the variable is a nodal variable,
        the resulting numpy array will have the same number of values as there are nodes.
        If the variable is elemental, the `elem_type` selects the block of elements to return
        the variable values for (`elem_type` is ignored for other variable types).

        Parameters
        ----------
        variable : Variable
            The variable to return the values for.
        elem_type : int
            Used only if the variable location is elemental, this keyword selects the element
            type to return the variable values for.
        imaginary : bool
            If the variable is of type complex, setting this to True will select the imaginary
            portion of the data.
        component : int
            Select the channel for a multivalued variable type.  For example, if the variable
            is a vector, setting component to 1 will select the 'Y' component.

        Returns
        -------
        numpy.array
            A numpy array or a single scalar float.
        """
        self._userd.connect_check()
        pb = libuserd_pb2.Part_variable_valuesRequest()
        pb.part_id = self.id
        pb.var_id = variable.id
        pb.elemType = elem_type
        pb.varComponent = component
        pb.complex = imaginary
        try:
            stream = self._userd.stub.Part_variable_values(pb, metadata=self._userd.metadata())
            v = numpy.empty(0, dtype=numpy.float32)
            for chunk in stream:
                if len(v) < chunk.total_size:
                    v = numpy.empty(chunk.total_size, dtype=numpy.float32)
                offset = chunk.offset
                values = numpy.array(chunk.varValues)
                v[offset : offset + len(values)] = values
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        return v

    def rigid_body_transform(self) -> dict:
        """
        Return the rigid body transform for this part at the current timestep.  The
        returned dictionary includes the following fields:

        - "translation" : Translation 3 floats x,y,z
        - "euler_value" : Euler values 4 floats e0,e1,e2,e3
        - "center_of_gravity" : Center of transform 3 floats x,y,z
        - "rotation_order" : The order rotations are applied 1 float
        - "rotation_angles" : The rotations in radians 3 floats rx,ry,rz

        Returns
        -------
        dict
            The transform dictionary.
        """
        self._userd.connect_check()
        pb = libuserd_pb2.Part_rigid_body_transformRequest()
        pb.part_id = self.id
        try:
            reply = self._userd.stub.Part_rigid_body_transform(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        out = {
            "translation": numpy.array(reply.transform.translation),
            "euler_value": numpy.array(reply.transform.euler_value),
            "center_of_gravity": numpy.array(reply.transform.center_of_gravity),
            "rotation_order": reply.transform.rotation_order,
            "rotation_angles": numpy.array(reply.transform.rotation_angles),
        }
        return out


class Reader(object):
    """
    This class represents is an instance of a user-defined reader that is actively reading a
    dataset.

    Parameters
    ----------
    userd
        The LibUserd instance this query is associated with.
    pb
        The protobuffer that represents this object.

    Attributes
    ----------
    unit_system : str
        The units system provided by the dataset.
    metadata : Dict[str, str]
        The metadata for this query.

    Notes
    -----
    There can only be one reader active in a single `LibUserd` instance.

    """

    def __init__(self, userd: "LibUserd", pb: libuserd_pb2.Reader) -> None:
        self._userd = userd
        self.unit_system = pb.unitSystem
        self.metadata = {}
        for key in pb.metadata.keys():
            self.metadata[key] = pb.metadata[key]
        self.raw_metadata = pb.raw_metadata

    def parts(self) -> List[Part]:
        """
        Get a list of the parts this reader can access.

        Returns
        -------
        List[Part]
            A list of Part objects.
        """
        self._userd.connect_check()
        pb = libuserd_pb2.Reader_partsRequest()
        try:
            parts = self._userd.stub.Reader_parts(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        out = []
        for part in parts.partList:
            out.append(Part(self._userd, part))
        return out

    def variables(self) -> List[Variable]:
        """
        Get a list of the variables this reader can access.

        Returns
        -------
        List[Variable]
            A list of Variable objects.
        """
        self._userd.connect_check()
        pb = libuserd_pb2.Reader_variablesRequest()
        try:
            variables = self._userd.stub.Reader_variables(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        out = []
        for variable in variables.variableList:
            out.append(Variable(self._userd, variable))
        return out

    def queries(self) -> List[Query]:
        """
        Get a list of the queries this reader can access.

        Returns
        -------
        List[Query]
            A list of Query objects.
        """
        self._userd.connect_check()
        pb = libuserd_pb2.Reader_queriesRequest()
        try:
            queries = self._userd.stub.Reader_queries(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        out = []
        for query in queries.queryList:
            out.append(Query(self._userd, query))
        return out

    def get_number_of_time_sets(self) -> int:
        """
        Get the number of timesets in the dataset.

        Returns
        -------
        int
            The number of timesets.
        """
        self._userd.connect_check()
        pb = libuserd_pb2.Reader_get_number_of_time_setsRequest()
        try:
            reply = self._userd.stub.Reader_get_number_of_time_sets(
                pb, metadata=self._userd.metadata()
            )
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        return reply.numberOfTimeSets

    def timevalues(self, timeset: int = 1) -> List[float]:
        """
        Get a list of the time step values in this dataset.

        Parameters
        ----------
        timeset : int, optional
            The timestep to query (default is 1)

        Returns
        -------
        List[float]
            A list of time floats.
        """
        self._userd.connect_check()
        pb = libuserd_pb2.Reader_timevaluesRequest()
        pb.timeSetNumber = timeset
        try:
            timevalues = self._userd.stub.Reader_timevalues(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        return numpy.array(timevalues.timeValues)

    def set_timevalue(self, timevalue: float, timeset: int = 1) -> None:
        """
        Change the current time to the specified value.  This value should ideally
        be on of the values returned by `timevalues`

        Parameters
        ----------
        timevalue : float
            The time value to change the timestep closest to.
        timeset : int, optional
            The timestep to query (default is 1)
        """
        self._userd.connect_check()
        pb = libuserd_pb2.Reader_set_timevalueRequest()
        pb.timesetNumber = timeset
        pb.timeValue = timevalue
        try:
            _ = self._userd.stub.Reader_set_timevalue(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)

    def set_timestep(self, timestep: int, timeset: int = 1) -> None:
        """
        Change the current time to the specified timestep.  This call is the same as:
        ``reader.set_timevalue(reader.timevalues()[timestep])``.

        Parameters
        ----------
        timestep : int
            The timestep to change to.
        timeset : int, optional
            The timestep to query (default is 1)
        """
        self._userd.connect_check()
        pb = libuserd_pb2.Reader_set_timestepRequest()
        pb.timeSetNumber = timeset
        pb.timeStep = timestep
        try:
            _ = self._userd.stub.Reader_set_timestep(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)

    def is_geometry_changing(self) -> bool:
        """
        Check to see if the geometry in this dataset is changing. over time

        Returns
        -------
        bool
            True if the geometry is changing, False otherwise.
        """
        self._userd.connect_check()
        pb = libuserd_pb2.Reader_is_geometry_changingRequest()
        try:
            reply = self._userd.stub.Reader_is_geometry_changing(
                pb, metadata=self._userd.metadata()
            )
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        return reply.isGeomChanging

    def variable_value(self, variable: "Variable") -> float:
        """
        For any "case" variable (e.g. time), the value of the variable.

        Parameters
        ----------
        variable
            The variable to query.  Note, this variable location must be on a CASE.

        Returns
        -------
        float
            The value of the variable.
        """
        self._userd.connect_check()
        pb = libuserd_pb2.Reader_variable_valueRequest()
        pb.variable_id = variable.id
        try:
            reply = self._userd.stub.Reader_variable_value(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        return reply.value


class ReaderInfo(object):
    """
    This class represents an available reader, before it has been instantiated.
    The read_dataset() function actually tries to open a dataset and returns
    a `Reader` instance that is reading the data.

    The class contains a list of options that can control/configure the reader.
    These include "boolean", "option" and "field" options.  These include defaults
    supplied by the reader. To use these, change the value or value_index fields
    to the desired values before calling `read_dataset`.

    Parameters
    ----------
    userd
        The LibUserd instance this query is associated with.
    pb
        The protobuffer that represents this object.

    Attributes
    ----------
    id : int
        The reader id.
    name : str
        The reader name.
    description : str
        A brief description of the reader and in some cases its operation.
    fileLabel1 : str
        A string appropriate for a "file select" button for the primary filename.
    fileLabel2 : str
        A string appropriate for a "file select" button for the secondary filename.
    opt_booleans : List[dict]
        The boolean user options.
    opt_options : List[dict]
        The option user options suitable for display via an option menu.
    opt_fields : List[dict]
        The field user options suitable for display via a text field.
    """

    def __init__(self, userd: "LibUserd", pb: libuserd_pb2.ReaderInfo):
        self._userd = userd
        self.id = pb.id
        self.name = pb.name
        self.description = pb.description
        self.fileLabel1 = pb.fileLabel1
        self.fileLabel2 = pb.fileLabel2
        self.opt_booleans = []
        for b in pb.options.booleans:
            self.opt_booleans.append(dict(name=b.name, value=b.value, default=b.default_value))
        self.opt_options = []
        for o in pb.options.options:
            values = []
            for v in o.values:
                values.append(v)
            self.opt_options.append(
                dict(name=o.name, values=values, value=o.value_index, default=o.default_value_index)
            )
        self.opt_fields = []
        for f in pb.options.fields:
            self.opt_fields.append(dict(name=f.name, value=f.value, default=f.default_value))

    def read_dataset(self, file1: str, file2: str = "") -> "Reader":
        """
        Attempt to read some files on disk using this reader and the specified options.
        If successful, return an actual reader instance.

        Parameters
        ----------
        file1 : str
            The primary filename (e.g. "foo.cas")
        file2 : str
            An optional secondary filename (e.g. "foo.dat")

        Returns
        -------
        Reader
            An instance of the `Reader` class.
        """
        self._userd.connect_check()
        pb = libuserd_pb2.ReaderInfo_read_datasetRequest()
        pb.filename_1 = file1
        if file2:
            pb.filename_2 = file2
        pb.reader_id = self.id
        options = self._get_option_values()
        for b in options["booleans"]:
            pb.option_values_bools.append(b)
        for o in options["options"]:
            pb.option_values_options.append(o)
        for f in options["fields"]:
            pb.option_values_fields.append(f)
        try:
            reader = self._userd.stub.ReaderInfo_read_dataset(pb, metadata=self._userd.metadata())
        except grpc.RpcError as e:
            raise self._userd.libuserd_exception(e)
        return Reader(self._userd, reader.reader)

    def _get_option_values(self) -> dict:
        """Extract the current option values from the options dictionaries"""
        out = dict()
        booleans = []
        for b in self.opt_booleans:
            booleans.append(b["value"])
        out["booleans"] = booleans
        options = []
        for o in self.opt_options:
            options.append(o["value"])
        out["options"] = options
        fields = []
        for f in self.opt_fields:
            fields.append(f["value"])
        out["fields"] = fields
        return out

    def __str__(self) -> str:
        return f"ReaderInfo id: {self.id}, name: {self.name}, description: {self.description}"

    def __repr__(self):
        return f"<{self.__class__.__name__} object, id: {self.id}, name: '{self.name}'>"


class LibUserd(object):
    """
    LibUserd is the primary interface to the USERD library. All interaction starts at this object.

    Parameters
    ----------
    ansys_installation
        Optional location to search for an Ansys software installation.

    Examples
    --------

    >>> from ansys.pyensight.core import libuserd
    >>> l = libuserd.LibUserd()
    >>> l.initialize()
    >>> readers = l.query_format(r"D:\data\Axial_001.res")
    >>> data = readers[0].read_dataset(r"D:\data\Axial_001.res")
    >>> part = data.parts[0]
    >>> print(part, part.nodes())
    >>> l.shutdown()

    """

    def __init__(
        self,
        ansys_installation: str = "",
        use_docker: bool = False,
        data_directory: Optional[str] = None,
        docker_image_name: Optional[str] = None,
        use_dev: bool = False,
        product_version: Optional[str] = None,
        channel: Optional[grpc.Channel] = None,
        pim_instance: Optional[Any] = None,
        timeout: float = 120.0,
        pull_image_if_not_available: bool = False,
    ):
        self._server_pathname: Optional[str] = None
        self._host = "127.0.0.1"
        self._security_token = str(uuid.uuid1())
        self._grpc_port = 0
        self._server_process: Optional[subprocess.Popen] = None
        self._channel: Optional[grpc.Channel] = None
        self._stub = None
        self._security_file: Optional[str] = None
        # Docker attributes
        self._pull_image = pull_image_if_not_available
        self._timeout = timeout
        self._product_version = product_version
        self._data_directory = data_directory
        self._image_name = "ghcr.io/ansys-internal/ensight"
        if use_dev:
            self._image_name = "ghcr.io/ansys-internal/ensight_dev"
        if docker_image_name:
            self._image_name = docker_image_name
        self._docker_client: Optional["DockerClient"] = None
        self._container: Optional["Container"] = None
        self._enshell: Optional["EnShellGRPC"] = None
        self._pim_instance = pim_instance
        self._enshell_grpc_channel: Optional[grpc.Channel] = channel
        self._pim_file_service: Optional[Any] = None
        self._service_host_port: Dict[str, Tuple[str, int]] = {}
        local_launch = True
        if any([use_docker, use_dev, self._pim_instance]):
            local_launch = False
            self._launch_enshell()
        else:
            # find the pathname to the server
            self._server_pathname = self._find_ensight_server_name(
                ansys_installation=ansys_installation
            )
            if self._server_pathname is None:
                raise RuntimeError("Unable to detect an EnSight server installation.")
        # enums
        self._build_enums()
        if local_launch:
            self._local_launch()
        # Build the gRPC connection
        self._connect()

    def _local_launch(self) -> None:
        """Launch the gRPC server from a local installation."""
        # have the server save status so we can read it later
        with tempfile.TemporaryDirectory() as tmpdirname:
            self._security_file = os.path.join(tmpdirname, "security.grpc")

            # Build the command line
            cmd = [str(self.server_pathname)]
            cmd.extend(["-grpc_server", str(self.grpc_port)])
            cmd.extend(["-security_file", self._security_file])
            env_vars = os.environ.copy()
            if self.security_token:
                env_vars["ENSIGHT_SECURITY_TOKEN"] = self.security_token
            env_vars["ENSIGHT_GRPC_SECURITY_FILE"] = self._security_file
            # start the server
            try:
                self._server_process = subprocess.Popen(
                    cmd,
                    close_fds=True,
                    env=env_vars,
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                )
            except Exception as error:
                raise error

            start_time = time.time()
            while (self._grpc_port == 0) and (time.time() - start_time < 120.0):
                try:
                    # Read the port and security token from the security file
                    with open(self._security_file, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("grpc_port:"):
                                self._grpc_port = int(line[len("grpc_port:") :])
                            elif line.startswith("grpc_password:"):
                                self._security_token = line[len("grpc_password:") :]
                except (OSError, IOError):
                    pass

            # Unable to get the grpc port/password
            if self._grpc_port == 0:
                self.shutdown()
                raise RuntimeError(f"Unable to start the gRPC server ({str(self.server_pathname)})")

    def _build_enums(self) -> None:
        """Build the enums values."""
        values = {}
        for v in libuserd_pb2.ErrorCodes.items():
            values[v[0]] = v[1]
        self.ErrorCodes = enum.IntEnum("ErrorCodes", values)  # type: ignore
        values = {}
        for v in libuserd_pb2.ElementType.items():
            values[v[0]] = v[1]
        self.ElementType = enum.IntEnum("ElementType", values)  # type: ignore
        values = {}
        for v in libuserd_pb2.VariableLocation.items():
            values[v[0]] = v[1]
        self.VariableLocation = enum.IntEnum("VariableLocation", values)  # type: ignore
        values = {}
        for v in libuserd_pb2.VariableType.items():
            values[v[0]] = v[1]
        self.VariableType = enum.IntEnum("VariableType", values)  # type: ignore
        values = {}
        for v in libuserd_pb2.PartHints.items():
            values[v[0]] = v[1]
        self.PartHints = enum.IntEnum("PartHints", values)  # type: ignore

    def _pull_docker_image(self) -> None:
        """Pull the docker image if not available"""
        pull_image(self._docker_client, self._image_name)

    def _check_if_image_available(self) -> bool:
        """Check if the input docker image is available."""
        if not self._docker_client:
            return False
        filtered_images = self._docker_client.images.list(filters={"reference": self._image_name})
        if len(filtered_images) > 0:
            return True
        return False

    def _launch_enshell(self) -> None:
        """Create an enshell entry point and use it to launch a Container."""
        if self._pim_instance:
            self._service_host_port = populate_service_host_port(self._pim_instance, {})
            self._pim_file_service = get_file_service(self._pim_instance)
            self._grpc_port = int(self._service_host_port["grpc_private"][1])
            self._host = self._service_host_port["grpc_private"][0]
        else:
            if not self._data_directory:
                self._data_directory = tempfile.mkdtemp(prefix="pyensight_")
            available = self._check_if_image_available()
            if not available and self._pull_image and not self._pim_instance:
                self._pull_docker_image()
            ports = find_unused_ports(2, avoid=[1999])
            self._service_host_port = {
                "grpc": ("127.0.0.1", ports[0]),
                "grpc_private": ("127.0.0.1", ports[1]),
            }
            self._grpc_port = ports[1]
        if not self._pim_instance:
            self._launch_container()
        self._enshell = launch_enshell_interface(
            self._enshell_grpc_channel, self._service_host_port["grpc"][1], self._timeout
        )
        self._cei_home = self._enshell.cei_home()
        self._ansys_version = self._enshell.ansys_version()
        print("CEI_HOME=", self._cei_home)
        print("Ansys Version=", self._ansys_version)
        grpc_port = self._service_host_port["grpc_private"][1]
        ensight_args = f"-grpc_server {grpc_port}"
        container_env_str = f"ENSIGHT_SECURITY_TOKEN={self._security_token}\n"
        ret = self._enshell.start_ensight_server(ensight_args, container_env_str)
        if ret[0] != 0:  # pragma: no cover
            self._stop_container_and_enshell()  # pragma: no cover
            raise RuntimeError(
                f"Error starting EnSight Server with args: {ensight_args}"
            )  # pragma: no cover

    def _launch_container(self) -> None:
        """Launch a docker container for the input image."""
        self._docker_client = docker.from_env()
        grpc_port = self._service_host_port["grpc"][1]
        private_grpc_port = self._service_host_port["grpc_private"][1]
        ports_to_map = {
            str(self._service_host_port["grpc"][1]) + "/tcp": str(grpc_port),
            str(self._service_host_port["grpc_private"][1]) + "/tcp": str(private_grpc_port),
        }
        enshell_cmd = "-app -v 3 -grpc_server " + str(grpc_port)
        container_env = {
            "ENSIGHT_SECURITY_TOKEN": self.security_token,
        }
        data_volume = {self._data_directory: {"bind": "/data", "mode": "rw"}}

        if not self._docker_client:
            raise RuntimeError("Could not startup docker.")
        self._container = self._docker_client.containers.run(  # pragma: no cover
            self._image_name,
            command=enshell_cmd,
            volumes=data_volume,
            environment=container_env,
            ports=ports_to_map,
            tty=True,
            detach=True,
            auto_remove=True,
            remove=True,
        )

    def _stop_container_and_enshell(self) -> None:
        """Release any additional resources allocated during launching."""
        if self._enshell:
            if self._enshell.is_connected():  # pragma: no cover
                try:
                    logging.debug("Stopping EnShell.\n")
                    self._enshell.stop_server()
                except Exception:  # pragma: no cover
                    pass  # pragma: no cover
                self._enshell = None
        if self._container:
            try:
                logging.debug("Stopping the Docker Container.\n")
                self._container.stop()
            except Exception:
                pass
            try:
                logging.debug("Removing the Docker Container.\n")
                self._container.remove()
            except Exception:
                pass
            self._container = None

        if self._pim_instance is not None:
            logging.debug("Deleting the PIM instance.\n")
            self._pim_instance.delete()
            self._pim_instance = None

    @property
    def stub(self):
        """A libuserd_pb2_grpc.LibUSERDServiceStub instance bound to a gRPC connection channel"""
        return self._stub

    @property
    def server_pathname(self) -> Optional[str]:
        """The pathanme of the detected EnSight server executable used as the gRPC server"""
        return self._server_pathname

    @property
    def security_token(self) -> str:
        """The current gRPC security token"""
        return self._security_token

    @property
    def grpc_port(self) -> int:
        """The current gRPC port"""
        return self._grpc_port

    def __del__(self) -> None:
        self.shutdown()

    @staticmethod
    def _find_ensight_server_name(ansys_installation: str = "") -> Optional[str]:
        """
        Parameters
        ----------
        ansys_installation : str
            Path to the local Ansys installation, including the version
            directory. The default is ``None``, in which case common locations
            are scanned to detect the latest local Ansys installation. The
            ``PYENSIGHT_ANSYS_INSTALLATION`` environmental variable is checked first.

        Returns
        -------
        str
            The first valid ensight_server found or None

        """
        dirs_to_check = []
        if ansys_installation:
            dirs_to_check.append(ansys_installation)

        if "PYENSIGHT_ANSYS_INSTALLATION" in os.environ:
            env_inst = os.environ["PYENSIGHT_ANSYS_INSTALLATION"]
            dirs_to_check.append(env_inst)
            # Note: PYENSIGHT_ANSYS_INSTALLATION is designed for devel builds
            # where there is no CEI directory, but for folks using it in other
            # ways, we'll add that one too, just in case.
            dirs_to_check.append(os.path.join(env_inst, "CEI"))

        if "CEI_HOME" in os.environ:
            env_inst = os.environ["CEI_HOME"]
            dirs_to_check.append(env_inst)

        # Look for most recent Ansys install
        awp_roots = []
        for env_name in dict(os.environ).keys():
            if env_name.startswith("AWP_ROOT"):
                try:
                    version = int(env_name[len("AWP_ROOT") :])
                    # this API is new in 2025 R1 distributions
                    if version >= 251:
                        awp_roots.append(env_name)
                except ValueError:
                    pass
        awp_roots.sort(reverse=True)
        for env_name in awp_roots:
            dirs_to_check.append(os.path.join(os.environ[env_name], "CEI"))

        # check all the collected locations in order
        app_name = "ensight_server"
        if platform.system() == "Windows":
            app_name += ".bat"
        for install_dir in dirs_to_check:
            launch_file = os.path.join(install_dir, "bin", app_name)
            if os.path.isfile(launch_file):
                return launch_file
        return None

    def _is_connected(self) -> bool:
        """Check to see if the gRPC connection is live

        Returns
        -------
        bool
            True if the connection is active.
        """
        return self._channel is not None

    def _connect(self) -> None:
        """Establish the gRPC connection to EnSight

        Attempt to connect to an EnSight gRPC server using the host and port
        established by the constructor.  Note on failure, this function just
        returns, but is_connected() will return False.

        Parameters
        ----------
        timeout: float
            how long to wait for the connection to timeout
        """
        if self._is_connected():
            return
        # set up the channel

        self._channel = grpc.insecure_channel(
            "{}:{}".format(self._host, self._grpc_port),
            options=[
                ("grpc.max_receive_message_length", -1),
                ("grpc.max_send_message_length", -1),
                ("grpc.testing.fixed_reconnect_backoff_ms", 1100),
            ],
        )
        try:
            grpc.channel_ready_future(self._channel).result(timeout=self._timeout)
        except grpc.FutureTimeoutError:  # pragma: no cover
            self._channel = None  # pragma: no cover
            return  # pragma: no cover
        # hook up the stub interface
        self._stub = libuserd_pb2_grpc.LibUSERDServiceStub(self._channel)

    def metadata(self) -> List[Tuple[bytes, Union[str, bytes]]]:
        """Compute the gRPC stream metadata

        Compute the list to be passed to the gRPC calls for things like security
        and the session name.

        Returns
        -------
        List[Tuple[bytes, Union[str, bytes]]]
            A list object of the metadata elements needed in a gRPC call to
            satisfy the EnSight server gRPC requirements.
        """
        ret: List[Tuple[bytes, Union[str, bytes]]] = list()
        s: Union[str, bytes]
        if self._security_token:  # pragma: no cover
            s = self._security_token
            if type(s) == str:  # pragma: no cover
                s = s.encode("utf-8")
            ret.append((b"shared_secret", s))
        return ret

    def libuserd_exception(self, e: "grpc.RpcError") -> Exception:
        """
        Given an exception raised as the result of a gRPC call, return either
        the input exception or a LibUserdError exception object to differentiate
        between gRPC issues and libuserd issues.

        Parameters
        ----------
        e
            The exception raised by a gRPC call.

        Returns
        -------
        Exception
            Either the original exception or a LibUserdError exception instance, depending on
            the original exception message details.
        """
        msg = e.details()
        if msg.startswith("LibUserd("):
            return LibUserdError(msg)
        return e

    def _disconnect(self, no_error: bool = False) -> None:
        """Close down the gRPC connection

        Disconnect all connections to the gRPC server.  Send the shutdown request gRPC command
        to the server first.

        Parameters
        ----------
        no_error
            If true, ignore errors resulting from the shutdown operation.
        """
        if not self._is_connected():  # pragma: no cover
            return
        # Note: this is expected to return an error
        try:
            pb = libuserd_pb2.Libuserd_shutdownRequest()
            self._stub.Libuserd_shutdown(pb, metadata=self.metadata())  # type: ignore
            if self._channel:
                self._channel.close()
        except grpc.RpcError as e:
            if not no_error:
                raise self.libuserd_exception(e)
        finally:
            # clean up control objects
            self._stub = None
            self._channel = None

    def connect_check(self) -> None:
        """
        Verify that there is an active gRPC connection established.  If not raise
        a RuntimeError

        Raises
        ------
        RuntimeError
            If there is no active connection.
        """
        if not self._is_connected():
            raise RuntimeError("gRPC connection not established")

    """
    gRPC method bindings
    """

    def shutdown(self) -> None:
        """
        Close any active gRPC connection and shut down the EnSight server.
        The object is no longer usable.
        """
        self._disconnect(no_error=True)
        # Just in case, we will try to kill the server directly as well
        if self._server_process:
            if psutil.pid_exists(self._server_process.pid):
                proc = psutil.Process(self._server_process.pid)
                for child in proc.children(recursive=True):
                    if psutil.pid_exists(child.pid):
                        # This can be a race condition, so it is ok if the child is dead already
                        try:
                            child.kill()
                        except psutil.NoSuchProcess:
                            pass
                # Same issue, this process might already be shutting down, so NoSuchProcess is ok.
                try:
                    proc.kill()
                except psutil.NoSuchProcess:
                    pass
        if self._container:
            self._stop_container_and_enshell()
        self._server_process = None

    def ansys_release_string(self) -> str:
        """
        Return the Ansys release for the library.

        Returns
        -------
        str
            Return a string like "2025 R1"
        """
        self.connect_check()
        pb = libuserd_pb2.Libuserd_ansys_release_stringRequest()
        try:
            ret = self.stub.Libuserd_ansys_release_string(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def ansys_release_number(self) -> int:
        """
        Return the Ansys release number of the library.

        Returns
        -------
        int
            A version number like 251 (for "2025 R1")
        """
        self.connect_check()
        pb = libuserd_pb2.Libuserd_ansys_release_numberRequest()
        try:
            ret = self.stub.Libuserd_ansys_release_number(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def library_version(self) -> str:
        """
        The library version number.  This string is the version of the
        library interface itself.  This is not the same as the version
        number of the Ansys release that corresponds to the library.

        This number follows semantic versioning rules: "1.0.0" or
        "0.4.3-rc.1" would be examples of valid library_version() strings.

        Returns
        -------
        str
            The library interface version number string.
        """
        self.connect_check()
        pb = libuserd_pb2.Libuserd_library_versionRequest()
        try:
            ret = self.stub.Libuserd_library_version(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def nodes_per_element(self, element_type: int) -> int:
        """
        For a given element type (e.g. HEX20), return the number of nodes used by the element.
        Note, this is not supported for NSIDED and NFACED element types.

        Parameters
        ----------
        element_type
            The element type:  LibUserd.ElementType enum value

        Returns
        -------
        int
            Number of nodes per element or 0 if elem_type is not a valid zoo element type.
        """
        self.connect_check()
        pb = libuserd_pb2.Libuserd_nodes_per_elementRequest()
        pb.elemType = element_type
        try:
            ret = self.stub.Libuserd_nodes_per_element(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def element_is_ghost(self, element_type: int) -> bool:
        """

        For a given element type (e.g. HEX20), determine if the element type should be considered
        a "ghost" element.

        Parameters
        ----------
        element_type
            The element type:  LibUserd.ElementType enum value

        Returns
        -------
        bool
            True if the element is a ghost (or an invalid element type).
        """
        self.connect_check()
        pb = libuserd_pb2.Libuserd_element_is_ghostRequest()
        pb.elemType = element_type
        try:
            ret = self.stub.Libuserd_element_is_ghost(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def element_is_zoo(self, element_type: int) -> bool:
        """
        For a given element type (e.g. HEX20), determine if the element type is zoo or not

        Parameters
        ----------
        element_type
            The element type:  LibUserd.ElementType enum value

        Returns
        -------
        bool
            True if the element is a zoo element and false if it is NSIDED or NFACED.
        """
        self.connect_check()
        pb = libuserd_pb2.Libuserd_element_is_zooRequest()
        pb.elemType = element_type
        try:
            ret = self.stub.Libuserd_element_is_zoo(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def element_is_nsided(self, element_type: int) -> bool:
        """
        For a given element type, determine if the element type is n-sided or not

        Parameters
        ----------
        element_type
            The element type:  LibUserd.ElementType enum value

        Returns
        -------
        bool
            True if the element is a NSIDED or NSIDED_GHOST and False otherwise.
        """
        self.connect_check()
        pb = libuserd_pb2.Libuserd_element_is_nsidedRequest()
        pb.elemType = element_type
        try:
            ret = self.stub.Libuserd_element_is_nsided(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def element_is_nfaced(self, element_type: int) -> bool:
        """
        For a given element type, determine if the element type is n-faced or not

        Parameters
        ----------
        element_type
            The element type:  LibUserd.ElementType enum value

        Returns
        -------
        bool
            True if the element is a NFACED or NFACED_GHOST and False otherwise.
        """
        self.connect_check()
        pb = libuserd_pb2.Libuserd_element_is_nfacedRequest()
        pb.elemType = element_type
        try:
            ret = self.stub.Libuserd_element_is_nfaced(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def number_of_simple_element_types(self) -> int:
        """
        There is a consecutive range of element type enums that are supported by the
        Part.element_conn() method.  This function returns the number of those elements
        and may be useful in common element type handling code.

        Note: The value is effectively int(LibUserd.ElementType.NSIDED).

        Returns
        -------
        int
            The number of zoo element types.
        """
        self.connect_check()
        pb = libuserd_pb2.Libuserd_number_of_simple_element_typesRequest()
        try:
            ret = self.stub.Libuserd_number_of_simple_element_types(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        return ret.result

    def initialize(self) -> None:
        """
        This call initializes the libuserd system.  It causes the library to scan for available
        readers and set up any required reduction engine bits.  It can only be called once.
        """
        self.connect_check()
        pb = libuserd_pb2.Libuserd_initializeRequest()
        try:
            _ = self.stub.Libuserd_initialize(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)

    def get_all_readers(self) -> List["ReaderInfo"]:
        """
        Return a list of the readers that are available.

        Returns
        -------
        List[ReaderInfo]
            List of all ReaderInfo objects.
        """
        self.connect_check()
        pb = libuserd_pb2.Libuserd_get_all_readersRequest()
        try:
            readers = self.stub.Libuserd_get_all_readers(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        out = []
        for reader in readers.readerInfo:
            out.append(ReaderInfo(self, reader))
        return out

    def query_format(self, name1: str, name2: str = "") -> List["ReaderInfo"]:
        """
        For a given dataset (filename(s)), ask the readers if they should be able to read
        that data.

        Parameters
        ----------
        name1
            Primary input filename

        name2
            Optional, secondary input filename

        Returns
        -------
        List[ReaderInfo]
            List of ReaderInfo objects that might be able to read the dataset
        """
        self.connect_check()
        pb = libuserd_pb2.Libuserd_query_formatRequest()
        pb.name1 = name1
        if name2:
            pb.name2 = name2
        try:
            readers = self.stub.Libuserd_query_format(pb, metadata=self.metadata())
        except grpc.RpcError as e:
            raise self.libuserd_exception(e)
        out = []
        for reader in readers.readerInfo:
            out.append(ReaderInfo(self, reader))
        return out

    def load_data(
        self,
        data_file: str,
        result_file: str = "",
        file_format: Optional[str] = None,
        reader_options: Dict[str, Any] = {},
    ) -> "Reader":
        """Use the reader to load a dataset and return an instance
        to the resulting ``Reader`` interface.

        Parameters
        ----------
        data_file : str
            Name of the data file to load.
        result_file : str, optional
            Name of the second data file for dual-file datasets.
        file_format : str, optional
            Name of the USERD reader to use. The default is ``None``,
            in which case libuserd selects a reader.
        reader_options : dict, optional
            Dictionary of reader-specific option-value pairs that can be used
            to customize the reader behavior. The default is ``None``.

        Returns
        -------
        Reader
            Resulting Reader object instance.

        Raises
        ------
        RuntimeError
            If libused cannot guess the file format or an error occurs while the
            data is being read.

        Examples
        --------

        >>> from ansys.pyensight.core import libuserd
        >>> userd = libuserd.LibUserd()
        >>> userd.initialize()
        >>> opt = {'Long names': False, 'Number of timesteps': '10', 'Number of scalars': '3'}
        >>> data = userd.load_data("foo", file_format="Synthetic", reader_options=opt
        >>> print(data.parts())
        >>> print(data.variables())
        >>> userd.shutdown()

        """
        the_reader: Optional[ReaderInfo] = None
        if file_format:
            for reader in self.get_all_readers():
                if reader.name == file_format:
                    the_reader = reader
                    break
            if the_reader is None:
                raise RuntimeError(f"The reader '{file_format}' could not be found.")
        else:
            readers = self.query_format(data_file, name2=result_file)
            if len(readers):
                the_reader = readers[0]
            if the_reader is None:
                raise RuntimeError(f"Unable to find a reader for '{data_file}':'{result_file}'.")
        for key, value in reader_options.items():
            for b in the_reader.opt_booleans:
                if key == b["name"]:
                    b["value"] = bool(value)
            for o in the_reader.opt_options:
                if key == o["name"]:
                    o["value"] = int(value)
            for f in the_reader.opt_fields:
                if key == f["name"]:
                    f["value"] = str(value)
        try:
            output = the_reader.read_dataset(data_file, result_file)
        except Exception:
            raise RuntimeError("Unable to open the specified dataset.")

        return output

    @staticmethod
    def _download_files(uri: str, pathname: str, folder: bool = False):
        """Download files from the input uri and save them on the input pathname.

        Parameters:
        ----------

        uri: str
            The uri to get files from
        pathname: str
            The location were to save the files. It could be either a file or a folder.
        folder: bool
            True if the uri will server files from a directory. In this case,
            pathname will be used as the directory were to save the files.
        """
        if not folder:
            with requests.get(uri, stream=True) as r:
                with open(pathname, "wb") as f:
                    shutil.copyfileobj(r.raw, f)
        else:
            with requests.get(uri) as r:
                data = r.json()
                os.makedirs(pathname, exist_ok=True)
                for item in data:
                    if item["type"] == "file":
                        file_url = item["download_url"]
                        filename = os.path.join(pathname, item["name"])
                        r = requests.get(file_url, stream=True)
                        with open(filename, "wb") as f:
                            f.write(r.content)

    def file_service(self) -> Optional[Any]:
        """Get the PIM file service object if available."""
        return self._pim_file_service

    def download_pyansys_example(
        self,
        filename: str,
        directory: Optional[str] = None,
        root: Optional[str] = None,
        folder: bool = False,
    ) -> str:
        """Download an example dataset from the ansys/example-data repository.
        The dataset is downloaded local to the EnSight server location, so that it can
        be downloaded even if running from a container.

        Parameters
        ----------
        filename: str
            The filename to download
        directory: str
            The directory to download the filename from
        root: str
            If set, the download will happen from another location
        folder: bool
            If set to True, it marks the filename to be a directory rather
            than a single file

        Returns
        -------
        pathname: str
            The download location, local to the EnSight server directory.
            If folder is set to True, the download location will be a folder containing
            all the items available in the repository location under that folder.

        Examples
        --------
        >>> from ansys.pyensight.core import libuserd
        >>> l = libuserd.LibUserd()
        >>> cas_file = l.download_pyansys_example("mixing_elbow.cas.h5","pyfluent/mixing_elbow")
        >>> dat_file = l.download_pyansys_example("mixing_elbow.dat.h5","pyfluent/mixing_elbow")
        """
        base_uri = "https://github.com/ansys/example-data/raw/master"
        base_api_uri = "https://api.github.com/repos/ansys/example-data/contents"
        if not folder:
            if root is not None:
                base_uri = root
        else:
            base_uri = base_api_uri
        uri = f"{base_uri}/{filename}"
        if directory:
            uri = f"{base_uri}/{directory}/{filename}"
        # Local installs and PIM instances
        download_path = f"{os.getcwd()}/{filename}"
        if self._container and self._data_directory:
            # Docker Image
            download_path = os.path.join(self._data_directory, filename)
        self._download_files(uri, download_path, folder=folder)
        pathname = download_path
        if self._container:
            # Convert local path to Docker mounted volume path
            pathname = f"/data/{filename}"
        return pathname
