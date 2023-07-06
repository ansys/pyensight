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

   ansys.api.pyensight.ensight_api
   ansys.api.pyensight.ensight_api.anim
   ansys.api.pyensight.ensight_api.anim_flipbook
   ansys.api.pyensight.ensight_api.anim_keyframe
   ansys.api.pyensight.ensight_api.anim_quick
   ansys.api.pyensight.ensight_api.anim_recorders
   ansys.api.pyensight.ensight_api.anim_screens
   ansys.api.pyensight.ensight_api.anim_traces
   ansys.api.pyensight.ensight_api.annot_backgr
   ansys.api.pyensight.ensight_api.annot_entlbl
   ansys.api.pyensight.ensight_api.annotation
   ansys.api.pyensight.ensight_api.arrow
   ansys.api.pyensight.ensight_api.auxgeom
   ansys.api.pyensight.ensight_api.boundarylayer
   ansys.api.pyensight.ensight_api.case
   ansys.api.pyensight.ensight_api.clip
   ansys.api.pyensight.ensight_api.collab
   ansys.api.pyensight.ensight_api.command
   ansys.api.pyensight.ensight_api.connect
   ansys.api.pyensight.ensight_api.context_restore
   ansys.api.pyensight.ensight_api.contour
   ansys.api.pyensight.ensight_api.curve
   ansys.api.pyensight.ensight_api.data
   ansys.api.pyensight.ensight_api.data_partbuild
   ansys.api.pyensight.ensight_api.define
   ansys.api.pyensight.ensight_api.devsrf
   ansys.api.pyensight.ensight_api.dial
   ansys.api.pyensight.ensight_api.dpart
   ansys.api.pyensight.ensight_api.elevsurf
   ansys.api.pyensight.ensight_api.ensight
   ansys.api.pyensight.ensight_api.enums
   ansys.api.pyensight.ensight_api.extrude
   ansys.api.pyensight.ensight_api.file
   ansys.api.pyensight.ensight_api.filterpart
   ansys.api.pyensight.ensight_api.format
   ansys.api.pyensight.ensight_api.frame
   ansys.api.pyensight.ensight_api.function
   ansys.api.pyensight.ensight_api.gauge
   ansys.api.pyensight.ensight_api.help
   ansys.api.pyensight.ensight_api.isos
   ansys.api.pyensight.ensight_api.legend
   ansys.api.pyensight.ensight_api.lightsource
   ansys.api.pyensight.ensight_api.line
   ansys.api.pyensight.ensight_api.logo
   ansys.api.pyensight.ensight_api.material
   ansys.api.pyensight.ensight_api.message_window
   ansys.api.pyensight.ensight_api.model
   ansys.api.pyensight.ensight_api.nplot
   ansys.api.pyensight.ensight_api.nvc
   ansys.api.pyensight.ensight_api.objs
   ansys.api.pyensight.ensight_api.part
   ansys.api.pyensight.ensight_api.plot
   ansys.api.pyensight.ensight_api.pointpart
   ansys.api.pyensight.ensight_api.prefs
   ansys.api.pyensight.ensight_api.profile
   ansys.api.pyensight.ensight_api.ptrace
   ansys.api.pyensight.ensight_api.ptrace_emitr
   ansys.api.pyensight.ensight_api.query_ent_var
   ansys.api.pyensight.ensight_api.query_interact
   ansys.api.pyensight.ensight_api.savegeom
   ansys.api.pyensight.ensight_api.scene
   ansys.api.pyensight.ensight_api.sepattach
   ansys.api.pyensight.ensight_api.set_tdata
   ansys.api.pyensight.ensight_api.set_visenv
   ansys.api.pyensight.ensight_api.shape
   ansys.api.pyensight.ensight_api.shell
   ansys.api.pyensight.ensight_api.shock
   ansys.api.pyensight.ensight_api.show_info
   ansys.api.pyensight.ensight_api.solution_time
   ansys.api.pyensight.ensight_api.species
   ansys.api.pyensight.ensight_api.subset
   ansys.api.pyensight.ensight_api.tensor
   ansys.api.pyensight.ensight_api.text
   ansys.api.pyensight.ensight_api.texture
   ansys.api.pyensight.ensight_api.tools
   ansys.api.pyensight.ensight_api.user
   ansys.api.pyensight.ensight_api.varextcfd
   ansys.api.pyensight.ensight_api.variables
   ansys.api.pyensight.ensight_api.vctarrow
   ansys.api.pyensight.ensight_api.view
   ansys.api.pyensight.ensight_api.view_transf
   ansys.api.pyensight.ensight_api.viewport
   ansys.api.pyensight.ensight_api.viewport_axis
   ansys.api.pyensight.ensight_api.viewport_bounds
   ansys.api.pyensight.ensight_api.views
   ansys.api.pyensight.ensight_api.vof
   ansys.api.pyensight.ensight_api.vortexcore
