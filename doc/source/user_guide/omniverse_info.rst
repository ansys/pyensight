.. _omniverse_info:

PyEnSight/ANSYS Omniverse Interface
===================================

This release of PyEnSight includes an interface to export the surfaces
in the current EnSight scene to an Omniverse server.  This functionality
is was developed against the "203" (2023.x) version of Omniverse.  Other
versions may or may not work.  The interface supports EnSight 2023 R2
or later.

The API is available through a PyEnSight session instance, from EnSight
Python directly as (ensight.utils.omniverse for 2025 R1 and later) and
from within Omniverse applications via the ansys.geometry.service and
ansys.geometry.serviceui kit extensions.

The Python API is defined here: :class:`Omniverse<ansys.pyensight.core.utils.omniverse.Omniverse>`.


Omniverse System Configuration
------------------------------

To use this functionality, a local installation of Omniverse is required.
Please `install Omniverse <https://docs.omniverse.nvidia.com/install-guide/>`_ along
with one application like "Create" or "View" on your local system before
attempting to use this interface.


PyEnSight and EnSight Python API
--------------------------------

The ``omniverse`` pyensight module will look for and leverage locally installed
Omniverse to provide its APIs. If you are using the
`ansys-pyensight-core <https://pypi.org/project/ansys-pyensight-core/>`_ module
in your own python, one can just use the API like this:

.. code-block:: python

    from ansys.pyensight.core import LocalLauncher
    s = LocalLauncher(batch=False).start()
    s.load_example("waterbreak.ens")
    # Start a new connection between EnSight and Omniverse
    uri = "omniverse://localhost/Users/water"
    s.ensight.utils.omniverse.create_connection(uri)
    # Do some more work...
    # Push a scene update
    s.ensight.utils.omniverse.update()


.. note::

    The ``batch=False`` option used in the examples causes the EnSight
    GUI to be displayed together with the Omniverse Composer GUI.

    Also, care must be taken to close the EnSight session before
    exiting an Omniverse application hosting a PyEnSight session or is
    it possible to leave the EnSight instance running.


From inside an EnSight session, the API is similar:

.. code-block:: python

    # Start a DSG server in EnSight first
    (_, grpc_port, security) = ensight.objs.core.grpc_server(port=0, start=True)
    # Start a new connection between the EnSight DSG server and Omniverse
    options = {"host": "127.0.0.1", "port": str(grpc_port)}
    if security:
        options["security"] = security
    uri = "omniverse://localhost/Users/water"
    ensight.utils.omniverse.create_connection(uri, options=options)
    # Do some more work...
    # Push a scene update
    ensight.utils.omniverse.update()


After running the script, the scene will appear in the Nucleus tree view as
``User/water``.  The file ``dsg_scene.usd`` can be loaded into Composer.  The
``ensight.utils.omniverse.update()`` command can be used to update the
USD data in Omniverse, reflecting any recent changes in the EnSight scene.

Starting with 2025 R1, one can also access Omniverse via an EnSight
user-defined tool:

.. image:: /_static/omniverse_tool.png

This tool will only be available if EnSight detects an installed copy
of Omniverse.  Clicking on "Connect to Omniverse" executes something
similar to the previous Python snippet and the button will change to
a mode where it just executes ``ensight.utils.omniverse.update()``.


PyEnSight/Omniverse kit from Within an Omniverse Application
------------------------------------------------------------

To install the service (and the pyensight module) into an Omniverse
application, one can install is via the third party extensions dialog.
Select the ``Extensions`` option from the ``Window`` menu.  Select
third party extensions and filter by ``ANSYS``.  Enabling the extension
will install it, along with the ansys.pyensight.core module.

.. image:: /_static/omniverse_extension.png

At this point, the same pyensight script run in the Omniverse
``Script Editor`` panel can be used to connect to
an EnSight session or the GUI panel can be used to connect to a
copy of EnSight that was launched with the ``-grpc_server {port}``
option specified.

The ``ansys.geometry.serviceui`` kit includes a GUI similar to the
EnSight 2025 R1 user-defined tool.  It allows one to select a
target URI in Omniverse and the details of a gRPC connection
to a running EnSight.  For example, if one launches EnSight with
``ensight.bat -grpc_server 2345``, then the uri:  ``grpc://127.0.0.1:2345``
can to used to request a locally running EnSight to push the current
scene to Omniverse.


.. note::

    If the ``ansys.geometry.service`` and ``ansys.geometry.serviceui``
    do not show up in the Community extensions list in Omniverse, then
    it can be added to the ``Extension Search Paths`` list as:
    ``git://github.com/ansys/pyensight.git?branch=main&dir=exts``.
