from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routes.health import router as health_router
from routes.selection import router as selection_router

WEB_DIR = Path(__file__).resolve().parents[1] / "web"

app = FastAPI(title="ST MCU Selector", version="0.1.0")
app.include_router(health_router)
app.include_router(selection_router)
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
