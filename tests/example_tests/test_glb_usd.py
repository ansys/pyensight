import os
import shutil
import subprocess
import sys
import tempfile
import warnings

import requests


def test_glb_usd():
    # Get the example files
    if sys.version_info.minor >= 13:
        warnings.warn("Test not supported for Python >= 3.13")
        return
    base_uri = "https://s3.amazonaws.com/www3.ensight.com/PyEnSight/ExampleData"
    filenames = ["fluent_elbow.glb", "rwing_bsl_1.glb", "rwing_bsl_2.glb", "ens_car_exts.glb"]
    with tempfile.TemporaryDirectory() as tmpdirname:
        for filename in filenames:
            outpath = os.path.join(tmpdirname, filename)
            url = f"{base_uri}/{filename}"
            with requests.get(url, stream=True) as r:
                with open(outpath, "wb") as f:
                    shutil.copyfileobj(r.raw, f)
            # convert these into USD format
            with tempfile.TemporaryDirectory() as usd_dir:
                # Build the CLI command
                cmd = [sys.executable]
                cmd.extend(["-m", "ansys.pyensight.core.utils.omniverse_cli"])
                cmd.extend(["--oneshot", "1"])
                cmd.extend(["--include_camera", "0"])
                cmd.extend(["--monitor_directory", outpath])
                cmd.append(usd_dir)
                env_vars = os.environ.copy()
                subprocess.run(cmd, close_fds=True, env=env_vars)
                assert os.path.isfile(os.path.join(usd_dir, "dsg_scene.usd"))
                assert os.path.isdir(os.path.join(usd_dir, "Parts"))


def test_ensight_glb_usd():
    if sys.version_info.minor >= 13:
        warnings.warn("Test not supported for Python >= 3.13")
        return
    # Get the example files: both generated by Ensight, _10.glb is time varying.
    base_uri = "https://s3.amazonaws.com/www3.ensight.com/PyEnSight/ExampleData"
    filenames = ["obstacle.glb", "obstacle_10.glb"]
    with tempfile.TemporaryDirectory() as tmpdirname:
        for filename in filenames:
            outpath = os.path.join(tmpdirname, filename)
            url = f"{base_uri}/{filename}"
            with requests.get(url, stream=True) as r:
                with open(outpath, "wb") as f:
                    shutil.copyfileobj(r.raw, f)
            # convert these into USD format
            with tempfile.TemporaryDirectory() as usd_dir:
                # Build the CLI command
                cmd = [sys.executable]
                cmd.extend(["-m", "ansys.pyensight.core.utils.omniverse_cli"])
                cmd.extend(["--oneshot", "1"])
                cmd.extend(["--include_camera", "0"])
                cmd.extend(["--monitor_directory", outpath])
                cmd.append(usd_dir)
                env_vars = os.environ.copy()
                subprocess.run(cmd, close_fds=True, env=env_vars)
                assert os.path.isfile(os.path.join(usd_dir, "dsg_scene.usd"))
                assert os.path.isdir(os.path.join(usd_dir, "Parts"))
