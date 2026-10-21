"""timer.py - Đồng hồ giới hạn thời gian suy nghĩ mỗi lượt (TV4).

Thiết kế "pull": Timer không tự tạo thread. Server (hoặc vòng lặp tick của
TV3/TV5) gọi engine.check_timeout() định kỳ ~ mỗi 0.5-1 giây. Cách này dễ test
(truyền clock giả) và tránh race condition giữa nhiều thread.
"""
import time
from typing import Callable, Optional


class TurnTimer:
    def __init__(self, limit: float = 30.0, clock: Callable[[], float] = time.monotonic):
        if limit <= 0:
            raise ValueError("limit phải > 0")
        self.limit = limit
        self._clock = clock
        self._deadline: Optional[float] = None   # khi đang chạy
        self._paused_left: Optional[float] = None  # khi đang tạm dừng

    # ---------- điều khiển ----------
    def start(self, seconds: Optional[float] = None) -> None:
        """Bắt đầu đếm ngược (mặc định = limit). Dùng khi đổi lượt."""
        self._paused_left = None
        self._deadline = self._clock() + (self.limit if seconds is None else seconds)

    def stop(self) -> None:
        self._deadline = None
        self._paused_left = None

    def pause(self) -> None:
        """Tạm dừng (vd: người chơi mất kết nối, đang chờ kết nối lại)."""
        if self._deadline is not None:
            self._paused_left = max(0.0, self._deadline - self._clock())
            self._deadline = None

    def resume(self) -> None:
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

    def expired(self) -> bool:
        return self._deadline is not None and self._clock() >= self._deadline
