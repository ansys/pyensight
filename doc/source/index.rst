PyEnSight  documentation |version|
==================================

.. |title| image:: https://s3.amazonaws.com/www3.ensight.com/build/media/pyensight_title.png


.. toctree::
   :hidden:
   :maxdepth: 3

   getting_started/index
   class_documentation

|title|

Introduction
------------
Ansys EnSight is a full-featured post-processor and general-purpose data
visualization tool. It is capable of handling large simulation datasets
from a variety of physics and engineering disciplines. It includes the
ability to load data from and analyze results from different data sources
simultaneously.

Key features include:

- Large data tuned post-processing
- Time varying visualization and analysis
- Complete palette of visualization algorithms: clips, isocontours, vectors, particle traces, vortex cores, etc
- Extensive collection of calculator functions
- Support for a large number of file formats
- High-performance rendering (local and remote)
- High-quality rendering
- Embedded Python scripting


What is PyEnSight?
------------------
PyEnSight is part of the `PyAnsys <https://docs.pyansys.com>`_ ecosystem. It is a
Python module that can be installed in most any Python distribution that provides
the ability to launch and control an EnSight instance from an external/remote Python
instance.

It provides the ability to launch an EnSight instance, connect to it and
run commands using the same syntax as the embedded Python interpreter uses.
PyEnSight also includes access to the visualization systems of EnSight via
images, geometry files and remote HTML rendering. The object event system
is also supported, making it possible to develop asynchronous, remote or
desktop applications using the PyEnSight interfaces.

Documentation and issues
------------------------
Please see the latest release `documentation <https://furry-waffle-422870de.pages.github.io/>`_
page for more details.

Please feel free to post issues and other questions at `PyEnSight Issues
<https://github.com/pyansys/pyensight/issues>`_.  This is the best place
to post questions and code.

License
-------
``PyEnSight`` is licensed under the MIT license.

This module, ``ansys-pyensight`` makes no commercial claim over Ansys whatsoever.
This tool extends the functionality of ``Ansys EnSight`` by adding a remote Python
interface to EnSight without changing the core behavior or license of the original
software. The use of interactive ``Ansys EnSight`` ``control by ``PyEnSight`` requires
a legally licensed local copy of ``Ansys EnSight``.

To obtain a copy, please visit `Ansys EnSight <https://www.ansys.com/products/fluids/ansys-ensight>`_.

Project index
-------------

* :ref:`genindex`
