"""Create, accept, and reject player invitations."""

import threading
import uuid
from collections.abc import Callable
from typing import Any

from .models import Invitation, PlayerStatus
from .player_management import PlayerManager

SendMessage = Callable[[Any, dict[str, Any]], None]


class InvitationManager:
    def __init__(
        self,
        players: PlayerManager,
        send_message: SendMessage,
        on_accept: Callable[[str, str], None] | None = None,
    ) -> None:
        self._players = players
        self._send_message = send_message
        self._on_accept = on_accept
        self._lock = threading.RLock()
        self._invitations: dict[str, Invitation] = {}

    def invite(self, connection: Any, requested_target: object) -> bool:
        error = None
        with self._lock, self._players.lock:
            sender = self._players.get_player(connection)
            if sender is None:
                error = "Login is required"
            elif not self._players.is_valid_name(requested_target):
                error = "Invalid target name"
            else:
                target_key = requested_target.strip().casefold()
                recipient = next(
                    (
                        player
                        for player in self._players.get_players()
                        if player.name.casefold() == target_key
                    ),
                    None,
                )
                if recipient is None or recipient.connection is None:
                    error = "Target player is not online"
                elif recipient is sender:
                    error = "You cannot invite yourself"
                elif (
                    sender.status is not PlayerStatus.ONLINE
                    or recipient.status is not PlayerStatus.ONLINE
                ):
                    error = "One of the players is not available"
                else:
                    invitation = Invitation(
                        invite_id=uuid.uuid4().hex,
                        sender_key=sender.name.casefold(),
                        recipient_key=recipient.name.casefold(),
                        sender_name=sender.name,
                        recipient_name=recipient.name,
                    )
                    recipient_connection = recipient.connection
                    self._invitations[invitation.invite_id] = invitation
                    sender.status = PlayerStatus.INVITE_PENDING
                    recipient.status = PlayerStatus.INVITE_PENDING

        if error is not None:
            return self._error(connection, error)

        self._send_message(
            recipient_connection,
            {
                "type": "INVITE",
                "invite_id": invitation.invite_id,
                "from": sender.name,
            },
        )
        self._send_message(connection, self._result(invitation, "PENDING"))
        return True

    def respond(self, connection: Any, invite_id: object, accepted: bool) -> bool:
        error = None
        cancellation_notifications = []
        with self._lock, self._players.lock:
            recipient = self._players.get_player(connection)
            invitation = (
                self._invitations.get(invite_id)
                if isinstance(invite_id, str)
                else None
            )
            if recipient is None:
                error = "Login is required"
            elif invitation is None:
                error = "Invitation is not pending"
            elif recipient.name.casefold() != invitation.recipient_key:
                error = "Only the invited player can respond"
            else:
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
                    del self._invitations[invitation.invite_id]
                    for participant in (sender, recipient):
                        if (
                            participant is not None
                            and participant.status is PlayerStatus.INVITE_PENDING
                        ):
                            participant.status = (
                                PlayerStatus.ONLINE
                                if participant.connection is not None
                                else PlayerStatus.OFFLINE
                            )
                    if sender is not None and sender.connection is not None:
                        cancellation_notifications.append(
                            (
                                sender.connection,
                                self._result(invitation, "CANCELLED"),
                            )
                        )
                    error = "Invitation participants are no longer available"
                else:
                    del self._invitations[invitation.invite_id]
                    sender.status = PlayerStatus.ONLINE
                    recipient.status = PlayerStatus.ONLINE
                    result = self._result(
                        invitation,
                        "ACCEPTED" if accepted else "REJECTED",
                    )
                    sender_connection = sender.connection
                    recipient_connection = recipient.connection

        if error is not None:
            for cancelled_connection, packet in cancellation_notifications:
                self._send_message(cancelled_connection, packet)
            return self._error(connection, error)

        if accepted and self._on_accept is not None:
            self._on_accept(invitation.sender_name, invitation.recipient_name)
        self._send_message(sender_connection, result)
        self._send_message(recipient_connection, result)
        return True

    def cancel_for(self, player_name: str) -> None:
        player_key = player_name.casefold()
        notifications = []
        with self._lock, self._players.lock:
            for invite_id, invitation in list(self._invitations.items()):
                if player_key not in (invitation.sender_key, invitation.recipient_key):
                    continue
                del self._invitations[invite_id]
                participant = next(
                    (
                        player
                        for player in self._players.get_players()
                        if player.name.casefold() == player_key
                    ),
                    None,
                )
                if (
                    participant is not None
                    and participant.status is PlayerStatus.INVITE_PENDING
                ):
                    participant.status = (
                        PlayerStatus.ONLINE
                        if participant.connection is not None
                        else PlayerStatus.OFFLINE
                    )
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
                if other is not None:
                    if other.status is PlayerStatus.INVITE_PENDING:
                        other.status = (
                            PlayerStatus.ONLINE
                            if other.connection is not None
                            else PlayerStatus.OFFLINE
                        )
                    if other.connection is not None:
                        notifications.append(
                            (
                                other.connection,
                                self._result(invitation, "CANCELLED"),
                            )
                        )
        for connection, packet in notifications:
            self._send_message(connection, packet)

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
