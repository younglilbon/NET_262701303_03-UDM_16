import tempfile
import time
import unittest

from Code.Client.Network.tcp_client import TCPClient
from Code.Server.Network.tcp_server import TCPServer


class TestNetworkLoadT22(unittest.TestCase):
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

    def _connect_user(self, name: str):
        inbox: list[dict] = []
        client = TCPClient(inbox.append)
        client.connect(self.host, self.port)
        self.clients.append(client)
        client.send({"type": "LOGIN", "name": name})
        self._wait_for(inbox, lambda m: m.get("type") == "LOGIN_RESULT")
        return client, inbox

    def _wait_for(self, inbox, predicate, timeout=4.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for msg in list(inbox):
                if predicate(msg):
                    return msg
            time.sleep(0.005)
        self.fail(f"Timeout waiting for message; got {len(inbox)} messages")

    def test_t22_concurrent_rooms_players_and_spectators(self):
        rooms = []
        latencies_ms = []

        for idx in range(3):
            p1, box1 = self._connect_user(f"PlayerX_{idx}")
            p2, box2 = self._connect_user(f"PlayerO_{idx}")

            t0 = time.monotonic()
            p1.send({"type": "CREATE_ROOM", "name": f"Arena_{idx}", "time_limit": 30})
            created = self._wait_for(box1, lambda m: m.get("type") == "ROOM_CREATED")
            latencies_ms.append((time.monotonic() - t0) * 1000)

            room_id = created["room"]["room_id"]
            p2.send({"type": "JOIN_ROOM", "room_id": room_id})
            self._wait_for(box2, lambda m: m.get("type") == "ROOM_JOINED")
            p1.send({"type": "START_MATCH", "room_id": room_id})
            self._wait_for(box1, lambda m: m.get("type") == "SYNC_FULL_STATE")
            self._wait_for(box2, lambda m: m.get("type") == "SYNC_FULL_STATE")
            rooms.append((room_id, p1, box1, p2, box2))

        spectators = []
        for s_idx in range(2):
            spec, s_box = self._connect_user(f"Spectator_{s_idx}")
            target_room_id = rooms[s_idx][0]
            spec.send({"type": "JOIN_AS_SPECTATOR", "room_id": target_room_id})
            self._wait_for(s_box, lambda m: m.get("type") == "SYNC_FULL_STATE")
            spectators.append((target_room_id, spec, s_box))

        for r_idx, (room_id, p1, box1, p2, box2) in enumerate(rooms):
            for step in range(3):
                t0 = time.monotonic()
                p1.send({"type": "MOVE", "row": r_idx, "col": step})
                move_x = self._wait_for(
                    box2,
                    lambda m, rid=room_id, c=step: m.get("type") == "SYNC_MOVE"
                    and m.get("room_id") == rid
                    and m["move"]["col"] == c
                    and m["move"]["symbol"] == "X",
                )
                latencies_ms.append((time.monotonic() - t0) * 1000)
                self.assertEqual(move_x["move"]["row"], r_idx)

                p2.send({"type": "MOVE", "row": r_idx + 5, "col": step})
                self._wait_for(
                    box1,
                    lambda m, rid=room_id, c=step: m.get("type") == "SYNC_MOVE"
                    and m.get("room_id") == rid
                    and m["move"]["col"] == c
                    and m["move"]["symbol"] == "O",
                )

        for target_room_id, _, s_box in spectators:
            sync_moves = [m for m in s_box if m.get("type") == "SYNC_MOVE"]
            self.assertEqual(len(sync_moves), 6)
            self.assertTrue(all(m.get("room_id") == target_room_id for m in sync_moves))

        avg_ms = sum(latencies_ms) / len(latencies_ms)
        max_ms = max(latencies_ms)
        print(f"\n[T22 Benchmark] Samples={len(latencies_ms)} | Avg={avg_ms:.2f}ms | Max={max_ms:.2f}ms")
        self.assertLess(max_ms, 500.0)


if __name__ == "__main__":
    unittest.main()
    