from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class Symbol(str, Enum):
    X = "X"
    O = "O"

    @property
    def opponent(self) -> "Symbol":
        return Symbol.O if self is Symbol.X else Symbol.X


class GameStatus(str, Enum):
    WAITING = "WAITING"    # đã tạo, chưa bắt đầu
    PLAYING = "PLAYING"    # đang chơi
    PAUSED = "PAUSED"      # tạm dừng chờ reconnect
    FINISHED = "FINISHED"  # đã có kết quả


class EndReason(str, Enum):
    FIVE_IN_ROW = "FIVE_IN_ROW"              # đủ >= 5 quân liên tiếp
    BOARD_FULL = "BOARD_FULL"                # hết ô -> hòa
    TIMEOUT = "TIMEOUT"                      # hết giờ suy nghĩ -> thua
    RESIGN = "RESIGN"                        # chủ động rời/đầu hàng
    DISCONNECT = "DISCONNECT"                # mất kết nối quá hạn (1 người)
    BOTH_DISCONNECTED = "BOTH_DISCONNECTED"  # cả hai mất kết nối quá hạn -> ABORTED


class MoveCode(str, Enum):
    """Mã kết quả kiểm tra nước đi."""
    OK = "OK"
    GAME_NOT_STARTED = "GAME_NOT_STARTED"
    GAME_PAUSED = "GAME_PAUSED"
    GAME_OVER = "GAME_OVER"
    NOT_A_PLAYER = "NOT_A_PLAYER"      # khán giả / người lạ gửi nước đi
    NOT_YOUR_TURN = "NOT_YOUR_TURN"
    OUT_OF_BOUNDS = "OUT_OF_BOUNDS"
    CELL_OCCUPIED = "CELL_OCCUPIED"
    INVALID_TYPE = "INVALID_TYPE"      # row/col không phải số nguyên (hoặc là bool)

    @property
    def protocol_code(self) -> str:
        """Mã lỗi chuẩn gửi qua giao thức JSON theo mục 9.3."""
        mapping = {
            MoveCode.GAME_NOT_STARTED: "INVALID_STATE",
            MoveCode.INVALID_TYPE: "INVALID_ARGUMENT",
            MoveCode.NOT_A_PLAYER: "SPECTATOR_FORBIDDEN",
        }
        return mapping.get(self, self.value)


@dataclass(frozen=True)
class Move:
    number: int          # thứ tự nước đi, bắt đầu từ 1
    row: int
    col: int
    symbol: Symbol
    player_id: str
    timestamp: float     # time.time()

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "move_number": self.number,
            "row": self.row,
            "col": self.col,
            "symbol": self.symbol.value,
            "player_id": self.player_id,
            "player": self.player_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Move":
        number = d["number"] if "number" in d else d["move_number"]
        player_id = d["player_id"] if "player_id" in d else d["player"]
        return cls(
            number,
            d["row"],
            d["col"],
            Symbol(d["symbol"]),
            player_id,
            d["timestamp"],
        )


@dataclass(frozen=True)
class GameResult:
    is_draw: bool
    reason: EndReason
    winner_id: Optional[str] = None
    loser_id: Optional[str] = None
    winner_symbol: Optional[Symbol] = None
    winning_line: Tuple[Tuple[int, int], ...] = ()
    total_moves: int = 0
    outcome: Optional[str] = None

    def __post_init__(self) -> None:
        if self.reason is EndReason.BOTH_DISCONNECTED and self.is_draw:
            raise ValueError("BOTH_DISCONNECTED must not be marked as is_draw=True (ABORTED).")
        if self.is_draw and self.reason is not EndReason.BOARD_FULL:
            raise ValueError("is_draw=True is only valid for BOARD_FULL.")

    @property
    def outcome_text(self) -> str:
        if self.outcome is not None:
            return self.outcome
        if self.reason is EndReason.BOTH_DISCONNECTED:
            return "ABORTED"
        return "DRAW" if self.is_draw else "WIN"

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome_text,
            "is_draw": self.is_draw,
            "reason": self.reason.value,
            "winner_id": self.winner_id,
            "loser_id": self.loser_id,
            "winner_symbol": self.winner_symbol.value if self.winner_symbol else None,
            "winning_line": [list(p) for p in self.winning_line],
            "total_moves": self.total_moves,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GameResult":
        ws = d.get("winner_symbol")
        return cls(
            d["is_draw"],
            EndReason(d["reason"]),
            d.get("winner_id"),
            d.get("loser_id"),
            Symbol(ws) if ws else None,
            tuple(tuple(p) for p in d.get("winning_line", [])),
            d.get("total_moves", 0),
            d.get("outcome"),
        )


@dataclass
class MoveOutcome:
    """Giá trị trả về của GameEngine.validate_move() và GameEngine.play_move()."""
    ok: bool
    code: MoveCode
    message: str = ""
    move: Optional[Move] = None
    result: Optional[GameResult] = None   # khác None nếu nước đi này kết thúc trận
    next_turn: Optional[Symbol] = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "code": self.code.value,
            "protocol_code": self.code.protocol_code,
            "message": self.message,
            "move": self.move.to_dict() if self.move else None,
            "result": self.result.to_dict() if self.result else None,
            "next_turn": self.next_turn.value if self.next_turn else None,
        }
