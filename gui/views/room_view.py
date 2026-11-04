import tkinter as tk

from gui.style import (
    BG_COLOR,
    PRIMARY_COLOR,
    SECONDARY_COLOR,
    FONT_TITLE,
    FONT_SUBTITLE,
    FONT_NORMAL,
    FONT_SMALL,
)


class RoomView(tk.Frame):

    def __init__(
        self,
        parent,
        username,
        room_id,
        on_start_game,
        on_back
    ):

        super().__init__(
            parent,
            bg=BG_COLOR
        )

        # Lưu thông tin phòng và callback.
        self.username = username
        self.room_id = room_id
        self.on_start_game = on_start_game
        self.on_back = on_back

        self.create_widgets()

    # TẠO GIAO DIỆN PHÒNG ĐẤU

    def create_widgets(self):

        # Tiêu đề.
        tk.Label(
            self,
            text="PHÒNG ĐẤU CARO",
            font=FONT_TITLE,
            fg=PRIMARY_COLOR,
            bg=BG_COLOR,
        ).pack(pady=25)

        # Thông tin phòng.
        info_frame = tk.Frame(
            self,
            bg="white",
            padx=30,
            pady=20,
            relief=tk.SOLID,
            bd=1,
        )

        info_frame.pack(pady=10)

        tk.Label(
            info_frame,
            text=f"Mã phòng: {self.room_id}",
            font=FONT_SUBTITLE,
            fg=PRIMARY_COLOR,
            bg="white",
        ).pack(pady=10)

        tk.Label(
            info_frame,
            text=f"Người chơi hiện tại: {self.username}",
            font=FONT_NORMAL,
            bg="white",
        ).pack(pady=8)

        tk.Label(
            info_frame,
            text="Đối thủ: Người chơi demo",
            font=FONT_NORMAL,
            bg="white",
        ).pack(pady=8)

        tk.Label(
            info_frame,
            text="Trạng thái: Đang chờ bắt đầu",
            font=FONT_NORMAL,
            fg="#64748B",
            bg="white",
        ).pack(pady=8)

        # Thông báo demo.
        tk.Label(
            self,
            text="Đây là phòng đấu mô phỏng, chưa kết nối Server.",
            font=FONT_SMALL,
            fg="#64748B",
            bg=BG_COLOR,
        ).pack(pady=10)

        # CÁC NÚT CHỨC NĂNG

        buttons = tk.Frame(
            self,
            bg=BG_COLOR
        )

        buttons.pack(pady=15)

        # Nút bắt đầu chơi.
        tk.Button(
            buttons,
            text="Bắt đầu chơi demo",
            command=self.start_game,
            bg=PRIMARY_COLOR,
            fg="white",
            activebackground="#0D2C63",
            activeforeground="white",
            font=FONT_NORMAL,
            width=22,
            relief=tk.FLAT,
            cursor="hand2",
        ).pack(
            pady=8,
            ipady=5
        )

        # Nút quay lại sảnh chờ.
        tk.Button(
            buttons,
            text="Quay lại sảnh chờ",
            command=self.back_to_lobby,
            bg=SECONDARY_COLOR,
            fg=PRIMARY_COLOR,
            font=FONT_NORMAL,
            width=22,
            relief=tk.FLAT,
            cursor="hand2",
        ).pack(
            pady=8,
            ipady=5
        )

    # BẮT ĐẦU TRẬN ĐẤU

    def start_game(self):

        if callable(self.on_start_game):
            self.on_start_game()

    # QUAY LẠI SẢNH CHỜ

    def back_to_lobby(self):

        if callable(self.on_back):
            self.on_back()
