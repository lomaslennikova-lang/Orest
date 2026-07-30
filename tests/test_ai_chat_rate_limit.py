from __future__ import annotations

import unittest

from app.ai_chat.rate_limit import ChatRateLimiter


class MutableClock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


class ChatRateLimiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_allows_ten_requests_and_rejects_the_eleventh(self):
        clock = MutableClock(100.0)
        limiter = ChatRateLimiter(clock=clock)

        for _ in range(10):
            self.assertIsNone(await limiter.consume("admin"))

        self.assertEqual(await limiter.consume("admin"), 60)

    async def test_allows_a_request_after_the_sliding_window_expires(self):
        clock = MutableClock(100.0)
        limiter = ChatRateLimiter(clock=clock)

        for _ in range(10):
            await limiter.consume("admin")

        clock.value += 60.0
        self.assertIsNone(await limiter.consume("admin"))

    async def test_tracks_administrators_independently(self):
        limiter = ChatRateLimiter(max_requests=1, clock=MutableClock(100.0))

        self.assertIsNone(await limiter.consume("admin-one"))
        self.assertEqual(await limiter.consume("admin-one"), 60)
        self.assertIsNone(await limiter.consume("admin-two"))
