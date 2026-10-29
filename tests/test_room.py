"""
TV3 - Room & Match
Unit Test cho module Room & Match.

Chạy từ thư mục gốc dự án:
    python -m unittest tests.test_room -v
"""
import unittest

import threading

from Server.room import (
    ALREADY_IN_ROOM,
    INVALID_ARGUMENT,
    INVALID_STATE,
    NOT_HOST,
    NOT_IN_ROOM,
    ROOM_FULL,
    ROOM_NOT_FOUND,
    SPECTATOR_FORBIDDEN,
    Role,
    RoomError,
    RoomManager,
    RoomStatus,
)


class TestRoom(unittest.TestCase):
    def setUp(self):
        self.m = RoomManager()
        self.r = self.m.create_room("an")

    def test_create_assigns_x_to_host(self):
        self.assertEqual(self.r.players[Role.PLAYER_X], "an")
        self.assertEqual(self.r.status, RoomStatus.WAITING)

    def test_join_makes_ready(self):
        self.assertEqual(self.m.join_as_player(self.r.room_id, "binh"), Role.PLAYER_O)
        self.assertEqual(self.r.status, RoomStatus.READY)

    def test_room_full(self):
        self.m.join_as_player(self.r.room_id, "binh")
        with self.assertRaises(RoomError) as c:
            self.m.join_as_player(self.r.room_id, "chi")
        self.assertEqual(c.exception.code, ROOM_FULL)

    def test_cannot_join_twice(self):
        with self.assertRaises(RoomError) as c:
            self.m.join_as_spectator(self.r.room_id, "an")
        self.assertEqual(c.exception.code, ALREADY_IN_ROOM)

    def test_unknown_room(self):
        with self.assertRaises(RoomError) as c:
            self.m.join_as_player("XXXXXX", "binh")
        self.assertEqual(c.exception.code, ROOM_NOT_FOUND)

    def test_only_host_starts(self):
        self.m.join_as_player(self.r.room_id, "binh")
        with self.assertRaises(RoomError) as c:
            self.m.start_match(self.r.room_id, "binh")
        self.assertEqual(c.exception.code, NOT_HOST)

    def test_spectator_cannot_move(self):
        self.m.join_as_player(self.r.room_id, "binh")
        self.m.join_as_spectator(self.r.room_id, "chi")
        self.m.start_match(self.r.room_id, "an")
        with self.assertRaises(RoomError) as c:
            self.m.validate_move_permission("chi", self.r.room_id)
        self.assertEqual(c.exception.code, SPECTATOR_FORBIDDEN)

    def test_spectator_leave_does_not_affect_match(self):
        self.m.join_as_player(self.r.room_id, "binh")
        self.m.join_as_spectator(self.r.room_id, "chi")
        self.m.start_match(self.r.room_id, "an")
        info = self.m.leave_room("chi")
        self.assertFalse(info["match_aborted"])
        self.assertEqual(self.r.status, RoomStatus.PLAYING)

    def test_player_leave_aborts_match(self):
        self.m.join_as_player(self.r.room_id, "binh")
        self.m.start_match(self.r.room_id, "an")
        info = self.m.leave_room("binh")
        self.assertTrue(info["match_aborted"])
        self.assertEqual(info["winner"], "an")

    def test_multiple_rooms_independent(self):
        r2 = self.m.create_room("dung")
        self.assertEqual(len(self.m.list_rooms()), 2)
        self.assertNotEqual(self.r.room_id, r2.room_id)

    def test_list_only_playing(self):
        self.m.join_as_player(self.r.room_id, "binh")
        self.m.start_match(self.r.room_id, "an")
        self.m.create_room("dung")
        self.assertEqual(len(self.m.list_rooms(only_playing=True)), 1)

    # ---- Sửa lỗi: không ghi đè người chơi khi chủ phòng X rời lúc READY
    def test_host_leaves_ready_new_player_gets_free_role(self):
        self.m.join_as_player(self.r.room_id, "binh")        # binh = O
        self.m.leave_room("an")                              # X rời
        self.assertEqual(self.r.status, RoomStatus.WAITING)
        self.assertEqual(self.r.host, "binh")
        role = self.m.join_as_player(self.r.room_id, "chi")
        self.assertEqual(role, Role.PLAYER_X)                # vai còn trống
        self.assertEqual(self.r.players,
                         {Role.PLAYER_O: "binh", Role.PLAYER_X: "chi"})
        self.assertEqual(self.r.status, RoomStatus.READY)
        self.assertEqual(self.m.room_of("binh").room_id, self.r.room_id)

    # ---- Sửa lỗi: phòng không bị kẹt sau khi có người rời giữa trận
    def test_room_reusable_after_player_leaves_mid_match(self):
        self.m.join_as_player(self.r.room_id, "binh")
        self.m.start_match(self.r.room_id, "an")
        self.m.leave_room("binh")
        self.assertEqual(self.r.status, RoomStatus.WAITING)
        self.assertEqual(self.m.join_as_player(self.r.room_id, "chi"),
                         Role.PLAYER_O)
        self.assertEqual(self.r.status, RoomStatus.READY)

    def test_leave_after_finished_returns_to_waiting(self):
        self.m.join_as_player(self.r.room_id, "binh")
        self.m.start_match(self.r.room_id, "an")
        self.m.finish_match(self.r.room_id)
        info = self.m.leave_room("binh")
        self.assertFalse(info["match_aborted"])
        self.assertIsNone(info["winner"])
        self.assertEqual(self.r.status, RoomStatus.WAITING)

    def test_leave_while_ready_back_to_waiting(self):
        self.m.join_as_player(self.r.room_id, "binh")
        self.m.leave_room("binh")
        self.assertEqual(self.r.status, RoomStatus.WAITING)
        self.assertFalse(self.r.is_full())

    def test_last_player_leaves_closes_room_and_frees_spectators(self):
        self.m.join_as_spectator(self.r.room_id, "chi")
        info = self.m.leave_room("an")
        self.assertTrue(info["room_closed"])
        self.assertEqual(self.m.list_rooms(), [])
        self.assertIsNone(self.m.room_of("chi"))
        # khán giả đã được giải phóng, có thể tạo phòng mới
        self.m.create_room("chi")

    def test_leave_when_not_in_room(self):
        with self.assertRaises(RoomError) as c:
            self.m.leave_room("nobody")
        self.assertEqual(c.exception.code, NOT_IN_ROOM)

    # ---- Vòng đời trận
    def test_start_needs_two_players(self):
        with self.assertRaises(RoomError) as c:
            self.m.start_match(self.r.room_id, "an")
        self.assertEqual(c.exception.code, INVALID_STATE)

    def test_start_twice_rejected(self):
        self.m.join_as_player(self.r.room_id, "binh")
        self.m.start_match(self.r.room_id, "an")
        with self.assertRaises(RoomError) as c:
            self.m.start_match(self.r.room_id, "an")
        self.assertEqual(c.exception.code, INVALID_STATE)

    def test_finish_requires_playing(self):
        with self.assertRaises(RoomError) as c:
            self.m.finish_match(self.r.room_id)
        self.assertEqual(c.exception.code, INVALID_STATE)

    def test_rematch_swaps_roles(self):
        self.m.join_as_player(self.r.room_id, "binh")
        self.m.start_match(self.r.room_id, "an")
        self.m.finish_match(self.r.room_id)
        self.m.rematch(self.r.room_id)
        self.assertEqual(self.r.players[Role.PLAYER_X], "binh")
        self.assertEqual(self.r.players[Role.PLAYER_O], "an")
        self.assertEqual(self.r.status, RoomStatus.READY)

    def test_rematch_requires_finished(self):
        self.m.join_as_player(self.r.room_id, "binh")
        with self.assertRaises(RoomError) as c:
            self.m.rematch(self.r.room_id)
        self.assertEqual(c.exception.code, INVALID_STATE)

    def test_move_permission_rules(self):
        self.m.join_as_player(self.r.room_id, "binh")
        with self.assertRaises(RoomError) as c:       # chưa PLAYING
            self.m.validate_move_permission("an", self.r.room_id)
        self.assertEqual(c.exception.code, INVALID_STATE)
        self.m.start_match(self.r.room_id, "an")
        self.m.validate_move_permission("an", self.r.room_id)      # hợp lệ
        with self.assertRaises(RoomError) as c:       # người lạ
            self.m.validate_move_permission("lạ", self.r.room_id)
        self.assertEqual(c.exception.code, NOT_IN_ROOM)

    def test_spectator_can_join_mid_match(self):
        self.m.join_as_player(self.r.room_id, "binh")
        self.m.start_match(self.r.room_id, "an")
        self.assertEqual(self.m.join_as_spectator(self.r.room_id, "chi"),
                         Role.SPECTATOR)
        self.assertEqual(self.r.status, RoomStatus.PLAYING)

    def test_cannot_play_after_match_started(self):
        self.m.join_as_player(self.r.room_id, "binh")
        self.m.start_match(self.r.room_id, "an")
        with self.assertRaises(RoomError) as c:
            self.m.join_as_player(self.r.room_id, "chi")
        self.assertEqual(c.exception.code, ROOM_FULL)

    # ---- Kiểm tra đầu vào
    def test_invalid_username_rejected(self):
        for bad in ("", "   ", None, 123):
            with self.assertRaises(RoomError) as c:
                self.m.create_room(bad)
            self.assertEqual(c.exception.code, INVALID_ARGUMENT)
        with self.assertRaises(RoomError) as c:
            self.m.join_as_player(self.r.room_id, "")
        self.assertEqual(c.exception.code, INVALID_ARGUMENT)
        with self.assertRaises(RoomError) as c:
            self.m.join_as_spectator(self.r.room_id, " ")
        self.assertEqual(c.exception.code, INVALID_ARGUMENT)

    def test_invalid_time_limit_rejected(self):
        for bad in (-5, 0, 1, 99999, "30", None, True):
            with self.assertRaises(RoomError) as c:
                self.m.create_room("x" + str(bad), time_limit=bad)
            self.assertEqual(c.exception.code, INVALID_ARGUMENT)

    def test_default_room_name_and_summary(self):
        self.assertEqual(self.r.name, "Phòng của an")
        s = self.r.to_summary()
        self.assertEqual(s["players"], {"X": "an"})
        self.assertEqual(s["spectator_count"], 0)

    # ---- Đa luồng (đề yêu cầu: nhiều người cùng thao tác)
    def test_concurrent_join_only_one_wins(self):
        results, lock = [], threading.Lock()
        barrier = threading.Barrier(20)

        def worker(i):
            barrier.wait()
            try:
                self.m.join_as_player(self.r.room_id, f"u{i}")
                out = "ok"
            except RoomError as e:
                out = e.code
            with lock:
                results.append(out)

        ts = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(results.count("ok"), 1)
        self.assertEqual(results.count(ROOM_FULL), 19)
        self.assertTrue(self.r.is_full())

    def test_concurrent_create_many_rooms(self):
        def worker(i):
            self.m.create_room(f"host{i}")

        ts = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(len(self.m.list_rooms()), 51)   # +1 phòng của setUp
        ids = {r["room_id"] for r in self.m.list_rooms()}
        self.assertEqual(len(ids), 51)


if __name__ == "__main__":
    unittest.main()