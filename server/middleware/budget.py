"""Sliding-window counters behind the rate limit. No web framework, so it stays testable."""

from __future__ import annotations

from collections import deque
from typing import Deque
import threading

WINDOW_SECONDS = 60.0
MAX_TRACKED_CLIENTS = 4096


class Budget:
    """One sliding window of hit timestamps per key."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._hits: dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float) -> tuple[bool, int]:
        """Record a hit. Returns (allowed, seconds to wait when refused)."""
        cutoff = now - WINDOW_SECONDS
        with self._lock:
            window = self._hits.get(key)
            if window is None:
                if len(self._hits) >= MAX_TRACKED_CLIENTS:
                    self._evict(cutoff)
                window = self._hits.setdefault(key, deque())
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= self.limit:
                return False, max(1, int(window[0] + WINDOW_SECONDS - now) + 1)
            window.append(now)
            return True, 0

    def tracked(self) -> int:
        with self._lock:
            return len(self._hits)

    def _evict(self, cutoff: float) -> None:
        """Drop keys whose whole window has expired; clear everything if none have."""
        stale = [key for key, window in self._hits.items() if not window or window[-1] <= cutoff]
        for key in stale:
            del self._hits[key]
        if not stale:
            self._hits.clear()
