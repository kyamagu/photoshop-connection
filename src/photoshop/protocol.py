from __future__ import annotations

import enum
import json
import logging
import socket
from struct import pack, unpack
from typing import Any, Dict

from photoshop.crypto import EncryptDecrypt
from PIL import Image

logger = logging.getLogger(__name__)


class ContentType(enum.IntEnum):
    """
    Message content type.
    """

    ILLEGAL = 0
    ERROR_STRING = 1
    SCRIPT = 2
    IMAGE = 3
    PROFILE = 4
    DATA = 5
    KEEP_ALIVE = 6
    FILE_STREAM = 7
    CANCEL_COMMAND = 8
    EVENT_STATUS = 9
    SCRIPT_SHARED = 10


class Pixmap(object):
    """
    Pixmap representing an uncompressed pixels, ARGB, row-major order.

    :ivar width: width of the image.
    :ivar height: height of the image.
    :ivar row_bytes: bytes per row.
    :ivar color_mode: color mode of the image.
    :ivar channels: number of channels.
    :ivar bits: bits per pixel.
    :ivar data: raw data bytes.
    """

    def __init__(
        self,
        width: int,
        height: int,
        row_bytes: int,
        color_mode: int,
        channels: int,
        bits: int,
        data: bytes,
    ):
        self.width = width
        self.height = height
        self.row_bytes = row_bytes
        self.color_mode = color_mode
        self.channels = channels
        self.bits = bits
        self.data = data

    @classmethod
    def parse(cls, data: bytes) -> Pixmap:
        """Parse Pixmap from data."""
        assert len(data) >= 14
        return cls(*(unpack(">3I3B", data[:15]) + (data[15:],)))

    def dump(self) -> bytes:
        """Dump Pixmap to bytes."""
        header = pack(
            ">3I3B",
            self.width,
            self.height,
            self.row_bytes,
            self.color_mode,
            self.channels,
            self.bits,
        )
        return header + self.data

    def topil(self) -> Image.Image:
        """Convert to PIL Image."""
        if self.width == 0 or self.height == 0:
            return None
        return Image.frombytes(
            "RGBA", (self.width, self.height), self.data, "raw", "ARGB", 0, 1
        )

    def __repr__(self) -> str:
        return "Pixmap(width=%d, height=%d, color=%d, bits=%d, data=%r)" % (
            self.width,
            self.height,
            self.color_mode,
            self.bits,
            self.data if len(self.data) < 12 else self.data[:12] + b"...",
        )


class Protocol(object):
    """
    Photoshop protocol.
    """

    VERSION = 1

    def __init__(self, password: str):
        self.enc = EncryptDecrypt(password.encode("ascii"))

    def send(
        self,
        socket: socket.socket,
        content_type: ContentType,
        data: bytes,
        transaction: int = 0,
        status: int = 0,
    ) -> None:
        """
        Sends data to Photoshop.

        :param content_type: See :py:class:`.ContentType`.
        :param data: `bytes` to send.
        :param transaction: transaction id.
        :param status: execution status, should be 0.
        """
        body = pack(">3I", self.VERSION, transaction, content_type) + data
        encrypted = self.enc.encrypt(body)
        length = 4 + len(encrypted)
        data = pack(">2I", length, status) + encrypted
        logger.debug("Sending %d bytes (total %d bytes)" % (length, len(data)))
        socket.sendall(data)

    def receive(self, socket: socket.socket) -> Dict[str, Any]:
        """
        Receives data from Photoshop.

        :param socket: socket to receive data.
        :return: `dict` of the following fields.

         - `status`: execution status, 0 when success, otherwise error.
         - `protocol`: protocol version, equal to 1.
         - `transaction`: transaction id.
         - `content_type`: data type. See :py:class:`ContentType`.
         - `body`: body of the response data, `dict` for IMAGE type, otherwise
           bytes.

        Example::

            {
                'status': 0,
                'protocol': 1,
                'transaction': 0,
                'content_type': ContentType.SCRIPT,
                'body': b'[ActionDescriptor]'
            }

        :raise AssertionError: if response format is invalid.

        """
        length_bytes = socket.recv(4)
        if len(length_bytes) != 4:
            raise ConnectionError("Empty response, likely connection closed.")
        length: int = unpack(">I", length_bytes)[0]
        assert length >= 4, "length = %d" % length
        body = self._receive_all(socket, length)
        assert (
            len(body) == length
        ), "Expected %d bytes, received %d bytes, password incorrect?" % (
            length,
            len(body),
        )
        status = unpack(">I", body[:4])[0]
        logger.debug("%d bytes returned, status = %d" % (length, status))
        body = body[4:]

        if status:
            raise ValueError(
                "status = %d: likely incorrect password: %r"
                % (
                    status,
                    body[: min(12, len(body))] + (b"" if len(body) <= 12 else b"..."),
                )
            )

        data = self.enc.decrypt(body)
        assert len(data) >= 12
        protocol, transaction, content_type = unpack(">3I", data[:12])
        assert protocol == self.VERSION
        result: Any = data[12:]
        if content_type == ContentType.IMAGE:
            result = self._parse_image(result)
        elif content_type == ContentType.FILE_STREAM:
            result = self._parse_file_stream(result)

        return dict(
            status=status,
            protocol=protocol,
            transaction=transaction,
            content_type=ContentType(content_type),
            body=result,
        )

    def _receive_all(self, socket: socket.socket, length: int) -> bytes:
        """
        Blocks until exactly `length` bytes are read from the socket, or raises
        ConnectionError if the connection is closed before all bytes are received.

        :param socket: The socket to read from.
        :param length: The exact number of bytes to read.
        :return: The bytes read from the socket.
        :raises ConnectionError: If the connection is closed before all bytes are received.
        """
        chunk_size = 4096
        chunks = []
        bytes_received = 0
        while bytes_received < length:
            # Request the remaining part of the data, in chunks of up to 4096 bytes.
            chunk = socket.recv(min(length - bytes_received, chunk_size))
            if not chunk:
                raise ConnectionError(
                    "Socket connection broken. Expected %i bytes but "
                    "received only %i before connection closed." % (length, bytes_received)
                )
            chunks.append(chunk)
            bytes_received += len(chunk)

        # Assemble all chunks into a single bytes object.
        return b"".join(chunks)

    def _parse_image(self, data: bytes) -> Dict[str, Any]:
        assert len(data) > 0
        image_type = data[0]
        if image_type == 1:
            return dict(image_type=image_type, data=data[1:])
        elif image_type == 2:
            return dict(image_type=image_type, data=Pixmap.parse(data[1:]))
        raise ValueError("Unsupported image type: %d" % image_type)

    def _parse_file_stream(self, data: bytes) -> Dict[str, Any]:
        assert len(data) >= 4
        length: int = unpack(">I", data[:4])[0]
        info = json.loads(data[4 : length + 4].decode("utf-8"))
        info["data"] = data[4 + length :]
        return info  # type: ignore
