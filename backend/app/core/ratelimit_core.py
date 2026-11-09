"""Sliding-window counter. In-memory = one process; with several workers or servers, move this to Redis."""
import time
from collections import deque


class RateLimiter:
    def __init__(self, max_hits: int, window_s: float, clock=time.monotonic):
        self.max_hits, self.window_s, self.clock = max_hits, window_s, clock
        self.hits: dict[str, deque[float]] = {}

    def _recent(self, key: str) -> deque[float]:
        q = self.hits.get(key, deque())
        cutoff = self.clock() - self.window_s
        while q and q[0] <= cutoff:
            q.popleft()
        if q:
            self.hits[key] = q
        else:
            self.hits.pop(key, None)            # don't keep empty keys around forever
        return q

    def blocked(self, key: str) -> float:
        """Seconds until `key` may try again; 0 means allowed now."""
        q = self._recent(key)
        return q[0] + self.window_s - self.clock() if len(q) >= self.max_hits else 0

    def hit(self, key: str) -> None:
        q = self._recent(key)
        q.append(self.clock())
        self.hits[key] = q

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self.hits.clear()
        else:
            self.hits.pop(key, None)
