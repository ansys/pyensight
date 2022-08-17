import argparse
import glob
import os
import shutil
import subprocess
import sys
import textwrap

# Python script alternative to 'make' targets.  To build everything:
# python pybuild.py clean
# python pybuild.py all


def docs():
    print("-" * 10, "Build sphinx docs")
    pydir = os.path.dirname(sys.executable)
    sphinx = os.path.join(pydir, "scripts", "sphinx-build")
    cmd = [sphinx, "-M", "html", "doc/source", "doc/build"]
    subprocess.run(cmd)


def generate():
    print("-" * 10, "Running generate.py")
    cmd = [sys.executable, "codegen/generate.py"]
    subprocess.run(cmd)


def wheel():
    print("-" * 10, "Building wheel")
    cmd = [sys.executable, "-m", "build", "--wheel"]
    subprocess.run(cmd)


def test():
    print("-" * 10, "Run tests")
    pydir = os.path.dirname(sys.executable)
    pytest = os.path.join(pydir, "scripts", "pytest")
    cmd = [pytest, "-rvx", "--setup-show", "--cov=ansys.pyensight",
           "--cov-report", "html:coverage-html", "--cov-report", "term",
           "--cov-config=.coveragerc"]
    subprocess.run(cmd)


def codespell():
    pydir = os.path.dirname(sys.executable)
    codespellexe = os.path.join(pydir, "scripts", "codespell")
    print("-" * 10, "Running codespell")
    cmd = [
        codespellexe,
        "--count",
        "src",
    ]
    ret = subprocess.run(cmd, capture_output=True)
    if ret.returncode < 0:
        raise RuntimeError(f"Error running {codespellexe}")
    print(ret.stdout.decode().strip())
    num = int(ret.stderr.decode().split()[-1])
    if num > 0:
        print(f"Warning: {num} potential spelling error(s) detected")


def flake8():
    pydir = os.path.dirname(sys.executable)
    flake8exe = os.path.join(pydir, "scripts", "flake8")
    print("-" * 10, "Running flake8")
    cmd = [
        flake8exe,
    ]
    subprocess.run(cmd)


def black():
    pydir = os.path.dirname(sys.executable)
    blackexe = os.path.join(pydir, "scripts", "black")
    print("-" * 10, "Running black")
    cmd = [
        blackexe,
        "--line-length", "100",
        "--target-version", "py37",
        "src/ansys", "codegen", "doc", "tests",
    ]
    subprocess.run(cmd)


def isort():
    pydir = os.path.dirname(sys.executable)
    isortexe = os.path.join(pydir, "scripts", "isort")
    print("-" * 10, "Running isort")
    cmd = [
        isortexe,
        "--profile", "black",
        "--skip-gitignore",
        "--force-sort-within-sections",
        "--line-length", "100",
        "--section-default", "THIRDPARTY",
        "--filter-files",
        "--project", "ansys",
        "ansys", "codegen", "doc", "tests"
    ]
    subprocess.run(cmd)


def clean():
    paths = [
        "dist",
        "build",
        os.path.join("src", "ansys", "api"),
        os.path.join("doc", "build"),
        os.path.join("doc", "source", "_autosummary"),
    ]
    for path in paths:
        shutil.rmtree(path, ignore_errors=True)
    files = [
        os.path.join("codegen", "ensight.proto"),
        os.path.join("codegen", "ensight_api.xml"),
        os.path.join("src", "ansys", "pyensight", "ensight_api.py"),
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
'docs' : Generate documentation.
'all' : Run codegen, build the wheel and generate documentation."""
    )

    parser = argparse.ArgumentParser(
        description="Python only build script",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "operation",
        metavar="operation",
        choices=["clean", "precommit", "codegen", "test", "build", "docs", "all"],
        help=operation_help,
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
        test()
    elif args.operation == "build":
        generate()
        wheel()
    elif args.operation == "docs":
        generate()
        docs()
    elif args.operation == "all":
        generate()
        wheel()
        docs()
    elif args.operations == "":
        print()
    print("Complete.")
