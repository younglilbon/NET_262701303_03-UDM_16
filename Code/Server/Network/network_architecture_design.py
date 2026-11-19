"""Entry point for the shared threaded TCP server."""

from .tcp_server import TCPServer


if __name__ == "__main__":
    TCPServer().serve_forever()