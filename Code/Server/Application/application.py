"""Application service that connects the network, lobby, rooms, and matches."""

from typing import Any, Callable
from copy import deepcopy
import logging

from .coordination import Coordinator, coordinated

from ..Room_Match.errors import RoomError
from ..Room_Match.manager import RoomManager
from ..Room_Match.models import Role, RoomStatus
from ..Synchronization.sync_manager import SyncManager
from ..User_Lobby.invitation import InvitationManager
from ..User_Lobby.login import LoginService
from ..User_Lobby.models import PlayerStatus
from ..User_Lobby.online_list import OnlineList
from ..User_Lobby.player_management import PlayerManager

SendMessage = Callable[[Any, dict[str, Any]], None]


class ServerApplication:
    """Dispatch the single JSON message format used by all server modules."""

    def __init__(self, send_message: SendMessage) -> None:
        self.coordinator = Coordinator()
        self._transport_send = send_message
        self.players = PlayerManager()
        self.online_list = OnlineList(self.players, self._send_message)
        self.login = LoginService(self.players, self.online_list, self._send_message)
        self.rooms = RoomManager()
        self.sync = SyncManager(
            send_callback=self._send_message,
            on_match_finished=self._match_finished,
            coordinator=self.coordinator,
        )
        self.invitations = InvitationManager(
            self.players, self._send_message, on_accept=self._start_invited_match
        )

    def _send_message(self, connection, message):
        if connection is None:
            return
        packet = deepcopy(message)
        def send():
            try:
                self._transport_send(connection, packet)
            except OSError:
                logging.exception("Could not send %s to a client", packet.get("type"))
        self.coordinator.defer(send)

    @coordinated
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
            # A new opponent must not receive events or reconnect into the old match.
            self.sync.close_room(room.room_id)
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

    @coordinated
    def _match_finished(self, room_id: str, winner: str, reason: str, match_id: str) -> None:
        state = self.sync.match_snapshot(room_id)
        if state is None or state["match_id"] != match_id:
            return
        try:
            room = self.rooms.get_room(room_id)
        except RoomError:
            return
        if room.status == RoomStatus.PLAYING:
            self.rooms.finish_match(room_id)
        affected = room.members()
        self._detach_offline_players(room_id)
        self._notify_room_change(room_id, affected)

    @coordinated
    def _leave_room(self, username: str) -> None:
        room = self.rooms.room_of(username)
        if room is None:
            raise RoomError("NOT_IN_ROOM", "Player is not in a room.")
        room_id = room.room_id
        members_before = room.members()
        state = self.sync.match_snapshot(room_id)
        role = room.role_of(username)
        if role != Role.SPECTATOR and state is not None and state["status"] in ("PLAYING", "PAUSED"):
            winner_symbol = next(
                symbol for symbol, name in state["players"].items() if name != username
            )
            self.sync.finish_and_save_match(
                room_id, winner_symbol, reason="RESIGN", notify_callback=False,
                expected_match_id=state["match_id"],
            )
            if room.status == RoomStatus.PLAYING:
                self.rooms.finish_match(room_id)
        leave_info = self.rooms.leave_room(username)
        self._clean_removed_members(leave_info)
        extra_removed = self._detach_offline_players(room_id)
        if role == Role.SPECTATOR and state is not None:
            remaining = self.rooms.get_room(room_id)
            self._send_to_members(remaining.members(), {
                "type": "SPECTATOR_LEFT", "room_id": room_id,
                "match_id": state["match_id"], "spectator": username,
                "spectator_count": len(remaining.spectators),
            })
        self._send_message(
            self._connection_for(username),
            {"type": "ROOM_LEFT", "room_id": room_id},
        )
        self._notify_room_change(room_id, members_before + extra_removed)

    def _clean_removed_members(self, change):
        for name in change["removed_members"]:
            self.sync.detach_member(change["room_id"], name)
            self._set_player_status(name, PlayerStatus.ONLINE)
        if change["room_closed"]:
            self.sync.close_room(change["room_id"])

    def _detach_offline_players(self, room_id):
        try:
            room = self.rooms.get_room(room_id)
        except RoomError:
            return []
        if room.status not in (RoomStatus.FINISHED, RoomStatus.WAITING):
            return []
        removed = []
        for name in list(room.players.values()):
            if self._connection_for(name) is None:
                change = self.rooms.detach_disconnected_player(name)
                removed.extend(change["removed_members"])
                self._clean_removed_members(change)
        return removed

    def _send_to_members(self, members, packet):
        for name in dict.fromkeys(members):
            self._send_message(self._connection_for(name), packet)

    def _notify_room_change(self, room_id, affected=()):
        try:
            room = self.rooms.get_room(room_id)
        except RoomError:
            self._send_to_members(affected, {
                "type": "ROOM_CLOSED", "room_id": room_id, "reason": "NO_PLAYERS",
            })
        else:
            self._send_room_update(room, "ROOM_UPDATED")
        packet = {"type": "ROOM_LIST", "rooms": self.rooms.list_rooms()}
        for player in self.players.get_players():
            if player.connection is not None and self.rooms.room_of(player.name) is None:
                self._send_message(player.connection, packet)

    def _logout(self, connection: Any, username: str) -> None:
        self.invitations.cancel_for(username)
        room = self.rooms.room_of(username)
        if room is not None:
            self._leave_room(username)
        self.sync.unregister_connection(username, connection)
        self.login.handle_logout(connection)

    @coordinated
    def disconnect(self, connection: Any) -> None:
        player = self.players.get_player(connection)
        if player is None:
            return
        self.invitations.cancel_for(player.name)
        self.players.disconnect(connection)
        self.sync.unregister_connection(player.name, connection)
        room = self.rooms.room_of(player.name)
        if room is not None:
            state = self.sync.match_snapshot(room.room_id)
            if (room.role_of(player.name) == Role.SPECTATOR or state is None
                    or state["status"] == "FINISHED"):
                self._leave_room(player.name)
            else:
                self.sync.handle_disconnect(player.name)
        self.online_list.broadcast()

    def _connection_for(self, username: str) -> Any:
        return self.players.connection_for(username)

    def _set_player_status(self, username: str, status: PlayerStatus) -> None:
        self.players.set_status_by_name(username, status)

    def _send_room_update(self, room, message_type: str) -> None:
        if room is None:
            return
        packet = {"type": message_type, "room": room.to_dict()}
        for username in room.members():
            connection = self._connection_for(username)
            if connection is not None:
                self._send_message(connection, packet)
