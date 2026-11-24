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


if __name__ == "__main__":
    unittest.main()
    