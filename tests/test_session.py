"""Unit tests for session.py"""
import pytest

from ansys.pyensight import LocalLauncher


def test_session_without_installation() -> None:
    """todo: just a stub. Remove and write actual tests like below"""
    with pytest.raises(RuntimeError) as exec_info:
        session = LocalLauncher().start()
        session.close()
    assert "Unable to detect an EnSight installation" in str(exec_info)


"""
def test_close(local_launcher_session) -> None:
    local_launcher_session.close()
    assert local_launcher_session.launcher is None
"""
