import tkinter as tk

from GUI.style import (
    bg_color,
    primary_color,
    border_color,
    secondary_color,
    font_normal,
    font_small,
    success_color,
    error_color,
    warning_color
)


class StatusBar(tk.Frame):
    def __init__(self, parent):
        super().__init__(
            parent,
            bg = bg_color,
            padx = 10,
            pady = 6,
            highlightbackground=border_color,
            highlightthickness=1
        )

        #Biến lưu trạng thái

        self.connection_var = tk.StringVar(
            value="Chế độ DEMO"
        )
        self.message_var = tk.StringVar(
            value="Sẵn sàng"
        )

        #Trạng thái kết nối
        self.connection_label = tk.Label(
            self,
            textvariable=self.connection_var,
            font=font_normal,
            fg=secondary_color,
            bg=bg_color
        )
        self.connection_label.pack(
            side=tk.LEFT, padx=5
        )

        #Đường phân cách
        separator = tk.Frame(
            self,
            bg=border_color,
            width=1
        )

        separator.pack(
            side=tk.LEFT,
            fill=tk.Y,
            padx=10
        )

        #Thông báo
        self.message_label = tk.Label(
            self,
            textvariable=self.message_var,
            font=font_normal,
            fg=primary_color,
            bg=bg_color,
            anchor="w"
        )
        self.message_label.pack(
            side=tk.RIGHT, 
            padx=5,
            fill=tk.X,
            expand=True
        )

    #Cập nhật trạng thái kết nối
    def set_connection(self, message, online=False):
        self.connection_var.set(message)

        if online:
            color = success_color

        elif message=="Chế độ DEMO":
            color = warning_color

        else:
            color = error_color

        self.connection_label.config(
            fg=color
        )

    #Cập nhật thông báo
    def set_message(self, message):
        self.message_var.set(message)

    #Cập nhật hai trạng thái
    def update_status(
            self,
            connection_message,
            game_message,
            online= False
    ):

        self.set_connection(
            connection_message,
            online
        )

        self.set_message(
            game_message
        )

    #Khôi phục trạng thái ban đầu
    def restart_status(self):
        self.set_connection(
            "Chế độ Demo",
            online = False
        )

        self.set_message(
            "Sẵn sàng"
        )
