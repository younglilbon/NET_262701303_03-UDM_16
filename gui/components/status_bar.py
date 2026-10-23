import tkinter as tk

from gui.style import (
    SECONDARY_COLOR,
    FONT_NORMAL,
    SUCCESS_COLOR,
    ERROR_COLOR,
)


class StatusBar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padx=10, pady=6)

        self.connection_var = tk.StringVar(
            value="Chế độ DEMO"
        )
        self.message_var = tk.StringVar(
            value="Sẵn sàng"
        )

        self.connection_label = tk.Label(
            self,
            textvariable=self.connection_var,
            font=FONT_NORMAL,
            fg=SECONDARY_COLOR,
        )
        self.connection_label.pack(
            side=tk.LEFT, padx=5
        )

        self.message_label = tk.Label(
            self,
            textvariable=self.message_var,
            font=FONT_NORMAL,
            anchor="e",
        )
        self.message_label.pack(
            side=tk.RIGHT, padx=5
        )

    def set_connection(self, message, online=False):
        self.connection_var.set(message)

        color = SUCCESS_COLOR if online else ERROR_COLOR
        self.connection_label.config(fg=color)

    def set_message(self, message):
        self.message_var.set(message)
