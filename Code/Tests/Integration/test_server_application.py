import unittest
import tempfile

from Code.Server.Room_Match.models import RoomStatus
from Code.Server.application import ServerApplication


class TestServerApplication(unittest.TestCase):
    def setUp(self):
        self.sent = {}

        def send(connection, message):
            self.sent.setdefault(connection, []).append(message)

        self.app = ServerApplication(send)
        temporary_history = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_history.cleanup)
        self.app.sync.history_file = temporary_history.name + "\\match_history.json"
        self.alice = object()
        self.bob = object()
        self.app.handle_message(self.alice, {"type": "LOGIN", "name": "Alice"})
        self.app.handle_message(self.bob, {"type": "LOGIN", "name": "Bobby"})

    def tearDown(self):
        for room_id in list(self.app.sync._turn_timers):
            self.app.sync._cancel_turn_timeout(room_id)

    def _last_message(self, connection, message_type):
        return next(
            message
            for message in reversed(self.sent[connection])
            if message["type"] == message_type
        )

    def test_invite_to_game_uses_one_consistent_flow(self):
        self.app.handle_message(
            self.alice, {"type": "INVITE", "target": "Bobby"}
        )
        invite = self._last_message(self.bob, "INVITE")
        self.app.handle_message(self.bob, {
            "type": "INVITE_RESPONSE",
            "invite_id": invite["invite_id"],
            "accepted": True,
        })

        room_id = self._last_message(self.alice, "ROOM_STARTED")["room_id"]
        room = self.app.rooms.get_room(room_id)
        state = self.app.sync.rooms[room_id]
        self.assertEqual(room.status, RoomStatus.PLAYING)
        self.assertEqual(state.players, {"X": "Alice", "O": "Bobby"})

        for col in range(5):
            success, _ = self.app.sync.sync_move(room_id, "Alice", 7, col)
            self.assertTrue(success)
            if col < 4:
                success, _ = self.app.sync.sync_move(
                    room_id, "Bobby", 5, col
                )
                self.assertTrue(success)

        self.assertEqual(state.winner, "X")
        self.assertEqual(room.status, RoomStatus.FINISHED)
        self.assertIn(
            "MATCH_FINISHED",
            [message["type"] for message in self.sent[self.alice]],
        )

    def test_room_commands_share_room_and_match_state(self):
        self.app.handle_message(self.alice, {
            "type": "CREATE_ROOM",
            "name": "Test room",
        })
        room_id = self._last_message(self.alice, "ROOM_CREATED")["room"]["room_id"]
        self.app.handle_message(self.bob, {
            "type": "JOIN_ROOM",
            "room_id": room_id,
        })
        self.app.handle_message(self.alice, {
            "type": "START_MATCH",
            "room_id": room_id,
        })
        self.assertEqual(self.app.rooms.get_room(room_id).status, RoomStatus.PLAYING)
        self.assertEqual(self.app.sync.rooms[room_id].status, "PLAYING")


if __name__ == "__main__":
    unittest.main()
