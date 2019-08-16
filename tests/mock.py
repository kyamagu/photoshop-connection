import contextlib
import pytest
import threading
from socketserver import BaseRequestHandler, ThreadingTCPServer
from photoshop.protocol import Protocol, ContentType, Pixmap

PASSWORD = 'secret'


class PhotoshopHandler(BaseRequestHandler):
    def setup(self):
        self.protocol = Protocol(PASSWORD)

    def handle(self):
        raise NotImplementedError


class ScriptHandler(PhotoshopHandler):
    def handle(self):
        request = self.protocol.receive(self.request)
        self.protocol.send(self.request, ContentType.SCRIPT, b'null')


class JPEGHandler(PhotoshopHandler):
    def handle(self):
        request = self.protocol.receive(self.request)
        self.protocol.send(self.request, ContentType.IMAGE, b'\x01\x00')


class PixmapHandler(PhotoshopHandler):
    def handle(self):
        request = self.protocol.receive(self.request)
        data = b'\x02' + Pixmap(2, 2, 8, 3, 3, 8, b'\x00' * 16).dump()
        self.protocol.send(self.request, ContentType.IMAGE, data)


class ErrorImageHandler(PhotoshopHandler):
    def handle(self):
        request = self.protocol.receive(self.request)
        self.protocol.send(self.request, ContentType.IMAGE, b'\x03\x00')


class IllegalHandler(PhotoshopHandler):
    def handle(self):
        request = self.protocol.receive(self.request)
        self.protocol.send(self.request, ContentType.ILLEGAL, b'')


class ErrorHandler(BaseRequestHandler):
    def handle(self):
        self.request.recv(1024)
        self.request.sendall(b'\x00\x00\x00\x04\x00\x00\x00\x01')


@contextlib.contextmanager
def serve(handler):
    server = ThreadingTCPServer(('localhost', 0), handler)
    with server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield server.server_address
        server.shutdown()


@pytest.yield_fixture
def script_server():
    with serve(ScriptHandler) as server:
        yield server


@pytest.yield_fixture
def jpeg_server():
    with serve(JPEGHandler) as server:
        yield server


@pytest.yield_fixture
def pixmap_server():
    with serve(PixmapHandler) as server:
        yield server


@pytest.yield_fixture
def illegal_server():
    with serve(IllegalHandler) as server:
        yield server


@pytest.yield_fixture
def error_server():
    with serve(ErrorHandler) as server:
        yield server


@pytest.yield_fixture
def error_image_server():
    with serve(ErrorImageHandler) as server:
        yield server
