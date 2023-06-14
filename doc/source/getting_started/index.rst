
.. _getting_started:

===============
Getting started
===============
To use PyEnSight, you must have a locally installed and licensed copy of Ansys EnSight
2022 R2 or later.

To obtain a copy, see the `Ansys EnSight page <https://www.ansys.com/products/fluids/ansys-ensight>`_
on the Ansys website.

Installation
------------
The ``ansys-ensight`` package supports Python 3.7 through
Python 3.10 on Windows and Linux.

Install the latest package with this code:

.. code::

   pip install ansys-ensight


If you plan on doing local *development* of PyEnSight on Linux,
install the latest package with this code:

.. code::

   git clone https://github.com/ansys/pyensight
   cd pyensight
   pip install virtualenv
   virtualenv venv  # create virtual environment
   source venv/bin/activate
   pip install -r requirements/dev.txt  # install dependencies
   make install-dev  # install pyensight in editable mode


If you plan on doing local *development* of PyEnSight on Windows,
build the wheel using a ``pybuild.py`` script like this one:

.. code::

   git clone https://github.com/ansys/pyensight
   cd pyensight
   C:\Python310\python.exe -m pip install virtualenv
   C:\Python310\Scripts\virtualenv.exe venv
   .\venv\Scripts\activate
   .\venv\Scripts\pip.exe install -r .\requirements\dev.txt
   .\venv\Scripts\python.exe pybuild.py clean
   .\venv\Scripts\python.exe pybuild.py build


Now you can start developing PyEnSight.


Start the EnSight session
-------------------------
The simplest way of starting an EnSight session is to use this code:

.. code:: python

   from ansys.ensight.core import LocalLauncher
   session = LocalLauncher().start()


The preceding code looks for a local Ansys software installation to use to launch an
EnSight instance on the local system.

Optionally, you can start an EnSight Docker container by using code like this:

.. code:: python

   from ansys.ensight.core import DockerLauncher
   launcher = DockerLauncher(data_directory=r"d:\data", use_dev=True)
   launcher.pull()
   session = launcher.start()


The ``data_directory`` keyword specifies the host directory to map into the container at the mount
point /data within the container. This provides a method for EnSight running in the container
to access the host's file system to read or write data. The optional argument ``use_dev=True``
specifies that the latest development version of EnSight should be used.

Run commands
------------
Once an EnSight instance is running, you can use the session interface to interact with it.
The ``cmd()`` method can execute any Python string in the EnSight Python interpreter.

For example, this code returns the value 25.0:

.. code:: python

    value = session.cmd("10.*2.5")


This code uses the ``load_data()`` method to load a dataset and
render the current scene into a PNG-formatted stream:

.. code:: python

    session.load_data(r'D:\data\CFX\example_data.res')
    image_data = session.render(1920, 1080, aa=4)
    with open("image.png", "wb") as f:
        f.write(image_data)


The resulting image, which is rendered using 4x antialiasing, is 1920x1080 pixels.

You can use the ``show()`` method to view or interact with the current EnSight session
via the web. This method supports creating various graphical representations and returns URLs
for viewing or interacting with these representations.

.. code:: python

    remote = session.show("remote")
    remote.browser()
