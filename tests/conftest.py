"""
Global fixtures go here.
"""

import pytest

from ansys.pyensight import DockerLauncher, LocalLauncher


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    This let's you specify the install path when you run pytest:
    $ pytest tests --install-path "/ansys_inc/v231/CEI/bin/ensight"
    TODO: Default must be set to the one on the CI/CD server.
    """
    parser.addoption(
        "--install-path",
        action="store",
        default="/ansys_inc/v222/",
    )


@pytest.fixture
def local_launcher_session(pytestconfig: pytest.Config) -> "pyensight.Session":
    session = LocalLauncher(ansys_installation=pytestconfig.getoption("install_path")).start()
    yield session
    session.close()


@pytest.fixture
def docker_launcher_session() -> "pyensight.Session":
    launcher = DockerLauncher(data_directory=".", use_dev=True)
    launcher.pull()
    session = launcher.start()
    yield session
    session.close()
