"""Exercise the real GUI message handler without opening a Tk window."""

import unittest
from unittest.mock import Mock, patch

from Code.Client.GUI import app as app_module
from Code.Client.GUI.app import CaroApp
from Code.Client.Network.client_sync import ClientStateSync


class TestClientRoomUpdates(unittest.TestCase):
    def setUp(self):
        self.app = CaroApp.__new__(CaroApp)
        self.app.room_id = "ROOM_A"
        self.app.sync = ClientStateSync("Alice", ui_callback=lambda *_: None)
        self.app.sync.handle_server_message({
            "type": "SYNC_FULL_STATE", "room_id": "ROOM_A", "status": "PLAYING",
            "players": {"X": "Alice", "O": "Bobby"}, "spectators": ["Viewer"],
            "current_turn": "X", "board": [[""] * 15 for _ in range(15)],
        })
        self.app.show_room_view = Mock()
        self.app.show_game_view = Mock()

    def test_spectator_leave_update_keeps_current_board(self):
        self.app._handle_message({"type": "SPECTATOR_LEFT", "room_id": "ROOM_A",
                                  "spectator": "Viewer", "spectator_count": 0})
        self.app._handle_message({"type": "ROOM_UPDATED", "room": {
            "room_id": "ROOM_A", "status": "PLAYING",
            "players": {"X": "Alice", "O": "Bobby"}, "spectators": [],
        }})
        self.app.show_room_view.assert_not_called()
        self.assertEqual(self.app.sync.status, "PLAYING")
        self.assertTrue(self.app.sync.can_make_move()[0])

    def test_paused_and_finished_board_stays_visible_on_room_update(self):
        for match_status, room_status in (("PAUSED", "PLAYING"), ("FINISHED", "FINISHED")):
            with self.subTest(status=match_status):
                self.app.sync.status = match_status
                self.app._handle_message({"type": "ROOM_UPDATED", "room": {
                    "room_id": "ROOM_A", "status": room_status,
                }})
                self.app.show_room_view.assert_not_called()

    def test_player_leave_returns_remaining_player_to_waiting_room(self):
        room = {"room_id": "ROOM_A", "status": "WAITING", "players": {"X": "Alice"}}
        self.app._handle_message({"type": "ROOM_UPDATED", "room": room})
        self.app.show_room_view.assert_called_once_with(room)

    def test_old_room_update_does_not_pull_user_back(self):
        self.app.room_id = None
        self.app._handle_message({"type": "ROOM_UPDATED", "room": {
            "room_id": "ROOM_A", "status": "PLAYING",
        }})
        self.app.show_room_view.assert_not_called()
        self.assertIsNone(self.app.room_id)

    def test_room_joined_still_opens_waiting_room(self):
        room = {"room_id": "ROOM_B", "status": "READY"}
        self.app._handle_message({"type": "ROOM_JOINED", "room": room})
        self.app.show_room_view.assert_called_once_with(room)

    def test_room_player_text_uses_server_role_mapping(self):
        room = {
            "room_id": "ROOM_B",
            "status": "READY",
            "players": {"X": "Alice", "O": "Bobby"},
        }
        self.assertEqual(
            CaroApp._format_room_players(room),
            "Alice: X\nBobby: O",
        )

    def test_room_view_displays_server_players(self):
        self.app.root = Mock()
        self.app.client = Mock()
        self.app.username = "Alice"
        self.app.room_id = None
        self.app._show = Mock()

        with patch.object(app_module.ttk, "Frame"), \
                patch.object(app_module.ttk, "Label") as label, \
                patch.object(app_module.ttk, "Button"):
            CaroApp.show_room_view(self.app, {
                "room_id": "ROOM_B",
                "status": "READY",
                "players": {"X": "Alice", "O": "Bobby"},
            })

        label_texts = [call.kwargs.get("text") for call in label.call_args_list]
        self.assertIn("Alice: X\nBobby: O", label_texts)

    def test_room_closed_returns_client_to_lobby_and_clears_room_state(self):
        self.app.username = "Alice"
        self.app.show_lobby_view = Mock()
        self.app._room_action_pending = False
        self.app._leaving_room = False
        self.app._handle_message({"type": "ROOM_CLOSED", "room_id": "ROOM_A"})

        self.assertIsNone(self.app.room_id)
        self.assertIsNone(self.app.sync.room_id)
        self.assertEqual(self.app.sync.board, [])
        self.app.show_lobby_view.assert_called_once_with()

    def test_leave_waits_for_server_confirmation_before_returning_to_lobby(self):
        self.app.client = Mock()
        self.app._leaving_room = False
        self.app.show_lobby_view = Mock()

        self.app.leave_room()

        self.app.client.send.assert_called_once_with({"type": "LEAVE_ROOM"})
        self.assertEqual(self.app.room_id, "ROOM_A")
        self.app.show_lobby_view.assert_not_called()

        self.app.username = "Alice"
        self.app._handle_message({"type": "ROOM_LEFT", "room_id": "ROOM_A"})

        self.assertIsNone(self.app.room_id)
        self.app.show_lobby_view.assert_called_once_with()

    def test_invitation_rejection_is_shown_to_sender(self):
        self.app.username = "Alice"
        self.app.status_bar = Mock()

        with patch.object(app_module.messagebox, "showinfo") as showinfo:
            self.app._handle_message({
                "type": "INVITE_RESULT",
                "from": "Alice",
                "to": "Bobby",
                "status": "REJECTED",
            })

        self.app.status_bar.set_message.assert_called_once_with(
            "Bobby đã từ chối lời mời đấu.", "warning"
        )
        showinfo.assert_called_once_with(
            "Lời mời bị từ chối", "Bobby đã từ chối lời mời đấu."
        )

    def test_invitation_acceptance_is_shown_before_entering_game(self):
        self.app.username = "Alice"
        self.app.status_bar = Mock()

        self.app._handle_message({
            "type": "INVITE_RESULT",
            "from": "Alice",
            "to": "Bobby",
            "status": "ACCEPTED",
        })

        self.app.status_bar.set_message.assert_called_once_with(
            "Bobby đã chấp nhận lời mời đấu.", "success"
        )


if __name__ == "__main__":
    unittest.main()
