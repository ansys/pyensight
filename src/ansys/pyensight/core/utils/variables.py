"""Variables module.

This module provides simplified interface to compute specific variables via PyEnSight

"""
import math
import os
from typing import TYPE_CHECKING, Dict, List, Optional, Union

from ansys.api.pyensight.calc_funcs import ens_calculator
from ansys.pyensight.core.utils.parts import convert_variable
import numpy as np

try:
    import ensight
except ImportError:
    pass

if TYPE_CHECKING:
    from ansys.api.pyensight import ensight_api
    from ansys.api.pyensight.ens_part import ENS_PART
    from ansys.api.pyensight.ens_var import ENS_VAR

"""
Compute the vector magnitude of the input vector

Parameters
----------
inval: list
    the vector components

Returns
-------
float
    the value of the vector magnitude. 0.0 if the vector is not a 3D vector

"""


def vec_mag(inval: List[float]) -> float:
    if len(inval) == 3:
        vm = math.sqrt(inval[0] * inval[0] + inval[1] * inval[1] + inval[2] * inval[2])
    else:
        vm = 0.0
    return vm


class Variables:
    """Controls the variables in the current EnSight ``Session`` instance."""

    def __init__(self, ensight: Union["ensight_api.ensight", "ensight"]):
        self.ensight = ensight
        self._calculator = ens_calculator(self.ensight)

    @property
    def calculator(self) -> "ens_calculator":
        """
        The calculator interface presents a Pythonic mechanism to access all the
        EnSight calculator functions: :doc:`Calculator Functions <../calc_functions>`.

        Unlike the native API function :func:`pyensight.ensight_api.variables.evaluate`
        and the object API function :func:`pyensight.ens_globals.ENS_GLOBALS.create_variable`
        which take a string as the function definition, the methods on the calculator
        object take natural Python objects and return any newly created ``ENS_VARIABLE``
        object.

        Returns
        -------
        ens_calculator
            An object supporting a method for each EnSight calculator function.

        Examples
        --------
        The following are equavalent:

        >>> # Native API
        >>> session.ensight.part.select_all()
        >>> session.ensight.variables.evaluate("EleSize = EleSize(plist)")
        >>> var1 = session.ensight.objs.core.VARIABLES["EleSize"][0]
        >>> session.ensight.variables.evaluate("OffsetVar = OffsetVar(plist,Momentum,2e-05)")
        >>> var2 = session.ensight.objs.core.VARIABLES["OffsetVar"][0]
        >>> # Object API
        >>> parts = session.ensight.objs.core.PARTS
        >>> var1 = session.ensight.objs.core.create_variable("EleSize", "EleSize(plist)", sources=parts)
        >>> var2 = session.ensight.objs.core.create_variable("OffsetVar", "OffsetVar(plist,Momentum,2e-05)", sources=parts)
        >>> # ens_calculator API
        >>> parts = session.ensight.objs.core.PARTS
        >>> var1 = session.ensight.utils.variables.calculator.elesize(parts, output_varname="EleSize")
        >>> momentum = session.objs.core.PARTS["Momentum"]
        >>> var2 = session.ensight.utils.variables.calculator.offsetvar(parts, momentum[0], 2.e-5, output_varname="OffsetVar")

        """
        return self._calculator

    def _check_for_var_elem(
        self, var_name: str, pobj_list: List["ENS_PART"]
    ) -> Optional["ENS_VAR"]:
        """
        Check for the existence of a variable whose name is the input
        var_name in the list of available variables. Check also if
        the variable is defined in the input part object list

        Parameters
        ----------
        var_name: str
            the variable name to look for
        pobj_list: list
            the list of parts to see if the variable is defined on them

        Returns
        -------
        ENS_VAR
            the variable found if defined on all the input parts, None otherwise
        """
        vlist = self.ensight.objs.core.VARIABLES.find(var_name)
        if len(vlist) > 0:
            var = vlist[0]
            #  Check to see that selected parts are all
            #   within the list of parts used to calc var
            #   if NOT then return None
            for prt in pobj_list:
                if prt not in var.PARTS:  # pragma: no cover
                    return None  # pragma: no cover
            return var
        return None

    def _move_var_to_elem(
        self, pobj_list: List["ENS_PART"], var_obj: "ENS_VAR"
    ) -> Optional[List["ENS_VAR"]]:
        """
        Check the input variable to see if it is an elemental variable.
        If not, compute the equivalent Nodal variable via the NodeToElem
        EnSight calculator function.

        Parameters
        ----------
        pobj_list: list
            the list of part objects to compute eventually the variable on
        var_obj: ENS_VAR
            the variable object to check

        Returns
        -------
        list
            A list containing either the original variable if already elemental,
            or the computed nodal equivalent variable
        """
        # get the last created var obj to use as a test to see if a new one is created
        last_var_obj = max(self.ensight.objs.core.VARIABLES)
        #
        var_name = var_obj.DESCRIPTION
        calc_var_name = ""
        if self.ensight.objs.enums.ENS_VAR_ELEM != var_obj.LOCATION:
            calc_var_name = "_E"
            ret_val = self._check_for_var_elem(var_name + calc_var_name, pobj_list)
            if not ret_val:
                print("Calculating elemental variable: {} {}".format(var_name, calc_var_name))
                self.ensight.utils.parts.select_parts(pobj_list)
                calc_string = "(plist," + var_name + ")"
                per_node_var = var_name + calc_var_name + " = NodeToElem"
                temp_string = per_node_var + calc_string
                if not self._calc_var(pobj_list, temp_string):  # pragma: no cover
                    raise RuntimeError("Failed to calculate elemental variable")  # pragma: no cover
            else:
                print(
                    "Using elemental variable that already exists: {}".format(ret_val.DESCRIPTION)
                )
                return [ret_val]

        new_var_obj = max(self.ensight.objs.core.VARIABLES)
        if new_var_obj != last_var_obj:  # a new, elemental one was created!
            return [new_var_obj]
        else:  # return the input value as a new one wasn't created
            return [var_obj]

    def _calc_var(
        self, pobj_list: Optional[List["ENS_PART"]] = None, calc_string: Optional[str] = None
    ) -> bool:
        """
        Computes a variable using the input calculator function on
        the input part object list

        Parameters
        ----------
        pobj_list: list
            the list of part objects to compute the variable on
        calc_string: str
            the calculator function to compute

        Returns
        -------
        bool
            True if the computation was successful
        """
        err = -1
        if not pobj_list or not calc_string:
            return False
        if len(calc_string) > 0 and len(pobj_list) > 0:  # pragma: no cover
            self.ensight.utils.parts.select_parts(pobj_list)
            err = self.ensight.variables.evaluate(calc_string)  # ,record=1)
            if err != 0:  # pragma: no cover
                err_string = "Error calculating " + calc_string  # pragma: no cover
                raise RuntimeError(err_string)  # pragma: no cover
        return err == 0

    def _shear_force_xyz_rtz(
        self,
        pobj_list: Optional[List[Union[str, int, "ENS_PART"]]] = None,
        shear_var_obj: Optional[Union[str, int, "ENS_VAR"]] = None,
        shear_or_force_flag: Optional[str] = "Shear stress",
        frame_index: Optional[int] = 0,
    ) -> bool:
        """
        Compute the shear force in the cartesian and cylindrical space.
        It creates (or recreates) several intermediate vars:

        - ENS_Force_Norm

        depending on if the shear variable is Force or Stress:

        - ENS_Force_Dot_prod_Flu_shear_<Force or Stress>_Norm
        - ENS_Force_NomalShear<Force or Stress>

        - ENS_Force_TangentialShear<Force or Stress>

        - ENS_Force_TangentialShear<Force or Stress>_X
        - ENS_Force_TangentialShear<Force or Stress>_Y
        - ENS_Force_TangentialShear<Force or Stress>_Z

        if the variable is shear stress
        - ENS_Force_ElementArea

        And finally the shear force components:
        - ENS_Force_TangentialShearForce_X
        - ENS_Force_TangentialShearForce_Y
        - ENS_Force_TangentialShearForce_Z

        If there is more than one frame and the input frame exists, also the
        cylindrical components are computed, whose names will be:

        - ENS_Force_Tan_ShearForce (which is a vector composed of the above components)
        - ENS_Force_Tan_ShearForce_cyl (which is cylindrical resolved in the frame index coordinate sys)
        and the components of the cylindrical vector:
        - ENS_Force_Tan_ShearForce_R - Radial component
        - ENS_Force_Tan_ShearForce_T - Theta (angular) component
        - ENS_Force_Tan_ShearForce_A - Axial (frame index Z) component

        WARNING: Each time you call this function, it
        overwrites all these EnSight variables.

        WARNING: These variable names are the same
        as the 10.0 Pressure Force Python Tool

        Parameters
        ----------
        pobj_list: list
            The list of part objects to compute the forces on. It can either be a list of names
            a list of IDs (integers or strings) or directly a list of ENS_PART objects
        var_object: ENS_VAR
            The variable object to use as shear variable. If nodal, it will be converted
            into an elemental variable
        shear_or_force_flag: str
            It can either be "Shear stress" or "Shear force" to indicate the kind of shear variable
            supplied
        frame_index: int
            The eventual frame index on which to compute the cylindrical components of the forces

        Returns
        -------
        bool
            True if the computation was successful

        """
        if not frame_index:
            frame_index = 0
        #
        # This pobj_list should contain only 2D parts
        #

        # tricks for mypy
        varid = convert_variable(self.ensight, shear_var_obj)
        _shear_var_obj: "ENS_VAR"
        values = self.ensight.objs.core.VARIABLES.find(varid, "ID")
        ensvar_values: List["ENS_VAR"]
        ensvar_values = [v for v in values]
        _shear_var_obj = ensvar_values[0]

        if not pobj_list:  # pragma: no cover
            raise RuntimeError("Error, no part provided")  # pragma: no cover
        #
        # select all parts in list
        #
        _pobj_list: List["ENS_PART"]
        _pobj_list = self.ensight.utils.parts.select_parts(pobj_list)
        if not _pobj_list:  # pragma: no cover
            return False  # pragma: no cover
        #
        # can be using shear force or shear stress
        #
        if shear_or_force_flag == "Shear stress":  # pragma: no cover
            stemp_string = "Stress"
        else:  # pragma: no cover
            stemp_string = "Force"  # pragma: no cover
        # create a surface normal vector variable using the
        # "Normal" function in the variable calculator.
        #
        temp_string = "ENS_Force_Norm = Normal(plist)"
        if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
            return False  # pragma: no cover
        #
        # makes a new elem var if input var is nodal
        #
        #
        new_shear_var_obj: "ENS_VAR"
        shear_var_name: str
        if _shear_var_obj.LOCATION != self.ensight.objs.enums.ENS_VAR_ELEM:  # pragma: no cover
            # tricks for mypy
            values = self._move_var_to_elem(_pobj_list, _shear_var_obj)
            ensvar_values = [v for v in values]
            new_shear_var_obj = ensvar_values[0]
            shear_var_name = new_shear_var_obj.DESCRIPTION
        else:  # pragma: no cover
            shear_var_name = _shear_var_obj.DESCRIPTION  # pragma: no cover

        #
        # Compute the Dot product of the Vector Normal and the FluidShearVector
        #
        temp_string = (
            "ENS_Force_Dot_prod_Flu_shear_"
            + stemp_string
            + "_Norm = DOT("
            + shear_var_name
            + ",ENS_Force_Norm)"
        )
        if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
            return False  # pragma: no cover

        # multiplying this DOT product by the surface normal vector produces
        # the normal component of the shear stress vector.
        #
        temp_string = (
            "ENS_Force_NomalShear"
            + stemp_string
            + " = ENS_Force_Dot_prod_Flu_shear_"
            + stemp_string
            + "_Norm*ENS_Force_Norm"
        )
        if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
            return False  # pragma: no cover
        #
        # The tangential component is now computed by subtracting this normal
        # component from the shear stress vector, or Vt = V - Vn,
        # where V represents the shear stress vector.
        #
        temp_string = (
            "ENS_Force_TangentialShear"
            + stemp_string
            + " = "
            + shear_var_name
            + "-ENS_Force_NomalShear"
            + stemp_string
        )
        if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
            return False  # pragma: no cover
        #
        # Decompose the TangentialShearStress Vector into its x, y, z component of
        # TangentialShearStress_X, TangentialShearStress_Y, and TangentialShearStress_Z
        temp_string = (
            "ENS_Force_TangentialShear"
            + stemp_string
            + "_X = ENS_Force_TangentialShear"
            + stemp_string
            + "[X]"
        )
        if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
            return False  # pragma: no cover

        temp_string = (
            "ENS_Force_TangentialShear"
            + stemp_string
            + "_Y = ENS_Force_TangentialShear"
            + stemp_string
            + "[Y]"
        )
        if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
            return False  # pragma: no cover

        temp_string = (
            "ENS_Force_TangentialShear"
            + stemp_string
            + "_Z = ENS_Force_TangentialShear"
            + stemp_string
            + "[Z]"
        )
        if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
            return False  # pragma: no cover

        #
        #
        # Calculate the Tangential Shear stress forces by multiplying each of the
        # Components of the Tangential Shear stress with Element Size scalar.
        if shear_or_force_flag == "Shear stress":  # pragma: no cover
            #
            # Calculate the element area Scalar using the "EleSize function in the Variable Calculator
            #
            temp_string = "ENS_Force_ElementArea = EleSize(plist)"
            if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
                return False  # pragma: no cover

            temp_string = (
                "ENS_Force_Tan_ShearForce_X = ENS_Force_TangentialShear"
                + stemp_string
                + "_X*ENS_Force_ElementArea"
            )
            if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
                return False  # pragma: no cover

            temp_string = (
                "ENS_Force_Tan_ShearForce_Y = ENS_Force_TangentialShear"
                + stemp_string
                + "_Y*ENS_Force_ElementArea"
            )
            if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
                return False  # pragma: no cover

            temp_string = (
                "ENS_Force_Tan_ShearForce_Z = ENS_Force_TangentialShear"
                + stemp_string
                + "_Z*ENS_Force_ElementArea"
            )
            if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
                return False  # pragma: no cover

        else:
            temp_string = (  # pragma: no cover
                "ENS_Force_Tan_ShearForce_X = ENS_Force_TangentialShear" + stemp_string + "_X"
            )
            if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
                return False  # pragma: no cover

            temp_string = (  # pragma: no cover
                "ENS_Force_Tan_ShearForce_Y = ENS_Force_TangentialShear" + stemp_string + "_Y"
            )
            if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
                return False  # pragma: no cover

            temp_string = (  # pragma: no cover
                "ENS_Force_Tan_ShearForce_Z = ENS_Force_TangentialShear" + stemp_string + "_Z"
            )
            if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
                return False  # pragma: no cover

        if frame_index > 0 and frame_index < len(self.ensight.objs.core.FRAMES):
            # remake the vector
            temp_string = "ENS_Force_Tan_ShearForce = MakeVect(plist, ENS_Force_Tan_ShearForce_X, ENS_Force_Tan_ShearForce_Y, ENS_Force_Tan_ShearForce_Z)"
            if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
                return False  # pragma: no cover

            # resolve it in cylindrical coords
            temp_string = (
                "ENS_Force_Tan_ShearForce_cyl = RectToCyl(plist,ENS_Force_Tan_ShearForce,"
                + str(frame_index)
                + ")"
            )
            if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
                return False  # pragma: no cover

            # Radial, theta , axial
            temp_string = "ENS_Force_Tan_ShearForce_R  = ENS_Force_Tan_ShearForce_cyl[X]"
            if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
                return False  # pragma: no cover

            temp_string = "ENS_Force_Tan_ShearForce_T  = ENS_Force_Tan_ShearForce_cyl[Y]"
            if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
                return False  # pragma: no cover

            temp_string = "ENS_Force_Tan_ShearForce_A  = ENS_Force_Tan_ShearForce_cyl[Z]"
            if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
                return False  # pragma: no cover
        return True

    def _sum_shear_forces_xyz_rtz(
        self,
        pobj_list: Optional[List[Union[str, int, "ENS_PART"]]] = None,
        frame_index: Optional[int] = 0,
    ) -> Optional[List[List[float]]]:
        """
        Compute the sum of the shear forces on the input part objects list
        and on the eventual frame selected via the StatMoment calculator function in EnSight

        Parameters
        ----------
        pobj_list: list
            The list of part objects to compute the forces on. It can either be a list of names
            a list of IDs (integers or strings) or directly a list of ENS_PART objects
        frame_index: int
            The eventual frame index on which to compute the cylindrical components of the forces

        Returns
        -------
        list
            The list of computed force values. These will be per part constant variables.
            Three if only cartesian, six if also the cylindrical components were computed.
        """
        if not frame_index:
            frame_index = 0
        #
        # This pobj_list should contain only 2D parts
        #
        #
        fcn_name = "sum_shear_forces_xyz_rtz"
        if not pobj_list:  # pragma: no cover
            raise RuntimeError("Error, no part provided")  # pragma: no cover
        #
        # select all parts in list
        #
        self.ensight.utils.parts.select_parts(pobj_list)
        #
        # Sum up each of the Tangential Shear Stress Force Components to get Constants in each
        # of the directions ENS_Force_Net_Tan_Shear_X, ENS_Force_Net_Tan_Shear_Y, ENS_Force_Net_Tan_Shear_X
        #
        #
        temp_string = "ENS_Force_Net_Tan_ShearForce_X = StatMoment(plist,ENS_Force_Tan_ShearForce_X, 0, Compute_Per_part)"
        if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
            err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
            raise RuntimeError(err_string)  # pragma: no cover

        temp_string = "ENS_Force_Net_Tan_ShearForce_Y = StatMoment(plist,ENS_Force_Tan_ShearForce_Y, 0, Compute_Per_part)"
        if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
            err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
            raise RuntimeError(err_string)  # pragma: no cover

        temp_string = "ENS_Force_Net_Tan_ShearForce_Z = StatMoment(plist,ENS_Force_Tan_ShearForce_Z, 0, Compute_Per_part)"
        if not self._calc_var(pobj_list, temp_string):  # pragma: no cover
            err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
            raise RuntimeError(err_string)  # pragma: no cover
        #
        # get the 3 constant force values XYZ
        # 10.1.6(b) use ens_utils, 10.2.0(d) Now gets all the per part constants in a list

        # In this case we know that the value returned by get_const_val will be a List of floats,
        # but mypy doesn't know about it. The next code just makes it happy
        Fx: List[float] = []
        Fy: List[float] = []
        Fz: List[float] = []
        val = self.get_const_val("ENS_Force_Net_Tan_ShearForce_X", pobj_list)
        if not val:  # pragma: no cover
            return None  # pragma: no cover
        if val:
            if isinstance(val, list):
                for v in val:
                    if v is None:  # pragma: no cover
                        return None  # pragma: no cover
                    Fx.append(v)
            else:
                return None
        val = self.get_const_val("ENS_Force_Net_Tan_ShearForce_Y", pobj_list)
        if not val:  # pragma: no cover
            return None  # pragma: no cover
        if val:
            if isinstance(val, list):
                for v in val:
                    if v is None:  # pragma: no cover
                        return None  # pragma: no cover
                    Fy.append(v)
            else:
                return None
        val = self.get_const_val("ENS_Force_Net_Tan_ShearForce_Z", pobj_list)
        if not val:  # pragma: no cover
            return None  # pragma: no cover
        if val:
            if isinstance(val, list):
                for v in val:
                    if v is None:  # pragma: no cover
                        return None  # pragma: no cover
                    Fz.append(v)
            else:
                return None  # pragma: no cover
        #
        # Calculate the Total Shear force X, Y, and Z , 10.2.0(d) now case constant variable
        #  Totals are a case constants. We don't do anything with these vars
        #   they are calc'd to give the user the totals.
        #
        temp_string = "ENS_Force_Total_Net_Tan_ShearForce_X = StatMoment(plist,ENS_Force_Tan_ShearForce_X, 0, Compute_Per_case)"
        if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
            err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
            raise RuntimeError(err_string)  # pragma: no cover

        temp_string = "ENS_Force_Total_Net_Tan_ShearForce_Y = StatMoment(plist,ENS_Force_Tan_ShearForce_Y, 0, Compute_Per_case)"
        if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
            err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
            raise RuntimeError(err_string)  # pragma: no cover

        temp_string = "ENS_Force_Total_Net_Tan_ShearForce_Z = StatMoment(plist,ENS_Force_Tan_ShearForce_Z, 0, Compute_Per_case)"
        if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
            err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
            raise RuntimeError(err_string)  # pragma: no cover

        if frame_index > 0 and frame_index < len(self.ensight.objs.core.FRAMES):
            temp_string = "ENS_Force_Net_Tan_ShearForce_R = StatMoment(plist,ENS_Force_Tan_ShearForce_R,0, Compute_Per_part)"
            if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
                err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
                raise RuntimeError(err_string)  # pragma: no cover

            temp_string = "ENS_Force_Net_Tan_ShearForce_T = StatMoment(plist,ENS_Force_Tan_ShearForce_T,0, Compute_Per_part)"
            if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
                err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
                raise RuntimeError(err_string)  # pragma: no cover

            temp_string = "ENS_Force_Net_Tan_ShearForce_A = StatMoment(plist,ENS_Force_Tan_ShearForce_A,0, Compute_Per_part)"
            if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
                err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
                raise RuntimeError(err_string)  # pragma: no cover
            #
            # Totals
            #
            temp_string = "ENS_Force_Total_Net_Tan_ShearForce_R = StatMoment(plist,ENS_Force_Tan_ShearForce_R,0, Compute_Per_case)"
            if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
                err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
                raise RuntimeError(err_string)  # pragma: no cover

            temp_string = "ENS_Force_Total_Net_Tan_ShearForce_T = StatMoment(plist,ENS_Force_Tan_ShearForce_T,0, Compute_Per_case)"
            if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
                err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
                raise RuntimeError(err_string)  # pragma: no cover

            temp_string = "ENS_Force_Total_Net_Tan_ShearForce_A = StatMoment(plist,ENS_Force_Tan_ShearForce_A,0, Compute_Per_case)"
            if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
                err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
                raise RuntimeError(err_string)  # pragma: no cover
            #
            # get the 3 constant force values Radial, Theta, Axial
            # new use ens_utils 10.1.6(b)

            # we know that the output of get_const_val will be a list of floats,
            # buy mypy doesn't know it. So the next code is just to make it happy

            Fr: List[float] = []
            Ft: List[float] = []
            Fa: List[float] = []
            val = self.get_const_val("ENS_Force_Net_Tan_ShearForce_R", pobj_list)
            if not val:  # pragma: no cover
                return None  # pragma: no cover
            if val:
                if isinstance(val, list):
                    for v in val:
                        if v is None:  # pragma: no cover
                            return None  # pragma: no cover
                        Fr.append(v)
                else:
                    return None  # pragma: no cover
            val = self.get_const_val("ENS_Force_Net_Tan_ShearForce_T", pobj_list)
            if not val:
                return None  # pragma: no cover
            if val:
                if isinstance(val, list):
                    for v in val:
                        if v is None:  # pragma: no cover
                            return None  # pragma: no cover
                        Ft.append(v)
                else:
                    return None
            val = self.get_const_val("ENS_Force_Net_Tan_ShearForce_A", pobj_list)
            if not val:  # pragma: no cover
                return None  # pragma: no cover
            if val:
                if isinstance(val, list):
                    for v in val:
                        if v is None:  # pragma: no cover
                            return None  # pragma: no cover
                        Fa.append(v)
                else:
                    return None  # pragma: no cover
            if all([Fr, Fa, Ft, Fx, Fy, Fz]):
                ret_val = []
                for ii in range(len(pobj_list)):
                    ret_val.append([Fx[ii], Fy[ii], Fz[ii], Fr[ii], Ft[ii], Fa[ii]])
                return ret_val
            else:  # pragma: no cover
                raise RuntimeError(
                    "Error getting ENS_Force_Net_Tan_ShearForce_R, T and/or A"
                )  # pragma: no cover
        else:  # Only one frame or user picked frame 0 (None) for cylindrical frame calc
            if all([Fx, Fy, Fz]):
                ret_val = []
                for ii in range(len(pobj_list)):
                    ret_val.append([Fx[ii], Fy[ii], Fz[ii], 0.0, 0.0, 0.0])
                return ret_val
            else:  # pragma: no cover
                raise RuntimeError(  # pragma: no cover
                    "Error getting Fx, Fy, and/or Fz Shear Net force per part constant values"
                )

    def get_const_vars(self, var_type: Optional[int] = None) -> List["ENS_VAR"]:
        """
        Get all constant OR per part constant variables

        Parameters
        ----------
        var_type: int
            enums.ENS_VAR_CONSTANT (default) if not provided
            or enums.ENS_VAR_CONSTANT_PER_PART

        Returns
        -------
        list
            List containing ENS_VAR objects
        """
        if not var_type:
            var_type = self.ensight.objs.enums.ENS_VAR_CONSTANT
        return [v for v in self.ensight.objs.core.VARIABLES if v.VARTYPE == var_type]

    def get_const_var_names(self, v_type: Optional[int] = None) -> List[str]:
        """
        Get the names of all constant OR per part constant variables

        Parameters
        ----------
        v_type: int
            enums.ENS_VAR_CONSTANT (default) if not provided
            or enums.ENS_VAR_CONSTANT_PER_PART

        Returns
        -------
        list
            List containing names of constants
        """
        if not v_type:
            v_type = self.ensight.objs.enums.ENS_VAR_CONSTANT
        name_list = []
        vars = self.get_const_vars(var_type=v_type)
        for var in vars:
            name_list.append(var.DESCRIPTION)
        return name_list

    def get_const_val(
        self,
        cname: str,
        part_list: Optional[List[Union[str, int, "ENS_PART"]]] = None,
        undef_none=False,
    ) -> Optional[Union[Optional[float], Optional[List[Optional[float]]]]]:
        """
        Return a float value of a variable Case constant at the current timestep,
        or return a list of values one for each part if a per part constant.

        Parameters
        ----------
        cname: str
            the text name of the constant or ENS_VAR object

        part_list: list
            The list of part objects to get the constant values on. It can either be a list of names
            a list of IDs (integers or strings) or directly a list of ENS_PART objects.
            If not provided, all the parts will be considered.

        undef_none: bool
            if False (default) returns undef value (ensight.Undefined) if var
            value is undefined. If False, for undefined values None will be returned

        Returns
        -------
        float or list of float:
            if the variable is a constant, it will either return the constant value, ensight.Undefined or None
            depending on the input.
            If the variable is a constant per part, a list of floats, ensight.Undefined or None will be returned
        """
        if not part_list:
            part_list = self.ensight.objs.core.PARTS
        ens_routine = " 'get_const_val' "
        const_name = ""
        #
        #  error checking
        #
        if isinstance(cname, str):
            if len(cname) > 0:
                const_name = cname
                if const_name in self.get_const_var_names(
                    v_type=self.ensight.objs.enums.ENS_VAR_CONSTANT_PER_PART
                ):
                    const_type = self.ensight.objs.enums.ENS_VAR_CONSTANT_PER_PART
                elif const_name in self.get_const_var_names(
                    v_type=self.ensight.objs.enums.ENS_VAR_CONSTANT
                ):
                    const_type = self.ensight.objs.enums.ENS_VAR_CONSTANT
                else:  # pragma: no cover
                    raise RuntimeError(  # pragma: no cover
                        "Error, {} Constant name {} is not a constant nor a per part constant".format(
                            ens_routine, const_name
                        )
                    )
            else:  # pragma: no cover
                raise RuntimeError(  # pragma: no cover
                    "Error, {} must supply a valid constant variable name ".format(ens_routine)
                )
        elif isinstance(cname, self.ensight.objs.ENS_VAR):
            const_name = cname.DESCRIPTION
            const_type = cname.VARTYPEENUM
            if (  # pragma: no cover
                const_type != self.ensight.objs.enums.ENS_VAR_CONSTANT
                and const_type != self.ensight.objs.enums.ENS_VAR_CONSTANT_PER_PART
            ):
                raise RuntimeError(  # pragma: no cover
                    "Error, Variable {} is not a constant nor a per part constant".format(cname)
                )
        else:  # pragma: no cover
            raise RuntimeError(
                "Error, 'get_const_val' Constant name is neither string nor ENS_VAR"
            )  # pragma: no cover
        #
        #
        #  Now get it
        #
        self.ensight.variables.activate(const_name)  # bug fixed 10.1.6(c)

        if const_type == self.ensight.objs.enums.ENS_VAR_CONSTANT_PER_PART:  # new in 10.2
            if not part_list:  # pragma: no cover
                part_list = self.ensight.objs.core.PARTS  # pragma: no cover

            plist = self.ensight.utils.parts.get_part_id_obj_name(part_list, "obj")
            ret_val: List[Optional[float]] = []
            #
            for prt in plist:
                if isinstance(prt, self.ensight.objs.ENS_PART):
                    val_dict = prt.get_values([const_name])
                    if val_dict:  # pragma: no cover
                        val = float(val_dict[const_name][0])
                        if undef_none and np.isclose(
                            val, self.ensight.Undefined, rtol=1e-6, atol=1e-16
                        ):
                            ret_val.append(None)  # pragma: no cover
                        else:
                            ret_val.append(val)
                else:  # pragma: no cover
                    raise RuntimeError(  # pragma: no cover
                        "Error {} part list must contain a list of only ENS_PARTs".format(
                            ens_routine
                        )
                    )
            return ret_val
        # the legacy way using the interface manual ch 6
        (val, type_val, scope_val) = self.ensight.ensvariable(const_name)

        # type = 0 if the value is an integer, 1 if the value is a float and 2 if the value is a string
        # scope =  -1 if it is a constant computed in EnSight, and
        #             scope will be >= 0 if a command language global
        #             (0 if command language global and >0 if local to a file or loop)
        if scope_val == -1 and type_val == 1:  # EnSight constant and float
            if undef_none and np.isclose(
                val, self.ensight.Undefined, rtol=1e-6, atol=1e-16
            ):  # pragma: no cover
                return None  # pragma: no cover
            else:
                return val
        else:  # pragma: no cover
            raise RuntimeError(  # pragma: no cover
                "Error, {} return value from ensight.ensvariable indicates it is not a float from an Ensight Constant".format(
                    ens_routine
                )
            )

    #
    #
    # IN:
    #  part object list
    #  var_object -     Must be an elemental variable
    #  frame_index -    if > 0 and frame exists, use that frame to calc cylindrical forces
    # OUT:
    #
    #    Creates (or recreates)
    #    several intermediate vars:
    #    ENS_Force_press
    #    ENS_Force_press_X
    #    ENS_Force_press_Y
    #    ENS_Force_press_Z
    #    if frame index > 0 and less than the number of frames,
    #       ENS_Force_press_cyl is the conversion of ENS_Force_press to cylindrical coords
    #       ENS_Force_press_R - Radial component of the pressure force in frame index
    #       ENS_Force_press_T - Angular (theta)  component of the pressure force in frame index
    #       ENS_Force_press_A - Axial (z component of chosen frame) of the pressure force
    #
    #   WARNING: Each time you call this function, it
    #     overwrites all these EnSight variables.
    #
    #   WARNING: These variable names are the same
    #      as the 10.0 Pressure Force Python Tool
    #
    #    Return: True if success
    #            False if error
    #
    def _press_force_xyz_rtz(
        self,
        pobj_list: Optional[List[Union[str, int, "ENS_PART"]]] = None,
        press_var_obj: Optional["ENS_VAR"] = None,
        frame_index: Optional[int] = 0,
    ) -> bool:
        """
        Compute the pressure force in the cartesian and cylindrical space.
        It creates (or recreates) several intermediate vars:

        - ENS_Force_press
        - ENS_Force_press_X
        - ENS_Force_press_Y
        - ENS_Force_press_Z
        if frame index > 0 and the frame exists:
        - ENS_Force_press_cyl is the conversion of ENS_Force_press to cylindrical coords
        - ENS_Force_press_R - Radial component of the pressure force in frame index
        - ENS_Force_press_T - Angular (theta)  component of the pressure force in frame index
        - ENS_Force_press_A - Axial (z component of chosen frame) of the pressure force

        WARNING: Each time you call this function, it
        overwrites all these EnSight variables.


        Parameters
        ----------
        pobj_list: list
            The list of part objects to compute the forces on. It can either be a list of names
            a list of IDs (integers or strings) or directly a list of ENS_PART objects
        press_var_obj: ENS_VAR
            The variable object to use as pressure variable. If nodal, it will be converted
            into an elemental variable
        frame_index: int
            The eventual frame index on which to compute the cylindrical components of the forces

        Returns
        -------
        bool
            True if the computation was successful

        """
        #
        # This pobj_list should contain only 2D parts
        #
        if not frame_index:
            frame_index = 0
        varid = convert_variable(self.ensight, press_var_obj)
        _press_var_obj: "ENS_VAR"
        values = self.ensight.objs.core.VARIABLES.find(varid, "ID")
        ensvar_values: List["ENS_VAR"]
        ensvar_values = [v for v in values]
        _press_var_obj = ensvar_values[0]
        if not pobj_list:  # pragma: no cover
            raise RuntimeError("Error, no part provided")  # pragma: no cover
        #
        # select all parts in list
        #
        _pobj_list: List["ENS_PART"]
        _pobj_list = self.ensight.utils.parts.select_parts(pobj_list)
        if not _pobj_list:  # pragma: no cover
            return False  # pragma: no cover
        #
        # makes a new elem var if input var is nodal
        #
        new_pres_var_obj: "ENS_VAR"
        press_var_name: str
        if _press_var_obj.LOCATION != self.ensight.objs.enums.ENS_VAR_ELEM:  # pragma: no cover
            # tricks for mypy
            values = self._move_var_to_elem(_pobj_list, _press_var_obj)
            ensvar_values = [v for v in values]
            new_pres_var_obj = ensvar_values[0]
            press_var_name = new_pres_var_obj.DESCRIPTION
        else:
            press_var_name = _press_var_obj.DESCRIPTION  # pragma: no cover

        #
        # Calculate the Force vector
        #
        calc_string = "(plist," + press_var_name + ")"
        force_calc_string = "ENS_Force_press = Force"
        temp_string = force_calc_string + calc_string
        if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
            raise RuntimeError("Error calculating: '" + temp_string + "'")  # pragma: no cover

        temp_string = "ENS_Force_press_X = ENS_Force_press[X]"
        if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
            raise RuntimeError("Error calculating: '" + temp_string + "'")  # pragma: no cover

        temp_string = "ENS_Force_press_Y = ENS_Force_press[Y]"
        if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
            raise RuntimeError("Error calculating: '" + temp_string + "'")  # pragma: no cover

        temp_string = "ENS_Force_press_Z = ENS_Force_press[Z]"
        if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
            raise RuntimeError("Error calculating: '" + temp_string + "'")  # pragma: no cover
        #
        #  RTZ Cylindrical force
        #
        if frame_index > 0 and frame_index < len(self.ensight.objs.core.FRAMES):
            temp_string = (
                "ENS_Force_press_cyl = RectToCyl(plist,ENS_Force_press," + str(frame_index) + ")"
            )
            if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
                raise RuntimeError("Error calculating: '" + temp_string + "'")  # pragma: no cover

            temp_string = "ENS_Force_press_R = ENS_Force_press_cyl[X]"
            if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
                raise RuntimeError("Error calculating: '" + temp_string + "'")  # pragma: no cover

            temp_string = "ENS_Force_press_T  = ENS_Force_press_cyl[Y]"
            if not self._calc_var(pobj_list, temp_string):  # pragma: no cover
                raise RuntimeError("Error calculating: '" + temp_string + "'")  # pragma: no cover

            temp_string = "ENS_Force_press_A  = ENS_Force_press_cyl[Z]"
            if not self._calc_var(_pobj_list, temp_string):  # pragma: no cover
                raise RuntimeError("Error calculating: '" + temp_string + "'")  # pragma: no cover
        return True

    def _sum_pressure_forces_xyz_rtz(
        self,
        pobj_list: Optional[List[Union[str, int, "ENS_PART"]]] = None,
        frame_index: Optional[int] = 0,
    ) -> Optional[List[List[float]]]:
        """
        Compute the sum of the pressure forces on the input part objects list
        and on the eventual frame selected via the StatMoment calculator function in EnSight

        Parameters
        ----------
        pobj_list: list
            The list of part objects to compute the forces on. It can either be a list of names
            a list of IDs (integers or strings) or directly a list of ENS_PART objects
        frame_index: int
            The eventual frame index on which to compute the cylindrical components of the forces

        Returns
        -------
        list
            The list of computed force values. These will be per part constant variables.
            Three if only cartesian, six if also the cylindrical components were computed.
        """
        #
        # This pobj_list should contain only 2D parts
        #
        if not frame_index:
            frame_index = 0
        if not pobj_list:  # pragma: no cover
            raise RuntimeError("Error, no part provided")  # pragma: no cover
        #
        # Select the part(s) in the list
        # ensight.variables.evaluate("ENS_Force_Net_press_Y = StatMoment(plist,pressure,0,Compute_Per_part)")
        fcn_name = "sum_press_forces_xyz_rtz"
        self.ensight.utils.parts.select_parts(pobj_list)
        #
        # Calculate the net force X, Y, and Z , 10.2.0(d) now per part constant variable
        #
        force_calc_string = "ENS_Force_Net_press_X = StatMoment"
        calc_string = "(plist," + "ENS_Force_press_X , 0, Compute_Per_part )"
        temp_string = force_calc_string + calc_string
        if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
            err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
            raise RuntimeError(err_string)  # pragma: no cover
        #
        force_calc_string = "ENS_Force_Net_press_Y = StatMoment"
        calc_string = "(plist," + "ENS_Force_press_Y , 0, Compute_Per_part )"
        temp_string = force_calc_string + calc_string
        if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
            err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
            raise RuntimeError(err_string)  # pragma: no cover
        #
        force_calc_string = "ENS_Force_Net_press_Z = StatMoment"
        calc_string = "(plist," + "ENS_Force_press_Z , 0, Compute_Per_part )"
        temp_string = force_calc_string + calc_string
        if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
            err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
            raise RuntimeError(err_string)  # pragma: no cover
        #
        # Calculate the Total force X, Y, and Z , 10.2.0(d) now case constant variable
        #  Totals are a case constants. We don't do anything with these vars
        #   they are calc'd to give the user the totals.
        #
        force_calc_string = "ENS_Force_Total_Net_press_X = StatMoment"
        calc_string = "(plist," + "ENS_Force_press_X , 0, Compute_Per_case )"
        temp_string = force_calc_string + calc_string
        if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
            err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
            raise RuntimeError(err_string)  # pragma: no cover
        #
        force_calc_string = "ENS_Force_Total_Net_press_Y = StatMoment"
        calc_string = "(plist," + "ENS_Force_press_Y , 0, Compute_Per_case )"
        temp_string = force_calc_string + calc_string
        if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
            err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
            raise RuntimeError(err_string)  # pragma: no cover
        #
        force_calc_string = "ENS_Force_Total_Net_press_Z = StatMoment"
        calc_string = "(plist," + "ENS_Force_press_Z , 0, Compute_Per_case )"
        temp_string = force_calc_string + calc_string
        if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
            err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
            raise RuntimeError(err_string)  # pragma: no cover
        #
        # get a list with a per part force, one for each part, new 10.1.6(b)
        #

        Fx: List[float] = []
        Fy: List[float] = []
        Fz: List[float] = []
        val = self.get_const_val("ENS_Force_Net_press_X", pobj_list)
        if not val:  # pragma: no cover
            return None  # pragma: no cover
        if val:
            if isinstance(val, list):
                for v in val:
                    if v is None:  # pragma: no cover
                        return None  # pragma: no cover
                    Fx.append(v)
            else:
                return None  # pragma: no cover
        val = self.get_const_val("ENS_Force_Net_press_Y", pobj_list)
        if not val:  # pragma: no cover
            return None  # pragma: no cover
        if val:
            if isinstance(val, list):
                for v in val:
                    if v is None:  # pragma: no cover
                        return None  # pragma: no cover
                    Fy.append(v)
            else:
                return None  # pragma: no cover
        val = self.get_const_val("ENS_Force_Net_press_Z", pobj_list)
        if not val:  # pragma: no cover
            return None  # pragma: no cover
        if val:
            if isinstance(val, list):
                for v in val:
                    if v is None:  # pragma: no cover
                        return None  # pragma: no cover
                    Fz.append(v)
            else:
                return None  # pragma: no cover
        #
        #
        # Fr, Ft, Fa
        #
        if frame_index > 0 and frame_index < len(
            self.ensight.objs.core.FRAMES
        ):  # user picked non-zero frame index
            #
            self.ensight.utils.parts.select_parts(pobj_list)
            #
            #  per part constant as of 10.2.0(d)
            #
            force_calc_string = "ENS_Force_Net_press_R = StatMoment"
            calc_string = "(plist," + "ENS_Force_press_R, 0, Compute_Per_part )"
            temp_string = force_calc_string + calc_string
            if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
                err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
                raise RuntimeError(err_string)  # pragma: no cover
            #
            force_calc_string = "ENS_Force_Net_press_T = StatMoment"
            calc_string = "(plist," + "ENS_Force_press_T, 0, Compute_Per_part )"
            temp_string = force_calc_string + calc_string
            if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
                err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
                raise RuntimeError(err_string)  # pragma: no cover
            #
            force_calc_string = "ENS_Force_Net_press_A = StatMoment"
            calc_string = "(plist," + "ENS_Force_press_A, 0, Compute_Per_part )"
            temp_string = force_calc_string + calc_string
            if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
                err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
                raise RuntimeError(err_string)  # pragma: no cover
            #
            #  Totals are a case constants. We don't do anything with these vars
            #   they are calc'd to give the user the totals.
            #
            force_calc_string = "ENS_Force_Total_Net_press_R = StatMoment"
            calc_string = "(plist," + "ENS_Force_press_R, 0, Compute_Per_case )"
            temp_string = force_calc_string + calc_string
            if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
                err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
                raise RuntimeError(err_string)  # pragma: no cover
            #
            force_calc_string = "ENS_Force_Total_Net_press_T = StatMoment"
            calc_string = "(plist," + "ENS_Force_press_T, 0, Compute_Per_case )"
            temp_string = force_calc_string + calc_string
            if self._calc_var(pobj_list, temp_string) is False:  # pragma: no cover
                err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
                raise RuntimeError(err_string)  # pragma: no cover
            #
            force_calc_string = "ENS_Force_Total_Net_press_A = StatMoment"
            calc_string = "(plist," + "ENS_Force_press_A, 0, Compute_Per_case )"
            temp_string = force_calc_string + calc_string
            if not self._calc_var(pobj_list, temp_string):  # pragma: no cover
                err_string = f"Error, failed to calculate {temp_string} in {fcn_name}"  # pragma: no cover  # pragma: no cover  # pragma: no cover
                raise RuntimeError(err_string)  # pragma: no cover
            #
            #   get a list with a per part force, one for each part, new 10.1.6(b)
            #
            Fr: List[float] = []
            Ft: List[float] = []
            Fa: List[float] = []
            val = self.get_const_val("ENS_Force_Net_press_R", pobj_list)
            if not val:  # pragma: no cover
                return None  # pragma: no cover
            if val:
                if isinstance(val, list):
                    for v in val:
                        if v is None:  # pragma: no cover
                            return None  # pragma: no cover
                        Fr.append(v)
                else:
                    return None  # pragma: no cover
            val = self.get_const_val("ENS_Force_Net_press_T", pobj_list)
            if not val:  # pragma: no cover
                return None  # pragma: no cover
            if val:
                if isinstance(val, list):
                    for v in val:
                        if v is None:  # pragma: no cover
                            return None  # pragma: no cover
                        Ft.append(v)
                else:
                    return None  # pragma: no cover
            val = self.get_const_val("ENS_Force_Net_press_A", pobj_list)
            if not val:  # pragma: no cover
                return None  # pragma: no cover
            if val:
                if isinstance(val, list):
                    for v in val:
                        if v is None:  # pragma: no cover
                            return None  # pragma: no cover
                        Fa.append(v)
                else:
                    return None  # pragma: no cover
            #
            if all([Fr, Ft, Fz, Fx, Fy, Fz]):
                ret_val = []
                for ii in range(len(pobj_list)):
                    ret_val.append([Fx[ii], Fy[ii], Fz[ii], Fr[ii], Ft[ii], Fa[ii]])
                return ret_val
            else:
                err_string = "Error getting XYZ and/or Cylindrical RTZ Pressure Net Force per part constant values"  # pragma: no cover
                raise RuntimeError(err_string)  # pragma: no cover
        else:  # either only one Frame or Frame 0 has been chosen so no cylindrical calc
            if all([Fx, Fy, Fz]):
                ret_val = []
                for ii in range(len(pobj_list)):
                    ret_val.append([Fx[ii], Fy[ii], Fz[ii], 0.0, 0.0, 0.0])
                return ret_val
            else:  # pragma: no cover
                err_string = "Error getting Fx, Fy, and/or Fz Pressure Net force per part constant values"  # pragma: no cover  # pragma: no cover
                raise RuntimeError(err_string)  # pragma: no cover

    def _write_out_force_data(
        self,
        filename: str,
        original_part_selection_list: List["ENS_PART"],
        params: Dict[str, str],
        press_force_list: Optional[List[List[float]]] = None,
        shear_force_list: Optional[List[List[float]]] = None,
        press_coeff_list: Optional[List[List[float]]] = None,
        shear_coeff_list: Optional[List[List[float]]] = None,
        press_LDS_force_list: Optional[List[List[float]]] = None,
        shear_LDS_force_list: Optional[List[List[float]]] = None,
        press_LDS_coeff_list: Optional[List[List[float]]] = None,
        shear_LDS_coeff_list: Optional[List[List[float]]] = None,
    ) -> bool:
        """
        Write the computed forces in a file split part by part

        Parameters
        ----------
        filename: str
            the file on which to write the force data
        params: dict
            A dictionary containing the settings for the file. It can contain:
            press_varname: the name of the pressure variable
            shear_varname: the name of the shear variable
            shear_vartype: the type of shear variable
            Area_ref: the reference area for the force coefficients computation
            Dens_ref: the reference density for the force coefficients computation
            Vx_ref: the X velocity reference for the force coefficients computation
            Vy_ref: the Y velocity reference for the force coefficients computation
            Vz_ref: the Z velocity reference for the force coefficients computation
            up_vector: the "Up vector" used for the force components computation
            frame_index: the index of the frame used for the cylindrical components computation
        press_force_list: list
            the list of pressure forces to write
        shear_force_list: list
            the list of shear forces to write
        press_coeff_list:
            the list of pressure force coefficients to write
        shear_coeff_list:
            the list of shear force coefficients to write
        press_LDS_force_list:
            the list of pressure Lift, Drag, Side force components to write
        shear_LDS_force_list:
            the list of shear Lift, Drag, Side force components to write
        press_LDS_coeff_list:
            the list of pressure Lift, Drag, Side force coefficients components to write
        shear_LDS_coeff_list:
            the list of pressure Lift, Drag, Side force coefficients components to write

        Returns
        -------
        bool
            True if the export was successful
        """
        frames = (
            self.ensight.objs.core.FRAMES is not None
            and len(self.ensight.objs.core.FRAMES) > 0
            and "frame_index" in params
            and int(params["frame_index"]) > 0
        )
        shear = (
            "shear_varname" in params
            and params["shear_varname"] != "None"
            and params["shear_vartype"] != "None"
        )
        if (
            press_force_list
        ):  # FIX ME what if we have no pressure force list but do have shear force list???
            try:
                with open(filename, "w") as fp:
                    temp_list = [0.0, 0.0, 0.0]
                    #
                    #  get the input data filename from the server and write the filename for the current case
                    #
                    c = self.ensight.objs.core.CURRENTCASE[
                        0
                    ]  # for c in ensight.objs.core.CASES.find(True, attr=ensight.objs.enums.ACTIVE):
                    fp.write("'" + os.path.join(c.SERVERDIR, c.SERVERINFO.get("file", "")) + "'\n")
                    #
                    #  Write the gui input values to the .csv output file as  a second
                    #   line in the header
                    #
                    fp.write("Pressure variable name ," + params["press_varname"] + "\n")
                    if frames:
                        fp.write(
                            "Cylindrical reference frame coordinate system frame, "
                            + str(params["frame_index"])
                            + "\n"
                        )
                    if shear:
                        fp.write("Shear variable name ," + params["shear_varname"] + ", " + "\n")
                        fp.write("Shear variable type ," + params["shear_vartype"] + "\n")
                    if (
                        params.get("Area_ref")
                        and params.get("Dens_ref")
                        and params.get("Vx_ref")
                        and params.get("Vy_ref")
                        and params.get("Vz_ref")
                    ):
                        if float(params["Area_ref"]) > 0.0:
                            fp.write("Reference Area, %.5f \n" % float(params["Area_ref"]))
                            fp.write("Reference Density, %.5f \n" % float(params["Dens_ref"]))
                            fp.write("Reference Velocity xyz, %.5f," % float(params["Vx_ref"]))
                            fp.write("%.5f, " % float(params["Vy_ref"]))
                            fp.write("%.5f  \n" % float(params["Vz_ref"]))
                            if params.get("up_vector"):
                                if params["up_vector"] != "None":
                                    fp.write("Up vector," + params["up_vector"] + "\n")
                        fp.write("\n")
                    fp.write(
                        "Part ID,   Part Name , Pressure Force X , Pressure Force Y , Pressure Force Z , Total Pressure Force "
                    )
                    if frames:
                        fp.write(
                            ", Pressure Force Radial , Pressure Force Theta , Pressure Force Axial, Total Cyl Pressure Force "
                        )
                    if shear_force_list:  # pragma: no cover
                        fp.write(
                            ", Shear Force X , Shear Force Y , Shear Force Z , Total Shear Force "
                        )
                        if frames:
                            fp.write(
                                ", Shear Force Radial , Shear Force Theta , Shear Force Axial , Total Cyl Shear Force "
                            )
                        fp.write(
                            ", Press + Shear Force X , Press + Shear Force Y , Press + Shear Force Z , Total Press + Shear Force "
                        )
                        if frames:
                            fp.write(
                                ", Press + Shear Force Radial , Press + Shear Force Theta , Press + Shear Force Axial , Total Press + Shear Force "
                            )
                    if press_coeff_list:  # pragma: no cover
                        fp.write(
                            ", Coeff Press X , Coeff Press Y , Coeff Press Z , Total Coeff Press "
                        )
                        if frames:
                            fp.write(
                                ", Coeff Press Radial , Coeff Press Theta , Coeff Press Axial , Total Coeff Press "
                            )
                    if shear_coeff_list:  # pragma: no cover
                        fp.write(
                            ", Coeff Shear X , Coeff Shear Y , Coeff Shear Z , Total Coeff Shear ,"
                        )
                        if frames:
                            fp.write(
                                "Coeff Shear Radial , Coeff Shear Theta , Coeff Shear Axial , Total Coeff Shear ,"
                            )
                        fp.write(
                            "Coeff Press + Shear X , Coeff Press + Shear Y , Coeff Press + Shear Z , Total Coeff Press + Shear"
                        )
                        if frames:
                            fp.write(
                                ", Coeff Press + Shear Radial , Coeff Press + Shear Theta , Coeff Press + Shear Axial , Total Coeff Press + Shear"
                            )
                    if press_LDS_force_list:  # pragma: no cover
                        fp.write(", Lift Force , Drag Force , Side Force , Total Pressure Force ")
                    if shear_LDS_force_list:  # pragma: no cover
                        fp.write(
                            ", Shear Force L , Shear Force D , Shear Force Side , Total Shear Force LDS "
                        )
                        fp.write(
                            ", Press + Shear Force L , Press + Shear Force D , Press + Shear Force Side , Total Press + Shear Force LDS "
                        )
                    if press_LDS_coeff_list:  # pragma: no cover
                        fp.write(
                            ", Lift Coeff Press  , Drag Coeff Press , Side Coeff Press , Total Coeff Press "
                        )
                    if shear_LDS_coeff_list:  # pragma: no cover
                        fp.write(
                            ", Lift Coeff Shear  , Drag Coeff Shear , Side Coeff Shear , Coeff Shear LDS Total,"
                        )
                        fp.write(
                            "Coeff Press + Shear L , Coeff Press + Shear D , Coeff Press + Shear Side , Coeff Press + Shear LDS Total"
                        )
                    fp.write("\n")
                    #
                    #  Loop through and write out the vals
                    #
                    for ii in range(len(press_force_list)):
                        fp.write(
                            str(original_part_selection_list[ii].PARTNUMBER)
                            + " , "
                            + original_part_selection_list[ii].DESCRIPTION
                            + " , "
                        )
                        #
                        # pressure force components then magnitude
                        #
                        for jj in range(3):
                            fp.write(str(press_force_list[ii][jj]))
                            fp.write(" , ")
                        fp.write(str(vec_mag(press_force_list[ii][:3])))  # magnitude of Fx, Fy, Fz
                        if frames:
                            fp.write(" , ")
                            for jj in range(3):
                                fp.write(str(press_force_list[ii][jj + 3]))
                                fp.write(" , ")
                            fp.write(
                                str(vec_mag(press_force_list[ii][3:]))
                            )  # magnitude of Cyl Fr, Ft, Fa
                        #
                        # shear force components then magnitude
                        #
                        if shear_force_list:  # pragma: no cover
                            fp.write(" , ")
                            for jj in range(3):
                                fp.write(str(shear_force_list[ii][jj]))
                                fp.write(" , ")
                            fp.write(str(vec_mag(shear_force_list[ii][:3])))
                            if frames:
                                fp.write(" , ")
                                for jj in range(3):
                                    fp.write(str(shear_force_list[ii][jj + 3]))
                                    fp.write(" , ")
                                fp.write(str(vec_mag(shear_force_list[ii][3:])))
                            fp.write(" , ")
                            # sum of pressure and shear forces components then magnitude
                            for jj in range(3):
                                temp_list[jj] = press_force_list[ii][jj] + shear_force_list[ii][jj]
                                fp.write(str(temp_list[jj]))
                                fp.write(" , ")
                            fp.write(str(vec_mag(temp_list[:3])))
                            if frames:
                                fp.write(" , ")
                                for jj in range(3):
                                    temp_list[jj] = (
                                        press_force_list[ii][jj + 3] + shear_force_list[ii][jj + 3]
                                    )
                                    fp.write(str(temp_list[jj]))
                                    fp.write(" , ")
                                fp.write(str(vec_mag(temp_list[:3])))

                        #
                        # Coefficient of pressure force components then magnitude
                        #
                        if press_coeff_list:  # pragma: no cover
                            fp.write(" , ")
                            for jj in range(3):
                                fp.write(str(press_coeff_list[ii][jj]))
                                fp.write(" , ")
                            fp.write(str(vec_mag(press_coeff_list[ii][:3])))
                            if frames:
                                fp.write(" , ")
                                for jj in range(3):
                                    fp.write(str(press_coeff_list[ii][jj + 3]))
                                    fp.write(" , ")
                                fp.write(str(vec_mag(press_coeff_list[ii][3:])))
                        #
                        # Coefficient shear force components then magnitude
                        #
                        if (
                            shear_coeff_list is not None and press_coeff_list is not None
                        ):  # pragma: no cover
                            if (
                                len(shear_coeff_list) > 0 and len(press_coeff_list) > 0
                            ):  # pragma: no cover
                                fp.write(" , ")
                                for jj in range(3):
                                    fp.write(str(shear_coeff_list[ii][jj]))
                                    fp.write(" , ")
                                fp.write(str(vec_mag(shear_coeff_list[ii][:3])))
                                fp.write(" , ")
                                if frames:
                                    for jj in range(3):
                                        fp.write(str(shear_coeff_list[ii][jj + 3]))
                                        fp.write(" , ")
                                    fp.write(str(vec_mag(shear_coeff_list[ii][3:])))
                                    fp.write(" , ")
                                # sum of pressure and shear Coefficient components then magnitude
                                for jj in range(3):
                                    temp_list[jj] = (
                                        press_coeff_list[ii][jj] + shear_coeff_list[ii][jj]
                                    )
                                    fp.write(str(temp_list[jj]))
                                    fp.write(" , ")
                                fp.write(str(vec_mag(temp_list)))
                                if frames:
                                    fp.write(" , ")
                                    for jj in range(3):
                                        temp_list[jj] = (
                                            press_coeff_list[ii][jj + 3]
                                            + shear_coeff_list[ii][jj + 3]
                                        )
                                        fp.write(str(temp_list[jj]))
                                        fp.write(" , ")
                                    fp.write(str(vec_mag(temp_list)))
                                fp.write(" , ")
                        #
                        # Lift, Drag and Side Force
                        # No cylindrical stuff here
                        # LDS pressure force components then magnitude
                        #
                        if press_LDS_force_list:  # pragma: no cover
                            for jj in range(3):
                                fp.write(str(press_LDS_force_list[ii][jj]))
                                fp.write(" , ")
                            fp.write(str(vec_mag(press_LDS_force_list[ii][:3])))
                            fp.write(" , ")
                        # LDS shear force components then magnitude
                        if (
                            shear_LDS_force_list is not None and press_LDS_force_list is not None
                        ):  # pragma: no cover
                            if (
                                len(shear_LDS_force_list) > 0 and len(press_LDS_force_list) > 0
                            ):  # pragma: no cover
                                for jj in range(3):
                                    fp.write(str(shear_LDS_force_list[ii][jj]))
                                    fp.write(" , ")
                                fp.write(str(vec_mag(shear_LDS_force_list[ii][:3])))
                                fp.write(" , ")
                                # LDS sum of pressure and shear forces components then magnitude
                                for jj in range(3):
                                    temp_list[jj] = (
                                        press_LDS_force_list[ii][jj] + shear_LDS_force_list[ii][jj]
                                    )
                                    fp.write(str(temp_list[jj]))
                                    fp.write(" , ")
                                fp.write(str(vec_mag(temp_list)))
                                fp.write(" , ")
                            # LDS Coefficient of pressure force components then magnitude
                            if press_LDS_coeff_list:  # pragma: no cover
                                for jj in range(3):
                                    fp.write(str(press_LDS_coeff_list[ii][jj]))
                                    fp.write(" , ")
                                fp.write(str(vec_mag(press_LDS_coeff_list[ii][:3])))
                                fp.write(" , ")
                            # LDS Coefficient shear force components then magnitude
                            if (  # pragma: no cover
                                shear_LDS_coeff_list is not None
                                and press_LDS_coeff_list is not None
                            ):
                                if (
                                    len(shear_LDS_coeff_list) > 0 and len(press_LDS_coeff_list) > 0
                                ):  # pragma: no cover
                                    for jj in range(3):
                                        fp.write(str(shear_LDS_coeff_list[ii][jj]))
                                        fp.write(" , ")
                                    fp.write(str(vec_mag(shear_LDS_coeff_list[ii][:3])))
                                    fp.write(" , ")
                                    # LDS sum of pressure and shear Coefficient components then magnitude
                                    for jj in range(3):
                                        temp_list[jj] = (
                                            press_LDS_coeff_list[ii][jj]
                                            + shear_LDS_coeff_list[ii][jj]
                                        )
                                        fp.write(str(temp_list[jj]))
                                        fp.write(" , ")
                                    fp.write(str(vec_mag(temp_list)))
                                fp.write("\n")
                    #  FIX ME keep track of and write out totals here when loop is done on last line?
                    fp.close()
                    return True
            except IOError:  # pragma: no cover
                raise RuntimeError(  # pragma: no cover
                    "Error Failed to open output csv filename for writing '" + filename + "'"
                )
        raise RuntimeError("Error no pressure force list to write out")  # pragma: no cover

    @staticmethod
    def _force_coeffs(
        Forces: List[float], area_ref: float, vel_ref: float, dens_ref: float
    ) -> List[float]:
        """Compute the force coefficients for the input list of forces

        Parameters
        ----------

        Forces: list
            A list of force values to compute the coefficients for
        area_ref: float
            the reference area value for the coefficients computation
        vel_ref: float
            the reference velocity magnitude value for the coefficients computation
        dens_ref: float
            the reference velocity magnitude value for the coefficients computation

        Returns
        -------
        list
            The list of force coefficients computed
        """
        coeffs = []
        qS = area_ref * vel_ref * vel_ref * dens_ref / 2.0
        if qS > 0:  # pragma: no cover
            for ff in Forces:
                coeffs.append(ff / qS)
        else:
            coeffs = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # pragma: no cover
        return coeffs

    @staticmethod
    def _get_up_vec(up_str: str) -> np.array:  # pragma: no cover
        """
        Convert the up_vector string to the actual components

        Parameters
        ----------
        up_str: str
            the up_vector string

        Returns
        -------
        numpy.array
            The up vector components as a numpy array
        """
        if up_str == "+X":
            up_vec = [1.0, 0.0, 0.0]
        elif up_str == "+Y":
            up_vec = [0.0, 1.0, 0.0]
        elif up_str == "+Z":
            up_vec = [0.0, 0.0, 1.0]
        elif up_str == "-X":
            up_vec = [-1.0, 0.0, 0.0]
        elif up_str == "-Y":
            up_vec = [0.0, -1.0, 0.0]
        elif up_str == "-Z":
            up_vec = [0.0, 0.0, -1.0]
        else:  # pragma: no cover
            raise RuntimeError(  # pragma: no cover
                f"Up vector {up_str} not allowed. It can only be +X, +Y, +Z, -X, -Y, -Z."
            )
        return np.array(up_vec)

    @staticmethod
    def _lds_forces(
        f_np_vec: np.array, lift_vec: np.array, drag_vec: np.array, side_vec: np.array
    ) -> List[float]:
        """
        Compute the lift, drag and side force components for the input vector of forces

        Parameters
        ----------
        f_np_vec: numpy.array
            the numpy array representing the force vector in the X,Y,Z directions of the model
        lift_vec: numpy.array
            a numpy array representing the lift direction in the X,Y,Z space
        drag_vec: numpy.array
            a numpy array representing the drag direction in the X,Y,Z space
        side_vec: numpy.array
            a numpy array representing the side force direction in the X,Y,Z space

        Returns
        -------
        list:
            the computed lift, drag and side force component values
        """
        lf = np.dot(f_np_vec[:3], lift_vec)
        df = np.dot(f_np_vec[:3], drag_vec)
        sf = np.dot(f_np_vec[:3], side_vec)
        return [lf, df, sf]

    SHEAR_VAR_TYPE_STRESS = 0
    SHEAR_VAR_TYPE_FORCE = 1
    UP_VECTOR_PLUS_X = "+X"
    UP_VECTOR_PLUS_Y = "+Y"
    UP_VECTOR_PLUS_Z = "+Z"
    UP_VECTOR_MINUS_X = "-X"
    UP_VECTOR_MINUS_Y = "-Y"
    UP_VECTOR_MINUS_Z = "-Z"

    def compute_forces(
        self,
        pobj_list: Optional[List[Union[str, int, "ENS_PART"]]] = None,
        press_var_obj: Optional[Union["ENS_VAR", str, int]] = None,
        shear_var_obj: Optional[Union["ENS_VAR", str, int]] = None,
        shear_var_type: Optional[int] = None,
        area_ref: Optional[float] = None,
        density_ref: Optional[float] = None,
        velocity_x_ref: Optional[float] = None,
        velocity_y_ref: Optional[float] = None,
        velocity_z_ref: Optional[float] = None,
        up_vector: Optional[str] = None,
        export_filename: Optional[str] = None,
        frame_index: Optional[int] = 0,
    ) -> Optional[Dict[str, Dict[str, List[float]]]]:
        """
        Compute the force values for the current model.
        During the force computation process, several intermediate EnSight variables are computed.
        These can always be retrieved for later use.
        If area_ref, density_ref, velocity_x_ref, velocity_y_ref and velocity_z_ref are supplied,
        also the normalized forces will be computed.
        If velocity_x_ref, velocity_y_ref, velocity_z_ref and up_vector are supplied, also the
        lift, drag and side components of the force will be computed. Eventually, also the normalized
        lift, drag and side force components are computed if also area_ref and density_ref are supplied.
        The forces are returned in a dictionary, which will split the force values in pressure, shear, normalized pressure,
        normalized shear, lds pressure, lds shear, normalized lds pressure and normalized lds shear components,
        populated depending on the input (lds stands for lift, drag and side components). They can optionatally be
        saved into a .csv file, which will also report the total values for each group.

        Parameters
        ----------
        pobj_list: list
            The list of part objects to compute the forces on. It can either be a list of names
            a list of IDs (integers or strings) or directly a list of ENS_PART objects.
            The list must contain 2D surfaces.
        press_var_obj: str, ENS_VAR or int
            The variable to use for the pressure force computation. It can be supplied as variable name,
            variable ID or ENS_VAR object. It must be a scalar.
        shear_var_obj: str, ENS_VAR or int
            The variable to use for the shear force computation. It can be supplied as variable name,
            variable ID or ENS_VAR object. It must be a vector.
        shear_var_type: int
            The kind of shear variable supplied. It can be:

            ===================== ========================================================
            Name                  Shear variable type
            ===================== ========================================================
            SHEAR_VAR_TYPE_STRESS The variable represents the shear stresses distribution
            SHEAR_VAR_TYPE_FORCE  The variable represents the shear forces distribution
            ===================== ========================================================

            If not supplied, it will be defaulted to SHEAR_VAR_TYPE_STRESS
        area_ref: float
            the area reference value for the force coefficients computation
        density_ref: float
            the area reference value for the force coefficients computation
        velocity_x_ref: float
            the X velocity reference component. Needed For the coefficients computation and/or the
            lift/drag/side components computation. The X direction is the X direction for the model.
        velocity_y_ref: float
            the Y velocity reference component. Needed For the coefficients computation and/or the
            lift/drag/side components computation. The Y direction is the Y direction for the model.
        velocity_z_ref: float
            the Z velocity reference component. Needed For the coefficients computation and/or the
            lift/drag/side components computation. The Z direction is the Z direction for the model.
        up_vector: str
            Define the "up vector" for the lift/drag/side decomposition. It can be:
            ================== =================
            Name               Up vector value
            ================== =================
            UP_VECTOR_PLUS_X   +X
            UP_VECTOR_PLUS_Y   +Y
            UP_VECTOR_PLUS_Z   +Z
            UP_VECTOR_MINUS_X  -X
            UP_VECTOR_MINUS_Y  -Y
            UP_VECTOR_MINUS_Z  -Z
            ================== =================

            If not provided, it will default to +Z
        export_filename: str
            The filename for the export file. If not provided, not file will be exported.
            The file will be exported relative to the PyEnSight session, not to the EnSight session.
        frame_index: int
            The eventual frame index on which to compute the cylindrical components of the forces.
            If not provided, the cylindrical components won't be computed.

        Returns
        -------
        dict:
            A dictionary containing all the forces computed, split by force kind and part name
        """
        if not frame_index:
            frame_index = 0
        if not shear_var_type:  # pragma: no cover
            shear_var_type = self.SHEAR_VAR_TYPE_STRESS
        shear_map = {
            self.SHEAR_VAR_TYPE_STRESS: "Shear stress",
            self.SHEAR_VAR_TYPE_FORCE: "Shear force",
        }
        if not up_vector:  # pragma: no cover
            up_vector = self.UP_VECTOR_PLUS_Z  # pragma: no cover
        _pobj_list = self.ensight.utils.parts.select_parts(pobj_list)
        computed_press_forces: List[List[float]] = []
        computed_shear_forces: List[List[float]] = []
        computed_press_force_coeffs: List[List[float]] = []
        computed_shear_force_coeffs: List[List[float]] = []
        computed_press_forces_lds: List[List[float]] = []
        computed_shear_forces_lds: List[List[float]] = []
        computed_press_forces_lds_coeffs: List[List[float]] = []
        computed_shear_forces_lds_coeffs: List[List[float]] = []
        if press_var_obj:  # pragma: no cover
            success = self._press_force_xyz_rtz(
                pobj_list=pobj_list, press_var_obj=press_var_obj, frame_index=frame_index
            )
            if not success:  # pragma: no cover
                return None  # pragma: no cover
            temp = self._sum_pressure_forces_xyz_rtz(pobj_list=pobj_list, frame_index=frame_index)
            if not temp:  # pragma: no cover
                return None  # pragma: no cover
            computed_press_forces = temp.copy()
        if shear_var_obj:
            success = self._shear_force_xyz_rtz(
                pobj_list=pobj_list,
                shear_var_obj=shear_var_obj,
                shear_or_force_flag=shear_map.get(shear_var_type),
                frame_index=frame_index,
            )
            if not success:
                return None
            temp = self._sum_shear_forces_xyz_rtz(pobj_list=pobj_list, frame_index=frame_index)
            if not temp:
                return None
            computed_shear_forces = temp.copy()
        coeffs_computation = all(
            [
                x is not None
                for x in [area_ref, velocity_x_ref, velocity_y_ref, velocity_z_ref, density_ref]
            ]
        )
        # Just making mypy happy
        if (  # pragma: no cover
            coeffs_computation
            and velocity_x_ref is not None
            and velocity_y_ref is not None
            and velocity_z_ref is not None
            and area_ref is not None
            and density_ref is not None
        ):
            _vec_mag = vec_mag([velocity_x_ref, velocity_y_ref, velocity_z_ref])
            # We need to compute the force coeffs
            if computed_press_forces:  # pragma: no cover
                for part_force in computed_press_forces:
                    computed_press_force_coeffs.append(
                        self._force_coeffs(part_force, area_ref, _vec_mag, density_ref)
                    )
            if computed_shear_forces:  # pragma: no cover
                for part_force in computed_shear_forces:
                    computed_shear_force_coeffs.append(
                        self._force_coeffs(part_force, area_ref, _vec_mag, density_ref)
                    )
        lds = all(
            [x is not None for x in [up_vector, velocity_x_ref, velocity_y_ref, velocity_z_ref]]
        )
        if lds:  # pragma: no cover
            temp_np_vec = np.array([velocity_x_ref, velocity_y_ref, velocity_z_ref])
            drag_vec = temp_np_vec / np.sqrt(np.dot(temp_np_vec, temp_np_vec))
            up_vec = self._get_up_vec(up_vector)
            temp_np_vec = np.cross(drag_vec, up_vec)
            side_vec = temp_np_vec / np.sqrt(np.dot(temp_np_vec, temp_np_vec))
            # Lift vec normalized
            temp_np_vec = np.cross(side_vec, drag_vec)
            lift_vec = temp_np_vec / np.sqrt(np.dot(temp_np_vec, temp_np_vec))
            if computed_press_forces:  # pragma: no cover
                for part_force in computed_press_forces:
                    computed_press_forces_lds.append(
                        self._lds_forces(np.array(part_force), lift_vec, drag_vec, side_vec)
                    )
            if computed_shear_forces:  # pragma: no cover
                for part_force in computed_shear_forces:
                    computed_shear_forces_lds.append(
                        self._lds_forces(np.array(part_force), lift_vec, drag_vec, side_vec)
                    )
            if coeffs_computation:  # pragma: no cover
                if computed_press_force_coeffs:  # pragma: no cover
                    for part_force in computed_press_force_coeffs:
                        computed_press_forces_lds_coeffs.append(
                            self._lds_forces(np.array(part_force), lift_vec, drag_vec, side_vec)
                        )
                if computed_shear_force_coeffs:  # pragma: no cover
                    for part_force in computed_shear_force_coeffs:
                        computed_shear_forces_lds_coeffs.append(
                            self._lds_forces(np.array(part_force), lift_vec, drag_vec, side_vec)
                        )
        if export_filename is not None and pobj_list is not None:  # pragma: no cover
            if len(pobj_list) > 0:  # pragma: no cover
                press_varname = None
                shear_varname = None
                if press_var_obj:  # pragma: no cover
                    _press_var_id = convert_variable(self.ensight, press_var_obj)
                    if _press_var_id:  # pragma: no cover
                        press_varnames = [
                            v for v in self.ensight.objs.core.VARIABLES if v.ID == _press_var_id
                        ]
                        if press_varnames:
                            press_varname = str(press_varnames[0].DESCRIPTION)
                if shear_var_obj:  # pragma: no cover
                    _shear_var_id = convert_variable(self.ensight, shear_var_obj)
                    if _shear_var_id:  # pragma: no cover
                        shear_varnames = [
                            v for v in self.ensight.objs.core.VARIABLES if v.ID == _press_var_id
                        ]
                        if shear_varnames:  # pragma: no cover
                            shear_varname = str(shear_varnames[0].DESCRIPTION)
                params = {}
                if press_varname:  # pragma: no cover
                    params["press_varname"] = press_varname
                if shear_varname:  # pragma: no cover
                    params["shear_varname"] = shear_varname
                if shear_var_type is not None:  # pragma: no cover
                    value = shear_map.get(shear_var_type)
                    if value:  # pragma: no cover
                        params["shear_vartype"] = value
                if area_ref is not None:  # pragma: no cover
                    params["Area_ref"] = str(area_ref)
                if density_ref is not None:  # pragma: no cover
                    params["Dens_ref"] = str(density_ref)
                if velocity_x_ref is not None:  # pragma: no cover
                    params["Vx_ref"] = str(velocity_x_ref)
                if velocity_y_ref is not None:  # pragma: no cover
                    params["Vy_ref"] = str(velocity_y_ref)
                if velocity_z_ref is not None:  # pragma: no cover
                    params["Vz_ref"] = str(velocity_z_ref)
                if up_vector is not None:  # pragma: no cover
                    params["up_vector"] = up_vector
                if frame_index > 0:
                    params["frame_index"] = str(frame_index)

                self._write_out_force_data(
                    export_filename,
                    _pobj_list,
                    params=params,
                    press_force_list=computed_press_forces,
                    shear_force_list=computed_shear_forces,
                    press_coeff_list=computed_press_force_coeffs,
                    shear_coeff_list=computed_shear_force_coeffs,
                    press_LDS_force_list=computed_press_forces_lds,
                    shear_LDS_force_list=computed_shear_forces_lds,
                    press_LDS_coeff_list=computed_press_forces_lds_coeffs,
                    shear_LDS_coeff_list=computed_shear_forces_lds_coeffs,
                )
        return {
            "pressure_forces": {
                p.DESCRIPTION: computed_press_forces[idx]
                for idx, p in enumerate(_pobj_list)
                if idx < len(computed_press_forces)
            },
            "shear_forces": {
                p.DESCRIPTION: computed_shear_forces[idx]
                for idx, p in enumerate(_pobj_list)
                if idx < len(computed_shear_forces)
            },
            "normalized_pressure_forces": {
                p.DESCRIPTION: computed_press_force_coeffs[idx]
                for idx, p in enumerate(_pobj_list)
                if idx < len(computed_press_force_coeffs)
            },
            "normalized_shear_forces": {
                p.DESCRIPTION: computed_shear_force_coeffs[idx]
                for idx, p in enumerate(_pobj_list)
                if idx < len(computed_shear_force_coeffs)
            },
            "pressure_forces_lds_direction": {
                p.DESCRIPTION: computed_press_forces_lds[idx]
                for idx, p in enumerate(_pobj_list)
                if idx < len(computed_press_forces_lds)
            },
            "shear_forces_lds_direction": {
                p.DESCRIPTION: computed_shear_forces_lds[idx]
                for idx, p in enumerate(_pobj_list)
                if idx < len(computed_shear_forces_lds)
            },
            "normalized_pressure_forces_lds_direction": {
                p.DESCRIPTION: computed_press_forces_lds_coeffs[idx]
                for idx, p in enumerate(_pobj_list)
                if idx < len(computed_press_forces_lds_coeffs)
            },
            "normalized_shear_forces_lds_direction": {
                p.DESCRIPTION: computed_shear_forces_lds[idx]
                for idx, p in enumerate(_pobj_list)
                if idx < len(computed_shear_forces_lds_coeffs)
            },
        }
