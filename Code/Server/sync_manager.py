import json
import os
import threading
import logging
import time
from game_state import GameState

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

class SyncManager:
    """
    Module điều phối đồng bộ hóa trung tâm (TV5) - Đã cập nhật chuẩn Tích hợp v1.0
    """
    def __init__(self, send_callback=None, history_file="match_history.json"):
        self.rooms = {}
        self.user_connections = {}
        self.user_room_map = {}
        
        self.lock = threading.RLock()
        self.file_lock = threading.Lock() # Khóa dành riêng để ghi file an toàn
        
        self.send_callback = send_callback or self._default_mock_send
        self.history_file = os.path.join(os.path.dirname(__file__), history_file)

    def _default_mock_send(self, target_user, message_dict):
        print(f"  -> [SEND TO {target_user}]: {json.dumps(message_dict, ensure_ascii=False)}")

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
            state.set_players(player_x, player_o, match_id) # Khởi tạo với match_id
            self.rooms[room_id] = state
            self.user_room_map[player_x] = room_id
            self.user_room_map[player_o] = room_id

            logging.info(f"Bắt đầu trận {match_id} (Phòng {room_id}): {player_x}(X) vs {player_o}(O)")
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
                "type": "SYNC_MOVE",
                "room_id": room_id,
                "match_id": state.match_id, # Đính kèm match_id
                "move": result,
                "next_turn": state.current_turn,
                "remaining_time": state.get_remaining_turn_time()
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
            "type": "SPECTATOR_JOINED", 
            "room_id": room_id, 
            "match_id": state.match_id, 
            "spectator": spectator_username, 
            "spectator_count": len(state.spectators)
        }, exclude_user=spectator_username)
        return True, "Thành công"

    def handle_disconnect(self, username):
        with self.lock:
            room_id = self.user_room_map.get(username)
            if not room_id or room_id not in self.rooms: return
            state = self.rooms[room_id]
            
            if state.is_spectator(username):
                state.remove_spectator(username)
                self.user_room_map.pop(username, None)
                self.broadcast_to_room(room_id, {"type": "SPECTATOR_LEFT", "room_id": room_id, "match_id": state.match_id, "spectator": username, "spectator_count": len(state.spectators)})
                return

            if state.mark_player_disconnected(username):
                # Xử lý Cả hai cùng offline
                if len(state.disconnected_players) == 2:
                    logging.info(f"Cả 2 người chơi rời phòng {room_id}. Hủy ván đấu.")
                    self.finish_and_save_match(room_id, winner_symbol=None, reason="BOTH_DISCONNECTED", outcome="ABORTED")
                else:
                    self.broadcast_to_room(room_id, {
                        "type": "PLAYER_DISCONNECTED", 
                        "room_id": room_id, 
                        "match_id": state.match_id,
                        "username": username, 
                        "status": state.status, 
                        "reconnect_timeout": state.reconnect_timeout
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
            "type": "PLAYER_RECONNECTED",
            "room_id": room_id,
            "match_id": state.match_id,
            "username": username,
            "status": state.status,
            "current_turn": state.current_turn,
            "remaining_time": state.get_remaining_turn_time()
        }, exclude_user=username)
        return True, msg

    def finish_and_save_match(self, room_id, winner_symbol, reason="NORMAL", outcome="WIN"):
        with self.lock:
            state = self.rooms.get(room_id)
            if not state or state.status == "FINISHED": return
            
            # Gán hòa nếu outcome truyền vào là DRAW
            if reason == "BOARD_FULL": outcome = "DRAW"
            
            state.finish_match(winner_symbol, outcome)
            record = state.get_history_record(reason)
            self._safe_write_history(record) # Dùng hàm ghi an toàn
            
            # Dọn dẹp chỗ giữ reconnect
            state.disconnected_players.clear()

        self.broadcast_to_room(room_id, {
            "type": "MATCH_FINISHED",
            "room_id": room_id,
            "match_id": state.match_id,
            "winner": winner_symbol,
            "result": outcome,
            "reason": reason,
            "total_moves": len(state.move_history)
        })

    def _safe_write_history(self, record):
        """Ghi file an toàn dùng file tạm (.temp) rồi os.replace"""
        with self.file_lock:
            history_data = []
            if os.path.exists(self.history_file):
                try:
                    with open(self.history_file, "r", encoding="utf-8") as f:
                        history_data = json.load(f)
                except Exception:
                    pass
            history_data.append(record)
            
            temp_file = self.history_file + ".temp"
            try:
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(history_data, f, indent=2, ensure_ascii=False)
                # Ghi đè file chính an toàn (Atomic write)
                os.replace(temp_file, self.history_file)
            except Exception as e:
                logging.error(f"Lỗi ghi lịch sử: {e}")