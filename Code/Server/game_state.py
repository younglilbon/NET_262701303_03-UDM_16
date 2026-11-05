import time
import json
from datetime import datetime

class GameState:
    """
    Module quản lý trạng thái trận đấu (TV5) - Đã cập nhật chuẩn Tích hợp v1.0
    """
    def __init__(self, room_id, board_size=15, turn_timeout=30, reconnect_timeout=60):
        self.room_id = room_id
        self.match_id = None  # Thêm match_id theo yêu cầu
        self.board_size = board_size
        self.board = [["" for _ in range(board_size)] for _ in range(board_size)]
        
        self.players = {"X": None, "O": None}
        self.spectators = set()
        
        self.status = "WAITING"
        self.current_turn = "X"
        self.winner = None
        self.result_outcome = None # Lưu outcome: "WIN", "DRAW", "ABORTED"
        
        self.turn_timeout = turn_timeout
        self.turn_start_time = None
        self.paused_remaining_time = 0 # Lưu thời gian còn lại khi bị rớt mạng
        
        self.reconnect_timeout = reconnect_timeout
        self.disconnected_players = {} 
        
        self.move_history = []
        self.match_start_time = None
        self.match_end_time = None

    def set_players(self, player_x, player_o, match_id):
        """Khởi tạo thông tin ván cờ với match_id"""
        self.match_id = match_id
        self.players["X"] = player_x
        self.players["O"] = player_o
        self.status = "PLAYING"
        self.current_turn = "X"
        self.turn_start_time = time.time()
        self.match_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.disconnected_players.clear()
        self.result_outcome = None

    def is_spectator(self, username):
        return username in self.spectators

    def add_spectator(self, username):
        if username not in self.players.values():
            self.spectators.add(username)
            return True
        return False

    def remove_spectator(self, username):
        self.spectators.discard(username)

    def update_move(self, username, row, col):
        if self.status != "PLAYING":
            return False, "Trận đấu không ở trạng thái đang diễn ra."
        if self.is_spectator(username):
            return False, "Khán giả không được phép đánh cờ."

        role = "X" if self.players["X"] == username else ("O" if self.players["O"] == username else None)
        if role != self.current_turn:
            return False, "Chưa đến lượt của bạn."
        if not (0 <= row < self.board_size and 0 <= col < self.board_size) or self.board[row][col] != "":
            return False, "Ô cờ không hợp lệ."

        self.board[row][col] = role
        move_record = {
            "move_number": len(self.move_history) + 1,
            "player": username,
            "symbol": role,
            "row": row,
            "col": col,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        self.move_history.append(move_record)

        self.current_turn = "O" if self.current_turn == "X" else "X"
        self.turn_start_time = time.time()
        return True, move_record

    def get_remaining_turn_time(self):
        if self.status != "PLAYING" or not self.turn_start_time:
            return self.paused_remaining_time if self.status == "PAUSED" else self.turn_timeout
        elapsed = time.time() - self.turn_start_time
        return max(0, int(self.turn_timeout - elapsed))

    def mark_player_disconnected(self, username):
        if username in self.players.values() and self.status == "PLAYING":
            self.status = "PAUSED"
            self.paused_remaining_time = self.get_remaining_turn_time() # Giữ lại số giây còn lại
            self.disconnected_players[username] = time.time()
            return True
        return False

    def try_reconnect(self, username):
        if username not in self.disconnected_players:
            return False, "Không có quyền reconnect."

        disconnect_time = self.disconnected_players[username]
        if time.time() - disconnect_time > self.reconnect_timeout:
            return False, "Quá thời gian reconnect."

        del self.disconnected_players[username]
        if not self.disconnected_players and self.winner is None and self.result_outcome is None:
            self.status = "PLAYING"
            # Cấp lại đúng số giây còn lại lúc rớt mạng, không cấp lại từ đầu
            self.turn_start_time = time.time() - (self.turn_timeout - self.paused_remaining_time)
        return True, "Reconnect thành công."

    def finish_match(self, winner_symbol, outcome):
        """Kết thúc ván: outcome có thể là 'WIN', 'DRAW', hoặc 'ABORTED'"""
        self.status = "FINISHED"
        self.winner = winner_symbol
        self.result_outcome = outcome
        self.match_end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_full_snapshot(self):
        return {
            "type": "SYNC_FULL_STATE",
            "room_id": self.room_id,
            "match_id": self.match_id, # Bắt buộc có match_id
            "status": self.status,
            "players": self.players,
            "spectators": list(self.spectators),
            "current_turn": self.current_turn,
            "remaining_time": self.get_remaining_turn_time(),
            "board": self.board,
            "move_history": self.move_history,
            "winner": self.winner,
            "result": self.result_outcome
        }

    def get_history_record(self, reason):
        return {
            "room_id": self.room_id,
            "match_id": self.match_id,
            "start_time": self.match_start_time,
            "end_time": self.match_end_time,
            "players": self.players,
            "winner": self.winner,
            "result": self.result_outcome,
            "reason": reason,
            "total_moves": len(self.move_history),
            "moves": self.move_history
        }