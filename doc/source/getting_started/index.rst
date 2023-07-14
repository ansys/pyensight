
.. _getting_started:

===============
Getting started
===============
To use PyEnSight, you must have a locally installed and licensed copy of Ansys EnSight
2022 R2 or later.

To obtain a copy, see the `Ansys EnSight <https://www.ansys.com/products/fluids/ansys-ensight>`_
page on the Ansys website.

Install the package
-------------------
The ``ansys-pyensight-core`` package supports Python 3.8 through
Python 3.11 on Windows and Linux.

Install the latest package with this command:

.. code::

   pip install ansys-pyensight-core


If you plan on doing local *development* of PyEnSight on Linux,
install the latest package with these commands:

.. code::

   git clone https://github.com/ansys/pyensight
   cd pyensight
   pip install virtualenv
   virtualenv venv  # create virtual environment
   source venv/bin/activate  # (.\venv\Scripts\activate for Windows shell)
   pip install .[dev]   # install development dependencies


You can then start developing PyEnSight.

To build and install PyEnSight, run these commands:

.. code::

   python -m build   # build
   # this replaces the editable installation done previously. If you don't want
   # to replace, switch your virtual environments to test the new install separately.
   pip install .[tests]   # install test dependencies
   pytest  # Run the tests


Set up ``pre-commit``
---------------------
``pre-commit`` is a multi-language package manager for pre-commit hooks.


To install pre-commit into your git hooks, run this command:

.. code::

   pre-commit install

``pre-commit`` now runs on every commit. Each time that you clone a repository,
running the preceding command to install ``pre-commit`` is always the first
thing that you should do.

If you want to manually run all pre-commit hooks on a repository, run
this command:

.. code::

   pre-commit run --all-files


A bunch of formatters run on your source files.

To run individual hooks, use this command:

.. code::

   pre-commit run <hook_id>


The ``<hook_id>`` can be obtained from the ``.pre-commit-config.yaml`` file.
The first time ``pre-commit`` runs on a file, it automatically downloads,
installs, and runs the hook.


Start the EnSight session
-------------------------
The simplest way of starting an EnSight session is to use this code:

.. vale off

.. code:: python

   from ansys.pyensight.core import LocalLauncher
   session = LocalLauncher().start()


The preceding code looks for a local Ansys software installation to use to launch an
EnSight instance on the local system.

Optionally, you can start an EnSight Docker container by using code like this:

.. code:: python

   from ansys.pyensight.core import DockerLauncher
   launcher = DockerLauncher(data_directory=r"d:\data", use_dev=True)
   launcher.pull()
   session = launcher.start()

.. vale on

In the preceding code, the ``data_directory`` argument specifies the host directory
to map into the container at the mount point, providing access to the data within
the container. This provides a method for EnSight running in the container to access
the host's file system to read or write data. The optional ``use_dev=True`` argument
specifies that the latest development version of EnSight should be used.

Run commands
------------
Once an EnSight instance is running, you can use the session interface to interact with it.
The :func:`cmd<ansys.pyensight.core.Session.cmd>` method can execute any Python string
in the EnSight Python interpreter.

For example, this code returns the value 25.0:

.. code:: python

    value = session.cmd("10.*2.5")


The following code uses the :func:`load_data<ansys.pyensight.core.Session.load_data>`
method to load a dataset and render the current scene into a PNG-formatted stream.

.. code:: python

    session.load_data('D:/data/CFX/example_data.res')
    image_data = session.render(1920, 1080, aa=4)
    with open("image.png", "wb") as f:
        f.write(image_data)


The resulting image, which is rendered using 4x antialiasing, is 1920x1080 pixels.

You can use the :func:`show<ansys.pyensight.core.Session.show>` method to view or interact
with the current EnSight session via the web. This method supports creating various graphical
representations and returns URLs for viewing or interacting with these representations.

.. code:: python

    remote = session.show("remote")
    remote.browser()
