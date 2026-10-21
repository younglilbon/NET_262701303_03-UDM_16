import json

class ClientStateSync:
    """
    Module đồng bộ trạng thái phía Client (TV5 - Synchronization)
    Phụ trách: Nhận gói tin đồng bộ từ Server, duy trì trạng thái bàn cờ ở máy Client
    và kích hoạt hàm cập nhật giao diện cho TV6 (GUI).
    """
    def __init__(self, username, ui_callback=None):
        self.username = username
        self.room_id = None
        self.role = None          # 'X', 'O', hoặc 'SPECTATOR'
        self.status = "WAITING"
        self.board = []
        self.players = {"X": None, "O": None}
        self.spectators = []
        self.current_turn = None
        self.remaining_time = 0
        self.move_history = []
        self.winner = None

        # Hàm callback để báo cho GUI (TV6) vẽ lại màn hình: ui_callback(event_type, data)
        self.ui_callback = ui_callback or self._default_ui_logger

    def _default_ui_logger(self, event_type, data):
        """Hàm hiển thị giả lập khi chưa ghép nối với GUI của TV6"""
        print(f"  [CLIENT '{self.username}' UI UPDATE] -> Sự kiện: {event_type} | Dữ liệu: {data}")

    def _update_role(self):
        """Tự động xác định vai trò của Client hiện tại (Người chơi X/O hay Khán giả)"""
        if self.players.get("X") == self.username:
            self.role = "X"
        elif self.players.get("O") == self.username:
            self.role = "O"
        else:
            self.role = "SPECTATOR"

    def can_make_move(self):
        """
        Kiểm tra ở phía Client xem người dùng có quyền bấm vào bàn cờ không.
        (Khán giả hoặc người chưa tới lượt sẽ bị khóa thao tác click trên GUI).
        """
        if self.role == "SPECTATOR":
            return False, "Bạn đang là Khán giả (chỉ xem)."
        if self.status != "PLAYING":
            return False, f"Trận đấu đang ở trạng thái: {self.status}"
        if self.current_turn != self.role:
            return False, "Chưa đến lượt của bạn."
        return True, "Có thể đánh."

    def handle_server_message(self, message):
        """
        Hàm trung tâm xử lý các gói tin đồng bộ nhận từ Server (do TV1 truyền sang).
        `message` có thể là chuỗi JSON hoặc Dictionary.
        """
        if isinstance(message, str):
            message = json.loads(message)

        msg_type = message.get("type")

        if msg_type == "SYNC_FULL_STATE":
            # Đồng bộ toàn bộ bàn cờ (Khi bắt đầu trận, Khán giả vào giữa trận, hoặc Reconnect)
            self.room_id = message.get("room_id")
            self.status = message.get("status")
            self.players = message.get("players", {"X": None, "O": None})
            self.spectators = message.get("spectators", [])
            self.current_turn = message.get("current_turn")
            self.remaining_time = message.get("remaining_time", 0)
            self.board = message.get("board", [])
            self.move_history = message.get("move_history", [])
            self.winner = message.get("winner")
            self._update_role()

            self.ui_callback("FULL_SYNC", {
                "role": self.role,
                "status": self.status,
                "current_turn": self.current_turn,
                "remaining_time": self.remaining_time,
                "moves_count": len(self.move_history)
            })

        elif msg_type == "SYNC_MOVE":
            # Đồng bộ 1 nước đi mới theo thời gian thực
            move = message.get("move", {})
            row, col, symbol = move.get("row"), move.get("col"), move.get("symbol")
            if 0 <= row < len(self.board) and 0 <= col < len(self.board[0]):
                self.board[row][col] = symbol

            self.move_history.append(move)
            self.current_turn = message.get("next_turn")
            self.remaining_time = message.get("remaining_time", 0)

            self.ui_callback("MOVE_UPDATED", {
                "row": row,
                "col": col,
                "symbol": symbol,
                "next_turn": self.current_turn,
                "remaining_time": self.remaining_time
            })

        elif msg_type == "SPECTATOR_JOINED" or msg_type == "SPECTATOR_LEFT":
            self.ui_callback(msg_type, {
                "spectator": message.get("spectator"),
                "spectator_count": message.get("spectator_count")
            })

        elif msg_type == "PLAYER_DISCONNECTED":
            self.status = message.get("status", "PAUSED")
            self.ui_callback("MATCH_PAUSED", {
                "disconnected_user": message.get("username"),
                "timeout": message.get("reconnect_timeout")
            })

        elif msg_type == "PLAYER_RECONNECTED":
            self.status = message.get("status", "PLAYING")
            self.current_turn = message.get("current_turn")
            self.remaining_time = message.get("remaining_time", 0)
            self.ui_callback("MATCH_RESUMED", {
                "reconnected_user": message.get("username"),
                "current_turn": self.current_turn
            })

        elif msg_type == "MATCH_FINISHED":
            self.status = "FINISHED"
            self.winner = message.get("winner")
            self.ui_callback("MATCH_OVER", {
                "winner": self.winner,
                "reason": message.get("reason")
            })

        elif msg_type == "ERROR":
            self.ui_callback("SYNC_ERROR", {"message": message.get("message")})


# --- Khối code chạy thử nghiệm đồng bộ Client (Mock Test cho TV5) ---
if __name__ == "__main__":
    # Giả lập 1 máy Client của người chơi X và 1 máy Client của Khán giả
    client_x = ClientStateSync("Player_A")
    client_spec = ClientStateSync("Spectator_1")

    # 1. Server gửi gói tin SYNC_FULL_STATE
    sample_snapshot = {
        "type": "SYNC_FULL_STATE",
        "room_id": "ROOM_101",
        "status": "PLAYING",
        "players": {"X": "Player_A", "O": "Player_B"},
        "spectators": ["Spectator_1"],
        "current_turn": "X",
        "remaining_time": 30,
        "board": [["" for _ in range(5)] for _ in range(5)],
        "move_history": [],
        "winner": None
    }
    print("1. Đồng bộ toàn bộ trạng thái cho Player_A và Spectator_1:")
    client_x.handle_server_message(sample_snapshot)
    client_spec.handle_server_message(sample_snapshot)

    print("   -> Kiểm tra quyền đánh cờ của Player_A:", client_x.can_make_move())
    print("   -> Kiểm tra quyền đánh cờ của Spectator_1:", client_spec.can_make_move())

    # 2. Server gửi gói tin SYNC_MOVE khi Player_A đánh (2, 2)
    sample_move = {
        "type": "SYNC_MOVE",
        "room_id": "ROOM_101",
        "move": {"move_number": 1, "player": "Player_A", "symbol": "X", "row": 2, "col": 2},
        "next_turn": "O",
        "remaining_time": 30
    }
    print("\n2. Nhận cập nhật nước đi mới (2, 2):")
    client_x.handle_server_message(sample_move)
    client_spec.handle_server_message(sample_move)
    print("   -> Kiểm tra quyền đánh cờ của Player_A sau khi đã đánh xong:", client_x.can_make_move())