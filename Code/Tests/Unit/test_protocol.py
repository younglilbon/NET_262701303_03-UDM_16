import unittest

from Code.Shared.Protocol.messages import (
    CLIENT_MESSAGE_TYPES,
    ERROR_CODES,
    MAX_MESSAGE_BYTES,
    ProtocolError,
    SERVER_MESSAGE_TYPES,
    decode_message,
    encode_message,
    make_error,
)


class TestProtocol(unittest.TestCase):
    def test_round_trip_unicode_message(self):
        message = {"type": "ROOM_CREATED", "room": {"name": "Phòng Caro"}}
        self.assertEqual(decode_message(encode_message(message)), message)

    def test_rejects_message_without_type(self):
        with self.assertRaises(ProtocolError) as ctx:
            encode_message({"action": "LOGIN"})
        self.assertEqual(ctx.exception.code, "INVALID_MESSAGE")

    def test_rejects_non_object_message(self):
        with self.assertRaises(ProtocolError) as ctx:
            decode_message(b'["not", "an object"]\n')
        self.assertEqual(ctx.exception.code, "INVALID_MESSAGE")

    def test_rejects_invalid_utf8_and_malformed_json(self):
        with self.assertRaises(ProtocolError) as utf8_ctx:
            decode_message(b"\xff\xfe\xfd\n")
        self.assertEqual(utf8_ctx.exception.code, "INVALID_JSON")

        with self.assertRaises(ProtocolError) as json_ctx:
            decode_message(b'{"type": "LOGIN"\n')
        self.assertEqual(json_ctx.exception.code, "INVALID_JSON")

    def test_rejects_missing_newline(self):
        with self.assertRaises(ProtocolError) as ctx:
            decode_message(b'{"type": "PLAYER_LIST"}')
        self.assertEqual(ctx.exception.code, "INVALID_MESSAGE")

    def test_enforces_max_message_bytes_boundary(self):
        overhead = len(encode_message({"type": "LOGIN", "name": ""}))
        exact_name = "a" * (MAX_MESSAGE_BYTES - overhead)
        encoded = encode_message({"type": "LOGIN", "name": exact_name})
        self.assertEqual(len(encoded), MAX_MESSAGE_BYTES)
        self.assertEqual(decode_message(encoded)["name"], exact_name)

        with self.assertRaises(ProtocolError) as ctx:
            encode_message({"type": "LOGIN", "name": exact_name + "x"})
        self.assertEqual(ctx.exception.code, "MESSAGE_TOO_LARGE")

    def test_protocol_catalog_and_make_error(self):
        self.assertIn("LOGIN", CLIENT_MESSAGE_TYPES)
        self.assertIn("REMATCH_RESPONSE", CLIENT_MESSAGE_TYPES)
        self.assertIn("SYNC_FULL_STATE", SERVER_MESSAGE_TYPES)
        self.assertIn("MESSAGE_TOO_LARGE", ERROR_CODES)
        err = make_error("NOT_YOUR_TURN", "Chưa tới lượt.", room_id="R1", match_id="M1")
        self.assertEqual(err["type"], "ERROR")
        self.assertEqual(err["room_id"], "R1")
        self.assertEqual(err["match_id"], "M1")

    def test_protocol_trip_multiple_valid_message_types(self):
        message_types = [
            "LOGIN",
            "LOGIN_RESULT",
            "PLAYER_LIST",
            "INVITE",
            "INVITE_RESPONSE",
            "INVITE_RESULT",
            "CREATE_ROOM",
            "JOIN_ROOM",
            "LEAVE_ROOM",
            "ROOM_CREATE",
            "ROOM_JOINED",
            "ROOM_LEFT",
            "START_MATCH",
            "MOVE",
            "SYNC_MOVE",
            "SYNC_FULL_STATE",
            "MATCH_FINISHED",
            "ERROR",
            "PLAYER_DISCONNECTED",
            "PLAYER_RECONNECTED"
        ]

        for message_type in message_types:
            with self.subTest(message_type=message_type):
                original_message = {
                    "type": message_type,
                    "room_id": "ROOM_01",
                    "username": "Alice",
                    "payload": {
                        "text": "Phòng Caro",
                        "row": 2,
                        "col": 3,
                        "active": True,
                        "extra": None
                    },
                }

                encoded = encode_message(original_message)

                self.assertIsInstance(encoded, bytes)
                self.assertTrue(encoded.endswith(b"\n"))

                decoded = decode_message(encoded)

                self.assertEqual(decoded, original_message)

    def test_rejects_malformed_json_message(self):
        invalid_payload = b"abc\n"
        with self.assertRaises(ProtocolError):
            decode_message(invalid_payload)

    def test_rejects_json_message_missing_type(self):
        invalid_payload = b'{"action":"move"}\n'
        with self.assertRaises(ProtocolError) as context:
            decode_message(invalid_payload)
        self.assertIn("type", str(context.exception).lower())

    def test_rejects_unknown_message_type(self):
        invalid_payload = b'{"type": "unknown_xyz"}\n'
        with self.assertRaises(ProtocolError) as context:
            decode_message(invalid_payload)
        self.assertEqual(
            context.exception.code,
            "UNKNOWN_MESSAGE"
        )
        self.assertIn(
            "unknown_xyz",
            str(context.exception)
        )

    def test_round_trip_vietnamese_unicode_message(self):
        original_message = {
            "type": "LOGIN",
            "username": "Nguyễn Văn An",
            "display_name": "Nguyễn Thị Ánh",
            "message": "Chào mừng bạn đến với phòng Caro!"
        }
        encoded = encode_message(original_message)
        decoded = decode_message(encoded)

        self.assertIsInstance(encoded, bytes)
        self.assertTrue(encoded.endswith(b"\n"))
        self.assertEqual(decoded, original_message)

    def test_round_trip_large_100kb_message(self):
        large_text = "A" * (100*1024)
        original_message = {
            "type": "SYNC_FULL_STATE",
            "username": "alice",
            "display_name": "Nguyễn Văn An",
            "payload": large_text,
        }
        encoded = encode_message(original_message)
        decoded = decode_message(encoded)
        self.assertLessEqual(len(encoded), MAX_MESSAGE_BYTES)
        self.assertGreater(len(encoded), 100 * 1024)
        self.assertEqual(decoded, original_message)
        self.assertEqual(decoded["payload"], large_text)
        self.assertEqual(decoded["username"], "alice")
        self.assertEqual(decoded["display_name"], "Nguyễn Văn An")

if __name__ == "__main__":
    unittest.main()
    