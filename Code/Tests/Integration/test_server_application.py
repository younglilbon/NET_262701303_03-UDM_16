import unittest
import tempfile
import json
import threading
from unittest.mock import Mock, patch

from Code.Client.GUI.app import CaroApp
from Code.Client.Network.client_sync import ClientStateSync

from Code.Server.Room_Match.models import RoomStatus
from Code.Server.User_Lobby.models import PlayerStatus
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
        for timer in self.app.sync._reconnect_timers.values():
            timer.cancel()

    def _create_room(self, playing=False, spectators=0):
        self.app.handle_message(self.alice, {"type": "CREATE_ROOM"})
        room_id = self._last_message(self.alice, "ROOM_CREATED")["room"]["room_id"]
        self.spectators = []
        if playing:
            self.app.handle_message(self.bob, {"type": "JOIN_ROOM", "room_id": room_id})
            self.app.handle_message(self.alice, {"type": "START_MATCH", "room_id": room_id})
        for i in range(spectators):
            connection = object()
            name = f"Viewer{i}"
            self.app.handle_message(connection, {"type": "LOGIN", "name": name})
            self.app.handle_message(connection, {"type": "JOIN_AS_SPECTATOR", "room_id": room_id})
            self.spectators.append((name, connection))
        return room_id

    def _history(self):
        with open(self.app.sync.history_file, encoding="utf-8") as stream:
            return json.load(stream)

    def test_last_player_leave_releases_all_spectators_before_sending(self):
        room_id = self._create_room(spectators=3)
        original_send = self.app._transport_send

        def observe(connection, message):
            if message["type"] == "ROOM_CLOSED":
                self.assertNotIn(room_id, self.app.sync.rooms)
                self.assertEqual(self.app.rooms.list_rooms(), [])
                for name, conn in self.spectators:
                    self.assertIsNone(self.app.rooms.room_of(name))
                    self.assertEqual(self.app.players.get_player(conn).status, PlayerStatus.ONLINE)
            original_send(connection, message)

        self.app._transport_send = observe
        self.app.handle_message(self.alice, {"type": "LEAVE_ROOM"})
        self._last_message(self.alice, "ROOM_LEFT")
        for name, conn in self.spectators:
            self.assertEqual(self._last_message(conn, "ROOM_CLOSED")["reason"], "NO_PLAYERS")
            self.assertNotIn(name, self.app.sync.user_room_map)
        self.assertEqual(self.app.players.get_player(self.alice).status, PlayerStatus.ONLINE)

    def test_leave_playing_commits_resign_once_and_preserves_history(self):
        room_id = self._create_room(playing=True, spectators=1)
        state = self.app.sync.rooms[room_id]
        self.app.handle_message(self.alice, {"type": "LEAVE_ROOM"})
        self.assertEqual(self.app.rooms.get_room(room_id).host, "Bobby")
        self.assertEqual(self.app.rooms.get_room(room_id).status, RoomStatus.WAITING)
        self.assertNotIn("Alice", self.app.sync.user_room_map)
        self.assertNotIn(room_id, self.app.sync._turn_timers)
        self.assertEqual(state.players, {"X": "Alice", "O": "Bobby"})
        self.assertEqual(self._history()[0]["reason"], "RESIGN")
        self.assertEqual(self._history()[0]["players"], state.players)
        self.app.sync.finish_and_save_match(room_id, "X", "TIMEOUT")
        finished = [m for m in self.sent[self.bob] if m["type"] == "MATCH_FINISHED"]
        self.assertEqual(len(finished), 1)
        self.assertEqual(finished[0]["winner"], "O")
        self.assertEqual(len(self._history()), 1)
        self.app.handle_message(self.alice, {"type": "MOVE", "row": 0, "col": 0})
        self.assertEqual(self._last_message(self.alice, "ERROR")["code"], "NOT_IN_ROOM")

    def test_leave_paused_releases_offline_opponent_and_closes_room(self):
        room_id = self._create_room(playing=True, spectators=2)
        self.app.disconnect(self.bob)
        self.assertEqual(self.app.sync.rooms[room_id].status, "PAUSED")
        self.assertIsNotNone(self.app.rooms.room_of("Bobby"))
        self.app.handle_message(self.alice, {"type": "LEAVE_ROOM"})
        self.assertEqual(self.app.rooms.list_rooms(), [])
        self.assertNotIn(room_id, self.app.sync.rooms)
        self.assertFalse(self.app.sync._reconnect_timers)
        self.assertIsNone(self.app.rooms.room_of("Bobby"))
        for _, conn in self.spectators:
            self._last_message(conn, "ROOM_CLOSED")
        self.assertEqual(self._history()[0]["reason"], "RESIGN")
        self.assertEqual(self._history()[0]["winner"], "O")

    def test_socket_failure_does_not_interrupt_cleanup_or_other_recipients(self):
        self._create_room(spectators=3)
        original_send = self.app._transport_send
        broken = self.spectators[0][1]

        def fail_one(connection, message):
            if connection is broken:
                raise BrokenPipeError("disconnected client")
            original_send(connection, message)

        self.app._transport_send = fail_one
        with self.assertLogs(level="ERROR"):
            self.app.handle_message(self.alice, {"type": "LEAVE_ROOM"})
        self.assertEqual(self.app.rooms.list_rooms(), [])
        for _, conn in self.spectators[1:]:
            self._last_message(conn, "ROOM_CLOSED")

    def test_spectator_leave_does_not_replace_timer_or_result(self):
        room_id = self._create_room(playing=True, spectators=2)
        timer = self.app.sync._turn_timers[room_id]
        name, conn = self.spectators[0]
        self.app.handle_message(conn, {"type": "LEAVE_ROOM"})
        self.assertIs(self.app.sync._turn_timers[room_id], timer)
        self.assertIsNone(self.app.sync.rooms[room_id].result)
        self.assertNotIn(name, self.app.sync.user_room_map)
        self._last_message(self.bob, "SPECTATOR_LEFT")

    def test_players_keep_game_view_and_can_move_after_spectator_leaves(self):
        room_id = self._create_room(playing=True, spectators=1)
        clients = {}
        offsets = {}
        for name, conn in (("Alice", self.alice), ("Bobby", self.bob)):
            gui = CaroApp.__new__(CaroApp)
            gui.room_id = room_id
            gui.sync = ClientStateSync(name, ui_callback=lambda *_: None)
            gui.sync.handle_server_message(self.app.sync.match_snapshot(room_id))
            gui.show_room_view = Mock()
            gui.show_game_view = Mock()
            clients[conn] = gui
            offsets[conn] = len(self.sent[conn])
        _, spectator = self.spectators[0]
        self.app.handle_message(spectator, {"type": "LEAVE_ROOM"})
        self.app.handle_message(self.alice, {"type": "MOVE", "row": 7, "col": 7})
        self.app.handle_message(self.bob, {"type": "MOVE", "row": 7, "col": 8})
        for conn, gui in clients.items():
            for message in self.sent[conn][offsets[conn]:]:
                self.assertNotIn(message["type"], ("MATCH_FINISHED", "ROOM_CLOSED"))
                gui._handle_message(message)
            gui.show_room_view.assert_not_called()
            self.assertEqual(gui.sync.board[7][7:9], ["X", "O"])
            self.assertEqual(gui.sync.status, "PLAYING")
        self.assertEqual(self.app.rooms.get_room(room_id).status, RoomStatus.PLAYING)

    def test_disconnect_after_finished_removes_seat_without_resign(self):
        room_id = self._create_room(playing=True)
        self.app.sync.finish_and_save_match(room_id, "X", "TIMEOUT")
        self.app.disconnect(self.bob)
        self.assertIsNone(self.app.rooms.room_of("Bobby"))
        self.assertEqual(self.app.rooms.get_room(room_id).status, RoomStatus.WAITING)
        self.assertEqual(len(self._history()), 1)
        self.assertEqual(self._history()[0]["reason"], "TIMEOUT")

    def test_close_keeps_failed_history_pending(self):
        room_id = self._create_room(playing=True)
        self.app.disconnect(self.bob)
        match_id = self.app.sync.rooms[room_id].match_id
        with patch.object(self.app.sync, "_append_history_to_file", return_value=False):
            self.app.handle_message(self.alice, {"type": "LEAVE_ROOM"})
        self.assertNotIn(room_id, self.app.sync.rooms)
        self.assertIn(match_id, self.app.sync._pending_history)
        self.assertNotIn(match_id, self.app.sync._saved_matches)
        self.assertEqual(self.app.sync._pending_history[match_id]["players"]["O"], "Bobby")

    def test_network_and_history_effects_run_without_data_locks(self):
        self._create_room(playing=True)
        checked = []

        def check_locks(*args):
            acquired = []
            def probe():
                for lock in (self.app.coordinator.lock, self.app.sync.lock, self.app.players.lock):
                    ok = lock.acquire(timeout=0.5)
                    acquired.append(ok)
                    if ok:
                        lock.release()
            worker = threading.Thread(target=probe)
            worker.start()
            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
            self.assertEqual(acquired, [True, True, True])
            checked.append(True)
            return True

        self.app._transport_send = check_locks
        with patch.object(self.app.sync, "_append_history_to_file", side_effect=check_locks):
            self.app.handle_message(self.alice, {"type": "LEAVE_ROOM"})
        self.assertGreaterEqual(len(checked), 3)

    def test_stale_match_callback_cannot_finish_new_match(self):
        room_id = self._create_room(playing=True)
        old_id = self.app.sync.rooms[room_id].match_id
        self.app.sync.finish_and_save_match(room_id, "X", "TIMEOUT")
        self.app.rooms.rematch(room_id)
        self.app.rooms.start_match(room_id, "Alice")
        self.app._start_match(self.app.rooms.get_room(room_id))
        self.app._match_finished(room_id, "O", "RESIGN", old_id)
        self.app.sync._expire_turn(room_id, "X", old_id)
        self.assertEqual(self.app.rooms.get_room(room_id).status, RoomStatus.PLAYING)
        self.assertEqual(self.app.sync.rooms[room_id].status, "PLAYING")

    def _race(self, *actions):
        barrier = threading.Barrier(len(actions))
        errors = []
        def run(action):
            try:
                barrier.wait(timeout=2)
                action()
            except Exception as error:
                errors.append(error)
        workers = [threading.Thread(target=run, args=(action,)) for action in actions]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=3)
        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertEqual(errors, [])

    def test_concurrent_start_and_leave_has_no_orphan_match(self):
        room_id = self._create_room()
        self.app.handle_message(self.bob, {"type": "JOIN_ROOM", "room_id": room_id})
        self._race(
            lambda: self.app.handle_message(self.alice, {"type": "START_MATCH", "room_id": room_id}),
            lambda: self.app.handle_message(self.bob, {"type": "LEAVE_ROOM"}),
        )
        self.assertEqual(self.app.rooms.get_room(room_id).status, RoomStatus.WAITING)
        self.assertIsNone(self.app.rooms.room_of("Bobby"))
        self.assertNotIn("Bobby", self.app.sync.user_room_map)
        self.assertNotIn(room_id, self.app.sync._turn_timers)
        state = self.app.sync.match_snapshot(room_id)
        self.assertTrue(state is None or state["status"] == "FINISHED")

    def test_concurrent_finish_and_leave_commits_one_result(self):
        room_id = self._create_room(playing=True)
        self._race(
            lambda: self.app.sync.finish_and_save_match(room_id, "O", "TIMEOUT"),
            lambda: self.app.handle_message(self.alice, {"type": "LEAVE_ROOM"}),
        )
        finished = [m for m in self.sent[self.bob] if m["type"] == "MATCH_FINISHED"]
        self.assertEqual(len(finished), 1)
        records = self._history()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["reason"], finished[0]["reason"])
        self.assertEqual(records[0]["winner"], "O")
        self.assertEqual(self.app.rooms.get_room(room_id).status, RoomStatus.WAITING)

    def test_spectator_disconnect_preserves_timer_and_releases_membership(self):
        room_id = self._create_room(playing=True, spectators=1)
        timer = self.app.sync._turn_timers[room_id]
        name, connection = self.spectators[0]
        self.app.disconnect(connection)
        self.assertIsNone(self.app.rooms.room_of(name))
        self.assertNotIn(name, self.app.sync.user_room_map)
        self.assertIs(self.app.sync._turn_timers[room_id], timer)
        self._last_message(self.bob, "SPECTATOR_LEFT")

    def test_late_events_from_closed_room_do_not_affect_users_new_room(self):
        old_room = self._create_room(playing=True)
        old_id = self.app.sync.rooms[old_room].match_id
        self.app.handle_message(self.alice, {"type": "LEAVE_ROOM"})
        self.app.handle_message(self.bob, {"type": "LEAVE_ROOM"})
        self.app.handle_message(self.alice, {"type": "CREATE_ROOM"})
        new_room = self.app.rooms.room_of("Alice").room_id
        self.app.sync._expire_reconnect(old_room, "Alice", old_id)
        self.app._match_finished(old_room, "O", "DISCONNECT", old_id)
        self.assertEqual(self.app.rooms.room_of("Alice").room_id, new_room)
        self.assertEqual(self.app.players.get_player(self.alice).status, PlayerStatus.IN_ROOM)

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
