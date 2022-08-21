"""
.. _ref_basic_example:

Basic PyEnSight Usage
~~~~~~~~~~~~~~~~~~~~~

TBD

"""

from ansys.pyensight import LocalLauncher

###############################################################################
# Start by launching and connecting to an instance of EnSight
# In this case, we use a local installation of EnSight

session = LocalLauncher().start()

###############################################################################
# Close the connection and shut down the EnSight instance

session.close()
