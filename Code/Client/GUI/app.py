"""Tkinter client for the Caro TCP server."""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from ..Network.client_sync import ClientStateSync
from ..Network.tcp_client import TCPClient
from .status_bar import StatusBar
from .style import bg_color, window_height, window_width
from .board_widget import BoardWidget 



class CaroApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Caro trực tuyến")
        self.root.geometry(f"{window_width}x{window_height}")
        self.root.configure(bg=bg_color)
        self.client = TCPClient(self._receive_message)
        self.username = ""
        self.room_id: str | None = None
        self.rooms: list[dict] = []
        self.sync = ClientStateSync("", ui_callback=self._sync_event)
        self.current_view: tk.Widget | None = None
        self.status_bar = StatusBar(root)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.show_login_view()

    def show_login_view(self) -> None:
        frame = ttk.Frame(self.root, padding=24)
        ttk.Label(frame, text="Đăng nhập Caro", font=("Segoe UI", 20, "bold")).pack(pady=12)
        self.host_entry = self._labeled_entry(frame, "Địa chỉ server", "127.0.0.1")
        self.port_entry = self._labeled_entry(frame, "Cổng", "8888")
        self.name_entry = self._labeled_entry(frame, "Tên người chơi", "")
        ttk.Button(frame, text="Kết nối", command=self.login).pack(pady=14)
        self._show(frame)

    @staticmethod
    def _labeled_entry(parent: ttk.Frame, label: str, initial: str) -> ttk.Entry:
        ttk.Label(parent, text=label).pack(anchor=tk.W, pady=(8, 2))
        entry = ttk.Entry(parent, width=36)
        entry.insert(0, initial)
        entry.pack(fill=tk.X)
        return entry

    def login(self) -> None:
        try:
            host = self.host_entry.get().strip()
            port = int(self.port_entry.get())
            self.username = self.name_entry.get().strip()
            if not host or not 1 <= port <= 65535:
                raise ValueError("Địa chỉ hoặc cổng server không hợp lệ.")
            self.client.connect(host, port)
            self.sync.username = self.username
            self.client.send({"type": "LOGIN", "name": self.username})
            self.status_bar.set_connection(f"Đang kết nối {host}:{port}")
        except (OSError, ValueError, RuntimeError) as error:
            messagebox.showerror("Không thể kết nối", str(error))
            self.status_bar.set_connection("Ngoại tuyến")

    def show_lobby_view(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        ttk.Label(frame, text=f"Xin chào, {self.username}", font=("Segoe UI", 16, "bold")).pack(anchor=tk.W)

        lists = ttk.Frame(frame)
        lists.pack(fill=tk.BOTH, expand=True, pady=10)
        players_frame = ttk.Frame(lists)
        players_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        rooms_frame = ttk.Frame(lists)
        rooms_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))

        ttk.Label(players_frame, text="Người chơi trực tuyến").pack(anchor=tk.W)
        self.player_list = tk.Listbox(players_frame, height=15)
        self.player_list.pack(fill=tk.BOTH, expand=True)
        ttk.Button(players_frame, text="Mời đấu", command=self.invite_player).pack(anchor=tk.W, pady=6)

        ttk.Label(rooms_frame, text="Phòng").pack(anchor=tk.W)
        self.room_list = tk.Listbox(rooms_frame, height=15)
        self.room_list.pack(fill=tk.BOTH, expand=True)
        room_buttons = ttk.Frame(rooms_frame)
        room_buttons.pack(fill=tk.X, pady=6)
        ttk.Button(room_buttons, text="Làm mới", command=self.list_rooms).pack(side=tk.LEFT)
        ttk.Button(room_buttons, text="Tạo phòng", command=self.create_room).pack(side=tk.LEFT, padx=4)
        ttk.Button(room_buttons, text="Vào chơi", command=lambda: self.join_room(False)).pack(side=tk.LEFT)
        ttk.Button(room_buttons, text="Xem", command=lambda: self.join_room(True)).pack(side=tk.LEFT, padx=4)

        self._show(frame)
        self.client.send({"type": "PLAYER_LIST"})
        self.list_rooms()

    def show_room_view(self, room: dict | None = None) -> None:
        frame = ttk.Frame(self.root, padding=20)
        room = room or {}
        self.room_id = room.get("room_id", self.room_id)
        ttk.Label(
            frame,
            text=f"Phòng {self.room_id or ''} — {room.get('status', 'WAITING')}",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=14)
        players = room.get("player", {})
        if isinstance(players, dict):
            players_text="\n".join(f"{name}: {role}" for name, role in players.item())
        else:
            players_text="\n".join(str(p) for p in players)
        ttk.Label(
            frame, 
            text=players_text or "Chưa có người chơi",
            justify=tk.CENTER,
        ).pack(pady=6)
        ttk.Button(
            frame, text="Bắt đầu trận",
            command=lambda: self.client.send({
                "type": "START_MATCH", "room_id": self.room_id
            }),
        ).pack(pady=6)
        ttk.Button(frame, text="Rời phòng", command=self.leave_room).pack(pady=6)
        self._show(frame)

    def show_game_view(self) -> None:
        frame = ttk.Frame(self.root, padding=8)
        self.turn_label = ttk.Label(frame, text="", font=("Segoe UI", 14, "bold"))
        self.turn_label.pack(pady=6)
        board_frame = ttk.Frame(frame)
        board_frame.pack(expand=True)
        self.board_widget = BoardWidget(
            board_frame,
            on_move=self.make_move
        )
        self.board_widget.pack(
            padx=10,
            pady=10
        )
        ttk.Button(
            frame,
            text="Rời phòng",
            command=self.leave_room
        ).pack(pady=6)
        self._show(frame)
        self._render_board()

    def make_move(self, row: int, col: int) -> None:
        allowed, reason = self.sync.can_make_move()
        if not allowed:
            self.status_bar.set_message(reason)
            return
        self.client.send({
            "type": "MOVE",
            "row": row,
            "col": col,
        })

    def create_room(self) -> None:
        name = simpledialog.askstring("Tạo phòng", "Tên phòng:", parent=self.root) or ""
        self.client.send({"type": "CREATE_ROOM", "name": name, "time_limit": 30})

    def join_room(self, spectator: bool) -> None:
        selection = self.room_list.curselection()
        if not selection:
            messagebox.showinfo("Chọn phòng", "Hãy chọn một phòng trước.")
            return
        room = self.rooms[selection[0]]
        message_type = "JOIN_AS_SPECTATOR" if spectator else "JOIN_ROOM"
        self.client.send({"type": message_type, "room_id": room["room_id"]})

    def invite_player(self) -> None:
        selection = self.player_list.curselection()
        if not selection:
            messagebox.showinfo("Chọn người chơi", "Hãy chọn người chơi cần mời.")
            return
        self.client.send({
            "type": "INVITE",
            "target": self.player_list.get(selection[0]),
        })

    def leave_room(self) -> None:
        self.client.send({"type": "LEAVE_ROOM"})
        self.room_id = None
        self.show_lobby_view()

    def list_rooms(self) -> None:
        self.client.send({"type": "LIST_ROOMS"})

    def _receive_message(self, message: dict) -> None:
        self.root.after(0, self._handle_message, message)

    def _handle_message(self, message: dict) -> None:
        message_type = message.get("type")
        if message_type == "LOGIN_RESULT":
            self.status_bar.set_connection("Đã kết nối", online=True)
            self.show_lobby_view()
        elif message_type == "PLAYER_LIST":
            if hasattr(self, "player_list"):
                self.player_list.delete(0, tk.END)
                for name in message.get("players", []):
                    if name != self.username:
                        self.player_list.insert(tk.END, name)
        elif message_type == "ROOM_LIST":
            self.rooms = message.get("rooms", [])
            if hasattr(self, "room_list"):
                self.room_list.delete(0, tk.END)
                for room in self.rooms:
                    self.room_list.insert(
                        tk.END,
                        f'{room["room_id"]} — {room["name"]} [{room["status"]}]',
                    )
        elif message_type == "ROOM_UPDATED":
            room = message.get("room")
            if not room or room.get("room_id") != self.room_id:
                return
            self.room_info = room
            # Membership updates must not replace an active/finished board
            # with the waiting-room view (e.g. when a spectator leaves).
            if (room.get("status") in ("PLAYING", "FINISHED")
                    and self.sync.room_id == self.room_id and self.sync.board):
                return
            self.show_room_view(room)
        elif message_type in ("ROOM_CREATED", "ROOM_JOINED"):
            room = message.get("room")
            if room:
                self.room_id = room.get("room_id", self.room_id)
                self.show_room_view(room)
        elif message_type == "ROOM_STARTED":
            self.room_id = message.get("room_id", self.room_id)
            self.show_game_view()
        elif message_type == "SYNC_FULL_STATE":
            self.sync.handle_server_message(message)
            self.room_id = message.get("room_id", self.room_id)
            self.show_game_view()
        elif message_type in (
            "SYNC_MOVE", "SPECTATOR_JOINED", "SPECTATOR_LEFT",
            "PLAYER_DISCONNECTED", "PLAYER_RECONNECTED", "MATCH_FINISHED",
        ):
            self.sync.handle_server_message(message)
        elif message_type == "INVITE":
            accepted = messagebox.askyesno(
                "Lời mời đấu", f'{message.get("from")} mời bạn đấu. Chấp nhận?'
            )
            self.client.send({
                "type": "INVITE_RESPONSE",
                "invite_id": message.get("invite_id"),
                "accepted": accepted,
            })
        elif message_type == "ROOM_LEFT":
            self.list_rooms()
        elif message_type in ("ERROR", "CONNECTION_ERROR"):
            self.status_bar.set_message(message.get("message", "Lỗi kết nối"))
            if message_type == "CONNECTION_ERROR":
                self.status_bar.set_connection("Mất kết nối")
            else:
                messagebox.showerror("Lỗi", message.get("message", "Yêu cầu thất bại"))

    def _sync_event(self, event_type: str, data: dict) -> None:
        self.root.after(0, self._show_sync_event, event_type, data)

    def _show_sync_event(self, event_type: str, data: dict) -> None:
        if event_type == "MOVE_UPDATED":
            self._render_board()
        elif event_type == "MATCH_OVER":
            messagebox.showinfo("Kết thúc trận", f"Kết quả: {data.get('winner')}")
        elif event_type == "MATCH_PAUSED":
            self.status_bar.set_message("Đối thủ mất kết nối; đang chờ kết nối lại.")
        elif event_type == "MATCH_RESUMED":
            self.status_bar.set_message("Trận đấu tiếp tục.")
        elif event_type == "SYNC_ERROR":
            self.status_bar.set_message(data.get("message", "Lỗi đồng bộ"))

    def _render_board(self) -> None:
        if not hasattr(self, "board_widget") or not self.board_widget.winfo_exists():
            return
        if self.sync.board:
            try:
                self.board_widget.render_board(self.sync.board)
            except ValueError as error:
                self.status_bar.set_message(str(error))
        self.turn_label.configure(
            text=f"Vai: {self.sync.role} | Lượt: {self.sync.current_turn}"
                f"| Còn: {self.sync.remaining_time}s | Trạng thái: {self.sync.status}"
        )

    def _show(self, view: tk.Widget) -> None:
        if self.current_view is not None:
            self.current_view.destroy()
        self.current_view = view
        view.pack(fill=tk.BOTH, expand=True)

    def close(self) -> None:
        try:
            self.client.close()
        except OSError:
            pass
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    CaroApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
