from typing import Optional, Tuple

from esprima import parseScript
from photoshop import PhotoshopConnection
from photoshop.protocol import Pixmap


class CallbackHandler(object):
    def __init__(self) -> None:
        self.count = 0

    def __call__(self, conn: PhotoshopConnection, data: Optional[bytes]) -> bool:
        assert data == b"{}"
        self.count += 1
        if self.count >= 3:
            return True
        return False


def test_subscribe(password: str, subscribe_server: Tuple[Optional[str], int]) -> None:
    with PhotoshopConnection(
        password, port=subscribe_server[1], validator=parseScript
    ) as conn:
        conn.subscribe("imageChanged", CallbackHandler(), block=True)


def test_subscribe_error(
    password: str, error_status_server: Tuple[Optional[str], int]
) -> None:
    with PhotoshopConnection(
        password, port=error_status_server[1], validator=parseScript
    ) as conn:
        conn.subscribe("imageChanged", CallbackHandler(), block=True)


def test_get_document_thumbnail(
    password: str, jpeg_server: Tuple[Optional[str], int]
) -> None:
    with PhotoshopConnection(
        password, port=jpeg_server[1], validator=parseScript
    ) as conn:
        jpeg_binary = conn.get_document_thumbnail()
        assert isinstance(jpeg_binary, bytes)


def test_get_layer_thumbnail(
    password: str, pixmap_server: Tuple[Optional[str], int]
) -> None:
    with PhotoshopConnection(
        password, port=pixmap_server[1], validator=parseScript
    ) as conn:
        pixmap = conn.get_layer_thumbnail()
        assert isinstance(pixmap, Pixmap)


def test_get_layer_shape(
    password: str, script_output_server: Tuple[Optional[str], int]
) -> None:
    with PhotoshopConnection(
        password, port=script_output_server[1], validator=parseScript
    ) as conn:
        shape_info = conn.get_layer_shape()
        assert isinstance(shape_info, dict)


def test_get_document_info(
    password: str, script_output_server: Tuple[Optional[str], int]
) -> None:
    with PhotoshopConnection(
        password, port=script_output_server[1], validator=parseScript
    ) as conn:
        document_info = conn.get_document_info()
        assert isinstance(document_info, dict)


def test_get_document_stream(
    password: str, filestream_server: Tuple[Optional[str], int]
) -> None:
    with PhotoshopConnection(
        password, port=filestream_server[1], validator=parseScript
    ) as conn:
        document_info = conn.get_document_stream()
        assert isinstance(document_info, dict)
