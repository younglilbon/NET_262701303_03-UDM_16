import tempfile
import time
import unittest

from Code.Client.Network.client_sync import ClientStateSync
from Code.Server.Synchronization.sync_manager import SyncManager

def run_integration_test():
    print("=== BẮT ĐẦU KIỂM THỬ ĐỒNG BỘ HÓA TOÀN DIỆN (TV5) ===")

    clients = {
        "Player_X": ClientStateSync("Player_X"),
        "Player_O": ClientStateSync("Player_O"),
        "Spectator_1": ClientStateSync("Spectator_1")
    }

    def mock_network_send(target_user, message_dict):
        if target_user in clients:
            clients[target_user].handle_server_message(message_dict)

    sync = SyncManager(send_callback=mock_network_send)

    print("\n[Test 1] Khởi tạo phòng ROOM_TEST và đánh 2 nước cờ...")
    sync.create_or_init_match("ROOM_TEST", "Player_X", "Player_O", board_size=5)
    sync.sync_move("ROOM_TEST", "Player_X", 1, 1)
    sync.sync_move("ROOM_TEST", "Player_O", 1, 2)
    assert clients["Player_X"].board == clients["Player_O"].board
    print(" -> PASS: Hai Client nhận cùng trạng thái bàn cờ nhất quán!")

    print("\n[Test 2] Khán giả Spectator_1 vào giữa trận...")
    sync.sync_spectator_join("ROOM_TEST", "Spectator_1")
    assert clients["Spectator_1"].board == clients["Player_X"].board
    assert clients["Spectator_1"].can_make_move()[0] is False
    print(" -> PASS: Khán giả nhận đủ bàn cờ hiện tại và bị khóa quyền đánh cờ")

    print("\n[Test 3] Player_O mất kết nối và kết nối lại...")
    sync.handle_disconnect("Player_O")
    clients["Player_O"] = ClientStateSync("Player_O") # Giả lập reset app
    sync.handle_reconnect("Player_O")
    assert clients["Player_O"].board == clients["Player_X"].board
    print(" -> PASS: Player_O kết nối lại và khôi phục bàn cờ thành công!")

    print("\n=== TẤT CẢ CÁC BÀI KIỂM THỬ ĐỒNG BỘ ĐỀU ĐẠT 100%! ===")

if __name__ == "__main__":
    run_integration_test()


class TestSynchronizationTimeout(unittest.TestCase):
    def test_turn_timeout_finishes_and_saves_match(self):
        messages = []
        with tempfile.TemporaryDirectory() as history_dir:
            sync = SyncManager(
                send_callback=lambda connection, message: messages.append(message),
                history_file=history_dir + "\\history.json",
            )
            state = sync.create_or_init_match(
                "ROOM_TIMEOUT", "Player_X", "Player_O", board_size=5,
                turn_timeout=0.05,
            )
            time.sleep(0.15)
            self.assertEqual(state.status, "FINISHED")
            self.assertEqual(state.winner, "O")
            self.assertTrue(
                any(message["type"] == "MATCH_FINISHED" for message in messages)
            )

class TestSynchronizationBroadcast(unittest.TestCase):
    def test_valid_move_broadcasts_same_state_to_both_clients(self):
        clients = {
            "Alice": ClientStateSync("Alice"),
            "Bob": ClientStateSync("Bob")
        }

        received_messages = {
            "Alice": [],
            "Bob": []
        }

        def mock_network_send(target_user, message):
            received_messages[target_user].append(message)
            clients[target_user].handle_server_message(message)

        sync = SyncManager(send_callback=mock_network_send)
        room_id = "ROOM_SY_02"

        sync.create_or_init_match(
            room_id,
            "Alice",
            "Bob",
            board_size=15
        )

        success, result = sync.sync_move(
            room_id,
            "Alice",
            7,
            7
        )

        self.assertTrue(success)

        for username in ("Alice", "Bob"):
            self.assertTrue(
                any(
                    msg["type"] == "SYNC_MOVE"
                    for msg in received_messages[username]
                )
            )

        self.assertEqual(clients["Alice"].board[7][7], "X")
        self.assertEqual(clients["Bob"].board[7][7], "X")

        self.assertEqual(
            clients["Alice"].board,
            clients["Bob"].board
        )

        self.assertEqual(clients["Alice"].current_turn, "O")
        self.assertEqual(clients["Bob"].current_turn, "O")

        self.assertEqual(
            clients["Alice"].move_history,
            clients["Bob"].move_history
        )
        self.assertEqual(len(clients["Alice"].move_history), 1)

        server_state = sync.rooms[room_id]

        self.assertEqual(
            server_state.board,
            clients["Alice"].board
        )
        self.assertEqual(
            server_state.board,
            clients["Bob"].board
        )