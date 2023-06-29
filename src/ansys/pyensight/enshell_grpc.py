import os
import random
import re
import subprocess
import sys
from typing import Optional

import grpc

# these modules are the result of running protoc on the .proto file
try:
    from ansys.api.enshell.v0 import enshell_pb2, enshell_pb2_grpc
except ImportError:
    import enshell_pb2
    import enshell_pb2_grpc

from ansys.pyensight._version import (  # pylint: disable=import-outside-toplevel
    DEFAULT_ANSYS_VERSION,
)

# @defgroup enshell_grpc enshell_grpc
# @ingroup grpc
# @brief Python wrapper for the core enshellservice
#
# This package defines the EnShellGRPC class which provides a simpler
# interface to the EnShell gRPC interface.
# @{


# @brief Python binding for the EnShell gRPC API
#
# This class provides an asynchronous interface to the EnShell
# core gRPC interface.
class EnShellGRPC(object):
    # @brief create an instance of the EnShell gRPC interface wrapper
    #
    # The default is to make a connection to an EnShell gRPC server
    # on port 12345 on the loopback host.  If requested to launch
    # the server, it will be the current version.
    #
    # @param port The port number of the EnShell gRPC server
    # @param host The hostname of the EnShell gRPC server
    # @param version A specific EnShell version number to run (e.g. '232' for 2023R2)
    def __init__(
        self, port: int = 12345, host: str = "127.0.0.1", version: str = DEFAULT_ANSYS_VERSION
    ):
        self._port = port
        self._host = host
        self._desired_version = version
        #
        self._pid = None
        self._channel = None
        self._stub = None
        #
        # self._security_token = str(random.randint(0, 1000000))
        self._security_token: Optional[int] = None
        #
        # values found from EnShell in the Container
        self._cei_home = None
        self._ansys_version = None

    def __del__(self):
        self.shutdown()

    # @brief get the hostname for this connection
    #
    # Returns the current connection hostname.
    def host(self):
        return self._host

    # @brief get the port number for this connection
    #
    # Returns the current connection port number.
    def port(self):
        return self._port

    # @brief set the security token for the gRPC connection.
    #
    # EnShell supports a security token in either numeric (-security {int}) or
    # string (ENSIGHT_SECURITY_TOKEN environmental variable) form.  If EnShell
    # is using a security token, all gRPC calls must include this token.  This
    # call sets the token for all rGPC calls made by this class.
    # Note: for this module, the security token must be a in bytes() format.
    # For example:  str(1000).encode("utf-8")
    # @param n an string to be used as the security token
    def set_security_token(self, n: Optional[int] = None):
        self._security_token = n

    # @brief set a random security token for the gRPC connection.
    #
    def set_random_security_token(self):
        self._security_token = str(random.randint(0, 1000000))

    # @brief return the security token for the gRPC connection.
    #
    # Returns the current connection security token
    def security_token(self):
        return self._security_token

    # @brief shut down all gRPC connections
    #
    # If this class launched the EnShell client instance, it will
    # send the gRPC exit() call and then shut down all connections.
    def shutdown(self):
        # if we launched EnShell, shut it down.
        if self._pid is not None:
            _ = self.stop_server()

    # @brief Start an EnShell gRPC server instance
    #
    # If the host application wishes to launch an EnShell instance, start_server()
    # will launch a batch mode EnShell application with the security token and
    # a gRPC server started on the port passed in the constructor.
    def start_server(self):
        if self._pid is not None:
            return self._pid

        my_env = os.environ.copy()
        if self._desired_version != "":
            exe = f"enshell{self._desired_version}"
        else:
            exe = "enshell"
        cmd = [exe, "-app", "-grpc_server", str(self._port)]
        if self._security_token:
            cmd.append("-security")
            cmd.append(self._security_token)
        if sys.platform in ("win32", "cygwin"):
            cmd[0] += ".bat"
            # cmd.append("-minimize_console")
            # si = subprocess.STARTUPINFO()
            # si.dwFlags = subprocess.STARTF_USESHOWWINDOW | subprocess.CREATE_NEW_CONSOLE
            # si.wShowWindow = subprocess.SW_HIDE
            # f = subprocess.DETACHED_PROCESS
            # DETACHED_PROCESS = 0x00000008
            # self._pid = subprocess.Popen(cmd, creationflags=f, close_fds=True, env=my_env).pid
            # self._pid = subprocess.Popen(cmd, startupinfo=si, close_fds=True, env=my_env).pid
            print(f"command: {cmd}\n\n")
            self._pid = subprocess.Popen(cmd, close_fds=True, env=my_env).pid
        else:
            self._pid = subprocess.Popen(cmd, close_fds=True, env=my_env).pid
        return self._pid

    # @brief shut down any gPRC connection made by this class
    #
    # First, if this class launched the EnShell instance, via start_server(), the
    # exit_cleanly() gRPC command will be sent.  Second, the local gRPC connection is
    # dropped.
    def stop_server(self):
        response = None
        # if we are connected and we started the server, we will emit the 'exit' message
        if self.is_connected():
            response = self._stub.exit_cleanly(
                enshell_pb2.google_dot_protobuf_dot_empty__pb2.Empty(), metadata=self.metadata()
            )
        self._stub = None
        self._dsg_stub = None
        if self._channel:
            self._channel.close()
        self._channel = None
        self._pid = None
        return response

    # @brief check if a gRPC connection has been established
    #
    # Returns True if a previous connect() call made a valid gRPC connection.
    def is_connected(self):
        if not self._channel:
            return False
        return self._channel is not None

    # @brief establish a connection to an EnShell gRPC server
    #
    # Attempt to connect to an EnShell gRPC server using the host and port
    # established by the constructor.  Note on failure, this function just
    # returns, but is_connected() will return False.
    # @param timeout how long to wait for the connection to timeout.
    def connect(self, timeout: Optional[float] = 15.0):
        if self._channel is not None:
            return
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
        except grpc.FutureTimeoutError:
            self._channel = None
            return
        self._stub = enshell_pb2_grpc.EnShellServiceStub(self._channel)

    # @brief establish a connection to an EnShell gRPC server
    #
    # Attempt to connect to an EnShell gRPC server using the host and port
    # established by the constructor.  Note on failure, this function just
    # returns, but is_connected() will return False.
    # @param timeout how long to wait for the connection to timeout.
    def connect_existing_channel(self, channel: grpc.Channel):
        if self._channel is not None:
            raise RuntimeError("connect_existing_channel: channel already connected.")

        if channel is None:
            raise RuntimeError("connect_existing_channel: bad channel passed in.")

        self._channel = channel
        self._stub = enshell_pb2_grpc.EnShellServiceStub(self._channel)

    # @brief compute internal gRPC stream metadata
    #
    # @private
    def metadata(self):
        ret = list()
        if self._security_token is not None:
            s = self._security_token
            if type(s) == str:
                s = s.encode("utf-8")
            ret.append((b"shared_secret", s))
        return ret

    # @brief send an EnShell command string to be executed in EnShell
    #
    # The string will be sent to EnShell via the EnShellService::run_command()
    # gRPC call.  An IOError exception may be thrown
    # if there's a gRPC communication problem.  The response
    # is the tuple of the EnShell return code and return string.
    # @param command_string the EnShell string to be executed
    # @return A tuple of (int, string) for (returnCode, returnString)
    def run_command(self, command_string: str):
        self.connect()
        if not self._stub:
            return (0, "")
        try:
            response = self._stub.run_command(
                enshell_pb2.EnShellCommandLine(command_line=command_string),
                metadata=self.metadata(),
            )
        except Exception:
            raise IOError("gRPC connection dropped")

        return (response.ret, response.response)

    # @brief Tell EnShell to start EnSight
    #
    # The string will be sent to EnShell via the EnShellService::run_command()
    # gRPC call.  An IOError exception may be thrown
    # if there's a gRPC communication problem.  The response
    # is the tuple of the EnShell return code and return string.
    # @param ensight_args arguments for the ensight command line
    # @return A tuple of (int, string) for (returnCode, returnString)
    def start_ensight(self, ensight_args: Optional[str] = None, ensight_env: Optional[str] = None):
        self.connect()

        command_string = "start_app CLIENT -c 127.0.0.1 -enshell"
        if ensight_args and (ensight_args != ""):
            command_string += " " + ensight_args

        return self.run_command(command_string)

    # @brief Tell EnShell to start a non-EnShell aware command
    #
    # The string will be sent to EnShell via the EnShellService::run_command()
    # gRPC call.  An IOError exception may be thrown
    # if there's a gRPC communication problem.  The response
    # is the tuple of the EnShell return code and return string.
    # @param cmd The command line
    # @return A tuple of (int, string) for (returnCode, returnString)
    def start_other(self, cmd: str, env: Optional[str] = None):
        self.connect()
        command_string = "start_app OTHER " + cmd

        return self.run_command(command_string)

    # @brief Get the value of CEI_HOME from EnShell
    def cei_home(self):
        self._get_cei_home()
        return self._cei_home

    # @brief Get the Ansys version from EnShell (e.g. 232)
    def ansys_version(self):
        self._get_cei_home()
        return self._ansys_version

    def _get_cei_home(self):
        if self._cei_home is not None:
            return

        self.connect()
        command_string = "run_cmd /usr/bin/printenv"
        ret = self.run_command(command_string)
        # print(f"{command_string} :: ret = {ret}\n")
        if ret[0] != 0:
            self._cei_home = None
            raise RuntimeError("Error getting printenv from EnShell")

        # split the newline delimited string into a list of strings
        env_vars = ret[1].strip().split("\n")
        # find the string containing CEI_HOME
        cei_home_line = [x for x in env_vars if "CEI_HOME" in x][0]
        if cei_home_line is None:
            raise RuntimeError("Error getting CEI_HOME env var from the Docker container.\n{ret}\n")

        # CEI_HOME is everything after the equal sign
        equal_sign_loc = cei_home_line.find("=")
        if equal_sign_loc < 0:
            raise RuntimeError("Error getting CEI_HOME env var from the Docker container.\n{ret}\n")
        self._cei_home = cei_home_line[equal_sign_loc + 1 :]
        m = re.search("/v(\d\d\d)/", self._cei_home)
        if not m:
            self.stop_server()
            raise RuntimeError("Can't find version from cei_home in the Docker container.\n{ret}\n")
        self._ansys_version = m.group(1)
