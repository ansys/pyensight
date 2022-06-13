"""This init file allows python to treat directories containing it as modules.

Import any methods you want exposed at your library level here.

For example, if you want to avoid this behavior:

.. code::

   >>> from ansys.pyensight.module import add

Then add the import within this module to enable:

.. code::

   >>> import ansys.pyensight as pyensight
   >>> pyensight.add(1, 2)

"""

from ._version import VERSION

__version__ = VERSION

# Default Ansys version number
__ansys_version__ = "222"

from ansys.pyensight.launcher import LocalLauncher
from ansys.pyensight.launcher import Launcher
from ansys.pyensight.session import Session
