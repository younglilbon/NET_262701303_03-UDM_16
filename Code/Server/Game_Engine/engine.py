import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .board import Board, DEFAULT_BOARD_SIZE, DIRECTIONS, find_winning_line
from .models import (
    EndReason,
    GameResult,
    GameStatus,
    Move,
    MoveCode,
    MoveOutcome,
    Symbol,
)
from .timer import DEFAULT_TURN_TIME_LIMIT, TurnTimer


class GameEngine:
    """Bộ xử lý luật chơi Caro độc lập với GUI và mạng."""

    DIRECTIONS = DIRECTIONS

    def __init__(
        self,
        board_size: int = DEFAULT_BOARD_SIZE,
        turn_timeout: float = DEFAULT_TURN_TIME_LIMIT,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.board = Board(size=board_size)
        self.timer = TurnTimer(limit=turn_timeout, clock=clock)
        self.players: Dict[str, Optional[str]] = {"X": None, "O": None}
        self.status: GameStatus = GameStatus.WAITING
        self.current_turn: Symbol = Symbol.X
        self.moves: List[Move] = []
        self.match_result: Optional[GameResult] = None

    # ---------- Vòng đời ván đấu ----------
    def start(self, player_x: str, player_o: str) -> None:
        """Khởi tạo ván mới: bàn trống, X luôn đi trước, bắt đầu đồng hồ lượt."""
        if not player_x or not player_o or player_x == player_o:
            raise ValueError("Cần hai người chơi hợp lệ và khác nhau cho X và O.")
        self.players = {"X": player_x, "O": player_o}
        self.board.clear()
        self.moves.clear()
        self.match_result = None
        self.status = GameStatus.PLAYING
        self.current_turn = Symbol.X
        self.timer.start()

    def pause(self) -> None:
        if self.status is GameStatus.PLAYING:
            self.status = GameStatus.PAUSED
            self.timer.pause()

    def resume(self) -> None:
        if self.status is GameStatus.PAUSED:
            self.status = GameStatus.PLAYING
            self.timer.resume()

    def player_symbol(self, player_id: str) -> Optional[Symbol]:
        if player_id == self.players.get("X"):
            return Symbol.X
        if player_id == self.players.get("O"):
            return Symbol.O
        return None

    # ---------- Kiểm tra & thực hiện nước đi ----------
    def validate_move(self, player_id: str, row: Any, col: Any) -> MoveOutcome:
        if self.status is GameStatus.WAITING:
            return MoveOutcome(
                False, MoveCode.GAME_NOT_STARTED, "Trận đấu chưa bắt đầu."
            )
        if self.status is GameStatus.PAUSED:
            return MoveOutcome(
                False, MoveCode.GAME_PAUSED, "Trận đấu đang tạm dừng chờ kết nối lại."
            )
        if self.status is GameStatus.FINISHED:
            return MoveOutcome(
                False, MoveCode.GAME_OVER, "Trận đấu đã kết thúc."
            )

        role = self.player_symbol(player_id)
        if role is None:
            return MoveOutcome(
                False, MoveCode.NOT_A_PLAYER, "Bạn không phải người chơi trong trận."
            )
        if role is not self.current_turn:
            return MoveOutcome(
                False, MoveCode.NOT_YOUR_TURN, "Chưa đến lượt của bạn."
            )
        if (
            not Board.is_valid_coord_type(row)
            or not Board.is_valid_coord_type(col)
        ):
            return MoveOutcome(
                False,
                MoveCode.INVALID_TYPE,
                "Tọa độ row và col phải là số nguyên (không chấp nhận bool).",
            )
        if not self.board.in_bounds(row, col):
            return MoveOutcome(
                False,
                MoveCode.OUT_OF_BOUNDS,
                f"Tọa độ ({row}, {col}) nằm ngoài bàn cờ {self.board.size}x{self.board.size}.",
            )
        if not self.board.is_empty(row, col):
            return MoveOutcome(
                False,
                MoveCode.CELL_OCCUPIED,
                f"Ô ({row}, {col}) đã có quân cờ.",
            )
        return MoveOutcome(True, MoveCode.OK, "Nước đi hợp lệ.")

    def play_move(self, player_id: str, row: Any, col: Any) -> MoveOutcome:
        outcome = self.validate_move(player_id, row, col)
        if not outcome.ok:
            return outcome

        role = self.current_turn
        self.board.place(row, col, role)
        move = Move(
            number=len(self.moves) + 1,
            row=row,
            col=col,
            symbol=role,
            player_id=player_id,
            timestamp=time.time(),
        )
        self.moves.append(move)

        # Kiểm tra thắng trước khi kiểm tra đầy bàn theo mục 2.
        line = self.board.winning_line(row, col, role)
        if line:
            self.status = GameStatus.FINISHED
            self.timer.stop()
            game_result = self.result(
                role.value,
                self.players,
                EndReason.FIVE_IN_ROW,
                len(self.moves),
                line,
            )
            self.match_result = game_result
            return MoveOutcome(
                True,
                MoveCode.OK,
                f"Người chơi {role.value} thắng.",
                move=move,
                result=game_result,
                next_turn=None,
            )

        if self.board.is_full():
            self.status = GameStatus.FINISHED
            self.timer.stop()
            game_result = self.result(
                None,
                self.players,
                EndReason.BOARD_FULL,
                len(self.moves),
            )
            self.match_result = game_result
            return MoveOutcome(
                True,
                MoveCode.OK,
                "Hòa do bàn cờ đã đầy.",
                move=move,
                result=game_result,
                next_turn=None,
            )

        self.current_turn = role.opponent
        self.timer.start()
        return MoveOutcome(
            True,
            MoveCode.OK,
            "Nước đi hợp lệ.",
            move=move,
            result=None,
            next_turn=self.current_turn,
        )

    def check_timeout(self) -> Optional[GameResult]:
        if self.status is GameStatus.PLAYING and self.timer.expired():
            winner_symbol = self.current_turn.opponent
            return self.finish(winner_symbol, EndReason.TIMEOUT)
        return None

    def finish(
        self,
        winner_symbol: Optional[Union[Symbol, str]],
        reason: Union[EndReason, str],
    ) -> GameResult:
        """Chốt kết quả trận đấu tối đa một lần."""
        if self.match_result is not None:
            return self.match_result
        end_reason = reason if isinstance(reason, EndReason) else EndReason(reason)
        self.status = GameStatus.FINISHED
        self.timer.stop()
        if end_reason is EndReason.BOTH_DISCONNECTED:
            sym_str = None
        elif isinstance(winner_symbol, Symbol):
            sym_str = winner_symbol.value
        elif winner_symbol in ("X", "O"):
            sym_str = winner_symbol
        else:
            sym_str = None
        self.match_result = self.result(
            sym_str,
            self.players,
            end_reason,
            len(self.moves),
        )
        return self.match_result

    # ---------- Hàm thuần / tương thích trực tiếp ----------
    @classmethod
    def winning_line(
        cls, board: List[List[str]], row: int, col: int, symbol: str
    ) -> Tuple[Tuple[int, int], ...]:
        return find_winning_line(board, row, col, symbol)

    @staticmethod
    def is_board_full(board: List[List[str]]) -> bool:
        return all(cell != "" for row in board for cell in row)

    @staticmethod
    def result(
        symbol: Optional[str],
        players: Dict[str, Optional[str]],
        reason: Union[EndReason, str],
        total_moves: int,
        winning_line: Tuple[Tuple[int, int], ...] = (),
    ) -> GameResult:
        end_reason = reason if isinstance(reason, EndReason) else EndReason(reason)
        if end_reason is EndReason.BOTH_DISCONNECTED:
            return GameResult(
                is_draw=False,
                reason=EndReason.BOTH_DISCONNECTED,
                winner_id=None,
                loser_id=None,
                winner_symbol=None,
                winning_line=(),
                total_moves=total_moves,
                outcome="ABORTED",
            )
        is_draw = symbol is None
        winner = players.get(symbol) if symbol is not None else None
        loser_symbol = Symbol(symbol).opponent.value if symbol is not None else None
        return GameResult(
            is_draw=is_draw,
            reason=end_reason,
            winner_id=winner,
            loser_id=players.get(loser_symbol) if loser_symbol else None,
            winner_symbol=Symbol(symbol) if symbol is not None else None,
            winning_line=winning_line,
            total_moves=total_moves,
            outcome="DRAW" if is_draw else "WIN",
        )
