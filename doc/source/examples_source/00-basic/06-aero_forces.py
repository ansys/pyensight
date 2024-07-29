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

from ansys.pyensight.core import LocalLauncher

session = LocalLauncher().start()

###############################################################################
# Load a dataset
# --------------
# Load RC Plane case included in the https://github.com/ansys/example-data
# repository
#

path = session.download_pyansys_example("RC_Plane", "pyensight", folder=True)
session.load_data(os.path.join(path, "extra300_RC_Plane_cpp.case"))
session.show("image", width=800, height=600)

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
session.ensight.utils.variables.calculator.area(["wing_upper_surface"], output_varname="area_ref")
area_ref = session.ensight.utils.variables.get_const_val("area_ref")

if not area_ref:
    raise RuntimeError("The reference area could not be calculated")


###############################################################################
#  Compute forces on 2D parts
# .. image:: /_static/06_aero_forces_1.png
#

forces = session.ensight.utils.variables.compute_forces(
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

# Hide 3D parts and mirror geometry
session.ensight.part.select_begin(1, 5, 7, 8, 9, 10)
session.ensight.part.modify_begin()
session.ensight.part.visible("OFF")
session.ensight.part.modify_end()
session.ensight.part.select_begin(2, 3, 4, 6, 11, 12, 13, 14, 15)
session.ensight.view_transf.fit(0)
session.ensight.part.select_begin(2, 3, 4, 6, 11, 12, 13, 14, 15)
session.ensight.part.modify_begin()
session.ensight.part.symmetry_type("mirror")
session.ensight.part.modify_end()
session.ensight.part.select_begin(2, 3, 4, 6, 11, 12, 13, 14, 15)
session.ensight.part.modify_begin()
session.ensight.part.symmetry_mirror_x("ON")
session.ensight.part.modify_end()
session.ensight.view_transf.fit(0)
session.ensight.view_transf.rotate(16.3245811, 44.9999962, 0)
session.ensight.view.highlight_parts("OFF")

session.show("image", width=800, height=600)

###############################################################################
#  Print out the computed forces
# ----------------------------------------------------------
# The compute_forces function returns a dictionary that can be easily
# walked to get all the results
#

for idx, axis in enumerate(["X", "Y", "Z"]):
    print(f"Per part force {axis}")
    total_pressure_force = 0
    total_shear_force = 0
    for part in body_parts:
        part_press_force = forces["pressure_forces"][part][idx]
        part_shear_force = forces["shear_forces"][part][idx]
        print(f"Pressure {axis} force on {part} surface: {part_press_force}")
        print(f"Shear {axis} force on {part} surface: {part_shear_force}")
        total_pressure_force += part_press_force
        total_shear_force += part_shear_force
    print(f"Total Force along the {axis} direction")
    print(f"Total (Net) Pressure Force {axis} = {total_pressure_force}")
    print(f"Total (Net) Shear Force {axis} = {total_shear_force}")


###############################################################################
# Thumbnail
# sphinx_gallery_thumbnail_path = '_static/06_aero_forces_1.png'


session.close()
