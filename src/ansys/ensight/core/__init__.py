"""This init file allows python to treat directories containing it as modules.

Import any methods you want exposed at your library level here.

For example, if you want to avoid this behavior:

.. code::

   >>> from ansys.ensight.core.module import add

Then add the import within this module to enable:

.. code::

   >>> from ansys.ensight import core
   >>> core.add(1, 2)

"""

# major, minor, patch
version_info = 0, 1, "dev0"

# Nice string for the version
__version__ = ".".join(map(str, version_info))

from ansys.ensight.core.module import add
from ansys.ensight.core.other_module import Complex
