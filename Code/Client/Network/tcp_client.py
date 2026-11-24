import socket
import threading
from collections.abc import Callable
from typing import Any

from ...Shared.Protocol.messages import MAX_MESSAGE_BYTES, decode_message, encode_message

MessageHandler = Callable[[dict[str, Any]], None]


class TCPClient:
    def __init__(self, on_message: MessageHandler) -> None:
        self._on_message = on_message
        self._socket: socket.socket | None = None
        self._reader: threading.Thread | None = None
        self._send_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._closed = threading.Event()
        self._closed.set()

    @property
    def is_connected(self) -> bool:
        with self._state_lock:
            return self._socket is not None and not self._closed.is_set()

    def connect(self, host: str, port: int, timeout: float = 10.0) -> None:
        if self.is_connected:
            self.close()
        connection = socket.create_connection((host, port), timeout=timeout)
        connection.settimeout(None)
        with self._state_lock:
            self._socket = connection
            self._closed.clear()
            self._reader = threading.Thread(
                target=self._read_messages,
                args=(connection,),
                daemon=True,
            )
            self._reader.start()

    def send(self, message: dict[str, Any]) -> None:
        with self._state_lock:
            connection = self._socket
        if connection is None or self._closed.is_set():
            raise RuntimeError("Client is not connected.")
        payload = encode_message(message)
        with self._send_lock:
            try:
                connection.sendall(payload)
            except OSError as error:
                self._notify_unexpected_close(connection, f"Connection lost: {error}")
                raise

    def close(self) -> None:
        self._closed.set()
        with self._state_lock:
            connection, self._socket = self._socket, None
        if connection is not None:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            finally:
                connection.close()

    def _notify_unexpected_close(self, connection: socket.socket, reason: str) -> None:
        should_emit = False
        with self._state_lock:
            if not self._closed.is_set() and self._socket is connection:
                self._closed.set()
                self._socket = None
                should_emit = True
        try:
            connection.close()
        except OSError:
            pass
        if should_emit:
            self._on_message({
                "type": "CONNECTION_ERROR",
                "code": "CONNECTION_CLOSED",
                "message": reason,
            })

    def _read_messages(self, connection: socket.socket) -> None:
        stream = None
        try:
            stream = connection.makefile("rb")
            while not self._closed.is_set():
                raw = stream.readline(MAX_MESSAGE_BYTES + 1)
                if not raw:
                    self._notify_unexpected_close(connection, "Server closed the connection.")
                    return
                message = decode_message(raw)
                self._on_message(message)
        except (OSError, ValueError) as error:
            self._notify_unexpected_close(connection, str(error))
        finally:
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
            with self._state_lock:
                if self._socket is connection:
                    self._socket = None
                    self._closed.set()
            try:
                connection.close()
            except OSError:
                pass
            