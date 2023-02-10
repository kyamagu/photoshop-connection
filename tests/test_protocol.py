from typing import Any, Tuple

import pytest
from photoshop.protocol import Pixmap
from PIL import Image


@pytest.mark.parametrize(
    "args",
    [
        (2, 2, 8, 3, 3, 8, b"\x00" * 16),
        (0, 0, 0, 3, 0, 0, b""),
    ],
)
def test_pixmap(args: Tuple[Any, ...]) -> None:

    pixmap = Pixmap(*args)
    data = pixmap.dump()
    assert Pixmap.parse(data).dump() == data
    pixmap.__repr__()
    image = pixmap.topil()
    assert image is None or isinstance(image, Image.Image)
