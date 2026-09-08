"""Keep a long-lived instance's database in step with the ST bundle.

The freshness probe otherwise runs once, at process start. An instance that outlives
that check serves whatever it booted with, and nothing in the service can tell you it
is behind. Two pieces fix that:

- a background thread that re-probes on an interval and reloads only when the ETag moved;
- a recorded reading of the upstream fingerprint, so /api/health can answer "are we
  current?" from memory instead of calling ST on every poll (the page polls health
  every 8s, and that endpoint is deliberately exempt from rate limiting).

Refresh failures never take the serving database down. A probe that cannot reach ST
leaves the loaded database in place and only marks the reading as failed.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Any, Callable

import update_database as updater

DEFAULT_INTERVAL_HOURS = 168.0  # weekly
_SLEEP_SLICE = 30.0

_lock = threading.Lock()
_checked_at: str | None = None
_upstream_fingerprint: str | None = None
_check_error: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def interval_hours() -> float:
    """Hours between probes. 0 (or an unparsable value) disables the thread."""
    raw = str(os.environ.get("ST_MCU_DB_CHECK_INTERVAL_HOURS", "")).strip()
    if not raw:
        return DEFAULT_INTERVAL_HOURS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_INTERVAL_HOURS
    return value if value > 0 else 0.0


def database_url() -> str:
    return os.environ.get("ST_MCU_DB_URL", updater.DEFAULT_URL)


def record(fingerprint: str | None, error: str | None = None) -> None:
    global _checked_at, _upstream_fingerprint, _check_error
    with _lock:
        _checked_at = _now()
        _upstream_fingerprint = fingerprint
        _check_error = error


def probe_upstream(url: str | None = None) -> str | None:
    """HEAD the ST bundle and remember what it says. Returns the upstream fingerprint."""
    target = url or database_url()
    try:
        remote = updater.metadata(target)
    except Exception as exc:
        record(None, str(exc))
        return None
    fingerprint = updater.fingerprint(remote)
    record(fingerprint)
    return fingerprint


def snapshot(loaded_fingerprint: str | None) -> dict[str, Any]:
    """Freshness as currently known. Never touches the network."""
    with _lock:
        checked_at, upstream, error = _checked_at, _upstream_fingerprint, _check_error
    payload: dict[str, Any] = {"interval_hours": interval_hours()}
    if checked_at:
        payload["checked_at"] = checked_at
    if upstream:
        payload["upstream_fingerprint"] = upstream
    if error:
        payload["check_error"] = error
    if upstream and loaded_fingerprint:
        payload["up_to_date"] = upstream == loaded_fingerprint
    return payload


def _default_reload() -> Any:
    # Imported lazily and injected rather than referenced directly: this is an engine
    # module, and reaching up into the server entrypoint would invert the layering.
    # mode=always only runs after the fingerprint has already moved; if_missing would
    # no-op on a local file that already exists.
    from bootstrap import ensure_database

    return ensure_database(mode="always")


def refresh_once(
    on_reload: Callable[[dict[str, Any]], None] | None = None,
    reload_fn: Callable[[], Any] | None = None,
    loaded_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Probe upstream and reload only when the fingerprint moved.

    Returns the outcome; `reloaded` is True when a new database was installed.
    """
    url = database_url()
    upstream = probe_upstream(url)
    if upstream is None:
        return {"reloaded": False, "reason": "probe_failed"}
    if loaded_fingerprint and upstream == loaded_fingerprint:
        return {"reloaded": False, "reason": "already_current"}
    try:
        result = (reload_fn or _default_reload)()
    except Exception as exc:
        record(upstream, f"reload failed: {exc}")
        return {"reloaded": False, "reason": "reload_failed", "error": str(exc)}
    payload = result.as_dict()
    new_fingerprint = payload.get("fingerprint")
    if not new_fingerprint or new_fingerprint == loaded_fingerprint:
        return {"reloaded": False, "reason": "reload_noop", "cache": payload}
    if on_reload is not None:
        on_reload(payload)
    return {"reloaded": True, "cache": payload}


def _loop(
    stop: threading.Event,
    on_reload: Callable[[dict[str, Any]], None] | None,
    loaded_fn: Callable[[], str | None] | None,
) -> None:
    hours = interval_hours()
    while not stop.is_set():
        # Sleep in slices so a stop request is honoured without waiting out the interval.
        remaining = hours * 3600.0
        while remaining > 0 and not stop.is_set():
            nap = min(_SLEEP_SLICE, remaining)
            if stop.wait(nap):
                return
            remaining -= nap
        if stop.is_set():
            return
        loaded = loaded_fn() if loaded_fn is not None else None
        try:
            outcome = refresh_once(on_reload, loaded_fingerprint=loaded)
        except Exception as exc:  # a refresh must never kill the thread
            print(f"Database refresh check failed: {exc}", flush=True)
            continue
        if outcome.get("reloaded"):
            print(f"Database refreshed: {outcome.get('cache')}", flush=True)


def start(
    on_reload: Callable[[dict[str, Any]], None] | None = None,
    loaded_fn: Callable[[], str | None] | None = None,
) -> threading.Event | None:
    """Start the periodic probe. Returns None when the interval disables it."""
    if interval_hours() <= 0:
        return None
    stop = threading.Event()
    thread = threading.Thread(
        target=_loop,
        args=(stop, on_reload, loaded_fn),
        daemon=True,
        name="st-mcu-db-refresh",
    )
    thread.start()
    return stop


def reset_for_tests() -> None:
    global _checked_at, _upstream_fingerprint, _check_error
    with _lock:
        _checked_at = None
        _upstream_fingerprint = None
        _check_error = None
