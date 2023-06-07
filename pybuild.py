import argparse
import datetime
import glob
import os
import platform
import shutil
import subprocess
import sys
import textwrap

import junitparser

# Python script alternative to 'make' targets.  To build everything:
# python pybuild.py all


def find_exe(name: str) -> str:
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


def docs(target: str = "html", full: bool = True, skip_tests: bool = False) -> None:
    # We run the tests first so we have access to their results when
    # building the documentation
    if not skip_tests:
        test()
    # Build the actual docs
    print("-" * 10, "Build sphinx docs")
    # run sphinx
    sphinx = find_exe("sphinx-build")
    cmd = [sphinx, "-M", target, "doc/source", "doc/build"]
    env = os.environ.copy()
    if not full:
        env["FASTDOCS"] = "1"
    subprocess.run(cmd, env=env)
    if not skip_tests:
        # build the coverage badge, overriding the default badge
        cov_badge = find_exe("coverage-badge")
        cmd = [cov_badge, "-f", "-o", "doc/build/html/_images/coverage.svg"]
        subprocess.run(cmd)
    # make the yaml file available to enable the swagger edtiro
    src = os.path.join("doc", "source", "rest_api", "ensight_rest_v1.yaml")
    dst = os.path.join("doc", "build", "html", "_static", "ensight_rest_v1.yaml")
    shutil.copyfile(src, dst)


def generate() -> None:
    print("-" * 10, "Running generate.py")
    cmd = [sys.executable, "codegen/generate.py"]
    subprocess.run(cmd)


def wheel() -> None:
    print("-" * 10, "Building wheel")
    # Clean up the dist director
    for name in glob.glob("dist/*.whl"):
        os.unlink(name)
    # Build the wheel
    cmd = [sys.executable, "-m", "build", "--wheel"]
    subprocess.run(cmd)
    # rename: ansys_ensight-0.2.dev0-py3-none-any.whl to
    # ansys_ensight-0.2.dev0-{date_tag}-py3-none-any.whl
    # monotonically increasing number with minute level
    # resolution so a nightly can be run once a minute
    date_tag = datetime.datetime.now().strftime("%Y%m%d%H%M")
    for name in glob.glob("dist/*.whl"):
        chunks = name.split("-")
        if len(chunks) == 5:
            chunks.insert(2, date_tag)
            new_name = "-".join(chunks)
            os.rename(name, new_name)
            print(f"Rename wheel to: '{new_name}'")


def test(local: bool = False) -> None:
    print("-" * 10, "Run tests")
    junit_path = os.path.join(os.getcwd(), "pyensight_test_results.xml")
    try:
        os.unlink(junit_path)
    except IOError:
        pass
    pytest = find_exe("pytest")
    cmd = [
        pytest,
        "-rvx",
        "--setup-show",
        "--cov=ansys.pyensight",
        "--cov-report",
        "html:coverage-html",
        "--cov-report",
        "term",
        "--cov-config=.coveragerc",
        "--junit-xml={}".format(junit_path),
    ]
    if local:
        cmd.append("--use-local-launcher")
    result = subprocess.run(cmd)
    # Attempt check of the return code
    if result.returncode == 0:
        print("pyEnSight tests run successfully.")
    else:
        print("pyEnSight tests failed.")
        sys.exit(1)
    # Check also junit file
    xml = junitparser.JUnitXml.fromfile(junit_path)
    if xml.failures > 0:
        print(f"There were {xml.failures} PyEnSight failures.")
        sys.exit(1)
    if xml.errors > 0:
        print(f"There were {xml.errors} errors in the PyEnSight tests.")
        sys.exit(1)


def codespell() -> None:
    codespellexe = find_exe("codespell")
    print("-" * 10, "Running codespell")
    codespell_skip = "*.pyc,*.xml,*.txt,*.gif,*.png,*.jpg,*.js,*.html,*.doctree,*.ttf,*.woff,"
    codespell_skip += "*.woff2,*.eot,*.mp4,*.inv,*.pickle,*.ipynb,flycheck*,./.git/*,"
    codespell_skip += "./.hypothesis/*,*.yml,./docs/build/*,./docs/images/*,"
    codespell_skip += "./dist/*,*~,.hypothesis*,./docs/source/examples/*,*cover,*.dat,*.mac,"
    codespell_skip += "PKG-INFO,*.mypy_cache/*,*.xml,*.aedt,*.svg"

    cmd = [
        codespellexe,
        "--count",
        "--ignore-words",
        "ignore_words.txt",
        "--skip",
        codespell_skip,
        "src",
        "doc",
        "codegen",
    ]
    ret = subprocess.run(cmd, capture_output=True)
    if ret.returncode < 0:
        raise RuntimeError(f"Error running {codespellexe}")
    print(ret.stdout.decode().strip())
    num = int(ret.stderr.decode().split()[-1])
    if num > 0:
        print(f"Warning: {num} potential spelling error(s) detected")


def flake8() -> None:
    flake8exe = find_exe("flake8")
    print("-" * 10, "Running flake8")
    cmd = [
        flake8exe,
    ]
    subprocess.run(cmd)


def black() -> None:
    blackexe = find_exe("black")
    print("-" * 10, "Running black")
    cmd = [
        blackexe,
        "--line-length",
        "100",
        "--target-version",
        "py37",
        "src/ansys",
        "codegen",
        "doc",
        "tests",
        "pybuild.py",
    ]
    subprocess.run(cmd)


def isort() -> None:
    isortexe = find_exe("isort")
    print("-" * 10, "Running isort")
    cmd = [
        isortexe,
        "--profile",
        "black",
        "--skip-gitignore",
        "--force-sort-within-sections",
        "--line-length",
        "100",
        "--section-default",
        "THIRDPARTY",
        "--filter-files",
        "--project",
        "ansys",
        "src",
        "codegen",
        "doc",
        "tests",
    ]
    subprocess.run(cmd)

def mypy() -> None:
    mypyexe = find_exe("mypy")
    print("-" * 10, "Running mypy")
    cmd = [
    mypyexe,
        "--config-file", os.path.join(os.path.dirname(__file__), "mypy.ini"),
        os.path.join(os.path.dirname(__file__), "src", "ansys", "pyensight"),
    ]
    subprocess.run(cmd)


def clean() -> None:
    paths = [
        "dist",
        "build",
        os.path.join("src", "ansys", "api"),
        os.path.join("doc", "build"),
        os.path.join("doc", "source", "_autosummary"),
        os.path.join("doc", "source", "_examples"),
    ]
    for path in paths:
        shutil.rmtree(path, ignore_errors=True)
    files = [
        os.path.join("codegen", "ensight.proto"),
        os.path.join("codegen", "ensight_api.xml"),
        os.path.join("src", "ansys", "pyensight", "ensight_api.py"),
        os.path.join("src", "ansys", "pyensight", "build_info.py"),
    ]
    ensobj_files = os.path.join("src", "ansys", "pyensight", "ens_*.py")
    files.extend(glob.glob(ensobj_files))
    for file in files:
        try:
            os.remove(file)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    operation_help = textwrap.dedent(
        """\
'clean' : Clean build directories.
'precommit' : Run linting tools.
'codegen' : Execute the codegen operations.
'test' : Execute the pytests.
'build' : Build the wheel.
'fastdocs' : Generate partial documentation.
'docs' : Generate documentation.
'mypy : Run mypy check.
'all' : Run clean codegen, build and complete documentation."""
)

    parser = argparse.ArgumentParser(
        description="Python only build script",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "operation",
        metavar="operation",
        choices=[
            "clean",
            "precommit",
            "codegen",
            "test",
            "build",
            "fastdocs",
            "docs",
            "mypy",
            "all",
        ],
        help=operation_help,
    )
    parser.add_argument(
        "--skip_tests",
        default=False,
        action="store_true",
        help="Set to skip running tests when building documentation",
    )
    parser.add_argument(
        "--locallauncher",
        default=False,
        action="store_true",
        help="Set to use LocalLauncher instead of DockerLauncher for tests",
    )

    # parse the command line
    args = parser.parse_args()

    if args.operation == "clean":
        clean()
    elif args.operation == "precommit":
        black()
        isort()
        flake8()
        codespell()
    elif args.operation == "codegen":
        generate()
    elif args.operation == "test":
        test(local=args.locallauncher)
    elif args.operation == "build":
        generate()
        wheel()
    elif args.operation == "docs":
        generate()
        docs(target="html", skip_tests=args.skip_tests)
    elif args.operation == "fastdocs":
        generate()
        docs(target="html", full=False, skip_tests=args.skip_tests)
    elif args.operation == "all":
        clean()
        generate()
        wheel()
        docs()
    elif args.operation == "":
        print()
    elif args.operation == "mypy":
        mypy()
    print("Complete.")
