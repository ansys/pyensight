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

.. |title| image:: https://s3.amazonaws.com/www3.ensight.com/build/media/pyensight_title.png

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
Documentation for the latest stable release of PyEnSight is hosted at
`PyEnSight documentation <https://ensight.docs.pyansys.com/version/stable/>`_.

In the upper right corner of the documentation's title bar, there is an option for switching from
viewing the documentation for the latest stable release to viewing the documentation for the
development version or previously released versions.

You can also `view <https://cheatsheets.docs.pyansys.com/pyensight_cheat_sheet.png>`_ or
`download <https://cheatsheets.docs.pyansys.com/pyensight_cheat_sheet.pdf>`_ the
PyEnSight cheat sheet. This one-page reference provides syntax rules and commands
for using PyEnSight.

On the `PyEnSight Issues <https://github.com/ansys/pyensight/issues>`_ page, you can
create issues to report bugs and request new features. On the `Discussions <https://discuss.ansys.com/>`_
page on the Ansys Developer portal, you can post questions, share ideas, and get community feedback.

To reach the project support team, email `pyansys.core@ansys.com <pyansys.core@ansys.com>`_.

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
