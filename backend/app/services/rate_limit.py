"""In-process fixed-window rate limiting.

Best-effort brute-force defense for a trusted local / home-server deployment:
state lives in this process only, so it resets on restart and is not shared
across workers. That is enough to blunt an online password-guessing attack
without adding Redis. Put a real WAF / reverse-proxy limiter in front for
anything internet-facing.
"""

from __future__ import annotations

import threading
import time

from fastapi import HTTPException, status


class FixedWindowLimiter:
    def __init__(self, max_events: int, window_seconds: float) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> list[float]:
        cutoff = now - self.window_seconds
        kept = [t for t in self._events.get(key, ()) if t > cutoff]
        if kept:
            self._events[key] = kept
        else:
            self._events.pop(key, None)
        return kept

    def check(self, key: str) -> None:
        """Raise 429 if ``key`` has already hit the limit in the window."""
        now = time.monotonic()
        with self._lock:
            if len(self._prune(key, now)) >= self.max_events:
                retry = int(self.window_seconds)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many attempts. Try again later.",
                    headers={"Retry-After": str(retry)},
                )

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            self._events.setdefault(key, []).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


# 10 failed logins per identity per 15 minutes.
login_limiter = FixedWindowLimiter(max_events=10, window_seconds=15 * 60)
