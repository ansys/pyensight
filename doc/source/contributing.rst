.. _ref_contributing:

==========
Contribute
==========
Overall guidance on contributing to a PyAnsys library appears in the
`Contributing <https://dev.docs.pyansys.com/how-to/contributing.html>`_ topic
in the *PyAnsys Developer's Guide*. Ensure that you are thoroughly familiar with
this guide before attempting to contribute to PyEnSight.
 

Post issues
-----------
Use the `PyEnSight Issues <https://github.com/pyansys/pyensight/issues>`_ page to
submit questions, report bugs, and request new features.


Adhere to code style
--------------------
PyEnSight is compliant with the `Coding style <https://dev.docs.pyansys.com/coding-style/index.html>`_
documented in the *PyAnsys Developer's Guide*. It uses the tool
`pre-commit <https://pre-commit.com/>`_ to check the code style. You can
install and activate this tool with this code:

.. code:: bash

   python -m pip install pre-commit
   pre-commit install


Once ``pre-commit`` is installed, you can directly execute this tool with this command:

.. code:: bash

    pre-commit run --all-files --show-diff-on-failure

