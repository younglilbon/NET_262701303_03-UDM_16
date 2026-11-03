"""Create, accept, and reject player invitations."""

import threading
import uuid
from collections.abc import Callable
from typing import Any

from .models import Invitation, PlayerStatus
from .player_management import PlayerManager

SendMessage = Callable[[Any, dict[str, Any]], None]


class InvitationManager:
    def __init__(self, players: PlayerManager, send_message: SendMessage) -> None:
        self._players = players
        self._send_message = send_message
        self._lock = threading.RLock()
        self._invitations: dict[str, Invitation] = {}

    def invite(self, connection: Any, requested_target: object) -> bool:
        with self._lock, self._players.lock:
            sender = self._players.get_player(connection)
            if sender is None:
                return self._error(connection, "Login is required")
            if not self._players.is_valid_name(requested_target):
                return self._error(connection, "Invalid target name")

            recipient = next(
                (
                    player
                    for player in self._players.get_players()
                    if player.name.casefold() == requested_target.strip().casefold()
                ),
                None,
            )
            if recipient is None or recipient.connection is None:
                return self._error(connection, "Target player is not online")
            if recipient is sender:
                return self._error(connection, "You cannot invite yourself")
            if (
                sender.status is not PlayerStatus.ONLINE
                or recipient.status is not PlayerStatus.ONLINE
            ):
                return self._error(connection, "One of the players is not available")

            invitation = Invitation(
                invite_id=uuid.uuid4().hex,
                sender_key=sender.name.casefold(),
                recipient_key=recipient.name.casefold(),
                sender_name=sender.name,
                recipient_name=recipient.name,
            )
            self._invitations[invitation.invite_id] = invitation
            sender.status = PlayerStatus.INVITE_PENDING
            recipient.status = PlayerStatus.INVITE_PENDING

        self._send_message(
            recipient.connection,
            {
                "type": "INVITE",
                "invite_id": invitation.invite_id,
                "from": sender.name,
            },
        )
        self._send_message(connection, self._result(invitation, "PENDING"))
        return True

    def respond(self, connection: Any, invite_id: object, accepted: bool) -> bool:
        with self._lock, self._players.lock:
            recipient = self._players.get_player(connection)
            invitation = (
                self._invitations.get(invite_id)
                if isinstance(invite_id, str)
                else None
            )
            if recipient is None:
                return self._error(connection, "Login is required")
            if invitation is None:
                return self._error(connection, "Invitation is not pending")
            if recipient.name.casefold() != invitation.recipient_key:
                return self._error(connection, "Only the invited player can respond")

            sender = next(
                (
                    player
                    for player in self._players.get_players()
                    if player.name.casefold() == invitation.sender_key
                ),
                None,
            )
            if (
                sender is None
                or sender.connection is None
                or recipient.connection is None
                or sender.status is not PlayerStatus.INVITE_PENDING
                or recipient.status is not PlayerStatus.INVITE_PENDING
            ):
                self._invitations.pop(invitation.invite_id, None)
                return self._error(connection, "Invitation participants are no longer available")

            del self._invitations[invitation.invite_id]
            sender.status = PlayerStatus.ONLINE
            recipient.status = PlayerStatus.ONLINE
            result = self._result(
                invitation,
                "ACCEPTED" if accepted else "REJECTED",
            )
            sender_connection = sender.connection
            recipient_connection = recipient.connection

        self._send_message(sender_connection, result)
        self._send_message(recipient_connection, result)
        return True

    def cancel_for(self, player_name: str) -> None:
        player_key = player_name.casefold()
        with self._lock, self._players.lock:
            for invite_id, invitation in list(self._invitations.items()):
                if player_key not in (invitation.sender_key, invitation.recipient_key):
                    continue
                del self._invitations[invite_id]
                other_key = (
                    invitation.recipient_key
                    if invitation.sender_key == player_key
                    else invitation.sender_key
                )
                other = next(
                    (
                        player
                        for player in self._players.get_players()
                        if player.name.casefold() == other_key
                    ),
                    None,
                )
                if other is not None and other.status is PlayerStatus.INVITE_PENDING:
                    other.status = PlayerStatus.ONLINE
                    if other.connection is not None:
                        self._send_message(other.connection, self._result(invitation, "CANCELLED"))

    def _error(self, connection: Any, reason: str) -> bool:
        self._send_message(connection, {"type": "ERROR", "message": reason})
        return False

    @staticmethod
    def _result(invitation: Invitation, status: str) -> dict[str, str]:
        return {
            "type": "INVITE_RESULT",
            "invite_id": invitation.invite_id,
            "from": invitation.sender_name,
            "to": invitation.recipient_name,
            "status": status,
        }
