"""
TV3 - Room & Match
Định nghĩa các mã lỗi nghiệp vụ phòng đấu.
TV1 sẽ dùng các mã này để map sang Protocol message.
"""

# Mã lỗi thống nhất với TV1 (Protocol)
ROOM_NOT_FOUND = "ROOM_NOT_FOUND"
ROOM_FULL = "ROOM_FULL"
ALREADY_IN_ROOM = "ALREADY_IN_ROOM"
NOT_IN_ROOM = "NOT_IN_ROOM"
NOT_HOST = "NOT_HOST"
INVALID_STATE = "INVALID_STATE"
SPECTATOR_FORBIDDEN = "SPECTATOR_FORBIDDEN"
INVALID_ARGUMENT = "INVALID_ARGUMENT"


class RoomError(Exception):
    """Lỗi nghiệp vụ phòng; code dùng để TV1 map sang mã lỗi Protocol."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code