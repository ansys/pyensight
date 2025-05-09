import argparse
from functools import partial
import glob
import json
import logging
import os
import pathlib
import sys
import time
from typing import Any, List, Optional
from urllib.parse import urlparse

import ansys.pyensight.core

original_stderr = sys.stderr
original_stdout = sys.stdout
sys.stderr = open(os.devnull, "w")
sys.stdout = open(os.devnull, "w")
try:
    import ansys.pyensight.core.utils.dsg_server as dsg_server
    import ansys.pyensight.core.utils.omniverse_dsg_server as ov_dsg_server
    import ansys.pyensight.core.utils.omniverse_glb_server as ov_glb_server
except AttributeError as exc:
    if "_ARRAY_API" not in str(exc):
        raise exc
finally:
    sys.stderr = original_stderr
    sys.stdout = original_stdout


def str2bool_type(v: Any) -> bool:
    """
    This function is designed to be a 'type=' filter for an argparse entry returning a boolean.
    It allows for additional, common alternative strings as booleans.  These include 'yes','no',
    'true','false','t','f','y','n','1' and '0'.  If the value does not meet the requirements,
    the function will raise the argparse.ArgumentTypeError exception.
    :param v: The (potential) boolean argument.
    :return: The actual boolean value.
    :raises: argparse.ArgumentTypeError
    """
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


def int_range_type(
    v: Any, min_value: int = 0, max_value: int = 100, allow: Optional[List[int]] = None
) -> int:
    """
    This function is designed to be a 'type=' filter for an argparse entry returning an integer value within
    a specified range.  If the value does not meet the requirements, the function will raise the
    argparse.ArgumentTypeError exception.  This function is normally used with functools.partial to bind
    the minimum and maximum values.  For example:  type=partial(int_range_type, min_value=0, max_value=65535)
    :param v: The (potential) integer argument.
    :param min_value: The minimum legal integer value.
    :param max_value: The maximum legal integer value.
    :param allow：A list of additional, legal values
    :return: The validated integer value.
    :raises: argparse.ArgumentTypeError
    """
    try:
        value = int(v)
    except ValueError:
        raise argparse.ArgumentTypeError("Integer value expected.")
    if allow is None:
        allow = []
    if (value >= min_value) and (value <= max_value):
        return value
    elif value in allow:
        return value
    else:
        msg = f"Integer value is not in the range [{min_value},{max_value}]"
        if allow:
            msg += f" or in the list {allow}"
        raise argparse.ArgumentTypeError(msg + ".")


class OmniverseGeometryServer(object):
    def __init__(
        self,
        security_token: str = "",
        destination: str = "",
        temporal: bool = False,
        vrmode: bool = False,
        time_scale: float = 1.0,
        normalize_geometry: bool = False,
        dsg_uri: str = "",
        monitor_directory: str = "",
        line_width: float = 0.0,
    ) -> None:
        self._dsg_uri = dsg_uri
        self._destination = destination
        self._security_token = security_token
        if not self._security_token:
            self._security_token = os.environ.get("ENSIGHT_SECURITY_TOKEN", "")
        self._temporal = temporal
        self._vrmode = vrmode
        self._time_scale = time_scale
        self._normalize_geometry = normalize_geometry
        self._version = "unknown"
        self._shutdown = False
        self._server_process = None
        self._status_filename: str = ""
        self._monitor_directory: str = monitor_directory
        self._line_width = line_width

    @property
    def monitor_directory(self) -> Optional[str]:
        if self._monitor_directory:
            return self._monitor_directory
        # converts "" -> None
        return None

    @property
    def pyensight_version(self) -> str:
        """The ansys.pyensight.core version"""
        return ansys.pyensight.core.VERSION

    @property
    def dsg_uri(self) -> str:
        """The endpoint of a Dynamic Scene Graph service:  grpc://{hostname}:{port}"""
        return self._dsg_uri

    @dsg_uri.setter
    def dsg_uri(self, uri: str) -> None:
        self._dsg_uri = uri

    @property
    def destination(self) -> str:
        """The endpoint of an Omniverse Nucleus service:  omniverse://{hostname}/{path}"""
        return self._destination

    @destination.setter
    def destination(self, value: str) -> None:
        self._destination = value

    @property
    def security_token(self) -> str:
        """The security token of the DSG service instance."""
        return self._security_token

    @security_token.setter
    def security_token(self, value: str) -> None:
        self._security_token = value

    @property
    def temporal(self) -> bool:
        """If True, the DSG update should include all timesteps."""
        return self._temporal

    @temporal.setter
    def temporal(self, value: bool) -> None:
        self._temporal = bool(value)

    @property
    def vrmode(self) -> bool:
        """If True, the DSG update should not include camera transforms."""
        return self._vrmode

    @vrmode.setter
    def vrmode(self, value: bool) -> None:
        self._vrmode = bool(value)

    @property
    def normalize_geometry(self) -> bool:
        """If True, the DSG geometry should be remapped into normalized space."""
        return self._normalize_geometry

    @normalize_geometry.setter
    def normalize_geometry(self, val: bool) -> None:
        self._normalize_geometry = val

    @property
    def time_scale(self) -> float:
        """Value to multiply DSG time values by before passing to Omniverse"""
        return self._time_scale

    @time_scale.setter
    def time_scale(self, value: float) -> None:
        self._time_scale = value

    @property
    def line_width(self) -> float:
        return self._line_width

    @line_width.setter
    def line_width(self, line_width: float) -> None:
        self._line_width = line_width

    def run_server(self, one_shot: bool = False) -> None:
        """
        Run a DSG to Omniverse server in process.

        Note: this method does not return until the DSG connection is dropped or
        self.stop_server() has been called.

        Parameters
        ----------
        one_shot : bool
            If True, only run the server to transfer a single scene and
            then return.
        """

        # Build the Omniverse connection
        omni_link = ov_dsg_server.OmniverseWrapper(
            destination=self._destination, line_width=self.line_width
        )
        logging.info("Omniverse connection established.")

        # parse the DSG URI
        parsed = urlparse(self.dsg_uri)
        port = parsed.port
        host = parsed.hostname

        # link it to a DSG session
        update_handler = ov_dsg_server.OmniverseUpdateHandler(omni_link)
        dsg_link = dsg_server.DSGSession(
            port=port,
            host=host,
            vrmode=self.vrmode,
            security_code=self.security_token,
            verbose=1,
            normalize_geometry=self.normalize_geometry,
            time_scale=self.time_scale,
            handler=update_handler,
        )

        # Start the DSG link
        logging.info(f"Making DSG connection to: {self.dsg_uri}")
        err = dsg_link.start()
        if err < 0:
            logging.error("Omniverse connection failed.")
            return

        # Initial pull request
        dsg_link.request_an_update(animation=self.temporal)

        # until the link is dropped, continue
        while not dsg_link.is_shutdown() and not self._shutdown:
            # Reset the line width to the CLI default before each update
            omni_link.line_width = self.line_width
            dsg_link.handle_one_update()

            if one_shot:
                break

        logging.info("Shutting down DSG connection")
        dsg_link.end()
        omni_link.shutdown()

    def run_monitor(self):
        """
        Run monitor and upload GLB files to Omniverse in process.  There are two cases:

        1) the "directory name" is actually a .glb file.  In this case, simply push
        the glb file contents to Omniverse.

        2) If a directory, then we periodically scan the directory for files named "*.upload".
        If this file is found, there are two cases:

            a) The file is empty.  In this case, for a file named ABC.upload, the file
            ABC.glb will be read and uploaded before both files are deleted.

            b) The file contains valid json.  In this case, the json object is parsed with
            the following format (two glb files for the first timestep and one for the second):

                {
                    "version": 1,
                    "destination": "",
                    "files": ["a.glb", "b.glb", "c.glb"],
                    "times": [0.0, 0.0, 1.0]
                }

            "times" is optional and defaults to [0*len("files")].  Once processed,
            all the files referenced in the json and the json file itself are deleted.
            "omniuri" is optional and defaults to the passed Omniverse path.

            Note: In this mode, the method does not return until a "shutdown" file or
            an error is encountered.

            TODO: add "push" mechanism to trigger a DSG push from the connected session.  This
                can be done via the monitor mechanism and used by the Omniverse kit to implement
                a "pull".
        """
        the_dir = self.monitor_directory
        single_file_upload = False
        if os.path.isfile(the_dir) and the_dir.lower().endswith(".glb"):
            single_file_upload = True
        else:
            if not os.path.isdir(the_dir):
                logging.error(f"The monitor directory {the_dir} does not exist.")
                return

        # Build the Omniverse connection
        omni_link = ov_dsg_server.OmniverseWrapper(
            destination=self._destination, line_width=self.line_width
        )
        logging.info("Omniverse connection established.")

        # use an OmniverseUpdateHandler
        update_handler = ov_dsg_server.OmniverseUpdateHandler(omni_link)

        # Link it to the GLB file monitoring service
        glb_link = ov_glb_server.GLBSession(verbose=1, handler=update_handler, vrmode=self.vrmode)
        if single_file_upload:
            start_time = time.time()
            logging.info(f"Uploading file: {the_dir}.")
            try:
                glb_link.start_uploads([0.0, 0.0])
                glb_link.upload_file(the_dir)
                glb_link.end_uploads()
            except Exception as error:
                logging.error(f"Unable to upload file: {the_dir}: {error}")
            logging.info(f"Uploaded in {(time.time() - start_time):.2f}")
        else:
            logging.info(f"Starting file monitoring for {the_dir}.")
            the_dir_path = pathlib.Path(the_dir)
            try:
                stop_file = os.path.join(the_dir, "shutdown")
                orig_destination = omni_link.destination
                while not os.path.exists(stop_file):
                    loop_time = time.time()
                    files_to_remove = []
                    for filename in glob.glob(os.path.join(the_dir, "*.upload")):
                        # reset to the launch URI/directory
                        omni_link.destination = orig_destination
                        # Keep track of the files and time values
                        files_to_remove.append(filename)
                        files_to_process = []
                        file_timestamps = []
                        if os.path.getsize(filename) == 0:
                            # replace the ".upload" extension with ".glb"
                            glb_file = os.path.splitext(filename)[0] + ".glb"
                            if os.path.exists(glb_file):
                                files_to_process.append(glb_file)
                                file_timestamps.append(0.0)
                                files_to_remove.append(glb_file)
                        else:
                            # read the .upload file json content
                            try:
                                with open(filename, "r") as fp:
                                    glb_info = json.load(fp)
                            except Exception:
                                logging.error(f"Unable to read file: {filename}")
                                continue
                            # if specified, set the URI/directory target
                            omni_link.destination = glb_info.get("destination", orig_destination)
                            # Get the GLB files to process
                            the_files = glb_info.get("files", [])
                            files_to_remove.extend(the_files)
                            # Times not used for now, but parse them anyway
                            the_times = glb_info.get("times", [0.0] * len(the_files))
                            file_timestamps.extend(the_times)
                            # Validate a few things
                            if len(the_files) != len(the_times):
                                logging.error(
                                    f"Number of times and files are not the same in: {filename}"
                                )
                                continue
                            files_to_process.extend(the_files)
                        # manage time
                        timeline = sorted(set(file_timestamps))
                        if len(timeline) != 1:
                            logging.warning("Time values not currently supported.")
                        if len(files_to_process) > 1:
                            logging.warning("Multiple glb files not currently fully supported.")
                        # Reset the line width to the CLI default before each update
                        omni_link.line_width = self.line_width
                        # Upload the files
                        glb_link.start_uploads([timeline[0], timeline[-1]])
                        for glb_file, timestamp in zip(files_to_process, file_timestamps):
                            start_time = time.time()
                            logging.info(f"Uploading file: {glb_file} to {omni_link.destination}.")
                            try:
                                time_idx = timeline.index(timestamp) + 1
                                if time_idx == len(timeline):
                                    time_idx -= 1
                                limits = [timestamp, timeline[time_idx]]
                                glb_link.upload_file(glb_file, timeline=limits)
                            except Exception as error:
                                logging.error(f"Unable to upload file: {glb_file}: {error}")
                            logging.info(f"Uploaded in {(time.time() - start_time):.2f}s")
                        glb_link.end_uploads()
                    for filename in files_to_remove:
                        try:
                            # Only delete the file if it is in the_dir_path
                            filename_path = pathlib.Path(filename)
                            if filename_path.is_relative_to(the_dir_path):
                                os.remove(filename)
                        except IOError:
                            pass
                    if time.time() - loop_time < 0.1:
                        time.sleep(0.25)
            except Exception as error:
                logging.error(f"Error encountered while monitoring: {error}")
            logging.info("Stopping file monitoring.")
            try:
                os.remove(stop_file)
            except IOError:
                logging.error("Unable to remove 'shutdown' file.")

        omni_link.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PyEnSight Omniverse Geometry Service")
    parser.add_argument(
        "destination", default="", type=str, help="The directory to save the USD scene graph into."
    )
    parser.add_argument(
        "--verbose",
        metavar="verbose_level",
        default=0,
        type=partial(int_range_type, min_value=0, max_value=3),
        help="Enable logging information (0-3).  Default: 0",
    )
    parser.add_argument(
        "--log_file",
        metavar="log_filename",
        default="",
        type=str,
        help="Save logging output to the named log file instead of stdout.",
    )
    parser.add_argument(
        "--dsg_uri",
        default="grpc://127.0.0.1:5234",
        type=str,
        help="The URI of the EnSight Dynamic Scene Graph server.  Default: grpc://127.0.0.1:5234",
    )
    parser.add_argument(
        "--security_token",
        metavar="token",
        default="",
        type=str,
        help="Dynamic scene graph API security token.  Default: none",
    )
    parser.add_argument(
        "--monitor_directory",
        metavar="glb_directory",
        default="",
        type=str,
        help="Monitor specified directory for GLB files to be exported.  Default: none",
    )
    parser.add_argument(
        "--time_scale",
        metavar="time_scale",
        default=1.0,
        type=float,
        help="Scaling factor to be applied to input time values.  Default: 1.0",
    )
    parser.add_argument(
        "--normalize_geometry",
        metavar="yes|no|true|false|1|0",
        default=False,
        type=str2bool_type,
        help="Enable mapping of geometry to a normalized Cartesian space. Default: false",
    )
    parser.add_argument(
        "--include_camera",
        metavar="yes|no|true|false|1|0",
        default=True,
        type=str2bool_type,
        help="Include the camera in the output USD scene graph. Default: true",
    )
    parser.add_argument(
        "--temporal",
        metavar="yes|no|true|false|1|0",
        default=False,
        type=str2bool_type,
        help="Export a temporal scene graph. Default: false",
    )
    parser.add_argument(
        "--oneshot",
        metavar="yes|no|true|false|1|0",
        default=False,
        type=str2bool_type,
        help="Convert a single geometry into USD and exit.  Default: false",
    )
    line_default: Any = os.environ.get("ANSYS_OV_LINE_WIDTH", None)
    if line_default is not None:
        try:
            line_default = float(line_default)
        except ValueError:
            line_default = None
    parser.add_argument(
        "--line_width",
        metavar="line_width",
        default=line_default,
        type=float,
        help=f"Width of lines: >0=absolute size. <0=fraction of diagonal. 0=none. Default: {line_default}",
    )

    # parse the command line
    args = parser.parse_args()

    # set up logging
    level = logging.ERROR
    if args.verbose == 1:
        level = logging.WARN
    elif args.verbose == 2:
        level = logging.INFO
    elif args.verbose == 3:
        level = logging.DEBUG
    log_args = dict(format="GeometryService:%(levelname)s:%(message)s", level=level)
    if args.log_file:
        log_args["filename"] = args.log_file
    # start with a clean logging instance
    while logging.root.hasHandlers():
        logging.root.removeHandler(logging.root.handlers[0])
    logging.basicConfig(**log_args)  # type: ignore

    # size of lines in data units or fraction of bounding box diagonal
    line_width = 0.0
    if args.line_width is not None:
        line_width = args.line_width

    # Build the server object
    server = OmniverseGeometryServer(
        destination=args.destination,
        dsg_uri=args.dsg_uri,
        security_token=args.security_token,
        monitor_directory=args.monitor_directory,
        time_scale=args.time_scale,
        normalize_geometry=args.normalize_geometry,
        vrmode=not args.include_camera,
        temporal=args.temporal,
        line_width=line_width,
    )

    # run the server
    logging.info("Server startup.")
    if server.monitor_directory:
        server.run_monitor()
    else:
        server.run_server(one_shot=args.oneshot)
    logging.info("Server shutdown.")
