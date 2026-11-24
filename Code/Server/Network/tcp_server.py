import logging
import socket
import socketserver
import threading
from typing import Any

from ..Application.application import ServerApplication
from ...Shared.Protocol.messages import (
    MAX_MESSAGE_BYTES,
    ProtocolError,
    decode_message,
    encode_message,
    make_error,
)

logger = logging.getLogger(__name__)


class _ClientHandler(socketserver.StreamRequestHandler):
    def setup(self) -> None:
        super().setup()
        self.server.register_connection(self.request)

    def handle(self) -> None:
        while True:
            try:
                raw = self.rfile.readline(MAX_MESSAGE_BYTES + 1)
            except OSError:
                return
            if not raw:
                return
            if len(raw) > MAX_MESSAGE_BYTES:
                self.server.send_message(
                    self.request,
                    make_error("MESSAGE_TOO_LARGE", "Message exceeds the 1,000,000-byte limit."),
                )
                return
            if not raw.endswith(b"\n"):
                self.server.send_message(
                    self.request,
                    make_error("INVALID_MESSAGE", "Message must end with a newline character."),
                )
                return
            try:
                message = decode_message(raw)
            except ProtocolError as error:
                self.server.send_message(self.request, make_error(error.code, str(error)))
                continue
            except ValueError as error:
                self.server.send_message(self.request, make_error("INVALID_JSON", str(error)))
                continue

            try:
                self.server.application.handle_message(self.request, message)
            except Exception:
                logger.exception("Unhandled error while processing %s", message.get("type"))
                self.server.send_message(
                    self.request,
                    make_error("INVALID_STATE", "Internal server error while processing message."),
                )

    def finish(self) -> None:
        try:
            super().finish()
        except OSError:
            pass
        finally:
            self.server.notify_disconnect(self.request)


class _ThreadedTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int]) -> None:
        self._send_locks: dict[Any, threading.Lock] = {}
        self._active_connections: set[Any] = set()
        self._disconnected: set[Any] = set()
        self._state_lock = threading.Lock()
        self.application = ServerApplication(self.send_message)
        super().__init__(address, _ClientHandler)

    def register_connection(self, connection: Any) -> None:
        if connection is None:
            return
        with self._state_lock:
            self._active_connections.add(connection)
            self._send_locks.setdefault(connection, threading.Lock())

    def send_message(self, connection: Any, message: dict[str, Any]) -> None:
        if connection is None:
            return
        with self._state_lock:
            if connection in self._disconnected:
                return
            lock = self._send_locks.setdefault(connection, threading.Lock())
        payload = encode_message(message)
        try:
            with lock:
                connection.sendall(payload)
        except OSError:
            logger.debug("Socket send failed for %s", message.get("type"))
            self.notify_disconnect(connection)

    def close_connection(self, connection: Any) -> None:
        if connection is None:
            return
        try:
            connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            connection.close()
        except OSError:
            pass
        self.notify_disconnect(connection)

    def close_all_connections(self) -> None:
        with self._state_lock:
            connections = list(self._active_connections)
        for connection in connections:
            self.close_connection(connection)

    def notify_disconnect(self, connection: Any) -> None:
        if connection is None:
            return
        with self._state_lock:
            if connection in self._disconnected:
                return
            self._disconnected.add(connection)
            self._active_connections.discard(connection)
            self._send_locks.pop(connection, None)
        try:
            self.application.disconnect(connection)
        finally:
            with self._state_lock:
                self._disconnected.discard(connection)


class TCPServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8888) -> None:
        self._server = _ThreadedTCPServer((host, port))
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> tuple[str, int]:
        return self._server.server_address

    @property
    def application(self) -> ServerApplication:
        return self._server.application

    def start_in_thread(self) -> threading.Thread:
        if self._thread is not None and self._thread.is_alive():
            return self._thread
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        self._server.close_all_connections()
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def serve_forever(self) -> None:
        print(f"Server listening on {self.address[0]}:{self.address[1]}")
        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            print("Stopping server...")
        finally:
            self._server.close_all_connections()
            self._server.server_close()


if __name__ == "__main__":
    TCPServer().serve_forever()
    