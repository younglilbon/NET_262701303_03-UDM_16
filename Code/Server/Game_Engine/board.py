"""Caro move validation and win/draw detection."""

from .models import EndReason, GameResult, Symbol


class GameEngine:
    DIRECTIONS = ((1, 0), (0, 1), (1, 1), (1, -1))

    @classmethod
    def winning_line(
        cls, board: list[list[str]], row: int, col: int, symbol: str
    ) -> tuple[tuple[int, int], ...]:
        size = len(board)
        for row_step, col_step in cls.DIRECTIONS:
            line = [(row, col)]
            for direction in (-1, 1):
                current_row, current_col = row, col
                while True:
                    current_row += row_step * direction
                    current_col += col_step * direction
                    if not (
                        0 <= current_row < size
                        and 0 <= current_col < size
                        and board[current_row][current_col] == symbol
                    ):
                        break
                    line.append((current_row, current_col))
            if len(line) >= 5:
                return tuple(line)
        return ()

    @staticmethod
    def is_board_full(board: list[list[str]]) -> bool:
        return all(cell for row in board for cell in row)

    @staticmethod
    def result(
        symbol: str | None,
        players: dict[str, str | None],
        reason: EndReason,
        total_moves: int,
        winning_line: tuple[tuple[int, int], ...] = (),
    ) -> GameResult:
        is_draw = symbol is None
        winner = players.get(symbol) if symbol is not None else None
        loser_symbol = Symbol(symbol).opponent.value if symbol is not None else None
        return GameResult(
            is_draw=is_draw,
            reason=reason,
            winner_id=winner,
            loser_id=players.get(loser_symbol) if loser_symbol else None,
            winner_symbol=Symbol(symbol) if symbol is not None else None,
            winning_line=winning_line,
            total_moves=total_moves,
        )

