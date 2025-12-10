# Copyright (C) 2022 - 2025 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
Python wrapper for the core enshellservice

This package defines the EnShellGRPC class which provides a simpler
interface to the EnShell gRPC interface.

Python binding for the EnShell gRPC API

This class provides an asynchronous interface to the EnShell
core gRPC interface.
"""
import logging
import os
import random
import re
import subprocess
import sys
from typing import TYPE_CHECKING, Optional

from ansys.api.pyensight.v0 import enshell_pb2, enshell_pb2_grpc
from ansys.pyensight.core import DEFAULT_ANSYS_VERSION  # pylint: disable=import-outside-toplevel
from ansys.tools.common.cyberchannel import create_channel
import grpc

if TYPE_CHECKING:
    from ansys.pyensight.core import Session


class EnShellGRPC(object):
    """Create an instance of the EnShell gRPC interface wrapper.

    The default is to make a connection to an EnShell gRPC server
    on port 12345 on the loopback host.  If requested to launch
    the server, it will be the current version.

    Parameters
    ----------
    port: int, optional
        The port number of the EnShell gRPC server
    host:
        The hostname of the EnShell gRPC server
    version:
        A specific EnShell version number to run (e.g. '232' for 2023R2)
    secret_key: str, optional
        Connection secret key
    grpc_use_tcp_sockets :
        If using gRPC, and if True, then allow TCP Socket based connections
        instead of only local connections.
    grpc_allow_network_connections :
        If using gRPC and using TCP Socket based connections, listen on all networks.
    grpc_disable_tls :
        If using gRPC and using TCP Socket based connections, disable TLS.
    grpc_uds_pathname :
        If using gRPC and using Unix Domain Socket based connections, explicitly
        set the pathname to the shared UDS file instead of using the default.
    disable_grpc_options: bool, optional
        Whether to disable the gRPC options check, and allow to run older
        versions of EnSight

    WARNING:
    Overriding the default values for these options: grpc_use_tcp_sockets, grpc_allow_network_connections,
    and grpc_disable_tls
    can possibly permit control of this computer and any data which resides on it.
    Modification of this configuration is not recommended.  Please see the
    documentation for your installed product for additional information.
    """

    def __init__(
        self,
        port: int = 12345,
        host: str = "127.0.0.1",
        version: str = DEFAULT_ANSYS_VERSION,
        secret_key: str = "",
        grpc_use_tcp_sockets: bool = False,
        grpc_allow_network_connections: bool = False,
        grpc_disable_tls: bool = False,
        grpc_uds_pathname: Optional[str] = None,
        session: Optional["Session"] = None,
        disable_grpc_options: bool = False,
    ):
        self._port = port
        self._host = host
        self._desired_version = version
        #
        self._pid = None
        self._channel = None
        self._stub = None
        self._grpc_use_tcp_sockets = grpc_use_tcp_sockets
        self._grpc_allow_network_connections = grpc_allow_network_connections
        self._grpc_disable_tls = grpc_disable_tls
        self._grpc_uds_pathname = grpc_uds_pathname
        #
        # self._security_token = str(random.randint(0, 1000000))
        self._security_token: Optional[str] = None
        if not secret_key and not disable_grpc_options:
            self._security_token = str(random.randint(0, 1000000))
        else:
            self._security_token = secret_key
        # self._security_token: Optional[int] = None
        #
        # values found from EnShell in the Container
        self._cei_home = None
        self._ansys_version = None
        self._pyensight_session = session
        self._disable_grpc_options = disable_grpc_options

    def __del__(self):
        self.shutdown()

    def host(self):
        """Get the hostname for this connection.

        Returns
        -------
        str
            the current connection hostname.
        """
        return self._host

    def port(self):
        """Get the port number for this connection.

        Returns
        -------
        int
            The current connection port number.
        """
        return self._port

    @property
    def security_token(self):
        """Return the security token for the gRPC connection.

        Returns
        -------
        str
            Returns the current connection security token
        """
        return self._security_token

    @security_token.setter
    def security_token(self, n: str):
        """set the security token for the gRPC connection.

        EnShell supports a security token in either numeric (-security {int}) or
        string (ENSIGHT_SECURITY_TOKEN environmental variable) form.  If EnShell
        is using a security token, all gRPC calls must include this token.  This
        call sets the token for all rGPC calls made by this class.
        Note: for this module, the security token must be a in bytes() format.
        For example:  str(1000).encode("utf-8")

        Parameters
        ----------
        n : Optional[int], optional
            An string to be used as the security token, by default None
        """
        self._security_token = n  # pragma: no cover

    @property
    def grpc_use_tcp_sockets(self):
        """Get whether to use Unix Domain Sockets or TCP Sockets for gRPC"""
        return self._grpc_use_tcp_sockets

    @grpc_use_tcp_sockets.setter
    def grpc_use_tcp_sockets(self, use_sockets: bool):
        """Set whether to use Unix Domain Sockets or TCP Sockets for gRPC"""
        self._grpc_use_tcp_sockets = use_sockets

    @property
    def grpc_allow_network_connections(self):
        """Get whether to allow listening on all networks if using TCP Sockets for gRPC"""
        return self._grpc_allow_network_connections

    @grpc_allow_network_connections.setter
    def grpc_allow_network_connections(self, allow: bool):
        """Set whether to allow listening on all networks if using TCP Sockets for gRPC"""
        self._grpc_allow_network_connections = allow

    @property
    def grpc_disable_tls(self):
        """Get whether to use TLS for TCP Sockets for gRPC"""
        return self._grpc_disable_tls

    @grpc_disable_tls.setter
    def grpc_disable_tls(self, disable_tls: bool):
        """Set whether to use TLS for TCP Sockets for gRPC"""
        self._grpc_disable_tls = disable_tls

    @property
    def grpc_uds_pathname(self):
        """Get the pathname for the UDS file if not using the default for gRPC"""
        return self._grpc_uds_pathname

    @grpc_uds_pathname.setter
    def grpc_uds_pathname(self, uds_pathname: str):
        """Set the pathname for the UDS file if not using the default for gRPC"""
        self._grpc_uds_pathname = uds_pathname

    def set_random_security_token(self):
        """Set a random security token for the gRPC connection."""
        self._security_token = str(random.randint(0, 1000000))  # pragma: no cover

    def shutdown(self):
        """shut down all gRPC connections.

        If this class launched the EnShell client instance, it will
        send the gRPC exit() call and then shut down all connections.
        """
        # if we launched EnShell, shut it down.
        if self._pid is not None:  # pragma: no cover
            _ = self.stop_server()  # pragma: no cover

    def start_server(self):  # pragma: no cover
        """Start an EnShell gRPC server instance.

        If the host application wishes to launch an EnShell instance, start_server()
        will launch a batch mode EnShell application with the security token and
        a gRPC server started on the port passed in the constructor.
        """
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
        if self._grpc_use_tcp_sockets:
            cmd.append("-grpc_use_tcp_sockets")
        if self._grpc_allow_network_connections:
            cmd.append("-grpc_allow_network_connections")
        if self._grpc_disable_tls:
            cmd.append("-grpc_disable_tls")
        if self._grpc_uds_pathname:
            cmd.append("-grpc_uds_pathname")
            cmd.append(self._grpc_uds_pathname)
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
            logging.debug(f"command: {cmd}\n\n")
            self._pid = subprocess.Popen(cmd, close_fds=True, env=my_env).pid
        else:
            self._pid = subprocess.Popen(cmd, close_fds=True, env=my_env).pid
        return self._pid

    def stop_server(self):
        """Shut down any gPRC connection made by this class.

        First, if this class launched the EnShell instance, via start_server(), the
        exit_cleanly() gRPC command will be sent.  Second, the local gRPC connection is
        dropped
        """
        response = None
        # if we are connected and we started the server, we will emit the 'exit' message
        if self.is_connected():  # pragma: no cover
            response = self._stub.exit_cleanly(
                enshell_pb2.google_dot_protobuf_dot_empty__pb2.Empty(), metadata=self.metadata()
            )
        self._stub = None
        self._dsg_stub = None
        if self._channel:  # pragma: no cover
            self._channel.close()
        self._channel = None
        self._pid = None
        return response

    def is_connected(self):
        """Check if a gRPC connection has been established.

        Returns
        -------
        bool
            True if a previous connect() call made a valid gRPC connection.
        """
        if not self._channel:
            return False
        return self._channel is not None

    def connect(self, timeout: Optional[float] = 15.0):
        """Establish a connection to an EnShell gRPC server.

        Attempt to connect to an EnShell gRPC server using the host and port
        established by the constructor.  Note on failure, this function just
        returns, but is_connected() will return False.

        Parameters
        ----------
        timeout : Optional[float], optional
            timeout how long to wait for the connection to timeout., by default 15.0
        """
        if self._channel is not None:
            return
        transport_mode = None
        host = None
        port = None
        uds_service = None
        uds_dir = None
        options = [
            ("grpc.max_receive_message_length", -1),
            ("grpc.max_send_message_length", -1),
            ("grpc.testing.fixed_reconnect_backoff_ms", 1100),
        ]
        if self._grpc_use_tcp_sockets:
            host = self._host
            transport_mode = "mtls"
            if self._grpc_disable_tls:
                transport_mode = "insecure"
            port = self._port
        else:
            host = "127.0.0.1"
            if sys.platform == "win32":
                transport_mode = "wnua"
                port = self._port
            else:
                transport_mode = "uds"
                uds_service = "pyensight" if self._grpc_uds_pathname else "greeter"
                if not self._grpc_uds_pathname:
                    uds_dir = "/tmp"
                else:
                    uds_dir = os.path.dirname(self._grpc_uds_pathname)
        # Ignore the security options if the version of EnSight cannot handle them
        if self._disable_grpc_options:
            transport_mode = "insecure"
            host = self._host
            port = self._port
        self._channel = create_channel(
            host=host,
            port=port,
            transport_mode=transport_mode,
            uds_dir=uds_dir,
            uds_service=uds_service,
            grpc_options=options,
        )
        try:
            grpc.channel_ready_future(self._channel).result(timeout=timeout)
        except grpc.FutureTimeoutError:  # pragma: no cover
            self._channel = None  # pragma: no cover
            return  # pragma: no cover
        self._stub = enshell_pb2_grpc.EnShellServiceStub(self._channel)

    def connect_existing_channel(self, channel: grpc.Channel):  # pragma: no cover
        """Establish a connection to an EnShell gRPC server.

        Attempt to connect to an EnShell gRPC server using the host and port
        established by the constructor.  Note on failure, this function just
        returns, but is_connected() will return False.

        Parameters
        ----------
        channel : grpc.Channel
            Timeout how long to wait for the connection to timeout.
        """
        if self._channel is not None:
            raise RuntimeError("connect_existing_channel: channel already connected.")

        if channel is None:
            raise RuntimeError("connect_existing_channel: bad channel passed in.")

        self._channel = channel
        self._stub = enshell_pb2_grpc.EnShellServiceStub(self._channel)

    def metadata(self):  # pragma: no cover
        """Compute internal gRPC stream metadata."""
        ret = list()
        if self._security_token is not None:
            s = self._security_token
            if type(s) == str:
                s = s.encode("utf-8")
            ret.append((b"shared_secret", s))
        return ret

    def run_command(self, command_string: str):
        """send an EnShell command string to be executed in EnShell.

        The string will be sent to EnShell via the EnShellService::run_command()
        gRPC call.  An IOError exception may be thrown
        if there's a gRPC communication problem.  The response
        is the tuple of the EnShell return code and return string.

        Parameters
        ----------
        command_string : str
            Command_string the EnShell string to be executed.

        Returns
        -------
        tuple
            A tuple of (int, string) for (returnCode, returnString)
        """
        self.connect()
        if not self._stub:  # pragma: no cover
            return (0, "")  # pragma: no cover
        try:
            response = self._stub.run_command(
                enshell_pb2.EnShellCommandLine(command_line=command_string),
                metadata=self.metadata(),
            )
        except Exception:  # pragma: no cover
            raise IOError("gRPC connection dropped")  # pragma: no cover

        return (response.ret, response.response)

    def run_command_with_env(self, command_string: str, env_string: str):
        """send an EnShell command string and env var string to be executed in EnShell

        The string will be sent to EnShell via the EnShellService::run_command()
        gRPC call.  An IOError exception may be thrown
        if there's a gRPC communication problem.  The response
        is the tuple of the EnShell return code and return string.
        Parameters
        ----------
        command_string : str
            the EnShell string to be executed.
        env_string : str
            String of the environment.

        Returns
        -------
        Tuple
            A tuple of (int, string) for (returnCode, returnString)
        """
        self.connect()
        if not self._stub:  # pragma: no cover
            return (0, "")  # pragma: no cover
        try:
            response = self._stub.run_command_with_env(
                enshell_pb2.EnShellCommandWithEnvLine(
                    command_line=command_string, env_line=env_string
                ),
                metadata=self.metadata(),
            )
        except Exception:  # pragma: no cover
            raise IOError("gRPC connection dropped")  # pragma: no cover

        return (response.ret, response.response)

    # @brief Tell EnShell to start EnSight
    #
    # The string will be sent to EnShell via the EnShellService::run_command()
    # gRPC call.  An IOError exception may be thrown
    # if there's a gRPC communication problem.  The response
    # is the tuple of the EnShell return code and return string.
    # If ensight_env is used, the format is a single string of
    # environment variable name=value pairs with multiple pairs
    # separated by '\n' characters.
    # @param ensight_args arguments for the ensight command line
    # @param ensight_env optional environment variables to set before running EnSight
    # @return A tuple of (int, string) for (returnCode, returnString)
    def start_ensight(self, ensight_args: Optional[str] = None, ensight_env: Optional[str] = None):
        """Tell EnShell to start EnSight.

        The string will be sent to EnShell via the EnShellService::run_command()
        gRPC call.  An IOError exception may be thrown
        if there's a gRPC communication problem.  The response
        is the tuple of the EnShell return code and return string.

        Parameters
        ----------
        ensight_args : Optional[str], optional
            ensight_args arguments for the ensight command line, by default None

        Returns
        -------
        Tuple
            A tuple of (int, string) for (returnCode, returnString)
        """
        self.connect()

        command_string = "start_app CLIENT -c 127.0.0.1 -enshell"
        if self._security_token:
            command_string += " -security "
            command_string += str(self._security_token)
        if self._grpc_use_tcp_sockets:
            command_string += " -grpc_use_tcp_sockets"
        if self._grpc_allow_network_connections:
            command_string += " -grpc_allow_network_connections"
        if self._grpc_disable_tls:
            command_string += " -grpc_disable_tls"
        # does not make sense to forward this option along
        # if self._grpc_uds_pathname:
        #    command_string += " -grpc_uds_pathname "+self._grpc_uds_pathname
        if ensight_args and (ensight_args != ""):
            command_string += " " + ensight_args

        if ensight_env is None or ensight_env == "":  # pragma: no cover
            return self.run_command(command_string)
        else:
            return self.run_command_with_env(command_string, ensight_env)  # pragma: no cover

    def start_ensight_server(
        self, ensight_args: Optional[str] = None, ensight_env: Optional[str] = None
    ):
        """Tell EnShell to start the EnSight server.

        The string will be sent to EnShell via the EnShellService::run_command()
        gRPC call.  An IOError exception may be thrown
        if there's a gRPC communication problem.  The response
        is the tuple of the EnShell return code and return string.

        Parameters
        ----------
        ensight_args : Optional[str], optional
            ensight_args arguments for the ensight command line, by default None

        Returns
        -------
        Tuple
            A tuple of (int, string) for (returnCode, returnString)
        """
        self.connect()
        command_string = (
            f"start_app OTHER /ansys_inc/v{self.ansys_version()}/CEI/bin/ensight_server"
        )
        if self._security_token:
            command_string += " -security "
            command_string += str(self._security_token)
        if self._grpc_use_tcp_sockets:
            command_string += " -grpc_use_tcp_sockets"
        if self._grpc_allow_network_connections:
            command_string += " -grpc_allow_network_connections"
        if self._grpc_disable_tls:
            command_string += " -grpc_disable_tls"
        # does not make sense to forward this option along
        # if self._grpc_uds_pathname:
        #    command_string += " -grpc_uds_pathname "+self._grpc_uds_pathname
        if ensight_args and (ensight_args != ""):
            command_string += " " + ensight_args

        if ensight_env is None or ensight_env == "":  # pragma: no cover
            return self.run_command(command_string)
        else:
            return self.run_command_with_env(command_string, ensight_env)  # pragma: no cover

    # @brief
    #
    # @param cmd The command line
    # @return A tuple of (int, string) for (returnCode, returnString)
    def start_other(self, cmd: str, extra_env: Optional[str] = None):
        """Tell EnShell to start a non-EnShell aware command.

        The string will be sent to EnShell via the EnShellService::run_command()
        gRPC call.  An IOError exception may be thrown
        if there's a gRPC communication problem.  The response
        is the tuple of the EnShell return code and return string.

        Parameters
        ----------
        cmd : str
            _description_

        Returns
        -------
        _type_
            _description_
        """
        self.connect()
        command_string = "start_app OTHER " + cmd

        if extra_env is None or extra_env == "":  # pragma: no cover
            return self.run_command(command_string)
        else:
            return self.run_command_with_env(command_string, extra_env)  # pragma: no cover

    def cei_home(self):
        """Get the value of CEI_HOME from EnShell."""
        self._get_cei_home()
        return self._cei_home

    def ansys_version(self):
        """Get the Ansys version from EnShell (e.g. 232)"""
        self._get_cei_home()
        return self._ansys_version

    def _get_cei_home(self):
        if self._cei_home is not None:
            return

        self.connect()
        command_string = "show_ceihome"
        ret = self.run_command(command_string)
        # logging.debug(f"{command_string} :: ret = {ret}\n")
        if ret[0] != 0:  # pragma: no cover
            self._cei_home = None  # pragma: no cover
            raise RuntimeError("Error getting printenv from EnShell")  # pragma: no cover

        # split the newline delimited string into a list of strings
        env_vars = ret[1].strip().split("\n")
        # find the string containing CEI_HOME
        cei_home_line = [x for x in env_vars if "CEI_HOME" in x][0]
        if cei_home_line is None:  # pragma: no cover
            raise RuntimeError(
                "Error getting CEI_HOME env var from the Docker container.\n{ret}\n"
            )  # pragma: no cover

        # CEI_HOME is everything after the equal sign
        equal_sign_loc = cei_home_line.find("=")
        if equal_sign_loc < 0:  # pragma: no cover
            raise RuntimeError(
                "Error getting CEI_HOME env var from the Docker container.\n{ret}\n"
            )  # pragma: no cover
        self._cei_home = cei_home_line[equal_sign_loc + 1 :]
        m = re.search(r"/v(\d\d\d)/", self._cei_home)
        if not m:  # pragma: no cover
            self.stop_server()  # pragma: no cover
            raise RuntimeError(
                "Can't find version from cei_home in the Docker container.\n{ret}\n"
            )  # pragma: no cover
        self._ansys_version = m.group(1)
