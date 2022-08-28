
.. _getting_started:

===============
Getting started
===============
You will need a locally installed and licensed copy of ``Ansys EnSight`` to use  ``PyEnSight``,
with the first supported version being 2022 R2.

To obtain a copy, please visit `Ansys EnSight <https://www.ansys.com/products/fluids/ansys-ensight>`_.

Installation
------------
The ``ansys-pyensight`` package currently supports Python 3.7 through
Python 3.10 on Windows and Linux.

Install the latest ansys-pyensight release with:

.. code::

   pip install ansys-pyensight

For a local, "development" version:

.. code::

   git clone https://github.com/pyansys/pyensight
   cd pyensight
   pip install virtualenv
   virtualenv venv  # create virtual environment
   source venv/bin/activate  # (.\venv\Scripts\activate for Windows shell)
   pip install -r requirements/dev.txt  # install dependencies
   make install-dev  # install pyensight in editable mode

Now you can start developing pyensight.


Starting the EnSight session
----------------------------
The simplest PyEnSight session may be started like this:

.. code:: python

   from ansys.pyensight import LocalLauncher
   session = LocalLauncher().start()

This code will look for a local Ansys software installation a use it to launch an
EnSight instance on the local system.

Optionally, PyEnSight can work with an EnSight Docker container like this:

.. code:: python

   from ansys.pyensight import DockerLauncher
   launcher = DockerLauncher(data_directory=r"d:\data", use_dev=True)
   launcher.pull()
   session = launcher.start()

The ``data_directory`` keyword specifies the host directory to map into the container at the mount
point /data within the container. This provides a method for EnSight running in the container
to access the host's file system to read or write data.  The optional argument ``use_dev=True``
specifies that the latest development version of EnSight should be used.

Running commands
----------------
At this point, the session interface may be used to interact with the running
EnSight instance.   The 'cmd()' method will execute any Python string in
the EnSight Python interpreter:

.. code:: python

    value = session.cmd("10.*2.5")

will return the value 25.0.  One may load a dataset using the ``load_data()`` method and
render the current scene into a png formatted stream with:

.. code:: python

    session.load_data(r'D:\data\CFX\example_data.res')
    image_data = session.render(1920, 1080, aa=4)
    with open("image.png", "wb") as f:
        f.write(image_data)

The resulting image will be 1920x1080 and will have been rendered using 4x antialiasing.

The current EnSight session can be viewed/interacted with via the web using the ``show()``
method.  The method can create various graphical representations and will return a URL
that can be used to view/interact with the representation.

.. code:: python

    import webbrowser
    remote = session.show("remote")
    remote.browser()
