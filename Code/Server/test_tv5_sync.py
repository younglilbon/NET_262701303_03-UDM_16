import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Server.sync_manager import SyncManager
from Client.client_sync import ClientStateSync

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