"""
.. _ref_remote_exec:

Remote Function Execution
=========================

The PyEnsight interface relies very heavily on the performance of communication
between the PyEnSight interpreter and the EnSight instance.  This communication,
while fast, is not nearly as fast as running Python directly within the EnSight
instance.  In this example, some (unexpected) performance bottlenecks will be
discussed along with methods that can be used to assert finer-grained control
over Python code execution.

"""

###############################################################################
# PyEnSight proxy objects
# -----------------------
#
# The EnSight API is based on the fact that every C++ object in EnSight can be
# uniquely identified by an ID.  This number is guaranteed to be unique within
# a specific instance of EnSight. PyEnSight exploits this by creating proxy
# objects that "wrap" an object ID.  This makes the PyEnSight interface simple
# and robust.
#
# The EnSight API is mostly "attributes" with a few methods.  PyEnSight (and
# the EnSight Python Object API) exposes these attributes as Python properties.
# Every attempt to set or get an attribute results in a network call.  These
# can be subtle.  For example, ``print(session.ensight.objs.core.PARTS[0])``
# results in this output:
# ``Class: ENS_PART_MODEL, desc: 'engine', CvfObjID: 1038, cached:no``.
# The proxy id number is 1038.  Importantly, the string
# 'engine' is the value of the DESCRIPTION attribute.  When the string is
# printed, a complete network round trip is performed.  Similar situations
# exist when processing objects in ensobjlist objs.
#
# In general, locally run PyEnSight code is much easier to develop and debug.
# It is strongly suggested that initial development be done with local code
# execution and only use switch to remote code execution if necessary to
# meet performance requirements.
#

###############################################################################
# Atomic function execution
# -------------------------
#
# PyEnSight supports two forms of asynchronous operation.  The first is for
# event callbacks. The EnSight Python interpreter will only dispatch callbacks
# when the interpreter becomes "idle" (unless a flush is forced).  Thus, if
# running a function in PyEnSight that causes event callbacks to be executed,
# these may be executed between lines inside the function.  Second, it is
# legal for multiple sessions to be talking to the same EnSight instance.
# In this situation, PyEnSight calls from the different session connections
# will be multiplexed.
#
# A feature of remote execution is that the entire function will complete as
# an "atomic" operation.  This avoids multi-session multiplexing of commands
# and defers callbacks until the function completes. This has the helpful
# side effect of allowing for event compression as well, avoiding redundant
# event callbacks.
#

###############################################################################
# Start an EnSight session
# ------------------------
# Start by launching and connecting to an instance of EnSight.
# In this case, we use a local installation of EnSight and load a simple
# dataset.

import time

from ansys.pyensight.core import LocalLauncher

session = LocalLauncher().start()
session.load_data(f"{session.cei_home}/ensight{session.cei_suffix}/data/guard_rail/crash.case")


###############################################################################
# Source level remote execution
# -----------------------------
#
# Perhaps the simplest approach is to use the :func:`cmd<ansys.pyensight.core.Session.cmd>`
# and the text representation of the function. Here the function simply collects the
# names of all the parts.  We define the function and then call it in two calls.
# The code in the function is executed entirely in the EnSight Python interpreter
# and the result can be returned when invoking the function.
#
# Care must be taken to ensure that the function does not conflict with other
# functions defined in the EnSight interpreter, but it is possible to store
# state and instance data as well.  For example, a callback can be set up
# entirely in the EnSight interpreter.  This makes it possible to chain
# event handling, doing parts of the work in the EnSight interpreter and
# other aspects of it in the PyEnSight interpreter.
#
# Limitations include the need for the function in source code form and some
# difficulties passing arbitrary parameters to the function.
#
# On a test system, the output is:
#
# ``Remote: 0.03598785400390625``
#
# ``['engine', 'tires', 'wheels', 'lights', 'front body', 'rear body', 'floor', 'windshields',
# 'windows', 'bumpers', 'hood', 'mounts', 'guardrail supports', 'guardrail supports ->> 0001',
# 'guardrail']``
#
# ``Remote: 0.002001523971557617``
#
# ``['engine', 'tires', 'wheels', 'lights', 'front body', 'rear body', 'floor', 'windshields',
# 'windows', 'bumpers', 'hood', 'mounts', 'guardrail supports', 'guardrail supports ->> 0001',
# 'guardrail']``


def myfunc(ensight):
    names = []
    for p in ensight.objs.core.PARTS:
        names.append(p.DESCRIPTION)
    return names


start = time.time()
names = myfunc(session.ensight)
print(f"Remote: {time.time()-start}")
print(names)

cmd = "def myfunc():\n"
cmd += "    names = []\n"
cmd += "    for p in ensight.objs.core.PARTS:\n"
cmd += "        names.append(p.DESCRIPTION)\n"
cmd += "    return names.__repr__()\n"
session.cmd(cmd, do_eval=False)
start = time.time()
names = session.cmd("myfunc()")
print(f"Remote: {time.time()-start}")
print(names)


###############################################################################
# Remote function calls
# ---------------------
#
# Note: this feature requires that the version of the EnSight Python interpreter
# and the PyEnSight interpreter must be the same.  PyEnSight makes a check for
# this when the such execution is requested.
#
# In this configuration, a function defined is in the PyEnSight interpreter
# is captured and passed as byte code over the EnSight Python interpreter
# with all parameters captured and passed.
#
# On a test system, the output is:
#
# ``(15, 0.09499883651733398)``
#
# ``(15, 0.06392621994018555)``
#
# ``(15, 0.0009984970092773438)``
#


def count(ensight, attr, value):
    import time  # time must be imported on the EnSight side as well

    start = time.time()
    count = 0
    for p in ensight.objs.core.PARTS:
        if p.getattr(attr) == value:
            count += 1
    return count, time.time() - start


print(count(session.ensight, "VISIBLE", True))
print(session.exec(count, "VISIBLE", True))
print(session.exec(count, "VISIBLE", True, remote=True))


###############################################################################
# Close the session
# -----------------
# Close the connection and shut down the EnSight instance

session.close()
