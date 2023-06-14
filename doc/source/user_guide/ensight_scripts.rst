.. _ref_ensight_scripts:

EnSight Python Scripts: Running and Debugging
=============================================

EnSight supports the notion of a "Python script", a parallel construct to the command language
journaling script, the ".enc" file.  This is a file of Python commands that can be directly
run from the EnSight command line or via the Python script editor built into EnSight.
Many EnSight Python scripts are written using the 'Python' tab script editor in the command
dialog, often by translating EnSight command language into Python via the built-in tools.
An example of such a script might be::

    ensight.legend.select_palette_begin("Coordinates")
    ensight.legend.visible("ON")
    ensight.part.select_begin(4)
    ensight.variables.activate("Coordinates")
    ensight.part.modify_begin()
    ensight.part.colorby_palette("Coordinates")
    ensight.part.modify_end()
    ensight.legend.select_palette_begin("Coordinates")
    ensight.legend.visible("ON")


Which is effectively line by line translation from EnSight command language into the native
Python bindings (:ref:`ref_cmdlang_native`).  Such scripts can be executed by the script
editor "Run script" or the "Import script as module" commands.
As one might note, these scripts assume that the 'ensight' module has been imported, making
it difficult to run them from inside of a PyEnSight session, where the ``ensight`` module is a
property of the :class:`Session<pyensight.Session>` object instance.


Running EnSight Python Scripts
------------------------------

It is possible to run such scripts in PyEnSight using the ``Session.run_script()`` command.
For example, if one has an EnSight Python script named ``"/home/ensight/example.py"``, then
the following session can be used to run the script via the PyEnSight module::

    from ansys.ensight.core import LocalLauncher

    session = LocalLauncher().start()
    _ = session.run_script("/home/ensight/example.py")


This will cause the file ``example.py`` to be imported into the interpreter.  This will result in
an ``example`` module being imported.  The imported module will have the symbol ``ensight`` set to
the current session ``ensight`` property and will use that interface to execute the script
commands remotely.


Debugging EnSight Python Scripts
--------------------------------

A common request is to be able to write and debug EnSight Python scripts in integrated development
environments (IDEs) like Visual Studio Code.  One example would include a file
named ``example.py``::

    for vp in ensight.objs.core.VPORTS:
        print(vp.DESCRIPTION)


A launching script ``runme.py`` in the same directory might have this content::

    from ansys.ensight.core import LocalLauncher

    session = LocalLauncher(batch=False).start()
    _ = session.run_script("./example.py")


In Visual Studio Code one can put a breakpoint on the print() line and debug the example.py
script when the script ``runme.py`` is run in debug mode from Visual Studio Code.
Note that in this example, ``batch=False`` is specified in the LocalLauncher constructor.
This will cause the EnSight GUI to be displayed as well, enabling direct interaction with the
full EnSight application and debugging.


Limitations
-----------

It is important to note that there are some important differences between an EnSight Python
script run in EnSight vs in an IDE via the PyEnSight interface.

Note, using this method will cause the directory containing the EnSight Python script to be
added to ``sys.path``, if it has not been already.


Speed
`````

There is a significant difference in the speed with which the code can be executed.  This
is because the ``ensight`` commands will be executed remotely and the results returned.  The
work-around for this is to use the Session.exec() method, but it requires that the code
in the Python script must be re-written as a function.  In debugging situations, this may
not be a major issue.


'ensight' module
````````````````

Another difference is that the nature of the ``ensight`` object in the script is very different.
When running in EnSight, it is a true Python module.   When running via ``run_script()``, the object
is an instance of the ``ensight_api`` class.  In general, these both provide the same API, but
it is not identical.  This, this approach includes the general API limitations
described here :ref:`api_differences`.


Import vs run
`````````````

The ``run_script()`` method always uses the module import mechanism to "run" the scripts.
EnSight Python scripts that do not run in the EnSight script editor using the
"Import script as module" menu, cannot be used with this system.
