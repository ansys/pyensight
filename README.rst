PyEnSight
=========
|pyansys| |python| |ci| |MIT| |pre-commit| |black| |isort| |bandit|

.. |pyansys| image:: https://img.shields.io/badge/Py-Ansys-ffc107.svg?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAABDklEQVQ4jWNgoDfg5mD8vE7q/3bpVyskbW0sMRUwofHD7Dh5OBkZGBgW7/3W2tZpa2tLQEOyOzeEsfumlK2tbVpaGj4N6jIs1lpsDAwMJ278sveMY2BgCA0NFRISwqkhyQ1q/Nyd3zg4OBgYGNjZ2ePi4rB5loGBhZnhxTLJ/9ulv26Q4uVk1NXV/f///////69du4Zdg78lx//t0v+3S88rFISInD59GqIH2esIJ8G9O2/XVwhjzpw5EAam1xkkBJn/bJX+v1365hxxuCAfH9+3b9/+////48cPuNehNsS7cDEzMTAwMMzb+Q2u4dOnT2vWrMHu9ZtzxP9vl/69RVpCkBlZ3N7enoDXBwEAAA+YYitOilMVAAAAAElFTkSuQmCC
   :target: https://docs.pyansys.com/

.. |python| image:: https://img.shields.io/badge/Python-%3E%3D3.9-blue.svg
   :target: https://nexusdemo.ensight.com/docs/python/html/Python.html

.. |MIT| image:: https://img.shields.io/badge/License-MIT-yellow.svg
   :target: https://opensource.org/licenses/MIT

.. |black| image:: https://img.shields.io/badge/code_style-black-000000.svg
   :target: https://github.com/psf/black

.. |isort| image:: https://img.shields.io/badge/imports-isort-%231674b1.svg?style=flat&labelColor=ef8336
   :target: https://pycqa.github.io/isort/

.. |pre-commit| image:: https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white
   :target: https://github.com/pre-commit/pre-commit

.. |bandit| image:: https://img.shields.io/badge/security-bandit-yellow.svg
    :target: https://github.com/PyCQA/bandit
    :alt: Security Status

.. |ci| image:: https://github.com/ansys/pyensight/actions/workflows/ci_cd.yml/badge.svg?branch=main
   :target: https://github.com/ansys/pyensight/actions?query=branch%3Amain

.. |title| image:: https://s3.amazonaws.com/www3.ensight.com/build/media/pyensight_title.png

.. _EnSight: https://www.ansys.com/products/fluids/ansys-ensight


Overview
--------
PyEnSight is a Python wrapper for EnSight_, the Ansys simulation postprocessor.
It supports Pythonic access to EnSight so that you communicate directly with it
from Python. With PyEnSight, you can perform these essential actions:

* Start a new EnSight session or connect to an existing one.
* Read simulation data from any supported solver output format into the session.
* Generate complex postprocessing results in a Pythonic fashion.
* Visualize the processed data, extract it, or get a widget to embed it in an external app.

Documentation and Issues
------------------------
For comprehensive information on PyEnSight, see the latest release
`documentation <https://ensight.docs.pyansys.com/>`_.

On the `PyEnSight Issues <https://github.com/ansys/pyensight/issues>`_
page, you can create issues to submit questions, report bugs, and
request new features. This is the best place to post questions and code.

Installation
------------
To use PyEnSight, you must have a locally installed and licensed copy of
Ansys EnSight 2022 R2 or later. The ``ansys-pyensight-core`` package supports
Python 3.8 through Python 3.11 on Windows and Linux.

Two modes of installation are available:

- User installation
- Developer installation

User installation
~~~~~~~~~~~~~~~~~
Install the latest release from `PyPI <https://pypi.org/project/ansys-optislang-core/>`_
with this command:

.. code::

   pip install ansys-pyensight-core


Developer installation
~~~~~~~~~~~~~~~~~~~~~~
If you plan on doing local *development* of PyEnSight with GitHub, consider
using a `virtual environment <https://docs.python.org/3/library/venv.html>`_.

To clone PyEnSight and then install it in a virtual environment, run these
commands:

.. code::

   git clone https://github.com/ansys/pyensight
   cd pyensight
   pip install virtualenv
   virtualenv venv  # create virtual environment
   source venv/bin/activate  # (.\venv\Scripts\activate for Windows shell)
   pip install .[dev]   # install development dependencies

A developer installation allows you to edit ``ansys-pyensight`` files locally.
Any changes that you make are reflected in your setup after restarting the
Python kernel.

To build and install PyEnSight, run these commands:

.. code::

   python -m build   # build
   # this will replace the editable install done previously. If you don't want to replace,
   # switch your virtual environments to test the new install separately.
   pip install .[tests]   # install test dependencies
   pytest  # Run the tests

Pre-commit setup
----------------

``pre-commit`` is a multi-language package manager for pre-commit hooks.


To install pre-commit into your git hooks, run this command:

.. code::

   pre-commit install

``pre-commit`` then runs on every commit. Each time you clone a project,
installing ``pre-commit`` should always be the first action that you take.

If you want to manually run all pre-commit hooks on a repository, run this
command:

.. code::

   pre-commit run --all-files

A bunch of formatters run on your source files.

To run individual hooks, use this command, where ``<hook_id>`` is obtained from
from the ``.pre-commit-config.yaml`` file:

.. code::

   pre-commit run <hook_id>

The first time pre-commit runs on a file, it automatically downloads, installs,
and runs the hook.


Local GitHub actions
--------------------
Simulating GitHub Actions on your local desktop is recommended. After installing the
`act <https://github.com/nektos/act#readme>`_ package, you can run a job. For
example, this command runs the ``docs`` job defined in the ``ci_cd.yml`` file:

.. code::

   act -j docs

Deploy and upload steps **must always** be ignored. If they are not ignored, before
running a job, add ``if: ${{ !env.ACT }}`` to the workflow step (and commit if required).

Usage
-----
You can use this code to start the simplest PyEnSight session:

.. code:: python

   >>> from ansys.pyensight.core import LocalLauncher
   >>> session = LocalLauncher().start()
   >>> data = session.render(1920, 1080, aa=4)
   >>> with open("image.png", "wb") as f:
   ...    f.write(data)


Optionally, EnSight can work with an EnSight Docker container using code like this:

.. code:: python

   >>> from ansys.pyensight.core import DockerLauncher
   >>> launcher = DockerLauncher(data_directory="d:/data", use_dev=True)
   >>> launcher.pull()
   >>> session = launcher.start()
   >>> data = session.render(1920, 1080, aa=4)
   >>> with open("image.png", "wb") as f:
   ...    f.write(data)


In the preceding code, the ``data_directory`` argument specifies the host directory
to map into the container at the mount point, providing access to the data within
the container. This provides a method for EnSight running in the container to access
the host's file system to read or write data. The optional ``use_dev=True`` argument
specifies that the latest development version of EnSight should be used.

Also, PyEnSight can be launched as other PyAnsys products with the ``launch_ensight`` method:

.. code:: python

   >>> from ansys.pyensight.core import launch_ensight
   >>> session = launch_ensight(use_sos=3)
   >>> data = session.render(1920, 1080, aa=4)
   >>> with open("image.png", "wb") as f:
   ...    f.write(data)


Dependencies
------------
You will need a locally installed and licensed copy of Ansys to run EnSight, with the
first supported version being Ansys 2022 R2.


Documentation and Issues
------------------------
Please see the latest release `documentation <https://ensight.docs.pyansys.com/>`_
page for more details.

Please feel free to post issues and other questions at `PyEnSight Issues
<https://github.com/ansys/pyensight/issues>`_. This is the best place
to post questions and code.

License
-------
PyEnSight is licensed under the MIT license.

PyEnsight makes no commercial claim over Ansys whatsoever. This library extends the functionality
of Ansys EnSight by adding a remote Python interface to EnSight without changing the core behavior
or license of the original software. The use of interactive control of PyEnSight requires a
legally licensed local copy of Ansys.

For more information on EnSight, see the `Ansys Ensight <https://www.ansys.com/products/fluids/ansys-ensight>`_
page on the Ansys website.
