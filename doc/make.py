import argparse
import glob
import os
import platform
import shutil
import subprocess
import sys
import textwrap


def find_exe(name: str) -> str:
    """Find an actual executable target
    Given the name of an executable, find the actual path to use.

    Parameters
    ----------
    name : str
        The undecorated name (e.g. pre-commit, sphinx-build, etc) to search for.

    """
    # exe files under Windows
    if platform.system().lower().startswith("win"):
        name += ".exe"
    pydir = os.path.dirname(sys.executable)
    pathname = os.path.join(pydir, "Scripts", name)
    if os.path.exists(pathname):
        return pathname
    pathname = os.path.join(pydir, "bin", name)
    if os.path.exists(pathname):
        return pathname
    pathname = os.path.join(pydir, name)
    if os.path.exists(pathname):
        return pathname
    raise RuntimeError(f"Unable to find script {name}.  Is it installed?")


"""
# install dependencies
python.exe -m pip install .[dev]
python.exe -m pip install .[doc]

# build - install
python.exe -m build
python.exe -m pip install .\dist\ansys_pyensight_core-0.1.dev0-py3-none-any.whl

# docs
cd doc
# FASTDOCS=1?
sphinx-build.exe -M html source _build -j auto
"""


def clean() -> None:
    """Clean up the documentation directories"""
    print("-" * 10, "Cleaning up old docs builds")
    paths = [
        "dist",
        os.path.join("doc", "_build"),
        os.path.join("doc", "source", "_autosummary"),
        os.path.join("doc", "source", "_examples"),
    ]
    for path in paths:
        shutil.rmtree(path, ignore_errors=True)


def install():
    """Install the current wheel"""
    print("-" * 10, "Installing wheel")
    wheel_file = glob.glob("dist/*.whl")[0]
    # Uninstall existing wheel
    cmd = [sys.executable, "-m", "pip", "uninstall", "ansys-pyensight-core", "-y"]
    subprocess.run(cmd)
    # Install new wheel
    cmd = [sys.executable, "-m", "pip", "install", wheel_file]
    subprocess.run(cmd)


def wheel():
    """Build the wheel"""
    print("-" * 10, "Building wheel")
    # Clean up the dist directory
    for name in glob.glob("dist/*.whl"):
        os.unlink(name)
    # Build the wheel
    cmd = [sys.executable, "-m", "build", "--wheel"]
    subprocess.run(cmd)


def precommit():
    """Execute the pre-commit action"""
    print("-" * 10, "Pre-commit checks")
    executable = find_exe("pre-commit")
    cmd = [executable, "run", "--all-files"]
    subprocess.run(cmd)


def docs(target: str = "html", skip_api: bool = False):
    """Run sphinx to build the docs

    Parameters
    ----------
    target : str, optional
        What specific build target (e.g. "html").
    skip_api : bool, optional
        Should we skip the (expensive) autosummary targets.

    """
    # Build the actual docs
    print("-" * 10, "Build sphinx docs")
    # chdir to docs
    os.chdir("doc")
    # build it
    executable = find_exe("sphinx-build")
    cmd = [executable, "-M", target, "source", "_build", "-j", "auto"]
    env = os.environ.copy()
    if skip_api:
        env["FASTDOCS"] = "1"
    subprocess.run(cmd, env=env)


if __name__ == "__main__":
    operation_help = textwrap.dedent(
        """\
'clean' : Clean build directories.
'install' : Install the wheel.
'precommit' : Run linting tools.
'build' : Build the wheel.
'docs' : Generate documentation.
"""
    )

    parser = argparse.ArgumentParser(
        description="Build pyensight docs",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "operation",
        metavar="operation",
        choices=[
            "clean",
            "install",
            "precommit",
            "build",
            "docs",
        ],
        help=operation_help,
    )
    parser.add_argument(
        "--fastdocs",
        default=False,
        action="store_true",
        help="Skip generation of API (autosummary) docs",
    )

    # parse the command line
    args = parser.parse_args()

    if args.operation == "clean":
        clean()
    elif args.operation == "precommit":
        precommit()
    elif args.operation == "install":
        install()
    elif args.operation == "build":
        wheel()
    elif args.operation == "docs":
        docs(target="html", skip_api=args.fastdocs)
    elif args.operations == "":
        print()
    print("Complete.")
