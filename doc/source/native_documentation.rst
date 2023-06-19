.. _ref_native_api_docs:

********************
Native API reference
********************

The :ref:`"Native"<ref_cmdlang_native>` API is the result of direct conversion from
EnSight command language into
Python syntax. In EnSight, one can select a block of command language from the
command dialog and copy it to the clipboard in this format. There are many limitations
to this interface. For example, there is no mechanism to query values and the scripts
are highly order dependent. For new development, consider the :ref:`"Object"<ref_object_api>`
API where possible.


.. toctree::
   :hidden:
   :maxdepth: 4


.. autosummary::
   :toctree: _autosummary/

   pyensight.ensight_api
   pyensight.ensight_api.anim
   pyensight.ensight_api.anim_flipbook
   pyensight.ensight_api.anim_keyframe
   pyensight.ensight_api.anim_quick
   pyensight.ensight_api.anim_recorders
   pyensight.ensight_api.anim_screens
   pyensight.ensight_api.anim_traces
   pyensight.ensight_api.annot_backgr
   pyensight.ensight_api.annot_entlbl
   pyensight.ensight_api.annotation
   pyensight.ensight_api.arrow
   pyensight.ensight_api.auxgeom
   pyensight.ensight_api.boundarylayer
   pyensight.ensight_api.case
   pyensight.ensight_api.clip
   pyensight.ensight_api.collab
   pyensight.ensight_api.command
   pyensight.ensight_api.connect
   pyensight.ensight_api.context_restore
   pyensight.ensight_api.contour
   pyensight.ensight_api.curve
   pyensight.ensight_api.data
   pyensight.ensight_api.data_partbuild
   pyensight.ensight_api.define
   pyensight.ensight_api.devsrf
   pyensight.ensight_api.dial
   pyensight.ensight_api.dpart
   pyensight.ensight_api.elevsurf
   pyensight.ensight_api.ensight
   pyensight.ensight_api.enums
   pyensight.ensight_api.extrude
   pyensight.ensight_api.file
   pyensight.ensight_api.filterpart
   pyensight.ensight_api.format
   pyensight.ensight_api.frame
   pyensight.ensight_api.function
   pyensight.ensight_api.gauge
   pyensight.ensight_api.help
   pyensight.ensight_api.isos
   pyensight.ensight_api.legend
   pyensight.ensight_api.lightsource
   pyensight.ensight_api.line
   pyensight.ensight_api.logo
   pyensight.ensight_api.material
   pyensight.ensight_api.message_window
   pyensight.ensight_api.model
   pyensight.ensight_api.nplot
   pyensight.ensight_api.nvc
   pyensight.ensight_api.objs
   pyensight.ensight_api.part
   pyensight.ensight_api.plot
   pyensight.ensight_api.pointpart
   pyensight.ensight_api.prefs
   pyensight.ensight_api.profile
   pyensight.ensight_api.ptrace
   pyensight.ensight_api.ptrace_emitr
   pyensight.ensight_api.query_ent_var
   pyensight.ensight_api.query_interact
   pyensight.ensight_api.savegeom
   pyensight.ensight_api.scene
   pyensight.ensight_api.sepattach
   pyensight.ensight_api.set_tdata
   pyensight.ensight_api.set_visenv
   pyensight.ensight_api.shape
   pyensight.ensight_api.shell
   pyensight.ensight_api.shock
   pyensight.ensight_api.show_info
   pyensight.ensight_api.solution_time
   pyensight.ensight_api.species
   pyensight.ensight_api.subset
   pyensight.ensight_api.tensor
   pyensight.ensight_api.text
   pyensight.ensight_api.texture
   pyensight.ensight_api.tools
   pyensight.ensight_api.user
   pyensight.ensight_api.varextcfd
   pyensight.ensight_api.variables
   pyensight.ensight_api.vctarrow
   pyensight.ensight_api.view
   pyensight.ensight_api.view_transf
   pyensight.ensight_api.viewport
   pyensight.ensight_api.viewport_axis
   pyensight.ensight_api.viewport_bounds
   pyensight.ensight_api.views
   pyensight.ensight_api.vof
   pyensight.ensight_api.vortexcore
