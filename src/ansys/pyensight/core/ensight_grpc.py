"""ensight_grpc module

This package defines the EnSightGRPC class which provides a simpler
interface to the EnSight gRPC interface, including event streams.

"""
import threading
from typing import Any, Callable, List, Optional, Tuple, Union
import uuid

from ansys.api.pyensight.v0 import dynamic_scene_graph_pb2_grpc, ensight_pb2, ensight_pb2_grpc
import grpc


class EnSightGRPC(object):
    """Wrapper around a gRPC connection to an EnSight instance

    This class provides an asynchronous interface to the EnSight
    core gRPC interface.  It can handle remote event
    streams, providing a much simpler interface to the EnSight
    application. The default is to make a connection to an EnSight
    gRPC server on port 12345 on the loopback host.

    Parameters
    ----------
    host: str, optional
        Hostname where there EnSight gRPC server is running.
    port: int, optional
        Port to make the gRPC connection to
    secret_key: str, optional
        Connection secret key
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 12345, secret_key: str = ""):
        self._host = host
        self._port = port
        self._channel = None
        self._stub = None
        self._dsg_stub = None
        self._security_token = secret_key
        self._session_name: str = ""
        # Streaming APIs
        # Event (strings)
        self._event_stream = None
        self._event_thread: Optional[threading.Thread] = None
        self._events: List[Any] = list()
        # Callback for events (self._events not used)
        self._event_callback: Optional[Callable] = None
        self._prefix: Optional[str] = None

    @property
    def host(self) -> str:
        """The gRPC server (EnSight) hostname"""
        return self._host

    def port(self) -> int:
        """The gRPC server (EnSight) port number"""
        return self._port

    @property
    def security_token(self) -> str:
        """The gRPC server (EnSight) secret key

        EnSight supports a security token in either numeric (-security {int}) or
        string (ENSIGHT_SECURITY_TOKEN environmental variable) form.  If EnSight
        is using a security token, all gRPC calls must include this token.  This
        call sets the token for all grPC calls made by this class.
        """
        return self._security_token

    @security_token.setter
    def security_token(self, name: str) -> None:
        self._security_token = name  # pragma: no cover

    @property
    def session_name(self) -> str:
        """The gRPC server session name

        EnSight gRPC calls can include the session name via 'session_name' metadata.
        A client session may provide a session name via this property.
        """
        return self._session_name

    @session_name.setter
    def session_name(self, name: str) -> None:
        self._session_name = name

    def shutdown(self, stop_ensight: bool = False, force: bool = False) -> None:
        """Close down the gRPC connection

        Disconnect all connections to the gRPC server.  If stop_ensight is True, send the
        'Exit' command to the EnSight gRPC server.

        Parameters
        ----------
        stop_ensight: bool, optional
            if True, send an 'Exit' command to the gRPC server.
        force: bool, optional
            if stop_ensight and force are true, stop EnSight aggressively
        """
        if self.is_connected():  # pragma: no cover
            # if requested, send 'Exit'
            if stop_ensight:  # pragma: no cover
                # the gRPC ExitRequest is exactly that, a request in some
                # cases the operation needs to be forced
                if force:  # pragma: no cover
                    try:
                        self.command("ensight.exit(0)", do_eval=False)
                    except IOError:  # pragma: no cover
                        # we expect this as the exit can result in the gRPC call failing
                        pass  # pragma: no cover
                else:
                    if self._stub:  # pragma: no cover
                        _ = self._stub.Exit(
                            ensight_pb2.ExitRequest(), metadata=self._metadata()
                        )  # pragma: no cover
            # clean up control objects
            self._stub = None
            self._dsg_stub = None
            if self._channel:
                self._channel.close()
            self._channel = None

    def is_connected(self) -> bool:
        """Check to see if the gRPC connection is live

        Returns
        -------
             True if the connection is active.
        """
        return self._channel is not None

    def connect(self, timeout: float = 15.0) -> None:
        """Establish the gRPC connection to EnSight

        Attempt to connect to an EnSight gRPC server using the host and port
        established by the constructor.  Note on failure, this function just
        returns, but is_connected() will return False.

        Parameters
        ----------
        timeout: float
            how long to wait for the connection to timeout
        """
        if self.is_connected():
            return
        # set up the channel
        self._channel = grpc.insecure_channel(
            "{}:{}".format(self._host, self._port),
            options=[
                ("grpc.max_receive_message_length", -1),
                ("grpc.max_send_message_length", -1),
                ("grpc.testing.fixed_reconnect_backoff_ms", 1100),
            ],
        )
        try:
            grpc.channel_ready_future(self._channel).result(timeout=timeout)
        except grpc.FutureTimeoutError:  # pragma: no cover
            self._channel = None  # pragma: no cover
            return  # pragma: no cover
        # hook up the stub interface
        self._stub = ensight_pb2_grpc.EnSightServiceStub(self._channel)
        self._dsg_stub = dynamic_scene_graph_pb2_grpc.DynamicSceneGraphServiceStub(self._channel)

    def _metadata(self) -> List[Tuple[bytes, Union[str, bytes]]]:
        """Compute the gRPC stream metadata

        Compute the list to be passed to the gRPC calls for things like security
        and the session name.

        """
        ret: List[Tuple[bytes, Union[str, bytes]]] = list()
        s: Union[str, bytes]
        if self._security_token:  # pragma: no cover
            s = self._security_token
            if type(s) == str:  # pragma: no cover
                s = s.encode("utf-8")
            ret.append((b"shared_secret", s))
        if self.session_name:  # pragma: no cover
            s = self.session_name.encode("utf-8")
            ret.append((b"session_name", s))
        return ret

    def render(
        self,
        width: int = 640,
        height: int = 480,
        aa: int = 1,
        png: bool = True,
        highlighting: bool = False,
    ) -> bytes:
        """Generate a rendering of the current EnSight scene

        Render the current scene at a specific size and using a specific number of anti-aliasing
        passes. The return value can be a byte array (width*height*3) bytes or a PNG image.

        Parameters
        ----------
        width: int, optional
            width of the image to render
        height: int, optional
            height of the image to render
        aa: int, optional
            number of antialiasing passes to use in generating the image
        png: bool, optional
            if True, the return value is a PNG image bytestream.  Otherwise, it is a simple
            bytes object with width*height*3 values.
        highlighting: bool, optional
            if True, selection highlighting will be included in the image.

        Returns
        -------
        bytes
            bytes object representation of the rendered image

        Raises
        ------
            IOError if the operation fails
        """
        self.connect()
        ret_type = ensight_pb2.RenderRequest.IMAGE_RAW
        if png:  # pragma: no cover
            ret_type = ensight_pb2.RenderRequest.IMAGE_PNG
        response: Any
        try:
            if self._stub:  # pragma: no cover
                response = self._stub.RenderImage(
                    ensight_pb2.RenderRequest(
                        type=ret_type,
                        image_width=width,
                        image_height=height,
                        image_aa_passes=aa,
                        include_highlighting=highlighting,
                    ),
                    metadata=self._metadata(),
                )
        except Exception:  # pragma: no cover
            raise IOError("gRPC connection dropped")  # pragma: no cover
        return response.value

    def geometry(self) -> bytes:
        """Return the current scene geometry in glTF format

        Package up the geometry currently being viewed in the EnSight session as
        a glTF stream.  Return this stream as an array of byte.  Note: no
        intermediate files are utilized.

        Note: currently there is a limitation of glTF files to 2GB

        Returns
        -------
            bytes object representation of the glTF file

        Raises
        ------
            IOError if the operation fails
        """
        self.connect()
        response: Any
        try:
            if self._stub:  # pragma: no cover
                response = self._stub.GetGeometry(
                    ensight_pb2.GeometryRequest(type=ensight_pb2.GeometryRequest.GEOMETRY_GLB),
                    metadata=self._metadata(),
                )
        except Exception:  # pragma: no cover
            raise IOError("gRPC connection dropped")  # pragma: no cover
        return response.value

    def command(self, command_string: str, do_eval: bool = True, json: bool = False) -> Any:
        """Send a Python command string to be executed in EnSight

        The string will be run or evaluated in the EnSight Python interpreter via the
        EnSightService::RunPython() gRPC all.  If an exception or other error occurs, this
        function will throw a RuntimeError.  If do_eval is False, the return value will be None,
        otherwise it will be the returned string (eval() will not be performed).  If json is True,
        the return value will be a JSON representation of the report execution result.

        Parameters
        ----------
        command_string: str
            The string to execute
        do_eval: bool, optional
            If True, a return value will be computed and returned
        json: bool, optional
            If True and do_eval is True, the return value will be a JSON representation of
            the evaluated value.

        Returns
        -------
        Any
             None, a string ready for Python eval() or a JSON string.

        Raises
        ------
            RuntimeError if the operation fails.
            IOError if the communication fails.
        """
        self.connect()
        flags = ensight_pb2.PythonRequest.EXEC_RETURN_PYTHON
        response: Any
        if json:  # pragma: no cover
            flags = ensight_pb2.PythonRequest.EXEC_RETURN_JSON  # pragma: no cover
        if not do_eval:
            flags = ensight_pb2.PythonRequest.EXEC_NO_RESULT
        try:
            if self._stub:  # pragma: no cover
                response = self._stub.RunPython(
                    ensight_pb2.PythonRequest(type=flags, command=command_string),
                    metadata=self._metadata(),
                )
        except Exception:
            raise IOError("gRPC connection dropped")
        if response.error < 0:  # pragma: no cover
            raise RuntimeError(response.value)  # pragma: no cover
        if flags == ensight_pb2.PythonRequest.EXEC_NO_RESULT:
            return None
        # This was moved externally so pre-processing could be performed
        # elif flags == ensight_pb2.PythonRequest.EXEC_RETURN_PYTHON:
        #    return eval(response.value)
        return response.value

    def prefix(self) -> str:
        """Return the unique prefix for this instance.

        Some EnSight gRPC APIs require a unique prefix so that EnSight can handle
        multiple, simultaneous remote connections. This method will generate a GUID-based
        prefix.

        Returns
        -------
        str
            A unique (for this session) prefix string of the form: grpc://{uuid}/
        """
        # prefix URIs will have the format:  "grpc://{uuid}/{callbackname}?enum={}&uid={}"
        if self._prefix is None:
            self._prefix = "grpc://" + str(uuid.uuid1()) + "/"
        return self._prefix

    def event_stream_enable(self, callback: Optional[Callable] = None) -> None:
        """Enable a simple gRPC-based event stream from EnSight

        This method makes a EnSightService::GetEventStream() gRPC call into EnSight, returning
        an ensightservice::EventReply stream.  The method creates a thread to hold this
        stream open and read new events from it.  The thread adds the event strings to
        a list of events stored on this instance.  If callback is not None, the object
        will be called with the event string, otherwise they can be retrieved using get_event().
        """
        if self._event_stream is not None:  # pragma: no cover
            return  # pragma: no cover
        self._event_callback = callback
        self.connect()
        if self._stub:  # pragma: no cover
            self._event_stream = self._stub.GetEventStream(
                ensight_pb2.EventStreamRequest(prefix=self.prefix()),
                metadata=self._metadata(),
            )
        self._event_thread = threading.Thread(target=self._poll_events)
        self._event_thread.daemon = True
        self._event_thread.start()

    def event_stream_is_enabled(self) -> bool:
        """Check to see if the event stream is enabled

        If an event stream has been successfully established via
        event_stream_enable(), then this function returns True.

        Returns
        -------
              True if a ensightservice::EventReply steam is active
        """
        return self._event_stream is not None  # pragma: no cover

    def dynamic_scene_graph_stream(self, client_cmds):  # pragma: no cover
        """Open up a dynamic scene graph stream

        Make a DynamicSceneGraphService::GetSceneStream() rpc call and return
        a ensightservice::SceneUpdateCommand stream instance.

        Parameters
        ----------
        client_cmds
            iterator that produces ensightservice::SceneClientCommand objects

        Returns
        -------
            ensightservice::SceneUpdateCommand stream instance
        """
        self.connect()
        return self._dsg_stub.GetSceneStream(client_cmds, metadata=self._metadata())

    def get_event(self) -> Optional[str]:  # pragma: no cover
        """Retrieve and remove the oldest ensightservice::EventReply string

        When any of the event streaming systems is enabled, Python threads will receive the
        event records and store them in this instance in an ordered fashion.  This method
        retrieves the oldest ensightservice::EventReply string in the queue.

        Returns
        -------
            None or the oldest event string in the queue.
        """
        try:
            return self._events.pop(0)
        except IndexError:
            return None

    def _put_event(self, evt: "ensight_pb2.EventReply") -> None:
        """Add an event record to the event queue on this instance

        This method is used by threads to make the events they receive available to
        calling applications via get_event().
        """
        if self._event_callback:  # pragma: no cover
            self._event_callback(evt.tag)
            return
        self._events.append(evt.tag)  # pragma: no cover

    def _poll_events(self) -> None:
        """Internal method to handle event streams

        This method is called by a Python thread to read events via the established
        ensightservice::EventReply stream.
        """
        try:
            while self._stub is not None:  # pragma: no cover
                evt = self._event_stream.next()
                self._put_event(evt)
        except Exception:
            # signal that the gRPC connection has broken
            self._event_stream = None
            self._event_thread = None
