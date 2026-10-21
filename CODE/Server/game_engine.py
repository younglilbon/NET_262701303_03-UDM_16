"""
GIAI ĐOẠN 1 & 2: ĐỊNH NGHĨA KHUNG LỚP VÀ TRẠNG THÁI 
"""

from typing import Dict, Any, List, Optional, Tuple

class CaroGameEngine:
    def __init__(self, room_id: str, player_x: str, player_o: str, size: int = 15, turn_time_limit: int = 30):
        # 1. Cấu hình cơ bản
        self.room_id = room_id
        self.player_x = player_x  # Người chơi X (đi trước)
        self.player_o = player_o  # Người chơi O
        self.size = size          # Bàn cờ 15x15
        self.turn_time_limit = turn_time_limit  # 30s/lượt

        # 2. Khởi tạo Ma trận Bàn cờ (15x15 rỗng)
        self.board: List[List[str]] = [['' for _ in range(size)] for _ in range(size)]

        # 3. Trạng thái trận đấu
        self.current_turn: str = 'X'
        self.current_player: str = self.player_x
        self.is_game_over: bool = False
        self.winner: Optional[str] = None  # 'X', 'O', hoặc 'DRAW'
        self.move_history: List[Tuple[int, int, str]] = []  # Lịch sử nước đi
