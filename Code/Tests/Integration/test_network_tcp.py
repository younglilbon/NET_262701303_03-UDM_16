import socket
import tempfile
import time
import unittest

from Code.Client.Network.tcp_client import TCPClient
from Code.Server.Network.tcp_server import TCPServer
from Code.Shared.Protocol.messages import MAX_MESSAGE_BYTES, decode_message


class TestNetworkTCP(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.server = TCPServer("127.0.0.1", 0)
        self.server.application.sync.history_file = self.temp_dir.name + "\\match_history.json"
        self.server.start_in_thread()
        self.host, self.port = self.server.address
        self.clients: list[TCPClient] = []

    def tearDown(self):
        for client in self.clients:
            client.close()
        for room_id in list(self.server.application.sync._turn_timers):
            self.server.application.sync._cancel_turn_timeout(room_id)
        for timer in self.server.application.sync._reconnect_timers.values():
            timer.cancel()
        self.server.stop()

    def _new_client(self):
        inbox: list[dict] = []
        client = TCPClient(inbox.append)
        client.connect(self.host, self.port)
        self.clients.append(client)
        return client, inbox

    def _wait_for(self, inbox, predicate, timeout=3.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for msg in list(inbox):
                if predicate(msg):
                    return msg
            time.sleep(0.01)
        self.fail(f"Timeout waiting for message; received: {inbox}")

    def _read_until(self, reader, predicate, max_lines=20):
        seen = []
        for _ in range(max_lines):
            raw = reader.readline()
            if not raw:
                self.fail(f"Unexpected EOF while waiting; seen={seen}")
            msg = decode_message(raw)
            seen.append(msg)
            if predicate(msg):
                return msg
        self.fail(f"Did not receive expected message; seen={seen}")

    def test_t19_fragmented_coalesced_malformed_and_oversized(self):
        alice, alice_box = self._new_client()
        alice.send({"type": "LOGIN", "name": "Alice"})
        self._wait_for(alice_box, lambda m: m.get("type") == "LOGIN_RESULT")
        alice.send({"type": "CREATE_ROOM", "name": "RoomT19"})
        room_id = self._wait_for(alice_box, lambda m: m.get("type") == "ROOM_CREATED")["room"]["room_id"]

        raw = socket.create_connection((self.host, self.port), timeout=3.0)
        reader = raw.makefile("rb")
        try:
            frag = b'{"type":"LOGIN","name":"Bobby"}\n'
            for i in range(0, len(frag), 4):
                raw.sendall(frag[i:i + 4])
                time.sleep(0.005)
            login_res = self._read_until(reader, lambda m: m.get("type") == "LOGIN_RESULT")
            self.assertEqual(login_res["status"], "OK")

            coalesced = (
                f'{{"type":"JOIN_ROOM","room_id":"{room_id}"}}\n'.encode("utf-8")
                + b'{"type":"LIST_ROOMS"}\n'
            )
            raw.sendall(coalesced)
            joined = self._read_until(reader, lambda m: m.get("type") == "ROOM_JOINED")
            rooms = self._read_until(reader, lambda m: m.get("type") == "ROOM_LIST")
            self.assertEqual(joined["role"], "O")
            self.assertTrue(isinstance(rooms.get("rooms"), list))

            raw.sendall(b"\xff\xfe\xfd\n")
            err_utf8 = self._read_until(reader, lambda m: m.get("type") == "ERROR")
            self.assertEqual(err_utf8["code"], "INVALID_JSON")

            raw.sendall(b"{broken_json\n")
            err_json = self._read_until(reader, lambda m: m.get("type") == "ERROR")
            self.assertEqual(err_json["code"], "INVALID_JSON")

            raw.sendall(b'["not_an_object"]\n')
            err_type = self._read_until(reader, lambda m: m.get("type") == "ERROR")
            self.assertEqual(err_type["code"], "INVALID_MESSAGE")

            oversized = b'{"type":"LIST_ROOMS","pad":"' + (b"x" * MAX_MESSAGE_BYTES) + b'"}\n'
            raw.sendall(oversized)
            err_big = self._read_until(reader, lambda m: m.get("type") == "ERROR")
            self.assertEqual(err_big["code"], "MESSAGE_TOO_LARGE")
        finally:
            reader.close()
            raw.close()

        alice.send({"type": "LIST_ROOMS"})
        room_list = self._wait_for(
            alice_box,
            lambda m: m.get("type") == "ROOM_LIST" and len(m.get("rooms", [])) == 1,
        )
        self.assertEqual(room_list["rooms"][0]["room_id"], room_id)

    def test_t13_retry_invalid_login_and_unexpected_server_eof(self):
        client, inbox = self._new_client()
        client.send({"type": "LOGIN", "name": "a"})
        err = self._wait_for(inbox, lambda m: m.get("type") == "ERROR")
        self.assertTrue(bool(err.get("message")))

        client.connect(self.host, self.port)
        client.send({"type": "LOGIN", "name": "ValidPlayer"})
        ok = self._wait_for(inbox, lambda m: m.get("type") == "LOGIN_RESULT")
        self.assertEqual(ok["name"], "ValidPlayer")

        self.server.stop()
        conn_err = self._wait_for(inbox, lambda m: m.get("type") == "CONNECTION_ERROR")
        self.assertEqual(conn_err["code"], "CONNECTION_CLOSED")
        self.assertFalse(client.is_connected)


if __name__ == "__main__":
    unittest.main()
