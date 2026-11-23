"""Exercise TV2 lobby messages through real TCP sockets."""

import socket
import threading
import unittest

from Code.Server.Network.tcp_server import _ThreadedTCPServer
from Code.Shared.Protocol.messages import decode_message, encode_message


class TcpPeer:
    def __init__(self, address):
        self.socket = socket.create_connection(address, timeout=3)
        self.socket.settimeout(3)
        self.buffer = b""
        self.messages = []

    def send(self, message):
        self.socket.sendall(encode_message(message))

    def receive(self, message_type):
        for message in self.messages:
            if message["type"] == message_type:
                self.messages.remove(message)
                return message

        while True:
            while b"\n" in self.buffer:
                raw_message, self.buffer = self.buffer.split(b"\n", 1)
                message = decode_message(raw_message + b"\n")
                if message["type"] == message_type:
                    return message
                self.messages.append(message)

            data = self.socket.recv(4096)
            if not data:
                raise AssertionError(
                    f"Connection closed while waiting for {message_type}"
                )
            self.buffer += data

    def close(self):
        try:
            self.socket.shutdown(socket.SHUT_WR)
            while self.socket.recv(4096):
                pass
        finally:
            self.socket.close()


class TestUserLobbyTcpIntegration(unittest.TestCase):
    def setUp(self):
        self.server = _ThreadedTCPServer(("127.0.0.1", 0))
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.server_thread.start()
        self.addCleanup(self._stop_server)

    def _stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=3)
        self.assertFalse(self.server_thread.is_alive())

    def _connect(self):
        peer = TcpPeer(self.server.server_address)
        self.addCleanup(peer.close)
        return peer

    def _login(self, peer, name):
        peer.send({"type": "LOGIN", "name": name})
        result = peer.receive("LOGIN_RESULT")
        self.assertEqual(result["status"], "OK")
        peer.receive("PLAYER_LIST")

    def test_invite_offline_player_is_rejected(self):
        alice = self._connect()
        self._login(alice, "Alice")

        alice.send({
            "type": "INVITE",
            "target": "Bobby"
        })

        error = alice.receive("ERROR")
        self.assertEqual(
            error["message"],
            "Target player is not online"
        )

        alice.send({"type": "PLAYER_LIST"})
        online_list = alice.receive("PLAYER_LIST")
        self.assertEqual(online_list["players"], ["Alice"])

    def test_login_online_list_invitation_and_room_roles(self):
        alice = self._connect()
        bob = self._connect()
        self._login(alice, "Alice")
        self._login(bob, "Bobby")

        online_list = alice.receive("PLAYER_LIST")
        self.assertEqual(online_list["players"], ["Alice", "Bobby"])

        alice.send({"type": "INVITE", "target": "Bobby"})
        invitation = bob.receive("INVITE")
        self.assertEqual(invitation["from"], "Alice")
        alice.receive("INVITE_RESULT")

        bob.send({
            "type": "INVITE_RESPONSE",
            "invite_id": invitation["invite_id"],
            "accepted": False,
        })
        self.assertEqual(alice.receive("INVITE_RESULT")["status"], "REJECTED")
        self.assertEqual(bob.receive("INVITE_RESULT")["status"], "REJECTED")

        alice.send({"type": "CREATE_ROOM", "name": "TCP test"})
        created = alice.receive("ROOM_CREATED")["room"]
        self.assertEqual(created["players"], {"X": "Alice"})

        bob.send({"type": "JOIN_ROOM", "room_id": created["room_id"]})
        joined = bob.receive("ROOM_JOINED")
        self.assertEqual(joined["role"], "O")
        self.assertEqual(
            joined["room"]["players"],
            {"X": "Alice", "O": "Bobby"},
        )

    
    def test_accept_invitation_starts_room_for_both_players(self):
        alice = self._connect()
        bob = self._connect()

        self._login(alice, "Alice")
        self._login(bob, "Bobby")

        alice.send({
            "type": "INVITE",
            "target": "Bobby"
        })

        invitation = bob.receive("INVITE")
        pending = alice.receive("INVITE_RESULT")
        self.assertEqual(pending["status"], "PENDING")

        bob.send({
            "type": "INVITE_RESPONSE",
            "invite_id": invitation["invite_id"],
            "accepted": True
        })

        alice_result = alice.receive("INVITE_RESULT")
        bob_result = bob.receive("INVITE_RESULT")

        self.assertEqual(alice_result["status"], "ACCEPTED")
        self.assertEqual(bob_result["status"], "ACCEPTED")

        alice_room = alice.receive("ROOM_STARTED")
        bob_room = bob.receive("ROOM_STARTED")

        self.assertEqual(
            alice_room["room_id"],
            bob_room["room_id"]
        )

        bob.send({
            "type": "INVITE_RESPONSE",
            "invite_id": invitation["invite_id"],
            "accepted": True
        })

        error = bob.receive("ERROR")
        self.assertEqual(error["message"], "Invitation is not pending")


    def test_accept_invitation_after_sender_logout_is_rejected(self):
        alice = self._connect()
        bob = self._connect()

        self._login(alice, "Alice")
        self._login(bob, "Bobby")

        alice.send({
            "type": "INVITE",
            "target": "Bobby"
        })

        invitation = bob.receive("INVITE")
        alice.receive("INVITE_RESULT")

        alice.send({"type": "LOGOUT"})

        cancelled = bob.receive("INVITE_RESULT")
        self.assertEqual(cancelled["status"], "CANCELLED")

        bob.send({
            "type": "INVITE_RESPONSE",
            "invite_id": invitation["invite_id"],
            "accepted": True
        })

        error = bob.receive("ERROR")
        self.assertEqual(
            error["message"],
            "Invitation is not pending"
        )

        bob.send({"type": "PLAYER_LIST"})
        online_list = bob.receive("PLAYER_LIST")
        self.assertEqual(online_list["players"], ["Bobby"])


    def test_invite_player_who_is_in_match_is_rejected(self):
        alice = self._connect()
        bob = self._connect()
        carol = self._connect()

        self._login(alice, "Alice")
        self._login(bob, "Bobby")
        self._login(carol, "Carol")

        carol.send({
            "type": "CREATE_ROOM",
            "name": "Test busy player"
        })
        created = carol.receive("ROOM_CREATED")
        room_id = created["room"]["room_id"]

        bob.send({
            "type": "JOIN_ROOM",
            "room_id": room_id
        })
        bob.receive("ROOM_JOINED")

        carol.send({
            "type": "START_MATCH",
            "room_id": room_id
        })

        carol.receive("ROOM_STARTED")
        bob.receive("ROOM_STARTED")

        alice.send({
            "type": "INVITE",
            "target": "Bobby"
        })

        error = alice.receive("ERROR")

        self.assertEqual(
            error["message"],
            "One of the players is not available"
        )


    def test_two_players_invite_same_recipient_only_first_is_pending(self):
        alice = self._connect()
        bob = self._connect()
        carol = self._connect()

        self._login(alice, "Alice")
        self._login(bob, "Bobby")
        self._login(carol, "Carol")

        bob.send({
            "type": "INVITE",
            "target": "Alice"
        })

        first_invitation = alice.receive("INVITE")
        bob_result = bob.receive("INVITE_RESULT")

        self.assertEqual(bob_result["status"], "PENDING")
        self.assertEqual(first_invitation["from"], "Bobby")

        carol.send({
            "type": "INVITE",
            "target": "Alice"
        })

        second_error = carol.receive("ERROR")
        self.assertEqual(
            second_error["message"],
            "One of the players is not available"
        )

        alice.send({
            "type": "INVITE_RESPONSE",
            "invite_id": first_invitation["invite_id"],
            "accepted": True
        })

        alice_result = alice.receive("INVITE_RESULT")
        bob_result = bob.receive("INVITE_RESULT")

        self.assertEqual(alice_result["status"], "ACCEPTED")
        self.assertEqual(bob_result["status"], "ACCEPTED")

        alice_room = alice.receive("ROOM_STARTED")
        bob_room = bob.receive("ROOM_STARTED")

        self.assertEqual(
            alice_room["room_id"],
            bob_room["room_id"]
        )

        self.assertNotIn(
            "ROOM_STARTED",
            [message["type"] for message in carol.messages]
        )


if __name__ == "__main__":
    unittest.main()
