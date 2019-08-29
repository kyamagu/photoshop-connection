Photoshop connection
====================

Python package to remotely execute ExtendScript_ in Adobe Photoshop.

.. _ExtendScript: https://www.adobe.com/devnet/photoshop/scripting.html

.. image:: https://travis-ci.org/kyamagu/photoshop-connection.svg?branch=master
    :target: https://travis-ci.org/kyamagu/photoshop-connection
    :alt: Build Status
.. image:: https://readthedocs.org/projects/photoshop-connection/badge/?version=latest
    :target: https://photoshop-connection.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status
.. image:: https://codecov.io/gh/kyamagu/photoshop-connection/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/kyamagu/photoshop-connection

Prerequisites
-------------

Photoshop must be configured to accept remote connection.

Open the plug-ins dialog from the `Preferences` > `Plug-ins...` menu in
Photoshop, and check `Enable Remote Connections` option. Enter password to the
given field, and click `OK` button and restart Photoshop.

Photoshop must be launched and running for the package to work.


Usage
-----

Example:

.. code-block:: python

    from photoshop import PhotoshopConnection

    with PhotoshopConnection(password='secret') as conn:
        conn.execute('alert("hello")')
        jpeg_binary = conn.get_document_thumbnail()

Check out documentation_ for details.

.. _documentation: https://photoshop-connection.readthedocs.io/en/latest/
