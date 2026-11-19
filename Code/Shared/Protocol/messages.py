"""Shared newline-delimited JSON message encoding for TCP."""

import json
from typing import Any

MAX_MESSAGE_BYTES = 1_000_000


def encode_message(message: dict[str, Any]) -> bytes:
    if not isinstance(message, dict) or not isinstance(message.get("type"), str):
        raise ValueError("A protocol message must be an object with a string 'type'.")
    payload = json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n"
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ValueError("Message exceeds the maximum size.")
    return payload


def decode_message(payload: bytes) -> dict[str, Any]:
    if len(payload) > MAX_MESSAGE_BYTES or not payload.endswith(b"\n"):
        raise ValueError("Message must be newline-terminated and within size limit.")
    message = json.loads(payload.decode("utf-8"))
    if not isinstance(message, dict) or not isinstance(message.get("type"), str):
        raise ValueError("A protocol message must be an object with a string 'type'.")
    return message
