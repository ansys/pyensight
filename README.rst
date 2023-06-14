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
This repository contains the pythonic API to EnSight_, the Ansys simulation Post
Processor. This API allows the user to:

* Start an EnSight session, or connect to an existing one.
* Read simulation data (from any of the supported solver output formats) into the session.
* Generate complex post-processing results in a pythonic fashion.

The user can then choose to visualize the processed data, extract it, or
get a widget to embed in an external application.

|title|


Installation
------------
Include installation directions.  Note that this README will be
included in your PyPI package, so be sure to include ``pip``
directions along with developer installation directions.  For example.

Install ansys-ensight with:

.. code::

   pip install ansys-ensight


Development
-----------

To clone and install in development mode:

.. code::

   git clone https://github.com/ansys/pyensight
   cd pyensight
   pip install virtualenv
   virtualenv venv  # create virtual environment
   source venv/bin/activate  # (.\venv\Scripts\activate for Windows shell)
   pip install -r requirements/dev.txt  # install dependencies
   make install-dev  # install pyensight in editable mode

Now you can start developing pyensight.

To build and install pyensight:

.. code::

   make clean  # clean
   make build   # build
   # this will replace the editable install done previously. If you don't want to replace,
   # switch your virtual environments to test the new install separately.
   make install
   make smoketest  # test import


Pre-commit setup:

``pre-commit`` is a multi-language package manager for pre-commit hooks.


To install pre-commit into your git hooks, run:

.. code::

   pre-commit install

pre-commit will now run on every commit. Every time you clone a project using pre-commit, this should always be the first thing you do.

If you want to manually run all pre-commit hooks on a repository, run:

.. code::

   pre-commit run --all-files

This will run a bunch of formatters on your source files.

To run individual hooks, use:

.. code::

   pre-commit run <hook_id>

``<hook_id>`` can be obtained from ``.pre-commit-config.yaml``.
The first time pre-commit runs on a file, it will automatically download, install, and run the hook.


Local GitHub actions:

To simulate GitHub Actions on your local desktop (recommended), install `act <https://github.com/nektos/act#readme>`_.
To run a job, for example - ``docs`` from ``ci_cd.yml``, use:

.. code::

   act -j docs

Deploy and upload steps **must always** be ignored. If not, please add ``if: ${{ !env.ACT }}`` to the workflow step (and commit if required) before running.


Usage
-----
The simplest PyEnSight session may be started like this:

.. code:: python

   >>> from ansys.ensight.core import LocalLauncher
   >>> session = LocalLauncher().start()
   >>> data = session.render(1920, 1080, aa=4)
   >>> with open("image.png", "wb") as f:
   ...    f.write(data)


Optionally, PyEnSight can work with an EnSight Docker container like this:

.. code:: python

   >>> from ansys.ensight.core import DockerLauncher
   >>> launcher = DockerLauncher(data_directory="d:/data", use_dev=True)
   >>> launcher.pull()
   >>> session = launcher.start()
   >>> data = session.render(1920, 1080, aa=4)
   >>> with open("image.png", "wb") as f:
   ...    f.write(data)

The ``data_directory`` specifies the host directory to map into the container at the mount point /data within
the container. This provides a method for EnSight running in the container to access the host's file system
to read or write data.  The optional argument ``use_dev=True`` specifies that the latest development version
of EnSight should be used.


Dependencies
------------
You will need a locally installed and licensed copy of Ansys to run EnSight, with the
first supported version being Ansys 2022 R2.


Documentation and Issues
------------------------
Please see the latest release `documentation <https://ensight.docs.pyansys.com/>`_
page for more details.

Please feel free to post issues and other questions at `PyEnSight Issues
<https://github.com/ansys/pyensight/issues>`_.  This is the best place
to post questions and code.


License
-------
``PyEnSight`` is licensed under the MIT license.

This module, ``ansys-ensight`` makes no commercial claim over Ansys whatsoever.
This tool extends the functionality of ``EnSight`` by adding a remote Python interface
to EnSight without changing the core behavior or license of the original
software.  The use of interactive EnSight control by ``PyEnSight`` requires a
legally licensed local copy of Ansys.

To get a copy of Ansys, please visit `Ansys <https://www.ansys.com/>`_.
