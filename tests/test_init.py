from photoshop import PhotoshopConnection, ContentType, Pixmap
from .mock import script_server, jpeg_server, pixmap_server, PASSWORD


def test_connection_script(script_server):
    with PhotoshopConnection(PASSWORD, port=script_server[1]) as conn:
        response = conn.execute('alert("hi")')
        assert response['status'] == 0
        assert response['protocol'] == 1
        assert response['transaction'] == 0
        assert response['content_type'] == ContentType.SCRIPT
        assert response['body'] == b'null'


def test_connection_jpeg(jpeg_server):
    with PhotoshopConnection(PASSWORD, port=jpeg_server[1]) as conn:
        response = conn.execute('alert("hi")')
        assert response['status'] == 0
        assert response['protocol'] == 1
        assert response['transaction'] == 0
        assert response['content_type'] == ContentType.IMAGE
        assert response['body']['data'] == b'\x00'


def test_connection_pixmap(pixmap_server):
    with PhotoshopConnection(PASSWORD, port=pixmap_server[1]) as conn:
        response = conn.execute('alert("hi")')
        assert response['status'] == 0
        assert response['protocol'] == 1
        assert response['transaction'] == 0
        assert response['content_type'] == ContentType.IMAGE
        assert isinstance(response['body']['data'], Pixmap)
