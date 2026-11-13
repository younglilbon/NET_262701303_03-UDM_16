import tkinter as tk

from .style import (
    board_size,
    cell_size,
    board_margin,
    board_color,
    grid_color,
    x_color,
    o_color,
    font_mark,
)


class BoardWidget(tk.Canvas):

    def __init__(self, parent, on_move=None):
        
        board_pixels = 2 * board_margin + (board_size - 1) * cell_size

        super().__init__(
            parent,
            width=board_pixels,
            height=board_pixels,
            bg=board_color,
            highlightbackground=grid_color,
            highlightthickness=1,
            takefocus=True
        )

        self.on_move = on_move
        self.board = [["" for _ in range(board_size)] for _ in range(board_size)]
        self.input_enabled = True
        self.bind("<Button-1>", self._handle_click)
        self.draw_board()

    # Vẽ bàn cờ
    def draw_board(self):

        self.delete("all")

        end = board_margin + (board_size - 1) * cell_size

        for index in range(board_size):
            position = (board_margin + index * cell_size)
            self.create_line(board_margin, position, end, position, fill=grid_color, width = 1)
            self.create_line(position, board_margin, position, end, fill=grid_color, width = 1)

        for row in range(board_size):
            for col in range(board_size):
                mark = self.board[row][col]
                if mark != "":
                    self._draw_mark(row, col, mark)

    # Vẽ quân X và O
    def _draw_mark(self, row, col, mark):

        x = (board_margin + col * cell_size)
        y = (board_margin + row * cell_size)

        if mark == "X":
            color = x_color
        elif mark == "O":
            color = o_color
        else:
            raise ValueError(
                f"Quân cờ không hợp lệ: {mark}"
            )

        self.create_text(x, y, text=mark, fill=color, font=font_mark, anchor = tk.CENTER)

    def _get_cell_from_click(self, event):

        col = round((event.x - board_margin) / cell_size)
        row = round((event.y - board_margin) / cell_size)

        if not (0 <= row < board_size and 0 <= col < board_size):
            return None

        # Toạ độ chính xác của giao điểm: x theo cột, y theo hàng
        target_x = board_margin + col * cell_size
        target_y = board_margin + row * cell_size

        tolerance = cell_size * 0.4

        if abs(event.x - target_x) > tolerance or abs(event.y - target_y) > tolerance:
            return None
        return row, col

    #Xử lý sự kiện click
    def _handle_click(self, event):

        if not self.input_enabled:
            return

        if self.on_move is None:
            return

        cell = self._get_cell_from_click(event)

        if cell is None:
            return

        row, col = cell

        if self.board[row][col] != "":
            return

        self.on_move(row,col)

    #Bật/Tắt Thao tác
    def set_input_enable(self, enabled):
        self.input_enabled = bool(enabled)

    def enabled_board(self):
        self.set_input_enable(True)

    def disable_board(self):
        self.set_input_enable(False)

    #Cập nhật bàn cờ
    def render_board(self, board):
        if not isinstance(board, (list, tuple)):
            raise ValueError(
                "Dữ liệu bàn cờ phải là danh sách"
            )

        if len(board) != board_size:
            raise ValueError(
                f"Bàn cờ phải có {board_size} hàng"
            )
        new_board = []

        for row in board:
            if not isinstance(row, (list, tuple)):
                raise ValueError(
                    "Dữ liệu từng hàng không hợp lệ"
                )
            if len(row) != board_size:
                raise ValueError(
                    f"Mỗi hàng phải có {board_size} cột"
                )
            new_row = []

            for mark in row:
                if mark is None:
                    mark = ""

                if mark not in ("", "X", "O"):
                    raise ValueError(
                        f"Quân cờ không hợp lệ: {mark!r}"
                    )
                new_row.append(mark)
            new_board.append(new_row)
        self.board = new_board
        self.draw_board()

    #Reset bàn cờ
    def reset_board(self):

        empty_board = [
            ["" for _ in range(board_size)] for _ in range(board_size)
        ]

        self.render_board(empty_board)
        self.enabled_board()

    #Lấy dữ liệu bàn cờ
    def get_board(self):
        return [row[:] for row in self.board]