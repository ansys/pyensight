.. _ref_ensight_scripts:

EnSight Python scripts: Running and debugging
=============================================

EnSight supports the notion of a Python script, a parallel construct to the command language
journaling script (``.enc`` file). This script is a file of Python commands that can be directly
run from the EnSight command line or via the Python script editor built into EnSight.
Many EnSight Python scripts are written using the **Python** tab script editor in the command
dialog, often by translating EnSight command language into Python via the built-in tools.

Here is an example of such a script::

    ensight.legend.select_palette_begin("Coordinates")
    ensight.legend.visible("ON")
    ensight.part.select_begin(4)
    ensight.variables.activate("Coordinates")
    ensight.part.modify_begin()
    ensight.part.colorby_palette("Coordinates")
    ensight.part.modify_end()
    ensight.legend.select_palette_begin("Coordinates")
    ensight.legend.visible("ON")


The preceding script is effectively a line-by-line translation from the EnSight command
language into the native Python bindings (:ref:`ref_cmdlang_native`). Such scripts can be
executed by the script editor's **Run script** or **Import script as module** commands.
These scripts assume that the ``ensight`` module has been imported, making
it difficult to run them from inside of a PyEnSight session, where the ``ensight`` module is a
property of the :class:`Session<pyensight.Session>` object instance.


Running EnSight Python scripts
------------------------------

To run scripts like the one in the preceding example in PyEnSight, you use the
:func:`run_script<ansys.pyensight.core.Session.run_script>` method. For example,
assume that you have an EnSight Python script named ``"/home/ensight/example.py"``.
You can use this code to run this script via the PyEnSight module::

    from ansys.pyensight.core import LocalLauncher

    session = LocalLauncher().start()
    _ = session.run_script("/home/ensight/example.py")


The preceding code imports the ``example.py`` file into the interpreter. This results in
an ``example`` module being imported. The imported module has the symbol ``ensight`` set to
the current session ``ensight`` property and uses that interface to execute the script
commands remotely.


Debugging EnSight Python scripts
--------------------------------

A common request is to be able to write and debug EnSight Python scripts in integrated development
environments (IDEs) like Visual Studio Code. Assume that you have a file
named ``example.py``::

    for vp in ensight.objs.core.VPORTS:
        print(vp.DESCRIPTION)


In the same directory, assume that you have a launching script, ``runme.py``::

    from ansys.pyensight.core import LocalLauncher

    session = LocalLauncher(batch=False).start()
    _ = session.run_script("./example.py")


In Visual Studio Code, you can insert a breakpoint on the ``print()`` line and debug the
``example.py`` script when the ``runme.py`` script is run in debug mode from Visual Studio Code.
Note that in this example, ``batch=False`` is specified in the ``LocalLauncher`` constructor.
This causes the EnSight GUI to display as well, enabling direct interaction with the
full EnSight app and debugging.


Limitations
-----------

It is important to note that there are some important differences between an EnSight Python
script run in EnSight versus in an IDE via the PyEnSight interface.

Using the :func:`run_script<ansys.pyensight.core.Session.run_script>` method causes the directory
containing the EnSight Python script to be added to ``sys.path``, if it is not already added.


Speed
`````

There is a significant difference in the speed with which the code can be executed. This
is because the ``ensight`` commands are executed remotely and the results are returned. The
workaround for this is to use the :func:`exec<ansys.pyensight.core.Session.exec>`
method, but it requires that the code in the Python script be rewritten as a function.
In debugging situations, this may not be a major issue.


``ensight`` module
```````````````````

Another difference is that the nature of the ``ensight`` object in the script is very different.
When running in EnSight, it is a true Python module. When running via the
:func:`run_script<ansys.pyensight.core.Session.run_script>` method, the object
is an instance of the ``ensight_api`` class. In general, these both provide the same API, but
they are not identical. This approach includes the general API limitations
described in :ref:`api_differences`.


Import versus run
`````````````````

The :func:`run_script<ansys.pyensight.core.Session.run_script>` method always uses
the module import mechanism to "run" the scripts. EnSight Python scripts that do not
run in the EnSight script editor using the **Import script as module** menu command
cannot be used with this system.
