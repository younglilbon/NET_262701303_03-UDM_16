import time
import threading
from typing import Dict, Any, List, Optional, Tuple

# =====================================================================
# PHẦN 1: LỚP GAME ENGINE (LOGIC CHÍNH CỦA TV4)
# =====================================================================
class CaroGameEngine:
    def __init__(
        self,
        room_id: str,
        player_x: str,
        player_o: str,
        size: int = 15,
        turn_time_limit: int = 30,
        on_timeout_callback = None
    ):
        self.room_id = room_id
        self.player_x = player_x
        self.player_o = player_o
        self.size = size
        self.turn_time_limit = turn_time_limit
        self.on_timeout_callback = on_timeout_callback

        # Bàn cờ ma trận 15x15
        self.board: List[List[str]] = [['' for _ in range(size)] for _ in range(size)]
        
        # Trạng thái game
        self.current_turn: str = 'X'
        self.current_player: str = self.player_x
        self.is_game_over: bool = False
        self.winner: Optional[str] = None
        self.move_history: List[Tuple[int, int, str]] = []

        # Quản lý Timer
        self.timer_thread: Optional[threading.Thread] = None
        self.time_left: int = self.turn_time_limit
        self.timer_running: bool = False
        self.lock = threading.Lock()

    def start_game(self) -> None:
        self.reset_timer()

    def reset_timer(self) -> None:
        self.timer_running = False
        self.time_left = self.turn_time_limit
        self.timer_running = True

        self.timer_thread = threading.Thread(target=self._run_timer, daemon=True)
        self.timer_thread.start()

    def _run_timer(self) -> None:
        while self.time_left > 0 and self.timer_running and not self.is_game_over:
            time.sleep(1)
            with self.lock:
                if self.timer_running:
                    self.time_left -= 1

        with self.lock:
            if self.time_left <= 0 and self.timer_running and not self.is_game_over:
                self.is_game_over = True
                self.timer_running = False
                self.winner = 'O' if self.current_turn == 'X' else 'X'
                winner_player = self.player_o if self.winner == 'O' else self.player_x
                
                if self.on_timeout_callback:
                    self.on_timeout_callback(
                        self.room_id, 
                        timeout_player=self.current_player, 
                        winner_symbol=self.winner,
                        winner_player=winner_player
                    )

    def make_move(self, username: str, row: int, col: int) -> Dict[str, Any]:
        with self.lock:
            if self.is_game_over:
                return {"success": False, "message": "Trận đấu đã kết thúc."}

            if username != self.current_player:
                return {"success": False, "message": "Chưa đến lượt đi của bạn!"}

            if not (0 <= row < self.size and 0 <= col < self.size):
                return {"success": False, "message": "Tọa độ nước đi ngoài bàn cờ."}

            if self.board[row][col] != '':
                return {"success": False, "message": "Ô này đã được đánh trước đó."}

            symbol = self.current_turn
            self.board[row][col] = symbol
            self.move_history.append((row, col, symbol))

# 6. Kiểm tra điều kiện Thắng (5 quân liên tiếp)
            if self._check_win(row, col, symbol):
                self.is_game_over = True
                self.winner = symbol
                self.timer_running = False
                return {
                    "success": True,
                    "row": row,
                    "col": col,
                    "symbol": symbol,
                    "player": username,
                    "game_over": True,
                    "winner": self.winner,
                    "winner_player": username,
                    "reason": "WIN"
                }
