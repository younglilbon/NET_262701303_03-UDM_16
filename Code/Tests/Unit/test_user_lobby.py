"""Unit tests for TV2 player, lobby, and invitation behavior."""

import unittest

from Code.Server.User_Lobby.invitation import InvitationManager
from Code.Server.User_Lobby.login import LoginService
from Code.Server.User_Lobby.models import PlayerStatus
from Code.Server.User_Lobby.online_list import OnlineList
from Code.Server.User_Lobby.player_management import PlayerManager


class TestUserLobby(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.players = PlayerManager()
        self.online_list = OnlineList(self.players, self._send)
        self.login = LoginService(self.players, self.online_list, self._send)
        self.alice = object()
        self.bob = object()

    def _send(self, connection, message):
        self.sent.append((connection, message.copy()))

    def _messages_for(self, connection, message_type):
        return [
            message for target, message in self.sent
            if target is connection and message["type"] == message_type
        ]

    def test_player_names_follow_rules_and_are_unique_case_insensitively(self):
        for name in ("ab", "a" * 21, "_alice", "alice_", "alice!"):
            with self.subTest(name=name):
                self.assertFalse(self.players.is_valid_name(name))
        for name in ("Alice", "player_2", "User-03"):
            with self.subTest(name=name):
                self.assertTrue(self.players.is_valid_name(name))

        self.assertTrue(self.login.handle_login(self.alice, "Alice"))
        self.assertFalse(self.login.handle_login(self.bob, "aLiCe"))
        self.assertEqual(self.players.get_online_players(), ["Alice"])
        self.assertEqual(self._messages_for(self.bob, "ERROR")[-1]["type"], "ERROR")

    def test_login_broadcasts_online_list_and_disconnect_allows_reconnect(self):
        self.assertTrue(self.login.handle_login(self.alice, "Alice"))
        self.assertTrue(self.login.handle_login(self.bob, "Bobby"))
        self.assertEqual(self._messages_for(self.alice, "LOGIN_RESULT")[-1]["status"], "OK")
        self.assertEqual(
            self._messages_for(self.alice, "PLAYER_LIST")[-1]["players"],
            ["Alice", "Bobby"],
        )

        disconnected = self.players.disconnect(self.bob)
        self.assertEqual(disconnected.status, PlayerStatus.OFFLINE)
        self.assertEqual(self.players.get_online_players(), ["Alice"])
        replacement = object()
        player, error = self.players.login(replacement, "Bobby")
        self.assertIsNone(error)
        self.assertEqual(player.status, PlayerStatus.ONLINE)
        self.assertEqual(self.players.connection_for("Bobby"), replacement)

    def test_invalid_login_does_not_change_online_list(self):
        self.assertFalse(self.login.handle_login(self.alice, "x"))
        self.assertIsNone(self.players.get_player(self.alice))
        self.assertEqual(self.players.get_online_players(), [])
        self.assertEqual(self._messages_for(self.alice, "ERROR")[-1]["type"], "ERROR")

    def test_invitation_acceptance_calls_room_integration_and_notifies_both(self):
        self.login.handle_login(self.alice, "Alice")
        self.login.handle_login(self.bob, "Bobby")
        accepted = []
        invitations = InvitationManager(
            self.players,
            self._send,
            on_accept=lambda sender, recipient: accepted.append((sender, recipient)),
        )

        self.assertTrue(invitations.invite(self.alice, "Bobby"))
        invite = self._messages_for(self.bob, "INVITE")[-1]
        self.assertEqual(self.players.get_player(self.alice).status, PlayerStatus.INVITE_PENDING)
        self.assertTrue(invitations.respond(self.bob, invite["invite_id"], True))

        self.assertEqual(accepted, [("Alice", "Bobby")])
        self.assertEqual(self.players.get_player(self.alice).status, PlayerStatus.ONLINE)
        self.assertEqual(self.players.get_player(self.bob).status, PlayerStatus.ONLINE)
        for connection in (self.alice, self.bob):
            self.assertEqual(
                self._messages_for(connection, "INVITE_RESULT")[-1]["status"],
                "ACCEPTED",
            )

    def test_rejected_invitation_restores_availability_without_starting_room(self):
        self.login.handle_login(self.alice, "Alice")
        self.login.handle_login(self.bob, "Bobby")
        accepted = []
        invitations = InvitationManager(
            self.players,
            self._send,
            on_accept=lambda *players: accepted.append(players),
        )

        invitations.invite(self.alice, "Bobby")
        invite = self._messages_for(self.bob, "INVITE")[-1]
        self.assertTrue(invitations.respond(self.bob, invite["invite_id"], False))

        self.assertEqual(accepted, [])
        self.assertEqual(self.players.get_player(self.alice).status, PlayerStatus.ONLINE)
        self.assertEqual(self.players.get_player(self.bob).status, PlayerStatus.ONLINE)
        self.assertEqual(
            self._messages_for(self.alice, "INVITE_RESULT")[-1]["status"],
            "REJECTED",
        )


if __name__ == "__main__":
    unittest.main()
