import tkinter as tk

from gui.style import (
    BOARD_SIZE,
    CELL_SIZE,
    BOARD_MARGIN,
    BOARD_COLOR,
    GRID_COLOR,
    X_COLOR,
    O_COLOR,
    FONT_MARK,
)


class BoardWidget(tk.Canvas):
    def __init__(self, parent, on_move=None):

        # Tính kích thước Canvas.
        # 15 giao điểm tạo thành 14 khoảng cách.
        board_pixels = (
            2 * BOARD_MARGIN
            + (BOARD_SIZE - 1) * CELL_SIZE
        )

        super().__init__(
            parent,
            width=board_pixels,
            height=board_pixels,
            bg=BOARD_COLOR,
            highlightthickness=1,
            highlightbackground=GRID_COLOR,
        )

        self.on_move = on_move

        # Khởi tạo ma trận bàn cờ.
        self.board = [
            ["" for _ in range(BOARD_SIZE)]
            for _ in range(BOARD_SIZE)
        ]

        # Bắt sự kiện click chuột trái.
        self.bind("<Button-1>", self._handle_click)

        # Vẽ bàn cờ ban đầu.
        self.draw_board()

    # VẼ BÀN CỜ

    def draw_board(self):
        self.delete("all")

        end = (
            BOARD_MARGIN
            + (BOARD_SIZE - 1) * CELL_SIZE
        )

        # Vẽ các đường ngang và đường dọc.
        for i in range(BOARD_SIZE):

            pos = BOARD_MARGIN + i * CELL_SIZE

            # Đường ngang.
            self.create_line(
                BOARD_MARGIN,
                pos,
                end,
                pos,
                fill=GRID_COLOR
            )

            # Đường dọc.
            self.create_line(
                pos,
                BOARD_MARGIN,
                pos,
                end,
                fill=GRID_COLOR
            )

        # Vẽ lại những quân cờ đã được đặt.
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):

                mark = self.board[row][col]

                if mark:
                    self._draw_mark(row, col, mark)

    # VẼ QUÂN CỜ X VÀ O

    def _draw_mark(self, row, col, mark):

        # Tính tọa độ giao điểm.
        x = BOARD_MARGIN + col * CELL_SIZE
        y = BOARD_MARGIN + row * CELL_SIZE

        # Chọn màu theo quân cờ.
        if mark == "X":
            color = X_COLOR
        else:
            color = O_COLOR

        self.create_text(
            x,
            y,
            text=mark,
            fill=color,
            font=FONT_MARK,
        )

    # XỬ LÝ SỰ KIỆN CLICK CHUỘT

    def _handle_click(self, event):

        # Tìm giao điểm gần vị trí click nhất.
        col = round(
            (event.x - BOARD_MARGIN) / CELL_SIZE
        )

        row = round(
            (event.y - BOARD_MARGIN) / CELL_SIZE
        )

        # Kiểm tra tọa độ có nằm trong bàn cờ không.
        if not (
            0 <= row < BOARD_SIZE
            and 0 <= col < BOARD_SIZE
        ):
            return

        # Tính tọa độ chính xác của giao điểm gần nhất.
        target_x = BOARD_MARGIN + col * CELL_SIZE
        target_y = BOARD_MARGIN + row * CELL_SIZE

        # Chỉ chấp nhận click đủ gần giao điểm.
        tolerance = CELL_SIZE * 0.4

        if (
            abs(event.x - target_x) > tolerance
            or abs(event.y - target_y) > tolerance
        ):
            return

        # Không cho phép đánh vào vị trí đã có quân.
        if self.board[row][col] != "":
            return

        # Chuyển tọa độ cho GameView xử lý.
        if self.on_move:
            self.on_move(row, col)

    # ĐẶT QUÂN CỜ

    def place_mark(self, row, col, mark):

        # Kiểm tra quân cờ hợp lệ.
        if mark not in ("X", "O"):
            raise ValueError(
                "Quân cờ phải là X hoặc O."
            )

        # Kiểm tra tọa độ.
        if not (
            0 <= row < BOARD_SIZE
            and 0 <= col < BOARD_SIZE
        ):
            raise ValueError(
                "Tọa độ nằm ngoài bàn cờ."
            )

        # Kiểm tra ô đã có quân chưa.
        if self.board[row][col] != "":
            return False

        # Lưu quân cờ vào ma trận.
        self.board[row][col] = mark

        # Vẽ quân cờ lên giao diện.
        self._draw_mark(row, col, mark)

        return True

    # LÀM MỚI BÀN CỜ

    def reset_board(self):

        # Khởi tạo lại ma trận rỗng.
        self.board = [
            ["" for _ in range(BOARD_SIZE)]
            for _ in range(BOARD_SIZE)
        ]

        # Vẽ lại bàn cờ.
        self.draw_board()

    # LẤY DỮ LIỆU BÀN CỜ

    def get_board(self):

        # Trả về bản sao để tránh thay đổi
        # trực tiếp ma trận bên trong.
        return [row[:] for row in self.board]
