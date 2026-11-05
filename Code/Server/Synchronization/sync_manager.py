import json
import os
import threading
import logging
import time
from game_state import GameState

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

class SyncManager:
    """
    Module điều phối đồng bộ hóa trung tâm (TV5) - Đã tích hợp API với TV3 (RoomManager)
    """
    def __init__(self, send_callback=None, match_finished_callback=None, history_file="match_history.json"):
        self.rooms = {}
        self.user_connections = {}
        self.user_room_map = {}
        
        self.lock = threading.RLock()
        self.file_lock = threading.Lock()
        
        self.send_callback = send_callback or self._default_mock_send
        self.match_finished_callback = match_finished_callback # Callback báo luồng chính
        self.history_file = os.path.join(os.path.dirname(__file__), history_file)

    def _default_mock_send(self, target_user, message_dict):
        pass

    def register_connection(self, username, conn):
        with self.lock:
            self.user_connections[username] = conn

    def send_to_user(self, username, message_dict):
        conn = self.user_connections.get(username, username)
        try:
            self.send_callback(conn, message_dict)
        except Exception as e:
            logging.error(f"Lỗi gửi tin cho {username}: {e}")

    def broadcast_to_room(self, room_id, message_dict, exclude_user=None):
        with self.lock:
            state = self.rooms.get(room_id)
            if not state: return
            recipients = set()
            if state.players["X"]: recipients.add(state.players["X"])
            if state.players["O"]: recipients.add(state.players["O"])
            recipients.update(state.spectators)
            if exclude_user: recipients.discard(exclude_user)

        for user in recipients:
            self.send_to_user(user, message_dict)

    def create_or_init_match(self, room_id, match_id, player_x, player_o, board_size=15, time_limit=30):
        with self.lock:
            state = GameState(room_id=room_id, board_size=board_size, turn_timeout=time_limit)
            state.set_players(player_x, player_o, match_id)
            self.rooms[room_id] = state
            self.user_room_map[player_x] = room_id
            self.user_room_map[player_o] = room_id
            snapshot = state.get_full_snapshot()
        self.broadcast_to_room(room_id, snapshot)
        return state

    def sync_move(self, room_id, username, row, col):
        with self.lock:
            state = self.rooms.get(room_id)
            if not state: return False, "Phòng không tồn tại."
            ok, result = state.update_move(username, row, col)
            if not ok:
                self.send_to_user(username, {"type": "ERROR", "code": "INVALID_STATE", "room_id": room_id, "message": result})
                return False, result

            delta_packet = {
                "type": "SYNC_MOVE", "room_id": room_id, "match_id": state.match_id,
                "move": result, "next_turn": state.current_turn, "remaining_time": state.get_remaining_turn_time()
            }
        self.broadcast_to_room(room_id, delta_packet)
        return True, result

    def sync_spectator_join(self, room_id, spectator_username):
        with self.lock:
            state = self.rooms.get(room_id)
            if not state or not state.add_spectator(spectator_username): return False, "Lỗi vào xem."
            self.user_room_map[spectator_username] = room_id
            snapshot = state.get_full_snapshot()
        self.send_to_user(spectator_username, snapshot)
        self.broadcast_to_room(room_id, {
            "type": "SPECTATOR_JOINED", "room_id": room_id, "match_id": state.match_id, 
            "spectator": spectator_username, "spectator_count": len(state.spectators)
        }, exclude_user=spectator_username)
        return True, "Thành công"

    def handle_disconnect(self, username):
        with self.lock:
            room_id = self.user_room_map.get(username)
            if not room_id or room_id not in self.rooms: return
            state = self.rooms[room_id]
            
            if state.is_spectator(username):
                self.detach_member(room_id, username)
                self.broadcast_to_room(room_id, {"type": "SPECTATOR_LEFT", "room_id": room_id, "match_id": state.match_id, "spectator": username, "spectator_count": len(state.spectators)})
                return

            if state.mark_player_disconnected(username):
                if len(state.disconnected_players) == 2:
                    logging.info(f"Cả 2 người chơi rời phòng {room_id}. Hủy ván đấu.")
                    self.finish_and_save_match(room_id, winner_symbol=None, reason="BOTH_DISCONNECTED", outcome="ABORTED")
                else:
                    self.broadcast_to_room(room_id, {
                        "type": "PLAYER_DISCONNECTED", "room_id": room_id, "match_id": state.match_id,
                        "username": username, "status": state.status, "reconnect_timeout": state.reconnect_timeout
                    }, exclude_user=username)

    def handle_reconnect(self, username, new_conn=None):
        with self.lock:
            if new_conn: self.user_connections[username] = new_conn
            room_id = self.user_room_map.get(username)
            if not room_id or room_id not in self.rooms: return False, "Phòng không tồn tại."
            state = self.rooms[room_id]
            ok, msg = state.try_reconnect(username)
            if not ok: return False, msg
            snapshot = state.get_full_snapshot()
        self.send_to_user(username, snapshot)
        self.broadcast_to_room(room_id, {
            "type": "PLAYER_RECONNECTED", "room_id": room_id, "match_id": state.match_id,
            "username": username, "status": state.status, "current_turn": state.current_turn, "remaining_time": state.get_remaining_turn_time()
        }, exclude_user=username)
        return True, msg

    # --- CÁC HÀM MỚI BỔ SUNG THEO API CỦA TV3 ---

    def detach_member(self, room_id, username):
        """TV3 API: Gỡ người khỏi danh sách ánh xạ và hạn reconnect, không xóa lịch sử."""
        with self.lock:
            if self.user_room_map.get(username) == room_id:
                del self.user_room_map[username]
            state = self.rooms.get(room_id)
            if state:
                state.remove_spectator(username)
                if username in state.disconnected_players:
                    del state.disconnected_players[username]

    def close_room(self, room_id):
        """TV3 API: Đóng phòng, giải phóng toàn bộ GameState và người xem."""
        with self.lock:
            state = self.rooms.pop(room_id, None)
            if state:
                # Dọn dẹp ánh xạ của tất cả thành viên trong phòng này
                users_to_remove = [u for u, r in self.user_room_map.items() if r == room_id]
                for u in users_to_remove:
                    del self.user_room_map[u]
                logging.info(f"Đã đóng GameState của phòng {room_id}")

    def finish_and_save_match(self, room_id, winner_symbol, reason="NORMAL", outcome="WIN", expected_match_id=None, notify_callback=True):
        """Được gọi khi kết thúc ván. Hỗ trợ expected_match_id và callback theo API luồng rời phòng."""
        callback_to_run = None
        match_id_to_report = None
        
        with self.lock:
            state = self.rooms.get(room_id)
            if not state or state.status == "FINISHED": return
            
            # API TV3: Bỏ qua nếu luồng ngoài gọi nhầm ván cũ
            if expected_match_id and state.match_id != expected_match_id:
                return 

            if reason == "BOARD_FULL": outcome = "DRAW"
            
            state.finish_match(winner_symbol, outcome)
            record = state.get_history_record(reason)
            self._safe_write_history(record)
            state.disconnected_players.clear()
            match_id_to_report = state.match_id

            self.broadcast_to_room(room_id, {
                "type": "MATCH_FINISHED", "room_id": room_id, "match_id": state.match_id,
                "winner": winner_symbol, "result": outcome, "reason": reason, "total_moves": len(state.move_history)
            })
            
            if notify_callback and self.match_finished_callback:
                callback_to_run = self.match_finished_callback

        # API TV3: Gọi callback TỪ BÊN NGOÀI KHÓA (nhả khóa SyncManager rồi mới gọi)
        if callback_to_run and match_id_to_report:
            callback_to_run(room_id, winner_symbol, reason, match_id_to_report)

    def _safe_write_history(self, record):
        with self.file_lock:
            history_data = []
            if os.path.exists(self.history_file):
                try:
                    with open(self.history_file, "r", encoding="utf-8") as f:
                        history_data = json.load(f)
                except Exception: pass
            history_data.append(record)
            temp_file = self.history_file + ".temp"
            try:
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(history_data, f, indent=2, ensure_ascii=False)
                os.replace(temp_file, self.history_file)
            except Exception as e:
                logging.error(f"Lỗi ghi lịch sử: {e}")