"""Phase-three entry point using the shared JSON TCP protocol."""

from .tcp_server import TCPServer


if __name__ == "__main__":
    TCPServer().serve_forever()
