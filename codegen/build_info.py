"""Generate the _build_info.py file

Usage
-----

`python build_info.py`
"""
import datetime
import os
import subprocess
import sys


def generate() -> None:
    """Create the ansys/pyensight/build_info.py file"""
    root = os.path.dirname(__file__)
    os.chdir(root)

    source = os.path.dirname(root)
    source_path = os.path.join(source, "src")
    # prepend this path!!!
    sys.path.insert(0, source_path)
    from ansys.ensight.core._version import VERSION

    now = datetime.datetime.now()

    cmd = ["git", "rev-parse", "--short", "HEAD"]
    ret = subprocess.run(cmd, capture_output=True)
    git_hash = ret.stdout.decode().strip()

    cmd = ["git", "branch", "--show-current"]
    ret = subprocess.run(cmd, capture_output=True)
    git_branch = ret.stdout.decode().strip()

    target = "../src/ansys/pyensight/build_info.py"
    print(f"Generating build_info.py file: {now.isoformat()}, {git_branch}, {git_hash}, {VERSION}")
    with open(target, "w") as fp:
        fp.write("# Build information\n")
        fp.write(f'BUILD_DATE="{now.isoformat()}"\n')
        fp.write(f'BUILD_HASH="{git_hash}"\n')
        fp.write(f'BUILD_BRANCH="{git_branch}"\n')
        fp.write(f'BUILD_DESCRIPTION="{VERSION}"\n')


if __name__ == "__main__":
    generate()
