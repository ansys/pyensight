.. _rest_api:


****
REST
****

An EnSight session started using PyEnSight will enable a direct REST API
that allows Javascript code to directly access the EnSight Python APIs.


.. note::

    **The information here is for informational purposes only.  The API has
    been defined, but is not currently enabled in EnSight.   It will be
    released in 2024 R1**


Enabling Access via PyEnSight
-----------------------------

The REST service can be started via the pyensight LocalLauncher::

    from ansys.pyensight.core import LocalLauncher
    s = LocalLauncher(enable_rest_api=True).start()
    s.load_data(f"{s.cei_home}/ensight{s.cei_suffix}/data/cube/cube.case")
    print(f"http://{s.hostname}:{s.html_port}/ensight/v1/{s.secret_key}/eval")


This with print out a string like this:
``http://127.0.0.1:36474/ensight/v1/b7c04700-0a27-11ee-be68-381428170733/eval``.
The string can be used via Python ``requests`` or ``curl`` to execute the REST call::

    curl -X PUT http://127.0.0.1:36474/ensight/v1/b7c04700-0a27-11ee-be68-381428170733/eval -H "Content-Type: application/json" -d '"ensight.objs.core.PARTS"'


Will use the REST API to run the command: ``ensight.objs.core.PARTS`` and output
something like: ``"[Class: ENS_PART, desc: 'Computational mesh', CvfObjID: 1083, cached:no]"``


API Reference
-------------

The REST API display here is a bit simplistic, but the OpenAPI yaml description of the
API (appropriate for use with `Swagger <https://editor.swagger.io/>`_), can be
downloaded `here <https://ensight.docs.pyansys.com/dev/_static/ensight_rest_v1.yaml>`_.


.. openapi:: ensight_rest_v1.yaml
    :examples:

