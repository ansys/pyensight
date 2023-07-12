PyEnSight documentation |version|
=================================

.. toctree::
   :hidden:
   :maxdepth: 3

   getting_started/index
   user_guide/index
   class_documentation
   _examples/index
   contributing


Introduction
------------
Ansys EnSight is a full-featured postprocessor and general-purpose data
visualization tool. It is capable of handling large simulation datasets
from a variety of physics and engineering disciplines. It includes the
ability to load data and analyze results from different data sources
simultaneously.

EnSight provides these key features:

- Large data-tuned postprocessing
- Time-varying visualization and analysis
- Complete palette of visualization algorithms, including clips, isocontours,
  vectors, particle traces, and vortex cores
- Extensive collection of calculator functions
- Support for a large number of file formats
- High-performance rendering (local and remote)
- High-quality rendering
- Embedded Python scripting

image:: /_static/pyensight_title.png

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

.. vale off

PyEnSight makes no commercial claim over Ansys whatsoever. This library extends
the functionality of Ansys EnSight by adding a remote Python interface to EnSight
without changing the core behavior or license of the original software. The use
of interactive Ansys EnSight control by PyEnSight requires a legally licensed
local copy of Ansys EnSight.

.. vale on

For more information on EnSight, see the `Ansys EnSight <https://www.ansys.com/products/fluids/ansys-ensight>`_
page on the Ansys website.

Project index
-------------

* :ref:`genindex`
