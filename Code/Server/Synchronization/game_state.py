import time
import json
from datetime import datetime
from ..Game_Engine.engine import GameEngine
from ..Game_Engine.models import EndReason

class GameState:
    """
    Module quản lý trạng thái trận đấu (TV5 - Synchronization)
    Phụ trách: GameState, Spectator state, Reconnect state, và Move History.
    """
    def __init__(self, room_id, board_size=15, turn_timeout=30, reconnect_timeout=60):
        self.room_id = room_id
        self.board_size = board_size
        # Ma trận bàn cờ: 0 là ô trống, 'X' và 'O' là quân cờ
        self.board = [["" for _ in range(board_size)] for _ in range(board_size)]
        
        # Thông tin người chơi và khán giả
        self.players = {"X": None, "O": None}  # Lưu username hoặc ID người chơi
        self.spectators = set()                # Danh sách khán giả (chỉ xem)
        
        # Trạng thái ván đấu
        self.status = "WAITING"  # WAITING, PLAYING, PAUSED (chờ kết nối lại), FINISHED
        self.current_turn = "X"
        self.winner = None       # 'X', 'O', hoặc 'DRAW'
        
        # Quản lý thời gian suy nghĩ mỗi lượt
        self.turn_timeout = turn_timeout
        self.turn_start_time = None
        
        # Quản lý Reconnect (khi người chơi rớt mạng)
        self.reconnect_timeout = reconnect_timeout
        self.disconnected_players = {}  # {username: thời_điểm_mất_kết_nối}
        
        # Lịch sử nước đi và thời gian trận đấu
        self.move_history = []
        self.match_start_time = None
        self.match_end_time = None
        self.result = None

    def set_players(self, player_x, player_o):
        """Thiết lập 2 người chơi và bắt đầu trận đấu"""
        self.players["X"] = player_x
        self.players["O"] = player_o
        self.status = "PLAYING"
        self.current_turn = "X"
        self.turn_start_time = time.time()
        self.match_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def is_spectator(self, username):
        """Kiểm tra xem user có phải là khán giả không (chặn khán giả đánh cờ)"""
        return username in self.spectators

    def add_spectator(self, username):
        """Thêm khán giả vào phòng"""
        if username not in self.players.values():
            self.spectators.add(username)
            return True
        return False

    def remove_spectator(self, username):
        """Khán giả rời phòng mà không ảnh hưởng trận đấu"""
        self.spectators.discard(username)

    def update_move(self, username, row, col):
        """
        Cập nhật nước đi vào trạng thái trận đấu và lưu lịch sử.
        (Phối hợp với hàm kiểm tra hợp lệ của TV4)
        """
        if self.status != "PLAYING":
            return False, "Trận đấu không ở trạng thái đang diễn ra."
            
        if self.is_spectator(username):
            return False, "Khán giả chỉ được xem, không được phép đánh cờ."

        role = "X" if self.players["X"] == username else ("O" if self.players["O"] == username else None)
        if role is None:
            return False, "Bạn không phải người chơi trong trận."
        if role != self.current_turn:
            return False, "Chưa đến lượt của bạn."

        if (
            not isinstance(row, int)
            or isinstance(row, bool)
            or not isinstance(col, int)
            or isinstance(col, bool)
            or not (0 <= row < self.board_size and 0 <= col < self.board_size)
            or self.board[row][col] != ""
        ):
            return False, "Ô cờ không hợp lệ hoặc đã có quân."

        # Cập nhật bàn cờ và lịch sử
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

        winning_line = GameEngine.winning_line(self.board, row, col, role)
        if winning_line:
            self.status = "FINISHED"
            self.winner = role
            self.result = GameEngine.result(
                role, self.players, EndReason.FIVE_IN_ROW,
                len(self.move_history), winning_line,
            )
            self.match_end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return True, move_record

        if GameEngine.is_board_full(self.board):
            self.status = "FINISHED"
            self.winner = "DRAW"
            self.result = GameEngine.result(
                None, self.players, EndReason.BOARD_FULL,
                len(self.move_history),
            )
            self.match_end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return True, move_record

        # Đổi lượt và đặt lại đồng hồ đếm ngược
        self.current_turn = "O" if self.current_turn == "X" else "X"
        self.turn_start_time = time.time()
        return True, move_record

    def get_remaining_turn_time(self):
        """Tính thời gian suy nghĩ còn lại của lượt hiện tại"""
        if self.status != "PLAYING" or not self.turn_start_time:
            return self.turn_timeout
        elapsed = time.time() - self.turn_start_time
        return max(0, int(self.turn_timeout - elapsed))

    def mark_player_disconnected(self, username):
        """Đánh dấu người chơi mất kết nối để chờ kết nối lại"""
        if username in self.players.values() and self.status in ("PLAYING", "PAUSED"):
            self.status = "PAUSED"
            self.disconnected_players[username] = time.time()
            return True
        return False

    def try_reconnect(self, username):
        """Xử lý người chơi kết nối lại trong thời gian cho phép"""
        if username not in self.disconnected_players:
            return False, "Người chơi không nằm trong danh sách chờ kết nối lại."

        disconnect_time = self.disconnected_players[username]
        if time.time() - disconnect_time > self.reconnect_timeout:
            return False, "Đã quá thời gian cho phép kết nối lại."

        del self.disconnected_players[username]
        if not self.disconnected_players and self.winner is None:
            self.status = "PLAYING"
            self.turn_start_time = time.time()  # Khôi phục bộ đếm lượt
        return True, "Kết nối lại thành công."

    def finish_match(self, winner_symbol_or_draw, reason=EndReason.TIMEOUT):
        """Kết thúc trận đấu và ghi nhận kết quả ('X', 'O', hoặc 'DRAW')"""
        self.status = "FINISHED"
        self.winner = winner_symbol_or_draw
        self.match_end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self.result is None:
            winner_symbol = (
                winner_symbol_or_draw
                if winner_symbol_or_draw in ("X", "O")
                else None
            )
            if not isinstance(reason, EndReason):
                try:
                    reason = EndReason(reason)
                except ValueError:
                    reason = EndReason.TIMEOUT
            self.result = GameEngine.result(
                winner_symbol, self.players, reason, len(self.move_history)
            )

    def get_full_snapshot(self):
        """
        Lấy toàn bộ trạng thái bàn cờ hiện tại (Snapshot).
        Dùng để đồng bộ cho Khán giả vào giữa trận hoặc Người chơi vừa Reconnect.
        """
        return {
            "type": "SYNC_FULL_STATE",
            "room_id": self.room_id,
            "status": self.status,
            "players": self.players,
            "spectators": list(self.spectators),
            "current_turn": self.current_turn,
            "remaining_time": self.get_remaining_turn_time(),
            "board": self.board,
            "move_history": self.move_history,
            "winner": self.winner
        }

    def get_history_record(self):
        """Xuất dữ liệu lịch sử trận đấu để lưu xuống Server"""
        return {
            "room_id": self.room_id,
            "start_time": self.match_start_time,
            "end_time": self.match_end_time,
            "players": self.players,
            "winner": self.winner,
            "result": self.result.to_dict() if self.result else None,
            "total_moves": len(self.move_history),
            "moves": self.move_history
        }


# --- Khối code chạy thử nghiệm độc lập (Mock Test cho TV5) ---
if __name__ == "__main__":
    state = GameState(room_id="ROOM_01", board_size=5)
    state.set_players("Alice", "Bob")
    state.add_spectator("Charlie_Voter")

    # Giả lập 2 nước đi
    state.update_move("Alice", 2, 2)
    state.update_move("Bob", 2, 3)

    # Giả lập khán giả cố tình đánh cờ
    ok, msg = state.update_move("Charlie_Voter", 0, 0)
    print("Test chặn khán giả đánh cờ:", ok, "-", msg)

    # In thử gói tin Snapshot gửi cho khán giả vào giữa trận
    print("\n--- GÓI TIN ĐỒNG BỘ TOÀN BỘ TRẠNG THÁI (SNAPSHOT) ---")
    print(json.dumps(state.get_full_snapshot(), indent=2, ensure_ascii=False))