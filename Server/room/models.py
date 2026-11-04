"""
TV3 - Room & Match
Mô hình dữ liệu Room, RoomStatus, Role.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------- Enum
class RoomStatus(str, Enum):
    WAITING = "WAITING"      # có chủ phòng, chờ đối thủ
    READY = "READY"          # đủ 2 người, chưa bắt đầu
    PLAYING = "PLAYING"      # đang đấu
    FINISHED = "FINISHED"    # kết thúc (thắng/thua/hòa)
    CLOSED = "CLOSED"        # đã đóng, sẽ bị xóa


class Role(str, Enum):
    PLAYER_X = "X"
    PLAYER_O = "O"
    SPECTATOR = "SPECTATOR"


# ---------------------------------------------------------------- Model
@dataclass
class Room:
    room_id: str
    host: str                                  # username chủ phòng
    name: str = ""
    status: RoomStatus = RoomStatus.WAITING
    players: Dict[Role, str] = field(default_factory=dict)   # {X: "an", O: "binh"}
    spectators: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    time_limit: int = 30                       # giây/lượt, TV4 dùng

    # ---- truy vấn
    def role_of(self, username: str) -> Optional[Role]:
        for role, name in self.players.items():
            if name == username:
                return role
        if username in self.spectators:
            return Role.SPECTATOR
        return None

    def is_full(self) -> bool:
        return Role.PLAYER_X in self.players and Role.PLAYER_O in self.players

    def members(self) -> List[str]:
        """Tất cả người trong phòng - TV5 dùng để broadcast."""
        return list(self.players.values()) + list(self.spectators)

    def can_move(self, username: str) -> bool:
        """Khán giả KHÔNG được đánh (yêu cầu đề bài)."""
        return self.role_of(username) in (Role.PLAYER_X, Role.PLAYER_O)

    # ---- chuyển sang dict/JSON để gửi qua mạng
    def to_summary(self) -> dict:
        """Dùng cho danh sách phòng (Room List)."""
        return {
            "room_id": self.room_id,
            "name": self.name,
            "host": self.host,
            "status": self.status.value,
            "players": {r.value: n for r, n in self.players.items()},
            "spectator_count": len(self.spectators),
        }

    def to_dict(self) -> dict:
        d = self.to_summary()
        d["spectators"] = list(self.spectators)
        d["time_limit"] = self.time_limit
        return d