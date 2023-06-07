PyEnSight
=========
Version: |version|

|pyansys| |python| |coverage| |MIT| |pre-commit| |black| |isort| |bandit|

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

.. |coverage| image:: /_static/coverage.svg
   :target: https://ensight.docs.pyansys.com/dev


.. |title| image:: https://s3.amazonaws.com/www3.ensight.com/build/media/pyensight_title.png


.. toctree::
   :hidden:
   :maxdepth: 3

   getting_started/index
   user_guide/index
   class_documentation
   rest_api/rest_api
   _examples/index
   contributing

|title|

Introduction
------------
Ansys EnSight is a full-featured postprocessor and general-purpose data
visualization tool. It is capable of handling large simulation datasets
from a variety of physics and engineering disciplines. It includes the
ability to load data and analyze results from different data sources
simultaneously.

Key features include:

- Large data-tuned postprocessing
- Time-varying visualization and analysis
- Complete palette of visualization algorithms, including clips, isocontours,
  vectors, particle traces, and vortex cores
- Extensive collection of calculator functions
- Support for a large number of file formats
- High-performance rendering (local and remote)
- High-quality rendering
- Embedded Python scripting


What is PyEnSight?
------------------
PyEnSight is part of the `PyAnsys <https://docs.pyansys.com>`_ ecosystem. A
Python module that can be installed in most any Python distribution, PyEnSight
provides the ability to launch and control an EnSight instance from an external
or remote Python instance.

With PyEnSight, you can launch an EnSight instance, connect to it, and
run commands using the same syntax that the embedded Python interpreter uses.
Additionally, PyEnSight includes access to the visualization systems of EnSight
via images, geometry files, and remote HTML rendering. Because PyEnSight also
supports the object event system, you can use its interfaces to develop asynchronous,
remote, or desktop apps.

Documentation and issues
------------------------
In addition to installation and usage information, the `PyEnSight documentation
<https://ensight.docs.pyansys.com/>`_ provides API member descriptions, examples,
and contribution information.

On the `PyEnSight Issues <https://github.com/ansys/pyensight/issues>`_ page,
you can create issues to submit questions, report bugs, and request new features.
This is the best place to post questions and code.

License
-------
PyEnSight is licensed under the MIT license.

PyEnsight makes no commercial claim over Ansys whatsoever. This library extends
the functionality of Ansys EnSight by adding a remote Python interface to EnSight
without changing the core behavior or license of the original software. The use
of interactive Ansys EnSight control by PyEnSight requires a legally licensed
local copy of Ansys EnSight.

For more information on EnSight, see the `Ansys EnSight page <https://www.ansys.com/products/fluids/ansys-ensight>`_
on the Ansys website.

Project index
-------------

* :ref:`genindex`
