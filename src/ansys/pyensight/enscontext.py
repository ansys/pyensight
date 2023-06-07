"""EnsContext module

Interface to objects that contain a representation of an EnSight session state.
Basically, this is a wrapper around a ZIP format file that contains an EnSight
context or state. Three types of content are supported:

#. Full context: a complete EnSight context file.
#. Simple context: an EnSight context file without any data loading reference.
#. State context: an EnSight state file, all object attributes, no part/object creation.


"""
import base64
import io
import os
import tempfile
from typing import Any, Union
import warnings
import zipfile


class EnsContext:
    """A saved EnSight state

    This object allows for the generation and application of an
    EnSight "state".  The object can store an EnSight "context",
    or a "data-less context".  The internal storage is in a zip
    file wrapper and leverages BytesIO buffers to allow for
    "file-less" operation and provides a mechanism for network
    transport.
    """

    UNKNOWN: int = 0
    FULL_CONTEXT: int = 1
    SIMPLE_CONTEXT: int = 2

    def __init__(self) -> None:
        self._type: int = self.UNKNOWN
        self._buffer: io.BytesIO = io.BytesIO()

    def _set_type(self, names: list) -> None:
        """Update the 'type' of the context

        Look though the file files stored in the zip file.  Look for the special "type" files
        and set the object type accordingly.

        Args:
            names:
                A list of filenames in the zip file.
        """
        self._type = self.UNKNOWN
        if "fullcontext.txt" in names:
            self._type = self.FULL_CONTEXT
        elif "simplecontext.txt" in names:
            self._type = self.SIMPLE_CONTEXT

    def from_zip_file(self, filename: str) -> None:
        """Read a context from a local zip file

        Given the name of a zip file, read in into memory and make the contents
        available via self._zip.

        Args:
            filename:
                The name of the file to read
        """
        with open(filename, "rb") as f:
            data = f.read()
        self.from_zip_data(data)

    def from_zip_data(self, data: Union[bytes, str]) -> None:
        """Read a context from a blob or string

        Given a context file in the form of a bytes object or a
        the same bytes object encoded into a string using base64
        encoding.

        Args:
            data:
                A bytes or string object of the contents of a
                context zip file.
        """
        if type(data) != bytes:
            data = base64.b64decode(data)
        self._buffer = io.BytesIO(data)
        thefile = zipfile.ZipFile(self._buffer, "r")
        self._set_type(thefile.namelist())

    def save_as_zip(self, filename: str) -> None:
        """Save the context information in zip file

        Save any current context to disk as a zip file.

        Args:
            filename:
                Name of the file to save.
        """
        data = self._buffer.getvalue()
        if len(data) < 1:
            raise RuntimeError("No context data to save")
        with open(filename, "wb") as fp:
            fp.write(data)

    def data(self, b64: bool = False) -> Union[bytes, str]:
        """Return a representation of the context file as a string or bytes object

        Either a bytes object or a string (base64 encoded bytes object) representation
        of the current context file is returned.

        Args:
            b64:
                If True, return the bytes representation encoded into a string
                object using base64 encoding.
        Returns:
            A bytes object or a string object.
        """
        data = self._buffer.getvalue()
        if b64:
            return base64.b64encode(data)
        return data

    def _build_from_directory(self, pathname: str) -> None:
        """Create a zip object from the contents of a directory

        Given a directory name, generate an in-memory zip file
        containing all the files in the directory.  A bytes/string
        representation (suitable for use by from_zip_data()) can be
        obtained using the data() method, following a from_directory
        call.

        Args:
            pathname:
                The directory of filenames to be placed in the context file.
        """
        self._buffer = io.BytesIO()
        thefile = zipfile.ZipFile(self._buffer, "w", compression=zipfile.ZIP_DEFLATED)
        for folder_name, sub_folders, file_names in os.walk(pathname):
            for filename in file_names:
                file_pathname = os.path.join(folder_name, filename)
                thefile.write(file_pathname, os.path.basename(file_pathname))
        self._set_type(thefile.namelist())
        thefile.close()

    @staticmethod
    def _fix_context_file(ctx_file: str) -> None:
        """Clean up a context file

        Currently, there is a bug in the single case context file saving code
        that puts information that cannot be recalled independently of other
        cases in the .ctx file.  Remove that information and rewrite the file.

        Args:
              ctx_file:
                The name of the context file to process.
        """
        try:
            with open(ctx_file, "rb") as f:
                ctx = f.read()
            try:
                # Remove the Object MetaData block units, we do not want to restore them
                # as they could change.
                # These are the lines we need to remove:
                #  ensight.objs.core.VARIABLES.find('Pressure',
                #                                   attr="DESCRIPTION")[0].setmetatag('CFD_VAR','')
                #  ensight.objs.core.CURRENTCASE[0].setmetatag('ENS_UNITS_LABEL',2.000000)
                #  ensight.objs.core.CURRENTCASE[0].setmetatag('ENS_UNITS_DIMS',1.000000)
                #  ensight.objs.core.CURRENTCASE[0].setmetatag('ENS_UNITS_LABEL_TIME','s')
                #  ensight.objs.core.CURRENTCASE[0].setmetatag('ENS_UNITS_SYSTEM',1.000000)
                #  ensight.objs.core.CURRENTCASE[0].setmetatag('ENS_UNITS_SYSTEM_NAME','SI')
                start = ctx.index(b"# Object MetaData commands")
                end = ctx.index(b"# End Object MetaData commands")
                if (start >= 0) and (end >= 0):
                    saved_lines = list()
                    for line in ctx[start:end].split(b"\n"):
                        skip = b".setmetatag('CFD_VAR'" in line
                        skip = skip or (b".setmetatag('ENS_UNITS_LABEL'" in line)
                        skip = skip or (b".setmetatag('ENS_UNITS_DIMS'" in line)
                        skip = skip or (b".setmetatag('ENS_UNITS_LABEL_TIME'" in line)
                        skip = skip or (b".setmetatag('ENS_UNITS_SYSTEM'" in line)
                        skip = skip or (b".setmetatag('ENS_UNITS_SYSTEM_NAME'" in line)
                        skip = skip and line.startswith(b"ensight.objs.core.")
                        if skip:
                            continue
                        saved_lines.append(line)
                    ctx = ctx[:start] + b"\n".join(saved_lines) + ctx[end:]
            except ValueError:
                warnings.warn("Note: Object Metadata block not found")
            try:
                # remove the Textures block (as the textures are not in the project)
                start = ctx.index(b"# Textures")
                end = ctx.index(b"# Attributes To Restore Viewport Defaults")
                if (start >= 0) and (end >= 0):
                    ctx = ctx[:start] + ctx[end:]
            except ValueError:
                warnings.warn("Note: Object Metadata block not found")
            # rewrite the file
            with open(ctx_file, "wb") as f:
                f.write(ctx)
        except Exception as e:
            warnings.warn("Unable to filter out undesired context file content: {}".format(e))

    def restore_context(self, ensight: Any) -> None:
        """Restore a context from the state in this object

        Unpack the zip contents to disk (temporary directory) and perform a context restore on
        the contents.

        Args:
            ensight:
                The EnSight interface to use to make the actual native API commands.
        """
        with tempfile.TemporaryDirectory() as tempdirname:
            thefile = zipfile.ZipFile(self._buffer, "r")
            thefile.extractall(path=tempdirname)
            if self._type in (self.SIMPLE_CONTEXT, self.FULL_CONTEXT):
                _ = ensight.file.context_restore_rescale("OFF")
                _ = ensight.file.restore_context(os.path.join(tempdirname, "context.ctx"))

    def capture_context(
        self, ensight: Any, context: int = SIMPLE_CONTEXT, all_cases: bool = True
    ) -> None:
        """Capture the current state

        Cause the EnSight interface to save a context into a temporary directory.
        Zip up the directory contents (along with a "type" marking file) into the
        zip object inside of this state instance.

        Args:
            ensight:
                The EnSight interface to use to make the actual native API commands.
            context:
                The type of context to save.
            all_cases:
                By default, save all cases.  If all_cases is set to False, only
                the current case will be saved.
        """
        with tempfile.TemporaryDirectory() as tempdirname:
            # Save a context
            which = "current_case"
            if all_cases:
                which = "all_cases"
            _ = ensight.file.save_context_type(which)
            _ = ensight.file.save_context(os.path.join(tempdirname, "context.ctx"))
            if context == self.SIMPLE_CONTEXT:
                # remove sections that cause problems
                with open(os.path.join(tempdirname, "simplecontext.txt"), "w") as fp:
                    fp.write("simplecontext")
                self._fix_context_file(os.path.join(tempdirname, "context.ctx"))
            elif context == self.FULL_CONTEXT:
                with open(os.path.join(tempdirname, "fullcontext.txt"), "w") as fp:
                    fp.write("fullcontext")
            self._build_from_directory(tempdirname)
