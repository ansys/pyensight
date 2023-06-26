.. _ref_object_api_docs:

********************
Object API reference
********************

The :ref:`"Object"<ref_object_api>` API is a direct interface to the EnSight object structures.
It includes the ability to set/query attributes as well as connect callback
function that execute when attribute values change, etc. While it is a more
advanced interface than the :ref:`"Native"<ref_cmdlang_native>`  API, there are some
operations that can only be performed via that interface.


.. toctree::
   :hidden:
   :maxdepth: 4


.. autosummary::
   :toctree: _autosummary/

   ansys.pyensight.core.ensobj.ENSOBJ
   ansys.pyensight.core.ensobjlist
   ansys.pyensight.core.ens_annot.ENS_ANNOT
   ansys.pyensight.core.ens_annot_text.ENS_ANNOT_TEXT
   ansys.pyensight.core.ens_annot_line.ENS_ANNOT_LINE
   ansys.pyensight.core.ens_annot_logo.ENS_ANNOT_LOGO
   ansys.pyensight.core.ens_annot_lgnd.ENS_ANNOT_LGND
   ansys.pyensight.core.ens_annot_marker.ENS_ANNOT_MARKER
   ansys.pyensight.core.ens_annot_arrow.ENS_ANNOT_ARROW
   ansys.pyensight.core.ens_annot_dial.ENS_ANNOT_DIAL
   ansys.pyensight.core.ens_annot_gauge.ENS_ANNOT_GAUGE
   ansys.pyensight.core.ens_annot_shape.ENS_ANNOT_SHAPE
   ansys.pyensight.core.ens_camera.ENS_CAMERA
   ansys.pyensight.core.ens_case.ENS_CASE
   ansys.pyensight.core.ens_flipbook.ENS_FLIPBOOK
   ansys.pyensight.core.ens_frame.ENS_FRAME
   ansys.pyensight.core.ens_globals.ENS_GLOBALS
   ansys.pyensight.core.ens_group.ENS_GROUP
   ansys.pyensight.core.ens_lightsource.ENS_LIGHTSOURCE
   ansys.pyensight.core.ens_lpart.ENS_LPART
   ansys.pyensight.core.ens_mat.ENS_MAT
   ansys.pyensight.core.ens_palette.ENS_PALETTE
   ansys.pyensight.core.ens_part.ENS_PART
   ansys.pyensight.core.ens_part_model.ENS_PART_MODEL
   ansys.pyensight.core.ens_part_clip.ENS_PART_CLIP
   ansys.pyensight.core.ens_part_contour.ENS_PART_CONTOUR
   ansys.pyensight.core.ens_part_discrete_particle.ENS_PART_DISCRETE_PARTICLE
   ansys.pyensight.core.ens_part_frame.ENS_PART_FRAME
   ansys.pyensight.core.ens_part_isosurface.ENS_PART_ISOSURFACE
   ansys.pyensight.core.ens_part_particle_trace.ENS_PART_PARTICLE_TRACE
   ansys.pyensight.core.ens_part_profile.ENS_PART_PROFILE
   ansys.pyensight.core.ens_part_vector_arrow.ENS_PART_VECTOR_ARROW
   ansys.pyensight.core.ens_part_elevated_surface.ENS_PART_ELEVATED_SURFACE
   ansys.pyensight.core.ens_part_developed_surface.ENS_PART_DEVELOPED_SURFACE
   ansys.pyensight.core.ens_part_built_up.ENS_PART_BUILT_UP
   ansys.pyensight.core.ens_part_tensor_glyph.ENS_PART_TENSOR_GLYPH
   ansys.pyensight.core.ens_part_fx_vortex_core.ENS_PART_FX_VORTEX_CORE
   ansys.pyensight.core.ens_part_fx_shock.ENS_PART_FX_SHOCK
   ansys.pyensight.core.ens_part_fx_sep_att.ENS_PART_FX_SEP_ATT
   ansys.pyensight.core.ens_part_mat_interface.ENS_PART_MAT_INTERFACE
   ansys.pyensight.core.ens_part_point.ENS_PART_POINT
   ansys.pyensight.core.ens_part_axisymmetric.ENS_PART_AXISYMMETRIC
   ansys.pyensight.core.ens_part_vof.ENS_PART_VOF
   ansys.pyensight.core.ens_part_aux_geom.ENS_PART_AUX_GEOM
   ansys.pyensight.core.ens_part_filter.ENS_PART_FILTER
   ansys.pyensight.core.ens_plotter.ENS_PLOTTER
   ansys.pyensight.core.ens_polyline.ENS_POLYLINE
   ansys.pyensight.core.ens_probe.ENS_PROBE
   ansys.pyensight.core.ens_query.ENS_QUERY
   ansys.pyensight.core.ens_source.ENS_SOURCE
   ansys.pyensight.core.ens_spec.ENS_SPEC
   ansys.pyensight.core.ens_state.ENS_STATE
   ansys.pyensight.core.ens_texture.ENS_TEXTURE
   ansys.pyensight.core.ens_tool.ENS_TOOL
   ansys.pyensight.core.ens_tool_cursor.ENS_TOOL_CURSOR
   ansys.pyensight.core.ens_tool_line.ENS_TOOL_LINE
   ansys.pyensight.core.ens_tool_plane.ENS_TOOL_PLANE
   ansys.pyensight.core.ens_tool_box.ENS_TOOL_BOX
   ansys.pyensight.core.ens_tool_cylinder.ENS_TOOL_CYLINDER
   ansys.pyensight.core.ens_tool_cone.ENS_TOOL_CONE
   ansys.pyensight.core.ens_tool_sphere.ENS_TOOL_SPHERE
   ansys.pyensight.core.ens_tool_revolution.ENS_TOOL_REVOLUTION
   ansys.pyensight.core.ens_var.ENS_VAR
   ansys.pyensight.core.ens_vport.ENS_VPORT
