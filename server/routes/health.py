from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

import engine_adapter
import nl_must
import readiness

router = APIRouter()


def _llm_status() -> dict[str, Any]:
    return {
        "configured": nl_must.llm_configured(),
        "model": os.environ.get("ST_MCU_LLM_MODEL", "deepseek-chat"),
    }


def _not_ready_payload() -> dict[str, Any]:
    snap = readiness.snapshot()
    if snap["status"] == "starting":
        payload: dict[str, Any] = {"status": "starting", "error": "器件库正在加载，请稍候。"}
    elif snap["status"] == "error":
        payload = {"status": "error", "error": snap.get("error") or "器件库加载失败。"}
    else:
        payload = {"status": snap["status"], "error": "器件库尚未就绪。"}
    payload["llm"] = _llm_status()
    return payload


@router.get("/healthz")
def healthz() -> PlainTextResponse:
    snap = readiness.snapshot()
    if snap["status"] == "ready":
        return PlainTextResponse("ok\n")
    return PlainTextResponse(snap["status"] + "\n", status_code=503)


@router.get("/api/health")
def api_health() -> JSONResponse:
    snap = readiness.snapshot()
    if snap["status"] != "ready":
        return JSONResponse(_not_ready_payload(), status_code=503)
    try:
        status = engine_adapter.database_status()
        payload: dict[str, Any] = {"status": "ok", **status}
        payload["llm"] = _llm_status()
        if snap.get("cache"):
            payload["cache"] = snap["cache"]
        return JSONResponse(payload)
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "error": str(exc), "llm": _llm_status()},
            status_code=503,
        )


@router.get("/api/database")
def database() -> JSONResponse:
    if readiness.snapshot()["status"] != "ready":
        return JSONResponse(_not_ready_payload(), status_code=503)
    try:
        return JSONResponse(engine_adapter.database_status())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
