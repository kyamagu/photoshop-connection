import pytest
import socket
from photoshop.version import __version__
from photoshop import PhotoshopConnection, ContentType
from photoshop.protocol import Pixmap
from .mock import (
    script_server, jpeg_server, pixmap_server, error_server,
    error_image_server, error_string_server, PASSWORD
)

SCRIPT = '''
var idNS = stringIDToTypeID( "sendDocumentThumbnailToNetworkClient" );
var desc1 = new ActionDescriptor();
desc1.putInteger( stringIDToTypeID( "width" ), 1 );
desc1.putInteger( stringIDToTypeID( "height" ), 1 );
desc1.putInteger( stringIDToTypeID( "format" ), 1 );
executeAction( idNS, desc1, DialogModes.NO );
'''


def test_connection_script(script_server):
    conn = PhotoshopConnection(PASSWORD, port=script_server[1])
    response = conn.execute('alert("hi")')
    assert response['status'] == 0
    assert response['protocol'] == 1
    assert response['transaction'] == 0
    assert response['content_type'] == ContentType.SCRIPT
    assert response['body'] == b'{}'
    conn.__del__()  # This is not elegant.


def test_connection_jpeg(jpeg_server):
    with PhotoshopConnection(PASSWORD, port=jpeg_server[1]) as conn:
        response = conn.execute(SCRIPT, receive_output=True)
        assert response['status'] == 0
        assert response['protocol'] == 1
        assert response['transaction'] == 0
        assert response['content_type'] == ContentType.IMAGE
        assert response['body']['data'] == b'\x00'


def test_connection_pixmap(pixmap_server):
    with PhotoshopConnection(PASSWORD, port=pixmap_server[1]) as conn:
        response = conn.execute(SCRIPT, receive_output=True)
        assert response['status'] == 0
        assert response['protocol'] == 1
        assert response['transaction'] == 0
        assert response['content_type'] == ContentType.IMAGE
        assert isinstance(response['body']['data'], Pixmap)


def test_connection_refused():
    with pytest.raises(ConnectionRefusedError):
        PhotoshopConnection(PASSWORD, host='localhost', port=23)


def test_connection_illegal(error_server):
    import logging
    logging.basicConfig(level=logging.DEBUG)
    with PhotoshopConnection(PASSWORD, port=error_server[1]) as conn:
        with pytest.raises(RuntimeError):
            response = conn.execute(SCRIPT, timeout=.5)


def test_connection_error_image(error_image_server):
    with PhotoshopConnection(PASSWORD, port=error_image_server[1]) as conn:
        with pytest.raises(RuntimeError):
            response = conn.execute(SCRIPT, timeout=.5)


def test_runtime_error(error_string_server):
    with PhotoshopConnection(PASSWORD, port=error_string_server[1]) as conn:
        with pytest.raises(RuntimeError):
            response = conn.execute(SCRIPT)


def test_upload(script_server):
    with PhotoshopConnection(PASSWORD, port=script_server[1]) as conn:
        conn.upload(b'\x00\x00\x00\x00')


def test_ping(script_server):
    with PhotoshopConnection(PASSWORD, port=script_server[1]) as conn:
        conn.ping()
