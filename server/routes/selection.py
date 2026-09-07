from __future__ import annotations

from typing import Any, Literal, Optional, Union

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import engine_adapter
import readiness

router = APIRouter()

UnknownPolicy = Literal["allow_risk", "exclude"]
Application = Literal["motor_control", "power_conversion", "bms", "industrial_control", "iot"]
Constraint = Union[int, float, bool, str, list[str], dict[str, Any]]


class RecommendBody(BaseModel):
    must: dict[str, Constraint] = Field(default_factory=dict)
    prefer: dict[str, Constraint] = Field(default_factory=dict)
    application: Optional[Application] = None
    unknown_policy: UnknownPolicy = "allow_risk"
    limit: int = Field(default=3, ge=1, le=20)
    include_inactive: bool = False


class CompareBody(BaseModel):
    manufacturer: str = Field(min_length=1, max_length=120)
    part_number: str = Field(min_length=1, max_length=120)
    source_note: str = Field(min_length=5, max_length=1000)
    specs: dict[str, Union[int, float, bool, str, list[str]]]
    essential: list[str] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)
    limit: int = Field(default=3, ge=1, le=20)
    include_inactive: bool = False
    application: Optional[Application] = None
    lang: str = "zh"


def _ensure_ready() -> None:
    snap = readiness.snapshot()
    if snap["status"] == "starting":
        raise HTTPException(status_code=503, detail="器件库正在加载，请稍候。")
    if snap["status"] != "ready":
        raise HTTPException(status_code=503, detail=snap.get("error") or "器件库尚未就绪。")


def _run(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_ready()
    try:
        if action == "recommend":
            return engine_adapter.recommend(payload)
        if action == "compare":
            return engine_adapter.compare(payload)
        raise ValueError(f"Unknown action: {action}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/recommend")
def recommend(body: RecommendBody) -> dict[str, Any]:
    payload = body.model_dump(exclude_none=True)
    return _run("recommend", payload)


@router.post("/api/compare")
def compare(body: CompareBody) -> dict[str, Any]:
    payload = body.model_dump()
    return _run("compare", payload)


@router.get("/api/inspect")
def inspect(
    part_number: str = Query(min_length=3, max_length=120),
    include_attributes: bool = False,
) -> dict[str, Any]:
    _ensure_ready()
    try:
        return engine_adapter.inspect_part(part_number, include_attributes)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/suggest")
def suggest(
    q: str = Query(min_length=2, max_length=40),
    limit: int = Query(default=12, ge=1, le=20),
) -> dict[str, Any]:
    _ensure_ready()
    try:
        return {"items": engine_adapter.suggest_parts(q, limit)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
