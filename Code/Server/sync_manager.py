import json
import os
import threading
import logging
from game_state import GameState

# Cấu hình ghi log sự kiện quan trọng trên Server theo yêu cầu chung
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

class SyncManager:
    """
    Module điều phối đồng bộ hóa trung tâm (TV5 - Synchronization)
    Phụ trách: Quản lý nhiều GameState đồng thời, Broadcast, Spectator Sync, Reconnect và History.
    """
    def __init__(self, send_callback=None, history_file="match_history.json"):
        # Quản lý nhiều phòng đấu cùng lúc: {room_id: GameState}
        self.rooms = {}
        # Ánh xạ username -> đối tượng kết nối (socket) do TV1 truyền vào
        self.user_connections = {}
        # Ánh xạ username -> room_id hiện tại để tìm phòng nhanh khi rớt mạng/reconnect
        self.user_room_map = {}
        
        # Khoá luồng (Thread Lock) tránh xung đột dữ liệu khi nhiều phòng đánh cùng lúc
        self.lock = threading.RLock()
        
        # Hàm callback của TV1 để gửi gói tin qua Socket: send_callback(conn, message_dict)
        self.send_callback = send_callback or self._default_mock_send
        self.history_file = os.path.join(os.path.dirname(__file__), history_file)

    def _default_mock_send(self, target_user, message_dict):
        """Hàm gửi giả lập dùng khi chạy test độc lập (chưa ghép code với TV1)"""
        print(f"  -> [SEND TO {target_user}]: {json.dumps(message_dict, ensure_ascii=False)}")

    def register_connection(self, username, conn):
        """Ghi nhận kết nối socket của người dùng"""
        with self.lock:
            self.user_connections[username] = conn

    def send_to_user(self, username, message_dict):
        """Gửi thông điệp tới 1 người dùng cụ thể"""
        conn = self.user_connections.get(username, username)
        try:
            self.send_callback(conn, message_dict)
        except Exception as e:
            logging.error(f"Lỗi khi gửi tin cho {username}: {e}")

    def broadcast_to_room(self, room_id, message_dict, exclude_user=None):
        """
        Phát sóng (Broadcast) thông điệp tới toàn bộ Người chơi và Khán giả trong phòng.
        """
        with self.lock:
            state = self.rooms.get(room_id)
            if not state:
                return

            recipients = set()
            if state.players["X"]:
                recipients.add(state.players["X"])
            if state.players["O"]:
                recipients.add(state.players["O"])
            recipients.update(state.spectators)

            if exclude_user:
                recipients.discard(exclude_user)

        for user in recipients:
            self.send_to_user(user, message_dict)

    def create_or_init_match(self, room_id, player_x, player_o, board_size=15):
        """Khởi tạo trạng thái trận đấu cho phòng và đồng bộ bàn cờ ban đầu"""
        with self.lock:
            state = GameState(room_id=room_id, board_size=board_size)
            state.set_players(player_x, player_o)
            self.rooms[room_id] = state
            self.user_room_map[player_x] = room_id
            self.user_room_map[player_o] = room_id

            logging.info(f"Bắt đầu trận đấu tại phòng {room_id}: {player_x} (X) vs {player_o} (O)")
            snapshot = state.get_full_snapshot()

        self.broadcast_to_room(room_id, snapshot)
        return state

    def sync_move(self, room_id, username, row, col):
        """Nhận nước đi, cập nhật GameState và Broadcast cho cả phòng (gồm cả khán giả)"""
        with self.lock:
            state = self.rooms.get(room_id)
            if not state:
                return False, "Không tìm thấy phòng đấu."

            ok, result = state.update_move(username, row, col)
            if not ok:
                # Gửi thông báo lỗi riêng cho người thao tác sai
                self.send_to_user(username, {
                    "type": "ERROR",
                    "room_id": room_id,
                    "message": result
                })
                return False, result

            # Gói tin cập nhật nước đi theo thời gian thực
            delta_packet = {
                "type": "SYNC_MOVE",
                "room_id": room_id,
                "move": result,
                "next_turn": state.current_turn,
                "remaining_time": state.get_remaining_turn_time()
            }
            logging.info(f"Phòng {room_id}: {username} đánh ({row}, {col})")

        self.broadcast_to_room(room_id, delta_packet)
        return True, result

    def sync_spectator_join(self, room_id, spectator_username):
        """
        Khán giả vào giữa trận: nhận ngay toàn bộ trạng thái hiện tại (Snapshot),
        sau đó nhận các cập nhật theo thời gian thực.
        """
        with self.lock:
            state = self.rooms.get(room_id)
            if not state:
                return False, "Không tìm thấy phòng đấu."

            if not state.add_spectator(spectator_username):
                return False, "Người chơi chính không thể làm khán giả cùng phòng."

            self.user_room_map[spectator_username] = room_id
            snapshot = state.get_full_snapshot()
            logging.info(f"Khán giả {spectator_username} tham gia xem phòng {room_id}")

        # 1. Gửi toàn bộ bàn cờ hiện tại riêng cho khán giả vừa vào
        self.send_to_user(spectator_username, snapshot)
        # 2. Thông báo cho phòng biết có khán giả mới
        self.broadcast_to_room(room_id, {
            "type": "SPECTATOR_JOINED",
            "room_id": room_id,
            "spectator": spectator_username,
            "spectator_count": len(state.spectators)
        }, exclude_user=spectator_username)
        return True, "Tham gia xem thành công."

    def sync_spectator_leave(self, room_id, spectator_username):
        """Khán giả rời phòng mà không ảnh hưởng đến trận đấu"""
        with self.lock:
            state = self.rooms.get(room_id)
            if not state:
                return
            state.remove_spectator(spectator_username)
            self.user_room_map.pop(spectator_username, None)
            logging.info(f"Khán giả {spectator_username} đã rời phòng {room_id}")

        self.broadcast_to_room(room_id, {
            "type": "SPECTATOR_LEFT",
            "room_id": room_id,
            "spectator": spectator_username,
            "spectator_count": len(state.spectators)
        })

    def handle_disconnect(self, username):
        """Xử lý khi Client ngắt kết nối đột ngột"""
        with self.lock:
            room_id = self.user_room_map.get(username)
            if not room_id or room_id not in self.rooms:
                return

            state = self.rooms[room_id]
            # Nếu là khán giả rớt mạng -> chỉ xóa khỏi danh sách xem, không dừng trận
            if state.is_spectator(username):
                self.sync_spectator_leave(room_id, username)
                return

            # Nếu là người chơi chính -> tạm dừng chờ Reconnect
            if state.mark_player_disconnected(username):
                logging.warning(f"Người chơi {username} mất kết nối tại phòng {room_id}. Chờ {state.reconnect_timeout}s.")
                self.broadcast_to_room(room_id, {
                    "type": "PLAYER_DISCONNECTED",
                    "room_id": room_id,
                    "username": username,
                    "status": state.status,
                    "reconnect_timeout": state.reconnect_timeout
                }, exclude_user=username)

    def handle_reconnect(self, username, new_conn=None):
        """Xử lý người chơi kết nối lại và đồng bộ lại toàn bộ ván đấu"""
        with self.lock:
            if new_conn is not None:
                self.user_connections[username] = new_conn

            room_id = self.user_room_map.get(username)
            if not room_id or room_id not in self.rooms:
                return False, "Không tìm thấy trận đấu đang diễn ra để kết nối lại."

            state = self.rooms[room_id]
            ok, msg = state.try_reconnect(username)
            if not ok:
                return False, msg

            snapshot = state.get_full_snapshot()
            logging.info(f"Người chơi {username} đã kết nối lại vào phòng {room_id}")

        # Gửi lại toàn bộ trạng thái bàn cờ cho người vừa kết nối lại
        self.send_to_user(username, snapshot)
        # Thông báo cho đối thủ và khán giả biết trận đấu tiếp tục
        self.broadcast_to_room(room_id, {
            "type": "PLAYER_RECONNECTED",
            "room_id": room_id,
            "username": username,
            "status": state.status,
            "current_turn": state.current_turn,
            "remaining_time": state.get_remaining_turn_time()
        }, exclude_user=username)
        return True, msg

    def finish_and_save_match(self, room_id, winner_symbol_or_draw, reason="NORMAL"):
        """Kết thúc trận đấu, thông báo kết quả và lưu lịch sử xuống file"""
        with self.lock:
            state = self.rooms.get(room_id)
            if not state:
                return
            state.finish_match(winner_symbol_or_draw)
            record = state.get_history_record()
            record["reason"] = reason
            self._append_history_to_file(record)
            logging.info(f"Kết thúc phòng {room_id} - Kết quả: {winner_symbol_or_draw} ({reason})")

        self.broadcast_to_room(room_id, {
            "type": "MATCH_FINISHED",
            "room_id": room_id,
            "winner": winner_symbol_or_draw,
            "reason": reason,
            "total_moves": len(state.move_history)
        })

    def _append_history_to_file(self, record):
        """Ghi lịch sử trận đấu vào file JSON trên Server"""
        history_data = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    history_data = json.load(f)
            except Exception:
                history_data = []

        history_data.append(record)
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)


# --- Khối code chạy thử nghiệm kịch bản đồng bộ (Mock Test cho TV5) ---
if __name__ == "__main__":
    sync = SyncManager()

    print("\n1. Khởi tạo trận đấu phòng ROOM_101:")
    sync.create_or_init_match("ROOM_101", "Player_A", "Player_B", board_size=5)

    print("\n2. Player_A đánh nước đầu tiên (2, 2):")
    sync.sync_move("ROOM_101", "Player_A", 2, 2)

    print("\n3. Khán giả 'Spectator_1' vào giữa trận (nhận toàn bộ trạng thái):")
    sync.sync_spectator_join("ROOM_101", "Spectator_1")

    print("\n4. Player_B mất kết nối đột ngột:")
    sync.handle_disconnect("Player_B")

    print("\n5. Player_B kết nối lại (Reconnect) thành công:")
    sync.handle_reconnect("Player_B")

    print("\n6. Kết thúc ván đấu và lưu lịch sử:")
    sync.finish_and_save_match("ROOM_101", "X", reason="FIVE_IN_A_ROW")