from __future__ import annotations

import hashlib
import ipaddress
import math
import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from sqlalchemy import text
from sqlmodel import Session

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


def _key_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _consume_database(
    session: Session, key: str, limit: int, window_seconds: int
) -> tuple[bool, int]:
    """Atomic fixed-window increment shared across serverless instances."""
    now = time.time()
    cutoff = now - window_seconds
    key_hash = _key_hash(key)
    session.execute(
        text(
            "DELETE FROM rate_limit_counter "
            "WHERE window_start < :retention"
        ),
        {"retention": now - _MAX_RETENTION_SECONDS},
    )
    row = session.execute(
        text(
            """
            INSERT INTO rate_limit_counter (key_hash, window_start, count)
            VALUES (:key_hash, :now, 1)
            ON CONFLICT (key_hash) DO UPDATE SET
                count = CASE
                    WHEN rate_limit_counter.window_start <= :cutoff
                    THEN 1 ELSE rate_limit_counter.count + 1
                END,
                window_start = CASE
                    WHEN rate_limit_counter.window_start <= :cutoff
                    THEN :now ELSE rate_limit_counter.window_start
                END
            RETURNING count, window_start
            """
        ),
        {"key_hash": key_hash, "now": now, "cutoff": cutoff},
    ).one()
    session.commit()
    count, window_start = row
    if count > limit:
        retry_after = max(1, math.ceil(window_start + window_seconds - now))
        return False, retry_after
    return True, 0


def reset_rate_limit(session: Session, key: str) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    if settings.RATE_LIMIT_BACKEND == "database":
        session.execute(
            text("DELETE FROM rate_limit_counter WHERE key_hash = :key_hash"),
            {"key_hash": _key_hash(key)},
        )
        session.commit()
        return
    limiter.reset(key)


def reset_rate_limits() -> None:
    limiter.clear()


def _parse_ip(value: str) -> str | None:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def client_ip(request: Request) -> str:
    if settings.TRUST_PROXY_HEADERS:
        # Vercel sets X-Real-IP to the client address.
        real_ip = _parse_ip(request.headers.get("x-real-ip", ""))
        if real_ip:
            return real_ip
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Traefik appends the peer address to X-Forwarded-For. Use the
            # rightmost value (the trusted proxy's observation), never a
            # client-supplied prefix. Invalid values fall back to the socket.
            candidate = _parse_ip(forwarded.split(",")[-1])
            if candidate:
                return candidate
    return request.client.host if request.client else "unknown"


def consume_or_429(
    *,
    session: Session,
    request: Request,
    scope: str,
    identity: str,
    limit: int,
    window_seconds: int,
) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    key = f"{scope}:{client_ip(request)}:{identity}"
    if settings.RATE_LIMIT_BACKEND == "database":
        allowed, retry_after = _consume_database(
            session, key, limit, window_seconds
        )
    else:
        allowed, retry_after = limiter.consume(key, limit, window_seconds)
    if not allowed:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=429,
            detail="too_many_attempts",
            headers={"Retry-After": str(retry_after)},
        )
