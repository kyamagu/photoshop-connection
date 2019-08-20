import contextlib
import socket
import logging

from photoshop.protocol import Protocol, ContentType
from photoshop.api import Kevlar

logger = logging.getLogger(__name__)


class PhotoshopConnection(Kevlar):
    """
    Execute the given ExtendScript in Photoshop.

    :param password: Password for the connection, configured in Photoshop.
    :param host: IP address of Photoshop host, default `localhost`.
    :param port: Connection port default to 49494.
    :param validator: Validate function for ECMAscript.

        Example::

            from esprima import parseScript
            with PhotoshopConnection(password='secret', validator=parseScript) as c:
                c.execute('bad_script +')  # Raises an Error

    :raises ConnectionRefusedError: if failed to connect to Photoshop.
    """

    def __init__(self, password, host='localhost', port=49494, validator=None):
        self.transaction_id = 0
        self.protocol = Protocol(password)
        self.host = host
        self.port = port
        self.socket = None
        self.validator = validator
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
        self.transaction_id = 0
        try:
            self.socket = socket.create_connection((self.host, self.port))
        except ConnectionRefusedError:
            logger.exception(
                'Is Photoshop running and configured for remote connection?'
            )
            raise

    @contextlib.contextmanager
    def _transaction(self):
        try:
            logger.debug('Transaction %d' % self.transaction_id)
            yield self.transaction_id
        finally:
            self.transaction_id += 1

    def execute(self, script, receive_output=False):
        """
        Execute the given ExtendScript in Photoshop.

        :param script: ExtendScript to execute in Photoshop.
        :return: `dict`. See :py:meth:`~photoshop.protocol.Protocol.receive`
        """
        if self.validator:
            self.validator(script)

        with self._transaction() as txn:
            self.protocol.send(
                self.socket, ContentType.SCRIPT, script.encode('utf-8'), txn
            )
            response = self.protocol.receive(self.socket)
            if receive_output:
                second_response = self.protocol.receive(self.socket)
                if response.get('body') == b'[ActionDescriptor]':
                    response = second_response

            logger.debug(response)
            if response.get('transaction') is not None:
                assert response['transaction'] == txn

        if response['status'] or (
            response['content_type'] == ContentType.ILLEGAL
        ):
            self._reset_connection()
        return response
