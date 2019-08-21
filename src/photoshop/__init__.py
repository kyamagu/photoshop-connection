import contextlib
import socket
import logging
from jinja2 import Environment, PackageLoader

from photoshop.protocol import Protocol, ContentType
from photoshop.api import Kevlar

logger = logging.getLogger(__name__)


class PhotoshopConnection(Kevlar):
    """
    Photoshop session.

    :param password: Password for the connection, configured in Photoshop.
    :param host: IP address of Photoshop host, default `localhost`.
    :param port: Connection port default to 49494.
    :param validator: Validate function for ECMAscript.

        Example::

            from esprima import parseScript
            with PhotoshopConnection(password='secret', validator=parseScript) as c:
                c.execute('bad_script +')  # Raises an Error

    :raise ConnectionRefusedError: if failed to connect to Photoshop.
    """
    _env = Environment(
        loader=PackageLoader('photoshop', 'api'), trim_blocks=True
    )

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

    def _check_response(self, response, txn=None):
        message = None
        if response['status']:
            self._reset_connection()
            message = 'ERROR %d: %r' % (response['status'], response['body'])
        if response['content_type'] == ContentType.ILLEGAL:
            self._reset_connection()
            message = 'ILLEGAL: %r' % response['body']
        if response['content_type'] == ContentType.ERROR_STRING:
            message = response['body'].decode('utf-8')
        if message:
            logger.exception(message)
            raise RuntimeError(message)
        if txn is not None and response['transaction'] is not None:
            assert response['transaction'] == txn
        logger.debug(response)

    def _execute(self, template_file, context, **kwargs):
        command = self._env.get_template(template_file).render(context)
        logger.debug('Command:\n%s' % command)
        return self.execute(command, **kwargs)

    def execute(self, script, receive_output=False):
        """
        Execute the given ExtendScript in Photoshop.

        :param script: ExtendScript to execute in Photoshop.
        :param receive_output: Indicates extra return value is returned from
            Photoshop.
        :return: `dict`. See :py:meth:`~photoshop.protocol.Protocol.receive`.

        :raise RuntimeError: if error happens in remote.
        :raise AssertionError: if unexpected response is returned.
        """
        if self.validator:
            self.validator(script)

        with self._transaction() as txn:
            self.protocol.send(
                self.socket, ContentType.SCRIPT, script.encode('utf-8'), txn
            )
            response = self.protocol.receive(self.socket)
            self._check_response(response, txn)
            if receive_output:
                second_response = self.protocol.receive(self.socket)
                self._check_response(second_response, txn)
                # This is the return value from executeAction().
                if response.get('body') == b'[ActionDescriptor]':
                    response = second_response

        return response

    def upload(self, data, suffix=None):
        """
        Upload arbitrary data to Photoshop, and returns the file path where the
        data is saved.

        :param data: `bytes` to send.
        :param suffix: suffix to append to the temporary file name.
        :return: Temporary server-side file path in `str`.
        :raise RuntimeError: if error happens in remote.
        :raise AssertionError: if unexpected response is returned.

        Example::

            with open('/path/to/example.psd', 'rb') as f:
                filepath = conn.upload(f.read())
            conn.open(filepath, 'photoshop')
        """
        with self._transaction() as txn:
            self.protocol.send(self.socket, ContentType.DATA, data, txn)
            response = self.protocol.receive(self.socket)
            self._check_response(response, txn)
        path = response.get('body', b'').decode('utf-8')
        if suffix:
            new_path = path + suffix
            self.execute(
                'var f = File("%s"); f.copy("%s"); f.remove()' %
                (path, new_path)
            )
            path = new_path
        return path

    def open(self, path, file_type=None, smart_object=False):
        """
        Open the specified document.

        :param path: file path on the server.
        :param file_type: file type. default is `None`. This must be one of the
            following:

            - 'ALIASPIX'
            - 'BMP'
            - 'CAMERARAW'
            - 'COMPUSERVEGIF'
            - 'DICOM'
            - 'ELECTRICIMAGE'
            - 'EPS'
            - 'EPSPICTPREVIEW'
            - 'EPSTIFFPREVIEW'
            - 'FILMSTRIP'
            - 'JPEG'
            - 'PCX'
            - 'PDF'
            - 'PHOTOCD'
            - 'PHOTOSHOP'
            - 'PHOTOSHOPDCS_1'
            - 'PHOTOSHOPDCS_2'
            - 'PHOTOSHOPEPS'
            - 'PHOTOSHOPPDF'
            - 'PICTFILEFORMAT'
            - 'PICTRESOURCEFORMAT'
            - 'PIXAR'
            - 'PNG'
            - 'PORTABLEBITMAP'
            - 'RAW'
            - 'SCITEXCT'
            - 'SGIRGB'
            - 'SOFTIMAGE'
            - 'TARGA'
            - 'TIFF'
            - 'WAVEFRONTRLA'
            - 'WIRELESSBITMAP'

        :param smart_object: open as a smart object.
        """
        if file_type:
            file_type = 'OpenDocumentType.%s' % file_type.upper()
        else:
            file_type = 'undefined'
        self._execute('open.js.j2', locals())
        # TODO: Create and return document wrapper.

    def download(self, path, file_type=None):
        """
        Download the specified document. The file type must be in the format
        supported by Photoshop.

        :param path: file path on the server.

        :return: `dict`. See return type of
            :py:meth:`~PhotoshopConnection.get_document_stream`
        """
        self.open(path, file_type, True)
        data = self.get_document_stream()
        self.execute('activeDocument.close(SaveOptions.DONOTSAVECHANGES)')
        return data

    def ping(self):
        """
        Send keep alive signal to Photoshop.

        :raise RuntimeError: if error happens in remote.
        :raise AssertionError: if unexpected response is returned.
        """
        with self._transaction() as txn:
            self.protocol.send(self.socket, ContentType.KEEP_ALIVE, b'', txn)
            response = self.protocol.receive(self.socket)
            self._check_response(response, txn)
        assert (
            response['content_type'] == ContentType.SCRIPT and
            response['body'] == b'Yep, still alive'
        )
