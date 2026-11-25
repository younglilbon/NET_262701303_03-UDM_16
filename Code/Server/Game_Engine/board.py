from typing import List, Tuple, Union

from .models import Symbol

DEFAULT_BOARD_SIZE = 15
EMPTY_CELL = ""
DIRECTIONS: Tuple[Tuple[int, int], ...] = ((1, 0), (0, 1), (1, 1), (1, -1))


class Board:
    """Bàn cờ Caro 2 chiều độc lập với giao diện."""

    def __init__(self, size: int = DEFAULT_BOARD_SIZE) -> None:
        if not isinstance(size, int) or isinstance(size, bool) or size < 5:
            raise ValueError("Kích thước bàn cờ phải là số nguyên >= 5.")
        self.size = size
        self._grid: List[List[str]] = [
            [EMPTY_CELL for _ in range(size)] for _ in range(size)
        ]

    @staticmethod
    def is_valid_coord_type(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool)

    def in_bounds(self, row: int, col: int) -> bool:
        if not (self.is_valid_coord_type(row) and self.is_valid_coord_type(col)):
            return False
        return 0 <= row < self.size and 0 <= col < self.size

    def get(self, row: int, col: int) -> str:
        if not self.in_bounds(row, col):
            raise IndexError(f"Tọa độ ({row}, {col}) nằm ngoài bàn cờ {self.size}x{self.size}.")
        return self._grid[row][col]

    def is_empty(self, row: int, col: int) -> bool:
        return self.get(row, col) == EMPTY_CELL

    def place(self, row: int, col: int, symbol: Union[Symbol, str]) -> None:
        sym = symbol.value if isinstance(symbol, Symbol) else Symbol(symbol).value
        if not self.in_bounds(row, col):
            raise IndexError(f"Tọa độ ({row}, {col}) nằm ngoài bàn cờ {self.size}x{self.size}.")
        if self._grid[row][col] != EMPTY_CELL:
            raise ValueError(f"Ô ({row}, {col}) đã có quân cờ.")
        self._grid[row][col] = sym

    def clear(self) -> None:
        for row in range(self.size):
            for col in range(self.size):
                self._grid[row][col] = EMPTY_CELL

    def is_full(self) -> bool:
        return all(cell != EMPTY_CELL for row in self._grid for cell in row)

    def to_matrix(self) -> List[List[str]]:
        """Trả về bản sao độc lập dạng list[list[str]]."""
        return [row[:] for row in self._grid]

    def winning_line(
        self, row: int, col: int, symbol: Union[Symbol, str]
    ) -> Tuple[Tuple[int, int], ...]:
        sym = symbol.value if isinstance(symbol, Symbol) else symbol
        return find_winning_line(self._grid, row, col, sym)


def find_winning_line(
    board: List[List[str]], row: int, col: int, symbol: str
) -> Tuple[Tuple[int, int], ...]:
    """Kiểm tra >= 5 quân liên tiếp theo 4 hướng đi qua (row, col).

    Chặn hai đầu vẫn tính thắng; trả về tuple tọa độ theo thứ tự liên tiếp.
    """
    size = len(board)
    if (
        not isinstance(row, int)
        or isinstance(row, bool)
        or not isinstance(col, int)
        or isinstance(col, bool)
        or not (0 <= row < size and 0 <= col < size)
        or not symbol
        or board[row][col] != symbol
    ):
        return ()

    for row_step, col_step in DIRECTIONS:
        backward: List[Tuple[int, int]] = []
        r, c = row - row_step, col - col_step
        while 0 <= r < size and 0 <= c < size and board[r][c] == symbol:
            backward.append((r, c))
            r -= row_step
            c -= col_step

        forward: List[Tuple[int, int]] = []
        r, c = row + row_step, col + col_step
        while 0 <= r < size and 0 <= c < size and board[r][c] == symbol:
            forward.append((r, c))
            r += row_step
            c += col_step

        line = list(reversed(backward)) + [(row, col)] + forward
        if len(line) >= 5:
            return tuple(line)
    return ()
