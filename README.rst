Photoshop connection
====================

Python package to remotely execute ExtendScript_ in Adobe Photoshop.


.. _ExtendScript: https://www.adobe.com/devnet/photoshop/scripting.html


Prerequisite
------------

Photoshop must be configured to accept remote connection.

Open the plug-ins dialog from the `Preferences` > `Plug-ins...` menu in
Photoshop, and check `Enable Remote Connections` option. Enter password to the
given field, and click `OK` button and restart Photoshop.

Photoshop must be launched and running for `PhotoshopConnection` to work.


Usage
-----

Example:

.. code-block:: python

    from photoshop import PhotoshopConnection

    conn = PhotoshopConnection(password='secret', host='127.0.0.1')
    print(conn.execute('11 + 2'))
    print(conn.execute('app'))
    del conn

It is also possible to use `with` statement:

.. code-block:: python

    with PhotoshopConnection(password='secret') as conn:
        print(conn.execute('app'))
        print(conn.execute('11 + 2'))
