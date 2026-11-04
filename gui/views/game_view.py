import tkinter as tk
from tkinter import messagebox

from gui.components.board_widget import BoardWidget
from gui.components.status_bar import StatusBar

from gui.style import (
    BG_COLOR,
    PRIMARY_COLOR,
    FONT_TITLE,
    FONT_SUBTITLE,
    FONT_NORMAL,
)


class GameView(tk.Frame):

    def __init__(
        self, parent, username, room_id, on_leave
    ):
        super().__init__(
            parent,
            bg=BG_COLOR
        )

        # Thông tin người chơi và phòng đấu
        self.username = username
        self.room_id = room_id
        self.on_leave = on_leave

        # Trạng thái trò chơi
        self.current_turn = "X"
        self.game_over = False

        # TIÊU ĐỀ TRÒ CHƠI

        tk.Label(
            self,
            text=f"CARO - {room_id}",
            font=FONT_TITLE,
            fg=PRIMARY_COLOR,
            bg=BG_COLOR,
        ).pack(pady=8)

        tk.Label(
            self,
            text=f"Người chơi: {username}",
            font=FONT_NORMAL,
            bg=BG_COLOR,
        ).pack()

        # HIỂN THỊ LƯỢT CHƠI

        self.turn_var = tk.StringVar(
            value="Lượt hiện tại: X"
        )

        tk.Label(
            self,
            textvariable=self.turn_var,
            font=FONT_SUBTITLE,
            fg=PRIMARY_COLOR,
            bg=BG_COLOR,
        ).pack(pady=5)

        # THANH TRẠNG THÁI

        self.status_bar = StatusBar(self)

        self.status_bar.pack(
            fill=tk.X
        )

        self.status_bar.set_connection(
            "Chế độ DEMO - Chưa kết nối Server",
            online=False
        )

        self.status_bar.set_message(
            "Đến lượt người chơi X"
        )

        # BÀN CỜ CARO=

        self.board_widget = BoardWidget(
            self,
            on_move=self.handle_move
        )

        self.board_widget.pack(
            pady=5
        )

        # CÁC NÚT CHỨC NĂNG

        buttons = tk.Frame(
            self,
            bg=BG_COLOR
        )

        buttons.pack(pady=8)

        tk.Button(
            buttons,
            text="Chơi lại",
            font=FONT_NORMAL,
            bg=PRIMARY_COLOR,
            fg="white",
            activebackground="#0D2C63",
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.restart_game,
        ).pack(
            side=tk.LEFT,
            padx=5,
            ipadx=10,
            ipady=5
        )

        tk.Button(
            buttons,
            text="Rời phòng",
            font=FONT_NORMAL,
            bg="#E0E0E0",
            fg="#222222",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.leave_game,
        ).pack(
            side=tk.LEFT,
            padx=5,
            ipadx=10,
            ipady=5
        )

    # XỬ LÝ NƯỚC ĐI

    def handle_move(self, row, col):
        # Nếu trận đấu đã kết thúc thì không cho đánh tiếp
        if self.game_over:
            return

        mark = self.current_turn

        # Đặt quân lên bàn cờ
        placed = self.board_widget.place_mark(
            row, col, mark
        )

        if not placed:
            return

        print("\n==== KIỂM TRA BÀN CỜ ====")
        print("Người vừa đánh: ", mark)
        print("Vị trí: ", row, col)

        board = self.board_widget.get_board()

        for line in board:
            print(line)

        print("===========================")

        # Kiểm tra chiến thắng
        if self.check_winner(row, col, mark):
            self.game_over = True

            self.turn_var.set(
                f"Người chơi {mark} chiến thắng!"
            )

            self.status_bar.set_message(
                f"Người chơi {mark} đã chiến thắng!"
            )

            messagebox.showinfo(
                "Kết thúc trận đấu",
                f"Người chơi {mark} Win!"
            )

            return

        # Chưa thắng thì chuyển lượt
        self.current_turn = "O" if mark == "X" else "X"

        self.turn_var.set(
            f"Lượt hiện tại: {self.current_turn}"
        )

        self.status_bar.set_message(
            f"Đến lượt người chơi {self.current_turn}"
        )
    
    # XỬ LÝ KẾT THÚC TRÒ CHƠI
    def check_winner(self, row, col, mark):
        board = self.board_widget.get_board()

        rows = len(board)
        cols = len(board[0]) if rows > 0 else 0

        #Kiểm tra dữ liệu nước đi
        if not (0 <= row < rows and 0 <= col < cols):
            return False

        #Ô vừa đánh phải đúng là quân đang kiểm tra
        if board[row][col] != mark:
            return False

        # 4 hướng kiểm tra:
        # Ngang, dọc, chéo xuống, chéo lên
        directions = [
            (0, 1),
            (1, 0),
            (1, 1),
            (1, -1)
        ]

        for dr, dc in directions:

            # Tính quân vừa đánh
            count = 1

            # Kiểm tra hai phía của quân vừa đánh
            for direction in (1, -1):

                r = row + dr * direction
                c = col + dc * direction

                while (
                    0 <= r < rows
                    and 0 <= c < cols
                    and board[r][c] == mark
                ):
                    count += 1

                    r += dr * direction
                    c += dc * direction

                print(
                    f"Hướng({dr}, {dc}): "
                    f"Đếm được {count} quân {mark}"
                )

            # Chỉ thắng khi có ít nhất 5 quân liên tiếp
            if count >= 5:
                return True

        return False
    
    # KHỞI ĐỘNG LẠI TRÒ CHƠI

    def restart_game(self):

        # Xóa toàn bộ quân cờ.
        self.board_widget.reset_board()

        # Đưa lượt chơi về X.
        self.current_turn = "X"

        # Đặt lại trạng thái trò chơi.
        self.game_over = False

        # Cập nhật giao diện.
        self.turn_var.set(
            "Lượt hiện tại: X"
        )

        self.status_bar.set_message(
            "Đã bắt đầu ván demo mới"
        )

    # RỜI PHÒNG

    def leave_game(self):

        should_leave = messagebox.askyesno(
            "Rời phòng",
            "Bạn có muốn rời phòng đấu không?"
        )

        if should_leave and self.on_leave:
            self.on_leave()
