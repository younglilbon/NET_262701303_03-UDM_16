"""engine.py - GameEngine: luật chơi, lượt đi, kết quả, đồng hồ (TV4).

Mỗi phòng đấu (TV3) tạo ĐÚNG MỘT GameEngine riêng -> nhiều trận chạy đồng thời
không ảnh hưởng nhau. Engine KHÔNG biết gì về socket; nó chỉ nhận lời gọi hàm và
trả về đối tượng kết quả để TV3/TV5 phát (broadcast) đi.
"""
import threading
import time
from typing import Callable, List, Optional

from .board import Board
from .models import (EndReason, GameResult, GameStatus, Move, MoveCode,
                     MoveOutcome, Symbol)
from .timer import TurnTimer

ROLE_PLAYER_X = "PLAYER_X"
ROLE_PLAYER_O = "PLAYER_O"
ROLE_SPECTATOR = "SPECTATOR"


class GameEngine:
    def __init__(self, player_x: str, player_o: str, size: int = 15,
                 win_length: int = 5, turn_limit: float = 30.0,
                 clock: Callable[[], float] = time.monotonic):
        if player_x == player_o:
            raise ValueError("Hai người chơi phải khác nhau")
        self.players = {Symbol.X: player_x, Symbol.O: player_o}
        self.board = Board(size, win_length)
        self.timer = TurnTimer(turn_limit, clock)
        self.status = GameStatus.WAITING
        self.turn: Symbol = Symbol.X          # X luôn đi trước
        self.history: List[Move] = []
        self.result: Optional[GameResult] = None
        self._lock = threading.RLock()        # nhiều thread client cùng gọi vào

    # ------------------------------------------------------------------ vai trò
    def get_role(self, user_id: str) -> str:
        """Phân biệt người chơi / khán giả (yêu cầu của đề)."""
        if user_id == self.players[Symbol.X]:
            return ROLE_PLAYER_X
        if user_id == self.players[Symbol.O]:
            return ROLE_PLAYER_O
        return ROLE_SPECTATOR

    def symbol_of(self, user_id: str) -> Optional[Symbol]:
        for s, uid in self.players.items():
            if uid == user_id:
                return s
        return None

    # ------------------------------------------------------------------ vòng đời
    def start(self) -> None:
        with self._lock:
            if self.status is not GameStatus.WAITING:
                raise RuntimeError("Trận đã bắt đầu hoặc đã kết thúc")
            self.status = GameStatus.PLAYING
            self.turn = Symbol.X
            self.timer.start()

    @property
    def is_finished(self) -> bool:
        return self.status is GameStatus.FINISHED

    # ------------------------------------------------------------------ nước đi
    def validate_move(self, user_id: str, row, col) -> MoveOutcome:
        """Chỉ kiểm tra, KHÔNG thay đổi trạng thái."""
        with self._lock:
            if self.status is GameStatus.WAITING:
                return self._fail(MoveCode.GAME_NOT_STARTED, "Trận đấu chưa bắt đầu")
            if self.status is GameStatus.FINISHED:
                return self._fail(MoveCode.GAME_OVER, "Trận đấu đã kết thúc")
            symbol = self.symbol_of(user_id)
            if symbol is None:
                return self._fail(MoveCode.NOT_A_PLAYER,
                                  "Khán giả không được phép đánh cờ")
            if symbol is not self.turn:
                return self._fail(MoveCode.NOT_YOUR_TURN, "Chưa đến lượt của bạn")
            # bool là con của int trong Python -> loại ra rõ ràng
            if (not isinstance(row, int) or not isinstance(col, int)
                    or isinstance(row, bool) or isinstance(col, bool)):
                return self._fail(MoveCode.INVALID_TYPE, "Toạ độ phải là số nguyên")
            if not self.board.in_bounds(row, col):
                return self._fail(MoveCode.OUT_OF_BOUNDS, "Nước đi nằm ngoài bàn cờ")
            if not self.board.is_empty(row, col):
                return self._fail(MoveCode.CELL_OCCUPIED, "Ô đã có quân")
            return MoveOutcome(True, MoveCode.OK, "Hợp lệ", next_turn=self.turn)

    def play_move(self, user_id: str, row, col) -> MoveOutcome:
        """Xác thực + thực hiện nước đi + đổi lượt + kiểm tra kết quả (nguyên tử)."""
        with self._lock:
            # hết giờ nhưng server chưa kịp tick -> xử lý hết giờ trước
            timeout_result = self.check_timeout()
            if timeout_result is not None:
                return MoveOutcome(False, MoveCode.GAME_OVER,
                                   "Hết giờ suy nghĩ, trận đã kết thúc",
                                   result=timeout_result)

            check = self.validate_move(user_id, row, col)
            if not check.ok:
                return check

            symbol = self.turn
            self.board.place(row, col, symbol)
            move = Move(len(self.history) + 1, row, col, symbol, user_id, time.time())
            self.history.append(move)

            line = self.board.check_win(row, col)
            if line:
                result = self._finish(GameResult(
                    is_draw=False, reason=EndReason.FIVE_IN_ROW,
                    winner_id=user_id, loser_id=self.players[symbol.opponent],
                    winner_symbol=symbol, winning_line=tuple(line),
                    total_moves=len(self.history)))
                return MoveOutcome(True, MoveCode.OK, "Thắng", move, result, None)

            if self.board.is_full():
                result = self._finish(GameResult(
                    is_draw=True, reason=EndReason.BOARD_FULL,
                    total_moves=len(self.history)))
                return MoveOutcome(True, MoveCode.OK, "Hòa", move, result, None)

            self.turn = symbol.opponent
            self.timer.start()                 # reset đồng hồ cho người kế tiếp
            return MoveOutcome(True, MoveCode.OK, "OK", move, None, self.turn)

    # ------------------------------------------------------------------ kết thúc bất thường
    def check_timeout(self) -> Optional[GameResult]:
        """Server gọi định kỳ. Luật nhóm công bố: hết giờ -> người đến lượt THUA."""
        with self._lock:
            if self.status is not GameStatus.PLAYING or not self.timer.expired():
                return None
            return self._finish_by_loser(self.turn, EndReason.TIMEOUT)

    def resign(self, user_id: str) -> Optional[GameResult]:
        """Người chơi đầu hàng. Khán giả gọi sẽ bị bỏ qua (trả None)."""
        return self._forfeit(user_id, EndReason.RESIGN)

    def forfeit_disconnect(self, user_id: str) -> Optional[GameResult]:
        """TV5 gọi khi hết thời gian chờ kết nối lại -> người rời mạng thua."""
        return self._forfeit(user_id, EndReason.DISCONNECT)

    def _forfeit(self, user_id: str, reason: EndReason) -> Optional[GameResult]:
        with self._lock:
            symbol = self.symbol_of(user_id)
            if symbol is None or self.status is not GameStatus.PLAYING:
                return None
            return self._finish_by_loser(symbol, reason)

    # ------------------------------------------------------------------ đồng hồ cho reconnect
    def pause_clock(self) -> None:
        with self._lock:
            if self.status is GameStatus.PLAYING:
                self.timer.pause()

    def resume_clock(self) -> None:
        with self._lock:
            if self.status is GameStatus.PLAYING:
                self.timer.resume()

    # ------------------------------------------------------------------ snapshot cho TV5
    def snapshot(self) -> dict:
        """Trạng thái đầy đủ: gửi cho khán giả vào giữa trận / người kết nối lại."""
        with self._lock:
            return {
                "status": self.status.value,
                "size": self.board.size,
                "win_length": self.board.win_length,
                "board": self.board.to_rows(),
                "players": {"X": self.players[Symbol.X], "O": self.players[Symbol.O]},
                "turn": self.turn.value if self.status is GameStatus.PLAYING else None,
                "turn_limit": self.timer.limit,
                "time_left": round(self.timer.remaining(), 3),
                "clock_paused": self.timer.paused,
                "move_count": len(self.history),
                "last_move": self.history[-1].to_dict() if self.history else None,
                "history": [m.to_dict() for m in self.history],
                "result": self.result.to_dict() if self.result else None,
            }

    @classmethod
    def from_snapshot(cls, snap: dict,
                      clock: Callable[[], float] = time.monotonic) -> "GameEngine":
        """Khôi phục engine (vd: server restart, hoặc kiểm thử đồng bộ)."""
        eng = cls(snap["players"]["X"], snap["players"]["O"], snap["size"],
                  snap["win_length"], snap["turn_limit"], clock)
        for m in snap["history"]:
            mv = Move.from_dict(m)
            eng.board.place(mv.row, mv.col, mv.symbol)
            eng.history.append(mv)
        eng.status = GameStatus(snap["status"])
        if snap["result"]:
            eng.result = GameResult.from_dict(snap["result"])
        if eng.status is GameStatus.PLAYING:
            eng.turn = Symbol(snap["turn"])
            eng.timer.start(snap["time_left"])
            if snap["clock_paused"]:
                eng.timer.pause()
        return eng

    # ------------------------------------------------------------------ nội bộ
    @staticmethod
    def _fail(code: MoveCode, msg: str) -> MoveOutcome:
        return MoveOutcome(False, code, msg)

    def _finish(self, result: GameResult) -> GameResult:
        self.status = GameStatus.FINISHED
        self.result = result
        self.timer.stop()
        return result

    def _finish_by_loser(self, loser: Symbol, reason: EndReason) -> GameResult:
        winner = loser.opponent
        return self._finish(GameResult(
            is_draw=False, reason=reason,
            winner_id=self.players[winner], loser_id=self.players[loser],
            winner_symbol=winner, total_moves=len(self.history)))
