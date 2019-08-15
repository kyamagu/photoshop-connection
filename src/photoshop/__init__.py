import enum
import struct
import socket
import logging

from photoshop.crypto import EncryptDecrypt

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = 1
NO_ERROR = 0


class ContentType(enum.IntEnum):
    """
    Message content type.
    """
    ILLEGAL = 0
    ERRORSTRING = 1
    JAVASCRIPT = 2
    IMAGE = 3
    PROFILE = 4
    DATA = 5


class PhotoshopConnection(object):
    def __init__(self, password, host='localhost', port=49494):
        """
        Execute the given ExtendScript in Photoshop.

        :param password: Password for the connection, configured in Photoshop.
        :param host: IP address of Photoshop host, default `localhost`.
        :param port: Connection port default to 49494.
        :throw ConnectionRefusedError: ConnectionRefusedError
        """
        self.transaction_id = 0
        self.enc = EncryptDecrypt(password.encode())
        self.host = host
        self.port = port
        self.socket = None
        self._reset_connection()

    def __del__(self):
        self._close_connection()

    def __enter__(self):
        return self

    def __exit__(self, ex_type, ex_value, trace):
        self._close_connection()

    def _close_connection(self):
        if self.socket:
            logger.debug('Closing the connection.')
            self.socket.close()
            self.socket = None


    def _reset_connection(self):
        logger.debug('Opening the connection.')
        self._close_connection()
        try:
            self.socket = socket.create_connection((self.host, self.port))
        except ConnectionRefusedError:
            logger.exception(
                'Is Photoshop running and configured for remote connection?'
            )
            raise

    def execute(self, script):
        """
        Execute the given ExtendScript in Photoshop.

        :param script: ExtendScript to execute in Photoshop.
        :return: `dict` of with the following fields:
            - `status`: execution status, 0 when success, otherwise error.
            - `content_type`: data type. See :py:class:`photoshop.ContentType`.
            - `body`: body of the response data.
        """
        # Pack the message.
        self.transaction_id += 1

        message = self._pack(ContentType.JAVASCRIPT, script.encode('utf-8'))
        self.socket.sendall(message)
        return self._parse_response()

    def _pack(self, content_type, data):
        to_enc = struct.pack(
            '>3I', PROTOCOL_VERSION, self.transaction_id, content_type
        ) + data
        encrypted = self.enc.encrypt(to_enc)
        return struct.pack('>2I', 4 + len(encrypted), NO_ERROR) + encrypted

    def _parse_response(self):
        # Parse the result.
        header = self.socket.recv(8)
        assert len(header) == 8, (
            'Invalid response, likely incorrect password: %r' % header
        )
        length, status = struct.unpack('>2I', header)
        logger.debug('%d bytes returned, status = %d' % (length, status))
        length = max(0, length - 4)
        body = self.socket.recv(length)
        assert len(body) == length, ''

        if status > 0:
            logger.error('status = %d: likely incorrect password: %r' % (
                status, body[:min(16, len(body))]
            ))
            self._reset_connection()
            return dict(
                status=status,
                content_type=ContentType.ILLEGAL,
                body=body
            )
        else:
            data = self.enc.decrypt(body)
            protocol, transaction, content_type = struct.unpack(
                '>3I', data[:12]
            )
            assert len(data) >= 12
            logger.debug(
                'protocol = %d, transaction = %d, content type = %d' %
                (protocol, transaction, content_type)
            )
            assert protocol == PROTOCOL_VERSION
            assert transaction == self.transaction_id

            if content_type == ContentType.IMAGE:
                body = self._parse_image(data[12:])
            else:
                body = data[12:]

            return dict(
                status=status,
                content_type=ContentType(content_type),
                body=body
            )

    def _parse_image(data):
        raise NotImplementedError('JPEG/Pixmap is not yet supported.')
