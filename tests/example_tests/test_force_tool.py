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

import math
import os
import time

from ansys.pyensight.core.dockerlauncher import DockerLauncher
from ansys.pyensight.core.locallauncher import LocalLauncher
import pytest


def create_frame(ensight):
    ensight.frame.create()
    ensight.frame.select_begin(1)
    ensight.frame.visible("OFF")
    ensight.frame.type("rectangular")
    ensight.frame.orientation_x(1, 0, 0)
    ensight.frame.orientation_y(0, 1, 0)
    ensight.frame.orientation_z(0, 0, 1)
    ensight.frame.len_x(6.66666651)
    ensight.frame.len_y(6.66666651)
    ensight.frame.len_z(6.66666651)
    ensight.frame.number_of_labels_x(3)
    ensight.frame.number_of_labels_y(3)
    ensight.frame.number_of_labels_z(3)
    ensight.frame.line_width(1)
    ensight.frame.rgb(1, 1, 1)
    ensight.frame.x_labels("OFF")
    ensight.frame.y_labels("OFF")
    ensight.frame.z_labels("OFF")
    ensight.frame.symmetry_type("none")
    ensight.frame.symmetry_angle(30)
    ensight.frame.symmetry_rinstances(1)
    ensight.frame.symmetry_mirror_z("OFF")
    ensight.frame.symmetry_mirror_y("OFF")
    ensight.frame.symmetry_mirror_x("OFF")
    ensight.frame.symmetry_mirror_xy("OFF")
    ensight.frame.symmetry_mirror_yz("OFF")
    ensight.frame.symmetry_mirror_xz("OFF")
    ensight.frame.symmetry_mirror_xyz("OFF")
    ensight.frame.symmetry_use_file("OFF")
    ensight.frame.symmetry_tinstances(1)
    ensight.frame.symmetry_delta(0, 0, 0)
    ensight.frame.symmetry_axis("z")
    ensight.frame.assign(0)


def test_force_tool(tmpdir, pytestconfig: pytest.Config):
    data_dir = tmpdir.mkdir("datadir")
    use_local = pytestconfig.getoption("use_local_launcher")
    install_path = pytestconfig.getoption("install_path")
    if use_local:
        launcher = LocalLauncher(ansys_installation=install_path)
    else:
        launcher = DockerLauncher(
            data_directory=data_dir, use_dev=True, grpc_disable_tls=True, grpc_use_tcp_sockets=True
        )
    session = launcher.start()
    path = None
    if use_local:
        path = f"{session.cei_home}/ensight{session.cei_suffix}/data/RC_Plane/"
    else:
        count = 0
        success = False
        while not success and count < 5:
            try:
                path = session.download_pyansys_example("RC_Plane", "pyensight", folder=True)
                success = True
            except Exception:
                time.sleep(5)
                count += 1
        if count == 5 and success is False:
            raise RuntimeError("Download of RC Plane case not possible")
    session.load_data(os.path.join(path, "extra300_RC_Plane_cpp.case"))
    create_frame(session.ensight)
    body_parts = [
        "canopy",
        "fuselage",
        "horizontal_stabilizer",
        "nose",
        "vertical_stabilizer",
        "wing_lower_surface",
        "wing_te",
        "wing_tip",
        "wing_upper_surface",
    ]
    vref = session.ensight.utils.variables.get_const_val("Vinf")
    dref = session.ensight.utils.variables.get_const_val("Rho")
    aoa = session.ensight.utils.variables.get_const_val("AoA")
    session.ensight.utils.variables.get_const_val(session.ensight.objs.core.VARIABLES["AoA"][0])
    vxref = vref * math.cos(aoa * math.pi / 180)
    vyref = vref * math.sin(aoa * math.pi / 180)
    vzref = 0.0
    area_ref = None
    if session.ensight.utils.variables._calc_var(["wing_upper_surface"], "area_ref = Area(plist)"):
        area_ref = session.ensight.utils.variables.get_const_val("area_ref")

    if not area_ref:
        raise RuntimeError("The reference area could not be calculated")
    session.ensight.utils.variables.compute_forces(
        pobj_list=body_parts.copy(),
        press_var_obj="staticPressure",
        shear_var_obj="wallShearStress",
        shear_var_type=session.ensight.utils.variables.SHEAR_VAR_TYPE_STRESS,
        export_filename="test.csv",
        area_ref=area_ref,
        density_ref=dref,
        velocity_x_ref=vxref,
        velocity_y_ref=vyref,
        velocity_z_ref=vzref,
        up_vector=session.ensight.utils.variables.UP_VECTOR_PLUS_Y,
        frame_index=1,
    )
    session.ensight.utils.variables.compute_forces(
        pobj_list=body_parts.copy(),
        press_var_obj="staticPressure",
        shear_var_obj="wallShearStress",
        shear_var_type=session.ensight.utils.variables.SHEAR_VAR_TYPE_STRESS,
        export_filename="test.csv",
        area_ref=area_ref,
        density_ref=dref,
        velocity_x_ref=vxref,
        velocity_y_ref=vyref,
        velocity_z_ref=vzref,
        up_vector=session.ensight.utils.variables.UP_VECTOR_PLUS_Y,
        frame_index=1,
    )
    session.ensight.utils.variables.compute_forces(
        pobj_list=body_parts.copy(),
        press_var_obj="staticPressure",
        shear_var_obj="wallShearStress",
        shear_var_type=session.ensight.utils.variables.SHEAR_VAR_TYPE_STRESS,
        export_filename="test2.csv",
        area_ref=area_ref,
        density_ref=dref,
        velocity_x_ref=vxref,
        velocity_y_ref=vyref,
        velocity_z_ref=vzref,
        up_vector=session.ensight.utils.variables.UP_VECTOR_PLUS_Y,
    )
    assert os.path.exists("test.csv")
    assert os.path.exists("test2.csv")
