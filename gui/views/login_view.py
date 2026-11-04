import tkinter as tk
from tkinter import messagebox

from gui.style import (
    BG_COLOR,
    PRIMARY_COLOR,
    FONT_TITLE,
    FONT_NORMAL,
    FONT_SMALL,
)


class LoginView(tk.Frame):

    def __init__(self, parent, on_login):

        super().__init__(
            parent,
            bg=BG_COLOR
        )

        # Callback nhận thông tin đăng nhập từ CaroApp.
        self.on_login = on_login

        self.create_widgets()

    # TẠO GIAO DIỆN ĐĂNG NHẬP

    def create_widgets(self):
        """Tạo các thành phần giao diện đăng nhập."""

        # Tiêu đề.
        tk.Label(
            self,
            text="CARO ONLINE",
            font=FONT_TITLE,
            bg=BG_COLOR,
            fg=PRIMARY_COLOR,
        ).pack(pady=(100, 25))

        # Nhãn hướng dẫn.
        tk.Label(
            self,
            text="Nhập tên người chơi",
            font=FONT_NORMAL,
            bg=BG_COLOR,
            fg=PRIMARY_COLOR,
        ).pack(pady=5)

        # Ô nhập tên người chơi.
        self.username_entry = tk.Entry(
            self,
            width=30,
            font=FONT_NORMAL,
            justify="center",
            bg="white",
            fg="#222222",
            relief=tk.SOLID,
            bd=1,
        )

        self.username_entry.pack(
            pady=8,
            ipady=5
        )

        self.username_entry.focus_set()

        # Nút đăng nhập.
        self.login_button = tk.Button(
            self,
            text="Đăng nhập",
            command=self.login,
            bg=PRIMARY_COLOR,
            fg="white",
            activebackground="#1D4ED8",
            activeforeground="white",
            font=FONT_NORMAL,
            width=20,
            relief=tk.FLAT,
            cursor="hand2",
        )

        self.login_button.pack(
            pady=15,
            ipady=5
        )

        # Thông báo trạng thái demo.
        tk.Label(
            self,
            text="Phiên bản DEMO - Chưa kết nối Server",
            font=FONT_SMALL,
            bg=BG_COLOR,
            fg="#64748B",
        ).pack(pady=5)

        # Nhấn Enter để đăng nhập.
        self.username_entry.bind(
            "<Return>",
            self.handle_enter
        )

    # XỬ LÝ PHÍM ENTER

    def handle_enter(self, event):
        """Xử lý khi người chơi nhấn Enter."""

        self.login()

        return "break"

    # XỬ LÝ ĐĂNG NHẬP

    def login(self):
        """Kiểm tra tên và gọi callback đăng nhập."""

        # Lấy tên người chơi và loại bỏ khoảng trắng.
        username = self.username_entry.get().strip()

        # Kiểm tra tên trống.
        if not username:

            messagebox.showwarning(
                "Lỗi đăng nhập",
                "Vui lòng nhập tên người chơi.",
                parent=self
            )

            self.username_entry.focus_set()

            return

        # Kiểm tra callback.
        if not callable(self.on_login):

            messagebox.showerror(
                "Lỗi hệ thống",
                "Không thể thực hiện đăng nhập."
            )

            return

        # Chuyển thông tin về CaroApp xử lý.
        self.on_login(username)
