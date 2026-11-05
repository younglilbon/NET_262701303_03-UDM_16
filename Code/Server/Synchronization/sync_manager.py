import json
import os
import threading
import logging
import time
import tempfile
from copy import deepcopy
from ..Application.coordination import Coordinator, coordinated
from .game_state import GameState

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
    def __init__(
        self, send_callback=None, history_file="match_history.json",
        on_match_finished=None,
        coordinator=None,
    ):
        # Quản lý nhiều phòng đấu cùng lúc: {room_id: GameState}
        self.rooms = {}
        self.coordinator = coordinator or Coordinator()
        self._room_members = {}
        self._finished_matches = set()
        self._pending_history = {}
        self._history_lock = threading.Lock()
        # Ánh xạ username -> đối tượng kết nối (socket) do TV1 truyền vào
        self.user_connections = {}
        # Ánh xạ username -> room_id hiện tại để tìm phòng nhanh khi rớt mạng/reconnect
        self.user_room_map = {}
        
        # Khoá luồng (Thread Lock) tránh xung đột dữ liệu khi nhiều phòng đánh cùng lúc
        self.lock = threading.RLock()
        self._turn_timers = {}
        self._reconnect_timers = {}
        self._saved_matches = set()
        
        # Hàm callback của TV1 để gửi gói tin qua Socket: send_callback(conn, message_dict)
        self.send_callback = send_callback or self._default_mock_send
        self.on_match_finished = on_match_finished
        history_directory = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "History")
        )
        os.makedirs(history_directory, exist_ok=True)
        self.history_file = os.path.join(history_directory, history_file)

    def _default_mock_send(self, target_user, message_dict):
        """Hàm gửi giả lập dùng khi chạy test độc lập (chưa ghép code với TV1)"""
        print(f"  -> [SEND TO {target_user}]: {json.dumps(message_dict, ensure_ascii=False)}")

    def register_connection(self, username, conn):
        """Ghi nhận kết nối socket của người dùng"""
        with self.lock:
            self.user_connections[username] = conn

    def send_to_user(self, username, message_dict):
        """Gửi thông điệp tới 1 người dùng cụ thể"""
        with self.lock:
            conn = self.user_connections.get(username, username)
            packet = deepcopy(message_dict)
        def send():
            try:
                self.send_callback(conn, packet)
            except Exception as e:
                logging.error(f"Lỗi khi gửi tin cho {username}: {e}")
        self.coordinator.defer(send)

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
            recipients = set(self._room_members.get(room_id, recipients))

            if exclude_user:
                recipients.discard(exclude_user)

        for user in recipients:
            self.send_to_user(user, message_dict)

    @coordinated
    def create_or_init_match(
        self, room_id, player_x, player_o, board_size=15,
        turn_timeout=30, spectators=(),
    ):
        """Khởi tạo trạng thái trận đấu cho phòng và đồng bộ bàn cờ ban đầu"""
        with self.lock:
            state = GameState(
                room_id=room_id,
                board_size=board_size,
                turn_timeout=turn_timeout,
            )
            state.set_players(player_x, player_o)
            for spectator in spectators:
                state.add_spectator(spectator)
            previous_state = self.rooms.get(room_id)
            if previous_state is not None:
                for username in previous_state.players.values():
                    if username:
                        if self.user_room_map.get(username) == room_id:
                            self.user_room_map.pop(username, None)
                for username in previous_state.spectators:
                    if self.user_room_map.get(username) == room_id:
                        self.user_room_map.pop(username, None)
            self.rooms[room_id] = state
            self._room_members[room_id] = {player_x, player_o, *spectators}
            self.user_room_map[player_x] = room_id
            self.user_room_map[player_o] = room_id
            for spectator in spectators:
                self.user_room_map[spectator] = room_id

            logging.info(f"Bắt đầu trận đấu tại phòng {room_id}: {player_x} (X) vs {player_o} (O)")
            snapshot = state.get_full_snapshot()

        self._schedule_turn_timeout(room_id, state.current_turn)
        self.broadcast_to_room(room_id, snapshot)
        return state

    @coordinated
    def sync_move(self, room_id, username, row, col):
        """Nhận nước đi, cập nhật GameState và Broadcast cho cả phòng (gồm cả khán giả)"""
        with self.lock:
            state = self.rooms.get(room_id)
            if not state:
                return False, "Không tìm thấy phòng đấu."

            if (
                state.status == "PLAYING"
                and state.turn_start_time + state.turn_timeout <= time.time()
            ):
                winner = "O" if state.current_turn == "X" else "X"
                state.finish_match(winner)
                timeout = True
            else:
                timeout = False

            if timeout:
                result = "Hết thời gian lượt đi."
                ok = False
            else:
                ok, result = state.update_move(username, row, col)
            if not timeout and not ok:
                # Gửi thông báo lỗi riêng cho người thao tác sai
                self.send_to_user(username, {
                    "type": "ERROR",
                    "room_id": room_id,
                    "message": result
                })
                return False, result

            if state.status == "FINISHED":
                finished = True
            else:
                finished = False
                next_turn = state.current_turn
            # Gói tin cập nhật nước đi theo thời gian thực
            delta_packet = {
                "type": "SYNC_MOVE",
                "room_id": room_id,
                "move": result,
                "next_turn": state.current_turn,
                "remaining_time": state.get_remaining_turn_time()
            }
            logging.info(f"Phòng {room_id}: {username} đánh ({row}, {col})")

        if timeout:
            self.finish_and_save_match(room_id, winner, reason="TIMEOUT")
            return False, result
        if finished:
            self._cancel_turn_timeout(room_id)
        else:
            self._schedule_turn_timeout(room_id, next_turn)
        self.broadcast_to_room(room_id, delta_packet)
        if finished:
            reason = "FIVE_IN_ROW" if state.winner != "DRAW" else "BOARD_FULL"
            self.finish_and_save_match(room_id, state.winner, reason)
        return True, result

    @coordinated
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
            self._room_members.setdefault(room_id, set(state.players.values())).add(spectator_username)
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

    @coordinated
    def sync_spectator_leave(self, room_id, spectator_username):
        """Khán giả rời phòng mà không ảnh hưởng đến trận đấu"""
        with self.lock:
            state = self.rooms.get(room_id)
            if not state:
                return
            self.detach_member(room_id, spectator_username)
            logging.info(f"Khán giả {spectator_username} đã rời phòng {room_id}")

        self.broadcast_to_room(room_id, {
            "type": "SPECTATOR_LEFT",
            "room_id": room_id,
            "spectator": spectator_username,
            "spectator_count": len(state.spectators)
        })

    @coordinated
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
                self._cancel_turn_timeout(room_id)
                logging.warning(f"Người chơi {username} mất kết nối tại phòng {room_id}. Chờ {state.reconnect_timeout}s.")
                self.broadcast_to_room(room_id, {
                    "type": "PLAYER_DISCONNECTED",
                    "room_id": room_id,
                    "username": username,
                    "status": state.status,
                    "reconnect_timeout": state.reconnect_timeout
                }, exclude_user=username)
                timer = threading.Timer(
                    state.reconnect_timeout,
                    self._expire_reconnect,
                    args=(room_id, username, state.match_id),
                )
                timer.daemon = True
                self._reconnect_timers[(room_id, username)] = timer
                timer.start()

    @coordinated
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
            reconnect_timer = self._reconnect_timers.pop((room_id, username), None)
            if reconnect_timer is not None:
                reconnect_timer.cancel()

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
        if state.status == "PLAYING":
            self._schedule_turn_timeout(room_id, state.current_turn)
        return True, msg

    @coordinated
    def finish_and_save_match(
        self, room_id, winner_symbol_or_draw, reason="NORMAL", *,
        notify_callback=True, expected_match_id=None,
    ):
        """Kết thúc trận đấu, thông báo kết quả và lưu lịch sử xuống file"""
        with self.lock:
            state = self.rooms.get(room_id)
            if not state:
                return
            if expected_match_id is not None and state.match_id != expected_match_id:
                return
            if state.match_id in self._finished_matches:
                return
            if state.status != "FINISHED":
                result_reason = {
                    "TIMEOUT": "TIMEOUT",
                    "DISCONNECT": "DISCONNECT",
                    "RESIGN": "RESIGN",
                    "BOARD_FULL": "BOARD_FULL",
                    "FIVE_IN_ROW": "FIVE_IN_ROW",
                }.get(reason, "TIMEOUT")
                state.finish_match(winner_symbol_or_draw, reason=result_reason)
            record = state.get_history_record()
            reason = state.result.reason.value
            winner_symbol_or_draw = state.winner
            record["reason"] = reason
            self._finished_matches.add(state.match_id)
            self._pending_history[state.match_id] = record
            self._cancel_turn_timeout(room_id)
            for key, timer in list(self._reconnect_timers.items()):
                if key[0] == room_id:
                    timer.cancel()
                    self._reconnect_timers.pop(key, None)
            logging.info(f"Kết thúc phòng {room_id} - Kết quả: {winner_symbol_or_draw} ({reason})")

        self._broadcast_finished(room_id, state, winner_symbol_or_draw, reason, notify_callback)
        self.coordinator.defer(lambda: self._save_pending_history(record))

    def _broadcast_finished(self, room_id, state, winner, reason, notify_callback=True):
        self.broadcast_to_room(room_id, {
            "type": "MATCH_FINISHED",
            "room_id": room_id,
            "match_id": state.match_id,
            "winner": winner,
            "reason": reason,
            "total_moves": len(state.move_history),
            "result": state.result.to_dict(),
        })
        if notify_callback and self.on_match_finished is not None:
            self.on_match_finished(room_id, winner, reason, state.match_id)

    def _save_pending_history(self, record):
        # Disk I/O runs after releasing the coordinator and SyncManager locks.
        with self._history_lock:
            with self.lock:
                if record["match_id"] in self._saved_matches:
                    return
            if self._append_history_to_file(record):
                with self.lock:
                    self._saved_matches.add(record["match_id"])
                    self._pending_history.pop(record["match_id"], None)

    def match_snapshot(self, room_id):
        with self.lock:
            state = self.rooms.get(room_id)
            return state.get_full_snapshot() if state is not None else None

    @coordinated
    def detach_member(self, room_id, username):
        """Remove active membership, preserving the players recorded for this match."""
        with self.lock:
            self._room_members.get(room_id, set()).discard(username)
            if self.user_room_map.get(username) == room_id:
                self.user_room_map.pop(username, None)
            timer = self._reconnect_timers.pop((room_id, username), None)
            if timer is not None:
                timer.cancel()
            state = self.rooms.get(room_id)
            if state is not None:
                state.remove_spectator(username)
                state.disconnected_players.pop(username, None)

    @coordinated
    def close_room(self, room_id):
        """Cancel activity; pending immutable history remains available for saving."""
        with self.lock:
            self._cancel_turn_timeout(room_id)
            for key, timer in list(self._reconnect_timers.items()):
                if key[0] == room_id:
                    timer.cancel()
                    self._reconnect_timers.pop(key, None)
            for username, mapped_room in list(self.user_room_map.items()):
                if mapped_room == room_id:
                    self.user_room_map.pop(username, None)
            self._room_members.pop(room_id, None)
            self.rooms.pop(room_id, None)

    def _schedule_turn_timeout(self, room_id, turn):
        self._cancel_turn_timeout(room_id)
        state = self.rooms.get(room_id)
        if state is None or state.status != "PLAYING":
            return
        timer = threading.Timer(
            max(0, state.turn_start_time + state.turn_timeout - time.time()),
            self._expire_turn,
            args=(room_id, turn, state.match_id),
        )
        timer.daemon = True
        self._turn_timers[room_id] = timer
        timer.start()

    def _cancel_turn_timeout(self, room_id):
        timer = self._turn_timers.pop(room_id, None)
        if timer is not None:
            timer.cancel()

    @coordinated
    def _expire_turn(self, room_id, expected_turn, expected_match_id=None):
        with self.lock:
            state = self.rooms.get(room_id)
            if (
                state is None
                or state.status != "PLAYING"
                or state.current_turn != expected_turn
                or (expected_match_id is not None and state.match_id != expected_match_id)
            ):
                return
            remaining = state.turn_start_time + state.turn_timeout - time.time()
            if remaining > 0:
                timer = threading.Timer(
                    remaining, self._expire_turn, args=(room_id, expected_turn, state.match_id)
                )
                timer.daemon = True
                self._turn_timers[room_id] = timer
                timer.start()
                return
            winner = "O" if expected_turn == "X" else "X"
        self.finish_and_save_match(room_id, winner, reason="TIMEOUT", expected_match_id=state.match_id)

    @coordinated
    def _expire_reconnect(self, room_id, username, expected_match_id=None):
        with self.lock:
            state = self.rooms.get(room_id)
            if (state is None or username not in state.disconnected_players
                    or (expected_match_id is not None and state.match_id != expected_match_id)):
                return
            winner = "O" if state.players.get("X") == username else "X"
        self.finish_and_save_match(room_id, winner, reason="DISCONNECT", expected_match_id=state.match_id)

    def unregister_connection(self, username, connection):
        with self.lock:
            if self.user_connections.get(username) is connection:
                self.user_connections.pop(username, None)

    def _append_history_to_file(self, record):
        """Ghi lịch sử trận đấu vào file JSON trên Server"""
        history_data = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    history_data = json.load(f)
            except (OSError, json.JSONDecodeError) as error:
                logging.error("Không thể đọc lịch sử trận đấu %s: %s", self.history_file, error)
                return False
            if not isinstance(history_data, list):
                logging.error("Tệp lịch sử trận đấu không chứa một JSON array: %s", self.history_file)
                return False

        if any(item.get("match_id") == record["match_id"] for item in history_data):
            return True
        history_data.append(record)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", delete=False,
                dir=os.path.dirname(os.path.abspath(self.history_file)),
            ) as f:
                temporary_path = f.name
                json.dump(history_data, f, indent=2, ensure_ascii=False)
            os.replace(temporary_path, self.history_file)
        except OSError as error:
            logging.error("Không thể ghi lịch sử trận đấu %s: %s", self.history_file, error)
            return False
        finally:
            if temporary_path is not None and os.path.exists(temporary_path):
                os.unlink(temporary_path)
        return True


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
