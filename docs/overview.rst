Overview
========

Prerequisites
-------------

Photoshop must be configured to accept remote connection.

Open the plug-ins dialog from the `Preferences` > `Plug-ins...` menu in
Photoshop, and check `Enable Remote Connections` option. Enter password to the
given field, and click `OK` button and restart Photoshop.

Photoshop must be launched and running for the package to work.


Usage
-----

Create a session with :py:class:`photoshop.PhotoshopConnection`:

.. code-block:: python

    from photoshop import PhotoshopConnection

    with PhotoshopConnection(password='secret') as conn:
        conn.execute('alert("hello")')
        jpeg_binary = conn.get_document_thumbnail()
