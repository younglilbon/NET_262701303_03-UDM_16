import tkinter as tk

from .style import (
    bg_color,
    primary_color,
    border_color,
    secondary_color,
    font_normal,
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
            fg=warning_color,
            bg=bg_color,
            anchor="w"
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
    def set_connection(self, message, online=True):
        self.connection_var.set(message)

        if online:
            color = success_color

        elif message in (
            "Chế độ Demo",
            "Đang kết nối",
        ) or message.startswith("Đang kết nối"):
            color = warning_color

        elif message in (
            "Ngoại tuyến",
            "Mất kết nối",
            "Kết nối thất bại",
        ):
            color = error_color

        else:
            color = primary_color


        self.connection_label.config(fg=color)

    def set_connected(self, message = "Đã kết nối"):
        self.set_connection(message, online = True)

    def set_disconnected(self, message = "Mất kết nối"):
        """Hiển thị trạng thái mất kết nối"""
        self.set_disconnection(message, online = False)

    def set_demo(self):
        """Hiển thị trạng thái chạy Demo"""
        self.set_connection("Chế độ Demo", online = False)


    #Cập nhật thông báo
    def set_message(self, message, message_type="info"):
        colors = {
            "info": primary_color,
            "success": success_color,
            "warning": warning_color,
            "error": error_color
        }

        color = colors.get(message_type, primary_color)

        self.message_var.set(str(message))
        self.message_label.config(fg=color)

    def set_processing(self, message = "Đang xử lý"):
        """Hiển thị trạng thái đang xử lý"""
        self.set_message(message, "warning")

    def set_success(self, message = "Thao tác thành công"):
        """Hiển thị thông báo thành công"""
        self.set_message(message, "success")

    def set_error(self, message = "Đã xảy ra lỗi"):
        """Hiển thị thông báo lỗi"""
        self.set_message(message, "error")

    #Cập nhật hai trạng thái
    def update_status(
            self,
            connection_message,
            game_message,
            online= False,
            message_type="info"
    ):
        """Cập nhật trạng thái kết nối và thông báo"""

        self.set_connection(
            connection_message,
            online
        )

        self.set_message(
            game_message,
            message_type
        )

    #Khôi phục trạng thái 
    def restart_status(self):
        self.set_connection()
        self.set_message("Sẵn sàng", "info")
