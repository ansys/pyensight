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

from concurrent.futures import Future
import os
import subprocess
from unittest import mock

from ansys.pyensight.core.locallauncher import LocalLauncher
from ansys.pyensight.core.schedulerlauncher import (
    SCHEDULER_MAP,
    SchedulerFuture,
    SchedulerLauncher,
    _copy_file,
    _get_slurm_job_id,
    _run_command,
    _SchedulerWrapper,
    _SlurmWrapper,
)
import pytest

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def slurm_wrapper():
    """Return a _SlurmWrapper that will not invoke real SSH / subprocess."""
    return _SlurmWrapper(headnode=None, account=None)


@pytest.fixture
def remote_slurm_wrapper():
    """Return a _SlurmWrapper pointing at a remote headnode."""
    return _SlurmWrapper(headnode="remote.host", account="testuser")


def _make_scheduler_launcher(mocker, **overrides):
    """Helper to build a SchedulerLauncher with everything mocked."""
    mocker.patch.object(LocalLauncher, "get_cei_install_directory", return_value="/path/to/awp/CEI")
    mocker.patch.object(
        SchedulerLauncher,
        "_validate_server_ansys_installation",
    )
    mocker.patch.object(
        SchedulerLauncher,
        "_check_slurm_available",
        return_value=True,
    )
    defaults = dict(
        ansys_installation="/remote/ansys/install",
        scheduler="SLURM",
        submission_host="127.0.0.1",
    )
    defaults.update(overrides)
    return SchedulerLauncher(**defaults)


# ---------------------------------------------------------------------------
# _run_command
# ---------------------------------------------------------------------------


class TestRunCommand:
    def test_local_command(self, mocker):
        mocker.patch.object(subprocess, "check_output", return_value="  hello world  ")
        result = _run_command("echo hello", head_node=None)
        assert result == "hello world"
        subprocess.check_output.assert_called_once_with(
            ["echo", "hello"], text=True, stderr=subprocess.DEVNULL
        )

    def test_remote_command_without_account(self, mocker):
        mocker.patch.object(subprocess, "check_output", return_value="remote-output")
        result = _run_command("hostname", head_node="remote.host")
        subprocess.check_output.assert_called_once_with(
            ["ssh", "remote.host", "-X", "-n", "hostname"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        assert result == "remote-output"

    def test_remote_command_with_account(self, mocker):
        mocker.patch.object(subprocess, "check_output", return_value="remote-output")
        result = _run_command("hostname", head_node="remote.host", account="user")
        subprocess.check_output.assert_called_once_with(
            ["ssh", "user@remote.host", "-X", "-n", "hostname"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        assert result == "remote-output"

    def test_command_failure_returns_none(self, mocker):
        mocker.patch.object(
            subprocess,
            "check_output",
            side_effect=subprocess.CalledProcessError(1, "cmd", output="err"),
        )
        result = _run_command("bad_cmd", head_node=None, print_error=False)
        assert result is None

    def test_command_failure_prints_error(self, mocker, capsys):
        mocker.patch.object(
            subprocess,
            "check_output",
            side_effect=subprocess.CalledProcessError(1, "cmd", output="some error"),
        )
        result = _run_command("bad_cmd", head_node="host")
        assert result is None
        captured = capsys.readouterr()
        assert "Error executing ssh command" in captured.out


# ---------------------------------------------------------------------------
# _copy_file
# ---------------------------------------------------------------------------


class TestCopyFile:
    def test_copy_to_remote_with_account(self, mocker):
        mocker.patch.object(subprocess, "check_output", return_value="")
        result = _copy_file("file.txt", "remote.host", account="user", dest="/tmp")
        subprocess.check_output.assert_called_once_with(
            ["scp", "file.txt", "user@remote.host:/tmp"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        assert result is True

    def test_copy_to_remote_without_account(self, mocker):
        mocker.patch.object(subprocess, "check_output", return_value="")
        result = _copy_file("file.txt", "remote.host")
        subprocess.check_output.assert_called_once_with(
            ["scp", "file.txt", "remote.host:."],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        assert result is True

    def test_copy_local(self, mocker):
        mocker.patch.object(subprocess, "check_output", return_value="")
        result = _copy_file("file.txt", None)
        subprocess.check_output.assert_called_once_with(
            ["scp", "file.txt", "."],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        assert result is True

    def test_copy_failure(self, mocker, capsys):
        mocker.patch.object(
            subprocess,
            "check_output",
            side_effect=subprocess.CalledProcessError(1, "scp", output="permission denied"),
        )
        result = _copy_file("file.txt", "host")
        assert result is False
        captured = capsys.readouterr()
        assert "Error copying file" in captured.out


# ---------------------------------------------------------------------------
# _get_slurm_job_id
# ---------------------------------------------------------------------------


class TestGetSlurmJobId:
    def test_extracts_job_id(self):
        output = "Some preamble\nSubmitted batch job 12345\nDone"
        assert _get_slurm_job_id(output) == 12345

    def test_returns_none_when_no_match(self):
        assert _get_slurm_job_id("No job id here\n") is None

    def test_single_line(self):
        assert _get_slurm_job_id("Submitted batch job 99") == 99


# ---------------------------------------------------------------------------
# _SchedulerWrapper (abstract base)
# ---------------------------------------------------------------------------


class TestSchedulerWrapper:
    def test_abstract_methods_raise(self):
        wrapper = _SchedulerWrapper(headnode=None, account=None)
        with pytest.raises(NotImplementedError):
            wrapper.is_available()
        with pytest.raises(NotImplementedError):
            wrapper.list_queues()
        with pytest.raises(NotImplementedError):
            wrapper.get_state(1)
        with pytest.raises(NotImplementedError):
            wrapper.cancel(1)
        with pytest.raises(NotImplementedError):
            wrapper.submit_job("file.slurm")
        with pytest.raises(NotImplementedError):
            wrapper.get_job_output("file.out")
        with pytest.raises(NotImplementedError):
            wrapper.get_cpus_per_node_on_queue("queue")
        with pytest.raises(NotImplementedError):
            wrapper.ping_host("host")


# ---------------------------------------------------------------------------
# _SlurmWrapper
# ---------------------------------------------------------------------------


class TestSlurmWrapper:
    def test_class_states(self):
        assert _SlurmWrapper.running_states == ["RUNNING"]
        assert _SlurmWrapper.cancelled_states == ["", "CANCELLED"]
        assert _SlurmWrapper.done_states == ["", "CANCELLED", "COMPLETED"]

    def test_is_available_true(self, mocker, slurm_wrapper):
        mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
            return_value="/usr/bin/sinfo",
        )
        # list_queues is lru_cached; create fresh instance
        wrapper = _SlurmWrapper(headnode=None, account=None)
        mocker.patch.object(wrapper, "list_queues", return_value=["batch", "debug"])
        assert wrapper.is_available() is True

    def test_is_available_false_command_not_found(self, mocker):
        mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
            return_value="Command not found",
        )
        wrapper = _SlurmWrapper(headnode=None, account=None)
        assert wrapper.is_available() is False

    def test_is_available_false_no_data(self, mocker):
        mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
            return_value=None,
        )
        wrapper = _SlurmWrapper(headnode=None, account=None)
        assert wrapper.is_available() is False

    def test_list_queues(self, mocker):
        mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
            return_value="batch*\ndebug\ngpu",
        )
        wrapper = _SlurmWrapper(headnode=None, account=None)
        queues = wrapper.list_queues()
        assert queues == ["batch", "debug", "gpu"]

    def test_list_queues_empty(self, mocker):
        mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
            return_value=None,
        )
        wrapper = _SlurmWrapper(headnode=None, account=None)
        assert wrapper.list_queues() == []

    def test_get_state(self, mocker, slurm_wrapper):
        mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
            return_value='"RUNNING"',
        )
        assert slurm_wrapper.get_state(123) == "RUNNING"

    def test_get_state_none(self, mocker, slurm_wrapper):
        mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
            return_value=None,
        )
        assert slurm_wrapper.get_state(123) is None

    def test_cancel(self, mocker, slurm_wrapper):
        mock_run = mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
        )
        slurm_wrapper.cancel(999)
        mock_run.assert_called_once_with("scancel 999", None, None)

    def test_submit_job(self, mocker, slurm_wrapper):
        mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
            return_value="Submitted batch job 42",
        )
        assert slurm_wrapper.submit_job("test.slurm") == 42

    def test_submit_job_failure(self, mocker, slurm_wrapper):
        mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
            return_value=None,
        )
        assert slurm_wrapper.submit_job("test.slurm") is None

    def test_get_job_output_local(self, mocker, slurm_wrapper, tmp_path):
        outfile = tmp_path / "job.out"
        outfile.write_text("job output content")
        result = slurm_wrapper.get_job_output(str(outfile))
        assert result == "job output content"

    def test_get_job_output_remote(self, mocker, remote_slurm_wrapper):
        mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
            return_value="remote output",
        )
        result = remote_slurm_wrapper.get_job_output("/path/to/job.out")
        assert result == "remote output"

    def test_get_job_output_remote_none(self, mocker, remote_slurm_wrapper):
        mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
            return_value=None,
        )
        result = remote_slurm_wrapper.get_job_output("/path/to/job.out")
        assert result is None

    def test_get_cpus_per_node_on_queue(self, mocker):
        mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
            return_value="'32'",
        )
        wrapper = _SlurmWrapper(headnode=None, account=None)
        assert wrapper.get_cpus_per_node_on_queue("batch") == 32

    def test_get_cpus_per_node_on_queue_none(self, mocker):
        mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
            return_value=None,
        )
        wrapper = _SlurmWrapper(headnode="h", account="a")
        assert wrapper.get_cpus_per_node_on_queue("batch") is None

    def test_ping_host(self, mocker, slurm_wrapper):
        mock_run = mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
        )
        slurm_wrapper.ping_host("node01")
        mock_run.assert_called_once_with("ping -w 1 node01", None, None)


# ---------------------------------------------------------------------------
# SCHEDULER_MAP
# ---------------------------------------------------------------------------


class TestSchedulerMap:
    def test_slurm_in_map(self):
        assert "SLURM" in SCHEDULER_MAP
        assert SCHEDULER_MAP["SLURM"] is _SlurmWrapper


# ---------------------------------------------------------------------------
# SchedulerFuture
# ---------------------------------------------------------------------------


class TestSchedulerFuture:
    def _make_future(self, state="RUNNING", future_done=True, future_running=False):
        inner_future = mock.MagicMock(spec=Future)
        inner_future.done.return_value = future_done
        inner_future.running.return_value = future_running
        scheduler = mock.MagicMock(spec=_SlurmWrapper)
        scheduler.get_state.return_value = state
        scheduler.running_states = _SlurmWrapper.running_states
        scheduler.cancelled_states = _SlurmWrapper.cancelled_states
        scheduler.done_states = _SlurmWrapper.done_states
        sf = SchedulerFuture(
            inner_future,
            job_id=10,
            scheduler_instance=scheduler,
            output_file="job.out",
            error_file="job.err",
        )
        return sf, inner_future, scheduler

    def test_running_true(self):
        sf, _, _ = self._make_future(state="RUNNING", future_done=True)
        assert sf.running() is True

    def test_running_false_wrong_state(self):
        sf, _, _ = self._make_future(state="COMPLETED", future_done=True)
        assert sf.running() is False

    def test_running_false_future_not_done(self):
        sf, _, _ = self._make_future(state="RUNNING", future_done=False)
        assert sf.running() is False

    def test_pending(self):
        sf, _, _ = self._make_future(future_running=True)
        assert sf.pending() is True

    def test_not_pending(self):
        sf, _, _ = self._make_future(future_running=False)
        assert sf.pending() is False

    def test_done_completed(self):
        sf, _, _ = self._make_future(state="COMPLETED")
        assert sf.done() is True

    def test_done_cancelled(self):
        sf, _, _ = self._make_future(state="CANCELLED")
        assert sf.done() is True

    def test_done_empty_string(self):
        sf, _, _ = self._make_future(state="")
        assert sf.done() is True

    def test_not_done(self):
        sf, _, _ = self._make_future(state="RUNNING")
        assert sf.done() is False

    def test_result_delegates_to_future(self):
        sf, inner, _ = self._make_future()
        inner.result.return_value = "session_obj"
        assert sf.result(timeout=30) == "session_obj"
        inner.result.assert_called_once_with(30)

    def test_exception_delegates_to_future(self):
        sf, inner, _ = self._make_future()
        inner.exception.return_value = RuntimeError("fail")
        assert isinstance(sf.exception(timeout=10), RuntimeError)
        inner.exception.assert_called_once_with(10)

    def test_add_done_callback(self):
        sf, inner, _ = self._make_future()
        cb = mock.MagicMock()
        sf.add_done_callback(cb)
        inner.add_done_callback.assert_called_once_with(cb)

    def test_cancel_when_already_done(self):
        sf, _, scheduler = self._make_future(state="COMPLETED")
        assert sf.cancel() is False
        scheduler.cancel.assert_not_called()

    def test_cancel_success(self, mocker):
        sf, _, scheduler = self._make_future(state="RUNNING")
        # After cancel is called, state transitions to CANCELLED
        scheduler.get_state.side_effect = ["RUNNING", "CANCELLED"]
        mocker.patch("ansys.pyensight.core.schedulerlauncher.time.sleep")
        assert sf.cancel(timeout=5) is True
        scheduler.cancel.assert_called_once_with(10)

    def test_cancel_timeout(self, mocker):
        sf, _, scheduler = self._make_future(state="RUNNING")
        scheduler.get_state.return_value = "RUNNING"
        mocker.patch("ansys.pyensight.core.schedulerlauncher.time.sleep")
        assert sf.cancel(timeout=3) is False

    def test_context_manager(self, mocker):
        sf, _, scheduler = self._make_future(state="COMPLETED")
        with sf:
            pass
        # __exit__ calls cancel, but since done() is True, cancel returns False

    def test_context_manager_cancels_on_exit(self, mocker):
        sf, _, scheduler = self._make_future(state="RUNNING")
        scheduler.get_state.side_effect = ["RUNNING", "CANCELLED"]
        mocker.patch("ansys.pyensight.core.schedulerlauncher.time.sleep")
        with sf:
            pass
        scheduler.cancel.assert_called_once()

    def test_get_output(self):
        sf, _, scheduler = self._make_future()
        scheduler.get_job_output.return_value = "job output content"
        assert sf.get_output() == "job output content"
        scheduler.get_job_output.assert_called_once_with("job.out")

    def test_get_error(self):
        sf, _, scheduler = self._make_future()
        scheduler.get_job_output.return_value = "job error content"
        assert sf.get_error() == "job error content"
        scheduler.get_job_output.assert_called_once_with("job.err")

    def test_get_output_returns_none(self):
        sf, _, scheduler = self._make_future()
        scheduler.get_job_output.return_value = None
        assert sf.get_output() is None

    def test_get_error_returns_none(self):
        sf, _, scheduler = self._make_future()
        scheduler.get_job_output.return_value = None
        assert sf.get_error() is None


# ---------------------------------------------------------------------------
# SchedulerLauncher
# ---------------------------------------------------------------------------


class TestSchedulerLauncher:
    def test_init_default(self, mocker):
        launcher = _make_scheduler_launcher(mocker)
        assert launcher._client_on_pyensight_host is False
        assert launcher._submission_host == "127.0.0.1"
        assert launcher._working_dir == "."
        assert launcher._tasks_per_node == 0
        assert launcher._queue is None

    def test_init_non_slurm_raises(self, mocker):
        mocker.patch.object(LocalLauncher, "get_cei_install_directory", return_value="/path")
        with pytest.raises(RuntimeError, match="Only slurm"):
            SchedulerLauncher(
                ansys_installation="/remote/install",
                scheduler="PBS",
            )

    def test_init_no_install_raises(self, mocker):
        mocker.patch.object(LocalLauncher, "get_cei_install_directory", return_value="/path")
        with pytest.raises(RuntimeError, match="At least ansys installation"):
            SchedulerLauncher(ansys_installation=None)

    def test_init_remote_host_warns_ssh(self, mocker):
        with pytest.warns(UserWarning, match="SSH will be used"):
            _make_scheduler_launcher(
                mocker,
                submission_host="remote.cluster",
                account="testuser",
            )

    def test_init_remote_host_no_account_warns(self, mocker):
        mocker.patch.object(os, "getlogin", return_value="defaultuser")
        with pytest.warns(UserWarning):
            launcher = _make_scheduler_launcher(
                mocker,
                submission_host="remote.cluster",
                account=None,
            )
        assert launcher._account == "defaultuser"

    def test_init_slurm_not_available_raises(self, mocker):
        mocker.patch.object(LocalLauncher, "get_cei_install_directory", return_value="/path")
        mocker.patch.object(SchedulerLauncher, "_validate_server_ansys_installation")
        mocker.patch.object(SchedulerLauncher, "_check_slurm_available", return_value=False)
        with pytest.raises(RuntimeError, match="Slurm not available"):
            SchedulerLauncher(
                ansys_installation="/remote/install",
                submission_host="127.0.0.1",
            )

    def test_init_client_on_pyensight_host(self, mocker):
        def _mock_set_local_ports(self_):
            self_._ports = [10000, 10001, 10002, 10003, 10004]

        mocker.patch.object(LocalLauncher, "_set_local_ports", _mock_set_local_ports)
        launcher = _make_scheduler_launcher(
            mocker,
            client_on_pyensight_host=True,
            client_ansys_installation="/client/install",
        )
        assert launcher._client_on_pyensight_host is True

    def test_init_python_loc_ignored_with_client_on_host(self, mocker):
        def _mock_set_local_ports(self_):
            self_._ports = [10000, 10001, 10002, 10003, 10004]

        mocker.patch.object(LocalLauncher, "_set_local_ports", _mock_set_local_ports)
        with pytest.warns(UserWarning, match="python_loc is ignored"):
            _make_scheduler_launcher(
                mocker,
                client_on_pyensight_host=True,
                python_location="/some/python",
                client_ansys_installation="/client/install",
            )

    def test_queue_property(self, mocker):
        launcher = _make_scheduler_launcher(mocker, queue="batch")
        assert launcher.queue == "batch"
        launcher.queue = "debug"
        assert launcher.queue == "debug"

    def test_get_cei_install_directory_override(self):
        assert SchedulerLauncher.get_cei_install_directory("/some/path") == "/some/path"

    def test_get_available_queues(self, mocker):
        launcher = _make_scheduler_launcher(mocker)
        mocker.patch.object(launcher._scheduler_instance, "list_queues", return_value=["q1", "q2"])
        assert launcher.get_available_queues() == ["q1", "q2"]

    def test_get_cpus_per_node_on_queue(self, mocker):
        launcher = _make_scheduler_launcher(mocker)
        mocker.patch.object(
            launcher._scheduler_instance,
            "get_cpus_per_node_on_queue",
            return_value=64,
        )
        assert launcher.get_cpus_per_node_on_queue("batch") == 64

    def test_set_tasks_per_node_zero(self, mocker):
        launcher = _make_scheduler_launcher(mocker, tasks_per_node=0)
        assert launcher._set_tasks_per_node() == ""

    def test_set_tasks_per_node_nonzero(self, mocker):
        launcher = _make_scheduler_launcher(mocker, tasks_per_node=4)
        result = launcher._set_tasks_per_node()
        assert "#SBATCH --ntasks-per-node=4" in result

    def test_build_timestamp(self):
        ts = SchedulerLauncher._build_timestamp()
        assert isinstance(ts, str)
        assert len(ts) > 0
        # Should only contain digits
        assert ts.isdigit()

    def test_check_ips_success(self, mocker):
        launcher = _make_scheduler_launcher(mocker)
        mocker.patch.object(launcher._scheduler_instance, "ping_host")
        result = launcher._check_ips(["10.0.0.1", "10.0.0.2"])
        assert result == "10.0.0.1"

    def test_check_ips_first_fails(self, mocker):
        launcher = _make_scheduler_launcher(mocker)
        mocker.patch.object(
            launcher._scheduler_instance,
            "ping_host",
            side_effect=[Exception("unreachable"), None],
        )
        result = launcher._check_ips(["10.0.0.1", "10.0.0.2"])
        assert result == "10.0.0.2"

    def test_check_ips_all_fail(self, mocker):
        launcher = _make_scheduler_launcher(mocker)
        mocker.patch.object(
            launcher._scheduler_instance,
            "ping_host",
            side_effect=Exception("unreachable"),
        )
        result = launcher._check_ips(["10.0.0.1"])
        assert result is None

    def test_parse_job_output_for_session(self):
        output = (
            "Some header\n"
            "Session(host='node01', secret_key=abc-123, html_port=8080, "
            "grpc_port=50051, ws_port=1234, sos=True, rest_api=False, extra=1)\n"
            "Client Machine IP: 192.168.1.100\n"
            "Remote Session Directory: /tmp/session_dir"
        )
        result = SchedulerLauncher._parse_job_output_for_session(output)
        secret_key, html_port, grpc_port, ws_port, sos, rest_api, ip, session_dir = result
        assert secret_key == "abc-123"
        assert html_port == 8080
        assert grpc_port == 50051
        assert ws_port == 1234
        assert sos == "True"
        assert rest_api == "False"
        assert ip == "192.168.1.100"
        assert session_dir == "/tmp/session_dir"

    def test_create_python_and_slurm_file_no_client_on_host(self, mocker, tmp_path):
        mocker.patch("os.getcwd", return_value=str(tmp_path))
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            launcher = _make_scheduler_launcher(
                mocker,
                queue="batch",
                use_sos=2,
            )
            launcher._python_loc = "/usr/bin/python"
            timestamp = "20260428100"
            slurm_file, python_file = launcher._create_python_and_slurm_file(timestamp)
            assert slurm_file.endswith(".slurm")
            assert python_file.endswith(".py")
            assert os.path.exists(slurm_file)
            assert os.path.exists(python_file)
            with open(slurm_file) as f:
                content = f.read()
            assert "batch" in content
            assert "/usr/bin/python" in content
        finally:
            os.chdir(original_cwd)

    def test_create_python_and_slurm_file_client_on_host(self, mocker, tmp_path):
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:

            def _mock_set_local_ports(self_):
                self_._ports = [10000, 10001, 10002, 10003, 10004]

            mocker.patch.object(LocalLauncher, "_set_local_ports", _mock_set_local_ports)
            launcher = _make_scheduler_launcher(
                mocker,
                queue="batch",
                client_on_pyensight_host=True,
                client_ansys_installation="/client/install",
            )
            launcher._client_machine = "myhost"
            launcher._internal_launcher = mock.MagicMock()
            launcher._internal_launcher._ports = [1, 2, 3, 4, 5000]
            timestamp = "20260428101"
            slurm_file, python_file = launcher._create_python_and_slurm_file(timestamp)
            assert slurm_file.endswith(".slurm")
            assert python_file is None
            assert os.path.exists(slurm_file)
        finally:
            os.chdir(original_cwd)

    def test_start_local_submission(self, mocker, tmp_path):
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            launcher = _make_scheduler_launcher(
                mocker,
                queue="batch",
                use_sos=1,
            )
            launcher._python_loc = "/usr/bin/python"
            mocker.patch.object(
                launcher._scheduler_instance,
                "submit_job",
                return_value=42,
            )
            mocker.patch.object(launcher, "_launch", return_value=mock.MagicMock())
            future = launcher.start()
            assert isinstance(future, SchedulerFuture)
            assert future._job_id == 42
        finally:
            os.chdir(original_cwd)

    def test_start_job_submission_failure(self, mocker, tmp_path):
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            launcher = _make_scheduler_launcher(
                mocker,
                queue="batch",
                use_sos=1,
            )
            launcher._python_loc = "/usr/bin/python"
            mocker.patch.object(
                launcher._scheduler_instance,
                "submit_job",
                return_value=None,
            )
            with pytest.raises(RuntimeError, match="Error while submitting job"):
                launcher.start()
        finally:
            os.chdir(original_cwd)

    def test_start_remote_copy_slurm_failure(self, mocker, tmp_path):
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            mocker.patch.object(os, "getlogin", return_value="user")
            launcher = _make_scheduler_launcher(
                mocker,
                queue="batch",
                use_sos=1,
                submission_host="remote.cluster",
                account="user",
            )
            launcher._python_loc = "/usr/bin/python"
            mocker.patch(
                "ansys.pyensight.core.schedulerlauncher._copy_file",
                return_value=False,
            )
            with pytest.raises(RuntimeError, match="Could not send slurm script"):
                launcher.start()
        finally:
            os.chdir(original_cwd)

    def test_start_remote_copy_python_failure(self, mocker, tmp_path):
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            mocker.patch.object(os, "getlogin", return_value="user")
            launcher = _make_scheduler_launcher(
                mocker,
                queue="batch",
                use_sos=1,
                submission_host="remote.cluster",
                account="user",
            )
            launcher._python_loc = "/usr/bin/python"
            # slurm copy succeeds, python copy fails
            mocker.patch(
                "ansys.pyensight.core.schedulerlauncher._copy_file",
                side_effect=[True, False],
            )
            with pytest.raises(RuntimeError, match="Could not send python script"):
                launcher.start()
        finally:
            os.chdir(original_cwd)

    def test_stop_cancels_future(self, mocker):
        launcher = _make_scheduler_launcher(mocker)
        mock_future = mock.MagicMock(spec=SchedulerFuture)
        launcher._future = mock_future
        launcher.stop()
        mock_future.cancel.assert_called_once()

    def test_validate_server_ansys_installation_direct_cei(self, mocker):
        mocker.patch.object(LocalLauncher, "get_cei_install_directory", return_value="/path")
        mocker.patch.object(SchedulerLauncher, "_check_slurm_available", return_value=True)
        # First _run_command succeeds (bin/ensight found)
        mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
            side_effect=["/remote/install/bin/ensight", None],
        )
        mock_scheduler = mock.MagicMock()
        mock_scheduler.is_available.return_value = True
        mocker.patch.dict(SCHEDULER_MAP, {"SLURM": lambda *a, **kw: mock_scheduler})
        launcher = SchedulerLauncher(ansys_installation="/remote/install")
        assert launcher._server_ansys_installation == "/remote/install"

    def test_validate_server_ansys_installation_with_cei_subfolder(self, mocker):
        mocker.patch.object(LocalLauncher, "get_cei_install_directory", return_value="/path")
        mocker.patch.object(SchedulerLauncher, "_check_slurm_available", return_value=True)
        # First call (bin/ensight) fails, second (CEI/bin/ensight) succeeds
        mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
            side_effect=[None, "/remote/install/CEI/bin/ensight"],
        )
        mock_scheduler = mock.MagicMock()
        mock_scheduler.is_available.return_value = True
        mocker.patch.dict(SCHEDULER_MAP, {"SLURM": lambda *a, **kw: mock_scheduler})
        launcher = SchedulerLauncher(ansys_installation="/remote/install")
        assert launcher._server_ansys_installation == "/remote/install/CEI"

    def test_validate_server_ansys_installation_fails(self, mocker):
        mocker.patch.object(LocalLauncher, "get_cei_install_directory", return_value="/path")
        mocker.patch.object(SchedulerLauncher, "_check_slurm_available", return_value=True)
        mocker.patch(
            "ansys.pyensight.core.schedulerlauncher._run_command",
            return_value=None,
        )
        mock_scheduler = mock.MagicMock()
        mock_scheduler.is_available.return_value = True
        mocker.patch.dict(SCHEDULER_MAP, {"SLURM": lambda *a, **kw: mock_scheduler})
        with pytest.raises(RuntimeError, match="Cannot find Ansys installation"):
            SchedulerLauncher(ansys_installation="/bad/path")

    def test_start_internal_launcher(self, mocker):
        def _mock_set_local_ports(self_):
            self_._ports = [10000, 10001, 10002, 10003, 10004]

        mocker.patch.object(LocalLauncher, "_set_local_ports", _mock_set_local_ports)
        launcher = _make_scheduler_launcher(
            mocker,
            client_on_pyensight_host=True,
            client_ansys_installation="/client/install",
        )
        mocker.patch.object(LocalLauncher, "__init__", return_value=None)
        launcher._start_internal_launcher()
        assert launcher._internal_launcher is not None

    def test_ssh_tunneling_options(self, mocker):
        def _mock_set_local_ports(self_):
            self_._ports = [10000, 10001, 10002, 10003, 10004]

        mocker.patch.object(LocalLauncher, "_set_local_ports", _mock_set_local_ports)
        launcher = _make_scheduler_launcher(
            mocker,
            client_on_pyensight_host=True,
            client_ansys_installation="/client/install",
            ssh_tunneling_server_to_client=True,
        )
        assert launcher._tunneling == "R"

        launcher2 = _make_scheduler_launcher(
            mocker,
            client_on_pyensight_host=True,
            client_ansys_installation="/client/install",
            ssh_tunneling_client_to_server=True,
        )
        assert launcher2._tunneling == "L"

    def test_default_python_loc_when_no_client_on_host(self, mocker):
        launcher = _make_scheduler_launcher(mocker)
        assert launcher._python_loc == "/remote/ansys/install/bin/cpython"

    def test_init_use_sos_sets_tasks(self, mocker):
        launcher = _make_scheduler_launcher(mocker, use_sos=4)
        assert launcher._use_sos == 4
