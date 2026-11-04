import unittest

from Code.Shared.Protocol.messages import decode_message, encode_message


class TestProtocol(unittest.TestCase):
    def test_round_trip_unicode_message(self):
        message = {"type": "ROOM_CREATED", "room": {"name": "Phòng Caro"}}
        self.assertEqual(decode_message(encode_message(message)), message)

    def test_rejects_message_without_type(self):
        with self.assertRaises(ValueError):
            encode_message({"action": "LOGIN"})

    def test_rejects_non_object_message(self):
        with self.assertRaises(ValueError):
            decode_message(b'["not", "an object"]\n')


if __name__ == "__main__":
    unittest.main()
