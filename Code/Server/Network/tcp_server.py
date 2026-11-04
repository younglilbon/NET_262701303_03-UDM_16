"""Newline-delimited JSON TCP server."""

import socketserver
import threading
from typing import Any

from ..application import ServerApplication
from ...Shared.Protocol.messages import (
    MAX_MESSAGE_BYTES,
    decode_message,
    encode_message,
)


class _ClientHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        while True:
            raw = self.rfile.readline(MAX_MESSAGE_BYTES + 1)
            if not raw:
                return
            if len(raw) > MAX_MESSAGE_BYTES or not raw.endswith(b"\n"):
                self.server.send_message(self.request, {
                    "type": "ERROR",
                    "code": "MESSAGE_TOO_LARGE",
                    "message": "Message exceeds the maximum size.",
                })
                return
            try:
                message = decode_message(raw)
            except (UnicodeDecodeError, ValueError) as error:
                self.server.send_message(self.request, {
                    "type": "ERROR",
                    "code": "INVALID_JSON",
                    "message": str(error),
                })
                continue
            self.server.application.handle_message(self.request, message)

    def finish(self) -> None:
        try:
            super().finish()
        finally:
            self.server.application.disconnect(self.request)


class _ThreadedTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int]) -> None:
        self._send_locks: dict[Any, threading.Lock] = {}
        self._send_locks_lock = threading.Lock()
        self.application = ServerApplication(self.send_message)
        super().__init__(address, _ClientHandler)

    def send_message(self, connection: Any, message: dict[str, Any]) -> None:
        if connection is None:
            return
        with self._send_locks_lock:
            lock = self._send_locks.setdefault(connection, threading.Lock())
        payload = encode_message(message)
        with lock:
            connection.sendall(payload)


class TCPServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8888) -> None:
        self._server = _ThreadedTCPServer((host, port))

    @property
    def address(self) -> tuple[str, int]:
        return self._server.server_address

    def serve_forever(self) -> None:
        print(f"Server listening on {self.address[0]}:{self.address[1]}")
        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            print("Stopping server...")
        finally:
            self._server.server_close()


if __name__ == "__main__":
    TCPServer().serve_forever()
