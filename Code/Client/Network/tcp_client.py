"""Thread-safe newline-delimited JSON client."""

import socket
import threading
from collections.abc import Callable
from typing import Any
from ...Shared.Protocol.messages import decode_message, encode_message

MessageHandler = Callable[[dict[str, Any]], None]


class TCPClient:
    def __init__(self, on_message: MessageHandler) -> None:
        self._on_message = on_message
        self._socket: socket.socket | None = None
        self._reader: threading.Thread | None = None
        self._send_lock = threading.Lock()
        self._closed = threading.Event()

    def connect(self, host: str, port: int) -> None:
        if self._socket is not None:
            raise RuntimeError("Client is already connected.")
        connection = socket.create_connection((host, port), timeout=10)
        connection.settimeout(None)
        self._socket = connection
        self._closed.clear()
        self._reader = threading.Thread(target=self._read_messages, daemon=True)
        self._reader.start()

    def send(self, message: dict[str, Any]) -> None:
        connection = self._socket
        if connection is None:
            raise RuntimeError("Client is not connected.")
        payload = encode_message(message)
        with self._send_lock:
            connection.sendall(payload)

    def close(self) -> None:
        self._closed.set()
        connection, self._socket = self._socket, None
        if connection is not None:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            finally:
                connection.close()

    def _read_messages(self) -> None:
        connection = self._socket
        if connection is None:
            return
        try:
            stream = connection.makefile("rb")
            while not self._closed.is_set():
                raw = stream.readline(1_000_001)
                if not raw:
                    break
                message = decode_message(raw)
                self._on_message(message)
        except (OSError, UnicodeDecodeError, ValueError) as error:
            if not self._closed.is_set():
                self._on_message({
                    "type": "CONNECTION_ERROR",
                    "message": str(error),
                })
        finally:
            stream.close()
            connection.close()
            if self._socket is connection:
                self._socket = None
            self._closed.set()
