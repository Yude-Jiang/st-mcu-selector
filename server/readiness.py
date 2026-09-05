from __future__ import annotations

import threading
from typing import Any, Literal

Status = Literal["starting", "ready", "error"]

_lock = threading.Lock()
_status: Status = "starting"
_error: str | None = None
_cache: dict[str, Any] = {}


def mark_ready(cache: dict[str, Any] | None = None) -> None:
    global _status, _error, _cache
    with _lock:
        _status = "ready"
        _error = None
        _cache = dict(cache or {})


def mark_error(exc: BaseException) -> None:
    global _status, _error, _cache
    with _lock:
        _status = "error"
        _error = str(exc)
        _cache = {}


def snapshot() -> dict[str, Any]:
    with _lock:
        payload: dict[str, Any] = {"status": _status}
        if _error:
            payload["error"] = _error
        if _cache:
            payload["cache"] = dict(_cache)
        return payload


def require_ready() -> dict[str, Any]:
    current = snapshot()
    if current["status"] == "ready":
        return current
    return current
