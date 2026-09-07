from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from middleware.ratelimit import RateLimitMiddleware
from routes.health import router as health_router
from routes.parse import router as parse_router
from routes.selection import router as selection_router

WEB_DIR = Path(__file__).resolve().parents[1] / "web"

app = FastAPI(title="ST MCU Selector", version="0.1.0")
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Content-Type"],
    max_age=600,
)
app.include_router(health_router)
app.include_router(selection_router)
app.include_router(parse_router)
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
