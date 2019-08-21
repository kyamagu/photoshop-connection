import contextlib
import pytest
import threading
from socketserver import BaseRequestHandler, ThreadingTCPServer
from photoshop.protocol import Protocol, ContentType, Pixmap

PASSWORD = 'secret'
KEEP_ALIVE_RESPONSE = b'Yep, still alive'
DATA_RESPONSE = b'/private/var/folders/xx/xxxxxx/T/TemporaryItems/tempdata.tmp'
FILE_STREAM_RESPONSE = (
    b'\x00\x00\x00n{"id":"903957cc-082d-464a-b13e-d55023442674","mimeFormat":"i'
    b'mage\\/png","position":0,"size":378,"fullSize":378}\x89PNG\r\n\x1a\n\x00'
    b'\x00\x00\rIHDR\x00\x00\x00 \x00\x00\x00 \x08\x06\x00\x00\x00szz\xf4\x00'
    b'\x00\x01AIDATX\x85\xed\x96\xd1m\x850\x0cEo\xa4\xfe\x97\x11\x18\x81\x11'
    b'\x18\xe1\x8d\x90\x11\xde\x08\x8c\xd0\x11\x18\x81\x112\x02#\xd0\r\xd8\xe0'
    b'\xf6\xa3Qu1PB\x1e\xd0\x8fb)R\x88\xe3\xf8\x90\xc4v\x80[n\xf9cq\xb9\x86\x04'
    b'\x1a\xf9\x0c\x0e\x08?:r\xd9\x99\xcbv7s\xee\tPZ?\xd1\x93\x8b\xed0!\xd0\x19'
    b'\x00\x12\xa8/\x01 P\x8a\xd3Q\xfa\xedU\x00\x8d8}\x1a\x88\xe2\n\x80A\x1c'
    b'\x96\x04Z\x05:\x15\x80@m/\x1e\x81\x87\x8c\rg\x03\xcc\xfe6\x8e\xeb\xae\xd4'
    b'\xa7\x00\x10(\xccy\x97\xa2\xfb\x90\xf1\xee,\x00\x8d\xfd\xce\xe842\xbe\xef'
    b'\xc6\t\x00\xbd8\xf0\x1b\xfa\xe6P\x00\x1b\xfb+st\x87\x86\xa3\x01\xf4\x8c'
    b'\xdb\x959\x859\x86\xc7\x91\x00\xa3Y<\xa5\x85C\x00L\x9c\xefm\xe5\x16\xc0['
    b'\x02\x83\x97\xfe\'b\xb2\xf9E*\x00\xef\xb1\xff\x84\xe4\x8b\xdd\xb2\x14^'
    b'\t6Z+\xc6\x97\x8e \x16\x9bI\xea\xcd\x80\xf6\xaf\x00h\x8aM\xdeJN\xdf\x0b!'
    b'\x0b\xc0\x14\x1e2\x96\xdaD[\xfbb\xaar\x00\xb4\xf0t\xdb\x16bK\xda\xd0mw'
    b'\x01p^x|\x06\x80&\xafqm\x07\x17\x9f\xa9qr%\x93\xc2^\x0087Y\x03@\xefV\xd2'
    b'\xf8-\xff[\xbe\x00\xc8\xecJ\x9e\x97kYc\x00\x00\x00\x00IEND\xaeB`\x82'
)


class PhotoshopHandler(BaseRequestHandler):
    def setup(self):
        self.protocol = Protocol(PASSWORD)

    def handle(self):
        raise NotImplementedError


class ScriptHandler(PhotoshopHandler):
    def handle(self):
        request = self.protocol.receive(self.request)
        if request.get('content_type') == ContentType.KEEP_ALIVE:
            self.protocol.send(
                self.request, ContentType.SCRIPT, KEEP_ALIVE_RESPONSE
            )
        elif request.get('content_type') == ContentType.DATA:
            self.protocol.send(self.request, ContentType.SCRIPT, DATA_RESPONSE)
        else:
            self.protocol.send(self.request, ContentType.SCRIPT, b'{}')


class ScriptOutputHandler(ScriptHandler):
    def handle(self):
        super(ScriptOutputHandler, self).handle()
        self.protocol.send(
            self.request, ContentType.SCRIPT, b'[ActionDescriptor]'
        )


class JPEGHandler(PhotoshopHandler):
    def handle(self):
        request = self.protocol.receive(self.request)
        self.protocol.send(
            self.request, ContentType.SCRIPT, b'[ActionDescriptor]'
        )
        self.protocol.send(self.request, ContentType.IMAGE, b'\x01\x00')


class PixmapHandler(PhotoshopHandler):
    def handle(self):
        request = self.protocol.receive(self.request)
        data = b'\x02' + Pixmap(2, 2, 8, 3, 3, 8, b'\x00' * 16).dump()
        self.protocol.send(self.request, ContentType.IMAGE, data)
        self.protocol.send(
            self.request, ContentType.SCRIPT, b'[ActionDescriptor]'
        )


class FileStreamHandler(PhotoshopHandler):
    def handle(self):
        request = self.protocol.receive(self.request)
        self.protocol.send(
            self.request, ContentType.FILE_STREAM, FILE_STREAM_RESPONSE
        )
        self.protocol.send(
            self.request, ContentType.SCRIPT, b'[ActionDescriptor]'
        )


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


class ErrorStringHandler(PhotoshopHandler):
    def handle(self):
        self.request.recv(1024)
        self.protocol.send(self.request, ContentType.ERROR_STRING, b'ERROR')


@contextlib.contextmanager
def serve(handler):
    server = ThreadingTCPServer(('localhost', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address
    server.shutdown()
    server.server_close()


@pytest.yield_fixture
def script_server():
    with serve(ScriptHandler) as server:
        yield server


@pytest.yield_fixture
def script_output_server():
    with serve(ScriptOutputHandler) as server:
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
def filestream_server():
    with serve(FileStreamHandler) as server:
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


@pytest.yield_fixture
def error_string_server():
    with serve(ErrorStringHandler) as server:
        yield server
