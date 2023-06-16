"""EnsContext module

Interface to objects that contain a representation of an EnSight session state.
Three types of content are supported:

    #. Full context: a complete EnSight context file.
    #. Simple context: an EnSight context file without any data loading reference.

"""
import base64
import io
import os
import tempfile
from typing import Any, Optional, Union
import warnings
import zipfile


class EnsContext:
    """A saved EnSight session state

    This object allows for the generation and application of the
    EnSight "state".  The object may store a EnSight "context",
    or a "data-less context" representation.  The object can
    save() and load() the context to/from disk.

    Parameters
    ----------
    filename : str, optional
        If specified, "load()" the named context file after
        creating the object instance.

    """

    _UNKNOWN: int = 0
    _FULL_CONTEXT: int = 1
    _SIMPLE_CONTEXT: int = 2

    def __init__(self, filename: Optional[str] = None) -> None:
        """Initialized EnsContext."""
        self._type: int = self._UNKNOWN
        self._buffer: io.BytesIO = io.BytesIO()
        if filename is not None:
            self.load(filename)

    def _set_type(self, names: list) -> None:
        """Update the 'type' of the context

        Look though the file files stored in the zip file.  Look for the special
        embedded "type" files and set the object type accordingly.

        Parameters
        ----------
        names: list
            A list of filenames in the zip file.

        """
        self._type = self._UNKNOWN
        if "fullcontext.txt" in names:
            self._type = self._FULL_CONTEXT
        elif "simplecontext.txt" in names:
            self._type = self._SIMPLE_CONTEXT

    def load(self, filename: str) -> None:
        """Read a context from a local zip file

        Given the name of a context file, read it into memory and make it available
        for use by the PyEnSight Session methods.

        Parameters
        ----------
        filename: str
            The name of the file to read.

        """
        if not zipfile.is_zipfile(filename):
            raise RuntimeError(f"'{filename}' is not a saved context file.")
        with open(filename, "rb") as f:
            data = f.read()
        self._from_data(data)

    def _from_data(self, data: Union[bytes, str]) -> None:
        """Read a context from a blob or string

        Given a context file in the form of a bytes object or a
        the same bytes object encoded into a string using base64
        encoding.

        Parameters
        ----------
        data: Union[bytes, str]
            A bytes or string object of the contents of a
            context zip file.

        """
        if type(data) != bytes:
            data = base64.b64decode(data)
        self._buffer = io.BytesIO(data)
        the_file = zipfile.ZipFile(self._buffer, "r")
        self._set_type(the_file.namelist())

    def save(self, filename: str) -> None:
        """Save the context information to a file

        Save the current context to disk.

        Parameters
        ----------
        filename: str
            Name of the file to save.

        """
        data = self._buffer.getvalue()
        if len(data) < 1:
            raise RuntimeError("No context data to save")
        with open(filename, "wb") as fp:
            fp.write(data)

    def _data(self, b64: bool = False) -> Union[bytes, str]:
        """Return a representation of the context file as a string or bytes object

        Either a bytes object or a string (base64 encoded bytes object)
        representation of the current context file is returned.

        Parameters
        ----------
        b64: bool
            If True, return the bytes representation encoded into a string
            object using base64 encoding. By default, false.

        Returns
        -------
        Union[bytes, str]
            A bytes object or a string object.

        """
        data = self._buffer.getvalue()
        if b64:
            return base64.b64encode(data).decode("ascii")
        return data

    def _build_from_directory(self, pathname: str) -> None:
        """Create a zip object from the contents of a directory

        Given a directory name, generate an in-memory zip file
        containing all the files in the directory.  A bytes/string
        representation (suitable for use by from_zip_data()) can be
        obtained using the data() method, following a from_directory
        call.

        Parameters
        ----------
        pathname: str
            The directory of filenames to be placed in the context
            file.
        """
        self._buffer = io.BytesIO()
        the_file = zipfile.ZipFile(self._buffer, "w", compression=zipfile.ZIP_DEFLATED)
        for folder_name, _, file_names in os.walk(pathname):
            for filename in file_names:
                file_pathname = os.path.join(folder_name, filename)
                the_file.write(file_pathname, os.path.basename(file_pathname))
        self._set_type(the_file.namelist())
        the_file.close()

    @staticmethod
    def _fix_context_file(ctx_file: str) -> None:
        """Clean up a context file

        Currently, there is a bug in the single case context file saving code
        that puts information that cannot be recalled independently of other
        cases in the .ctx file.  Remove that information and rewrite the file.

        Parameters
        ----------
        ctx_file: str
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

    def _restore_context(self, ensight: Any) -> None:
        """Restore a context from the state in this object

        Unpack the zip contents to disk (temporary directory) and perform a context restore on
        the contents.

        Parameters
        ----------
        ensight : Any
            The EnSight interface to use to make the actual native API commands.

        """
        with tempfile.TemporaryDirectory() as tempdirname:
            the_file = zipfile.ZipFile(self._buffer, "r")
            the_file.extractall(path=tempdirname)
            if self._type in (self._SIMPLE_CONTEXT, self._FULL_CONTEXT):
                _ = ensight.file.context_restore_rescale("OFF")
                _ = ensight.file.restore_context(os.path.join(tempdirname, "context.ctx"))

    def _capture_context(
        self, ensight: Any, context: int = _SIMPLE_CONTEXT, all_cases: bool = True
    ) -> None:
        """Capture the current state

        Cause the EnSight interface to save a context into a temporary directory.
        Zip up the directory contents (along with a "type" marking file) into the
        zip object inside of this state instance.

        Parameters
        ----------
        ensight : Any
            The EnSight interface to use to make the actual native API commands.
        context : int, optional
            The type of context to save. By default, _SIMPLE_CONTEXT.
        all_cases : bool, optional
            By default, save all cases.  If all_cases is set to False, only
            the current case will be saved. By default, True.

        """
        with tempfile.TemporaryDirectory() as tempdirname:
            # Save a context
            which = "current_case"
            if all_cases:
                which = "all_cases"
            _ = ensight.file.save_context_type(which)
            _ = ensight.file.save_context(os.path.join(tempdirname, "context.ctx"))
            if context == self._SIMPLE_CONTEXT:
                # remove sections that cause problems
                with open(os.path.join(tempdirname, "simplecontext.txt"), "w") as fp:
                    fp.write("simplecontext")
                self._fix_context_file(os.path.join(tempdirname, "context.ctx"))
            elif context == self._FULL_CONTEXT:
                with open(os.path.join(tempdirname, "fullcontext.txt"), "w") as fp:
                    fp.write("fullcontext")
            self._build_from_directory(tempdirname)


def _capture_context(ensight: Any, full: bool) -> Any:
    """Private interface called by PyEnSight

    API that makes it simpler to capture a context from a PyEnSight session.

    Parameters
    ----------
    ensight: Any
        EnSight session interface
    full: bool
        True if a "full context" should be saved.
    Returns
    -------
    Any
        A base64 representation of the context.

    """
    tmp = EnsContext()
    mode = EnsContext._SIMPLE_CONTEXT
    if full:
        mode = EnsContext._FULL_CONTEXT
    tmp._capture_context(ensight, context=mode)
    return tmp._data(b64=True)


def _restore_context(ensight: Any, data: str) -> None:
    """Private interface called by PyEnSight

    API that makes it simpler to restore a context from a PyEnSight session.

    Parameters
    ----------
    ensight: Any
        EnSight session interface
    data: str
        A base64 representation of the context.
    """
    tmp = EnsContext()
    tmp._from_data(data)
    tmp._restore_context(ensight)
