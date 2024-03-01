"""Variables module.

This module provides simplified interface to compute specific variables via PyEnSight

"""
import numpy as np
import os
import math
from typing import TYPE_CHECKING, Union

try:
    import ensight
    from ensight.objs import ens_emitterobj, ensobjlist  # type: ignore
except ImportError:
    from ansys.api.pyensight.ens_emitterobj import ens_emitterobj
    from ansys.pyensight.core.listobj import ensobjlist

if TYPE_CHECKING:
    from ansys.api.pyensight.ens_var import ENS_VAR
    from ansys.api.pyensight import ensight_api

#
#  finds float value vector magnitude
#
def vec_mag(inval):
    if len(inval) == 3:
        vm = math.sqrt(inval[0]*inval[0] + inval[1]*inval[1] + inval[2]*inval[2])
    else:
        vm = 0.0
    return vm

class Variables:
    
    def __init__(self, ensight: Union["ensight_api.ensight", "ensight"]):
        self.ensight = ensight

#  Checks for the existence of var_name
#   in the list of variables
#
#   FIX ME for many variables speed up!
#
    def _check_for_var_elem(self, var_name, pobj_list):
        vlist = self.ensight.core.VARIABLES.find(var_name)
        if len(vlist) > 0:
            var = vlist[0]
            #  Check to see that selected parts are all
            #   within the list of parts used to calc var
            #   if NOT then return None
            for prt in pobj_list:
                if prt not in var.PARTS:
                    return None
            return var
        return None
    
#
# IN: var_obj
# OUT: calcs elemental from nodal variable and 
#        returns list containing var object or empty list if err.
#        Does nothing and returns input var name
#        if already elemental.
#
#   elemental_var_list = move_var_to_elem( original_part_selection_list, shear_var_list[0])
#
#   Return a list containing the variable object or [ ] if failure 
#
    def _move_var_to_elem(self, pobj_list, var_obj):
        # get the last created var obj to use as a test to see if a new one is created
        last_var_obj = max(self.ensight.core.VARIABLES)
        #
        var_name = var_obj.DESCRIPTION
        calc_var_name = ""
        if self.ensight.objs.enums.ENS_VAR_ELEM != var_obj.LOCATION:
            calc_var_name = "_E"
            ret_val = self._check_for_var_elem(var_name+calc_var_name, pobj_list)
            if ret_val == None:
                print("Calculating elemental variable: {} {}".format(var_name, calc_var_name))
                self.ensight.utils.parts.select_parts(pobj_list) 
                calc_string = "(plist," + var_name + ')'
                per_node_var = var_name + calc_var_name + " = NodeToElem"
                temp_string = per_node_var + calc_string
                if 0 != self._calc_var(pobj_list, temp_string):
                    self.ensight.int_message("Failed to calculate elemental variable",1)
                    return []
            else:
                print("Using elemental variable that already exists: {}".format(ret_val.DESCRIPTION))
                return [ret_val]

        new_var_obj = max(self.ensight.objs.core.VARIABLES)
        if new_var_obj != last_var_obj: # a new, elemental one was created!
            return [new_var_obj]
        else: # return the input value as a new one wasn't created
            return [var_obj]
        
    #
#  Calculates a variable
#   using calc_string in ensight
#
#  Returns 0 if successful
#         non-zero if fail
#
    def _calc_var(self, pobj_list=[],calc_string=""):
        err = -1
        if len(calc_string) > 0 and len(pobj_list)>0:
            self.ensight.utils.parts.select_parts(pobj_list)
            err = self.ensight.variables.evaluate(calc_string) #,record=1)
            if err != 0:
                err_string = "Error calculating " + calc_string
                self.ensight.int_message(err_string,1)
        return err

#
#
# IN:
#  part object list - A list of ENS_PARTs
#  var_object -     Must be an elemental variable
#  shear_or_force_flag = "Shear stress" or "Shear force" depending on the shear variable
#                        This is obtained from the gui params['shear_vartype']
#  frame_index - if > 0 then use this frame to calculate cylindrical components in this
#                        frame
#
# OUT:
#
#    Creates (or recreates) several intermediate vars:
#
#    ENS_Force_Norm
#
#    depending on if the shear variable is Force or Stress:
#    ENS_Force_Dot_prod_Flu_shear_<Force or Stress>_Norm 
#    ENS_Force_NomalShear<Force or Stress>
#
#    ENS_Force_TangentialShear<Force or Stress>
#
#    ENS_Force_TangentialShear<Force or Stress>_X
#    ENS_Force_TangentialShear<Force or Stress>_Y
#    ENS_Force_TangentialShear<Force or Stress>_Z
#
#    if the variable is shear stress
#       ENS_Force_ElementArea
#
#    And finally the shear force components:
#     ENS_Force_TangentialShearForce_X
#     ENS_Force_TangentialShearForce_Y
#     ENS_Force_TangentialShearForce_Z
#
#    Now, new in 10.1.6(c), RTZ if more than one frame and chosen frame index exists
#     ENS_Force_Tan_ShearForce (which is a vector composed of the above components)
#     ENS_Force_Tan_ShearForce_cyl (which is cylindrical resolved in the frame index coordinate sys)
#     and the components of the cylindrical vector:
#      ENS_Force_Tan_ShearForce_R - Radial component
#      ENS_Force_Tan_ShearForce_T - Theta (angular) component
#      ENS_Force_Tan_ShearForce_A - Axial (frame index Z) component
#
#   WARNING: Each time you call this function, it
#     overwrites all these EnSight variables.
#
#   WARNING: These variable names are the same
#      as the 10.0 Pressure Force Python Tool
#
    def _shear_force_xyz_rtz(self, pobj_list, shear_var_obj, shear_or_force_flag = "Shear stress", frame_index = 0):
        #  
        # This pobj_list should contain only 2D parts
        #
        if len(pobj_list) < 1:
            self.ensight.int_message("Error, no part provided",1)
            return False
        #
        # select all parts in list
        #
        self.ensight.utils.parts.select_parts(pobj_list)
        #
        # can be using shear force or shear stress
        #
        if shear_or_force_flag == "Shear stress":
            stemp_string = "Stress"
        else:
            stemp_string = "Force"
        # create a surface normal vector variable using the 
        # "Normal" function in the variable calculator.
        #
        temp_string = "ENS_Force_Norm = Normal(plist)"
        if 0 != self._calc_var(pobj_list,temp_string):
            return False
        #
        # makes a new elem var if input var is nodal
        #
        #
        if shear_var_obj.LOCATION == self.ensight.objs.enums.ENS_VAR_ELEM:
            shear_var_name = shear_var_obj.DESCRIPTION
        else:
            err_string = "Error shear_force_xyz_rtz: variable {} is not an elemental variable".format(shear_var_obj.DESCRIPTION)
            self.ensight.int_message(err_string,1)
            return False
        
        #
        # Compute the Dot product of the Vector Normal and the FluidShearVector
        #
        temp_string = "ENS_Force_Dot_prod_Flu_shear_"+ stemp_string +"_Norm = DOT(" + shear_var_name + ",ENS_Force_Norm)"
        if 0 != self._calc_var(pobj_list,temp_string):
            return False
        
        # multiplying this DOT product by the surface normal vector produces 
        # the normal component of the shear stress vector.
        #
        temp_string = "ENS_Force_NomalShear"+ stemp_string +" = ENS_Force_Dot_prod_Flu_shear_"+ stemp_string +"_Norm*ENS_Force_Norm"
        if 0 != self._calc_var(pobj_list,temp_string):
            return False
        #
        # The tangential component is now computed by subtracting this normal 
        # component from the shear stress vector, or Vt = V - Vn, 
        # where V represents the shear stress vector. 
        #
        temp_string = "ENS_Force_TangentialShear" + stemp_string + " = " + shear_var_name + "-ENS_Force_NomalShear"+ stemp_string
        if 0 != self._calc_var(pobj_list,temp_string):
            return False
        #
        # Decompose the TangentialShearStress Vector into its x, y, z component of 
        # TangentialShearStress_X, TangentialShearStress_Y, and TangentialShearStress_Z
        temp_string = "ENS_Force_TangentialShear"+ stemp_string +"_X = ENS_Force_TangentialShear"+ stemp_string +"[X]"
        if 0 != self._calc_var(pobj_list,temp_string):
            return False
        
        temp_string = "ENS_Force_TangentialShear"+ stemp_string +"_Y = ENS_Force_TangentialShear"+ stemp_string +"[Y]"
        if 0 != self._calc_var(pobj_list,temp_string):
            return False
        
        temp_string = "ENS_Force_TangentialShear"+ stemp_string +"_Z = ENS_Force_TangentialShear"+ stemp_string +"[Z]"
        if 0 != self._calc_var(pobj_list,temp_string):
            return False
        
        #
        #
        # Calculate the Tangential Shear stress forces by multiplying each of the 
        # Components of the Tangential Shear stress with Element Size scalar.
        if shear_or_force_flag == "Shear stress":
            #
            # Calculate the element area Scalar using the "EleSize function in the Variable Calculator
            #
            temp_string = "ENS_Force_ElementArea = EleSize(plist)"
            if 0 != self._calc_var(pobj_list,temp_string):
                return False
            
            temp_string = "ENS_Force_Tan_ShearForce_X = ENS_Force_TangentialShear"+ stemp_string +"_X*ENS_Force_ElementArea"
            if 0 != self._calc_var(pobj_list,temp_string):
                return False
            
            temp_string = "ENS_Force_Tan_ShearForce_Y = ENS_Force_TangentialShear"+ stemp_string +"_Y*ENS_Force_ElementArea"
            if 0 != self._calc_var(pobj_list,temp_string):
                return False
            
            temp_string = "ENS_Force_Tan_ShearForce_Z = ENS_Force_TangentialShear"+ stemp_string +"_Z*ENS_Force_ElementArea"
            if 0 != self._calc_var(pobj_list,temp_string):
                return False
            
        else:
            temp_string = "ENS_Force_Tan_ShearForce_X = ENS_Force_TangentialShear"+ stemp_string +"_X"
            if 0 != self._calc_var(pobj_list,temp_string):
                return False
        
            temp_string = "ENS_Force_Tan_ShearForce_Y = ENS_Force_TangentialShear"+ stemp_string +"_Y"
            if 0 != self._calc_var(pobj_list,temp_string):
                return False
        
            temp_string = "ENS_Force_Tan_ShearForce_Z = ENS_Force_TangentialShear"+ stemp_string +"_Z"
            if 0 != self._calc_var(pobj_list,temp_string):
                return False
        
        if frame_index > 0 and frame_index < len(self.ensight.objs.core.FRAMES):
            # remake the vector
            temp_string = "ENS_Force_Tan_ShearForce = MakeVect(plist, ENS_Force_Tan_ShearForce_X, ENS_Force_Tan_ShearForce_Y, ENS_Force_Tan_ShearForce_Z)"
            if 0 != self._calc_var(pobj_list,temp_string):
                return False
            
            # resolve it in cylindrical coords
            temp_string = "ENS_Force_Tan_ShearForce_cyl = RectToCyl(plist,ENS_Force_Tan_ShearForce,"+str(frame_index)+")"
            if 0 != self._calc_var(pobj_list,temp_string):
                return False
            
            # Radial, theta , axial
            temp_string = "ENS_Force_Tan_ShearForce_R  = ENS_Force_Tan_ShearForce_cyl[X]"
            if 0 != self._calc_var(pobj_list,temp_string):  # radial force
                return False
        
            temp_string = "ENS_Force_Tan_ShearForce_T  = ENS_Force_Tan_ShearForce_cyl[Y]"
            if 0 != self._calc_var(pobj_list,temp_string): # angular force
                return False
        
            temp_string = "ENS_Force_Tan_ShearForce_A  = ENS_Force_Tan_ShearForce_cyl[Z]"
            if 0 != self._calc_var(pobj_list,temp_string): # axial force        
                return False
        return True

    #
    #  Uses the stat moment calc function to sum the shear forces for this list of parts
    #   resulting in a per part constant and a case constant as of 10.2.0(d) for each force component
    #   IN:
    #     pobj_list - A list of ENS_PART(s)
    #
    #     frame_index = If 0 then do not calc RTZ cylindrical net forces
    #                 otherwise calculate the net forces in Radial, Theta, and Axial
    #    
    #    OUT
    #    calculates the net shear force per part constant using all parts
    #     in the list and creates three or six per part constants:
    #      ENS_Force_Net_Tan_Shear_X, ENS_Force_Net_Tan_Shear_Y, ENS_Force_Net_Tan_Shear_Z
    #
    #    Now, new in 10.1.6(c), RTZ if more than one frame and chosen frame index exists
    #     if frame_index > 0, then calc net force using the cylindrical forces in the
    #     frame_index reference system adn in 10.2.0(d) three are per part constants
    #
    #       ENS_Force_Net_Tan_ShearForce_R - net shear force in the radial direction
    #       ENS_Force_Net_Tan_ShearForce_T - net shear force in the angular (theta) direction
    #       ENS_Force_Net_Tan_ShearForce_A - net shear force in the axial (frame index Z) direction
    #
    #    Returns:
    #       if frame_index > 0 and frame exists then returns forces for each part in the list:
    #          ( [ENS_Force_Net_Tan_Shear_X, ENS_Force_Net_Tan_Shear_Y, ENS_Force_Net_Tan_Shear_Z,  ENS_Force_Net_Tan_ShearForce_R, ENS_Force_Net_Tan_ShearForce_T, ENS_Force_Net_Tan_ShearForce_A  ]  ,
    #            [ENS_Force_Net_Tan_Shear_X, ENS_Force_Net_Tan_Shear_Y, ENS_Force_Net_Tan_Shear_Z , ENS_Force_Net_Tan_ShearForce_R, ENS_Force_Net_Tan_ShearForce_T, ENS_Force_Net_Tan_ShearForce_A  ]  ,
    #            [ENS_Force_Net_Tan_Shear_X, ENS_Force_Net_Tan_Shear_Y, ENS_Force_Net_Tan_Shear_Z, ENS_Force_Net_Tan_ShearForce_R, ENS_Force_Net_Tan_ShearForce_T, ENS_Force_Net_Tan_ShearForce_A  ]  , ...)
    #       else:
    #          ( [ENS_Force_Net_Tan_Shear_X, ENS_Force_Net_Tan_Shear_Y, ENS_Force_Net_Tan_Shear_Z , 0.0  , 0.0  , 0.0  ]  ,
    #          ( [ENS_Force_Net_Tan_Shear_X, ENS_Force_Net_Tan_Shear_Y, ENS_Force_Net_Tan_Shear_Z , 0.0  , 0.0  , 0.0  ]  ,
    #          ( [ENS_Force_Net_Tan_Shear_X, ENS_Force_Net_Tan_Shear_Y, ENS_Force_Net_Tan_Shear_Z , 0.0  , 0.0  , 0.0  ]  , ...)
    #       ERROR:
    #              [ ] empty list if error calculating vars or getting constant values
    #
    def _sum_shear_forces_xyz_rtz(self, pobj_list, frame_index = -1):
        #  
        # This pobj_list should contain only 2D parts
        #
        #
        fcn_name = "sum_shear_forces_xyz_rtz"
        if len(pobj_list) < 1:
            self.ensight.int_message("Error, no part provided",1)
            return []
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
        if 0 != self._calc_var(pobj_list,temp_string):
            err_string = "Error, failed to calculate a variable in {}".format(fcn_name)
            ensight.int_message(err_string,1)
            return []
        
        temp_string = "ENS_Force_Net_Tan_ShearForce_Y = StatMoment(plist,ENS_Force_Tan_ShearForce_Y, 0, Compute_Per_part)"
        if 0 != self._calc_var(pobj_list,temp_string):
            err_string = "Error, failed to calculate a variable in {}".format(fcn_name)
            self.ensight.int_message(err_string,1)
            return []
    
        temp_string = "ENS_Force_Net_Tan_ShearForce_Z = StatMoment(plist,ENS_Force_Tan_ShearForce_Z, 0, Compute_Per_part)"
        if 0 != self._calc_var(pobj_list,temp_string):
            err_string = "Error, failed to calculate a variable in {}".format(fcn_name)
            self.ensight.int_message(err_string,1)
            return []
        #
        # get the 3 constant force values XYZ
        # 10.1.6(b) use ens_utils, 10.2.0(d) Now gets all the per part constants in a list
        Fx = self.get_const_val("ENS_Force_Net_Tan_ShearForce_X",pobj_list)
        Fy = self.get_const_val("ENS_Force_Net_Tan_ShearForce_Y",pobj_list)
        Fz = self.get_const_val("ENS_Force_Net_Tan_ShearForce_Z",pobj_list)
        #
        # Calculate the Total Shear force X, Y, and Z , 10.2.0(d) now case constant variable
        #  Totals are a case constants. We don't do anything with these vars
        #   they are calc'd to give the user the totals.
        #
        temp_string = "ENS_Force_Total_Net_Tan_ShearForce_X = StatMoment(plist,ENS_Force_Tan_ShearForce_X, 0, Compute_Per_case)"
        if 0 != self._calc_var(pobj_list,temp_string):
            err_string = "Error, failed to calculate a variable in {}".format(fcn_name)
            self.ensight.int_message(err_string,1)
            return []
        
        temp_string = "ENS_Force_Total_Net_Tan_ShearForce_Y = StatMoment(plist,ENS_Force_Tan_ShearForce_Y, 0, Compute_Per_case)"
        if 0 != self._calc_var(pobj_list,temp_string):
            err_string = "Error, failed to calculate a variable in {}".format(fcn_name)
            self.ensight.int_message(err_string,1)
            return []
    
        temp_string = "ENS_Force_Total_Net_Tan_ShearForce_Z = StatMoment(plist,ENS_Force_Tan_ShearForce_Z, 0, Compute_Per_case)"
        if 0 != self._calc_var(pobj_list,temp_string):
            err_string = "Error, failed to calculate a variable in {}".format(fcn_name)
            self.ensight.int_message(err_string,1)
            return []
        #
        #   
        #
        if frame_index > 0 and frame_index < len(self.ensight.objs.core.FRAMES):
            temp_string = "ENS_Force_Net_Tan_ShearForce_R = StatMoment(plist,ENS_Force_Tan_ShearForce_R,0, Compute_Per_part)"
            if 0 != self._calc_var(pobj_list,temp_string):
                err_string = "Error, failed to calculate a variable in {}".format(fcn_name)
                self.ensight.int_message(err_string,1)
                return []
    
            temp_string = "ENS_Force_Net_Tan_ShearForce_T = StatMoment(plist,ENS_Force_Tan_ShearForce_T,0, Compute_Per_part)"
            if 0 != self._calc_var(pobj_list,temp_string):
                err_string = "Error, failed to calculate a variable in {}".format(fcn_name)
                self.ensight.int_message(err_string,1)
                return []
    
            temp_string = "ENS_Force_Net_Tan_ShearForce_A = StatMoment(plist,ENS_Force_Tan_ShearForce_A,0, Compute_Per_part)"
            if 0 != self._calc_var(pobj_list,temp_string):
                err_string = "Error, failed to calculate a variable in {}".format(fcn_name)
                self.ensight.int_message(err_string,1)
                return []
            #
            # Totals
            #
            temp_string = "ENS_Force_Total_Net_Tan_ShearForce_R = StatMoment(plist,ENS_Force_Tan_ShearForce_R,0, Compute_Per_case)"
            if 0 != self._calc_var(pobj_list,temp_string):
                err_string = "Error, failed to calculate a variable in {}".format(fcn_name)
                self.ensight.int_message(err_string,1)
                return []
    
            temp_string = "ENS_Force_Total_Net_Tan_ShearForce_T = StatMoment(plist,ENS_Force_Tan_ShearForce_T,0, Compute_Per_case)"
            if 0 != self._calc_var(pobj_list,temp_string):
                err_string = "Error, failed to calculate a variable in {}".format(fcn_name)
                self.ensight.int_message(err_string,1)
                return []
    
            temp_string = "ENS_Force_Total_Net_Tan_ShearForce_A = StatMoment(plist,ENS_Force_Tan_ShearForce_A,0, Compute_Per_case)"
            if 0 != self._calc_var(pobj_list,temp_string):
                err_string = "Error, failed to calculate a variable in {}".format(fcn_name)
                self.ensight.int_message(err_string,1)
                return []
            #
            # get the 3 constant force values Radial, Theta, Axial
            # new use ens_utils 10.1.6(b)
            Fr = self.get_const_val("ENS_Force_Net_Tan_ShearForce_R",pobj_list)
            Ft = self.get_const_val("ENS_Force_Net_Tan_ShearForce_T",pobj_list)
            Fa = self.get_const_val("ENS_Force_Net_Tan_ShearForce_A",pobj_list)
            if Fr != None and Fa != None and Ft != None and Fx != None and Fy != None and Fz != None: 
                ret_val = []
                for ii in range(len(pobj_list)):
                    ret_val.append([Fx[ii],Fy[ii],Fz[ii],Fr[ii],Ft[ii],Fa[ii]])
                return ret_val            
            else:
                self.ensight.int_message("Error getting ENS_Force_Net_Tan_ShearForce_R, T and/or A",1)
                return []
        else: # Only one frame or user picked frame 0 (None) for cylindrical frame calc
            if  Fx != None and Fy != None and Fz != None:
                ret_val = []
                for ii in range(len(pobj_list)):
                    ret_val.append([Fx[ii],Fy[ii],Fz[ii],0.0,0.0,0.0])
                return ret_val
            else:
                self.ensight.int_message("Error getting Fx, Fy, and/or Fz Shear Net force per part constant values",1)
                return []            

    
    
    #
    # Returns constant or (new in 10.2) per part constant var objects
    #
    def get_const_vars(self, var_type=None):
        """
        Get all constant OR per part constant variables

        Parameters
        ----------
        var_type - enums.ENS_VAR_CONSTANT (default)
            or     enums.ENS_VAR_CONSTANT_PER_PART (new in 10.2)

        Return
        List containing ENS_VAR objects

        """
        if not var_type:
            var_type = self.ensight.objs.enums.ENS_VAR_CONSTANT
        d = {self.ensight.objs.enums.VARTYPE: var_type}
        return(self.ensight.objs.core.find_objs(self.ensight.objs.core.VARIABLES,filter=d))
    #
    # Returns list constant or (new in 10.2) per part constant var names
    #
    def get_const_var_names(self, v_type=None):
        """
        Get string names of all constant OR per part constant variables 

        Parameters
        ----------
        v_type   - enums.ENS_VAR_CONSTANT (default)
            or     enums.ENS_VAR_CONSTANT_PER_PART (new in 10.2)

        Return
        List containing names of constants

        """
        if not v_type:
            v_type = self.ensight.objs.enums.ENS_VAR_CONSTANT
        name_list = []
        vars = self.get_const_vars(var_type=v_type)
        for var in vars:
            name_list.append(var.DESCRIPTION)
        return(name_list)

    def get_part_id_obj_name(self, plist=None, ret_flag="id"):
        """
        input a part or a list of parts and return an id, object, or name
          or a list of ids, objects, or names.
        
        Parameters
        ----------
        p_list:
          1. A list of ENS_PART objects 
          OR
          2. A list of int part ids 
          OR
          3. A list of strings
             a. each string is an ID
             b. each string is exact match for a part name 
          OR
          4. A single ENS_PART object 
          OR
          5. A single string
             a. that is a part id OR
             b. that extactly matches the part DESCRIPTION
          OR
          6. a single int that is a part id
          
        ret_flag - a string that determines what is returned
        
        Return: 
          - a list as follows
          A. ret_flag contains "id" -   returns a list of ids (default)
          B. ret_flag contains "name" - returns a list of part names
          C. ret_flag contains "obj"  - returns a list of ENS_PARTs      
          or [ ] if error.    
        """
        if not plist:
            plist = self.ensight.objs.core.PARTS
        pobj_list = []
        #
        #  Basically figure out what plist is, then convert it to a list of ENS_PARTs
        #
        if isinstance(plist, self.ensight.objs.ENS_PART) or  isinstance(plist,int) or isinstance(plist,str):
            p_list = [plist]
        elif  isinstance(plist, list) or isinstance(plist, self.ensight.objs.ensobjlist):
            p_list = plist
        else:
            print("Unknown type of input var plist {}".format(type(plist)))
            return []
        #
        #  p_list must now be a list
        #
        if len(p_list) > 0:
            if isinstance(p_list[0], self.ensight.objs.ENS_PART): # list of objects assumed consistent
                for prt in p_list:
                    pobj_list.append(prt)
            elif isinstance(p_list[0],int): # list of ints must be part ids
                for pid in p_list:
                    d = {self.ensight.objs.enums.PARTNUMBER:pid}
                    pobjs = self.ensight.objs.core.find_objs(self.ensight.objs.core.PARTS,d)
                    for prt in pobjs:
                        pobj_list.append(prt)
            elif isinstance(p_list[0],str):
                if p_list[0].isdigit() == False:
                    for pname in p_list:
                        d = {self.ensight.objs.enums.DESCRIPTION:pname}
                        pobjs = self.ensight.objs.core.find_objs(self.ensight.objs.core.PARTS,d)
                        for prt in pobjs:
                            pobj_list.append(prt)
                else: # digits, must be a string list of part ids? 
                    for pid_str in p_list:
                        d =  {self.ensight.objs.enums.PARTNUMBER:int(pid_str)}
                        pobjs = self.ensight.objs.core.find_objs(self.ensight.objs.core.PARTS,d)
                        for prt in pobjs:
                            pobj_list.append(prt)
            else:
                print("First member is neither ENS_PART, int, nor string")
                print("{} type= {}".format(p_list[0],type(p_list[0])))
                print("aborting")
                pobj_list = []
        else: # zero length list
            print("Zero length list")
            pobj_list = []
        ret_val = []
        if pobj_list:
            for pobj in pobj_list:
                if ret_flag.lower().find('name') >=0:
                    ret_val.append(pobj.DESCRIPTION)
                elif ret_flag.lower().find('obj') >=0:
                    ret_val.append(pobj)
                else:
                    ret_val.append(pobj.PARTNUMBER)
        else:
            ret_val = []
        return ret_val

    def get_const_val(self, cname, part_list=None, undef_none=False):
        """
          Return a float value of a variable Case constant at the current timestep,
             or return a list of values one for each part if a per part constant.
             
          Parameters
          ----------
          cname - the text name of the constant or ENS_VAR object 
    
          part_list - A single ENS_PART, part name, part id, or a list of these
                      For per part constants this is necessary so if empty, will
                      be all parts
    
          undef_none - if False (default) returns undef value (ensight.Undefined) if var
                       value is undefined OR
                       if True, returns None for undefined 
    
          Return if a Constant
                 the float value of a constant
                 OR
                 ensight.Undefined if var is undefined and undef_none is False (default)
                 OR
                 None if error or if var is undefined and undef_none is True
    
                 NEW in 10.2
                 if a Per part constant returns a list of values, corresponding to
                 each part in the input part list 
                  a list of float values if per part constant
                 OR
                  a list of float and None values if undef_none is True
                 OR
                  [ ] if error
    
        """
        if not part_list:
            part_list = self.ensight.objs.core.PARTS
        ens_routine = " 'get_const_val' "
        const_name = ""
        #
        #  error checking
        #
        if isinstance(cname,str):
            if len(cname) > 0:
                const_name = cname
                if const_name in self.get_const_var_names(v_type=ensight.objs.enums.ENS_VAR_CONSTANT_PER_PART):
                    const_type = ensight.objs.enums.ENS_VAR_CONSTANT_PER_PART
                elif const_name in self.get_const_var_names(v_type=ensight.objs.enums.ENS_VAR_CONSTANT):
                    const_type = ensight.objs.enums.ENS_VAR_CONSTANT
                else:
                    print("Error, {} Constant name {} is not a constant nor a per part constant".format( ens_routine,const_name))
                    return None
            else:
                print("Error, {} must supply a valid constant variable name ".format(ens_routine))
                return None
        elif isinstance(cname, self.ensight.objs.ENS_VAR):
            const_name = cname.DESCRIPTION
            const_type = cname.VARTYPEENUM
            if const_type != self.ensight.objs.enums.ENS_VAR_CONSTANT and const_type != self.ensight.objs.enums.ENS_VAR_CONSTANT_PER_PART:
                print("Error, Variable {} is not a constant nor a per part constant".format(cname))
                return None
        else:
            print("Error, 'get_const_val' Constant name is neither string nor ENS_VAR")
            return None
        #
        #
        #  Now get it
        #
        self.ensight.variables.activate(const_name) # bug fixed 10.1.6(c)
        
        if const_type == self.ensight.objs.enums.ENS_VAR_CONSTANT_PER_PART: # new in 10.2
    
            if not part_list:
                part_list = self.ensight.objs.core.PARTS
    
            plist = self.get_part_id_obj_name(part_list,'obj')
            ret_val = []
            #
            for prt in plist:
                if isinstance(prt,ensight.objs.ENS_PART):
                    val_dict = prt.get_values([const_name])
                    if val_dict:
                        val = val_dict[const_name][0]
                        if undef_none == True and  np.isclose( val , self.ensight.Undefined, rtol=1e-6,atol=1e-16):
                            ret_val.append(None)
                        else:
                            ret_val.append(val)
                else:
                    print("Error {} part list must contain a list of only ENS_PARTs".format(ens_routine))
            return ret_val
        else: # the legacy way using the interface manual ch 6
    
            (val,type_val,scope_val) = self.ensight.ensvariable(const_name)
    
            # type = 0 if the value is an integer, 1 if the value is a float and 2 if the value is a string
            # scope =  -1 if it is a constant computed in EnSight, and
            #             scope will be >= 0 if a command language global
            #             (0 if command language global and >0 if local to a file or loop)
            if scope_val == -1  and type_val == 1: # EnSight constant and float
                if undef_none == True and  np.isclose( val , self.ensight.Undefined, rtol=1e-6,atol=1e-16):
                    return None
                else:
                    return val
            else:
                print("Error, {} return value from ensight.ensvariable indicates it is not a float from an Ensight Constant".format(ens_routine))
                return None

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
    def _press_force_xyz_rtz(self, pobj_list, press_var_obj, frame_index = 0):
        #
        # This pobj_list should contain only 2D parts
        #
        if len(pobj_list) < 1:
            self.ensight.int_message("Error, no part provided",1)
            return False
        #
        # select all parts in list
        #
        self.ensight.utils.parts.select_parts(pobj_list)
        #
        # makes a new elem var if input var is nodal
        #
        if press_var_obj.LOCATION == self.ensight.objs.enums.ENS_VAR_ELEM:
            press_var_name = press_var_obj.DESCRIPTION
        else:
            err_string = "Error press_force_xyz_rtz: variable '{}' is not an elemental variable".format(press_var_obj.DESCRIPTION)
            self.ensight.int_message(err_string,1)
            return False
        #
        # Calculate the Force vector
        #
        calc_string = "(plist," + press_var_name + ')'
        force_calc_string = 'ENS_Force_press = Force'
        temp_string = force_calc_string + calc_string
        if 0 != self._calc_var(pobj_list,temp_string):
            self.ensight.int_message("Error calculating: '"+temp_string+"'",1)
            return False
        #
        # Calculate the force components
        #
        self.ensight.utils.parts.select_parts(pobj_list)
        temp_string = 'ENS_Force_press_X = ENS_Force_press[X]'
        if 0 != self._calc_var(pobj_list,temp_string):
            self.ensight.int_message("Error calculating: '"+temp_string+"'",1)
            return False
    
        temp_string = 'ENS_Force_press_Y = ENS_Force_press[Y]'
        if 0 != self._calc_var(pobj_list,temp_string):
            self.ensight.int_message("Error calculating: '"+temp_string+"'",1)
            return False
    
        temp_string = 'ENS_Force_press_Z = ENS_Force_press[Z]'
        if 0 != self._calc_var(pobj_list,temp_string):
            self.ensight.int_message("Error calculating: '"+temp_string+"'",1)
            return False
        #
        #  RTZ Cylindrical force
        #
        if frame_index > 0 and frame_index < len(self.ensight.objs.core.FRAMES):
            temp_string = "ENS_Force_press_cyl = RectToCyl(plist,ENS_Force_press,"+ str(frame_index)+")"
            if 0 != self._calc_var(pobj_list,temp_string):
                self.ensight.int_message("Error calculating: '"+temp_string+"'",1)
                return False
    
            temp_string = "ENS_Force_press_R = ENS_Force_press_cyl[X]"
            if 0 != self._calc_var(pobj_list,temp_string):  # radial force
                self.ensight.int_message("Error calculating: '"+temp_string+"'",1)
                return False
    
            temp_string = "ENS_Force_press_T  = ENS_Force_press_cyl[Y]"
            if 0 != self._calc_var(pobj_list,temp_string): # angular force
                self.ensight.int_message("Error calculating: '"+temp_string+"'",1)
                return False
    
            temp_string = "ENS_Force_press_A  = ENS_Force_press_cyl[Z]"
            if 0 != self._calc_var(pobj_list,temp_string): # axial force        
                self.ensight.int_message("Error calculating: '"+temp_string+"'",1)
                return False
        return True


    #
    #  Uses the stat moment to sum the forces for this list of parts
    #   resulting in a per part constant and a case constant as of 10.2.0(d)
    #   IN:
    #     pobj_list - A list of ENS_PART(s)
    #
    #     frame_index = If 0 then do not calc RTZ cylindrical net forces
    #                 otherwise calculate the net forces in Radial, Theta, and Axial
    #   OUT:
    #   calculates net pressure force per part constant using all parts
    #    in the list and creates three or six per part constants:
    #      ENS_Force_Net_press_X
    #      ENS_Force_Net_press_Y
    #      ENS_Force_Net_press_Z
    #
    #      if frame_index > 0, then calc net force using the
    #       cylindrical forces in the frame_index reference system three additional
    #       per part constants
    #
    #        ENS_Force_Net_press_R - net pressure force in the radial direction
    #        ENS_Force_Net_press_T - net pressure force in the theta angular direction
    #        ENS_Force_Net_press_A - net pressure force in the axial direction 
    #
    #   Returns:
    #      if frame_index > 0 and frame exists then returns forces for each part in the list:
    #         ( [ ENS_Force_Net_press_X, ENS_Force_Net_press_Y, ENS_Force_Net_press_Z, ENS_Force_Net_press_R, ENS_Force_Net_press_T, ENS_Force_Net_press_A ] ,
    #           [ ENS_Force_Net_press_X, ENS_Force_Net_press_Y, ENS_Force_Net_press_Z, ENS_Force_Net_press_R, ENS_Force_Net_press_T, ENS_Force_Net_press_A ] ,
    #           [ ENS_Force_Net_press_X, ENS_Force_Net_press_Y, ENS_Force_Net_press_Z, ENS_Force_Net_press_R, ENS_Force_Net_press_T, ENS_Force_Net_press_A ] , ... )
    #      else:
    #         ( [ ENS_Force_Net_press_X, ENS_Force_Net_press_Y, ENS_Force_Net_press_Z, 0.0, 0.0, 0.0] ,
    #           [ ENS_Force_Net_press_X, ENS_Force_Net_press_Y, ENS_Force_Net_press_Z, 0.0, 0.0, 0.0] ,
    #           [ ENS_Force_Net_press_X, ENS_Force_Net_press_Y, ENS_Force_Net_press_Z, 0.0, 0.0, 0.0] , ... )
    #      ERROR:
    #         [ ] if error calculating variables or getting back constant values
    #
    #
    def sum_pressure_forces_xyz_rtz(self, pobj_list, frame_index=0):
        #  
        # This pobj_list should contain only 2D parts
        #
        if len(pobj_list)<1 :
            self.ensight.int_message("Error, no part provided",1)
            return []
        #
        # Select the part(s) in the list
        # ensight.variables.evaluate("ENS_Force_Net_press_Y = StatMoment(plist,pressure,0,Compute_Per_part)")
        self.ensight.utils.parts.select_parts(pobj_list)
        #
        # Calculate the net force X, Y, and Z , 10.2.0(d) now per part constant variable
        #
        force_calc_string = "ENS_Force_Net_press_X = StatMoment"
        calc_string = "(plist," +  'ENS_Force_press_X , 0, Compute_Per_part )'
        temp_string = force_calc_string + calc_string
        if 0 != self._calc_var(pobj_list,temp_string):
            return []
        #
        force_calc_string = "ENS_Force_Net_press_Y = StatMoment"
        calc_string = "(plist," +  'ENS_Force_press_Y , 0, Compute_Per_part )'
        temp_string = force_calc_string + calc_string
        if 0 != self._calc_var(pobj_list,temp_string):
            return []
        #
        force_calc_string = "ENS_Force_Net_press_Z = StatMoment"
        calc_string = "(plist," +  'ENS_Force_press_Z , 0, Compute_Per_part )'
        temp_string = force_calc_string + calc_string
        if 0 != self._calc_var(pobj_list,temp_string):
            return []
        #
        # Calculate the Total force X, Y, and Z , 10.2.0(d) now case constant variable
        #  Totals are a case constants. We don't do anything with these vars
        #   they are calc'd to give the user the totals.
        #
        force_calc_string = "ENS_Force_Total_Net_press_X = StatMoment"
        calc_string = "(plist," +  'ENS_Force_press_X , 0, Compute_Per_case )'
        temp_string = force_calc_string + calc_string
        if 0 != self._calc_var(pobj_list,temp_string):
            return []
        #
        force_calc_string = "ENS_Force_Total_Net_press_Y = StatMoment"
        calc_string = "(plist," +  'ENS_Force_press_Y , 0, Compute_Per_case )'
        temp_string = force_calc_string + calc_string
        if 0 != self._calc_var(pobj_list,temp_string):
            return []
        #
        force_calc_string = "ENS_Force_Total_Net_press_Z = StatMoment"
        calc_string = "(plist," +  'ENS_Force_press_Z , 0, Compute_Per_case )'
        temp_string = force_calc_string + calc_string
        if 0 != self._calc_var(pobj_list,temp_string):
            return []
        #
        # get a list with a per part force, one for each part, new 10.1.6(b)
        #
        Fx = self.get_const_val("ENS_Force_Net_press_X",pobj_list)
        Fy = self.get_const_val("ENS_Force_Net_press_Y",pobj_list)
        Fz = self.get_const_val ("ENS_Force_Net_press_Z",pobj_list)
        #
        #
        # Fr, Ft, Fa
        #
        if frame_index > 0 and frame_index < len(self.ensight.objs.core.FRAMES): # user picked non-zero frame index
            #
            self.ensight.utils.parts.select_parts(pobj_list)
            #
            #  per part constant as of 10.2.0(d)
            #
            force_calc_string = "ENS_Force_Net_press_R = StatMoment"
            calc_string = "(plist," + 'ENS_Force_press_R, 0, Compute_Per_part )'
            temp_string = force_calc_string + calc_string
            if 0 != self._calc_var(pobj_list,temp_string):
                return []
            #
            force_calc_string = "ENS_Force_Net_press_T = StatMoment"
            calc_string = "(plist," + 'ENS_Force_press_T, 0, Compute_Per_part )'
            temp_string = force_calc_string + calc_string
            if 0 != self._calc_var(pobj_list,temp_string):
                return []
            #
            force_calc_string = "ENS_Force_Net_press_A = StatMoment"
            calc_string = "(plist," + 'ENS_Force_press_A, 0, Compute_Per_part )'
            temp_string = force_calc_string + calc_string
            if 0 != self._calc_var(pobj_list,temp_string):
                return []
            #
            #  Totals are a case constants. We don't do anything with these vars
            #   they are calc'd to give the user the totals.
            #
            force_calc_string = "ENS_Force_Total_Net_press_R = StatMoment"
            calc_string = "(plist," + 'ENS_Force_press_R, 0, Compute_Per_case )'
            temp_string = force_calc_string + calc_string
            if 0 != self._calc_var(pobj_list,temp_string):
                return []
            #
            force_calc_string = "ENS_Force_Total_Net_press_T = StatMoment"
            calc_string = "(plist," + 'ENS_Force_press_T, 0, Compute_Per_case )'
            temp_string = force_calc_string + calc_string
            if 0 != self._calc_var(pobj_list,temp_string):
                return []
            #
            force_calc_string = "ENS_Force_Total_Net_press_A = StatMoment"
            calc_string = "(plist," + 'ENS_Force_press_A, 0, Compute_Per_case )'
            temp_string = force_calc_string + calc_string
            if 0 != self._calc_var(pobj_list,temp_string):
                return []
            #
            #   get a list with a per part force, one for each part, new 10.1.6(b)
            #
            Fr = self.get_const_val("ENS_Force_Net_press_R",pobj_list)
            Ft = self.get_const_val("ENS_Force_Net_press_T",pobj_list)
            Fa = self.get_const_val("ENS_Force_Net_press_A",pobj_list)
            #
            if Fr != None and Ft != None and Fa != None and Fx != None and Fy != None and Fz != None: 
                ret_val = []
                for ii in range(len(pobj_list)):
                    ret_val.append([Fx[ii],Fy[ii],Fz[ii],Fr[ii],Ft[ii],Fa[ii]])
                return ret_val
            else:
                err_string = "Error getting XYZ and/or Cylindrical RTZ Pressure Net Force per part constant values"
                self.ensight.int_message(err_string,1)
                return []
        else: # either only one Frame or Frame 0 has been chosen so no cylindrical calc
            if Fx != None and Fy != None and Fz != None: 
                ret_val = []
                for ii in range(len(pobj_list)):
                    ret_val.append([Fx[ii],Fy[ii],Fz[ii],0.0,0.0,0.0])
                return ret_val
            else:
                err_string = "Error getting Fx, Fy, and/or Fz Pressure Net force per part constant values"
                self.ensight.int_message(err_string,1)
                return []

    #
    #  Writes out the lists part by part
    #
    def write_out_force_data(self, filename, original_part_selection_list, params, press_force_list, shear_force_list, press_coeff_list, shear_coeff_list, \
        press_LDS_force_list, shear_LDS_force_list, press_LDS_coeff_list, shear_LDS_coeff_list):
    
        if len(press_force_list) > 0:  # FIX ME what if we have no pressure force list but do have shear force list???
            try:
                fp = open(filename,"w")
            except:
                self.ensight.int_message("Error Failed to open output csv filename for writing '" + filename +"'",1)
                return False
    
            if 1: 
                temp_list = [0.,0.,0.]
                #
                #  get the input data filename from the server and write the filename for the current case
                #                    
                c = self.ensight.objs.core.CURRENTCASE[0]    # for c in ensight.objs.core.CASES.find(True, attr=ensight.objs.enums.ACTIVE):
                fp.write("'"+os.path.join(c.SERVERDIR, c.SERVERINFO.get('file',''))+"'\n")
                #
                #  Write the gui input values to the .csv output file as  a second
                #   line in the header
                #
                fp.write("Pressure variable name ," + params['press_varname'] + "\n")
                if len(self.ensight.objs.core.FRAMES) > 0:
                    if 'frame_index' in params:
                        fp.write("Cylindrical reference frame coordinate system frame, " + str(params['frame_index'])+ "\n")
                if ( 'shear_varname' in params) and ( params['shear_varname'] != "None") and ( params['shear_vartype'] != "None"):
                    fp.write("Shear variable name, " + params['shear_varname'] + ", " + "\n")
                    fp.write("Shear variable type, " + params['shear_vartype'] + "\n" )
                if params['Area_ref'] > 0.0:
                    fp.write("Reference Area, %.5f \n" % params['Area_ref'] )
                    fp.write("Reference Density, %.5f \n" % params['Dens_ref'] )
                    fp.write("Reference Velocity xyz, %.5f," % params['Vx_ref']  )
                    fp.write("%.5f, " % params['Vy_ref'])
                    fp.write("%.5f  \n" % params['Vz_ref'] )
                    if (params['up_vector'] != "None"):
                        fp.write('Up vector,' + params['up_vector'] + '\n')
                fp.write("\n")
                        
                fp.write("Part ID,   Part Name , Pressure Force X , Pressure Force Y , Pressure Force Z , Total Pressure Force ")
                if len(self.ensight.objs.core.FRAMES) > 0 and ( 'frame_index' in params) and ( params['frame_index'] > 0):
                    fp.write(", Pressure Force Radial , Pressure Force Theta , Pressure Force Axial, Total Cyl Pressure Force ")
                if len(shear_force_list):
                    fp.write(", Shear Force X , Shear Force Y , Shear Force Z , Total Shear Force ")
                    if len(self.ensight.objs.core.FRAMES) > 0 and ( 'frame_index' in params) and ( params['frame_index'] > 0):
                        fp.write(", Shear Force Radial , Shear Force Theta , Shear Force Axial , Total Cyl Shear Force ")
                    fp.write(", Press + Shear Force X , Press + Shear Force Y , Press + Shear Force Z , Total Press + Shear Force ")
                    if len(self.ensight.objs.core.FRAMES) > 0 and ( 'frame_index' in params) and ( params['frame_index'] > 0):
                        fp.write(", Press + Shear Force Radial , Press + Shear Force Theta , Press + Shear Force Axial , Total Press + Shear Force ")
                if len(press_coeff_list):
                    fp.write(", Coeff Press X , Coeff Press Y , Coeff Press Z , Total Coeff Press ")
                    if len(self.ensight.objs.core.FRAMES) > 0 and ( 'frame_index' in params) and ( params['frame_index'] > 0):
                        fp.write(", Coeff Press Radial , Coeff Press Theta , Coeff Press Axial , Total Coeff Press ")
                if len(shear_coeff_list):
                    fp.write(", Coeff Shear X , Coeff Shear Y , Coeff Shear Z , Total Coeff Shear ,")
                    if len(self.ensight.objs.core.FRAMES) > 0 and ( 'frame_index' in params) and ( params['frame_index'] > 0):
                        fp.write("Coeff Shear Radial , Coeff Shear Theta , Coeff Shear Axial , Total Coeff Shear ,")
                    fp.write("Coeff Press + Shear X , Coeff Press + Shear Y , Coeff Press + Shear Z , Total Coeff Press + Shear")
                    if len(self.ensight.objs.core.FRAMES) > 0 and ( 'frame_index' in params) and ( params['frame_index'] > 0):
                        fp.write(", Coeff Press + Shear Radial , Coeff Press + Shear Theta , Coeff Press + Shear Axial , Total Coeff Press + Shear")
                if len(press_LDS_force_list):
                    fp.write(", Lift Force , Drag Force , Side Force , Total Pressure Force ")
                if len(shear_LDS_force_list):
                    fp.write(", Shear Force L , Shear Force D , Shear Force Side , Total Shear Force LDS ")
                    fp.write(", Press + Shear Force L , Press + Shear Force D , Press + Shear Force Side , Total Press + Shear Force LDS ")
                if len(press_LDS_coeff_list):
                    fp.write(", Lift Coeff Press  , Drag Coeff Press , Side Coeff Press , Total Coeff Press ")
                if len(shear_LDS_coeff_list):
                    fp.write(", Lift Coeff Shear  , Drag Coeff Shear , Side Coeff Shear , Coeff Shear LDS Total,")
                    fp.write("Coeff Press + Shear L , Coeff Press + Shear D , Coeff Press + Shear Side , Coeff Press + Shear LDS Total")
                fp.write("\n")
                #
                #  Loop through and write out the vals
                #
                for ii in range(len(press_force_list)):
                    fp.write(str(original_part_selection_list[ii].PARTNUMBER) + " , " + original_part_selection_list[ii].DESCRIPTION + " , ")
                    #
                    # pressure force components then magnitude
                    #
                    for jj in range(3):
                        fp.write(str(press_force_list[ii][jj]))
                        fp.write(" , ")
                    fp.write(str( vec_mag(press_force_list[ii][:3]) )) # magnitude of Fx, Fy, Fz
                    if len(self.ensight.objs.core.FRAMES) > 0 and ('frame_index' in params) and (params['frame_index'] > 0):
                        fp.write(" , ")
                        for jj in range(3):
                            fp.write(str(press_force_list[ii][jj+3]))
                            fp.write(" , ")
                        fp.write(str( vec_mag(press_force_list[ii][3:]) )) # magnitude of Cyl Fr, Ft, Fa
                     #
                    # shear force components then magnitude
                    #
                    if len(shear_force_list) > 0:
                        fp.write(" , ")
                        for jj in range(3):
                            fp.write(str(shear_force_list[ii][jj]))
                            fp.write(" , ")
                        fp.write(str( vec_mag(shear_force_list[ii][:3]) ))
                        if len(self.ensight.objs.core.FRAMES) > 0 and ('frame_index' in params) and (params['frame_index'] > 0):
                            fp.write(" , ")
                            for jj in range(3):
                                fp.write(str(shear_force_list[ii][jj+3]))
                                fp.write(" , ")
                            fp.write(str( vec_mag(shear_force_list[ii][3:]) ))
                        fp.write(" , ")
                        # sum of pressure and shear forces components then magnitude
                        for jj in range(3):
                            temp_list[jj] = press_force_list[ii][jj] + shear_force_list[ii][jj]
                            fp.write(str( temp_list[jj] ))
                            fp.write(" , ")
                        fp.write(str( vec_mag(temp_list[:3]) ))
                        if len(self.ensight.objs.core.FRAMES) > 0 and ('frame_index' in params) and (params['frame_index'] > 0):
                            fp.write(" , ")
                            for jj in range(3):
                                temp_list[jj] = press_force_list[ii][jj+3] + shear_force_list[ii][jj+3]
                                fp.write(str( temp_list[jj] ))
                                fp.write(" , ")
                            fp.write(str( vec_mag(temp_list[:3]) ))
                            
                    #
                    # Coefficient of pressure force components then magnitude
                    #
                    if len(press_coeff_list) > 0:
                        fp.write(" , ")
                        for jj in range(3):
                            fp.write(str(press_coeff_list[ii][jj]))
                            fp.write(" , ")
                        fp.write(str( vec_mag(press_coeff_list[ii][:3]) ))
                        if len(self.ensight.objs.core.FRAMES) > 0 and ('frame_index' in params) and (params['frame_index'] > 0):
                            fp.write(" , ")
                            for jj in range(3):
                                fp.write(str(press_coeff_list[ii][jj+3]))
                                fp.write(" , ")
                            fp.write(str( vec_mag(press_coeff_list[ii][3:]) )) 
                    #
                    # Coefficient shear force components then magnitude
                    #
                    if len(shear_coeff_list) > 0:
                        fp.write(" , ")
                        for jj in range(3):
                            fp.write(str(shear_coeff_list[ii][jj]))
                            fp.write(" , ")
                        fp.write(str( vec_mag(shear_coeff_list[ii][:3]) ))
                        fp.write(" , ")
                        if len(self.ensight.objs.core.FRAMES) > 0 and ('frame_index' in params) and (params['frame_index'] > 0):
                            for jj in range(3):
                                fp.write(str(shear_coeff_list[ii][jj+3]))
                                fp.write(" , ")
                            fp.write(str( vec_mag(shear_coeff_list[ii][3:]) ))
                            fp.write(" , ")
                        # sum of pressure and shear Coefficient components then magnitude
                        for jj in range(3):
                            temp_list[jj] = press_coeff_list[ii][jj] + shear_coeff_list[ii][jj]
                            fp.write(str( temp_list[jj] ))
                            fp.write(" , ")
                        fp.write(str( vec_mag(temp_list) ))
                        if len(self.ensight.objs.core.FRAMES) > 0 and ('frame_index' in params) and (params['frame_index'] > 0):
                            fp.write(" , ")
                            for jj in range(3):
                                temp_list[jj] = press_coeff_list[ii][jj+3] + shear_coeff_list[ii][jj+3]
                                fp.write(str( temp_list[jj] ))
                                fp.write(" , ")
                            fp.write(str( vec_mag(temp_list) ))
                        fp.write(" , ")
                    #
                    # Lift, Drag and Side Force
                    # No cylindrical stuff here
                    # LDS pressure force components then magnitude
                    #
                    if len(press_LDS_force_list) > 0:
                        for jj in range(3):
                            fp.write(str(press_LDS_force_list[ii][jj]))
                            fp.write(" , ")
                        fp.write(str( vec_mag(press_LDS_force_list[ii][:3]) ))
                        fp.write(" , ")
                    # LDS shear force components then magnitude
                    if len(shear_LDS_force_list) > 0:
                        for jj in range(3):
                            fp.write(str(shear_LDS_force_list[ii][jj]))
                            fp.write(" , ")
                        fp.write(str( vec_mag(shear_LDS_force_list[ii][:3]) ))
                        fp.write(" , ")
                        # LDS sum of pressure and shear forces components then magnitude
                        for jj in range(3):
                            temp_list[jj] = press_LDS_force_list[ii][jj] + shear_LDS_force_list[ii][jj]
                            fp.write(str( temp_list[jj] ))
                            fp.write(" , ")
                        fp.write(str( vec_mag(temp_list) ))
                        fp.write(" , ")
                    # LDS Coefficient of pressure force components then magnitude
                    if len(press_LDS_coeff_list) > 0:
                        for jj in range(3):
                            fp.write(str(press_LDS_coeff_list[ii][jj]))
                            fp.write(" , ")
                        fp.write(str( vec_mag(press_LDS_coeff_list[ii][:3]) ))
                        fp.write(" , ")
                    # LDS Coefficient shear force components then magnitude
                    if len(shear_LDS_coeff_list) > 0:
                        for jj in range(3):
                            fp.write(str(shear_LDS_coeff_list[ii][jj]))
                            fp.write(" , ")
                        fp.write(str( vec_mag(shear_LDS_coeff_list[ii][:3] ) ))
                        fp.write(" , ")
                        # LDS sum of pressure and shear Coefficient components then magnitude
                        for jj in range(3):
                            temp_list[jj] = press_LDS_coeff_list[ii][jj] + shear_LDS_coeff_list[ii][jj]
                            fp.write(str( temp_list[jj] ))
                            fp.write(" , ")
                        fp.write(str( vec_mag(temp_list) ))
                    fp.write("\n")
                #  FIX ME keep track of and write out totals here when loop is done on last line?
                fp.close()
                return True
            else:
                self.ensight.int_message("Error opening filename: '{}'".format(filename),1)
                return False
        else:
            self.ensight.int_message("Error no pressure force list to write out",1)
            return False
