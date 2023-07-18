import os
import tempfile
from types import ModuleType
from typing import Any, Optional, Union
import uuid

from PIL import Image
import numpy

try:
    import ensight
except ImportError:
    from ansys.api.pyensight import ensight_api


class Export:
    """Provides the ``ensight.utils.export`` interface.

    The methods in this class implement simplified interfaces to common
    image and animation export operations.

    This class is instantiated as ``ensight.utils.export`` in EnSight Python
    and as ``Session.ensight.utils.export`` in PyEnSight. The constructor is
    passed the interface, which serves as the ``ensight`` module for either
    case. As a result, the methods can be accessed as ``ensight.utils.export.image()``
    in EnSight Python or ``session.ensight.utils.export.animation()`` in PyEnSight.

    Parameters
    ----------
    interface :
        Entity that provides the ``ensight`` namespace. In the case of
        EnSight Python, the ``ensight`` module is passed. In the case
        of PyEnSight, ``Session.ensight`` is passed.
    """

    def __init__(self, interface: Union["ensight_api.ensight", "ensight"]):
        self._ensight = interface

    def _remote_support_check(self):
        """Determine if ``ensight.utils.export`` exists on the remote system.

            Before trying to use this module, use this method to determine if this
            module is available in the EnSight instance.

        Raises
        ------
            RuntimeError if the module is not present.
        """
        # if a module, then we are inside EnSight
        if isinstance(self._ensight, ModuleType):
            return
        try:
            _ = self._ensight._session.cmd("dir(ensight.utils.export)")
        except RuntimeError:
            import ansys.pyensight.core

            raise RuntimeError(
                f"Remote EnSight session must have PyEnsight version \
            {ansys.pyensight.core.DEFAULT_ANSYS_VERSION} or higher installed to use this API."
            )

    TIFFTAG_IMAGEDESCRIPTION: int = 0x010E

    def image(
        self,
        filename: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        passes: int = 4,
        enhanced: bool = False,
        raytrace: bool = False,
    ) -> None:
        """Render an image of the current EnSight scene.

        This method returns a PIL image object.

        Parameters
        ----------
        filename : str
            Name of the local file to save the image to.
        width : int, optional
            Width of the image in pixels. The default is ``None``, in which case
            ```ensight.objs.core.WINDOWSIZE[0]`` is used.
        height : int, optional
            Height of the image in pixels. The default is ``None``, in which case
            ``ensight.objs.core.WINDOWSIZE[1]`` is used.
        passes : int, optional
            Number of antialiasing passes. The default is ``4``.
        enhanced : bool, optional
            Whether to save the image to the filename specified in the TIFF format.
            The default is ``False``. The TIFF format includes additional channels
            for the per-pixel object and variable information.
        raytrace : bool, optional
            Whether to render the image with the raytracing engine. The default is ``False``.

        Examples
        --------
        >>> s = LocalLauncher().start()
        >>> s.load_data(f"{s.cei_home}/ensight{s.cei_suffix}/data/cube/cube.case")
        >>> s.ensight.utils.export.image("example.png")

        """
        self._remote_support_check()

        win_size = self._ensight.objs.core.WINDOWSIZE
        if width is None:
            width = win_size[0]
        if height is None:
            height = win_size[1]

        if isinstance(self._ensight, ModuleType):
            raw_image = self._image_remote(width, height, passes, enhanced, raytrace)
        else:
            cmd = f"ensight.utils.export._image_remote({width}, {height}, {passes}, "
            cmd += f"{enhanced}, {raytrace})"
            raw_image = self._ensight._session.cmd(cmd)

        pil_image = self._dict_to_pil(raw_image)
        if enhanced:
            tiffinfo_dir = {self.TIFFTAG_IMAGEDESCRIPTION: raw_image["metadata"]}
            pil_image[0].save(
                filename,
                save_all=True,
                append_images=[pil_image[1], pil_image[2]],
                tiffinfo=tiffinfo_dir,
            )
        else:
            pil_image[0].save(filename)

    def _dict_to_pil(self, data: dict) -> list:
        """Convert the contents of the dictionary into a PIL image.

        Parameters
        ----------
        data : dict
            Dictionary representation of the contents of the ``enve`` object.

        Returns
        -------
        list
            List of one or three image objects, [RGB {, pick, variable}].
        """
        images = [
            Image.fromarray(self._numpy_from_dict(data["pixeldata"])).transpose(
                Image.FLIP_TOP_BOTTOM
            )
        ]
        if data.get("variabledata", None) and data.get("pickdata", None):
            images.append(
                Image.fromarray(self._numpy_from_dict(data["pickdata"])).transpose(
                    Image.FLIP_TOP_BOTTOM
                )
            )
            images.append(
                Image.fromarray(self._numpy_from_dict(data["variabledata"])).transpose(
                    Image.FLIP_TOP_BOTTOM
                )
            )
        return images

    @staticmethod
    def _numpy_to_dict(array: Any) -> Optional[dict]:
        """Convert a numpy array into a dictionary.

        Parameters
        ----------
        array:
            Numpy array or None.

        Returns
        -------
        ``None`` or a dictionary that can be serialized.
        """
        if array is None:
            return None
        return dict(shape=array.shape, dtype=array.dtype.str, data=array.tostring())

    @staticmethod
    def _numpy_from_dict(obj: Optional[dict]) -> Any:
        """Convert a dictionary into a numpy array.

        Parameters
        ----------
        obj:
            Dictionary generated by ``_numpy_to_dict`` or ``None``.

        Returns
        -------
        ``None`` or a numpy array.
        """
        if obj is None:
            return None
        return numpy.frombuffer(obj["data"], dtype=obj["dtype"]).reshape(obj["shape"])

    def _image_remote(
        self, width: int, height: int, passes: int, enhanced: bool, raytrace: bool
    ) -> dict:
        """EnSight-side implementation.

        Parameters
        ----------
        width : int
            Width of the image in pixels.
        height : int
            Height of the image in pixels.
        passes : int
            Number of antialiasing passes.
        enhanced : bool
            Whether to returned the image as a "deep pixel" TIFF image file.
        raytrace :
            Whether to render the image with the raytracing engine.

        Returns
        -------
        dict
            Dictionary of the various channels.
        """
        if not raytrace:
            img = ensight.render(x=width, y=height, num_samples=passes, enhanced=enhanced)
        else:
            import enve

            with tempfile.TemporaryDirectory() as tmpdirname:
                tmpfilename = os.path.join(tmpdirname, str(uuid.uuid1()))
                ensight.file.image_format("png")
                ensight.file.image_file(tmpfilename)
                ensight.file.image_window_size("user_defined")
                ensight.file.image_window_xy(width, height)
                ensight.file.image_rend_offscreen("ON")
                ensight.file.image_numpasses(passes)
                ensight.file.image_stereo("current")
                ensight.file.image_screen_tiling(1, 1)
                ensight.file.raytracer_options("fgoverlay 1 imagedenoise 1 quality 5")
                ensight.file.image_raytrace_it("ON")
                ensight.file.save_image()
                img = enve.image()
                img.load(f"{tmpfilename}.png")
        # get the channels from the enve.image instance
        output = dict(width=width, height=height, metadata=img.metadata)
        # extract the channels from the image
        output["pixeldata"] = self._numpy_to_dict(img.pixeldata)
        output["variabledata"] = self._numpy_to_dict(img.variabledata)
        output["pickdata"] = self._numpy_to_dict(img.pickdata)
        return output

    ANIM_TYPE_SOLUTIONTIME: int = 0
    ANIM_TYPE_ANIMATEDTRACES: int = 1
    ANIM_TYPE_FLIPBOOK: int = 2
    ANIM_TYPE_KEYFRAME: int = 3

    def animation(
        self,
        filename: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        passes: int = 4,
        anim_type: int = ANIM_TYPE_SOLUTIONTIME,
        frames: Optional[int] = None,
        starting_frame: int = 0,
        frames_per_second: float = 60.0,
        format_options: Optional[str] = "",
        raytrace: bool = False,
    ) -> None:
        """Generate an MPEG4 animation file.

        An MPEG4 animation file can be generated from temporal data, flipbooks, keyframes,
        or animated traces.

        Parameters
        ----------
        filename : str
            Name for the MPEG4 file to save to local disk.
        width : int, optional
            Width of the image in pixels. The default is ``None``, in which case
            ``ensight.objs.core.WINDOWSIZE[0]`` is used.
        height : int, optional
            Height of the image in pixels. The default is ``None``, in which case
            ``ensight.objs.core.WINDOWSIZE[1]`` is used.
        passes : int, optional
            Number of antialiasing passes. The default  is ``4``.
        anim_type : int, optional
            Type of the animation to render. The default is ``0``, in which case
            ``"ANIM_TYPE_SOLUTIONTIME"`` is used. This table provides descriptions
            by each option number and name:

            ========================== ========================================
            Name                       Animation type
            ========================== ========================================
            0: ANIM_TYPE_SOLUTIONTIME   Animation over all solution times
            1: ANIM_TYPE_ANIMATEDTRACES Records animated rotations and traces
            2: ANIM_TYPE_FLIPBOOK       Records current flipbook animation
            3: ANIM_TYPE_KEYFRAME       Records current kKeyframe animation
            ========================== ========================================

        frames : int, optional
            Number of frames to save. The default is ``None``. The default for
            all but ``ANIM_TYPE_ANIMATEDTRACES`` covers all timesteps, flipbook
            pages, or keyframe steps. If ``ANIM_TYPE_ANIMATEDTRACES`` is specified,
            this keyword is required.
        starting_frame : int, optional
            Keyword for saving a subset of the complete collection of frames.
            The default is ``0``.
        frames_per_second : float, optional
            Number of frames per second for playback in the saved animation.
            The default is ``60.0``.
        format_options : str, optional
            More specific options for the MPEG4 encoder. The default is ``""``.
        raytrace : bool, optional
            Whether to render the image with the raytracing engine. The default is ``False``.

        Examples
        --------
        >>> s = LocalLauncher().start()
        >>> data = f"{s.cei_home}/ensight{s.cei_suffix}gui/demos/Crash Queries.ens"
        >>> s.ensight.objs.ensxml_restore_file(data)
        >>> quality = "Quality Best Type 1"
        >>> s.ensight.utils.export.animation("local_file.mp4", format_options=quality)

        """
        self._remote_support_check()

        win_size = self._ensight.objs.core.WINDOWSIZE
        if width is None:
            width = win_size[0]
        if height is None:
            height = win_size[1]

        if format_options is None:
            format_options = "Quality High Type 1"

        num_frames: int = 0
        if frames is None:
            if anim_type == self.ANIM_TYPE_SOLUTIONTIME:
                num_timesteps = self._ensight.objs.core.TIMESTEP_LIMITS[1]
                num_frames = num_timesteps - starting_frame
            elif anim_type == self.ANIM_TYPE_ANIMATEDTRACES:
                raise RuntimeError("frames is a required keyword with ANIMATEDTRACES animations")
            elif anim_type == self.ANIM_TYPE_FLIPBOOK:
                num_flip_pages = len(self._ensight.objs.core.FLIPBOOKS[0].PAGE_DETAILS)
                num_frames = num_flip_pages - starting_frame
            elif anim_type == self.ANIM_TYPE_KEYFRAME:
                num_keyframe_pages = self._ensight.objs.core.KEYFRAMEDATA["totalFrames"]
                num_frames = num_keyframe_pages - starting_frame
        else:
            num_frames = frames

        if num_frames < 1:
            raise RuntimeError(
                "No frames selected. Perhaps a static dataset SOLUTIONTIME request \
                 or no FLIPBOOK/KEYFRAME defined."
            )

        if isinstance(self._ensight, ModuleType):
            raw_mpeg4 = self._animation_remote(
                width,
                height,
                passes,
                anim_type,
                starting_frame,
                num_frames,
                frames_per_second,
                format_options,
                raytrace,
            )
        else:
            cmd = f"ensight.utils.export._animation_remote({width}, {height}, {passes}, "
            cmd += f"{anim_type}, {starting_frame}, {num_frames}, "
            cmd += f"{frames_per_second}, '{format_options}', {raytrace})"
            raw_mpeg4 = self._ensight._session.cmd(cmd)

        with open(filename, "wb") as fp:
            fp.write(raw_mpeg4)

    def _animation_remote(
        self,
        width: int,
        height: int,
        passes: int,
        anim_type: int,
        start: int,
        frames: int,
        fps: float,
        options: str,
        raytrace: bool,
    ) -> bytes:
        """EnSight-side implementation.

        Parameters
        ----------
        width : int
            Width of the image in pixels.
        height : int
            Height of the image in pixels.
        passes : int
            Number of antialiasing passes.
        anim_type : int
            Type of animation to save.
        start : int
            First frame number to save.
        frames : int
            Number of frames to save.
        fps : float
            Output framerate.
        options : str
            MPEG4 configuration options.
        raytrace : bool
            Whether to render the image with the raytracing engine.

        Returns
        -------
        bytes
            MPEG4 stream in bytes.
        """

        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpfilename = os.path.join(tmpdirname, str(uuid.uuid1()) + ".mp4")
            self._ensight.file.animation_rend_offscreen("ON")
            self._ensight.file.animation_screen_tiling(1, 1)
            self._ensight.file.animation_format("mpeg4")
            if options:
                self._ensight.file.animation_format_options(options)
            self._ensight.file.animation_frame_rate(fps)
            self._ensight.file.animation_rend_offscreen("ON")
            self._ensight.file.animation_numpasses(passes)
            self._ensight.file.animation_stereo("mono")
            self._ensight.file.animation_screen_tiling(1, 1)
            self._ensight.file.animation_file(tmpfilename)
            self._ensight.file.animation_window_size("user_defined")
            self._ensight.file.animation_window_xy(width, height)
            self._ensight.file.animation_frames(frames)
            self._ensight.file.animation_start_number(start)
            self._ensight.file.animation_multiple_images("OFF")
            if raytrace:
                self._ensight.file.animation_raytrace_it("ON")
            else:
                self._ensight.file.animation_raytrace_it("OFF")
            self._ensight.file.animation_raytrace_ext("OFF")

            self._ensight.file.animation_play_time("OFF")
            self._ensight.file.animation_play_flipbook("OFF")
            self._ensight.file.animation_play_keyframe("OFF")

            self._ensight.file.animation_reset_time("OFF")
            self._ensight.file.animation_reset_traces("OFF")
            self._ensight.file.animation_reset_flipbook("OFF")
            self._ensight.file.animation_reset_keyframe("OFF")

            if anim_type == self.ANIM_TYPE_SOLUTIONTIME:
                # playing over time
                self._ensight.file.animation_play_time("ON")
                self._ensight.file.animation_reset_time("ON")
            elif anim_type == self.ANIM_TYPE_ANIMATEDTRACES:
                # recording particle traces/etc
                self._ensight.file.animation_reset_traces("ON")
            elif anim_type == self.ANIM_TYPE_KEYFRAME:
                self._ensight.file.animation_reset_keyframe("ON")
                self._ensight.file.animation_play_keyframe("ON")
            elif anim_type == self.ANIM_TYPE_FLIPBOOK:
                self._ensight.file.animation_play_flipbook("ON")
                self._ensight.file.animation_reset_flipbook("ON")

            self._ensight.file.save_animation()

            with open(tmpfilename, "rb") as fp:
                mp4_data = fp.read()

        return mp4_data
