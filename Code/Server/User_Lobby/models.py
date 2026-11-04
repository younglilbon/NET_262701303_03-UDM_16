"""Shared player and invitation models for the TV2 phase-3 sources."""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class PlayerStatus(str, Enum):
    ONLINE = "ONLINE"
    INVITE_PENDING = "INVITE_PENDING"
    IN_ROOM = "IN_ROOM"
    OFFLINE = "OFFLINE"


@dataclass
class Player:
    name: str
    connection: Any | None
    status: PlayerStatus = PlayerStatus.ONLINE


@dataclass(frozen=True)
class Invitation:
    invite_id: str
    sender_key: str
    recipient_key: str
    sender_name: str
    recipient_name: str
