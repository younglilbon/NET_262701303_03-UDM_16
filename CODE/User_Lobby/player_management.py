"""Player identity, availability, and connection management."""

import threading
from typing import Any

from .models import Player, PlayerStatus


class PlayerManager:
    MIN_NAME_LENGTH = 3
    MAX_NAME_LENGTH = 20

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self._players_by_key: dict[str, Player] = {}
        self._players_by_connection: dict[Any, Player] = {}

    @classmethod
    def is_valid_name(cls, name: object) -> bool:
        if not isinstance(name, str):
            return False
        cleaned = name.strip()
        return (
            cls.MIN_NAME_LENGTH <= len(cleaned) <= cls.MAX_NAME_LENGTH
            and cleaned[0].isalnum()
            and cleaned[-1].isalnum()
            and all(character.isalnum() or character in "_-" for character in cleaned)
        )

    def login(
        self,
        connection: Any,
        requested_name: object,
    ) -> tuple[Player | None, str | None]:
        if not self.is_valid_name(requested_name):
            return None, "Name must be 3-20 characters and start/end with a letter or digit"

        name = requested_name.strip()
        name_key = name.casefold()
        with self.lock:
            if connection in self._players_by_connection:
                return None, "This connection already has an identity"

            player = self._players_by_key.get(name_key)
            if player is not None and player.connection is not None:
                return None, "That player name is already online"
            if player is None:
                player = Player(
                    name=name,
                    connection=connection,
                )
                self._players_by_key[name_key] = player
            else:
                player.connection = connection
                player.status = PlayerStatus.ONLINE

            self._players_by_connection[connection] = player
            return player, None

    def get_player(self, connection: Any) -> Player | None:
        with self.lock:
            return self._players_by_connection.get(connection)

    def get_players(self) -> list[Player]:
        with self.lock:
            return list(self._players_by_key.values())

    def get_online_players(self) -> list[str]:
        with self.lock:
            return sorted(
                (
                    player.name
                    for player in self._players_by_key.values()
                    if player.connection is not None
                ),
                key=str.casefold,
            )

    def set_status(
        self,
        connection: Any,
        expected: PlayerStatus,
        new_status: PlayerStatus,
    ) -> bool:
        with self.lock:
            player = self._players_by_connection.get(connection)
            if player is None or player.status is not expected:
                return False
            player.status = new_status
            return True

    def disconnect(self, connection: Any) -> Player | None:
        with self.lock:
            player = self._players_by_connection.pop(connection, None)
            if player is None:
                return None
            player.connection = None
            if player.status is not PlayerStatus.IN_ROOM:
                player.status = PlayerStatus.OFFLINE
            return player

    def logout(self, connection: Any) -> bool:
        with self.lock:
            player = self._players_by_connection.pop(connection, None)
            if player is None:
                return False
            self._players_by_key.pop(player.name.casefold(), None)
            player.connection = None
            return True
