from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import settings

# Keys are pruned after this long without activity so an attacker spraying
# unique usernames cannot grow the in-process map without bound.
_MAX_RETENTION_SECONDS = 24 * 60 * 60
_PRUNE_EVERY = 1_000


class RateLimiter:
    """Small in-process sliding-window limiter.

    Appropriate for the single-instance MVP deployment. A horizontally scaled
    deployment must replace this with a shared limiter (for example Redis).
    """

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._calls = 0

    def consume(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        if not settings.RATE_LIMIT_ENABLED:
            return True, 0
        now = time.monotonic()
        with self._lock:
            self._calls += 1
            if self._calls % _PRUNE_EVERY == 0:
                self._prune(now)
            events = self._events[key]
            cutoff = now - window_seconds
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, math.ceil(events[0] + window_seconds - now))
                return False, retry_after
            events.append(now)
            return True, 0

    def _prune(self, now: float) -> None:
        cutoff = now - _MAX_RETENTION_SECONDS
        for key in list(self._events):
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if not events:
                del self._events[key]

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def size(self) -> int:
        with self._lock:
            return sum(len(events) for events in self._events.values())


limiter = RateLimiter()


def reset_rate_limits() -> None:
    limiter.clear()


def client_ip(request: Request) -> str:
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # The deployment has a single trusted proxy in front of the app.
            # Use the value added by that proxy, not a client-supplied prefix.
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def consume_or_429(
    *,
    request: Request,
    scope: str,
    identity: str,
    limit: int,
    window_seconds: int,
) -> None:
    allowed, retry_after = limiter.consume(
        f"{scope}:{client_ip(request)}:{identity}", limit, window_seconds
    )
    if not allowed:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=429,
            detail="too_many_attempts",
            headers={"Retry-After": str(retry_after)},
        )
