"""
TV3 - Room & Match
RoomManager: Quản lý nhiều phòng song song, thread-safe.
"""
from __future__ import annotations

import threading
import uuid
from typing import Dict, List, Optional

from .errors import (
    ALREADY_IN_ROOM,
    INVALID_ARGUMENT,
    INVALID_STATE,
    NOT_HOST,
    NOT_IN_ROOM,
    ROOM_FULL,
    ROOM_NOT_FOUND,
    SPECTATOR_FORBIDDEN,
    RoomError,
)
from .models import Role, Room, RoomStatus

MIN_TIME_LIMIT = 5      # giây/lượt
MAX_TIME_LIMIT = 600


class RoomManager:
    """Quản lý nhiều phòng song song; thread-safe vì server đa luồng."""

    def __init__(self) -> None:
        self._rooms: Dict[str, Room] = {}
        self._user_room: Dict[str, str] = {}   # username -> room_id
        self._lock = threading.RLock()

    # ---- helpers
    def _get(self, room_id: str) -> Room:
        if not isinstance(room_id, str) or not room_id:
            raise RoomError(INVALID_ARGUMENT, "room_id không hợp lệ")
        room = self._rooms.get(room_id)
        if room is None:
            raise RoomError(ROOM_NOT_FOUND, f"Không có phòng {room_id}")
        return room

    @staticmethod
    def _check_username(username: str) -> None:
        if not isinstance(username, str) or not username.strip():
            raise RoomError(INVALID_ARGUMENT, "username không hợp lệ")

    # ---- tạo / vào / rời
    def create_room(self, host: str, name: str = "", time_limit: int = 30) -> Room:
        self._check_username(host)
        if not isinstance(name, str):
            raise RoomError(INVALID_ARGUMENT, "name không hợp lệ")
        if (not isinstance(time_limit, int) or isinstance(time_limit, bool)
                or not MIN_TIME_LIMIT <= time_limit <= MAX_TIME_LIMIT):
            raise RoomError(
                INVALID_ARGUMENT,
                f"time_limit phải từ {MIN_TIME_LIMIT} đến {MAX_TIME_LIMIT} giây")
        with self._lock:
            if host in self._user_room:
                raise RoomError(ALREADY_IN_ROOM)
            # Check and reserve the ID under the same lock as room insertion.
            room_id = uuid.uuid4().hex[:6].upper()
            while room_id in self._rooms:
                room_id = uuid.uuid4().hex[:6].upper()
            room = Room(
                room_id=room_id,
                host=host,
                name=(name or "").strip() or f"Phòng của {host}",
                time_limit=time_limit,
            )
            room.players[Role.PLAYER_X] = host     # chủ phòng cầm X (có thể random)
            self._rooms[room.room_id] = room
            self._user_room[host] = room.room_id
            return room

    def join_as_player(self, room_id: str, username: str) -> Role:
        self._check_username(username)
        with self._lock:
            room = self._get(room_id)
            if username in self._user_room:
                raise RoomError(ALREADY_IN_ROOM)
            if room.status != RoomStatus.WAITING or room.is_full():
                raise RoomError(ROOM_FULL)
            # Gán vai còn trống (X nếu chủ phòng X đã rời, ngược lại O)
            # -> không bao giờ ghi đè người chơi đang có trong phòng.
            role = (Role.PLAYER_X if Role.PLAYER_X not in room.players
                    else Role.PLAYER_O)
            room.players[role] = username
            if room.is_full():
                room.status = RoomStatus.READY
            self._user_room[username] = room_id
            return role

    def join_as_spectator(self, room_id: str, username: str) -> Role:
        """Vào xem giữa trận cũng được; TV5 sẽ gửi full GameState sau đó."""
        self._check_username(username)
        with self._lock:
            room = self._get(room_id)
            if username in self._user_room:
                raise RoomError(ALREADY_IN_ROOM)
            room.spectators.append(username)
            self._user_room[username] = room_id
            return Role.SPECTATOR

    def leave_room(self, username: str) -> dict:
        """Gỡ thành viên, trả danh sách độc lập để tầng ứng dụng dọn và thông báo.

        Giữ các khóa kết quả cũ. removed_members gồm cả spectator bị đưa ra
        khi đóng phòng; remaining_members là thành viên sau thao tác.
        """
        self._check_username(username)
        with self._lock:
            return self._remove_member(username, allow_resign=True)

    def detach_disconnected_player(self, username: str) -> dict:
        """Gỡ người chơi offline sau khi kết quả đã được chốt, không tạo RESIGN.

        Tầng ứng dụng/TV2 phải xác nhận người này offline và TV5 đã kết thúc
        ván trước khi gọi. Chấp nhận WAITING để dọn người offline thứ hai sau
        lần detach đầu tiên; không gỡ chỗ reconnect trong PLAYING (kể cả PAUSED).
        """
        self._check_username(username)
        with self._lock:
            room_id = self._user_room.get(username)
            if room_id is None:
                raise RoomError(NOT_IN_ROOM)
            room = self._get(room_id)
            if room.role_of(username) not in (Role.PLAYER_X, Role.PLAYER_O):
                raise RoomError(SPECTATOR_FORBIDDEN)
            if room.status not in (RoomStatus.FINISHED, RoomStatus.WAITING):
                raise RoomError(INVALID_STATE, "Chỉ dọn người offline sau khi ván đã kết thúc")
            return self._remove_member(username, allow_resign=False)

    def _remove_member(self, username: str, *, allow_resign: bool) -> dict:
        """Thay đổi thành viên; bên gọi phải giữ self._lock."""
        room_id = self._user_room.get(username)
        if room_id is None:
            raise RoomError(NOT_IN_ROOM)
        room = self._get(room_id)
        role = room.role_of(username)
        members_before = room.members()
        removed_members = [username]
        aborted = allow_resign and role != Role.SPECTATOR and room.status == RoomStatus.PLAYING
        winner = None
        del self._user_room[username]

        if role == Role.SPECTATOR:
            room.spectators.remove(username)
        else:
            del room.players[role]
            if room.players:
                if aborted:
                    winner = next(iter(room.players.values()))
                room.status = RoomStatus.WAITING
                if room.host == username:
                    room.host = next(iter(room.players.values()))
            else:
                removed_members = members_before
                for member in removed_members:
                    self._user_room.pop(member, None)
                room.spectators.clear()
                room.status = RoomStatus.CLOSED
                del self._rooms[room_id]
        return {
            "room_id": room_id,
            "role": role,
            "match_aborted": aborted,
            "room_closed": room.status == RoomStatus.CLOSED,
            "winner": winner,
            "remaining_members": room.members(),
            "removed_members": removed_members,
        }

    # ---- vòng đời trận (TV4 gọi/được gọi qua các hàm này)
    def start_match(self, room_id: str, requester: str) -> Room:
        with self._lock:
            room = self._get(room_id)
            if requester != room.host:
                raise RoomError(NOT_HOST)
            if room.status != RoomStatus.READY:
                raise RoomError(INVALID_STATE, "Cần đủ 2 người chơi")
            room.status = RoomStatus.PLAYING
            return room

    def finish_match(self, room_id: str) -> Room:
        with self._lock:
            room = self._get(room_id)
            if room.status != RoomStatus.PLAYING:
                raise RoomError(INVALID_STATE)
            room.status = RoomStatus.FINISHED
            return room

    def rematch(self, room_id: str) -> Room:
        with self._lock:
            room = self._get(room_id)
            if room.status != RoomStatus.FINISHED or not room.is_full():
                raise RoomError(INVALID_STATE)
            # đổi quân X/O cho công bằng
            room.players[Role.PLAYER_X], room.players[Role.PLAYER_O] = (
                room.players[Role.PLAYER_O], room.players[Role.PLAYER_X])
            room.status = RoomStatus.READY
            return room

    # ---- truy vấn
    def get_room(self, room_id: str) -> Room:
        with self._lock:
            return self._get(room_id)

    def room_of(self, username: str) -> Optional[Room]:
        with self._lock:
            rid = self._user_room.get(username)
            return self._rooms.get(rid) if rid else None

    def list_rooms(self, only_playing: bool = False) -> List[dict]:
        """Room List; only_playing=True -> danh sách trận để khán giả vào xem."""
        with self._lock:
            rooms = self._rooms.values()
            if only_playing:
                rooms = [r for r in rooms if r.status == RoomStatus.PLAYING]
            return [r.to_summary() for r in rooms]

    def validate_move_permission(self, username: str, room_id: str) -> None:
        """Server gọi trước khi chuyển nước đi cho TV4 -> chặn khán giả."""
        with self._lock:
            room = self._get(room_id)
            if room.role_of(username) is None:
                raise RoomError(NOT_IN_ROOM)
            if not room.can_move(username):
                raise RoomError(SPECTATOR_FORBIDDEN)
            if room.status != RoomStatus.PLAYING:
                raise RoomError(INVALID_STATE)
