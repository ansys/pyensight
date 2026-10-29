.. _ref_libuserd_api_docs:

**********************
LibUserd API reference
**********************

The ``libuserd`` module allows PyEnSight to directly access EnSight
user-defined readers (USERD).  Any file format for which EnSight
uses a USERD interface can be read using this API.


.. note::
    This module was first introduced with the Ansys 2025 R1 distribution.
    It should be considered **Beta** at this point in time. Please report
    issues via github.



.. toctree::
   :hidden:
   :maxdepth: 4


.. autosummary::
   :toctree: _autosummary/

   ansys.pyensight.core.libuserd
   ansys.pyensight.core.libuserd.LibUserd
   ansys.pyensight.core.libuserd.ReaderInfo
   ansys.pyensight.core.libuserd.Reader
   ansys.pyensight.core.libuserd.Part
   ansys.pyensight.core.libuserd.PartHints
   ansys.pyensight.core.libuserd.ElementType
   ansys.pyensight.core.libuserd.Variable
   ansys.pyensight.core.libuserd.VariableType
   ansys.pyensight.core.libuserd.VariableLocation
   ansys.pyensight.core.libuserd.Query
   ansys.pyensight.core.libuserd.LibUserdError
   ansys.pyensight.core.libuserd.ErrorCodes

