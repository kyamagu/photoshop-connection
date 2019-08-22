import contextlib
import socket
import threading
import queue
import logging
import os
from jinja2 import Environment, PackageLoader

from photoshop.protocol import Protocol, ContentType
from photoshop.api import Kevlar

logger = logging.getLogger(__name__)


class Transaction(object):
    """Transaction class."""
    _id = 0

    def __init__(self, protocol, socket):
        self.id = self._id
        self.queue = queue.Queue()
        self.protocol = protocol
        self.socket = socket
        self._id += 1

    @classmethod
    def reset(cls, value=0):
        cls._id = value

    def send(self, content_type, data):
        self.protocol.send(self.socket, content_type, data, self.id)

    def receive(self, timeout=10):
        try:
            response = self.queue.get(timeout=timeout)
        except queue.Empty as e:
            raise RuntimeError('TIMEOUT: %s' % e)
        message = None
        if response['status']:
            message = 'ERROR %d: %r' % (response['status'], response['body'])
        if response['content_type'] == ContentType.ILLEGAL:
            message = 'ILLEGAL: %r' % response['body']
        if response['content_type'] == ContentType.ERROR_STRING:
            message = response['body'].decode('utf-8')
        if message:
            logger.exception(message)
            raise RuntimeError(message)

        message = '%s' % response
        logger.debug(message if len(message) < 256 else message[:256] + '...')
        return response


def dispatch(socket, protocol, transactions):
    """Receive response and dispatch transactions."""
    logger.debug('Dispatch thread starts.')
    while True:
        try:
            response = protocol.receive(socket)
        except OSError as e:
            logger.debug('Socket closed.')
            break
        except (AssertionError, ValueError) as e:
            logger.exception(e)
            break
        transaction_id = response.get('transaction')
        if transaction_id is None:
            raise RuntimeError('Invalid response: %s' % response)
        txn = transactions.get(response.get('transaction'))
        if not txn:
            raise RuntimeError('Transaction not found: %s' % response)
        txn.queue.put(response)
    logger.debug('Dispatch thread terminates.')


class PhotoshopConnection(Kevlar):
    """
    Photoshop session.

    :param password: Password for the connection, configured in Photoshop. If
        `None`, try to get password from `PHOTOSHOP_PASSWORD` environment
        variable.
    :param host: IP address of Photoshop host, default `localhost`.
    :param port: Connection port default to 49494.
    :param validator: Validate function for ECMAscript.

        Example::

            from esprima import parseScript
            with PhotoshopConnection(validator=parseScript) as c:
                c.execute('bad_script +')  # Raises an Error

    :raise ConnectionRefusedError: if failed to connect to Photoshop.
    """
    _env = Environment(
        loader=PackageLoader('photoshop', 'api'), trim_blocks=True
    )

    def __init__(
        self, password=None, host='localhost', port=49494, validator=None
    ):
        password = password or os.getenv('PHOTOSHOP_PASSWORD')
        assert password is not None
        self.dispatcher = None
        self.transactions = dict()
        self.protocol = Protocol(password)
        self.host = host
        self.port = port
        self.socket = None
        self.validator = validator
        self._reset_connection()

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, ex_type, ex_value, trace):
        self.close()

    def close(self):
        """
        Close the session.
        """
        if self.socket:
            logger.debug('Closing the connection.')
            self.socket.close()
            self.socket = None
        if self.dispatcher:
            self.dispatcher.join()
            self.dispatcher = None

    def _reset_connection(self):
        logger.debug('Opening the connection.')
        self.close()
        try:
            Transaction.reset()
            self.transactions = dict()
            self.socket = socket.create_connection((self.host, self.port))
            self.dispatcher = threading.Thread(
                target=dispatch,
                args=(self.socket, self.protocol, self.transactions),
                daemon=True
            )
            self.dispatcher.start()
        except ConnectionRefusedError:
            logger.exception(
                'Is Photoshop running and configured for remote connection?'
            )
            raise

    @contextlib.contextmanager
    def _transaction(self):
        txn = Transaction(self.protocol, self.socket)
        self.transactions[txn.id] = txn
        reset = False
        try:
            yield txn
            txn.queue.task_done()
        except queue.Empty as e:
            logger.error(e)
            reset = True
        finally:
            del self.transactions[txn.id]
            if reset:
                self._reset_connection()

    def _execute(self, template_file, context, **kwargs):
        command = self._env.get_template(template_file).render(context)
        logger.debug('Command:\n%s' % command)
        return self.execute(command, **kwargs)

    def execute(self, script, receive_output=False, timeout=10):
        """
        Execute the given ExtendScript in Photoshop.

        :param script: ExtendScript to execute in Photoshop.
        :param receive_output: Indicates extra return value is returned from
            Photoshop.
        :param timeout: Timeout in seconds to wait for response.
        :return: `dict`. See :py:meth:`~photoshop.protocol.Protocol.receive`.

        :raise RuntimeError: if error happens in remote.
        """
        if self.validator:
            self.validator(script)

        with self._transaction() as txn:
            txn.send(ContentType.SCRIPT, script.encode('utf-8'))
            response = txn.receive(timeout=timeout)

            if receive_output:
                second_response = txn.receive(timeout=timeout)
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

        Example::

            with open('/path/to/example.psd', 'rb') as f:
                filepath = conn.upload(f.read(), suffix='.psd')
            conn.open_document(filepath)
        """
        with self._transaction() as txn:
            txn.send(ContentType.DATA, data)
            response = txn.receive()

        path = response.get('body', b'').decode('utf-8')
        if suffix:
            new_path = path + suffix
            self.execute(
                'var f = File("%s"); f.copy("%s"); f.remove()' %
                (path, new_path)
            )
            path = new_path
        return path

    def open_document(self, path, file_type=None, smart_object=False):
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
        :return: `dict` of response.
        """
        if file_type:
            file_type = 'OpenDocumentType.%s' % file_type.upper()
        else:
            file_type = 'undefined'
        return self._execute('open.js.j2', locals())

    def download(self, path, file_type=None):
        """
        Download the specified document. The file type must be in the format
        supported by Photoshop.

        :param path: file path on the server.
        :return: `dict`. See return type of
            :py:meth:`~PhotoshopConnection.get_document_stream`
        """
        self.open_document(path, file_type, True)
        data = self.get_document_stream()
        self.execute('activeDocument.close(SaveOptions.DONOTSAVECHANGES)')
        return data

    def ping(self, timeout=10):
        """
        Send keep alive signal to Photoshop.

        :param timeout: Timeout in seconds to wait for response.
        :raise RuntimeError: if error happens in remote.
        """
        with self._transaction() as txn:
            txn.send(ContentType.KEEP_ALIVE, b'')
            response = txn.receive(timeout=timeout)
        assert (
            response['content_type'] == ContentType.SCRIPT and
            response['body'] == b'Yep, still alive'
        )
