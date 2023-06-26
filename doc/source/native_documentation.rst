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

   ansys.pyensight.core.ensight_api
   ansys.pyensight.core.ensight_api.anim
   ansys.pyensight.core.ensight_api.anim_flipbook
   ansys.pyensight.core.ensight_api.anim_keyframe
   ansys.pyensight.core.ensight_api.anim_quick
   ansys.pyensight.core.ensight_api.anim_recorders
   ansys.pyensight.core.ensight_api.anim_screens
   ansys.pyensight.core.ensight_api.anim_traces
   ansys.pyensight.core.ensight_api.annot_backgr
   ansys.pyensight.core.ensight_api.annot_entlbl
   ansys.pyensight.core.ensight_api.annotation
   ansys.pyensight.core.ensight_api.arrow
   ansys.pyensight.core.ensight_api.auxgeom
   ansys.pyensight.core.ensight_api.boundarylayer
   ansys.pyensight.core.ensight_api.case
   ansys.pyensight.core.ensight_api.clip
   ansys.pyensight.core.ensight_api.collab
   ansys.pyensight.core.ensight_api.command
   ansys.pyensight.core.ensight_api.connect
   ansys.pyensight.core.ensight_api.context_restore
   ansys.pyensight.core.ensight_api.contour
   ansys.pyensight.core.ensight_api.curve
   ansys.pyensight.core.ensight_api.data
   ansys.pyensight.core.ensight_api.data_partbuild
   ansys.pyensight.core.ensight_api.define
   ansys.pyensight.core.ensight_api.devsrf
   ansys.pyensight.core.ensight_api.dial
   ansys.pyensight.core.ensight_api.dpart
   ansys.pyensight.core.ensight_api.elevsurf
   ansys.pyensight.core.ensight_api.ensight
   ansys.pyensight.core.ensight_api.enums
   ansys.pyensight.core.ensight_api.extrude
   ansys.pyensight.core.ensight_api.file
   ansys.pyensight.core.ensight_api.filterpart
   ansys.pyensight.core.ensight_api.format
   ansys.pyensight.core.ensight_api.frame
   ansys.pyensight.core.ensight_api.function
   ansys.pyensight.core.ensight_api.gauge
   ansys.pyensight.core.ensight_api.help
   ansys.pyensight.core.ensight_api.isos
   ansys.pyensight.core.ensight_api.legend
   ansys.pyensight.core.ensight_api.lightsource
   ansys.pyensight.core.ensight_api.line
   ansys.pyensight.core.ensight_api.logo
   ansys.pyensight.core.ensight_api.material
   ansys.pyensight.core.ensight_api.message_window
   ansys.pyensight.core.ensight_api.model
   ansys.pyensight.core.ensight_api.nplot
   ansys.pyensight.core.ensight_api.nvc
   ansys.pyensight.core.ensight_api.objs
   ansys.pyensight.core.ensight_api.part
   ansys.pyensight.core.ensight_api.plot
   ansys.pyensight.core.ensight_api.pointpart
   ansys.pyensight.core.ensight_api.prefs
   ansys.pyensight.core.ensight_api.profile
   ansys.pyensight.core.ensight_api.ptrace
   ansys.pyensight.core.ensight_api.ptrace_emitr
   ansys.pyensight.core.ensight_api.query_ent_var
   ansys.pyensight.core.ensight_api.query_interact
   ansys.pyensight.core.ensight_api.savegeom
   ansys.pyensight.core.ensight_api.scene
   ansys.pyensight.core.ensight_api.sepattach
   ansys.pyensight.core.ensight_api.set_tdata
   ansys.pyensight.core.ensight_api.set_visenv
   ansys.pyensight.core.ensight_api.shape
   ansys.pyensight.core.ensight_api.shell
   ansys.pyensight.core.ensight_api.shock
   ansys.pyensight.core.ensight_api.show_info
   ansys.pyensight.core.ensight_api.solution_time
   ansys.pyensight.core.ensight_api.species
   ansys.pyensight.core.ensight_api.subset
   ansys.pyensight.core.ensight_api.tensor
   ansys.pyensight.core.ensight_api.text
   ansys.pyensight.core.ensight_api.texture
   ansys.pyensight.core.ensight_api.tools
   ansys.pyensight.core.ensight_api.user
   ansys.pyensight.core.ensight_api.varextcfd
   ansys.pyensight.core.ensight_api.variables
   ansys.pyensight.core.ensight_api.vctarrow
   ansys.pyensight.core.ensight_api.view
   ansys.pyensight.core.ensight_api.view_transf
   ansys.pyensight.core.ensight_api.viewport
   ansys.pyensight.core.ensight_api.viewport_axis
   ansys.pyensight.core.ensight_api.viewport_bounds
   ansys.pyensight.core.ensight_api.views
   ansys.pyensight.core.ensight_api.vof
   ansys.pyensight.core.ensight_api.vortexcore
