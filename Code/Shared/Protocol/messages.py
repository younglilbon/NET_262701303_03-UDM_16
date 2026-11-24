import json
from typing import Any

MAX_MESSAGE_BYTES = 1_000_000

CLIENT_MESSAGE_TYPES = frozenset({
    "LOGIN",
    "LOGOUT",
    "PLAYER_LIST",
    "INVITE",
    "INVITE_RESPONSE",
    "CREATE_ROOM",
    "LIST_ROOMS",
    "JOIN_ROOM",
    "JOIN_AS_SPECTATOR",
    "START_MATCH",
    "MOVE",
    "LEAVE_ROOM",
    "REMATCH",
    "REMATCH_RESPONSE",
})

SERVER_MESSAGE_TYPES = frozenset({
    "LOGIN_RESULT",
    "PLAYER_LIST",
    "INVITE",
    "INVITE_RESULT",
    "ROOM_LIST",
    "ROOM_CREATED",
    "ROOM_JOINED",
    "ROOM_UPDATED",
    "ROOM_STARTED",
    "ROOM_LEFT",
    "ROOM_CLOSED",
    "SYNC_FULL_STATE",
    "SYNC_MOVE",
    "SPECTATOR_JOINED",
    "SPECTATOR_LEFT",
    "PLAYER_DISCONNECTED",
    "PLAYER_RECONNECTED",
    "MATCH_FINISHED",
    "REMATCH_REQUEST",
    "REMATCH_RESULT",
    "ERROR",
})

ERROR_CODES = frozenset({
    "LOGIN_REQUIRED",
    "INVALID_MESSAGE",
    "INVALID_JSON",
    "MESSAGE_TOO_LARGE",
    "INVALID_ARGUMENT",
    "UNKNOWN_MESSAGE",
    "ROOM_NOT_FOUND",
    "ROOM_FULL",
    "ALREADY_IN_ROOM",
    "NOT_IN_ROOM",
    "NOT_HOST",
    "INVALID_STATE",
    "SPECTATOR_FORBIDDEN",
    "NAME_INVALID",
    "NAME_TAKEN",
    "ALREADY_LOGGED_IN",
    "PLAYER_BUSY",
    "INVITATION_NOT_FOUND",
    "INVITATION_FORBIDDEN",
    "REMATCH_PENDING",
    "REMATCH_NOT_FOUND",
    "REMATCH_FORBIDDEN",
    "GAME_PAUSED",
    "NOT_YOUR_TURN",
    "OUT_OF_BOUNDS",
    "CELL_OCCUPIED",
    "GAME_OVER",
})


class ProtocolError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def make_error(
    code: str,
    message: str,
    *,
    room_id: str | None = None,
    match_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "ERROR",
        "code": code,
        "message": message,
    }
    if room_id is not None:
        payload["room_id"] = room_id
    if match_id is not None:
        payload["match_id"] = match_id
    return payload


def encode_message(message: dict[str, Any]) -> bytes:
    if not isinstance(message, dict) or not isinstance(message.get("type"), str) or not message["type"].strip():
        raise ProtocolError("INVALID_MESSAGE", "Protocol message must be an object with a non-empty string 'type'.")
    payload = json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n"
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ProtocolError("MESSAGE_TOO_LARGE", "Message exceeds the 1,000,000-byte limit.")
    return payload


def decode_message(payload: bytes) -> dict[str, Any]:
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ProtocolError("MESSAGE_TOO_LARGE", "Message exceeds the 1,000,000-byte limit.")
    if not payload.endswith(b"\n"):
        raise ProtocolError("INVALID_MESSAGE", "Message must be newline-terminated.")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolError("INVALID_JSON", "Message is not valid UTF-8.") from exc
    try:
        message = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProtocolError("INVALID_JSON", f"Malformed JSON payload: {exc.msg}.") from exc
    if not isinstance(message, dict) or not isinstance(message.get("type"), str) or not message["type"].strip():
        raise ProtocolError("INVALID_MESSAGE", "Protocol message must be a JSON object with a string 'type'.")
    return message
