# Copyright (C) 2022 - 2026 ANSYS, Inc. and/or its affiliates.
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

from copy import copy
from types import ModuleType
from typing import TYPE_CHECKING, Any, Dict, List, Union
from uuid import uuid1
import xml.etree.ElementTree as et

if TYPE_CHECKING:
    try:
        import ensight
    except ImportError:
        from ansys.api.pyensight import ensight_api
    from ansys.api.pyensight.ens_part import ENS_PART

SPAN_EPS = 1e-5


class Turbosurfaces:

    def __init__(self, ensight: Union["ensight_api.ensight", "ensight"]):
        self.ensight = ensight
        self.component_list: List[str] = []  # Sorted list of the components by their name
        self.inlet: Dict[str, Union["ENS_PART", Any]] = {}
        self.outlet: Dict[str, Union["ENS_PART", Any]] = {}
        self.shroud: Dict[str, Union["ENS_PART", Any]] = {}
        self.hub: Dict[str, Union["ENS_PART", Any]] = {}
        self.fluid: Dict[str, Union["ENS_PART", Any]] = {}
        # Constant strings for turbosurfaces for string comparisons
        self.spanwise_str = "span"
        self.spanwise_metatag = "spanwise_"
        self.meridional_str = "meridional"
        self.meridional_metatag = "meridional_"
        self.thetacut_metatag = "thetacut_"
        self.streamwise_metatag = "streamwise_"
        # Metadata for vports
        self.spanwise_vport = "Spanwise"
        self.meridional_vport = "Meridional"
        self._progress_bar_method = None

    def hide_text_annotation(self):
        """
        Check if there is a 2D Spanwise vport and if it has a text annotation
        associated to it. If yes, hide it. We can not delete it to support multiple states
        """
        vport_spanwise_list = [
            x
            for x in self.ensight.objs.core.VPORTS
            if x.METADATA.get("ENS_TURBO_VPORT", "") == self.spanwise_vport
        ]
        if len(vport_spanwise_list) < 1:
            return
        vport = vport_spanwise_list[0]
        list_anno = [
            x
            for x in self.ensight.objs.core.ANNOTS
            if x.ANNOTTYPE == self.ensight.objs.enums.ANNO_TEXT and x.RELATIVEVIEWPORT == vport.ID
        ]
        # backward compatibility: if anno_id is empty, it could be because we were marking the
        # annotation id as part of the metadata of the viewport. So check that before assuming it does not exist.
        if len(list_anno) == 0:
            anno_id = vport.METADATA.get("ENS_TURBO_ANNO", "")
            if len(anno_id) > 0:
                # Check that anno_id corresponds to a valid text annotation. If not, reset it to nothing
                if (
                    len(
                        [
                            x
                            for x in self.ensight.objs.core.ANNOTS
                            if x.ANNOTTYPE == self.ensight.objs.enums.ANNO_TEXT
                            and x.ANNOTINDEX == int(anno_id)
                        ]
                    )
                    == 0
                ):
                    anno_id = ""
        else:
            anno_id = list_anno[0].ANNOTINDEX
        if anno_id:
            self.ensight.text.select_begin(int(anno_id))
            self.ensight.text.visible("OFF")

    def spanwise_displacement(self, part):
        """
        Check if the correct displacement for the 2D spanwise part already exists. If yes, then return its name
        If not, then create it.
        If it already exists but on the wrong part, then delete the variable and recreate it.
        Return the name of the displacement variable
        """
        caseid = str(self.ensight.objs.core.CURRENTCASE[0].CASENUMBER)
        turbo_displacement = "turbospan_displacement" + caseid
        recreate_displ = False
        if len(self.ensight.objs.core.VARIABLES[turbo_displacement]) == 0:
            recreate_displ = True
        else:
            if part not in self.ensight.objs.core.VARIABLES[turbo_displacement][0].PARTS:
                recreate_displ = True
                self.ensight.variables.deactivate(turbo_displacement)
        if recreate_displ:
            self.ensight.part.select_begin(part.PARTNUMBER)
            self.ensight.variables.evaluate(
                turbo_displacement
                + " = VectorDispProjection(plist,TURBO_stage_"
                + caseid
                + ",TurboSurfaceProjection_case"
                + caseid
                + "_7,0,3)"
            )
        self.ensight.objs.core.VARIABLES[turbo_displacement][0].PRIVATE = True
        return turbo_displacement

    def modify_turbo_part(self, part_id, p_name, p_value, twod=0, threed=0, link=0):
        """
        Modify a turbo surface. Set the new part name, isosurface value, per viewport visibility
        """
        part = [x for x in self.ensight.objs.core.PARTS if x.PARTNUMBER == part_id][0]
        # If the part is a spanwise part, make sure the value is not 0 nor 1 to avoid issues of broken
        # isosurface at the value limits
        if self.spanwise_metatag in part.METADATA.get("ENS_TURBO_VIEW", ""):
            if p_value == 0.0:
                p_value = SPAN_EPS
            elif p_value == 1.0:
                p_value = 1.0 - SPAN_EPS
        if p_name != part.DESCRIPTION:
            part.DESCRIPTION = p_name
        if float(p_value) != part.VALUE:
            part.VALUE = float(p_value)
        part.setmetatag(
            "ENS_TURBO_VDIM", str(int(twod)) + ";" + str(int(threed)) + ";" + str(int(link))
        )
        # Hide annotataion only if there is no 2D Spanwise part
        twoD_span_exists = False
        spanwise_parts = [
            p
            for p in self.ensight.objs.core.PARTS
            if p.CASENUMBER == self.ensight.objs.core.CURRENTCASE[0].CASENUMBER
            and self.spanwise_metatag in p.METADATA.get("ENS_TURBO_VIEW", "")
        ]
        for span_p in spanwise_parts:
            if "1" in span_p.METADATA.get("ENS_TURBO_VDIM", "0;1;0").split(";")[0]:
                twoD_span_exists = True
                break
        if twoD_span_exists is False:
            self.hide_text_annotation()
        threed_vports = [x for x in self.ensight.objs.core.VPORTS if x.VIEWDIMENSION == 1]
        if twod == 1:
            self.check_viewports()
            # After running check_viewports(), we know for sure that Spanwise and Meridional viewports exist
            vport_spanwise = [
                x
                for x in self.ensight.objs.core.VPORTS
                if x.METADATA.get("ENS_TURBO_VPORT", "") == self.spanwise_vport
            ][0]
            vport_meridional = [
                x
                for x in self.ensight.objs.core.VPORTS
                if x.METADATA.get("ENS_TURBO_VPORT", "") == self.meridional_vport
            ][0]
            turbo_displacement = self.spanwise_displacement(part)
            part.HANDLES_ENABLED = 0
            part.DISPLACEBY = self.ensight.objs.core.VARIABLES[turbo_displacement][0]
            self.show_text_annotation(part)
            # Set visibility. Needs to be done after setting the displacement
            for threedvports in threed_vports:
                if part.VIEWPORTVIS & 2**threedvports.ID:
                    part.setattr("VIEWPORTVIS", part.VIEWPORTVIS - 2**threedvports.ID, record=0)
            if part.VIEWPORTVIS & 2**vport_spanwise.ID == 0:
                part.setattr("VIEWPORTVIS", part.VIEWPORTVIS + 2**vport_spanwise.ID, record=0)
            if part.VIEWPORTVIS & 2**vport_meridional.ID > 0:
                part.setattr("VIEWPORTVIS", part.VIEWPORTVIS - 2**vport_meridional.ID, record=0)
        elif threed == 1:
            part.HANDLES_ENABLED = 1
            # turn off displacement
            part.DISPLACEBY = None
            # Set the part visible on all 3D viewports
            for threedvports in threed_vports:
                if not (part.VIEWPORTVIS & 2**threedvports.ID):
                    part.setattr("VIEWPORTVIS", part.VIEWPORTVIS + 2**threedvports.ID, record=0)
            # Turn off visibility on 2D viewports, if they exist
            vport_spanwise_list = [
                x
                for x in self.ensight.objs.core.VPORTS
                if x.METADATA.get("ENS_TURBO_VPORT", "") == self.spanwise_vport
            ]
            if vport_spanwise_list:
                vport_spanwise = vport_spanwise_list[0]
                if part.VIEWPORTVIS & 2**vport_spanwise.ID > 0:
                    part.setattr("VIEWPORTVIS", part.VIEWPORTVIS - 2**vport_spanwise.ID, record=0)
            vport_meridional_list = [
                x
                for x in self.ensight.objs.core.VPORTS
                if x.METADATA.get("ENS_TURBO_VPORT", "") == self.meridional_vport
            ]
            if vport_meridional_list:
                vport_meridional = vport_meridional_list[0]
                if part.VIEWPORTVIS & 2**vport_meridional.ID > 0:
                    part.setattr("VIEWPORTVIS", part.VIEWPORTVIS - 2**vport_meridional.ID, record=0)

    @staticmethod
    def ret_obj(p):
        return p.__OBJID__

    def set_twodviewport_properties(self, vtype="spanwise", vport=None):
        """
        Method to re-initialize the Spanwise or the Meridional 2D viewport and hide all parts on the vport

        Parameters
        ----------
        vtype : str
            Type of 2D viewport. Options: spanwise or meridional
        vport : ENS_VPORT

        Return
        ------
        twod_p : list
            list of parts that whose per viewport visibility is ON on vport
        """
        if vport is None:
            return
        # Record which parts are visible on this viewport before starting to modify it
        twodparts = [p for p in self.ensight.objs.core.PARTS if (p.VIEWPORTVIS & 2**vport.ID)]
        self.ensight.viewport.select_begin(vport.ID)
        if vtype == self.spanwise_str:
            self.ensight.viewport.view_dimension("3D")
            self.ensight.view_transf.initialize_viewports()
            self.ensight.view_transf.view_recall("+X")
            self.ensight.viewport.view_dimension("2D")
            self.ensight.viewport.global_axis_xlabel(".")
            self.ensight.viewport.global_axis_ylabel("M")
            self.ensight.viewport.global_axis_zlabel("T")
            self.ensight.sendmesg(r"""test: 2d_vport_align 1 1 0 0 """)
            self.ensight.view_transf.rotate(0, 0, 270)
            # Hide all parts on the 2D viewport
            for p in self.ensight.objs.core.PARTS:
                if p.VIEWPORTVIS & 2**vport.ID:
                    p.setattr("VIEWPORTVIS", p.VIEWPORTVIS - 2**vport.ID, record=0)
        elif vtype == self.meridional_str:
            self.ensight.viewport.view_dimension("3D")
            self.ensight.view_transf.initialize_viewports()
            # This needs to be commented out since setting it will mess up the Spanwise viewport
            # The meridional viewport is not being used anyway for the moment so it doesn't matter
            # self.ensight.view_transf.view_recall("+Z")
            self.ensight.viewport.view_dimension("2D")
            self.ensight.viewport.global_axis_xlabel("R")
            self.ensight.viewport.global_axis_ylabel("A")
            self.ensight.viewport.global_axis_zlabel(".")
            # Hide all parts on the 2D viewport
            for p in self.ensight.objs.core.PARTS:
                if self.meridional_metatag not in p.METADATA.get("ENS_TURBO_VIEW", ""):
                    if p.VIEWPORTVIS & 2**vport.ID:
                        p.setattr("VIEWPORTVIS", p.VIEWPORTVIS - 2**vport.ID, record=0)
        return twodparts

    def check_viewports(self):
        """
        Check if the Spanwise and Meridional viewports already exist - and if not, then create them
        and set their attributes
        """
        try:
            vpsanwise = [
                x
                for x in self.ensight.objs.core.VPORTS
                if x.METADATA.get("ENS_TURBO_VPORT", "") == self.spanwise_vport
            ]
            vmeridional = [
                x
                for x in self.ensight.objs.core.VPORTS
                if x.METADATA.get("ENS_TURBO_VPORT", "") == self.meridional_vport
            ]
            if vpsanwise and vmeridional:
                # 2D viewports already exists
                return
            # Create the 2D viewports
            # Make only main vport visible
            for v in self.ensight.objs.core.VPORTS:
                v.VISIBLE = False
            vport_main = self.ensight.objs.core.VPORTS[0]
            vport_main.VISIBLE = True
            vport_main.WIDTH = 0.66
            vport_main.HEIGHT = 1.0
            vport_main.ORIGINX = 0.34
            vport_main.ORIGINY = 0.0
            # Create Spanwise vport and make all parts invisible on it
            vport_spanwise = self.ensight.objs.core.DEFAULTVPORT[0].createviewport()
            vport_spanwise.setmetatag("ENS_TURBO_VPORT", self.spanwise_vport)
            vport_spanwise.WIDTH = 0.34
            vport_spanwise.HEIGHT = 0.5
            vport_spanwise.ORIGINX = 0.0
            vport_spanwise.ORIGINY = 0.5
            for v in self.ensight.objs.core.VPORTS:
                v.SELECTED = False
            _ = self.set_twodviewport_properties(vtype=self.spanwise_str, vport=vport_spanwise)
            # Create Meridional vport and make all parts invisible on it
            vport_mer = self.ensight.objs.core.DEFAULTVPORT[0].createviewport()
            vport_mer.setmetatag("ENS_TURBO_VPORT", self.meridional_vport)
            vport_mer.WIDTH = 0.34
            vport_mer.HEIGHT = 0.5
            vport_mer.ORIGINX = 0.0
            vport_mer.ORIGINY = 0.0
            for v in self.ensight.objs.core.VPORTS:
                v.SELECTED = False
            _ = self.set_twodviewport_properties(vtype=self.meridional_str, vport=vport_mer)
        except Exception:
            return

    def reset_spanwise_vport(self):
        """
        Reset the orientation of the 2D Spanwise viewport
        """
        vspanwise = [
            x
            for x in self.ensight.objs.core.VPORTS
            if x.METADATA.get("ENS_TURBO_VPORT", "") == self.spanwise_vport
        ]
        vport_id = vspanwise[0].ID
        self.ensight.viewport.select_begin(vport_id)
        self.ensight.view_transf.function("global")
        self.ensight.view_transf.initialize_viewports()
        self.ensight.sendmesg(r"""test: 2d_vport_align 1 1 0 0 """)
        self.ensight.view_transf.rotate(0, 0, 270)
        self.ensight.view_transf.fit(vport_id)
        return

    def reset_meridional_vport(self):
        """
        Reset the orientation of the 2D meridional viewport
        """
        vmer = [
            x
            for x in self.ensight.objs.core.VPORTS
            if x.METADATA.get("ENS_TURBO_VPORT", "") == self.meridional_vport
        ]
        vmerid = vmer[0].ID
        self.ensight.viewport.select_begin(vmerid)
        self.ensight.view_transf.function("global")
        self.ensight.view_transf.cameratoview_direction(0.000000, 0.000000, 1.0)
        self.ensight.view_transf.cameratoview_compute()
        self.ensight.view_transf.rotate(0, 0, 270)
        self.ensight.view_transf.fit(vmerid)
        return

    def set_views(self):
        """
        Reset the views in the 2D viewports. Needed to make sure the views are correct (in 2D changes in the parts can trigger
        undesired viewports updates)
        """
        for v in self.ensight.objs.core.VPORTS:
            v.SELECTED = False
        vspanwise = [
            x
            for x in self.ensight.objs.core.VPORTS
            if x.METADATA.get("ENS_TURBO_VPORT", "") == self.spanwise_vport
        ]
        if vspanwise:
            vspanwise[0].SELECTED = True
            # Identify parts with Spanwise in ENS_TURBO_VIEW metadata
            part_spanwise_metadata = [
                x
                for x in self.ensight.objs.core.PARTS
                if self.spanwise_metatag in x.METADATA.get("ENS_TURBO_VIEW", "")
            ]
            # From the list above, isolate the part(s) that are in 2D from the ENS_TURBO_VDIM metadata
            part_spanwise = []
            for p in part_spanwise_metadata:
                if p.METADATA.get("ENS_TURBO_VDIM", ""):
                    if (
                        p.METADATA.get("ENS_TURBO_VDIM", "").split(";")[0] == "1"
                        and p.CASENUMBER == self.ensight.objs.core.CURRENTCASE[0].CASENUMBER
                    ):
                        part_spanwise.append(p)
            tmp_list = self.ensight.objs.ensobjlist()
            tmp_list.extend(part_spanwise)
            tmp_list.set_attr(self.ensight.objs.enums.VISIBLE, True)
            vis_parts = self.set_twodviewport_properties(
                vtype=self.spanwise_str, vport=vspanwise[0]
            )
            if len(part_spanwise) > 0:
                part_spanwise[0].setattr("VIEWPORTVIS", (1 << vspanwise[0].ID), record=0)
                # If a part was set to be visible on the 2D Spanwise vport, and if it's a child of the
                # spanwise part, then reset it to have per vport visibility on
                for tmp_p in vis_parts:
                    if part_spanwise[0] in tmp_p.SOURCES:
                        tmp_p.setattr("VIEWPORTVIS", (1 << vspanwise[0].ID), record=0)
                # Make sure the text annotation for 2D Spanwise part is on
                self.show_text_annotation(part_spanwise[0])
            # Changing part visibility per viewport messes up the viewport orientation
            # so it needs to be reset here
            self.reset_spanwise_vport()
            vspanwise[0].SELECTED = False
            # If there are vector arrow parts associated with the 2D spanwise part, make sure their visibility per viewport
            # is on in the 2D vport (if the 2D spanwise part was turned to 3D and then back to 2D, the visibility per vport
            # will be off).
            # Step one: identify if there's any part that is a varrow and whose variable has been derived by VectorDispProjection
            if len(part_spanwise) > 0:
                varrowlist = [
                    x
                    for x in self.ensight.objs.core.PARTS
                    if x.PARTTYPE == self.ensight.objs.enums.PART_VECTOR_ARROW
                ]
                varrowlist_displ = []
                for v in varrowlist:
                    if v.VARIABLE is not None:
                        if "VectorDispProjection" in v.VARIABLE.EXPRESSION:
                            varrowlist_displ.append(v)
                # Step two: make sure all these parts have visibility per viewport set to be ON in the 2D span vport
                for varrow_part in varrowlist_displ:
                    if not (varrow_part.VIEWPORTVIS & 2 ** vspanwise[0].ID):
                        varrow_part.setattr(
                            "VIEWPORTVIS", varrow_part.VIEWPORTVIS + 2 ** vspanwise[0].ID, record=0
                        )
        vmeridional = [
            x
            for x in self.ensight.objs.core.VPORTS
            if x.METADATA.get("ENS_TURBO_VPORT", "") == self.meridional_vport
        ]
        if vmeridional:
            vmeridional[0].SELECTED = True
            vis_parts = self.set_twodviewport_properties(
                vtype=self.meridional_str, vport=vmeridional[0]
            )
            # Identify parts with meridional in ENS_TURBO_VIEW metadata
            part_mer_metadata = [
                x
                for x in self.ensight.objs.core.PARTS
                if self.meridional_metatag in x.METADATA.get("ENS_TURBO_VIEW", "")
            ]
            # From the list above, isolate the part(s) that are in 2D from the ENS_TURBO_VDIM metadata
            part_mer = []
            for p in part_mer_metadata:
                if p.METADATA.get("ENS_TURBO_VDIM", ""):
                    if (
                        p.METADATA.get("ENS_TURBO_VDIM", "").split(";")[0] == "1"
                        and p.CASENUMBER == self.ensight.objs.core.CURRENTCASE[0].CASENUMBER
                    ):
                        part_mer.append(p)
            if len(part_mer) > 0:
                part_mer[0].setattr("VIEWPORTVIS", (1 << vmeridional[0].ID), record=0)
                # If a part was set to be visible on the 2D Meridional vport, and if it's a child of the
                # meridional part, then reset it to have per vport visibility on
                for tmp_p in vis_parts:
                    if part_mer[0] in tmp_p.SOURCES:
                        tmp_p.setattr("VIEWPORTVIS", (1 << vmeridional[0].ID), record=0)
            self.reset_meridional_vport()
            vmeridional[0].SELECTED = False

    def show_text_annotation(self, part=None):
        """
        Create the text annotation in the 2D Spanwise vport for the 2D Spanwise part location
        If a text annotation associated with the vport already exists, modify it
        """
        # Check if there already is a text annotation associated with the vport
        vspanwise = [
            x
            for x in self.ensight.objs.core.VPORTS
            if x.METADATA.get("ENS_TURBO_VPORT", "") == self.spanwise_vport
        ]
        if len(vspanwise) == 0:
            # No 2D Spanwise vport. Return early
            return
        annot_list = [
            x
            for x in self.ensight.objs.core.ANNOTS
            if x.ANNOTTYPE == self.ensight.objs.enums.ANNO_TEXT
            and x.RELATIVEVIEWPORT == vspanwise[0].ID
        ]
        # Backward compatibility. If last_anno_id is empty, it might be because the annotation id was marked
        # as part of the viewport metadata. So, check on that before assuming there's no text annotation
        if len(annot_list) == 0:
            last_anno_id = vspanwise[0].METADATA.get("ENS_TURBO_ANNO", "")
            if last_anno_id:
                annot_list = [
                    x
                    for x in self.ensight.objs.core.ANNOTS
                    if x.ANNOTTYPE == self.ensight.objs.enums.ANNO_TEXT
                    and x.ANNOTINDEX == int(last_anno_id)
                ]
        if annot_list:
            last_anno = annot_list[0]
            last_anno.VISIBLE = True
        else:
            # For some reason, could not find the associated annotation. Create a new one
            # We should never end up here.
            last_anno = self.ensight.objs.core.DEFAULTANNOTS[0].createannot(update_fed=0)
        # Modify the text annotation
        txt_string = (
            r"""<\\pdes """
            + str(part.PARTNUMBER)
            + r"""\\> Span Value: <\\pval "%.5g" """
            + str(part.PARTNUMBER)
            + r"""\\> """
        )
        last_anno.DESCRIPTION = txt_string
        last_anno.LOCATIONX = 0.5
        last_anno.LOCATIONY = 0.9
        last_anno.SIZE = 10
        last_anno.RELATIVETO = 1
        last_anno.RELATIVEVIEWPORT = vspanwise[0].ID

    def change_visibility(self, part=None, turbotype="spanwise"):
        """
        Set the part to be visible only on the 2D viewport corresponding to the Turbo Type
        """
        # Unselect all viewports so the changes will be applied only to one viewport
        for v in self.ensight.objs.core.VPORTS:
            v.SELECTED = False
        if turbotype == self.spanwise_str:
            vport = [
                x
                for x in self.ensight.objs.core.VPORTS
                if x.METADATA.get("ENS_TURBO_VPORT", "") == self.spanwise_vport
            ][0]
            vport.SELECTED = True
            # Set the view in vport
            _ = self.set_twodviewport_properties(vtype=self.spanwise_str, vport=vport)
            part.setattr("VIEWPORTVIS", (1 << vport.ID), record=0)
            self.reset_spanwise_vport()
        else:
            part.VISIBLE = True
            vport = [
                x
                for x in self.ensight.objs.core.VPORTS
                if x.METADATA.get("ENS_TURBO_VPORT", "") == self.meridional_vport
            ][0]
            # Set the view in vport
            vis_parts = self.set_twodviewport_properties(vtype=self.meridional_str, vport=vport)
            part.setattr("VIEWPORTVIS", (1 << vport.ID), record=0)
            # Reset visibility for 2D children of part on the meridional vport
            for tmp_p in vis_parts:
                if part in tmp_p.SOURCES:
                    tmp_p.setattr("VIEWPORTVIS", (1 << vport.ID), record=0)
            self.ensight.view_transf.function("global")
            self.ensight.view_transf.cameratoview_direction(0.000000, 0.000000, 1.0)
            self.ensight.view_transf.cameratoview_compute()
            self.ensight.view_transf.rotate(0, 0, 270)

    def create_spanwise_part(self, partname="Spanwise", partvalue="0.5", twod=0, threed=0, link=0):
        """
        Create a Turbo Surface of the type: Spanwise
        """

        if twod == threed:
            # Error: only one of these options can be ON
            return

        # If part value is an extreme value (0 or 1), the isosurface will appear broken
        # Change the value to not be one of the extremes
        if float(partvalue) == 0:
            partvalue = SPAN_EPS
        elif float(partvalue) == 1:
            partvalue = 1.0 - SPAN_EPS

        # Make all the parts not visible on the new viewport
        self.ensight.objs.core.ensmodel_updates_suspend(
            modelfilter=self.ensight.objs.enums.ENSMODEL_SHOW_ANY,
            why=self.ensight.objs.enums.ENSMODEL_UPDATE_DTOR
            | self.ensight.objs.enums.ENSMODEL_UPDATE_SELECTION,
        )
        turbo_function = (
            "TurboSurfaceProjection_case"
            + str(self.ensight.objs.core.CURRENTCASE[0].CASENUMBER)
            + "_4"
        )
        fluid_part_list = [
            x.PARTNUMBER
            for x in self.ensight.objs.core.VARIABLES[turbo_function][0].PARTS
            if x.HAS3DELEMENTS
        ]
        self.ensight.part.select_begin(fluid_part_list)
        self.ensight.isos.select_default()
        self.ensight.part.modify_begin()
        self.ensight.isos.variable(turbo_function)
        self.ensight.isos.component(1, 0, 0)
        self.ensight.isos.value(partvalue)
        self.ensight.part.modify_end()
        self.ensight.part.select_begin(fluid_part_list)
        self.ensight.isos.begin()
        self.ensight.isos.variable(turbo_function)
        self.ensight.isos.end()
        self.ensight.isos.create()
        newpart = max(self.ensight.objs.core.PARTS, key=self.ret_obj)
        # Set part name and the metadata on the newly created part. i.e. the part obj with higher __OBJID__ value
        if len(partname) < 1:
            newpart.DESCRIPTION = "Spanwise"
        else:
            newpart.DESCRIPTION = partname
        newpart.setmetatag(
            "ENS_TURBO_VIEW",
            self.spanwise_metatag + str(self.ensight.objs.core.CURRENTCASE[0].CASENUMBER),
        )
        # Set metadata symmetry on the new part
        n_symmetry = max(
            [
                int(x.METADATA.get("ENS_SYMMETRY_COUNT", 0) or 0)
                for x in self.ensight.objs.core.VARIABLES[turbo_function][0].PARTS
                if x.HAS3DELEMENTS
            ]
        )
        newpart.setmetatag("ENS_SYMMETRY_COUNT", int(n_symmetry))
        newpart.SYMMETRYRINSTANCES = 0
        newpart.setmetatag(
            "ENS_TURBO_VDIM", str(int(twod)) + ";" + str(int(threed)) + ";" + str(int(link))
        )
        # Set the min and max value you can interactively drag the part on the viewport
        newpart.INTERACTIVERANGEMIN = SPAN_EPS
        newpart.INTERACTIVERANGEMAX = 1.0 - SPAN_EPS
        if twod == 1:
            # Apply displacement on the Spanwise part
            turbo_displacement = self.spanwise_displacement(newpart)
            # only in 360 degree cases
            if n_symmetry == -1:
                # 0.5 radians is ~30 degree span in a single element.
                newpart.setmetatag("ENS_THETAWRAP", 0.5)
            self.ensight.part.select_begin(newpart.PARTNUMBER)
            self.ensight.part.modify_begin()
            self.ensight.part.displace_by(turbo_displacement)
            self.ensight.part.modify_end()
            self.check_viewports()
            self.show_text_annotation(newpart)
            self.change_visibility(newpart, self.spanwise_str)
            newpart.HANDLES_ENABLED = 0
        elif threed == 1:
            threed_vports = [x for x in self.ensight.objs.core.VPORTS if x.VIEWDIMENSION == 1]
            newpart.VIEWPORTVIS = 0
            for threedvports in threed_vports:
                if not (newpart.VIEWPORTVIS & 2**threedvports.ID):
                    newpart.setattr(
                        "VIEWPORTVIS", newpart.VIEWPORTVIS + 2**threedvports.ID, record=0
                    )
            newpart.HANDLES_ENABLED = 1
        self.ensight.objs.core.ensmodel_updates_resume(
            modelfilter=self.ensight.objs.enums.ENSMODEL_SHOW_ANY,
            why=self.ensight.objs.enums.ENSMODEL_UPDATE_DTOR
            | self.ensight.objs.enums.ENSMODEL_UPDATE_SELECTION,
        )
        return newpart

    def create_thetacut_part(self, partname="ThetaCut", partvalue="0.5", twod=0, threed=0):
        """
        Create a Turbo Surface of the type: ThetaCut
        """

        if twod == threed or twod == 1:
            # Error: only one of these options can be ON
            return

        # Make all the parts not visible on the new viewport
        self.ensight.objs.core.ensmodel_updates_suspend(
            modelfilter=self.ensight.objs.enums.ENSMODEL_SHOW_ANY,
            why=self.ensight.objs.enums.ENSMODEL_UPDATE_DTOR
            | self.ensight.objs.enums.ENSMODEL_UPDATE_SELECTION,
        )
        turbo_function = (
            "TurboSurfaceProjection_case"
            + str(self.ensight.objs.core.CURRENTCASE[0].CASENUMBER)
            + "_4"
        )
        fluid_part_list = [
            x.PARTNUMBER
            for x in self.ensight.objs.core.VARIABLES[turbo_function][0].PARTS
            if x.HAS3DELEMENTS
        ]
        self.ensight.part.select_begin(fluid_part_list)
        self.ensight.isos.select_default()
        self.ensight.part.modify_begin()
        self.ensight.isos.variable(turbo_function)
        self.ensight.isos.component(0, 0, 1)
        self.ensight.isos.value(partvalue)
        self.ensight.part.modify_end()
        self.ensight.part.select_begin(fluid_part_list)
        self.ensight.isos.begin()
        self.ensight.isos.variable(turbo_function)
        self.ensight.isos.end()
        self.ensight.isos.create()
        # Set part name and the metadata on the newly created part. i.e. the part obj with higher __OBJID__ value
        newpart = max(self.ensight.objs.core.PARTS, key=self.ret_obj)
        if len(partname) < 1:
            newpart.DESCRIPTION = "ThetaCut"
        else:
            newpart.DESCRIPTION = partname
        # Set METADATA and symmetry on the new part
        newpart.setmetatag(
            "ENS_TURBO_VIEW",
            "thetacutview_" + str(self.ensight.objs.core.CURRENTCASE[0].CASENUMBER),
        )
        n_symmetry = max(
            [
                int(x.METADATA.get("ENS_SYMMETRY_COUNT", 0) or 0)
                for x in self.ensight.objs.core.VARIABLES[turbo_function][0].PARTS
                if x.HAS3DELEMENTS
            ]
        )
        newpart.setmetatag("ENS_SYMMETRY_COUNT", int(n_symmetry))
        newpart.SYMMETRYRINSTANCES = 0
        newpart.setmetatag("ENS_TURBO_VDIM", str(int(twod)) + ";" + str(int(threed)) + ";0")
        # Set the min and max value you can interactively drag the part on the viewport
        newpart.INTERACTIVERANGEMIN = 0.0
        newpart.INTERACTIVERANGEMAX = 1.0

        threed_vports = [x for x in self.ensight.objs.core.VPORTS if x.VIEWDIMENSION == 1]
        newpart.VIEWPORTVIS = 0
        for threedvports in threed_vports:
            if not (newpart.VIEWPORTVIS & 2**threedvports.ID):
                newpart.setattr("VIEWPORTVIS", newpart.VIEWPORTVIS + 2**threedvports.ID, record=0)
        newpart.HANDLES_ENABLED = 1

        self.ensight.objs.core.ensmodel_updates_resume(
            modelfilter=self.ensight.objs.enums.ENSMODEL_SHOW_ANY,
            why=self.ensight.objs.enums.ENSMODEL_UPDATE_DTOR
            | self.ensight.objs.enums.ENSMODEL_UPDATE_SELECTION,
        )
        return newpart

    def create_streamwise_part(self, partname="Streamwise", partvalue="0.5", twod=0, threed=1):
        """
        Create a Turbo Surface part of the type: Streamwise
        """

        if twod == threed or twod == 1:
            # Error: only one of these options can be ON
            return

        # Make all the parts not visible on the new viewport
        self.ensight.objs.core.ensmodel_updates_suspend(
            modelfilter=self.ensight.objs.enums.ENSMODEL_SHOW_ANY,
            why=self.ensight.objs.enums.ENSMODEL_UPDATE_DTOR
            | self.ensight.objs.enums.ENSMODEL_UPDATE_SELECTION,
        )
        turbo_function = (
            "TurboSurfaceProjection_case"
            + str(self.ensight.objs.core.CURRENTCASE[0].CASENUMBER)
            + "_4"
        )
        fluid_part_list = [
            x.PARTNUMBER
            for x in self.ensight.objs.core.VARIABLES[turbo_function][0].PARTS
            if x.HAS3DELEMENTS
        ]
        self.ensight.part.select_begin(fluid_part_list)
        self.ensight.isos.select_default()
        self.ensight.part.modify_begin()
        self.ensight.isos.variable(turbo_function)
        self.ensight.isos.component(0, 1, 0)
        self.ensight.isos.value(partvalue)
        self.ensight.part.modify_end()
        self.ensight.part.select_begin(fluid_part_list)
        self.ensight.isos.begin()
        self.ensight.isos.variable(turbo_function)
        self.ensight.isos.end()
        self.ensight.isos.create()
        newpart = max(self.ensight.objs.core.PARTS, key=self.ret_obj)
        # Set part name and the metadata on the newly created part. i.e. the part obj with higher __OBJID__ value
        if len(partname) < 1:
            newpart.DESCRIPTION = "Streamwise"
        else:
            newpart.DESCRIPTION = partname
        newpart.setmetatag(
            "ENS_TURBO_VIEW",
            self.streamwise_metatag + str(self.ensight.objs.core.CURRENTCASE[0].CASENUMBER),
        )
        # Set metadata symmetry on the new part
        n_symmetry = max(
            [
                int(x.METADATA.get("ENS_SYMMETRY_COUNT", 0) or 0)
                for x in self.ensight.objs.core.VARIABLES[turbo_function][0].PARTS
                if x.HAS3DELEMENTS
            ]
        )
        newpart.setmetatag("ENS_SYMMETRY_COUNT", int(n_symmetry))
        newpart.SYMMETRYRINSTANCES = 0
        newpart.setmetatag("ENS_TURBO_VDIM", str(int(twod)) + ";" + str(int(threed)) + ";0")
        # Set the min and max value you can interactively drag the part on the viewport
        newpart.INTERACTIVERANGEMIN = 0.0
        newpart.INTERACTIVERANGEMAX = max(1, len(self.component_list))
        # Make sure the new part is visible on all 3D viewports
        threed_vports = [x for x in self.ensight.objs.core.VPORTS if x.VIEWDIMENSION == 1]
        newpart.VIEWPORTVIS = 0
        for threedvports in threed_vports:
            if not (newpart.VIEWPORTVIS & 2**threedvports.ID):
                newpart.setattr("VIEWPORTVIS", newpart.VIEWPORTVIS + 2**threedvports.ID, record=0)

        self.ensight.objs.core.ensmodel_updates_resume(
            modelfilter=self.ensight.objs.enums.ENSMODEL_SHOW_ANY,
            why=self.ensight.objs.enums.ENSMODEL_UPDATE_DTOR
            | self.ensight.objs.enums.ENSMODEL_UPDATE_SELECTION,
        )
        return newpart

    def change_turbo_type(self, partname="", turbotype=0):
        """
        Change the type of Turbo Surface part. This implies modifying the Isosurface variable and the METADATA information

        Parameters
        ----------
        partname : str
            Name of the part to modify
        turbotype: int
            integer that corresponds to the part type to change to.
            0 = Spanwise
            1 = Thetacut
            2 = Streamwise

        Returns
        -------
        None
        """
        parttochange = self.ensight.objs.core.PARTS[partname][0]
        turbo_function = (
            "TurboSurfaceProjection_case"
            + str(self.ensight.objs.core.CURRENTCASE[0].CASENUMBER)
            + "_4"
        )
        meta_str = self.spanwise_metatag
        if turbotype == 1:
            meta_str = self.thetacut_metatag
        elif turbotype == 2:
            meta_str = self.streamwise_metatag
        # Change isosurface part
        self.ensight.part.select_begin(parttochange.PARTNUMBER)
        self.ensight.part.modify_begin()
        self.ensight.isos.variable(turbo_function)
        if turbotype == 0:
            self.ensight.isos.component(1, 0, 0)
            parttochange.INTERACTIVERANGEMIN = SPAN_EPS
            parttochange.INTERACTIVERANGEMAX = 1.0 - SPAN_EPS
        elif turbotype == 1:
            self.ensight.isos.component(0, 0, 1)
            parttochange.INTERACTIVERANGEMIN = 0.0
            parttochange.INTERACTIVERANGEMAX = 1.0
        elif turbotype == 2:
            self.ensight.isos.component(0, 1, 0)
            parttochange.INTERACTIVERANGEMIN = 0.0
            parttochange.INTERACTIVERANGEMAX = max(1, len(self.component_list))
        self.ensight.part.modify_end()
        # Change METADATA on the part
        parttochange.setmetatag(
            "ENS_TURBO_VIEW", meta_str + str(self.ensight.objs.core.CURRENTCASE[0].CASENUMBER)
        )
        self.hide_text_annotation()

    def delete_turbo_surface(self, partlist=[]):
        """
        Delete turbo surface part(s) and associated text annotations
        Input: partlist as list of part names
        """
        # Hide associated annotations
        part_ids = []
        for p in partlist:
            if self.ensight.objs.core.PARTS[p]:
                self.hide_text_annotation()
                part_ids.append(self.ensight.objs.core.PARTS[p][0].PARTNUMBER)
        if part_ids:
            self.ensight.part.select_begin(part_ids)
            self.ensight.part.delete()

    def set_rotation(self, partids_list=[], axis="x", instances=0, viewrotnumber=36):
        """
        Apply the visual symmetry on passed parts. Record the information in the TurboMachinery GUI, if it exists
        """
        backup_selection_parts = self.ensight.objs.core.PARTS.get_attr(
            self.ensight.objs.enums.SELECTED
        )

        self.ensight.part.select_begin(partids_list)
        self.ensight.part.modify_begin()
        if axis == "":
            self.ensight.part.symmetry_type("none")
        else:
            self.ensight.part.symmetry_type("rotational")
            self.ensight.part.modify_end()
            self.ensight.part.select_begin(partids_list)
            self.ensight.part.modify_begin()
            self.ensight.part.symmetry_axis(axis)
            self.ensight.part.modify_end()
            self.ensight.part.select_begin(partids_list)
            self.ensight.part.modify_begin()
            self.ensight.part.periodic_sections(viewrotnumber)
            self.ensight.part.modify_end()
            # Set the number of instances
            self.ensight.part.modify_begin()
            self.ensight.part.symmetry_rinstances(instances)
        self.ensight.part.modify_end()

        # Restore part selection
        self.ensight.objs.core.ensmodel_updates_suspend(
            modelfilter=self.ensight.objs.enums.ENSMODEL_SHOW_ANY,
            why=self.ensight.objs.enums.ENSMODEL_UPDATE_DTOR
            | self.ensight.objs.enums.ENSMODEL_UPDATE_SELECTION,
        )
        for i_p, p in enumerate(self.ensight.objs.core.PARTS):
            p.SELECTED = backup_selection_parts[i_p]
        self.ensight.objs.core.ensmodel_updates_resume(
            modelfilter=self.ensight.objs.enums.ENSMODEL_SHOW_ANY,
            why=self.ensight.objs.enums.ENSMODEL_UPDATE_DTOR
            | self.ensight.objs.enums.ENSMODEL_UPDATE_SELECTION,
        )

    def reinit_settings(self):
        """
        Cancel all previous TURBO initialization for each part in the current case
        """
        for p in self.ensight.objs.core.PARTS:
            if p.CASENUMBER == self.ensight.objs.core.CURRENTCASE[0].CASENUMBER:
                p.ENS_TURBO_STAGE = ""

    def dict_ids_to_part(self, id_dict):
        """
        Convert the dictionary values from list of part IDs to list of parts
        """
        tmp_dict = {}
        for k in id_dict.keys():
            tmp_dict[k] = []
            for p_id in id_dict[k]:
                tmp_dict[k].append(
                    [p for p in self.ensight.objs.core.PARTS if p.PARTNUMBER == p_id][0]
                )
        return tmp_dict

    def set_number_passages(self, list_npassages=[]):
        """
        Set the number of passages in 360 for each component
        Input: list of numbers
        """
        ret_value = True

        for i_component, component in enumerate(self.component_list):
            inlet_part = self.inlet.get(component, None)
            if inlet_part:
                for part in inlet_part:
                    part.setmetatag("ENS_SYMMETRY_COUNT", int(list_npassages[i_component]))
            else:
                if isinstance(self.ensight, ModuleType):
                    return False, component, "Number of 360 passages on inlet"
                raise RuntimeError(f"Cannot find inlet component {component}")
            outlet_part = self.outlet.get(component, None)
            if outlet_part:
                for part in outlet_part:
                    part.setmetatag("ENS_SYMMETRY_COUNT", int(list_npassages[i_component]))
            else:
                if isinstance(self.ensight, ModuleType):
                    return False, component, "Number of 360 passages on outlet"
                raise RuntimeError(f"Cannot find outlet component {component}")
            hub_part = self.hub.get(component, None)
            if hub_part:
                for part in hub_part:
                    part.setmetatag("ENS_SYMMETRY_COUNT", int(list_npassages[i_component]))
            else:
                if isinstance(self.ensight, ModuleType):
                    return False, component, "Number of 360 passages on hub"
                raise RuntimeError(f"Cannot find hub component {component}")
            shroud_part = self.shroud.get(component, None)
            if shroud_part:
                for part in shroud_part:
                    part.setmetatag("ENS_SYMMETRY_COUNT", int(list_npassages[i_component]))
            else:
                if isinstance(self.ensight, ModuleType):
                    return False, component, "Number of 360 passages on shroud"
                raise RuntimeError(f"Cannot find shroud component {component}")
            fluid_part = self.fluid.get(component, None)
            if fluid_part:
                for part in fluid_part:
                    part.setmetatag("ENS_SYMMETRY_COUNT", int(list_npassages[i_component]))
            else:
                if isinstance(self.ensight, ModuleType):
                    return False, component, "Number of 360 passages on fluid"
                raise RuntimeError(f"Cannot find fluid component {component}")

        return ret_value, None, ""

    def set_inlet_parts(self, part_dict={}):
        """
        Set the inlet parts.
        Input: part_dict: dictionary with key = component name, value = inlet part IDs
        """
        is_ensight_module = isinstance(self.ensight, ModuleType)
        try:
            self.inlet = self.dict_ids_to_part(part_dict)

            for component in self.component_list:
                inlet_part = self.inlet.get(component, None)
                if inlet_part is None:
                    if is_ensight_module:
                        return False, component
                    raise RuntimeError(f"Cannot find intel component {component}")
                elif len(inlet_part) == 0:
                    if is_ensight_module:
                        return False, component
                    raise RuntimeError(f"Cannot find intel component {component}")
                else:
                    if len(inlet_part) == 1:
                        existing_tag = inlet_part[0].ENS_TURBO_STAGE
                        existing_tag += ";" + str(component) + ",INLET"
                        inlet_part[0].ENS_TURBO_STAGE = existing_tag
                    elif len(inlet_part) > 1:
                        # Multiple inlet parts. Merge them together, hide the original parts
                        # and un-tag them as inlet parts
                        part_ids = ""
                        for p in inlet_part:
                            part_ids += str(p.PARTNUMBER) + ", "
                            p.ENS_TURBO_STAGE = ""
                        self.ensight.part.select_begin(part_ids[:-2])
                        self.ensight.part.merge()
                        self.ensight.objs.core.PARTS[-1].DESCRIPTION = str(component) + " INLET"
                        # Copy the metadata from the first inlet part onto the merged
                        for k in inlet_part[0].METADATA:
                            self.ensight.objs.core.PARTS[-1].setmetatag(
                                k, inlet_part[0].METADATA.get(k, "")
                            )
                        self.ensight.objs.core.PARTS[-1].setmetatag(
                            "ENS_TURBO_STAGE", str(component) + ",INLET"
                        )
                        self.inlet[component] = [self.ensight.objs.core.PARTS[-1]]
            return True, None
        except Exception:
            if is_ensight_module:
                return False, component
            raise RuntimeError(f"Cannot find intel component {component}")

    def set_outlet_parts(self, part_dict={}):
        """
        Set the outlet parts.
        Input: part_dict: dictionary with key = component name, value = outlet part IDs
        """
        is_ensight_module = isinstance(self.ensight, ModuleType)
        try:
            self.outlet = self.dict_ids_to_part(part_dict)

            for component in self.component_list:
                outlet_part = self.outlet.get(component, None)
                if outlet_part is None:
                    if is_ensight_module:
                        return False, component
                    raise RuntimeError(f"Cannot find outlet component {component}")
                elif len(outlet_part) == 0:
                    if is_ensight_module:
                        return False, component
                    raise RuntimeError(f"Cannot find outlet component {component}")
                else:
                    if len(outlet_part) == 1:
                        existing_tag = outlet_part[0].ENS_TURBO_STAGE
                        existing_tag += ";" + str(component) + ",OUTLET"
                        outlet_part[0].ENS_TURBO_STAGE = existing_tag
                    elif len(outlet_part) > 1:
                        # Multiple outlet parts. Merge them together, hide the original parts
                        # and un-tag them as outlet parts
                        part_ids = ""
                        for p in outlet_part:
                            part_ids += str(p.PARTNUMBER) + ", "
                            p.ENS_TURBO_STAGE = ""
                        self.ensight.part.select_begin(part_ids[:-2])
                        self.ensight.part.merge()
                        self.ensight.objs.core.PARTS[-1].DESCRIPTION = str(component) + " OUTLET"
                        # Copy the metadata from the first outlet part onto the merged
                        for k in outlet_part[0].METADATA:
                            self.ensight.objs.core.PARTS[-1].setmetatag(
                                k, outlet_part[0].METADATA.get(k, "")
                            )
                        self.ensight.objs.core.PARTS[-1].setmetatag(
                            "ENS_TURBO_STAGE", str(component) + ",OUTLET"
                        )
                        self.outlet[component] = [self.ensight.objs.core.PARTS[-1]]
            return True, None
        except Exception:
            if is_ensight_module:
                return False, component
            raise RuntimeError(f"Cannot find outlet component {component}")

    def set_shroud_parts(self, part_dict={}):
        """
        Set the shroud parts.
        Input: part_dict: dictionary with key = component name, value = shroud part IDs
        """
        is_ensight_module = isinstance(self.ensight, ModuleType)
        try:
            self.shroud = self.dict_ids_to_part(part_dict)

            for component in self.component_list:
                shroud_part = self.shroud.get(component, None)
                if shroud_part is None:
                    if is_ensight_module:
                        return False, component
                    raise RuntimeError(f"Cannot find shroud component {component}")
                elif len(shroud_part) == 0:
                    if is_ensight_module:
                        return False, component
                    raise RuntimeError(f"Cannot find shroud component {component}")
                else:
                    if len(shroud_part) == 1:
                        existing_tag = shroud_part[0].ENS_TURBO_STAGE
                        existing_tag += ";" + str(component) + ",SHROUD"
                        shroud_part[0].ENS_TURBO_STAGE = existing_tag
                    elif len(shroud_part) > 1:
                        # Multiple shroud parts. Merge them together, hide the original parts
                        # and un-tag them as shroud parts
                        part_ids = ""
                        for p in shroud_part:
                            part_ids += str(p.PARTNUMBER) + ", "
                            p.ENS_TURBO_STAGE = ""
                        self.ensight.part.select_begin(part_ids[:-2])
                        self.ensight.part.merge()
                        self.ensight.objs.core.PARTS[-1].DESCRIPTION = str(component) + " SHROUD"
                        # Copy the metadata from the first shroud part onto the merged
                        for k in shroud_part[0].METADATA:
                            self.ensight.objs.core.PARTS[-1].setmetatag(
                                k, shroud_part[0].METADATA.get(k, "")
                            )
                        self.ensight.objs.core.PARTS[-1].setmetatag(
                            "ENS_TURBO_STAGE", str(component) + ",SHROUD"
                        )
                        self.shroud[component] = [self.ensight.objs.core.PARTS[-1]]
            return True, None
        except Exception:
            if is_ensight_module:
                return False, component
            raise RuntimeError(f"Cannot find shroud component {component}")

    def set_hub_parts(self, part_dict={}):
        """
        Set the hub parts.
        Input: part_dict: dictionary with key = component name, value = hub part IDs
        """
        is_ensight_module = isinstance(self.ensight, ModuleType)
        try:
            self.hub = self.dict_ids_to_part(part_dict)

            for component in self.component_list:
                hub_part = self.hub.get(component, None)
                if hub_part is None:
                    if is_ensight_module:
                        return False, component
                    raise RuntimeError(f"Cannot find hub component {component}")
                elif len(hub_part) == 0:
                    if is_ensight_module:
                        return False, component
                    raise RuntimeError(f"Cannot find hub component {component}")
                else:
                    if len(hub_part) == 1:
                        existing_tag = hub_part[0].ENS_TURBO_STAGE
                        existing_tag += ";" + str(component) + ",HUB"
                        hub_part[0].ENS_TURBO_STAGE = existing_tag
                    elif len(hub_part) > 1:
                        # Multiple hub parts. Merge them together, hide the original parts
                        # and un-tag them as hub parts
                        part_ids = ""
                        for p in hub_part:
                            part_ids += str(p.PARTNUMBER) + ", "
                            p.ENS_TURBO_STAGE = ""
                        self.ensight.part.select_begin(part_ids[:-2])
                        self.ensight.part.merge()
                        self.ensight.objs.core.PARTS[-1].DESCRIPTION = str(component) + " HUB"
                        # Copy the metadata from the first hub part onto the merged
                        for k in hub_part[0].METADATA:
                            self.ensight.objs.core.PARTS[-1].setmetatag(
                                k, hub_part[0].METADATA.get(k, "")
                            )
                        self.ensight.objs.core.PARTS[-1].setmetatag(
                            "ENS_TURBO_STAGE", str(component) + ",HUB"
                        )
                        self.hub[component] = [self.ensight.objs.core.PARTS[-1]]
            return True, None
        except Exception:
            if is_ensight_module:
                return False, component
            raise RuntimeError(f"Cannot find hub component {component}")

    def set_fluid_parts(self, part_dict={}):
        """
        Set the fluid parts.
        Input: part_dict: dictionary with key = component name, value = fluid part IDs
        """
        is_ensight_module = isinstance(self.ensight, ModuleType)
        try:
            self.fluid = self.dict_ids_to_part(part_dict)

            for component in self.component_list:
                fluid_part = self.fluid.get(component, None)
                for p in fluid_part:
                    existing_tag = p.ENS_TURBO_STAGE
                    existing_tag += ";" + str(component) + ",FLUID"
                    p.ENS_TURBO_STAGE = existing_tag
            return True, None
        except Exception:
            if is_ensight_module:
                return False, component
            raise RuntimeError(f"Cannot find hub component {component}")

    def set_component_order(self, component_list):
        """
        Set the list of the components in the correct order, to be used by the turbo functions
        """
        self.component_list = component_list
        component_str = ""
        for i in self.component_list:
            component_str += i + ","
        self.ensight.objs.core.CURRENTCASE[0].setmetatag("ENS_COMPONENT_ORDER", component_str)
        # Mark that the initialization has been run. This needs to be done both here and in the GUI side
        # so that restoring a cmd file will still mark the initialization correctly
        self.ensight.objs.core.CURRENTCASE[0].LPARTS[0].setmetatag(
            "turbo_askedInit", str(self.ensight.objs.core.CURRENTCASE[0].LPARTS[0].__OBJID__)
        )

    def create_turbo_projection(self, turbo_function=0, is_360_case=0):
        """
        Create the individual turbomachinery calculator function
        """
        currentcase = self.ensight.objs.core.CURRENTCASE[0]
        currentcase_id = str(currentcase.CASENUMBER)
        all_parts = []
        for k in self.fluid.keys():
            all_parts.extend([x.PARTNUMBER for x in self.fluid[k]])
        for k in self.inlet.keys():
            all_parts.extend([x.PARTNUMBER for x in self.inlet[k]])
        for k in self.outlet.keys():
            all_parts.extend([x.PARTNUMBER for x in self.outlet[k]])
        for k in self.hub.keys():
            all_parts.extend([x.PARTNUMBER for x in self.hub[k]])
        for k in self.shroud.keys():
            all_parts.extend([x.PARTNUMBER for x in self.shroud[k]])
        self.ensight.part.select_begin(all_parts)
        turbo_string = (
            "TurboSurfaceProjection_case"
            + currentcase_id
            + "_"
            + str(turbo_function)
            + " = TurboSurfaceProjection(plist,TURBO_hub_"
            + currentcase_id
            + ",TURBO_shroud_"
            + currentcase_id
            + ",TURBO_inlet_"
            + currentcase_id
            + ",TURBO_outlet_"
            + currentcase_id
            + ","
        )
        originsplit = currentcase.METADATA.get("ENS_TURBO_ORIGIN", "0.0, 0.0, 0.0").split(",")
        axissplit = currentcase.METADATA.get("ENS_TURBO_AXIS", "0.0, 0.0, 1.0").split(",")
        turbo_string += originsplit[0] + "," + originsplit[1] + "," + originsplit[2] + ","
        turbo_axis_x = float(axissplit[0]) - float(originsplit[0])
        turbo_axis_y = float(axissplit[1]) - float(originsplit[1])
        turbo_axis_z = float(axissplit[2]) - float(originsplit[2])
        turbo_string += str(turbo_axis_x) + "," + str(turbo_axis_y) + "," + str(turbo_axis_z)
        self.ensight.part.select_begin(all_parts)
        turbo_string += ",TURBO_component_" + currentcase_id
        turbo_string += "," + str(is_360_case) + ","
        self.ensight.variables.evaluate(turbo_string + str(turbo_function) + ")")
        self.ensight.objs.core.VARIABLES[
            "TurboSurfaceProjection_case" + currentcase_id + "_" + str(turbo_function)
        ][0].PRIVATE = True

    def call_turbo_functions(self):
        """
        Create all the calculator functions that are needed for the Turbomachinery analysis. This is the core part
        of the turbomachinery initialization step
        """
        currentcase_id = str(self.ensight.objs.core.CURRENTCASE[0].CASENUMBER)
        # Delete the turbomachinery surface parts, if they exist
        turbo_type = [
            self.meridional_metatag,
            self.spanwise_metatag,
            self.thetacut_metatag,
            self.streamwise_metatag,
        ]
        for i_type in turbo_type:
            part_list = [
                x.PARTNUMBER
                for x in self.ensight.objs.core.PARTS
                if (
                    x.CASENUMBER == int(currentcase_id)
                    and i_type in x.METADATA.get("ENS_TURBO_VIEW", "")
                )
            ]
            if part_list:
                self.ensight.part.select_begin(part_list)
                self.ensight.part.delete()
        # Create TURBO_* variables that are needed to create the turbo projections. These variables contain the IDs for the turbo part types
        # If variables already exist, then delete them
        # Schema: for each turbo type (such as inlet) you'll get one Constant Per Case for component that gives you the
        # part id for the corresponding part. Variable name: TURBO_inlet_currentcaseid_componentnumber
        # Then, for each turbo type, (such as inlet) you'll have one Constant Per Part that gives you the ID of that turbo type on
        # all the parts from that component. Variable name: TURBO_inlet_currentcaseid
        turbo_type = ["inlet", "outlet", "hub", "shroud"]
        for t_type in turbo_type:
            t_type_vars = self.ensight.objs.core.VARIABLES.find(
                "TURBO_" + t_type + "_" + currentcase_id + "*", wildcard=1
            )
            for tmp_var in t_type_vars:
                self.ensight.variables.deactivate(tmp_var.DESCRIPTION)
        # Check if TURBO_stage and TURBO_component exist, and if yes, delete them
        stage_vars = ["TURBO_component_" + currentcase_id, "TURBO_stage_" + currentcase_id]
        for i_var in stage_vars:
            if len(self.ensight.objs.core.VARIABLES[i_var]) > 0:
                self.ensight.variables.deactivate(i_var)
        # Check is the 2D spanwise annotation exists, and if yes, then delete it
        vport_spanwise_list = [
            x
            for x in self.ensight.objs.core.VPORTS
            if x.METADATA.get("ENS_TURBO_VPORT", "") == self.spanwise_vport
        ]
        if len(vport_spanwise_list) > 0:
            vport = vport_spanwise_list[0]
            anno_id = vport.METADATA.get("ENS_TURBO_ANNO", "")
            if anno_id:
                self.ensight.text.select_begin(int(anno_id))
                self.ensight.text.delete()
        # Mark the most recent variable OBJID, so we can quickly identify the new ones and set them to private once we're done
        var_objid = max([x.__OBJID__ for x in self.ensight.objs.core.VARIABLES])
        # Now, create the Constant Per Case: for each turbo type, for each component
        for i_component, component in enumerate(self.component_list):
            self.ensight.part.select_begin(self.inlet[component][0].PARTNUMBER)
            self.ensight.variables.evaluate(
                "TURBO_inlet_"
                + currentcase_id
                + "_"
                + str(i_component)
                + " = PartNumber(plist,Compute_Per_case)"
            )
            self.ensight.part.select_begin(self.outlet[component][0].PARTNUMBER)
            self.ensight.variables.evaluate(
                "TURBO_outlet_"
                + currentcase_id
                + "_"
                + str(i_component)
                + " = PartNumber(plist,Compute_Per_case)"
            )
            self.ensight.part.select_begin(self.hub[component][0].PARTNUMBER)
            self.ensight.variables.evaluate(
                "TURBO_hub_"
                + currentcase_id
                + "_"
                + str(i_component)
                + " = PartNumber(plist,Compute_Per_case)"
            )
            self.ensight.part.select_begin(self.shroud[component][0].PARTNUMBER)
            self.ensight.variables.evaluate(
                "TURBO_shroud_"
                + currentcase_id
                + "_"
                + str(i_component)
                + " = PartNumber(plist,Compute_Per_case)"
            )
        # For each component, let's create the Constant Per Part that gives you the ID of the corresponding turbo part type
        # on all the parts belonging to that component
        for i_component, component in enumerate(self.component_list):
            all_parts_for_component = []
            all_parts_for_component.append(self.inlet[component][0].PARTNUMBER)
            all_parts_for_component.append(self.outlet[component][0].PARTNUMBER)
            all_parts_for_component.append(self.hub[component][0].PARTNUMBER)
            all_parts_for_component.append(self.shroud[component][0].PARTNUMBER)
            for i_fluid in self.fluid[component]:
                all_parts_for_component.append(i_fluid.PARTNUMBER)
            self.ensight.part.select_begin(all_parts_for_component)
            self.ensight.variables.evaluate(
                "TURBO_component_"
                + currentcase_id
                + "= ConstantPerPart(plist,"
                + str(i_component)
                + ")"
            )
            for t_type in turbo_type:
                tmp_input_name = "TURBO_" + t_type + "_" + currentcase_id + "_" + str(i_component)
                tmp_var_name = "TURBO_" + t_type + "_" + currentcase_id
                self.ensight.variables.evaluate(
                    tmp_var_name + "= ConstantPerPart(plist," + tmp_input_name + ")"
                )
            self._set_progress_bar_value(i_component)
        # Create a scalar field on the fluid parts that for each node returns its corresponding component number
        all_fluids = []
        for tmp_component in self.fluid.keys():
            for tmp_part in self.fluid.get(tmp_component, []):
                all_fluids.append(tmp_part.PARTNUMBER)
        self.ensight.part.select_begin(all_fluids)
        self.ensight.variables.evaluate(
            "TURBO_stage_"
            + currentcase_id
            + "= MakeScalNode(plist,TURBO_component_"
            + currentcase_id
            + ")"
        )
        # Set the variables to be private
        new_vars = [x for x in self.ensight.objs.core.VARIABLES if x.__OBJID__ > var_objid]
        for tmp_vars in new_vars:
            tmp_vars.PRIVATE = True

        # Determine if the case is a full wheel one. If all the component symmetries are set to -1,
        # then it's a fullwheel
        bool_fullwheel = True
        for i_component, component in enumerate(self.component_list):
            inlet_part = self.inlet.get(component, None)
            if inlet_part:
                for part in inlet_part:
                    tmp_symm = part.METADATA.get("ENS_SYMMETRY_COUNT", 0)
                    if tmp_symm >= 0:
                        bool_fullwheel = False
        fullwheel = int(bool_fullwheel)

        # Create the turbo functions
        self.create_turbo_projection(turbo_function=2, is_360_case=fullwheel)
        self._set_progress_bar_value(2 * len(self.component_list))
        self.create_turbo_projection(turbo_function=4, is_360_case=fullwheel)
        self._set_progress_bar_value(3 * len(self.component_list))
        self.create_turbo_projection(turbo_function=5, is_360_case=fullwheel)
        self._set_progress_bar_value(4 * len(self.component_list))
        self.create_turbo_projection(turbo_function=7, is_360_case=fullwheel)
        self._set_progress_bar_value(4 * len(self.component_list))

    def _set_progress_bar_value(self, n_pass):
        if self._progress_bar_method:
            self._progress_bar_method(n_pass)

    def set_origin_axis(self, values=[0, 0, 0, 0, 0, 1]):
        """
        Record the information on turbomachinery rotation origin and axis into the GUI, if it exists
        """
        # Store the origin and axis information
        self.ensight.objs.core.CURRENTCASE[0].setmetatag(
            "ENS_TURBO_ORIGIN", str(values[0]) + "," + str(values[1]) + "," + str(values[2])
        )
        self.ensight.objs.core.CURRENTCASE[0].setmetatag(
            "ENS_TURBO_AXIS", str(values[3]) + "," + str(values[4]) + "," + str(values[5])
        )

    def change_component_name(self, part_to_change):
        """
        Change the metadata of the passed parts: from old component name
        to a new component name.
        part_to_change: dictionary. keys = part ID. Value = list of 2 elements
        First element = old component name
        Second element = new component name
        """
        for pid in part_to_change.keys():
            part = [x for x in self.ensight.objs.core.PARTS if x.PARTNUMBER == pid][0]
            metadata = part.METADATA["ENS_TURBO_STAGE"]
            new_metadata = metadata.replace(part_to_change[pid][0], part_to_change[pid][1])
            part.setmetatag("ENS_TURBO_STAGE", new_metadata)

    @staticmethod
    def save_part_info(et, allparts, part, metadata, symm_count):
        """
        Record in the initialization file the leaf with the part information
        """
        part_item = et.SubElement(allparts, "partname")
        part_item.set("name", part.DESCRIPTION)
        part_turbo = et.SubElement(part_item, "turbo")
        part_turbo.set("turboinfo", "ENS_TURBO_STAGE")
        part_turbo.text = metadata
        part_turbo_sym = et.SubElement(part_item, "turbo")
        part_turbo_sym.set("turboinfo", "ENS_SYMMETRY_COUNT")
        part_turbo_sym.text = symm_count

    def save_initialization(self, filename):
        """Save the initialization settings in xml format"""
        try:
            data = et.Element("TurboMachinery")
            data.set("version", "1.0")
            case = et.SubElement(data, "case")

            origin_item = et.SubElement(case, "origin")
            origin_item.set("originpoint", "ENS_TURBO_ORIGIN")
            origin_item.text = self.ensight.objs.core.CURRENTCASE[0].METADATA.get(
                "ENS_TURBO_ORIGIN", "0.0,0.0,0.0"
            )

            origin_item = et.SubElement(case, "origin")
            origin_item.set("originpoint", "ENS_TURBO_AXIS")
            origin_item.text = self.ensight.objs.core.CURRENTCASE[0].METADATA.get(
                "ENS_TURBO_AXIS", "0.0,0.0,1.0"
            )

            origin_item = et.SubElement(case, "origin")
            origin_item.set("originpoint", "ENS_COMPONENT_ORDER")
            origin_item.text = self.ensight.objs.core.CURRENTCASE[0].METADATA.get(
                "ENS_COMPONENT_ORDER", "1"
            )

            allparts = et.SubElement(case, "parts")
            allparts.set("partlist", "")
            for p in self.ensight.objs.core.PARTS:
                metadata = p.METADATA.get("ENS_TURBO_STAGE", "")
                if len(metadata) > 0:
                    symm_count = str(p.METADATA.get("ENS_SYMMETRY_COUNT", 0))
                    # If the part has SOURCES, then it's a merged part. Mark its original parts instead of the
                    # merged one, so that the user can reproduce the actual initialization in a new EnSight session
                    if len(p.SOURCES) > 0:
                        for store_p in p.SOURCES:
                            self.save_part_info(et, allparts, store_p, metadata, symm_count)
                    else:
                        self.save_part_info(et, allparts, p, metadata, symm_count)

            mydata = et.tostring(data)
            myfile = open(filename, "wb")
            myfile.write(mydata)
            myfile.flush()
            myfile.close()
            return True
        except Exception:
            if isinstance(self.ensight, ModuleType):
                return False
            raise RuntimeError("Cannot save turbo initialization file")

    def restore_initialization(self, filename):
        """
        Restore the initialization settings as METADATA from an xml file
        """
        try:
            # Remove ENS_TURBO_STAGE from all parts and lparts to make sure we only use the info from the init file
            for p in self.ensight.objs.core.PARTS:
                p.setmetatag("ENS_TURBO_STAGE", "")
                for lp in p.LPARTPARENT:
                    if lp is not None:
                        lp.setmetatag("ENS_TURBO_STAGE", "")
            # Check if the turbo dataset is full_wheel. If all ENS_SYMMETRY_COUNT are < 0, then it's full wheel.
            # Set the checkbox accordingly in the UI, if it's available
            full_wheel = True
            tree = et.parse(filename)
            root = tree.getroot()
            for elem in root:
                for subelem in elem:
                    if "originpoint" in subelem.attrib.keys():
                        self.ensight.objs.core.CURRENTCASE[0].setmetatag(
                            subelem.attrib["originpoint"], subelem.text
                        )
                    if "partlist" in subelem.attrib.keys():
                        for subsubelem in subelem:
                            for i in subsubelem:
                                ipart_name = subsubelem.attrib["name"]
                                part_list = self.ensight.objs.core.PARTS[ipart_name]
                                if len(part_list) > 0 and i.text is not None:
                                    if i.attrib["turboinfo"] == "ENS_SYMMETRY_COUNT":
                                        part_list[0].setmetatag(i.attrib["turboinfo"], int(i.text))
                                        if float(i.text) >= 0:
                                            full_wheel = False
                                    else:
                                        part_list[0].setmetatag(i.attrib["turboinfo"], i.text)
            return True, full_wheel
        except Exception:
            if isinstance(self.ensight, ModuleType):
                return False, False
            raise RuntimeError("Cannot save turbo initialization file")

    def _visualize_turbo_parts_prep(self):
        self.ensight.part.select_all()
        self.ensight.part.visible("OFF")
        all_vis_parts = []
        current_case = self.ensight.objs.core.CURRENTCASE[0].CASENUMBER
        parts = self.ensight.objs.core.PARTS
        all_current_parts = [x for x in parts if x.CASENUMBER == current_case]
        return all_current_parts, all_vis_parts

    def visualize_turbo_parts(self, components=[], parttype=[]):
        """
        Change the visualization of parts. Set all parts to hidden, and show only the ones corresponding
        to the passed values.
        components: list of components by component name
        parttype: list of parttypes to visualize, by part name
        """
        all_current_parts, all_vis_parts = self._visualize_turbo_parts_prep()
        try:
            # The self.inlet and similar dictionaries do not keep track of the case. We should add support for that.
            # In the meantime, let's try to make sure the parts we extract from these dictionaries are on the current
            # case. If the dataset has been replaced, then the parts do not exist any more and this will result in
            # error. In that case, go in the except section and set all_vis_parts to be empty
            if "inlet" in parttype:
                for component in components:
                    inlet_part = self.inlet.get(component, None)
                    if inlet_part:
                        if (
                            inlet_part[0].CASENUMBER
                            == self.ensight.objs.core.CURRENTCASE[0].CASENUMBER
                        ):
                            all_vis_parts.extend(inlet_part)
            if "outlet" in parttype:
                for component in components:
                    outlet_part = self.outlet.get(component, None)
                    if outlet_part:
                        if (
                            outlet_part[0].CASENUMBER
                            == self.ensight.objs.core.CURRENTCASE[0].CASENUMBER
                        ):
                            all_vis_parts.extend(outlet_part)
            if "hub" in parttype:
                for component in components:
                    hub_part = self.hub.get(component, None)
                    if hub_part:
                        if (
                            hub_part[0].CASENUMBER
                            == self.ensight.objs.core.CURRENTCASE[0].CASENUMBER
                        ):
                            all_vis_parts.extend(hub_part)
            if "shroud" in parttype:
                for component in components:
                    shroud_part = self.shroud.get(component, None)
                    if shroud_part:
                        if (
                            shroud_part[0].CASENUMBER
                            == self.ensight.objs.core.CURRENTCASE[0].CASENUMBER
                        ):
                            all_vis_parts.extend(shroud_part)
            if "fluid" in parttype:
                for component in components:
                    fluid_parts = self.fluid.get(component, None)
                    if fluid_parts:
                        if (
                            fluid_parts[0].CASENUMBER
                            == self.ensight.objs.core.CURRENTCASE[0].CASENUMBER
                        ):
                            all_vis_parts.extend(fluid_parts)
        except Exception:
            all_vis_parts = []
        if len(all_vis_parts) < 1:
            # No selected parts. Most likely, initialization hadn't been run yet, so
            # the dictionaries weren't set, and we need to manually cycle through all
            # the parts
            for p in all_current_parts:
                if p.ENS_TURBO_STAGE:
                    split_metatag = p.ENS_TURBO_STAGE.split(",")
                    component_name = split_metatag[0].replace(";", "")
                    if len(component_name) > 0 and component_name in components:
                        if len(split_metatag) == 2:
                            comp_type = split_metatag[1]
                            if comp_type.lower() in parttype:
                                all_vis_parts.append(p)
        # Set the parts to visible
        if all_vis_parts:
            for tmp_p in all_vis_parts:
                tmp_p.VISIBLE = True

    def distort_vector_variable(self, newvar="", var="", create_part=0):
        """
        Apply distortion to a vector field, from the XYZ space to the RTA space
        Inputs:
        newvar = Name of the vector variable with distortion applied
        var = Original vector variable to distort
        create_part = Create a vector arrow part on the 2D spanwise part corresponding to the distorted vector var
        """
        try:
            if len(newvar):
                if self.ensight.objs.core.VARIABLES[var]:
                    # This calculation is valid only on 2D parts. Identify the spanwise parts
                    spanwise_parts = [
                        p
                        for p in self.ensight.objs.core.PARTS
                        if p.CASENUMBER == self.ensight.objs.core.CURRENTCASE[0].CASENUMBER
                        and self.spanwise_metatag in p.METADATA.get("ENS_TURBO_VIEW", "")
                    ]
                    # Create the distorted vector variable
                    turbo_displacement = (
                        "TurboSurfaceProjection_case"
                        + str(self.ensight.objs.core.CURRENTCASE[0].CASENUMBER)
                        + "_7"
                    )
                    fluid_part_ids = [
                        x.PARTNUMBER
                        for x in self.ensight.objs.core.VARIABLES[turbo_displacement][0].PARTS
                        if x.HAS3DELEMENTS
                    ]
                    selected_parts = [x.PARTNUMBER for x in spanwise_parts]
                    selected_parts.extend(fluid_part_ids)
                    self.ensight.part.select_begin(selected_parts)
                    if (
                        self.ensight.objs.core.VARIABLES[var][0].LOCATION
                        == self.ensight.objs.enums.ENS_VAR_ELEM
                    ):
                        # Create a new unique variable name
                        new_var_name = var + "_N"
                        while len(self.ensight.objs.core.VARIABLES[new_var_name]) > 0:
                            new_var_name = str(uuid1()).replace("-", "")[0:7]
                        self.ensight.variables.evaluate(
                            new_var_name + " = ElemToNode(plist," + var + ")"
                        )
                        var = new_var_name
                        self.ensight.objs.core.VARIABLES[new_var_name][0].PRIVATE = True
                    self.ensight.variables.evaluate(
                        newvar
                        + " = VectorDispProjection(plist,"
                        + var
                        + ","
                        + turbo_displacement
                        + ",0,2)"
                    )
                    if create_part == 1:
                        for span_p in spanwise_parts:
                            if "1" in span_p.METADATA.get("ENS_TURBO_VDIM", "0;1;0").split(";")[0]:
                                self.ensight.part.select_begin(span_p.PARTNUMBER)
                                self.ensight.variables.activate(newvar)
                                self.ensight.vctarrow.select_default()
                                self.ensight.part.modify_begin()
                                self.ensight.vctarrow.variable(newvar)
                                self.ensight.part.modify_end()
                                self.ensight.part.select_begin(span_p.PARTNUMBER)
                                self.ensight.vctarrow.begin()
                                self.ensight.vctarrow.end()
                                self.ensight.vctarrow.create()
                                # Apply displacement
                                varrow_part = sorted(
                                    self.ensight.objs.core.PARTS, key=lambda x: x.__OBJID__
                                )[-1]
                                varrow_part.DISPLACEBY = self.ensight.objs.core.VARIABLES[
                                    turbo_displacement
                                ][0]
        except Exception:
            raise RuntimeError("Error in distortion of vector field")

    def merge_variables(self, part_mer_dict={}, new_var_list=[], final_varname=""):
        """
        Merge variables defined on different meridional parts into a single variable defined on all of them

        Parameters
        ----------
        part_mer_dict : dict
            Dictionary with key = component ; value = meridional part
        new_var_list : list
            List of variables to merge together
        final_varname : string
            Name of the final variable

        Return
        ------
        None

        """
        n_pass = 3  # number of variables to combine together at each pass
        part_ids = [x.PARTNUMBER for x in part_mer_dict.values()]
        self.ensight.part.select_begin(part_ids)
        num_vars = len(new_var_list)
        while len(new_var_list) > 1:
            new_new_var_list = []
            if int(num_vars / n_pass) == 0 or (
                int(num_vars / n_pass) == 1 and (num_vars % n_pass == 0)
            ):
                # Last pass
                new_var_name = final_varname
                var_name_0 = new_var_list[0]
                var_name_1 = new_var_list[1]
                if len(new_var_list) == 3:
                    var_name_2 = new_var_list[2]
                    new_var_str = (
                        new_var_name
                        + " = IF_EQ("
                        + var_name_0
                        + ",UNDEFINED)*IF_EQ("
                        + var_name_1
                        + ",UNDEFINED)*"
                        + var_name_2
                        + "+IF_EQ("
                        + var_name_1
                        + ",UNDEFINED)*IF_EQ("
                        + var_name_2
                        + ",UNDEFINED)*"
                        + var_name_0
                        + "+IF_EQ("
                        + var_name_0
                        + ",UNDEFINED)*IF_EQ("
                        + var_name_2
                        + ",UNDEFINED)*"
                        + var_name_1
                    )
                else:
                    new_var_str = (
                        new_var_name
                        + " = IF_EQ("
                        + var_name_0
                        + ",UNDEFINED)*"
                        + var_name_1
                        + " + IF_EQ("
                        + var_name_1
                        + ",UNDEFINED)*"
                        + var_name_0
                    )
                self.ensight.variables.evaluate(new_var_str)
                new_new_var_list = [new_var_name]
            else:
                for i in range(int(num_vars / n_pass)):
                    var_name_0 = new_var_list[n_pass * i]
                    var_name_1 = new_var_list[n_pass * i + 1]
                    var_name_2 = new_var_list[n_pass * i + 2]
                    new_var_name = str(uuid1()).replace("-", "")[0:7]
                    # Make sure the var name is unique
                    while len(self.ensight.objs.core.VARIABLES[new_var_name]) > 0:
                        new_var_name = str(uuid1()).replace("-", "")[0:7]
                    new_var_str = (
                        new_var_name
                        + " = IF_EQ("
                        + var_name_0
                        + ",UNDEFINED)*IF_EQ("
                        + var_name_1
                        + ",UNDEFINED)*"
                        + var_name_2
                        + " + IF_EQ("
                        + var_name_1
                        + ",UNDEFINED)*IF_EQ("
                        + var_name_2
                        + ",UNDEFINED)*"
                        + var_name_0
                        + " + IF_EQ("
                        + var_name_0
                        + ",UNDEFINED)*IF_EQ("
                        + var_name_2
                        + ",UNDEFINED)*"
                        + var_name_1
                    )
                    self.ensight.variables.evaluate(new_var_str)
                    new_new_var_list.append(new_var_name)
                    self.ensight.objs.core.VARIABLES[new_var_name][0].PRIVATE = True
                if num_vars % n_pass == 1:
                    new_new_var_list.append(new_var_list[num_vars - 1])
                if num_vars % n_pass == 2:
                    new_new_var_list.append(new_var_list[num_vars - 2])
                    new_new_var_list.append(new_var_list[num_vars - 1])
            num_vars = len(new_new_var_list)
            new_var_list = new_new_var_list

    def create_meridional(self, n_stream=10, n_span=10, var="None", avg=0, density="", velocity=""):
        """
        Create / modify a meridional part
        Input:
        n_stream: number of points in stream direction
        n_span: number of points in span direction
        var: variable to average and color the meridional part(s) by
        avg: type of averaging to perform. 0 = Area. 1 = Mass
        density: name of density variable to use for Mass avaraging
        velocity: name of velocity variable to use for Mass averaging
        """
        # If we're coming from a ctx file restore, set_component_order has not been called directly so we have to
        # manually recalculate self.component_list from the metadata
        if self.component_list == []:
            list_cmp = self.ensight.objs.core.CURRENTCASE[0].METADATA.get("ENS_COMPONENT_ORDER", "")
            for i_cmp in list_cmp.split(","):
                if len(i_cmp) > 0:
                    self.component_list.append(i_cmp)
        # Number of components
        num_components = len(self.component_list)
        # Check if there is a self.fluid entry for each component. If not, try to fill the dictionary
        for i_component in self.component_list:
            if self.fluid.get(i_component, None) is None:
                threed_parts = [
                    p
                    for p in self.ensight.objs.core.PARTS
                    if (
                        p.HAS3DELEMENTS
                        and p.CASENUMBER == self.ensight.objs.core.CURRENTCASE[0].CASENUMBER
                    )
                ]
                fluid_p = [
                    p
                    for p in threed_parts
                    if (str(i_component) + ",FLUID" in p.METADATA.get("ENS_TURBO_STAGE", ""))
                ]
                self.fluid[i_component] = fluid_p
        # Find meridional part
        part_mer_list = [
            x
            for x in self.ensight.objs.core.PARTS
            if (
                x.CASENUMBER == self.ensight.objs.core.CURRENTCASE[0].CASENUMBER
                and self.meridional_metatag in x.METADATA.get("ENS_TURBO_VIEW", "")
            )
        ]
        # Dictionary that maps the component to its meridional part
        part_mer_dict = {}
        for p in part_mer_list:
            for k in self.fluid:
                if p.SOURCES[0] in self.fluid[k]:
                    part_mer_dict[k] = p
        # Get the name of the displacement variable for this case
        displ_varname = (
            "TurboSurfaceProjection_case"
            + str(self.ensight.objs.core.CURRENTCASE[0].CASENUMBER)
            + "_5"
        )
        # Name of the variable used to displace the meridional part(s) by
        final_varname = "Turbo_mer_displacement_" + str(
            self.ensight.objs.core.CURRENTCASE[0].CASENUMBER
        )
        # Create / Modify the meridional part
        if part_mer_list:
            # meridional part(s) exists. Modify it/them
            final_varname = part_mer_list[0].DISPLACEBY.DESCRIPTION
            for component in part_mer_dict:
                part_mer = part_mer_dict[component]
                x_delta = 0.01 / int(n_stream)
                x_min = x_delta
                x_max = 1 - x_delta
                y_min = part_mer.CLIPPLANEPT1[1]
                part_mer.GRIDPTS = [int(n_stream), int(n_span)]
                part_mer.CLIPPLANEPT1 = [x_min, y_min, 0.5]
                part_mer.CLIPPLANEPT2 = [x_min, y_min + 1, 0.5]
                part_mer.CLIPPLANEPT3 = [x_max, y_min + 1, 0.5]
        else:
            # meridional parts do not exist. Create them.
            part_mer_dict = {}
            # Inset the clip by half cell size in the R direction
            x_delta = 0.01 / int(n_stream)
            x_min = x_delta
            x_max = 1 - x_delta
            # Create the group for the meridional parts
            part_util = self.ensight.utils.parts
            mer_gr = part_util.create_part_group("Meridional")
            new_var_list = []
            for i in range(num_components):
                # Step 1: Create the meridional part as a clip on the fluid part
                fluid_parts = [x.PARTNUMBER for x in self.fluid.get(self.component_list[i], [])]
                self.ensight.clip.select_default()
                self.ensight.part.select_begin(fluid_parts)
                self.ensight.clip.begin()
                self.ensight.clip.type("grid_full")
                self.ensight.clip.grid_pts(int(n_stream), int(n_span))
                self.ensight.clip.extents("finite")
                self.ensight.clip.tool("plane")
                self.ensight.clip.plane(1, x_min, i, 0.5)
                self.ensight.clip.plane(2, x_min, i + 1, 0.5)
                self.ensight.clip.plane(3, x_max, i + 1, 0.5)
                self.ensight.clip.plane_nodeid(-1, -1, -1)
                self.ensight.clip.end()
                self.ensight.clip.create()
                part_mer = sorted(self.ensight.objs.core.PARTS, key=lambda x: x.__OBJID__)[-1]
                # Move the part under the Meridional group
                if mer_gr is not None:
                    _ = part_util.move_part_to_group(mer_gr, part_mer)
                part_mer.DESCRIPTION = "Meridional_" + self.component_list[i].replace(" ", "")
                part_mer.setmetatag(
                    "ENS_TURBO_VIEW",
                    self.meridional_metatag
                    + self.component_list[i].replace(" ", "")
                    + "_"
                    + str(self.ensight.objs.core.CURRENTCASE[0].CASENUMBER),
                )
                part_mer.HANDLES_ENABLED = 0
                part_mer_dict[self.component_list[i]] = part_mer
                # Make sure the part does not inherit client symmetry settings
                part_mer.SYMMETRYTYPE = self.ensight.objs.enums.VISUAL_SYMM_NONE
                # Step 2: Apply the displacement
                if num_components > 1:
                    outline_varname = (
                        "Turbo_mer_displacement_"
                        + str(i)
                        + "_"
                        + str(self.ensight.objs.core.CURRENTCASE[0].CASENUMBER)
                    )
                else:
                    outline_varname = final_varname
                # If outline variable already exists but it is defined on the wrong parts, deactivate it and recreate it
                if len(self.ensight.objs.core.VARIABLES[outline_varname]) > 0:
                    if part_mer not in self.ensight.objs.core.VARIABLES[outline_varname][0].PARTS:
                        self.ensight.variables.deactivate(outline_varname)
                # If the displacement variable doesn't exist, then create it
                if len(self.ensight.objs.core.VARIABLES[outline_varname]) == 0:
                    p_lists = copy(fluid_parts)
                    p_lists.extend([part_mer.PARTNUMBER])
                    self.ensight.part.select_begin(p_lists)
                    self.ensight.variables.evaluate(
                        outline_varname
                        + " = VectorDispProjection(plist,"
                        + displ_varname
                        + ","
                        + displ_varname
                        + ","
                        + str(i)
                        + ",4)"
                    )
                    self.ensight.objs.core.VARIABLES[outline_varname][0].PRIVATE = True
                    part_mer.setmetatag("ENS_TURBO_VDIM", "1;0;0")
                new_var_list.append(outline_varname)
            if num_components > 1:
                self.merge_variables(
                    part_mer_dict=part_mer_dict,
                    new_var_list=new_var_list,
                    final_varname=final_varname,
                )
                self.ensight.objs.core.VARIABLES[final_varname][0].PRIVATE = True
        # Apply displacement into the RTZ space with a constant T to the meridional part only
        for i in range(num_components):
            part_mer = part_mer_dict[self.component_list[i]]
            self.ensight.part.select_begin(part_mer.PARTNUMBER)
            part_mer.DISPLACEBY = self.ensight.objs.core.VARIABLES[final_varname][0]
            part_mer.DISPLACEFACTOR = 1.0

        # Set the meridional part(s) to be colored by a variable. Create the variable if needed.
        if var != "" and var != "None" and len(self.ensight.objs.core.VARIABLES[var]) > 0:
            # Meridional variable to color by: check if it already exists / create it
            # If the name of the variable is longer than 48 characters, truncate it to avoid
            # having a variable name in var_name longer than the allowed 79 characters
            if len(var) > 48:
                var_str = var[0:47]
            else:
                var_str = var
            new_var_list = []
            if (
                self.ensight.objs.core.VARIABLES[var][0].VARTYPEENUM
                == self.ensight.objs.enums.ENS_VAR_VECTOR
            ):
                # If the variable is a vector, first create its corresponding magnitude scalar and use
                # that instead. Parent parts: all turbo fluid and meridional parts
                p_lists = []
                p_list_no_merid = []
                for i in range(num_components):
                    for i_fluid in self.fluid.get(self.component_list[i], None):
                        p_lists.append(i_fluid.PARTNUMBER)
                        p_list_no_merid.append(i_fluid.PARTNUMBER)
                    part_mer = part_mer_dict[self.component_list[i]]
                    p_lists.extend([part_mer.PARTNUMBER])
                var_str = "magn_" + var_str
                # If the variable already exists, then expand its parent part to include all previous and
                # new parts. Do not delete the variable since it could have been used for other meridional
                # calculations.
                to_expand = []
                if len(self.ensight.objs.core.VARIABLES[var_str]) > 0:
                    parent_part_ids = [
                        x.PARTNUMBER for x in self.ensight.objs.core.VARIABLES[var_str][0].PARTS
                    ]
                    for fluid_part in p_lists:
                        if fluid_part not in parent_part_ids:
                            to_expand.append(fluid_part)
                if to_expand:
                    p_lists.extend(to_expand)
                self.ensight.part.select_begin(p_list_no_merid)
                self.ensight.variables.evaluate(var_str + " = RMS(" + var + ")")
                var = var_str
            for i in range(num_components):
                p_lists = []
                for i_fluid in self.fluid.get(self.component_list[i], None):
                    p_lists.append(i_fluid.PARTNUMBER)
                part_mer = part_mer_dict[self.component_list[i]]
                p_lists.extend([part_mer.PARTNUMBER])
                # If there is more than one component, then we need intermediate variables to create a single
                # variable valid on all the meridional parts
                var_name = ""
                set_private = False
                if num_components > 1:
                    set_private = True
                    var_name = str(i) + "_"
                var_name += (
                    "Mer_"
                    + var_str
                    + "_"
                    + str(avg)
                    + "_"
                    + str(self.ensight.objs.core.CURRENTCASE[0].CASENUMBER)
                )
                new_var_list.append(var_name)
                # If the variable already exists, then re-create it. This might be needed if, for example, we used the Mass
                # average with different density and velocity in a previous calculation
                if len(self.ensight.objs.core.VARIABLES[var_name]) > 0:
                    self.ensight.variables.deactivate(var_name)
                if len(self.ensight.objs.core.VARIABLES[var_name]) == 0:
                    self.ensight.part.select_begin(p_lists)
                    self.ensight.variables.activate(var)
                    if str(avg) == "0":
                        self.ensight.variables.evaluate(
                            var_name
                            + " = TurboSurfaceIntegral(plist,"
                            + str(part_mer.PARTNUMBER)
                            + ","
                            + var
                            + ","
                            + displ_varname
                            + ", 0, -1, -1)"
                        )
                    elif str(avg) == "1":
                        self.ensight.variables.evaluate(
                            var_name
                            + " = TurboSurfaceIntegral(plist,"
                            + str(part_mer.PARTNUMBER)
                            + ","
                            + var
                            + ","
                            + displ_varname
                            + ", 0,"
                            + density
                            + ","
                            + velocity
                            + ")"
                        )
                    self.ensight.objs.core.VARIABLES[var_name][0].PRIVATE = set_private
            # If there is more than one component, merge the variables into one single variable valid on all
            # the meridional parts
            colorby_varname = (
                "Mer_"
                + var_str
                + "_"
                + str(avg)
                + "_"
                + str(self.ensight.objs.core.CURRENTCASE[0].CASENUMBER)
            )
            if num_components > 1:
                self.merge_variables(
                    part_mer_dict=part_mer_dict,
                    new_var_list=new_var_list,
                    final_varname=colorby_varname,
                )
            # Finally, color the part(s) by the variable
            for i in range(num_components):
                part_mer = part_mer_dict[self.component_list[i]]
                color_var = self.ensight.objs.core.VARIABLES[colorby_varname][0]
                part_mer.COLORBYPALETTE = [color_var, 0]
        else:
            for part_mer in part_mer_dict.values():
                part_mer.COLORBYPALETTE = [None, 0]
        # Finish the settings of the meridional part, common to all the scenarios
        self.check_viewports()
        for part_mer in part_mer_dict.values():
            self.change_visibility(part=part_mer, turbotype="meridional")
        self.reset_meridional_vport()
