.. _ref_object_api_docs:

********************
Object API reference
********************

The :ref:`"Object"<ref_object_api>` API is a direct interface to the EnSight object structures.
It includes the ability to set/query attributes as well as connect callback
function that execute when attribute values change, etc.  While it is a more
advanced interface than the :ref:`"Native"<ref_cmdlang_native>`  API, there are some
operations that can only be performed via that interface.


.. toctree::
   :hidden:
   :maxdepth: 4


.. autosummary::
   :toctree: _autosummary/

   pyensight.ensobj.ENSOBJ
   pyensight.ensobjlist
   pyensight.ens_annot.ENS_ANNOT
   pyensight.ens_annot_text.ENS_ANNOT_TEXT
   pyensight.ens_annot_line.ENS_ANNOT_LINE
   pyensight.ens_annot_logo.ENS_ANNOT_LOGO
   pyensight.ens_annot_lgnd.ENS_ANNOT_LGND
   pyensight.ens_annot_marker.ENS_ANNOT_MARKER
   pyensight.ens_annot_arrow.ENS_ANNOT_ARROW
   pyensight.ens_annot_dial.ENS_ANNOT_DIAL
   pyensight.ens_annot_gauge.ENS_ANNOT_GAUGE
   pyensight.ens_annot_shape.ENS_ANNOT_SHAPE
   pyensight.ens_camera.ENS_CAMERA
   pyensight.ens_case.ENS_CASE
   pyensight.ens_flipbook.ENS_FLIPBOOK
   pyensight.ens_frame.ENS_FRAME
   pyensight.ens_globals.ENS_GLOBALS
   pyensight.ens_group.ENS_GROUP
   pyensight.ens_lightsource.ENS_LIGHTSOURCE
   pyensight.ens_lpart.ENS_LPART
   pyensight.ens_mat.ENS_MAT
   pyensight.ens_palette.ENS_PALETTE
   pyensight.ens_part.ENS_PART
   pyensight.ens_part_model.ENS_PART_MODEL
   pyensight.ens_part_clip.ENS_PART_CLIP
   pyensight.ens_part_contour.ENS_PART_CONTOUR
   pyensight.ens_part_discrete_particle.ENS_PART_DISCRETE_PARTICLE
   pyensight.ens_part_frame.ENS_PART_FRAME
   pyensight.ens_part_isosurface.ENS_PART_ISOSURFACE
   pyensight.ens_part_particle_trace.ENS_PART_PARTICLE_TRACE
   pyensight.ens_part_profile.ENS_PART_PROFILE
   pyensight.ens_part_vector_arrow.ENS_PART_VECTOR_ARROW
   pyensight.ens_part_elevated_surface.ENS_PART_ELEVATED_SURFACE
   pyensight.ens_part_developed_surface.ENS_PART_DEVELOPED_SURFACE
   pyensight.ens_part_built_up.ENS_PART_BUILT_UP
   pyensight.ens_part_tensor_glyph.ENS_PART_TENSOR_GLYPH
   pyensight.ens_part_fx_vortex_core.ENS_PART_FX_VORTEX_CORE
   pyensight.ens_part_fx_shock.ENS_PART_FX_SHOCK
   pyensight.ens_part_fx_sep_att.ENS_PART_FX_SEP_ATT
   pyensight.ens_part_mat_interface.ENS_PART_MAT_INTERFACE
   pyensight.ens_part_point.ENS_PART_POINT
   pyensight.ens_part_axisymmetric.ENS_PART_AXISYMMETRIC
   pyensight.ens_part_vof.ENS_PART_VOF
   pyensight.ens_part_aux_geom.ENS_PART_AUX_GEOM
   pyensight.ens_part_filter.ENS_PART_FILTER
   pyensight.ens_plotter.ENS_PLOTTER
   pyensight.ens_polyline.ENS_POLYLINE
   pyensight.ens_probe.ENS_PROBE
   pyensight.ens_query.ENS_QUERY
   pyensight.ens_source.ENS_SOURCE
   pyensight.ens_spec.ENS_SPEC
   pyensight.ens_state.ENS_STATE
   pyensight.ens_texture.ENS_TEXTURE
   pyensight.ens_tool.ENS_TOOL
   pyensight.ens_tool_cursor.ENS_TOOL_CURSOR
   pyensight.ens_tool_line.ENS_TOOL_LINE
   pyensight.ens_tool_plane.ENS_TOOL_PLANE
   pyensight.ens_tool_box.ENS_TOOL_BOX
   pyensight.ens_tool_cylinder.ENS_TOOL_CYLINDER
   pyensight.ens_tool_cone.ENS_TOOL_CONE
   pyensight.ens_tool_sphere.ENS_TOOL_SPHERE
   pyensight.ens_tool_revolution.ENS_TOOL_REVOLUTION
   pyensight.ens_var.ENS_VAR
   pyensight.ens_vport.ENS_VPORT
