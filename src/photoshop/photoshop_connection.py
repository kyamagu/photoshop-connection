"""
Photoshop session.
"""
from __future__ import annotations

import contextlib
import logging
import os
import queue
import socket
import threading
from typing import Any, Callable, Dict, Iterator, List, Optional, Type

from jinja2 import Environment, FileSystemLoader
from photoshop.api import Event, Kevlar
from photoshop.protocol import ContentType, Protocol

logger = logging.getLogger(__name__)


class Transaction(object):
    """Transaction class."""

    _id = 0
    lock = threading.Lock()

    def __init__(self, protocol: Protocol, socket: socket.socket, lock: threading.Lock):
        self.id = self._id
        self.queue: queue.Queue = queue.Queue()
        self.protocol = protocol
        self.socket = socket
        self.lock = lock
        self.__class__._id += 1

    @classmethod
    def reset(cls, value: int = 0) -> None:
        cls._id = value

    def send(self, content_type: ContentType, data: bytes) -> None:
        with self.lock:
            self.protocol.send(self.socket, content_type, data, self.id)

    def receive(self, **kwargs: Any) -> Dict[str, Any]:
        response = self.queue.get(**kwargs)
        self.queue.task_done()

        if isinstance(response, Exception):
            raise response

        assert response["status"] == 0
        assert response["content_type"] not in (
            ContentType.ILLEGAL,
            ContentType.ERROR_STRING,
        )
        message = "%s" % response
        logger.debug(message if len(message) < 256 else message[:256] + "...")
        return response  # type: ignore


def dispatch(
    socket: socket.socket, protocol: Protocol, transactions: Dict[str, Transaction]
) -> None:
    """Receive response and dispatch transactions."""
    thread = threading.current_thread()
    logger.debug("%s: Dispatch thread starts." % thread.name)
    while True:
        try:
            response = protocol.receive(socket)
            if response["content_type"] == ContentType.ILLEGAL:
                raise RuntimeError("Illegal response: %s" % response)
            elif response["content_type"] == ContentType.ERROR_STRING:
                raise RuntimeError(
                    "Error: %s" % response["body"].decode("utf-8", "ignore")
                )

            transaction_id = response["transaction"]
            with Transaction.lock:
                txn = transactions.get(transaction_id)
                if not isinstance(txn, Transaction):
                    raise RuntimeError("Transaction not found: %s" % response)
                txn.queue.put(response)
        except Exception as e:
            # If any exception happens, send that to all transaction threads.
            with Transaction.lock:
                logger.debug("%s: %s" % (thread.name, e))
                for txn in transactions.values():
                    txn.queue.put(e)
            break
    logger.debug("%s: Dispatch thread terminates." % thread.name)


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

    Example::

        from photoshop import PhotoshopConnection

        with PhotoshopConnection(password='secret', host='192.168.0.1') as conn:
            conn.execute('alert("hi");')
    """

    _env = Environment(
        loader=FileSystemLoader(
            os.path.join(os.path.abspath(os.path.dirname(__file__)), "api")
        ),
        trim_blocks=True,
    )

    def __init__(
        self,
        password: Optional[str] = None,
        host: str = "localhost",
        port: int = 49494,
        validator: Optional[Callable[[str], None]] = None,
    ):
        _password = password or os.getenv("PHOTOSHOP_PASSWORD")
        assert _password is not None
        self.dispatcher: Optional[threading.Thread] = None
        self.transactions: Dict[int, Transaction] = dict()
        self.protocol = Protocol(_password)
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.validator = validator
        self.lock = threading.Lock()
        self.subscribers: List[threading.Thread] = []
        self._reset_connection()

    def __del__(self) -> None:
        self.close()

    def __enter__(self) -> PhotoshopConnection:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        traceback: Optional[Any],
    ) -> None:
        self.close()

    def close(self) -> None:
        """
        Close the session.
        """
        if self.socket:
            logger.debug("Closing the connection.")
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()
            self.socket = None
        if self.dispatcher:
            self.dispatcher.join()
            self.dispatcher = None
        for thread in self.subscribers:
            thread.join()
        self.subscribers = []

    def _reset_connection(self) -> None:
        logger.debug("Opening the connection.")
        self.close()
        try:
            Transaction.reset()
            self.transactions = dict()
            self.socket = socket.create_connection((self.host, self.port))
            self._start_dispatcher()
        except ConnectionRefusedError:
            logger.exception(
                "Is Photoshop running and configured for remote connection?"
            )
            raise

    def _start_dispatcher(self) -> None:
        self.dispatcher = threading.Thread(
            target=dispatch,
            args=(self.socket, self.protocol, self.transactions),
            daemon=True,
        )
        self.dispatcher.start()

    @contextlib.contextmanager
    def _transaction(self) -> Iterator[Transaction]:
        assert self.socket is not None
        with Transaction.lock:
            txn = Transaction(self.protocol, self.socket, self.lock)
            self.transactions[txn.id] = txn
        try:
            assert self.dispatcher and self.dispatcher.is_alive()
            yield txn
        except Exception as e:
            logger.exception(e)
            raise
        finally:
            with Transaction.lock:
                logger.debug("Delete txn %d" % txn.id)
                del self.transactions[txn.id]

    def _render(self, template_file: str, context: Dict[str, Any]) -> str:
        """
        Render script template.
        """
        command = self._env.get_template(template_file).render(context)
        # logger.debug('Command:\n%s' % command)
        return command

    def execute(
        self, script: str, receive_output: bool = False, timeout: Optional[float] = None
    ) -> Dict[str, Any]:
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
            txn.send(ContentType.SCRIPT_SHARED, script.encode("utf-8"))
            response = txn.receive(timeout=timeout)

            if receive_output:
                second_response = txn.receive(timeout=timeout)
                # This is the return value from executeAction().
                if response.get("body") == b"[ActionDescriptor]":
                    response = second_response

        return response

    def upload(self, data: bytes, suffix: Optional[str] = None) -> str:
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

        path: str = response.get("body", b"").decode("utf-8")
        if suffix:
            new_path = path + suffix
            self.execute(
                'var f = File("%s"); f.copy("%s"); f.remove()' % (path, new_path)
            )
            path = new_path
        return path

    def open_document(
        self, path: str, file_type: Optional[str] = None, smart_object: bool = False
    ) -> Dict[str, Any]:
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
        return self.execute(self._render("open.js.j2", locals()))

    def download(
        self, path: str, file_type: Optional[str] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Download the specified document. The file type must be in the format
        supported by Photoshop.

        :param path: file path on the server.
        :param file_type: file type, see :py:meth:`open_document`.
        :return: `dict`. See return type of
            :py:meth:`~PhotoshopConnection.get_document_stream`
        """
        smart_object = True
        script = "\n".join(
            (
                self._render("open.js.j2", locals()),
                self._render("sendDocumentStreamToNetworkClient.js.j2", locals()),
            )
        )
        logger.debug(script)
        response = self.execute(script, receive_output=True)
        self.execute("activeDocument.close(SaveOptions.DONOTSAVECHANGES);")
        return response.get("body")  # type: ignore

    def ping(self, timeout: float = 10.0) -> None:
        """
        Send keep alive signal to Photoshop.

        :param timeout: Timeout in seconds to wait for response.
        :raise RuntimeError: if error happens in remote.
        """
        with self._transaction() as txn:
            txn.send(ContentType.KEEP_ALIVE, b"")
            response = txn.receive(timeout=timeout)
        assert (
            response["content_type"] == ContentType.SCRIPT
            and response["body"] == b"Yep, still alive"
        )

    def subscribe(
        self,
        event: str,
        callback: Callable[[PhotoshopConnection, Optional[bytes]], bool],
        block: bool = False,
        **kwargs: Any,
    ) -> None:
        """
        Subscribe to changes, sends any relevant change info back on subscribing
        socket.

        :param event: Event name, one of :py:class:`~photoshop.Event`.
        :param callback: Callable that takes two arguments:

            - `conn`: :py:class:`~photoshop.PhotoshopConnection` instance.
            - `data`: `bytes` data returned from Photoshop on this event. The
              actual data format varies by event type.

              Return value of `callback` signals termination of the current
              subscription. If `callback` returns True, subscription stops.

        :param block: Block until subscription finishes. default `False`.

        Example::

            import json
            import time

            def handler(conn, data):
                print(json.loads(data.decode('utf-8')))
                return True  # This terminates subscription

            with PhotoshopConnection() as conn:
                conn.subscribe('imageChanged', handler)
                conn.execute('documents.add()')
                time.sleep(5)
        """
        assert callable(callback)
        thread = threading.Thread(
            target=listen_event, args=(self, event, callback), daemon=True
        )
        self.subscribers.append(thread)
        thread.start()
        if block:
            thread.join()


def listen_event(
    self: PhotoshopConnection,
    event: str,
    callback: Callable[[PhotoshopConnection, Optional[bytes]], bool],
) -> None:
    event = Event(event)
    begin = self._render("networkEventSubscribe.js.j2", dict(event=event))
    with self._transaction() as txn:
        txn.send(ContentType.SCRIPT_SHARED, begin.encode("utf-8"))
        try:
            while True:
                response = txn.receive()
                data: bytes = response.get("body")  # type: ignore
                if data == b"[ActionDescriptor]":
                    continue
                lines = data.split(b"\r", 1)
                assert lines[0].decode("utf-8") == event
                result = callback(self, lines[1] if len(lines) else None)
                if result:
                    break
        except Exception as e:
            if not isinstance(e, OSError):
                logger.error("%s" % e)
            return

    end = self._render("networkEventUnsubscribe.js.j2", dict(event=event))
    with self._transaction() as txn:
        txn.send(ContentType.SCRIPT_SHARED, end.encode("utf-8"))
        assert txn.receive().get("body") == b"[ActionDescriptor]"
