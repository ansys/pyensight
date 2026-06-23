# Copyright (C) 2022 - 2026 ANSYS, Inc. and/or its affiliates.
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

"""Module to launch EnSight via a job scheduler."""

import atexit
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
import functools
import os
import re
import socket
import subprocess
import time
from typing import Any, Callable, List, Optional
import uuid
import warnings

import ansys.pyensight.core as pyensight
from ansys.pyensight.core.locallauncher import LocalLauncher
from ansys.pyensight.core.session import Session

SLURM_FILE_PREFIX = "pyensight_slurm"
PYTHON_SCRIPT_PREFIX = "launch_pyensight_slurm"
LOCALHOST = ["127.0.0.1", "localhost"]

SCHEDULER_FILE = """#!/bin/sh
#
##### use the specified partition
#SBATCH -p {partition}
##### use current working directory
#SBATCH -D {working_dir}
##### Specify the number of tasks
#SBATCH -n {tasks}
##### OutputFile
#SBATCH --output={output_file}
##### ErrorFile
#SBATCH --error={error_file}
{tasks_per_node}
{pyensight_debug}
export I_MPI_PIN_RESPECT_CPUSET=0
export SLURM_ENABLED=1
export SCHEDULER_TIGHT_COUPLING=1
export PYTHONUNBUFFERED=1
ENSIGHT_SCHEDULER_HOST_FILE="${{HOME}}/slurm.${{SLURM_JOB_ID}}.hosts"
/bin/rm -f ${{ENSIGHT_SCHEDULER_HOST_FILE}}
scontrol show hostnames "$SLURM_JOB_NODELIST" >> $ENSIGHT_SCHEDULER_HOST_FILE
#
echo "Running job on host: "
hostname
#
echo "env: "
env
env
#
#
{server_cmd}$ENSIGHT_SCHEDULER_HOST_FILE

#
#
echo "Done running job on host: "
hostname
"""

LAUNCH_FILE = """
import time
import argparse
from ansys.pyensight.core import LocalLauncher


def main():
    parser = argparse.ArgumentParser(
        description="Process a list of machine names separated by commas."
    )
    parser.add_argument(
        "machines",
        type=str,
        help="File containing the list of machines assigned"
    )

    args = parser.parse_args()
    with open(args.machines) as machine_file:
        machines = [l.strip() for l in machine_file.readlines()]
    launcher = LocalLauncher(
        ansys_installation='{ansys_installation}',
        batch={batch},
        use_sos={use_sos},
        server_hosts=machines,
        use_mpi='{use_mpi}',
        interconnect='{interconnect}',
        additional_command_line_options={additional_command_line_options},
        use_egl={use_egl},
        timeout={timeout},
        grpc_use_tcp_sockets={grpc_use_tcp_sockets},
        grpc_allow_network_connections={grpc_allow_network_connections},
        grpc_disable_tls={grpc_disable_tls},
        grpc_uds_pathname={grpc_uds_pathname}
    )
    session = launcher.start()
    print("Session data: \\\\n", flush=True)
    print(session, flush=True)
    print(f"Client Machine IP: {{session.machine_host()}}")
    print(f"Remote Session Directory: {{session._launcher._session_directory}}")
    while True:
        time.sleep(1)



if __name__ == "__main__":
    main()
"""


def _run_command(
    command: str, head_node: Optional[str] = None, account: Optional[str] = None, print_error=True
) -> Optional[str]:
    """Run a remote or local command depending on the headnode."""
    # If head_node is specified, run the command via ssh on the head node.
    # Otherwise, run it locally.
    try:
        if head_node and head_node not in LOCALHOST:
            if account:
                head_node = f"{account}@{head_node}"
            cmd = ["ssh", head_node, "-X", "-n"]
            cmd.extend(command.split(" "))
            output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
            if isinstance(output, bytes):
                output = output.decode("utf-8")
            return output.strip()
        else:
            output = subprocess.check_output(
                command.split(" "), text=True, stderr=subprocess.DEVNULL
            )
            if isinstance(output, bytes):
                output = output.decode("utf-8")
            return output.strip()
    except subprocess.CalledProcessError as e:
        if print_error:
            print(f"Error executing ssh command {command}: \n")
            print(e.output)
        return None


def _copy_file(source_file: str, head_node: str, account=None, dest="."):
    """Copy a file to a remote headnode."""
    if head_node:
        if account:
            dest = f"{account}@{head_node}:{dest}"
        else:
            dest = f"{head_node}:{dest}"
    cmd = ["scp", source_file, dest]
    try:
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        if isinstance(output, bytes):
            output = output.decode("utf-8")
        return output.strip() == ""
    except subprocess.CalledProcessError as e:
        print(f"Error copying file {source_file}: \n")
        print(e.output)
        return False


def _get_slurm_job_id(output: str) -> Optional[int]:
    """Get the job id from the sbatch output."""
    prefix = "Submitted batch job"
    for line in output.splitlines():
        if line.startswith(prefix):
            line = line.removeprefix(prefix).strip()
            return int(line)
    return None


class _SchedulerWrapper:
    """A class wrapping Scheduler commands."""

    running_states: List[str] = []
    cancelled_states: List[str] = []
    done_states: List[str] = []

    def __init__(
        self,
        headnode: Optional[str] = None,
        account: Optional[str] = None,
    ):
        self._headnode = headnode
        self._account = account

    def is_available(self) -> bool:
        """Check whether Scheduler is available.

        Returns
        -------
        bool
            ``True`` if Scheduler is available, otherwise ``False``.

        """
        raise NotImplementedError("Cannot call abstract method")

    @functools.lru_cache(maxsize=64)
    def list_queues(self) -> list[str]:
        """Return list of queues.

        Returns
        -------
        list[str]
        List of queues.
        """
        raise NotImplementedError("Cannot call abstract method")

    def get_state(self, job_id: int) -> Optional[str]:
        """Return state of a job.

        Parameters
        ----------
        job_id : int
            Job id.

        Returns
        -------
        str
            Any of the job status strings..
        """
        raise NotImplementedError("Cannot call abstract method")

    def cancel(self, job_id: int) -> None:
        """Cancel a job.

        Parameters
        ----------
        job_id : int
            Job id.
        """
        raise NotImplementedError("Cannot call abstract method")

    def submit_job(self, slurm_file: str) -> Optional[int]:
        """Submit a job."""
        raise NotImplementedError("Cannot call abstract method")

    def get_job_output(self, output_file: str):
        """Get the output of the job."""
        raise NotImplementedError("Cannot call abstract method")

    @functools.lru_cache(maxsize=64)
    def get_cpus_per_node_on_queue(self, queue: str):
        """Get the CPU info per node on a queue."""
        raise NotImplementedError("Cannot call abstract method")

    def ping_host(self, host: str):
        """Ping the input host on the submission host."""
        raise NotImplementedError("Cannot call abstract method")


class _SlurmWrapper(_SchedulerWrapper):
    """A class wrapping Slurm commands."""

    running_states: List[str] = ["RUNNING"]
    cancelled_states: List[str] = ["", "CANCELLED"]
    done_states: List[str] = ["", "CANCELLED", "COMPLETED"]

    def is_available(self) -> bool:
        """Check whether Slurm is available.

        Returns
        -------
        bool
            ``True`` if Slurm is available, otherwise ``False``.

        """
        data = _run_command("which sinfo", self._headnode, self._account)
        if not data:
            return False
        available = "Command not found" not in data
        queues_available = len(self.list_queues()) > 0
        return available and queues_available

    @functools.lru_cache(maxsize=64)
    def list_queues(self) -> list[str]:
        """Return list of queues.

        Returns
        -------
        list[str]
        List of queues.
        """

        queues = _run_command("sinfo --format=%P --noheader", self._headnode, self._account)
        if not queues:
            return []
        queues_split = queues.strip().split()
        queues_split = [q.removesuffix("*") for q in queues_split]
        return queues_split

    def get_state(self, job_id: int) -> Optional[str]:
        """Return state of a job.

        Parameters
        ----------
        job_id : int
            Job id.

        Returns
        -------
        str
            Any of ``""``, ``"RUNNING"``, ``"CANCELLED"`` or ``"COMPLETED"``.
        """
        cmd = ["squeue", "-j", f"{job_id}", "-o", '"%T"', "-h"]
        out = _run_command(" ".join(cmd), self._headnode, self._account)
        if not out:
            return out
        return out.strip().strip('"')

    def cancel(self, job_id: int) -> None:
        """Cancel a job.

        Parameters
        ----------
        job_id : int
            Job id.
        """
        cmd = ["scancel", f"{job_id}"]
        _run_command(" ".join(cmd), self._headnode, self._account)

    def submit_job(self, slurm_file: str) -> Optional[int]:
        """Submit a slurm job using the input slurm file."""
        cmd = ["sbatch", slurm_file]
        output = _run_command(" ".join(cmd), self._headnode, self._account)
        if not output:
            return None
        return _get_slurm_job_id(output)

    def get_job_output(self, output_file: str, print_error: bool = True):
        """Get the job output from the input output file."""
        if self._headnode and self._headnode not in LOCALHOST:
            output = _run_command(f"cat {output_file}", self._headnode, self._account, print_error)
            if not output:
                return output
        else:
            with open(output_file) as outfile:
                output = outfile.read()
        return output

    @functools.lru_cache(maxsize=64)
    def get_cpus_per_node_on_queue(self, queue: str):
        """Get the number of CPUs per node on the input queue."""
        cmd = ["sinfo", "-p", f"{queue}", "-o", "'%c'", "|", "grep", "-v", "CPUS"]
        cpus_output = _run_command(" ".join(cmd), self._headnode, self._account)
        if not cpus_output:
            return cpus_output
        cpu_values = re.search("([0-9]+)", cpus_output)
        if not cpu_values:
            raise RuntimeError("Cannot get CPU info for queue.")
        cpus = int(cpu_values.group(1))
        return cpus

    def ping_host(self, host: str):
        """Pint the input host on the headhode."""
        cmd = ["ping", "-w", "1", host]
        _run_command(" ".join(cmd), self._headnode, self._account)


class SchedulerFuture:
    """Encapsulates asynchronous launch of EnSight within a Scheduler environment.

    The interface is similar to Python's
    `future object <https://docs.python.org/3/library/asyncio-future.html#future-object>`_.
    """

    def __init__(
        self,
        future: Future,
        job_id: int,
        scheduler_instance: _SchedulerWrapper,
        output_file: str,
        error_file: str,
    ):
        """Initialize SchedulerFuture."""
        self._future = future
        self._job_id = job_id
        self._scheduler_instance = scheduler_instance
        self._output_file = output_file
        self._error_file = error_file

    def __enter__(self):
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any):
        self.cancel()

    def _get_state(self) -> Optional[str]:
        return self._scheduler_instance.get_state(self._job_id)

    def _cancel(self):
        self._scheduler_instance.cancel(self._job_id)

    def cancel(self, timeout: int = 60) -> bool:
        """Attempt to cancel the EnSight launch within timeout seconds.

        Parameters
        ----------
        timeout : int, optional
            timeout in seconds, by default 60

        Returns
        -------
        bool
            ``True`` if the EnSight launch is successfully cancelled, otherwise ``False``.

        Raises
        ------
        RuntimeError
            If the Scheduler job cannot be cancelled from client
        """
        if self.done():
            return False
        self._cancel()
        for _ in range(timeout):
            if self._get_state() in self._scheduler_instance.cancelled_states:
                return True
            time.sleep(1)
        return False

    def running(self) -> bool:
        """Return ``True`` if EnSight is currently running, otherwise ``False``.

        Returns
        -------
        bool
            ``True`` if EnSight is currently running, otherwise ``False``.

        Raises
        ------
        RuntimeError
            If the Scheduler job state cannot be obtained from client
        """
        return self._get_state() in self._scheduler_instance.running_states and self._future.done()

    def pending(self) -> bool:
        """Return ``True`` if the EnSight launch is currently waiting for Scheduler
        allocation or EnSight is being launched, otherwise ``False``.

        Returns
        -------
        bool
            ``True`` if the EnSight launch is currently waiting for Scheduler
            allocation or EnSight is being launched, otherwise ``False``.

        Raises
        ------
        RuntimeError
            If the Scheduler job state cannot be obtained from client
        """
        return self._future.running()

    def done(self) -> bool:
        """Return ``True`` if the EnSight launch was successfully cancelled or EnSight was
        finished running, otherwise ``False``.

        Returns
        -------
        bool
            ``True`` if the EnSight launch was successfully cancelled or EnSight was
            finished running, otherwise ``False``.

        Raises
        ------
        RuntimeError
            If Scheduler job state cannot be obtained from client
        """
        return self._get_state() in self._scheduler_instance.done_states

    def result(self, timeout: Optional[float] = None) -> Session:
        """Return the session instance corresponding to the PyEnSight launch. If EnSight
        hasn't yet launched, then this method will wait up to timeout seconds. If EnSight
        hasn't launched in timeout seconds, then a TimeoutError will be raised. If
        timeout is not specified or None, there is no limit to the wait time.

        If the EnSight launch raised an exception, this method will raise the same exception.

        Parameters
        ----------
        timeout : int, optional
            timeout in seconds

        Returns
        -------
        (Session):
            The PyEnSight session instance corresponding to the EnSight launch.
        """
        return self._future.result(timeout)

    def exception(self, timeout: Optional[float] = None) -> Optional[BaseException]:
        """Return the exception raised by the EnSight launch. If EnSight hasn't yet
        launched, then this method will wait up to timeout seconds. If EnSight hasn't
        launched in timeout seconds, then a TimeoutError will be raised. If timeout is
        not specified or None, there is no limit to the wait time.

        If the EnSight launch completed without raising, None is returned.

        Parameters
        ----------
        timeout : int, optional
            timeout in seconds

        Returns
        -------
        Exception
            The exception raised by the EnSight launch.
        """
        return self._future.exception(timeout)

    def add_done_callback(self, fn: Callable):
        """Attaches the callable function. The function will be called, with the session
        as its only argument, when EnSight is launched.

        Parameters
        ----------
        fn : Callable
            Callback function.
        """
        self._future.add_done_callback(fn)

    def get_output(self):
        """Get the current output of the job from its output file."""
        return self._scheduler_instance.get_job_output(self._output_file)

    def get_error(self):
        """Get the current errors of the job from its error file."""
        return self._scheduler_instance.get_job_output(self._error_file)


SCHEDULER_MAP = {"SLURM": _SlurmWrapper}


class SchedulerLauncher(LocalLauncher):
    """Creates a ``Session`` instance by launching EnSight via a job scheduler.

    The default option is to launch the client and the servers on the allocated nodes,
    with the client running on the first allocated node.
    Alternatively, the client can be launched on the host from which the SchedulerLauncher
    is started, that might be the submittion host itself, or a client machine submitting to
    a remote submission host. Right now only SLURM is supported.
    The server ansys installation path must be provided via the ansys_installation argument.
    There is also a separate argument called client_ansys_installation. This is equivalent to passing
    "ansys_installation" on the LocalLauncher, i.e. it will find a local EnSight install automatically if
    not provided. This will be used to launch a local client if needed.
    The user can also provide a Python path via the argument "python_loc". This will be used only for the case
    the client runs on the allocated nodes, so that one can provide an alternative Python path to launch the
    remote PyEnSight different from the remote ansys install.

    Parameters
    ----------
    ansys_installation: str
        The server EnSight installation. It can be either an Ansys install
        or its CEI subfolder. It must be provided, and is validated during
        the launcher creation.
    scheduler: str
        The scheduler to be used. Defaults to SLURM.
            Right now only SLURM is supported
    submission_host: str
        The submission host. If not provided, it defaults to 127.0.0.1
    account: str
        The account to be used. If not provided, and if the submission host
        is not 127.0.0.1/localhost, it defaults to the current user.
    queue: str
        The queue to be used. Can be set also after
        the launcher instance creation via the queue parameter
    python_location: str
        An optional python location to run the remote PyEnSight from.
        This is ignored if client_on_pyensight_host is set to True.
        If not provided and client_on_pyensight_host is False,
        it defaults to the server EnSight Python.
    working_directory: str
        The job working directory. It defaults to ".", i.e. the account
        user home.
    use_sos: int
        The number of EnSight servers to be used. Defaults to 1.
        This is converted in tasks number in the SLURM file.
        The number of tasks set will be equivalent to use_sos+1,
        to account for the SOS server. To manage the number of nodes
        allocation use tasks_per_node.
    tasks_per_node: int
        The number of tasks per node. This is effectively equivalent
        to set how many servers per node are distributed, plus one for the SOS.
        Can be used in conjunction to use_sos to force the spreading of
        EnSight Servers among different nodes.
        For instance, if use_sos is set to 4, setting tasks_per_node to 2
        will force the spawning of 3 nodes; the first two will contain two EnSight
        servers each, the third will contain the SOS server.
        This might be required for distributing the dataset among multiple machines
        for memory requirements.
    client_on_pyensight_host: bool
        Force the launch of the EnSight client on the host where
        the SchedulerLauncher is being invoked. It defaults to False.
        If False, the EnSight client is launched on the first allocated node.
        Setting it to True can be useful for cases where one wants to run
        the EnSight Client on the local machine while the servers are spawned on
        a remote cluster, or if the EnSight client is to be run on the
        submission host itself.
    client_ansys_installation: str
        The EnSight client installation. Used if client_on_pyensight_host is
        set to True. If not provided, defaults to the ansys_installation value.
        The latter will work only if the client is being launched on the submission
        host itself, that should have access to the (server) ansys installation.
        So it needs to be provided if the EnSight client is running on a local
        machine, and the submission host is remote.
    ssh_tunneling_server_to_client: bool
        Set to True if ssh tunneling is required from the server machine
        to the client machine. Ignored if client_on_pyensight_host is False.
    ssh_tunneling_client_to_server: bool
        Set to True if ssh tunneling is required from the client machine
        to the server machine. Ignored if client_on_pyensight_host is False.
    use_egl: bool
        It defaults to False. Setting it to True can be useful if the user
        wants to force hardware acceleration, provided the EGL drivers are
        available on the EnSight client host.
    use_mpi: str
        It defaults to intel2021.
        The valid values depend on the EnSight version to be used.
        The user can see the specific list starting the EnSight Launcher manually
        and specifying the options to launch EnSight in parallel and MPI.
        Here are reported the values from release 2024R2 up to release 2026R1.

        =================== =========================================
        Release             Valid MPI Types
        =================== =========================================
        2024R2-2026R1       intel2021, intel2018, openmpi
        =================== =========================================

        The remote nodes must be Linux nodes.
    interconnet: str, optional
        It defaults to "ethernet". EnSight will be launched with
        the MPI Interconnect selected. Valid values
        are "ethernet", "infiniband".
    grpc_use_tcp_sockets:
        If using gRPC, and if True, then allow TCP Socket based connections
        instead of only local connections. It must be set to True if
        client_on_pyensight_host is set to True, but it is the user
        responsibility doing it.
    grpc_allow_network_connections:
        If using gRPC and using TCP Socket based connections, listen on all networks.
        It must be set to True if client_on_pyensight_host is set to True
        and the submission host is remote, but it is the user
        responsibility doing it.
    grpc_disable_tls:
        If using gRPC and using TCP Socket based connections, disable TLS.
    grpc_uds_pathname:
        If using gRPC and using Unix Domain Socket based connections, explicitly
        set the pathname to the shared UDS file instead of using the default.
        This is valid only if client_on_pyensight_host is set to False, but it
        is the user responsibility doing it.
    job_launch_timeout: float
        Ignored if client_on_pyensight_host is True. It sets a timeout for the remote
        PyEnSight session object to be created from the SLURM job.
    """

    SLURM_SCHEDULER: str = "SLURM"

    def __init__(
        self,
        # new options,
        scheduler: str = SLURM_SCHEDULER,
        submission_host="127.0.0.1",
        account: Optional[str] = None,
        queue: Optional[str] = None,
        python_location: Optional[str] = None,
        working_directory: str = ".",
        tasks_per_node: int = 0,
        job_launch_timeout: float = 300.0,
        client_on_pyensight_host=False,
        client_ansys_installation: Optional[str] = None,
        ssh_tunneling_server_to_client: bool = False,
        ssh_tunneling_client_to_server: bool = False,
        # Existing options
        ansys_installation: Optional[str] = None,
        grpc_use_tcp_sockets: Optional[bool] = False,
        grpc_allow_network_connections: Optional[bool] = False,
        grpc_disable_tls: Optional[bool] = False,
        grpc_uds_pathname: Optional[str] = None,
        use_sos: int = 1,
        additional_command_line_options: Optional[List] = None,
        use_mpi: Optional[str] = "intel2021",
        interconnect: Optional[str] = "ethernet",
        use_egl: bool = False,
        **kwargs,
    ):
        if scheduler != "SLURM":
            raise RuntimeError("Only slurm is supported as scheduler.")
        if not ansys_installation:
            raise RuntimeError(
                "At least ansys installation must be provided. This must be the remote server ansys install."
            )
        self._client_on_pyensight_host = client_on_pyensight_host
        self._server_ansys_installation = ansys_installation
        # The init method finds the EnSight install local to the PyEnSight launcher
        super().__init__(
            ansys_installation=ansys_installation,
            grpc_allow_network_connections=grpc_allow_network_connections,
            grpc_disable_tls=grpc_disable_tls,
            grpc_uds_pathname=grpc_uds_pathname,
            grpc_use_tcp_sockets=grpc_use_tcp_sockets,
            use_sos=use_sos,
            use_mpi=use_mpi,
            additional_command_line_options=additional_command_line_options,
            interconnect=interconnect,
            use_egl=use_egl,
            **kwargs,
        )
        self._client_ansys_installation = (
            client_ansys_installation if client_ansys_installation else ansys_installation
        )
        if self._client_on_pyensight_host:
            self._client_ansys_installation = super().get_cei_install_directory(
                self._client_ansys_installation
            )
        tunneling = "R" if ssh_tunneling_server_to_client else None
        tunneling = "L" if ssh_tunneling_client_to_server else tunneling
        self._tunneling = tunneling
        # If not server ansys install provided, assume that the script
        # is being run on the submission host, hence ansys installation is
        # also the server location
        self._client_server_port = None
        if self._client_on_pyensight_host:
            self._set_local_ports()
            self._client_server_port = self._ports[4]
        # Client will be launched on the first allocated node
        if not self._client_on_pyensight_host:
            self._interconnect = interconnect
            self._use_mpi = use_mpi
        self._submission_host = submission_host
        if self._submission_host not in LOCALHOST:
            warnings.warn(
                "SSH will be used. It will work only if a passwordless connection to the headnode is set up."
            )
        self._account = account
        if not self._account and self._submission_host not in LOCALHOST:
            warnings.warn("No account provided. Defaulting to the current user.")
            self._account = os.getlogin()
        scheduler_found = SCHEDULER_MAP.get(scheduler)
        if not scheduler_found:
            raise RuntimeError(f"Scheduler {scheduler} not supported.")
        self._scheduler_instance = scheduler_found(self._submission_host, self._account)
        self._validate_server_ansys_installation()
        if not self._check_slurm_available():
            raise RuntimeError(
                f"Slurm not available on headnode {self._submission_host} for user {self._account}."
            )
        self._working_dir = working_directory
        self._tasks_per_node = tasks_per_node
        self._python_loc = python_location
        if self._client_on_pyensight_host and self._python_loc:
            warnings.warn("python_loc is ignored if the EnSight client runs on the current host.")
        if not self._python_loc and not self._client_on_pyensight_host:
            self._python_loc = f"{self._server_ansys_installation}/bin/cpython"
        self._output_file: Optional[str] = None
        self._error_file: Optional[str] = None
        self._job_timeout = job_launch_timeout
        self._internal_launcher = None
        self._secret_key = str(uuid.uuid1())
        self._queue = queue
        self._future: Optional["SchedulerFuture"] = None
        self._client_machine = None
        atexit.register(self.stop)

    @staticmethod
    def get_cei_install_directory(ansys_installation):
        """Override base get_cei_install_directory.

        Ansys installation is a server install, so the LocalLauncher
        get_cei_install_directory cannot be used.
        """
        return ansys_installation

    @property
    def queue(self):
        """Get the current queue."""
        return self._queue

    @queue.setter
    def queue(self, _queue):
        """Set the input queue"""
        self._queue = _queue

    def _start_internal_launcher(self):
        """Create a local launcher instance that starts the EnSight client.

        The client is launched on the host where SchedulerLauncher is invoked.
        """
        additional = ["-cm"]
        if self._additional_command_line_options:
            additional.extend(self._additional_command_line_options)
        self._internal_launcher = LocalLauncher(
            ansys_installation=self._client_ansys_installation,
            batch=self._batch,
            additional_command_line_options=additional,
            use_egl=self._use_egl_param_val,
            timeout=self._timeout,
            grpc_use_tcp_sockets=self._grpc_use_tcp_sockets,
            grpc_allow_network_connections=self._grpc_allow_network_connections,
            grpc_disable_tls=self._grpc_allow_network_connections,
            grpc_uds_pathname=self._grpc_uds_pathname,
            application="ensight_client",
        )
        self._internal_launcher._ports = self._ports
        self._internal_launcher._bypass_ports = True
        self._internal_launcher._secret_key = self._secret_key

    def get_available_queues(self):
        """Get the queue of the current headnode scheduler."""
        return self._scheduler_instance.list_queues()

    def get_cpus_per_node_on_queue(self, queue: str):
        """Get the cpus per node of the queue of the current headnode scheduler."""
        return self._scheduler_instance.get_cpus_per_node_on_queue(queue)

    def _validate_server_ansys_installation(self):
        """Validate the remote server install.

        The provided install is checked if being directly the CEI folder
        or an Ansys install. If both don't work, the remote AWP_ROOT###
        variable is tried, where ### is the current
        ansys.pyensight.core.__version__ value.
        """
        # path contains CEI
        output = _run_command(
            f"ls {self._server_ansys_installation}/bin/ensight",
            self._submission_host,
            self._account,
            False,
        )
        if not output:
            output = _run_command(
                f"ls {self._server_ansys_installation}/CEI/bin/ensight",
                self._submission_host,
                self._account,
                False,
            )
            if not output:
                # Try AWP_ROOT
                output = _run_command(
                    f"$AWP_ROOT{pyensight.__ansys_version__}",
                    self._submission_host,
                    self._account,
                    False,
                )
                if not output:
                    raise RuntimeError(
                        f"Cannot find Ansys installation on submission host {self._submission_host}"
                    )
                output = f"{self._server_ansys_installation}/CEI"
            else:
                output = f"{self._server_ansys_installation}/CEI"
        else:
            output = f"{self._server_ansys_installation}"
        self._server_ansys_installation = output
        print(f"Found remote EnSight installation at {self._server_ansys_installation}")

    def _check_slurm_available(self):
        """Check if slurm is available on the headnode."""
        return self._scheduler_instance.is_available()

    def _set_tasks_per_node(self):
        """Set the number of tasks per node in the SLURM script."""
        if self._tasks_per_node:
            return (
                "##### specify number of EnSight Servers per node\n"
                f"#SBATCH --ntasks-per-node={self._tasks_per_node}"
            )
        return ""

    @staticmethod
    def _build_timestamp():
        """Build a timestamp to be used for all the input files."""
        now = datetime.now()
        return f"{now.year}{now.month}{now.day}{now.hour}{now.minute}"

    def _check_ips(self, ips):
        """Check if the input ips can be pinged on the headnode."""
        for ip in ips:
            try:
                self._scheduler_instance.ping_host(ip)
                return ip
            except Exception:
                continue
        return None

    @staticmethod
    def _pyensight_debug():
        debug_set = os.environ.get("PYENSIGHT_DEBUG")
        if debug_set:
            return f"export PYENSIGHT_DEBUG={debug_set}"
        return ""

    def _create_slurm_file(self, timestamp: str, python_script: str):
        """Create the input SLURM script for the job.

        If client_on_pyensight_host is False, the SLURM script
        will launch PyEnSight and the current process will connect to it.
        Otherwise, the EnSight client will be launched on the host
        where SchedulerLauncher is invoked, while the SLURM script
        just launches the servers and connect to the client.
        """
        slurm_file = f"{SLURM_FILE_PREFIX}_{timestamp}.slurm"
        self._output_file = slurm_file.replace(".slurm", ".out")
        self._error_file = slurm_file.replace(".slurm", ".err")
        if self._client_on_pyensight_host:
            orig_client_machine = socket.gethostname()
            self._client_machine = self._check_ips([orig_client_machine])
            if not self._client_machine:
                ips = socket.gethostbyname_ex(orig_client_machine)[2]
                self._client_machine = self._check_ips(ips)
                if not self._client_machine:
                    raise RuntimeError(
                        (
                            f"Current machine {socket.gethostname()} is not reachable from"
                            " the submission host."
                        )
                    )
            server_cmd = f"{self._server_ansys_installation}/bin/ensight_server"
            if self._use_sos:
                port = self._internal_launcher._ports[4]
                server_cmd += f" -ports {port} "
                server_cmd += f" -c {self._client_machine} "
                server_cmd += f" -security {self._secret_key}"
                if self._tunneling:
                    server_cmd += f" -sshtunneloption {self._tunneling} {port}:127.0.0.1:{port}"
                server_cmd += " -sos --rsh=ssh"
                server_cmd += f" --np={int(self._use_sos) + 1}"
                server_cmd += f" --mpi={self._use_mpi}"
                server_cmd += f" --ic={self._interconnect} "
                server_cmd += " --cnf="
        else:
            server_cmd = f"{self._python_loc} -u {python_script} "
        with open(slurm_file, "w", newline="\n") as slurm_input:
            slurm_input.write(
                SCHEDULER_FILE.format(
                    partition=self._queue,
                    working_dir=self._working_dir,
                    tasks_per_node=self._set_tasks_per_node(),
                    server_cmd=server_cmd,
                    output_file=self._output_file,
                    error_file=self._error_file,
                    tasks=self._use_sos + 1,
                    pyensight_debug=self._pyensight_debug(),
                )
            )
        return slurm_file

    def _create_python_and_slurm_file(self, timestamp: str):
        """Create the input Python and SLURM script.

        The SLURM script is always created. No Python
        script is created if client_on_pyensight_host is True.
        """
        python_file = f"{PYTHON_SCRIPT_PREFIX}_{timestamp}.py"
        slurm_file = self._create_slurm_file(timestamp, python_file)
        install_path = self._install_path
        if self._client_on_pyensight_host:
            return slurm_file, None
        install_path = self._server_ansys_installation
        with open(python_file, "w", newline="\n") as python_input:
            python_input.write(
                LAUNCH_FILE.format(
                    ansys_installation=install_path,
                    batch=self._batch,
                    use_sos=self._use_sos,
                    use_mpi=self._use_mpi,
                    interconnect=self._interconnect,
                    additional_command_line_options=self._additional_command_line_options,
                    use_egl=self._use_egl_param_val,
                    timeout=self._timeout,
                    grpc_use_tcp_sockets=self._grpc_use_tcp_sockets,
                    grpc_allow_network_connections=self._grpc_allow_network_connections,
                    grpc_disable_tls=self._grpc_disable_tls,
                    grpc_uds_pathname=(
                        repr(self._grpc_uds_pathname) if self._grpc_uds_pathname else None
                    ),
                )
            )
        return slurm_file, python_file

    @staticmethod
    def _parse_job_output_for_session(output):
        """Parse the SLURM output file for the PyEnSight session data."""
        secret_key = re.search("secret_key=(.*?),", output).group(1).replace("'", "")
        html_port = int(re.search("html_port=(.*?),", output).group(1))
        grpc_port = int(re.search("grpc_port=(.*?),", output).group(1))
        ws_port = int(re.search("ws_port=(.*?),", output).group(1))
        sos = re.search("sos=(.*?),", output).group(1)
        rest_api = re.search("rest_api=(.*?),", output).group(1)
        client_machine_host = re.search(r"Client Machine IP: (.*?)\n", output).group(1)
        remote_session_dir = re.search("Remote Session Directory: (.*)", output).group(1)
        return (
            secret_key,
            html_port,
            grpc_port,
            ws_port,
            sos,
            rest_api,
            client_machine_host,
            remote_session_dir,
        )

    def _launch(self):
        """Launch the PyEnSight session."""
        now = time.time()
        if self._client_on_pyensight_host:
            session = self._internal_launcher.start()
            session._scheduler_session = True
            self._sessions.append(session)
            session._html_hostname = self._client_machine
            return session
        else:

            while time.time() - now < self._job_timeout:
                job_output = self._scheduler_instance.get_job_output(self._output_file, False)
                if (
                    job_output
                    and "Session(host" in job_output
                    and "Client Machine IP" in job_output
                ):
                    (
                        secret_key,
                        html_port,
                        grpc_port,
                        ws_port,
                        sos,
                        rest_api,
                        client_machine_host,
                        remote_session_dir,
                    ) = self._parse_job_output_for_session(job_output)
                    self._session_directory = remote_session_dir
                    self._secret_key = secret_key
                    session = Session(
                        host=client_machine_host,
                        secret_key=secret_key,
                        grpc_port=grpc_port,
                        ws_port=ws_port,
                        html_port=html_port,
                        html_hostname=client_machine_host,
                        grpc_allow_network_connections=self._grpc_allow_network_connections,
                        grpc_disable_tls=self._grpc_disable_tls,
                        grpc_use_tcp_sockets=self._grpc_use_tcp_sockets,
                        grpc_uds_pathname=self._grpc_uds_pathname,
                        rest_api=rest_api == "True",
                        sos=sos == "True",
                        session_directory=remote_session_dir,
                    )
                    self._sessions.append(session)
                    session._launcher = self
                    return session
                else:
                    time.sleep(10)
        raise RuntimeError("PyEnSight session didn't start within the job timeout.")

    def start(self) -> SchedulerFuture:
        """Start the job.

        Returns
        -------
        future: SchedulerFuture
            a future-like object, with interfaces that
            can let you check the job status.
            future.result() will return the PyEnSight session
            once ready. It accepts an input timeout in seconds.
        """
        timestamp = self._build_timestamp()
        if self._client_on_pyensight_host:
            self._start_internal_launcher()
        slurm_file, python_file = self._create_python_and_slurm_file(timestamp)
        if self._submission_host not in LOCALHOST:
            sent_slurm = _copy_file(
                slurm_file,
                self._submission_host,
                self._account,
            )
            if python_file:
                sent_python = _copy_file(
                    python_file,
                    self._submission_host,
                    self._account,
                )
            if not sent_slurm:
                raise RuntimeError("Could not send slurm script to submission host.")
            if python_file and not sent_python:
                raise RuntimeError("Could not send python script to submission host.")
        job_id = self._scheduler_instance.submit_job(slurm_file)
        if not self._output_file or not self._error_file:
            raise RuntimeError("Output File and Error file of the job haven't been set up.")
        if not job_id:
            raise RuntimeError("Error while submitting job.")
        self._future = SchedulerFuture(
            ThreadPoolExecutor(max_workers=1).submit(self._launch),
            job_id,
            self._scheduler_instance,
            self._output_file,
            self._error_file,
        )
        return self._future

    def stop(self):
        self._future.cancel()
        return super().stop()
