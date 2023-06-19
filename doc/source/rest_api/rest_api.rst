.. _rest_api:


********
REST API
********

An EnSight session started using PyEnSight may enable the direct REST API.
This API allows Javascript code to directly access the EnSight Python APIs.
The API is only available in versions of EnSight from the 2024 R1 release
and beyond.  The API is enabled using the ``enable_rest_api=True`` keyword
to the Launcher() subclass ctor.


.. note::

    **The information here is for informational purposes only. The API has
    been defined, but is not currently enabled in EnSight. It will be
    released in 2024 R1**


Enabling the API via PyEnSight
------------------------------

The REST API service can be started via the pyensight LocalLauncher::

    >>> from ansys.pyensight.core import LocalLauncher
    >>> s = LocalLauncher(enable_rest_api=True).start()
    >>> s.load_data(f"{s.cei_home}/ensight{s.cei_suffix}/data/cube/cube.case")
    >>> uri_base = f"http://{s.hostname}:{s.html_port}/ensight/v1/{s.secret_key}"


The base uri will look something like this (the port and GUID will vary):
``http://127.0.0.1:36474/ensight/v1/b7c04700-0a27-11ee-be68-381428170733``.


Basic REST API
--------------

The string from the previous example can be used via Python ``requests`` to execute REST calls::

    >>> import requests
    >>> requests.put(uri_base+"/eval", json="ensight.objs.core.PARTS").json()
    ['@ENSOBJ=1022@']
    >>> requests.put(uri_base+"/eval", json="ensight.objs.core.PARTS", params=dict(returns="DESCRIPTION,VISIBLE")).json()
    [['Computational mesh', True]]


Will use the REST API to run the command: ``ensight.objs.core.PARTS`` and output
something like: ``['@ENSOBJ=1022@']``, a reference to object 1022.  When the query
option ``returns`` is used to return the DESCRIPTION and VISIBLE attributes.  In that
case, the output for the second PUT is: ``[['Computational mesh', True]]``.

.. note::

    Examples here leverage Python requests to execute REST calls, but any mechanism can be
    used: curl, swagger, etc.  The intended use of the API is via JavaScript using fetch() from
    within a web page, making it possible to control and interact with a PyEnSight launched
    EnSight instance directly from the browser.  Moreover, both PyEnSight and REST calls can
    be used to talk to the same EnSight session, making it possible to communicate between
    browser JavaScript and PyEnSight Python scripts, using the EnSight instance as
    a common communication hub.


Remote Python functions
-----------------------

Continuing the example, the REST api can be used to define a Python function in the
remote EnSight session.  First we define the function::

    >>> foo_src = "def foo(n:int = 1):\n return list(numpy.random.rand(n))\n"
    >>> requests.put(uri_base+"/def_func/myapp/foo", json=foo_src, params=dict(imports="numpy"))
    <Response [200]>


This will use the provided function source code to define a function named ``foo`` in the ``myapp``
namespace.  The function being defined should use keywords only, no positional arguments.
Note: if the namespace does not exist, it will be created.   Also, the function
makes use of the ``numpy`` module.  A function must either import the module inside of the
function or include the names of the modules in the ``imports`` query options as a comma
separated list of module names.  Numpy arrays do not directly support serialization to JSON,
hence the use of list() for the returned value.

Once the function has been defined, it may be called like this::

    >>> requests.put(uri_base+"/call_func/myapp/foo", json=dict(n=3)).json()
    [0.2024879142048186, 0.7627361155568255, 0.6102904199228575]


The returned JSON is a list of 3 random floating point numbers.


Direct commands
---------------

The native API can be called directly using the REST API::

    >>> requests.put(uri_base+"/cmd/ensight.view_transf.rotate", json=[5.2,10.4,0]).json()
    0


The EnSight view will rotate accordingly.  The object API can be called directly as well.
Object attributes can be get/set in various forms on single objects or lists of objects::

    >>> requests.get(uri_base+"/ensobjs/ensight.objs.core/PARTS").json()
    ['@ENSOBJ=1022@']
    >>> requests.get(uri_base+"/ensobjs/ensight.objs.core/PARTS", params=dict(returns="VISIBLE,__OBJID__")).json()
    [[True, 1022]]
    >>> requests.put(uri_base+"/ensobjs/1022/VISIBLE", json=False)
    <Response [200]>
    >>> requests.put(uri_base+"/ensobjs/setattrs", json=dict(objects=["1022"], values=dict(VISIBLE=False)))
    <Response [200]>
    >>> requests.put(uri_base+"/ensobjs/getattrs", json=[1022], params=dict(returns="DESCRIPTION,VISIBLE")).json()
    {'1022': ['Computational mesh', False]}
    >>> requests.put(uri_base+"/eval", json="ensight.objs.core").json()
    '@ENSOBJ=220@'
    >>> requests.put(uri_base+"/eval", json="ensight.objs.core", params=dict(returns="__OBJID__")).json()
    220


Objects can be specified by name (``ensight.objs.core``) by number (``220``) and any attribute
of the objects can be returned in a single call, reducing the number of REST calls needed
for complex operations.


REST API Reference
------------------

The REST API display here is a bit simplistic, but the OpenAPI yaml description of the
API (appropriate for use with `Swagger <https://editor.swagger.io/>`_), can be
downloaded `here <https://ensight.docs.pyansys.com/dev/_static/ensight_rest_v1.yaml>`_.


.. openapi:: ensight_rest_v1.yaml
    :examples:

