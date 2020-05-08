import enum
import logging
import json
from struct import pack, unpack

from photoshop.crypto import EncryptDecrypt

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
        self, width, height, row_bytes, color_mode, channels, bits, data
    ):
        self.width = width
        self.height = height
        self.row_bytes = row_bytes
        self.color_mode = color_mode
        self.channels = channels
        self.bits = bits
        self.data = data

    @classmethod
    def parse(kls, data):
        """Parse Pixmap from data."""
        assert len(data) >= 14
        return kls(*(unpack('>3I3B', data[:15]) + (data[15:], )))

    def dump(self):
        """Dump Pixmap to bytes."""
        return pack(
            '>3I3B', self.width, self.height, self.row_bytes, self.color_mode,
            self.channels, self.bits
        ) + self.data

    def topil(self):
        """Convert to PIL Image."""
        from PIL import Image
        if self.width == 0 or self.height == 0:
            return None
        return Image.frombytes(
            'RGBA', (self.width, self.height), self.data, 'raw', 'ARGB', 0, 1
        )

    def __repr__(self):
        return 'Pixmap(width=%d, height=%d, color=%d, bits=%d, data=%r)' % (
            self.width, self.height, self.color_mode, self.bits,
            self.data if len(self.data) < 12 else self.data[:12] + b'...'
        )


class Protocol(object):
    """
    Photoshop protocol.
    """
    VERSION = 1

    def __init__(self, password):
        self.enc = EncryptDecrypt(password.encode('ascii'))

    def send(self, socket, content_type, data, transaction=0, status=0):
        """
        Sends data to Photoshop.

        :param content_type: See :py:class:`.ContentType`.
        :param data: `bytes` to send.
        :param transaction: transaction id.
        :param status: execution status, should be 0.
        """
        body = pack('>3I', self.VERSION, transaction, content_type) + data
        encrypted = self.enc.encrypt(body)
        length = 4 + len(encrypted)
        data = pack('>2I', length, status) + encrypted
        logger.debug('Sending %d bytes (total %d bytes)' % (length, len(data)))
        socket.sendall(data)

    def receive(self, socket):
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
        length = socket.recv(4)
        if len(length) != 4:
            raise ConnectionError('Empty response, likely connection closed.')
        length = unpack('>I', length)[0]
        assert length >= 4, 'length = %d' % length
        body = socket.recv(length)
        assert len(body) == length, (
            'Expected %d bytes, received %d bytes, password incorrect?' %
            (length, len(body))
        )
        status = unpack('>I', body[:4])[0]
        logger.debug('%d bytes returned, status = %d' % (length, status))
        body = body[4:]

        if status:
            raise ValueError(
                'status = %d: likely incorrect password: %r' % (
                    status, body[:min(12, len(body))] +
                    (b'' if len(body) <= 12 else b'...')
                )
            )

        data = self.enc.decrypt(body)
        assert len(data) >= 12
        protocol, transaction, content_type = unpack('>3I', data[:12])
        assert protocol == self.VERSION
        body = data[12:]
        if content_type == ContentType.IMAGE:
            body = self._parse_image(body)
        elif content_type == ContentType.FILE_STREAM:
            body = self._parse_file_stream(body)

        return dict(
            status=status,
            protocol=protocol,
            transaction=transaction,
            content_type=ContentType(content_type),
            body=body
        )

    def _parse_image(self, data):
        assert len(data) > 0
        image_type = data[0]
        if image_type == 1:
            return dict(image_type=image_type, data=data[1:])
        elif image_type == 2:
            return dict(image_type=image_type, data=Pixmap.parse(data[1:]))
        raise ValueError('Unsupported image type: %d' % image_type)

    def _parse_file_stream(self, data):
        assert len(data) >= 4
        length = unpack('>I', data[:4])[0]
        info = json.loads(data[4:length + 4].decode('utf-8'))
        info['data'] = data[4 + length:]
        return info
