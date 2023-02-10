from typing import Optional, Tuple

import pytest
from esprima import parseScript
from photoshop import PhotoshopConnection
from photoshop.protocol import ContentType, Pixmap

SCRIPT = """
var idNS = stringIDToTypeID( "sendDocumentThumbnailToNetworkClient" );
var desc1 = new ActionDescriptor();
desc1.putInteger( stringIDToTypeID( "width" ), 1 );
desc1.putInteger( stringIDToTypeID( "height" ), 1 );
desc1.putInteger( stringIDToTypeID( "format" ), 1 );
executeAction( idNS, desc1, DialogModes.NO );
"""


def test_connection_script(
    password: str, script_server: Tuple[Optional[str], int]
) -> None:
    conn = PhotoshopConnection(password, port=script_server[1])
    response = conn.execute('alert("hi")')
    assert response["status"] == 0
    assert response["protocol"] == 1
    assert response["transaction"] == 0
    assert response["content_type"] == ContentType.SCRIPT
    assert response["body"] == b"{}"
    conn.__del__()  # This is not elegant.


def test_connection_jpeg(password: str, jpeg_server: Tuple[Optional[str], int]) -> None:
    with PhotoshopConnection(password, port=jpeg_server[1]) as conn:
        response = conn.execute(SCRIPT, receive_output=True)
        assert response["status"] == 0
        assert response["protocol"] == 1
        assert response["transaction"] == 0
        assert response["content_type"] == ContentType.IMAGE
        assert response["body"]["data"] == b"\x00"


def test_connection_pixmap(
    password: str, pixmap_server: Tuple[Optional[str], int]
) -> None:
    with PhotoshopConnection(password, port=pixmap_server[1]) as conn:
        response = conn.execute(SCRIPT, receive_output=True)
        assert response["status"] == 0
        assert response["protocol"] == 1
        assert response["transaction"] == 0
        assert response["content_type"] == ContentType.IMAGE
        assert isinstance(response["body"]["data"], Pixmap)


def test_connection_refused(password: str) -> None:
    with pytest.raises(ConnectionRefusedError):
        PhotoshopConnection(password, host="localhost", port=23)


def test_connection_closed(
    password: str, error_connection_server: Tuple[Optional[str], int]
) -> None:
    with PhotoshopConnection(password, port=error_connection_server[1]) as conn:
        with pytest.raises(OSError):
            conn.execute(SCRIPT)


def test_connection_illegal(
    password: str, illegal_server: Tuple[Optional[str], int]
) -> None:
    with PhotoshopConnection(password, port=illegal_server[1]) as conn:
        with pytest.raises(RuntimeError):
            conn.execute(SCRIPT)


def test_connection_error_image(
    password: str, error_image_server: Tuple[Optional[str], int]
) -> None:
    with PhotoshopConnection(password, port=error_image_server[1]) as conn:
        with pytest.raises(ValueError):
            conn.execute(SCRIPT)


def test_runtime_error(
    password: str, error_string_server: Tuple[Optional[str], int]
) -> None:
    with PhotoshopConnection(password, port=error_string_server[1]) as conn:
        with pytest.raises(RuntimeError):
            conn.execute(SCRIPT)


def test_error_status(
    password: str, error_status_server: Tuple[Optional[str], int]
) -> None:
    with PhotoshopConnection(password, port=error_status_server[1]) as conn:
        with pytest.raises(ValueError):
            conn.execute(SCRIPT)


def test_error_transaction(
    password: str, error_transaction_server: Tuple[Optional[str], int]
) -> None:
    with PhotoshopConnection(password, port=error_transaction_server[1]) as conn:
        with pytest.raises(RuntimeError):
            conn.execute(SCRIPT)


def test_upload(password: str, script_server: Tuple[Optional[str], int]) -> None:
    with PhotoshopConnection(password, port=script_server[1]) as conn:
        conn.upload(b"\x00\x00\x00\x00", suffix=".dat")


def test_download(
    password: str, script_output_server: Tuple[Optional[str], int]
) -> None:
    with PhotoshopConnection(password, port=script_output_server[1]) as conn:
        conn.download("/path/to/tempdata.temp")


def test_ping(password: str, script_server: Tuple[Optional[str], int]) -> None:
    with PhotoshopConnection(password, port=script_server[1]) as conn:
        conn.ping()


@pytest.mark.parametrize(
    "file_type",
    [
        "PHOTOSHOP",
        None,
    ],
)
def test_open_document(
    password: str, script_server: Tuple[Optional[str], int], file_type: Optional[str]
) -> None:
    with PhotoshopConnection(
        password, port=script_server[1], validator=parseScript
    ) as conn:
        conn.open_document("filename.psd", file_type=file_type)
