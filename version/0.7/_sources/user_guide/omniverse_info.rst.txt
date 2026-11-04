.. _omniverse_info:

BETA: Omniverse Interface
=========================

This release of PyEnSight includes a technical preview of an interface
to export the surfaces in the current EnSight scene to an Omniverse
server.  This functionality is was developed against the "203" (2023.x)
version of Omniverse.  Other versions may or may not work.  The interface
supports EnSight 2023 R2 or later.

Python Interpreter Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To use this functionality, an installation of Omniverse is required
and the PyEnSight module must be used from within an Omniverse
Python interpreter.  In most cases, the script editor in the USD
Composer application.  To install PyEnSight into the Composer Python
interpreter the following script can be run in the embedded script
editor (``Windows->Script Editor`` menu):

.. code-block::

    import omni.kit.pipapi
    omni.kit.pipapi.install("ansys-pyensight-core")


It is also possible to install the module using the command line.
To do this, one needs to find the installation location of the target
tool.  Looking at the settings for "Create":

.. image:: /_static/omniverse_create_location.png

the install path can be found in the Omniverse GUI and the following
may be run:

.. code-block:: shell

    cd C:\Users\sampleuser\AppData\Local\ov\pkg\create-2023.2.5
    kit\python.bat -m pip install ansys-pyensight-core


to install pyensight.

Basic Example
^^^^^^^^^^^^^

The following can be run from inside the USD Composer script panel following
the previous install.  It can also be executed by the ``kit\python.bat``
interpreter, same as the one used during the configuration step.
It assumes there is a local Nucleus server running that can be accessed
via the URI: ``omniverse://localhost/Users/water``.

.. code-block:: python

    from ansys.pyensight.core import LocalLauncher
    s = LocalLauncher(batch=False).start()
    s.load_example("waterbreak.ens")
    uri = "omniverse://localhost/Users/water"
    s.ensight.utils.omniverse.create_connection(uri)


After running the script, scene will appear in the Nucleus tree view as ``User/water``.
The file ``dsg_scene.usd`` can be loaded into Composer.  The
``s.ensight.utils.omniverse.update()`` command can be used to update the
USD data in Omniverse, reflecting any recent changes in the EnSight scene.

.. note::

    The ``batch=False`` option cause the EnSight GUI to be displayed
    together with the Omniverse Composer GUI.  Also, care must be taken
    to close the EnSight session before exiting Composer or is it possible
    to leave the EnSight instance running.

