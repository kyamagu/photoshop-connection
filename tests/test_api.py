import pytest
from esprima import parseScript
from photoshop import PhotoshopConnection
from photoshop.protocol import Pixmap
from .mock import (
    script_server, jpeg_server, pixmap_server, error_server,
    error_image_server, PASSWORD
)


def test_get_document_thumbnail(jpeg_server):
    with PhotoshopConnection(
        PASSWORD, port=jpeg_server[1], validator=parseScript
    ) as conn:
        jpeg_binary = conn.get_document_thumbnail()
        assert isinstance(jpeg_binary, bytes)


def test_get_layer_thumbnail(pixmap_server):
    with PhotoshopConnection(
        PASSWORD, port=pixmap_server[1], validator=parseScript
    ) as conn:
        pixmap = conn.get_layer_thumbnail()
        assert isinstance(pixmap, Pixmap)
