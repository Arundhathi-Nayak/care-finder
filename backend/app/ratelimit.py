"""In-memory sliding-window rate limiter (per client IP). Fine for one Cloud Run instance."""
import threading
import time
from collections import deque

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, limit: int = 20, window: float = 60.0):
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] >= self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            if len(self._hits) > 10_000:  # keep memory bounded
                self._hits = {k: v for k, v in self._hits.items() if v and now - v[-1] < self.window}
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter(limit=20, window=60.0)


def check_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    if not limiter.allow(ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.",
                            headers={"Retry-After": "60"})