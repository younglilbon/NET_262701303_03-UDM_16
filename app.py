import tkinter as tk

from gui.style import (
    bg_color,
    window_width,
    window_height,
)

from gui.views.login_view import LoginView
from gui.views.lobby_view import LobbyView
from gui.views.game_view import GameView
from gui.views.room_view import RoomView


class CaroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Caro Game")
        self.root.geometry(
            f"{window_width}x{window_height}"
        )
        self.root.minsize(700, 550)
        self.root.configure(bg=bg_color)

        # Thông tin người chơi
        self.username = ""

        # Thông tin phòng hiện tại
        self.room_id = ""

        # Lưu màn hình đang hiển thị
        self.current_view = None

        # Hiển thị màn hình đăng nhập đầu tiên
        self.show_login_view()

    # HÀM CHUYỂN ĐỔI GIỮA CÁC MÀN HÌNH

    def show_views(self, view_class, *args):
        """
        Xóa màn hình cũ và hiển thị màn hình mới.
        """

        if self.current_view is not None:
            self.current_view.destroy()

        self.current_view = view_class(
            self.root, *args
        )

        self.current_view.pack(
            fill=tk.BOTH,
            expand=True
        )

    # MÀN HÌNH ĐĂNG NHẬP

    def show_login_view(self):
        self.show_views(
            LoginView,
            self.handle_login
        )

    def handle_login(self, username):
       username = username.strip()

       if not username:
           return

       self.username = username
       self.show_lobby_view()

    # MÀN HÌNH SẢNH CHỜ

    def show_lobby_view(self):
        self.show_views(
            LobbyView,
            self.username,
            self.handle_create_room,
            self.handle_join_room,
            self.handle_logout
        )

    def handle_create_room(self):
        """
        Xử lý khi người chơi tạo phòng.
        """

        self.room_id = "ROOM-001"
        self.show_room_view()

    def handle_join_room(self):
        """
        Xử lý khi người chơi tham gia phòng.
        """

        self.room_id = "ROOM-001"
        self.show_room_view()

    def handle_logout(self):
        """
        Xử lý đăng xuất.
        """

        self.username = ""
        self.room_id = ""
        self.show_login_view()

    # MÀN HÌNH PHÒNG CHỜ

    def show_room_view(self):
        self.show_views(
            RoomView,
            self.username,
            self.room_id,
            self.show_game_view,
            self.show_lobby_view
        )

    # MÀN HÌNH GAME CARO

    def show_game_view(self):
        self.show_views(
            GameView,
            self.username,
            self.room_id,
            self.handle_leave_game
        )

    def handle_leave_game(self):
        """
        Khi người chơi rời khỏi bàn cờ,
        quay lại sảnh chờ.
        """

        self.show_lobby_view()


# CHƯƠNG TRÌNH CHÍNH

if __name__ == "__main__":
    root = tk.Tk()

    app = CaroApp(root)

    root.mainloop()
