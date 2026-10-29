"""
TV3 - Room & Match
Package quản lý phòng đấu Caro.

Cách dùng:
    from Server.room import RoomManager, RoomError, Room, RoomStatus, Role
"""
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
from .manager import RoomManager
from .models import Role, Room, RoomStatus

__all__ = [
    "RoomManager",
    "Room",
    "RoomError",
    "RoomStatus",
    "Role",
    "ROOM_NOT_FOUND",
    "ROOM_FULL",
    "ALREADY_IN_ROOM",
    "NOT_IN_ROOM",
    "NOT_HOST",
    "INVALID_ARGUMENT",
    "INVALID_STATE",
    "SPECTATOR_FORBIDDEN",
]