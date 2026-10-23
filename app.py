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
        self.root.geometry(f"{window_width}x{window_height}")
        self.root.configure(bg=bg_color)
        self.username = ""
        self.room_id = "ROOM-001"
        self.current_view = None
        self.show_login_view()

    def show_views(self, view_class, *args):
        if self.current_view is not None:
            self.current_view.destroy()

        self.current_view = view_class(
            self.root, *args
        )
        self.current_view.pack(
            fill=tk.BOTH,
        )