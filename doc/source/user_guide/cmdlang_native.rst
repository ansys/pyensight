.. _ref_cmdlang_native:

EnSight Command Language Native Python API
==========================================

Since its inception, EnSight has had a journaling language, commonly referred to as
"command language".  Every operation in EnSight can be captured in command language.
Scripts can be generated using this language and played back in the GUI or in batch mode.
Furthermore, features like context files (that capture a session state) do so using
a command language variant.  Command language is not documented but it roughly follows
the :ref:`EnSight Architecture <ensight_architecture>`.  The "Native" Python API
is a binding to this command language interface.

Command Language Overview
-------------------------

A command language call has the general form: :samp:`{class}: {command} [values...]`.  For
example, :samp:`view_transf: rotate -4. 24. 0.` will rotate the current view and
:samp:`data: replace data.case` would load a dataset into the current case.  Commands
may also follow a "begin/end", "modify being/end" structure where commands of the
same class are used between the begin and end commands.  That form is used to "batch"
a collection of changes into a single update operation.  Finally, there is a
"select begin/end" idiom used to expand values onto multiple lines.

The language separates the specification of target objects and attribute changes into
separate commands.  Thus, there is always a "current selection" of all the objects of
a specific type and many commands operate on the current selection.  For example,
the sequence::

    part: select_begin
     1
    part: select_end
    part: modify_begin
    part: line_width 2
    part: colorby_rgb 1.0 0.0 0.0
    part: modify_end

Will set the current part selection to part number 1 and then it will modify the
line width and part color. Note: most of command language follows these two command
forms, but there are a number of commands that do not follow this scheme.

As noted previously, EnSight maintains a "default" object of every type.  Commands
can be used to modify attributes (not all) on the default object and then a "create"
command is used to create a new object instance.  For example, to create a new clip::

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

Which selects the default clip object and sets up the type and clip position value on the
default clip.  It then changes the current part selection to what part(s) should become the
parent of the clip and calls :samp:`clip: create` to create the clip.

PyEnsight Command Language Binding
----------------------------------

The 'Native' Python API binding is a simple syntax conversion from command language
into Python syntax.  The command class is a module in Python under the 'session.ensight'
module.  All values are passed as native Python parameters. For the "select/begin/end" construct,
only the begin command is used and all of the value lines can be specified as Python
parameters or a list.  The previous example becomes this Python script:

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
as parameters.  So this syntax is also valid:

.. code-block:: python

    session.ensight.part.select_begin([1, 2])
    session.ensight.part.modify_begin()
    session.ensight.part.colorby_rgb([0.0, 0.0, 1.0])
    session.ensight.part.modify_end()

Every command also returns an error code which is 0 on success.  For example:
:samp:`err = session.ensight.part.colorby_rgb([0.0,0.0,"sad"])` sets err to the value -1.
One can also arrange to have error return values converted int exceptions:

.. code-block:: python

    try:
        ensight.sendmesgoptions(exception=True)
        ensight.part.select_begin([1, 2])
        ensight.part.colorby_rgb([0.0,0.0,"sad"])
    except RuntimeError as e:
        print("Error", e)
    finally:
        ensight.sendmesgoptions(exception=False)

prints the error :samp:`RuntimeError: Command: (part: colorby_rgb 0.0 0.0 sad ) returned: RGB color: bad parameter`

GUI Conversion
--------------
There is a built-in mechanism to convert code in command language into Python. To do this,
you first paste the command language into the Python editor (lines of command language can
be selected and copied using the right mouse button menu in the Execution tab). Next, select
the text in the editor and use the Edit menu options for Convert selection to sendmesg() or
Convert selection to native Python. In general, the native Python conversion results in much
more readable Python code that is far easier to edit than the sendmesg() option. The native
option should be used for all but legacy development.

The file menu provides two items to execute the current file text in the EnSight Python
interpreter. The Run script item causes the file contents to be executed in the global
namespace (for example, like the execfile() function). The Import script as module item
first saves the current file to disk and then executes a Python import operation on the
file, which executes in a private namespace. Both will check the syntax of the current
file and allow for rapid prototyping.

Special Cases
-------------

There are a number of commands in the EnSight command language that are not valid
Python names. A few examples include::

    function: #_of_levels 5
    annotation: 3d_label_size 10.0
    command: print "hello"
    viewport: raise

Some reasons a name might be invalid include:

* Name includes an invalid character (for example, "#")

* Name begins with a digit (for example, "1")

* Name is a Python reserved word (for example, "raise")

These are transformed using the following rules:

* "#" characters are replaced with the text number

* Names that start with a digit are prefixed with an _

* Names that are the same as a Python reserved word are prefixed with an _

The previous examples become:

.. code-block:: python

    session.ensight.function.number_of_levels(5)
    session.ensight.annotation._3d_label_size(10.0)
    session.ensight.command.print("hello")
    session.ensight.viewport._raise()