import tkinter as tk

from gui.style import (
    BG_COLOR,
    PRIMARY_COLOR,
    FONT_NORMAL,
    SUCCESS_COLOR,
    ERROR_COLOR,
)


class StatusBar(tk.Frame):

    def __init__(self, parent):

        super().__init__(
            parent,
            bg=BG_COLOR,
            padx=10,
            pady=6
        )

        # Trạng thái kết nối
        self.connection_var = tk.StringVar(
            value="Chế độ DEMO"
        )

        # Thông báo trò chơi
        self.message_var = tk.StringVar(
            value="Sẵn sàng"
        )

        # Nhãn trạng thái kết nối
        self.connection_label = tk.Label(
            self,
            textvariable=self.connection_var,
            font=FONT_NORMAL,
            fg=ERROR_COLOR,
            bg=BG_COLOR,
        )

        self.connection_label.pack(
            side=tk.LEFT,
            padx=5
        )

        # Nhãn thông báo
        self.message_label = tk.Label(
            self,
            textvariable=self.message_var,
            font=FONT_NORMAL,
            fg=PRIMARY_COLOR,
            bg=BG_COLOR,
            anchor="e",
        )

        self.message_label.pack(
            side=tk.RIGHT,
            padx=5
        )

    # CẬP NHẬT TRẠNG THÁI KẾT NỐI

    def set_connection(self, message, online=False):

        self.connection_var.set(message)

        color = (
            SUCCESS_COLOR
            if online
            else ERROR_COLOR
        )

        self.connection_label.config(
            fg=color
        )

    # CẬP NHẬT THÔNG BÁO

    def set_message(self, message):

        self.message_var.set(message)
