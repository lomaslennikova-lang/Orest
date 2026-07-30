"""Process-local request limiting for the AI-chat endpoint."""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from collections.abc import Callable


class ChatRateLimiter:
    """Allow a bounded number of requests per key in a sliding time window."""

    def __init__(
        self,
        *,
        max_requests: int = 10,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be at least 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._requests: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def consume(self, key: str) -> int | None:
        """Consume one request slot, or return seconds until the next slot."""

        now = self._clock()
        cutoff = now - self.window_seconds

        async with self._lock:
            requests = self._requests.setdefault(key, deque())
            while requests and requests[0] <= cutoff:
                requests.popleft()

            if len(requests) >= self.max_requests:
                retry_after = self.window_seconds - (now - requests[0])
                return max(1, math.ceil(retry_after))

            requests.append(now)
            return None
