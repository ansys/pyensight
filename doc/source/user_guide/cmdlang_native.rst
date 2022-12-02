.. _ref_cmdlang_native:

EnSight Command Language Native Python API
==========================================

TBD

Command Language Conversion
---------------------------
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