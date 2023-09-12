.. _ref_cmdlang_native:

EnSight command language native Python API
==========================================

Since its inception, EnSight has had a journaling language, commonly referred to as
the *command language*. Every operation in EnSight can be captured in command language.
Scripts can be generated using this language and played back in the GUI or in batch mode.
Furthermore, features like context files (that capture a session state) do so using
a command language variant. Command language is not documented, but it roughly follows
the :ref:`EnSight architecture <ensight_architecture>`. The :ref: `native Python API <native_api_docs>`
is a binding to this command language interface.

Command language overview
-------------------------

A command language call has this general form: :samp:`{class}: {command} [values...]`.
For example, :samp:`view_transf: rotate -4. 24. 0.` rotates the current view, and
:samp:`data: replace data.case` loads a dataset into the current case.

Commands may also follow a *begin/end* or *modify begin/end* structure, where commands
of the same class are used between the begin and end commands. This form is used to *batch*
a collection of changes into a single update operation. Finally, there is a
*select begin/end* form for expanding values onto multiple lines.

The language separates the specification of target objects and attribute changes into
separate commands. Thus, there is always a *current selection* of all objects of
a specific type, and many commands operate on the current selection. For example,
this code sets the current part selection to part number 1 and then modifies the
line width and part color::

    part: select_begin
     1
    part: select_end
    part: modify_begin
    part: line_width 2
    part: colorby_rgb 1.0 0.0 0.0
    part: modify_end


.. note::
   While most of the command language follows these two command forms, there are
   some commands that do not follow this form.

As noted previously, EnSight maintains a *default* object of every type. You can
use commands to modify most attributes on the default object. For example, you can
use the ``create`` command to create a new object instance. The following code creates
a clip by selecting the default clip object and then setting up the type and clip position
value on the default clip. It then changes the current part selection to what parts should
become the parent of the clip and calls the :samp:`clip: create` command to create the clip::

    clip: select_default
    clip: begin
    clip: domain intersect
    clip: tool xyz
    clip: value 0.5
    clip: end
    part: select_begin
     1
     2
    part: select_end
    clip: create


PyEnSight command language binding
----------------------------------

The native Python API binding is a simple syntax conversion from command language
into Python syntax. The ``command`` class is a module in Python under the ``session.ensight``
module. All values are passed as native Python parameters. For the *select/begin/end*
command form, only the ``begin`` command is used. All of the value lines can be specified
as Python parameters or a list. The previous example becomes this Python script:

.. code-block:: python

    session.ensight.clip.select_default()
    session.ensight.clip.begin()
    session.ensight.clip.domain("intersect")
    session.ensight.clip.tool("xyz")
    session.ensight.clip.value(0.5)
    session.ensight.clip.end()
    session.ensight.part.select_begin(1, 2)
    session.ensight.clip.create()


Lists of objects can be used where multiple values are specified
as parameters, which means that this syntax is also valid:

.. code-block:: python

    session.ensight.part.select_begin([1, 2])
    session.ensight.part.modify_begin()
    session.ensight.part.colorby_rgb([0.0, 0.0, 1.0])
    session.ensight.part.modify_end()


Native API debugging
^^^^^^^^^^^^^^^^^^^^

Every command also returns an error code, which is ``0`` on success. For example,
:samp:`err = session.ensight.part.colorby_rgb([0.0,0.0,"sad"])` sets ``err`` to ``-1``.
You can use the :func:`attrtree<ansys.api.pyensight.ensight_api.ensight.sendmesgoptions>`
method to enable Python exception handling instead of returning an error code. You should
use the :func:`attrtree<ansys.api.pyensight.ensight_api.ensight.sendmesgoptions>`
method when debugging native API scripts.

.. note::
    Because the exception setting is global, care should be taken to reset the error
    handling status on an error to ensure proper EnSight operation.


This example shows how you can convert error return values into exceptions:

.. code-block:: python

    try:
        session.ensight.sendmesgoptions(exception=True)
        session.ensight.part.select_begin([1, 2])
        session.ensight.part.colorby_rgb([0.0,0.0,"sad"])
    except RuntimeError as e:
        print("Error", e)
    finally:
        session.ensight.sendmesgoptions(exception=False)


The code prints this error:

:samp:`RuntimeError: Command: (part: colorby_rgb 0.0 0.0 sad ) returned: RGB color: bad parameter`


GUI conversion
--------------
There is a built-in mechanism to convert code in command language into Python. To do this,
you first paste the command language into the Python editor. On EnSight's **Execution** tab,
you can use the right-mouse button menu to select and copy lines of command language.

Next, select the text in the editor and use the **Edit** menu to select either
the **Convert selection to sendmesg()** or **Convert selection to native Python**
option. In general, the native Python conversion results in much more readable Python code
that is far easier to edit than the **Convert selection to sendmesg()** option. You should
use the **Convert selection to native Python** option for all but legacy development.

The **File** menu provides two items to execute the current file text in the EnSight Python
interpreter. The **Run script** option causes the file contents to be executed in the global
namespace (for example, like the ``execfile()`` function). The **Import script as module**
option first saves the current file to disk and then executes a Python import operation on the
file, which executes in a private namespace. Both options verify the syntax of the current
file and allow for rapid prototyping.

Special cases
-------------

There are a number of commands in the EnSight command language that are not valid
Python names. Here are a few examples::

    function: #_of_levels 5
    annotation: 3d_label_size 10.0
    command: print "hello"
    viewport: raise

Here are some reasons that a name might be invalid:

* Name contains an invalid character (such as ``#``).

* Name begins with a digit (such as ``1``).

* Name is a Python-reserved word (such as ``raise``).

Invalid names are transformed using these rules:

* ``#`` characters are replaced with the text *number*.

* Names that start with a digit are prefixed with an underscore (_).

* Names that are the same as a Python-reserved word are prefixed with an underscore (_).

The previous examples are transformed as follows:

.. code-block:: python

    session.ensight.function.number_of_levels(5)
    session.ensight.annotation._3d_label_size(10.0)
    session.ensight.command.print("hello")
    session.ensight.viewport._raise()


.. _selection_transfer:

Selection and the object API
----------------------------

The native API maintains a notion of a *current selection* with a collection
of commands to manipulate it, such as :func: `select_begin()<ansys.api.pyensight.ensight_api.part.select_begin>`.
The object API reflects the EnSight GUI via SELECTED attributes and selection ``ENS_GROUP`` objects.
Due to the implicit nature of the native API, until it is used, the native selection
is not reflected in EnSight objects. When using both APIs in a single script, it can
become necessary to synchronize the two notions of selection. This is done with the
the :func:`get_mainpartlist_select()<ansys.api.pyensight.ensight_api.part.get_mainpartlist_select>`
command. This command sets the native selection to match the object selection. For example, this
code allows the object selection mechanisms to be used to set up the part selection for
subsequent native commands:

.. code-block:: python

    p = session.ensight.objs.core.PARTS["rear body"][0]
    session.ensight.objs.core.selection().addchild(p, replace=1)
    session.ensight.part.get_mainpartlist_select()
    session.ensight.part.modify_begin()
    session.ensight.part.colorby_rgb(0.0,1.0,0.0)
    session.ensight.part.modify_end()


.. _ensight_to_pyensight:

Convert existing EnSight scripts to PyEnSight
---------------------------------------------

PyEnSight has been designed to be fully compatible with the existing EnSight Python language,
supporting both the *native* Python API and the *object* API. Indeed, the ``ensight`` attribute
of a PyEnSight ``session`` object is a *clone* of the ``ensight`` module generated via
introspection. This means that any attribute, object, instance, variable, and more
available in the ``ensight`` module is also available in PyEnSight, which manages the
communication with EnSight and the conversion of a command to its corresponding EnSight counterpart.
However, you must make a few adjustments to port an existing EnSight script into
PyEnSight. Here is a list of operations to perform to make the conversion:

* All the calls to the ``ensight`` module and its attributes must be pre-fixed
  with the current session instance. For example:

.. code-block:: python

    # Old syntax
    # ensight.objs.core.PARTS
    # New syntax
    session.ensight.objs.core.PARTS

* The ``ensight`` module cannot be imported anymore because it is an attribute of the PyEnSight ``session`` object.
  However, you can use the ``scoped_name`` utility to mimic the syntax that you would obtain importing a module
  or a submodule:

.. code-block:: python

    # Remove previous imports
    # import ensight
    # from ensight.objs import *
    # from ensight.objs import core

    # Create a ``scoped_name`` instance
    sn = session.ensight.utils.support.scoped_name

    # Create a context manager with the ``scoped_name`` instance, where you can
    # use the old syntax

    with sn(session.ensight) as ensight, sn(session.ensight.objs.core) as core:
        core.PARTS[0].DESCRIPTION
        ensight.view.bounds("ON")

* The main advantage of using the ``scoped_Name`` instance is that the new syntax is also
  supported directly in EnSight. This greatly simplifies the porting of a PyEnSight script
  into EnSight.




