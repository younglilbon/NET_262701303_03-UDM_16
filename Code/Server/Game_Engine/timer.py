import math
import time
from typing import Any, Callable, Optional

MIN_TURN_TIME_LIMIT = 5
MAX_TURN_TIME_LIMIT = 600
DEFAULT_TURN_TIME_LIMIT = 30


def validate_turn_time_limit(limit: Any) -> int:
    """Kiểm tra cấu hình thời gian lượt từ chủ phòng: int trong [5, 600], từ chối bool."""
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not (MIN_TURN_TIME_LIMIT <= limit <= MAX_TURN_TIME_LIMIT)
    ):
        raise ValueError(
            f"Thời gian lượt phải là số nguyên từ {MIN_TURN_TIME_LIMIT} đến {MAX_TURN_TIME_LIMIT} giây."
        )
    return limit


class TurnTimer:
    def __init__(
        self,
        limit: float = DEFAULT_TURN_TIME_LIMIT,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if isinstance(limit, bool) or not isinstance(limit, (int, float)) or limit <= 0:
            raise ValueError("limit phải là số dương > 0")
        self.limit = float(limit)
        self._clock = clock
        self._deadline: Optional[float] = None      # khi đang chạy
        self._paused_left: Optional[float] = None   # khi đang tạm dừng

    # ---------- điều khiển ----------
    def start(self, seconds: Optional[float] = None) -> None:
        """Bắt đầu đếm ngược (mặc định = limit). Dùng khi bắt đầu hoặc đổi lượt."""
        duration = self.limit if seconds is None else seconds
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0:
            raise ValueError("seconds phải là số dương > 0")
        self._paused_left = None
        self._deadline = self._clock() + float(duration)

    def stop(self) -> None:
        self._deadline = None
        self._paused_left = None

    def pause(self) -> None:
        """Tạm dừng (vd: người chơi mất kết nối, đang chờ kết nối lại)."""
        if self._deadline is not None:
            self._paused_left = max(0.0, self._deadline - self._clock())
            self._deadline = None

    def resume(self) -> None:
        """Tiếp tục đếm với phần thời gian còn lại trước khi tạm dừng."""
        if self._paused_left is not None:
            self._deadline = self._clock() + self._paused_left
            self._paused_left = None

    # ---------- truy vấn ----------
    @property
    def running(self) -> bool:
        return self._deadline is not None

    @property
    def paused(self) -> bool:
        return self._paused_left is not None

    def remaining(self) -> float:
        if self._deadline is not None:
            return max(0.0, self._deadline - self._clock())
        if self._paused_left is not None:
            return self._paused_left
        return 0.0

    def remaining_seconds(self) -> int:
        """Số giây còn lại không âm, làm tròn lên để tránh hiện 0 khi vẫn còn phần giây."""
        return math.ceil(self.remaining())

    def expired(self) -> bool:
        return self._deadline is not None and self._clock() >= self._deadline
