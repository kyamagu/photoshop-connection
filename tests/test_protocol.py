from photoshop.protocol import Pixmap
from .mock import script_server, jpeg_server, pixmap_server, PASSWORD


def test_pixmap():
    pixmap = Pixmap(2, 2, 8, 3, 3, 8, b'\x00' * 16)
    data = pixmap.dump()
    assert Pixmap.parse(data).dump() == data
    pixmap.__repr__()
