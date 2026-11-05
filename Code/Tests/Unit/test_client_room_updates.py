"""Exercise the real GUI message handler without opening a Tk window."""

import unittest
from unittest.mock import Mock

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


if __name__ == "__main__":
    unittest.main()
