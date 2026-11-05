"""Login and logout request handling for the server lobby."""

from collections.abc import Callable
from typing import Any

from .online_list import OnlineList
from .player_management import PlayerManager

SendMessage = Callable[[Any, dict[str, Any]], None]


class LoginService:
    def __init__(
        self,
        players: PlayerManager,
        online_list: OnlineList,
        send_message: SendMessage,
    ) -> None:
        self._players = players
        self._online_list = online_list
        self._send_message = send_message

    def handle_login(
        self,
        connection: Any,
        name: object,
    ) -> bool:
        player, error = self._players.login(connection, name)
        if error is not None:
            self._send_message(
                connection,
                {"type": "ERROR", "message": error},
            )
            return False
        self._send_message(
            connection,
            {"type": "LOGIN_RESULT", "status": "OK", "name": player.name},
        )
        self._online_list.broadcast()
        return player is not None

    def handle_logout(self, connection: Any) -> bool:
        if not self._players.logout(connection):
            self._send_message(
                connection,
                {"type": "ERROR", "message": "Login is required"},
            )
            return False
        self._online_list.broadcast()
        return True
