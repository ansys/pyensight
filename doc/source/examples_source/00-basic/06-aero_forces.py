"""
.. _aero_forces:

Calculate the Net Aerodynamic Forces
=======================================================

Utilze EnSight Net Force Tool in order 
to Calculate the Net Aerodynamic Forces

Intended to work with EnSight version 24.2 or later

"""

###############################################################################
# Start an EnSight session
# ------------------------
# Launch and connect to an instance of EnSight.
# This example uses a local EnSight installation.
import math
import os
from ansys.pyensight.core import LocalLauncher
#
# batch is default (no visible ensight session)
session = LocalLauncher().start()
# use below for interactive debugging with a visible ensight session 
#session = LocalLauncher(batch=False).start()

# Setup shortcuts for long winded calls.
eocore = session.ensight.objs.core
eoutil = session.ensight.utils

###############################################################################
# Load a dataset
#
path = session.download_pyansys_example("RC_Plane", "pyensight", folder=True)
session.load_data(os.path.join(path, "extra300_RC_Plane_cpp.case"))
session.show("image", width=800, height=600)
#
# calc forces
#
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
vzref = 0
area_ref = None
if session.ensight.utils.variables._calc_var(["wing_upper_surface"], "area_ref = Area(plist)"):
    area_ref = session.ensight.utils.variables.get_const_val("area_ref")

if not area_ref:
    raise RuntimeError("The reference area could not be calculated")
#
#  Compute forces on 2D parts
# .. image:: /_static/06_aero_forces_1.png
#
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
)
#assert os.path.exists("test.csv")
session.ensight.part.select_begin(1,5,7,8,9,10)
session.ensight.part.modify_begin()
session.ensight.part.visible("OFF")
session.ensight.part.modify_end()
session.ensight.part.select_begin(2,3,4,6,11,12,13,14,15)
session.ensight.view_transf.fit(0)
session.ensight.part.select_begin(2,3,4,6,11,12,13,14,15)
session.ensight.part.modify_begin()
session.ensight.part.symmetry_type("mirror")
session.ensight.part.modify_end()
session.ensight.part.select_begin(2,3,4,6,11,12,13,14,15)
session.ensight.part.modify_begin()
session.ensight.part.symmetry_mirror_x("ON")
session.ensight.part.modify_end()
session.ensight.view_transf.fit(0)
session.ensight.view_transf.rotate(16.3245811,44.9999962,0)
session.ensight.view.highlight_parts("OFF")
#
#
# 
session.show("image", width=800, height=600)
gv = session.ensight.utils.variables.get_const_val
#
#  Print out results
#
per_part_pressure_var_list = ['ENS_Force_Net_press_X','ENS_Force_Net_press_Y','ENS_Force_Net_press_Z']
per_part_shear_var_list = ['ENS_Force_Net_Tan_ShearForce_X','ENS_Force_Net_Tan_ShearForce_Y','ENS_Force_Net_Tan_ShearForce_Z']
total_net_pressure_var_list= ['ENS_Force_Total_Net_press_X','ENS_Force_Total_Net_press_Y','ENS_Force_Total_Net_press_Z']
total_net_shear_var_list = ['ENS_Force_Total_Net_Tan_ShearForce_X','ENS_Force_Total_Net_Tan_ShearForce_Y','ENS_Force_Total_Net_Tan_ShearForce_Z']
#
print("Per part force X")
print(body_parts[0], gv(per_part_pressure_var_list[0],body_parts[0]))
print(body_parts[0], gv(per_part_shear_var_list[0],body_parts[0]))
print("Total Force")
print("Total (Net) Pressure Force X = ",gv(total_net_pressure_var_list[0]))
print("Total (Net) Shear Force X = ",gv( total_net_shear_var_list[0]))
session.close()