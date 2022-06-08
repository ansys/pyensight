PyEnSight
=========
|pyansys| |MIT|

.. |pyansys| image:: https://img.shields.io/badge/Py-Ansys-ffc107.png?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAABDklEQVQ4jWNgoDfg5mD8vE7q/3bpVyskbW0sMRUwofHD7Dh5OBkZGBgW7/3W2tZpa2tLQEOyOzeEsfumlK2tbVpaGj4N6jIs1lpsDAwMJ278sveMY2BgCA0NFRISwqkhyQ1q/Nyd3zg4OBgYGNjZ2ePi4rB5loGBhZnhxTLJ/9ulv26Q4uVk1NXV/f///////69du4Zdg78lx//t0v+3S88rFISInD59GqIH2esIJ8G9O2/XVwhjzpw5EAam1xkkBJn/bJX+v1365hxxuCAfH9+3b9/+////48cPuNehNsS7cDEzMTAwMMzb+Q2u4dOnT2vWrMHu9ZtzxP9vl/69RVpCkBlZ3N7enoDXBwEAAA+YYitOilMVAAAAAElFTkSuQmCC
   :target: https://docs.pyansys.com/

.. |MIT| image:: https://img.shields.io/badge/License-MIT-yellow.png
   :target: https://opensource.org/licenses/MIT

.. _EnSight: https://www.ansys.com/products/fluids/ansys-ensight

.. |title| image:: https://s3.amazonaws.com/www3.ensight.com/build/media/pyensight_title.png

Overview
--------
This repository contains the pythonic API to EnSight_, the Ansys Post
Processor. This API allows the user to:

* Start an EnSight session, or connect to an existing one.
* Read simulation data into the session.
* Generate complex post-processing results in a pythonic fashion.

The user can then choose to visualize the processed data, extract it, or
get a widget to embed in an external application.

|title|


Installation
------------
Include installation directions.  Note that this README will be
included in your PyPI package, so be sure to include ``pip``
directions along with developer installation directions.  For example.

Install ansys-pyensight with:

.. code::

   pip install ansys-pyensight

Alternatively, clone and install in development mode with:

.. code::

   git clone https://github.com/pyansys/pyensight
   cd src
   pip install poetry
   poetry install

This creates a new virtual environment, which can be activated with

.. code::

   poetry shell

Documentation
-------------
Include a link to the full sphinx documentation.  For example `PyAnsys <https://docs.pyansys.com/>`_


Usage
-----
The simplest PyEnSight session may be started like this:

.. code:: python

   >>> from ansys.pyensight import Launcher
   >>> session = Launcher.local_session()
   >>> session.show(render='envnc')


Testing
-------
You can feel free to include this at the README level or in CONTRIBUTING.md


License
-------
``PyEnSight`` is licensed under the MIT license.

This module, ``ansys-pyensight`` makes no commercial claim over Ansys whatsoever.
This tool extends the functionality of ``EnSight`` by adding a remote Python interface
to EnSight without changing the core behavior or license of the original
software.  The use of interactive EnSight control by ``PyEnSight`` requires a
legally licensed local copy of Ansys.

To get a copy of Ansys, please visit `Ansys <https://www.ansys.com/>`_.
