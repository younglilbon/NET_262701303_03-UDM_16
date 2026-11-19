"""Online-player list messages and broadcasting."""

from collections.abc import Callable
from typing import Any

from .player_management import PlayerManager

SendMessage = Callable[[Any, dict[str, Any]], None]


class OnlineList:
    def __init__(self, players: PlayerManager, send_message: SendMessage) -> None:
        self._players = players
        self._send_message = send_message

    def message_for(self) -> dict[str, Any]:
        return {
            "type": "PLAYER_LIST",
            "players": self._players.get_online_players(),
        }

    def broadcast(self) -> None:
        for player in self._players.get_players():
            if player.connection is not None:
                self._send_message(player.connection, self.message_for())
