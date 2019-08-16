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
