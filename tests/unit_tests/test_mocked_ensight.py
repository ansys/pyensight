# Copyright (C) 2022 - 2025 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
from unittest import mock
import zipfile

from ansys.pyensight.core.enscontext import EnsContext, _capture_context, _restore_context


def test_utils(mocked_session, tmpdir):
    data_dir = tmpdir.mkdir("datadir")

    def animation_file(filename):
        with open(filename, "w") as _file:
            _file.write("")

    export = mocked_session.ensight.utils.export
    export._image_remote(800, 600, 4, False, False)
    export._image_remote(800, 600, 4, False, True)
    export._image_remote(800, 600, 4, True, False)
    export._image_remote(800, 600, 4, True, True)
    _file = mock.MagicMock("file")
    _file.animation_rend_offscreen = lambda x: ""
    _file.animation_screen_tiling = lambda x, y: ""
    _file.animation_format = lambda x: ""
    _file.animation_format_options = lambda x: ""
    _file.animation_frame_rate = lambda x: ""
    _file.animation_numpasses = lambda x: ""
    _file.animation_stereo = lambda x: ""
    _file.animation_file = animation_file
    _file.animation_window_size = lambda x: ""
    _file.animation_window_xy = lambda x, y: ""
    _file.animation_frames = lambda x: ""
    _file.animation_start_number = lambda x: ""
    _file.animation_multiple_images = lambda x: ""
    _file.animation_raytrace_it = lambda x: ""
    _file.animation_raytrace_ext = lambda x: ""
    _file.animation_play_time = lambda x: ""
    _file.animation_play_flipbook = lambda x: ""
    _file.animation_play_keyframe = lambda x: ""
    _file.animation_reset_time = lambda x: ""
    _file.animation_reset_traces = lambda x: ""
    _file.animation_reset_flipbook = lambda x: ""
    _file.animation_reset_keyframe = lambda x: ""
    _file.save_animation = lambda: ""
    _file.save_context_type = lambda x: ""
    _file.save_context = lambda x: ""
    mocked_session._ensight.file = _file
    mocked_session._ensight.objs.core.WINDOWSIZE = 800, 600
    mocked_session._ensight.objs.core.TIMESTEP_LIMITS = [1, 10]
    export._animation_remote(800, 600, 4, export.ANIM_TYPE_SOLUTIONTIME, 0, 30, 30, "", True)
    export._animation_remote(800, 600, 4, export.ANIM_TYPE_SOLUTIONTIME, 0, 30, 30, "", False)
    export._animation_remote(800, 600, 4, export.ANIM_TYPE_ANIMATEDTRACES, 0, 30, 30, "", True)
    export._animation_remote(800, 600, 4, export.ANIM_TYPE_KEYFRAME, 0, 30, 30, "", False)
    export._animation_remote(800, 600, 4, export.ANIM_TYPE_KEYFRAME, 0, 30, 30, "", True)
    export._animation_remote(800, 600, 4, export.ANIM_TYPE_FLIPBOOK, 0, 30, 30, "", False)
    export._animation_remote(800, 600, 4, export.ANIM_TYPE_FLIPBOOK, 0, 30, 30, "", True)
    export._animation_remote(800, 600, 4, export.ANIM_TYPE_FLIPBOOK, 0, 30, 30, "test", True)
    export._animation_remote(800, 600, 4, "", 0, 30, 30, "", True)
    c = EnsContext()
    c._capture_context(ensight=mocked_session._ensight)
    _capture_context(ensight=mocked_session._ensight, full=False)
    _capture_context(ensight=mocked_session._ensight, full=True)
    with zipfile.ZipFile(os.path.join(data_dir, "test.zip"), "w") as _file:
        pass
    with open(os.path.join(data_dir, "test.zip"), "rb") as _file:
        data = _file.read()
    _restore_context(ensight=mocked_session._ensight, data=data)
    with open(os.path.join(data_dir, "ctx.ctx"), "wb") as _file:
        _file.write(b"# Object MetaData commands")
        _file.write(b"# End Object MetaData commands")
    c._fix_context_file(os.path.join(data_dir, "ctx.ctx"))
