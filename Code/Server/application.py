"""Application service that connects the network, lobby, rooms, and matches."""

from typing import Any, Callable

from .Room_Match.errors import RoomError
from .Room_Match.manager import RoomManager
from .Room_Match.models import Role, RoomStatus
from .Synchronization.sync_manager import SyncManager
from .User_Lobby.invitation import InvitationManager
from .User_Lobby.login import LoginService
from .User_Lobby.models import PlayerStatus
from .User_Lobby.online_list import OnlineList
from .User_Lobby.player_management import PlayerManager

SendMessage = Callable[[Any, dict[str, Any]], None]


class ServerApplication:
    """Dispatch the single JSON message format used by all server modules."""

    def __init__(self, send_message: SendMessage) -> None:
        self._send_message = send_message
        self.players = PlayerManager()
        self.online_list = OnlineList(self.players, send_message)
        self.login = LoginService(self.players, self.online_list, send_message)
        self.rooms = RoomManager()
        self.sync = SyncManager(
            send_callback=send_message,
            on_match_finished=self._match_finished,
        )
        self.invitations = InvitationManager(
            self.players, send_message, on_accept=self._start_invited_match
        )

    def handle_message(self, connection: Any, message: object) -> None:
        if not isinstance(message, dict) or not isinstance(message.get("type"), str):
            self._send_message(connection, {
                "type": "ERROR",
                "code": "INVALID_MESSAGE",
                "message": "Message must be a JSON object with a string 'type'.",
            })
            return

        message_type = message["type"]
        if message_type == "LOGIN":
            self._handle_login(connection, message)
            return

        player = self.players.get_player(connection)
        if player is None:
            self._send_message(connection, {
                "type": "ERROR",
                "code": "LOGIN_REQUIRED",
                "message": "Login is required.",
            })
            return

        try:
            self._dispatch_authenticated(connection, player.name, message_type, message)
        except RoomError as error:
            self._send_message(connection, {
                "type": "ERROR",
                "code": error.code,
                "message": str(error),
            })
        except (TypeError, ValueError, AttributeError) as error:
            self._send_message(connection, {
                "type": "ERROR",
                "code": "INVALID_ARGUMENT",
                "message": str(error),
            })

    def _handle_login(self, connection: Any, message: dict[str, Any]) -> None:
        if not self.login.handle_login(connection, message.get("name")):
            return
        player = self.players.get_player(connection)
        if player is None:
            return
        self.sync.register_connection(player.name, connection)
        reconnected, _ = self.sync.handle_reconnect(player.name, connection)
        if reconnected:
            self._set_player_status(player.name, PlayerStatus.IN_ROOM)

    def _dispatch_authenticated(
        self,
        connection: Any,
        username: str,
        message_type: str,
        message: dict[str, Any],
    ) -> None:
        if message_type == "LOGOUT":
            self._logout(connection, username)
        elif message_type == "PLAYER_LIST":
            self._send_message(connection, self.online_list.message_for())
        elif message_type == "INVITE":
            self.invitations.invite(connection, message.get("target"))
        elif message_type == "INVITE_RESPONSE":
            self.invitations.respond(
                connection,
                message.get("invite_id"),
                message.get("accepted") is True,
            )
        elif message_type == "CREATE_ROOM":
            room = self.rooms.create_room(
                username,
                name=message.get("name", ""),
                time_limit=message.get("time_limit", 30),
            )
            self._set_player_status(username, PlayerStatus.IN_ROOM)
            self._send_message(connection, {
                "type": "ROOM_CREATED",
                "room": room.to_dict(),
            })
        elif message_type == "JOIN_ROOM":
            role = self.rooms.join_as_player(message.get("room_id"), username)
            room = self.rooms.room_of(username)
            self._set_player_status(username, PlayerStatus.IN_ROOM)
            self._send_room_update(room, "ROOM_UPDATED")
            self._send_message(connection, {
                "type": "ROOM_JOINED",
                "role": role.value,
                "room": room.to_dict(),
            })
        elif message_type == "JOIN_AS_SPECTATOR":
            role = self.rooms.join_as_spectator(message.get("room_id"), username)
            room = self.rooms.room_of(username)
            self._set_player_status(username, PlayerStatus.IN_ROOM)
            state = self.sync.rooms.get(room.room_id)
            if state is not None and state.status == "PLAYING":
                self.sync.sync_spectator_join(room.room_id, username)
            else:
                self._send_message(connection, {
                    "type": "ROOM_JOINED",
                    "role": role.value,
                    "room": room.to_dict(),
                })
        elif message_type == "LIST_ROOMS":
            self._send_message(connection, {
                "type": "ROOM_LIST",
                "rooms": self.rooms.list_rooms(
                    only_playing=message.get("only_playing") is True
                ),
            })
        elif message_type == "START_MATCH":
            room = self.rooms.start_match(message.get("room_id"), username)
            self._start_match(room)
        elif message_type == "MOVE":
            room = self.rooms.room_of(username)
            if room is None:
                raise RoomError("NOT_IN_ROOM", "Player is not in a room.")
            self.rooms.validate_move_permission(username, room.room_id)
            self.sync.sync_move(
                room.room_id, username, message.get("row"), message.get("col")
            )
        elif message_type == "LEAVE_ROOM":
            self._leave_room(username)
        else:
            self._send_message(connection, {
                "type": "ERROR",
                "code": "UNKNOWN_MESSAGE",
                "message": f"Unknown message type: {message_type}",
            })

    def _start_invited_match(self, sender: str, recipient: str) -> None:
        room = self.rooms.create_room(sender)
        self.rooms.join_as_player(room.room_id, recipient)
        room = self.rooms.start_match(room.room_id, sender)
        self._set_player_status(sender, PlayerStatus.IN_ROOM)
        self._set_player_status(recipient, PlayerStatus.IN_ROOM)
        self._start_match(room)

    def _start_match(self, room) -> None:
        self.sync.create_or_init_match(
            room.room_id,
            room.players[Role.PLAYER_X],
            room.players[Role.PLAYER_O],
            board_size=15,
            turn_timeout=room.time_limit,
            spectators=room.spectators,
        )
        for username in room.members():
            connection = self.sync.user_connections.get(username)
            if connection is not None:
                self._send_message(
                    connection,
                    {"type": "ROOM_STARTED", "room_id": room.room_id},
                )

    def _match_finished(self, room_id: str, winner: str, reason: str) -> None:
        try:
            room = self.rooms.get_room(room_id)
        except RoomError:
            return
        if room.status == RoomStatus.PLAYING:
            self.rooms.finish_match(room_id)

    def _leave_room(self, username: str) -> None:
        room = self.rooms.room_of(username)
        if room is None:
            raise RoomError("NOT_IN_ROOM", "Player is not in a room.")
        state = self.sync.rooms.get(room.room_id)
        leave_info = self.rooms.leave_room(username)
        if leave_info["role"] == Role.SPECTATOR:
            self.sync.sync_spectator_leave(room.room_id, username)
        elif leave_info["match_aborted"] and state is not None:
            winner_name = leave_info["winner"]
            winner_symbol = next(
                (
                    symbol
                    for symbol, player_name in state.players.items()
                    if player_name == winner_name
                ),
                None,
            )
            self.sync.finish_and_save_match(
                room.room_id, winner_symbol, reason="RESIGN"
            )
        self._set_player_status(username, PlayerStatus.ONLINE)
        self._send_message(
            self._connection_for(username),
            {"type": "ROOM_LEFT", "room_id": leave_info["room_id"]},
        )
        if not leave_info["room_closed"] and leave_info["role"] != Role.SPECTATOR:
            updated_room = self.rooms.get_room(leave_info["room_id"])
            self._send_room_update(updated_room, "ROOM_UPDATED")

    def _logout(self, connection: Any, username: str) -> None:
        self.invitations.cancel_for(username)
        room = self.rooms.room_of(username)
        if room is not None:
            self._leave_room(username)
        self.sync.unregister_connection(username, connection)
        self.login.handle_logout(connection)

    def disconnect(self, connection: Any) -> None:
        player = self.players.get_player(connection)
        if player is None:
            return
        self.invitations.cancel_for(player.name)
        room = self.rooms.room_of(player.name)
        if room is not None and room.role_of(player.name) == Role.SPECTATOR:
            self.rooms.leave_room(player.name)
        elif room is not None and room.room_id not in self.sync.rooms:
            leave_info = self.rooms.leave_room(player.name)
            if not leave_info["room_closed"]:
                self._send_room_update(
                    self.rooms.get_room(leave_info["room_id"]), "ROOM_UPDATED"
                )
        self.sync.handle_disconnect(player.name)
        self.sync.unregister_connection(player.name, connection)
        self.players.disconnect(connection)
        self.online_list.broadcast()

    def _connection_for(self, username: str) -> Any:
        player = next(
            (item for item in self.players.get_players() if item.name == username),
            None,
        )
        return player.connection if player is not None else None

    def _set_player_status(self, username: str, status: PlayerStatus) -> None:
        with self.players.lock:
            player = next(
                (item for item in self.players.get_players() if item.name == username),
                None,
            )
            if player is not None:
                player.status = status

    def _send_room_update(self, room, message_type: str) -> None:
        if room is None:
            return
        packet = {"type": message_type, "room": room.to_dict()}
        for username in room.members():
            connection = self._connection_for(username)
            if connection is not None:
                self._send_message(connection, packet)
