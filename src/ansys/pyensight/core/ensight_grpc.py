"""ensight_grpc module

This package defines the EnSightGRPC class which provides a simpler
interface to the EnSight gRPC interface, including event streams.

"""
from concurrent import futures
import os
import platform
import sys
import tempfile
import threading
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Tuple, Union
import uuid

from ansys.api.pyensight.v0 import dynamic_scene_graph_pb2_grpc, ensight_pb2, ensight_pb2_grpc
import grpc

if TYPE_CHECKING:
    from ansys.pyensight.core.utils.dsg_server import DSGSession


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
        self._shmem_module = None
        self._shmem_filename: Optional[str] = None
        self._shmem_client = None
        self._image_stream = None
        self._image_thread = None
        self._image = None
        self._image_number = 0
        self._sub_service = None
        self._dsg_session: Optional["DSGSession"] = None

    def set_dsg_session(self, dsg_session: "DSGSession"):
        self._dsg_session = dsg_session

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
            if self._shmem_client:
                if self._shmem_module:
                    self._shmem_module.stream_destroy(self._shmem_client)
                else:
                    self.command("ensight_grpc_shmem.stream_destroy(enscl._shmem_client)")
                self._shmem_client = None

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

    def _attempt_shared_mem_import(self):
        try:
            import ensight_grpc_shmem

            self._shmem_module = ensight_grpc_shmem
        except ModuleNotFoundError:
            try:
                self.command("import enve", do_eval=False)
                cei_home = eval(self.command("enve.home()"))
                self.command("import ceiversion", do_eval=False)
                cei_version = eval(self.command("ceiversion.version_suffix"))
                self.command("import sys", do_eval=False)
                py_version = eval(self.command("sys.version_info[:3]"))
                is_win = True if "Win" in platform.system() else False
                plat = "win64" if is_win else "linux_2.6_64"
                _lib = "DLLs" if is_win else f"lib/python{py_version[0]}.{py_version[1]}"
                dll_loc = os.path.join(
                    cei_home,
                    f"apex{cei_version}",
                    "machines",
                    plat,
                    f"Python-{py_version[0]}.{py_version[1]}.{py_version[2]}",
                    _lib,
                )
                if os.path.exists(dll_loc):
                    sys.path.append(dll_loc)
                    import ensight_grpc_shmem

                    self._shmem_module = ensight_grpc_shmem
            except ModuleNotFoundError:
                pass

    @classmethod
    def _find_filename(cls, size=1024 * 1024 * 25):
        """Create a file on disk to support shared memory transport.

        A file, 25MB in size, will be created using the pid of the current
        process to generate the filename. It will be located in a temporary
        directory.
        """
        tempdir = tempfile.mkdtemp(prefix="pyensight_shmem")
        for i in range(100):
            filename = os.path.join(tempdir, "shmem_{}.bin".format(os.getpid() + i))
            if not os.path.exists(filename):
                try:
                    tmp = open(filename, "wb")
                    tmp.write(b"\0" * size)  # 25MB
                    tmp.close()
                    return filename
                except Exception:
                    pass
        return None

    def get_image(self):
        """Retrieve the current EnSight image.

        When any of the image streaming systems is enabled, Python threads will receive the
        most recent image and store them in this instance.  The frame stored in this instance
        can be accessed by calling this method

        Returns
        -------
        (tuple):
            A tuple containing a dictionary defining the image binary
            (pixels=bytearray, width=w, height=h) and the image frame number.
        """
        return self._image, self._image_number

    def _start_sub_service(self):
        """Start a gRPC client service.
        When the client calls one subscribe_events() or subscribe_images() with the
        connection set to GRPC, the interface requires the client to start a gRPC server
        that EnSight will call back to with event/image messages.  This method starts
        such a gRPC server."""
        try:
            if self._sub_service is not None:
                return
            self._sub_service = _EnSightSubServicer(parent=self)
            self._sub_service.start()
        except Exception:
            self._sub_service = None

    def subscribe_images(self, flip_vertical=False, use_shmem=True):
        """Subscribe to an image stream.

        This methond makes a EnSightService::SubscribeImages() gRPC call.  If
        use_shmem is False, the transport system will be made over gRPC.  It causes
        EnSight to make a reverse gRPC connection over with gRPC calls with the
        various images will be made.  If use_shmem is True (the default), the \ref shmem will be used.

        Parameters
        ---------
        flip_vertical: bool
            If True, the image pixels will be flipped over the X axis
        use_shmem: bool
            If True, use the shared memory transport, otherwise use reverse gRPC"""
        self.connect()
        if use_shmem:
            try:
                # we need a shared memory file
                self._shmem_filename = self._find_filename()
                if self._shmem_filename is not None:
                    conn_type = ensight_pb2.SubscribeImageOptions.SHARED_MEM
                    options = dict(filename=self._shmem_filename)
                    image_options = ensight_pb2.SubscribeImageOptions(
                        prefix=self.prefix(),
                        type=conn_type,
                        options=options,
                        flip_vertical=flip_vertical,
                        chunk=False,
                    )
                    _ = self._stub.SubscribeImages(image_options, metadata=self._metadata())
                    # start the local server
                    if not self._shmem_module:
                        self._attempt_shared_mem_import()
                    if self._shmem_module:
                        self._shmem_client = self._shmem_module.stream_create(self._shmem_filename)
                    else:
                        self.command("import ensight_grpc_shmem", do_eval=False)
                        to_send = self._shmem_filename.replace("\\", "\\\\")
                        self.command(
                            f"enscl._shmem_client = ensight_grpc_shmem.stream_create('{to_send}')",
                            do_eval=False,
                        )
                        if self.command("enscl._shmem_client is not None"):
                            self._shmem_client = True

                    # turn on the polling thread
                    self._image_thread = threading.Thread(target=self._poll_images)
                    self._image_thread.daemon = True
                    self._image_thread.start()
                    return
            except Exception as e:
                print("Unable to subscribe to an image stream via shared memory: {}".format(str(e)))

        self._start_sub_service()
        conn_type = ensight_pb2.SubscribeImageOptions.GRPC
        options = {}
        if self._sub_service:
            options = dict(uri=self._sub_service._uri)
        image_options = ensight_pb2.SubscribeImageOptions(
            prefix=self.prefix(),
            type=conn_type,
            options=options,
            flip_vertical=flip_vertical,
            chunk=True,
        )
        _ = self._stub.SubscribeImages(image_options, metadata=self._metadata())

    def image_stream_enable(self, flip_vertical=False):
        """Enable a simple gRPC-based image stream from EnSight.

        This method makes a EnSightService::GetImageStream() gRPC call into EnSight, returning
        an ensightservice::ImageReply stream.  The method creates a thread to hold this
        stream open and read new image frames from it.  The thread places the read images
        in this object.  An external application can retrieve the most recent one using
        get_image().

        Parameters
        ----------
        flip_vertical: bool
            If True, the image will be flipped over the X axis before being sent from EnSight."""
        if self._image_stream is not None:
            return
        self.connect()
        self._image_stream = self._stub.GetImageStream(
            ensight_pb2.ImageStreamRequest(flip_vertical=flip_vertical, chunk=True),
            metadata=self._metadata(),
        )
        self._image_thread = threading.Thread(target=self._poll_images)
        self._image_thread.daemon = True
        self._image_thread.start()

    def _put_image(self, the_image):
        """Store an image on this instance.

        This method is used by threads to store the latest image they receive
        so it can be accessed by get_image.
        """
        self._image = the_image
        self._image_number += 1

    def image_stream_is_enabled(self):
        """Check to see if the image stream is enabled.

        If an image stream has been successfully established via image_stream_enable(),
        then this function returns True.

        Returns
        -------
        (bool):
            True if a ensightservice::ImageReply steam is active
        """
        return self._image_stream is not None

    def _poll_images(self):
        """Handle image streams.

        This method is called by a Python thread to read imagery via the shared memory
        transport system or the the ensightservice::ImageReply stream.
        """
        try:
            while self._stub is not None:
                if self._shmem_client:
                    if self._shmem_module:
                        img = self._shmem_module.stream_lock(self._shmem_client)
                    else:
                        img = self.command("ensight_grpc_shmem.stream_lock(enscl._shmem_client)")
                    if type(img) is dict:
                        the_image = dict(
                            pixels=img["pixeldata"], width=img["width"], height=img["height"]
                        )
                        self._put_image(the_image)
                        if self._shmem_module:
                            self._shmem_module.stream_unlock(self._shmem_client)
                        else:
                            self.command(
                                "ensight_grpc_shmem.stream_unlock(enscl._shmem_client)",
                                do_eval=False,
                            )

                if self._image_stream is not None:
                    img = self._image_stream.next()
                    buffer = img.pixels

                    while not img.final:
                        img = self._image_stream.next()
                        buffer += img.pixels

                    the_image = dict(pixels=buffer, width=img.width, height=img.height)
                    self._put_image(the_image)
        except Exception:
            # signal that the gRPC connection has broken
            self._image_stream = None
            self._image_thread = None
            self._image = None


class _EnSightSubServicer(ensight_pb2_grpc.EnSightSubscriptionServicer):
    """Internal class handling reverse subscription connections.
    The EnSight gRPC interface has a mechanism for reversing the gRPC
    streams called Subscriptions.  Image and event streams can be
    subscribed to.  In this mode, the client application starts a
    gRPC server that implements the EnSightSubscription protocol.
    EnSight will connect back to the client using this protocol and
    send images/events back to the client as regular (non-stream)
    rpc calls.  This can be useful in situations where it is difficult
    keep a long-running stream alive.
    The EnSightSubServicer class implements a gRPC server for the client application.
    """

    def __init__(self, parent: Optional["EnSightGRPC"] = None):
        self._server: Optional["grpc.Server"] = None
        self._uri: str = ""
        self._parent = parent

    def PublishEvent(self, request: Any, context: Any) -> "ensight_pb2.GenericResponse":
        """Publish an event to the remote server."""
        if self._parent is not None:
            self._parent._put_event(request)
        return ensight_pb2.GenericResponse(str="Event Published")

    def PublishImage(self, request_iterator: Any, context: Any) -> "ensight_pb2.GenericResponse":
        """Publish a single image (possibly in chucks) to the remote server."""
        img: Any = request_iterator.next()
        buffer = img.pixels
        while not img.final:
            img = request_iterator.next()
            buffer += img.pixels
        the_image = dict(pixels=buffer, width=img.width, height=img.height)
        if self._parent is not None:
            self._parent._put_image(the_image)
        return ensight_pb2.GenericResponse(str="Image Published")

    def start(self):
        """Start the gRPC server to be used for the EnSight Subscription Service."""
        self._server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        ensight_pb2_grpc.add_EnSightSubscriptionServicer_to_server(self, self._server)
        # Start the server on localhost with a random port
        port = self._server.add_insecure_port("localhost:0")
        self._uri = "localhost:" + str(port)
        self._server.start()
