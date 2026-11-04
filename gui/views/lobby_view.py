import tkinter as tk
from tkinter import messagebox

from gui.style import (
    BG_COLOR,
    PRIMARY_COLOR,
    SECONDARY_COLOR,
    FONT_TITLE,
    FONT_SUBTITLE,
    FONT_NORMAL,
)


class LobbyView(tk.Frame):

    def __init__(
        self,
        parent,
        username,
        on_create_room,
        on_join_room,
        on_logout
    ):

        super().__init__(
            parent,
            bg=BG_COLOR
        )

        # Lưu thông tin người chơi và callback.
        self.username = username
        self.on_create_room = on_create_room
        self.on_join_room = on_join_room
        self.on_logout = on_logout

        # TIÊU ĐỀ SẢNH CHỜ

        tk.Label(
            self,
            text="SẢNH CHỜ",
            font=FONT_TITLE,
            fg=PRIMARY_COLOR,
            bg=BG_COLOR,
        ).pack(pady=20)

        # THÔNG TIN NGƯỜI CHƠI

        tk.Label(
            self,
            text=f"Xin chào, {username}",
            font=FONT_NORMAL,
            bg=BG_COLOR,
        ).pack(pady=5)

        tk.Label(
            self,
            text="Chọn phòng để tham gia hoặc tạo phòng mới",
            font=FONT_NORMAL,
            bg=BG_COLOR,
        ).pack(pady=5)

        # DANH SÁCH PHÒNG

        tk.Label(
            self,
            text="DANH SÁCH PHÒNG",
            font=FONT_SUBTITLE,
            fg=PRIMARY_COLOR,
            bg=BG_COLOR,
        ).pack(pady=10)

        list_frame = tk.Frame(
            self,
            bg=BG_COLOR
        )

        list_frame.pack(pady=5)

        self.room_list = tk.Listbox(
            list_frame,
            width=48,
            height=8,
            font=FONT_NORMAL,
            bg="white",
            fg=PRIMARY_COLOR,
            selectbackground=PRIMARY_COLOR,
            selectforeground="white",
            activestyle="none",
            relief=tk.SOLID,
            bd=1,
        )

        self.room_list.pack(
            side=tk.LEFT,
            fill=tk.BOTH
        )

        # Thanh cuộn danh sách phòng.
        scrollbar = tk.Scrollbar(
            list_frame,
            orient=tk.VERTICAL,
            command=self.room_list.yview
        )

        scrollbar.pack(
            side=tk.RIGHT,
            fill=tk.Y
        )

        self.room_list.config(
            yscrollcommand=scrollbar.set
        )

        # Dữ liệu demo, chưa lấy từ Server.
        self.room_list.insert(
            tk.END,
            "ROOM-001 | Phòng demo"
        )

        # CÁC NÚT CHỨC NĂNG

        buttons = tk.Frame(
            self,
            bg=BG_COLOR
        )

        buttons.pack(pady=20)

        # Nút tạo phòng.
        tk.Button(
            buttons,
            text="Tạo phòng",
            font=FONT_NORMAL,
            bg=PRIMARY_COLOR,
            fg="white",
            activebackground="#0D2C63",
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.create_room,
        ).pack(
            side=tk.LEFT,
            padx=5,
            ipadx=10,
            ipady=5
        )

        # Nút tham gia phòng.
        tk.Button(
            buttons,
            text="Tham gia phòng",
            font=FONT_NORMAL,
            bg=SECONDARY_COLOR,
            fg=PRIMARY_COLOR,
            relief=tk.FLAT,
            cursor="hand2",
            command=self.join_room,
        ).pack(
            side=tk.LEFT,
            padx=5,
            ipadx=10,
            ipady=5
        )

        # Nút đăng xuất.
        tk.Button(
            buttons,
            text="Đăng xuất",
            font=FONT_NORMAL,
            bg="#E0E0E0",
            fg="#222222",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.logout,
        ).pack(
            side=tk.LEFT,
            padx=5,
            ipadx=10,
            ipady=5
        )

    # CHỨC NĂNG TẠO PHÒNG

    def create_room(self):

        if self.on_create_room:
            self.on_create_room()

    # CHỨC NĂNG THAM GIA PHÒNG

    def join_room(self):

        # Kiểm tra người chơi đã chọn phòng chưa.
        if not self.room_list.curselection():

            messagebox.showwarning(
                "Chưa chọn phòng",
                "Vui lòng chọn phòng muốn tham gia."
            )

            return

        if self.on_join_room:
            self.on_join_room()

    # CHỨC NĂNG ĐĂNG XUẤT

    def logout(self):

        should_logout = messagebox.askyesno(
            "Đăng xuất",
            "Bạn có muốn đăng xuất khỏi trò chơi không?"
        )

        if should_logout and self.on_logout:
            self.on_logout()
