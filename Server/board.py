"""board.py - Bàn cờ Caro và thuật toán kiểm tra thắng (TV4)."""
from typing import List, Optional, Tuple

from .models import Symbol

Cell = Tuple[int, int]
# 4 hướng: ngang, dọc, chéo chính, chéo phụ
DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))


class Board:
    def __init__(self, size: int = 15, win_length: int = 5):
        if size < 3:
            raise ValueError("size phải >= 3")
        if not 3 <= win_length <= size:
            raise ValueError("win_length phải trong [3, size]")
        self.size = size
        self.win_length = win_length
        self._grid: List[List[Optional[Symbol]]] = [[None] * size for _ in range(size)]
        self.move_count = 0

    # ---------- truy vấn ----------
    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.size and 0 <= col < self.size

    def get(self, row: int, col: int) -> Optional[Symbol]:
        return self._grid[row][col]

    def is_empty(self, row: int, col: int) -> bool:
        return self._grid[row][col] is None

    def is_full(self) -> bool:
        return self.move_count >= self.size * self.size

    # ---------- thao tác ----------
    def place(self, row: int, col: int, symbol: Symbol) -> None:
        """Đặt quân. Việc kiểm tra hợp lệ do Engine làm; ở đây chỉ chặn lỗi lập trình."""
        if not self.in_bounds(row, col) or not self.is_empty(row, col):
            raise ValueError("Ô không hợp lệ hoặc đã có quân")
        self._grid[row][col] = symbol
        self.move_count += 1

    # ---------- thuật toán thắng ----------
    def check_win(self, row: int, col: int) -> Optional[List[Cell]]:
        """Kiểm tra quân vừa đặt tại (row, col) có tạo đường thắng không.

        Chỉ cần xét 4 đường đi qua ô vừa đánh (không quét cả bàn): với mỗi hướng
        đếm các quân cùng loại liên tiếp về 2 phía. Độ phức tạp O(4 * win_length)
        = O(1) cho mỗi nước đi.
        Trả về danh sách ô tạo thành đường thắng (>= win_length quân) hoặc None.
        """
        symbol = self._grid[row][col]
        if symbol is None:
            return None
        for dr, dc in DIRECTIONS:
            line: List[Cell] = [(row, col)]
            # đi về phía +
            r, c = row + dr, col + dc
            while self.in_bounds(r, c) and self._grid[r][c] == symbol:
                line.append((r, c))
                r, c = r + dr, c + dc
            # đi về phía -
            r, c = row - dr, col - dc
            while self.in_bounds(r, c) and self._grid[r][c] == symbol:
                line.insert(0, (r, c))
                r, c = r - dr, c - dc
            if len(line) >= self.win_length:
                return line
        return None

    # ---------- (de)serialize ----------
    def to_rows(self) -> List[str]:
        """Mỗi hàng là 1 chuỗi, '.' = trống. Gọn để gửi qua mạng."""
        return ["".join(c.value if c else "." for c in row) for row in self._grid]

    @classmethod
    def from_rows(cls, rows: List[str], win_length: int = 5) -> "Board":
        b = cls(len(rows), win_length)
        for r, line in enumerate(rows):
            if len(line) != b.size:
                raise ValueError("Bàn cờ phải vuông")
            for c, ch in enumerate(line):
                if ch in ("X", "O"):
                    b._grid[r][c] = Symbol(ch)
                    b.move_count += 1
                elif ch != ".":
                    raise ValueError(f"Ký tự không hợp lệ: {ch!r}")
        return b

    def __str__(self) -> str:
        header = "   " + " ".join(f"{c:2d}" for c in range(self.size))
        lines = [header]
        for r, row in enumerate(self.to_rows()):
            lines.append(f"{r:2d} " + " ".join(f" {ch}" for ch in row))
        return "\n".join(lines)
