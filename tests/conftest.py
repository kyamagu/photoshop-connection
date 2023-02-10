import contextlib
import logging
import socket
import threading
import time
from socketserver import BaseRequestHandler, ThreadingTCPServer
from typing import Any, Callable, Dict, Iterator, Optional, Tuple

import pytest
from esprima import parseScript
from esprima.error_handler import Error as ParseError
from photoshop.protocol import ContentType, Pixmap, Protocol

logger = logging.getLogger(__name__)

PASSWORD = "secret"
KEEP_ALIVE_RESPONSE = b"Yep, still alive"
DATA_RESPONSE = b"/private/var/folders/xx/xxxxxx/T/TemporaryItems/tempdata.tmp"
FILE_STREAM_RESPONSE = (
    b'\x00\x00\x00n{"id":"903957cc-082d-464a-b13e-d55023442674","mimeFormat":"i'
    b'mage\\/png","position":0,"size":378,"fullSize":378}\x89PNG\r\n\x1a\n\x00'
    b"\x00\x00\rIHDR\x00\x00\x00 \x00\x00\x00 \x08\x06\x00\x00\x00szz\xf4\x00"
    b"\x00\x01AIDATX\x85\xed\x96\xd1m\x850\x0cEo\xa4\xfe\x97\x11\x18\x81\x11"
    b"\x18\xe1\x8d\x90\x11\xde\x08\x8c\xd0\x11\x18\x81\x112\x02#\xd0\r\xd8\xe0"
    b"\xf6\xa3Qu1PB\x1e\xd0\x8fb)R\x88\xe3\xf8\x90\xc4v\x80[n\xf9cq\xb9\x86\x04"
    b"\x1a\xf9\x0c\x0e\x08?:r\xd9\x99\xcbv7s\xee\tPZ?\xd1\x93\x8b\xed0!\xd0\x19"
    b"\x00\x12\xa8/\x01 P\x8a\xd3Q\xfa\xedU\x00\x8d8}\x1a\x88\xe2\n\x80A\x1c"
    b"\x96\x04Z\x05:\x15\x80@m/\x1e\x81\x87\x8c\rg\x03\xcc\xfe6\x8e\xeb\xae\xd4"
    b"\xa7\x00\x10(\xccy\x97\xa2\xfb\x90\xf1\xee,\x00\x8d\xfd\xce\xe842\xbe\xef"
    b"\xc6\t\x00\xbd8\xf0\x1b\xfa\xe6P\x00\x1b\xfb+st\x87\x86\xa3\x01\xf4\x8c"
    b"\xdb\x959\x859\x86\xc7\x91\x00\xa3Y<\xa5\x85C\x00L\x9c\xefm\xe5\x16\xc0["
    b"\x02\x83\x97\xfe'b\xb2\xf9E*\x00\xef\xb1\xff\x84\xe4\x8b\xdd\xb2\x14^"
    b"\t6Z+\xc6\x97\x8e \x16\x9bI\xea\xcd\x80\xf6\xaf\x00h\x8aM\xdeJN\xdf\x0b!"
    b"\x0b\xc0\x14\x1e2\x96\xdaD[\xfbb\xaar\x00\xb4\xf0t\xdb\x16bK\xda\xd0mw"
    b"\x01p^x|\x06\x80&\xafqm\x07\x17\x9f\xa9qr%\x93\xc2^\x0087Y\x03@\xefV\xd2"
    b"\xf8-\xff[\xbe\x00\xc8\xecJ\x9e\x97kYc\x00\x00\x00\x00IEND\xaeB`\x82"
)
ACKNOWLEDGE = b"[ActionDescriptor]"


class PhotoshopHandler(BaseRequestHandler):
    def setup(self) -> None:
        self.protocol = Protocol(PASSWORD)

    def handle(self) -> None:
        try:
            while True:
                request = self.protocol.receive(self.request)
                self.do_handle(request)
        except OSError:
            pass

    def do_handle(self, request: Dict[str, Any]) -> None:
        body = self.make_response(request)
        self.send_script(request["transaction"], body)

    def send_script(self, transaction: int, body: bytes = b"") -> None:
        logger.debug("SEND RESPONSE: %r" % body)
        self.protocol.send(self.request, ContentType.SCRIPT, body, transaction)

    def make_response(
        self, request: Dict[str, Any], body: Optional[bytes] = None
    ) -> bytes:
        content_type = request.get("content_type")
        if content_type in (ContentType.SCRIPT, ContentType.SCRIPT_SHARED):
            try:
                parseScript(request["body"].decode("utf-8"))
            except ParseError as e:
                logger.exception("%s: %r" % (e, request["body"]))
                return b""
            return body or b"{}"
        elif content_type == ContentType.KEEP_ALIVE:
            return KEEP_ALIVE_RESPONSE
        elif content_type == ContentType.DATA:
            return DATA_RESPONSE
        return body or b""


class ScriptOutputHandler(PhotoshopHandler):
    def do_handle(self, request: Dict[str, Any]) -> None:
        super(ScriptOutputHandler, self).do_handle(request)
        self.send_script(request["transaction"], ACKNOWLEDGE)


class SubscribeHandler(PhotoshopHandler):
    def do_handle(self, request: Dict[str, Any]) -> None:
        self.send_script(request["transaction"], ACKNOWLEDGE)
        script = parseScript(request["body"].decode("utf-8"))
        command = script.body[0].declarations[0].init.arguments[0].value
        if command == "networkEventSubscribe":
            for _ in range(3):
                time.sleep(1.0)
                self.send_script(request["transaction"], b"imageChanged\r{}")


class JPEGHandler(PhotoshopHandler):
    def do_handle(self, request: Dict[str, Any]) -> None:
        # Can be before the data.
        self.send_script(request["transaction"], ACKNOWLEDGE)
        self.protocol.send(self.request, ContentType.IMAGE, b"\x01\x00")


class PixmapHandler(PhotoshopHandler):
    def do_handle(self, request: Dict[str, Any]) -> None:
        data = b"\x02" + Pixmap(2, 2, 8, 3, 3, 8, b"\x00" * 16).dump()
        self.protocol.send(self.request, ContentType.IMAGE, data)
        self.send_script(request["transaction"], ACKNOWLEDGE)


class FileStreamHandler(PhotoshopHandler):
    def do_handle(self, request: Dict[str, Any]) -> None:
        self.protocol.send(self.request, ContentType.FILE_STREAM, FILE_STREAM_RESPONSE)
        self.send_script(request["transaction"], ACKNOWLEDGE)


class IllegalHandler(PhotoshopHandler):
    def do_handle(self, request: Dict[str, Any]) -> None:
        self.protocol.send(self.request, ContentType.ILLEGAL, b"")


class ErrorStringHandler(PhotoshopHandler):
    def do_handle(self, request: Dict[str, Any]) -> None:
        self.protocol.send(
            self.request, ContentType.ERROR_STRING, b"ERROR", request["transaction"]
        )


class ErrorImageHandler(PhotoshopHandler):
    def do_handle(self, request: Dict[str, Any]) -> None:
        self.protocol.send(
            self.request, ContentType.IMAGE, b"\x03\x00", request["transaction"]
        )


class ErrorHandler(BaseRequestHandler):
    def handle(self) -> None:
        self.request.recv(1024)
        self.request.sendall(b"\x00\x00\x00\x04\x00\x00\x00\x01")


class ErrorStatusHandler(PhotoshopHandler):
    def do_handle(self, request: Dict[str, Any]) -> None:
        self.protocol.send(
            self.request, ContentType.SCRIPT, b"", request["transaction"], status=1
        )


class ErrorConnectionHandler(BaseRequestHandler):
    def handle(self) -> None:
        self.request.recv(1024)


class ErrorTransactionHandler(PhotoshopHandler):
    def do_handle(self, request: Dict[str, Any]) -> None:
        self.protocol.send(
            self.request,
            ContentType.SCRIPT,
            b"",
            request["transaction"] + 1,
        )


@contextlib.contextmanager
def serve(
    handler: Callable[..., BaseRequestHandler]
) -> Iterator[Tuple[Optional[str], int]]:
    server = ThreadingTCPServer(("localhost", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address
    server.shutdown()
    server.server_close()


@pytest.fixture
def script_server() -> Iterator[Tuple[Optional[str], int]]:
    with serve(PhotoshopHandler) as server:
        yield server


@pytest.fixture
def script_output_server() -> Iterator[Tuple[Optional[str], int]]:
    with serve(ScriptOutputHandler) as server:
        yield server


@pytest.fixture
def subscribe_server() -> Iterator[Tuple[Optional[str], int]]:
    with serve(SubscribeHandler) as server:
        yield server


@pytest.fixture
def jpeg_server() -> Iterator[Tuple[Optional[str], int]]:
    with serve(JPEGHandler) as server:
        yield server


@pytest.fixture
def pixmap_server() -> Iterator[Tuple[Optional[str], int]]:
    with serve(PixmapHandler) as server:
        yield server


@pytest.fixture
def filestream_server() -> Iterator[Tuple[Optional[str], int]]:
    with serve(FileStreamHandler) as server:
        yield server


@pytest.fixture
def illegal_server() -> Iterator[Tuple[Optional[str], int]]:
    with serve(IllegalHandler) as server:
        yield server


@pytest.fixture
def error_server() -> Iterator[Tuple[Optional[str], int]]:
    with serve(ErrorHandler) as server:
        yield server


@pytest.fixture
def error_image_server() -> Iterator[Tuple[Optional[str], int]]:
    with serve(ErrorImageHandler) as server:
        yield server


@pytest.fixture
def error_string_server() -> Iterator[Tuple[Optional[str], int]]:
    with serve(ErrorStringHandler) as server:
        yield server


@pytest.fixture
def error_status_server() -> Iterator[Tuple[Optional[str], int]]:
    with serve(ErrorStatusHandler) as server:
        yield server


@pytest.fixture
def error_connection_server() -> Iterator[Tuple[Optional[str], int]]:
    with serve(ErrorConnectionHandler) as server:
        yield server


@pytest.fixture
def error_transaction_server() -> Iterator[Tuple[Optional[str], int]]:
    with serve(ErrorTransactionHandler) as server:
        yield server


def test_error_server(error_server: Tuple[Optional[str], int]) -> None:
    with socket.create_connection(error_server) as sock:
        sock.sendall(b"\x00")
        assert sock.recv(1024)


@pytest.fixture
def password() -> str:
    return PASSWORD
