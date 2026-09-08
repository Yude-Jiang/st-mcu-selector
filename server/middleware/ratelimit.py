"""Sliding-window rate limit for the public Cloud Run service.

The @st.com gate on the page is cosmetic — the container answers `--allow-unauthenticated`,
so every endpoint is reachable with curl. Two budgets run together:

- per client, so one engineer looping a script cannot crowd out colleagues;
- global, because X-Forwarded-For is caller-supplied and a spoofed header would walk
  straight through a per-client bucket. The global ceiling is what actually caps spend
  on the DeepSeek key.

Buckets live in process memory. With `--max-instances 1` that is exact; if the service is
scaled out later each instance keeps its own counters and the effective global ceiling
becomes `limit x instances`, so lower ST_MCU_RATE_* accordingly or move to a shared store.
"""

from __future__ import annotations

import os
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from middleware.budget import Budget

# Endpoints that spend money or CPU: DeepSeek calls, OCR, PDF parsing.
COSTLY_PATHS = frozenset({
    "/api/turn",
    "/api/parse-requirements",
    "/api/parse-datasheet",
})
# Endpoints that only read the local SQLite database.
CHEAP_PATHS = frozenset({
    # db-freshness reaches sw-center.st.com, so it must never be exempt: an open
    # endpoint that proxies to ST is a way to hammer ST through us.
    "/api/db-freshness",
    "/api/recommend",
    "/api/compare",
    "/api/inspect",
    "/api/suggest",
})
# Probes and the static page are never limited; Cloud Run needs /healthz to stay answerable.
EXEMPT_PATHS = frozenset({"/healthz", "/api/health", "/api/database"})

RETRY_MESSAGE = {
    "zh": "请求过于频繁，请稍后再试。",
    "en": "Too many requests. Please retry shortly.",
}


def _env_int(name: str, default: int) -> int:
    try:
        value = int(str(os.environ.get(name, "")).strip() or default)
    except ValueError:
        return default
    return value if value > 0 else default


def client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        # Cloud Run puts the caller first. Spoofable, which is why the global budget exists.
        first = forwarded.split(",")[0].strip()
        if first:
            return first[:64]
    client = request.client
    return client.host if client else "unknown"


def _lang(request: Request) -> str:
    accept = request.headers.get("accept-language", "").lower()
    return "en" if accept.startswith("en") else "zh"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.costly = Budget(_env_int("ST_MCU_RATE_COSTLY_PER_MIN", 15))
        self.cheap = Budget(_env_int("ST_MCU_RATE_CHEAP_PER_MIN", 90))
        self.global_costly = Budget(_env_int("ST_MCU_RATE_GLOBAL_COSTLY_PER_MIN", 60))
        self.global_cheap = Budget(_env_int("ST_MCU_RATE_GLOBAL_CHEAP_PER_MIN", 600))

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in EXEMPT_PATHS or (path not in COSTLY_PATHS and path not in CHEAP_PATHS):
            return await call_next(request)
        costly = path in COSTLY_PATHS
        per_client = self.costly if costly else self.cheap
        overall = self.global_costly if costly else self.global_cheap
        now = time.monotonic()
        # Per client first, so one noisy caller is refused without eating global quota
        # that its colleagues still need. A spoofed key skips this and meets the ceiling.
        allowed, retry = per_client.allow(client_key(request), now)
        if allowed:
            allowed, retry = overall.allow("*", now)
        if allowed:
            return await call_next(request)
        return JSONResponse(
            {"detail": RETRY_MESSAGE[_lang(request)]},
            status_code=429,
            headers={"Retry-After": str(retry)},
        )
