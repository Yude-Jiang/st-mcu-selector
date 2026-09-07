from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

import engine_adapter
import readiness

ENGINE = Path(__file__).resolve().parents[1] / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))
import nl_brief  # noqa: E402
import nl_compare  # noqa: E402
import nl_datasheet  # noqa: E402
import nl_must  # noqa: E402
import nl_turn  # noqa: E402

router = APIRouter()


class ParseBody(BaseModel):
    text: str = Field(min_length=4, max_length=500)


class CandidateIn(BaseModel):
    part_number: str = Field(min_length=1, max_length=120)
    score: Optional[float] = None
    facts: dict[str, Any] = Field(default_factory=dict)
    matches: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class DatasheetIn(BaseModel):
    specs: dict[str, Any] = Field(default_factory=dict)
    part_number: str = ""
    manufacturer: str = ""
    source_note: str = ""
    notes: list[str] = Field(default_factory=list)


class TurnBody(BaseModel):
    text: str = Field(min_length=2, max_length=500)
    must: dict[str, Any] = Field(default_factory=dict)
    application: Optional[str] = None
    unknown_policy: str = "allow_risk"
    candidates: list[CandidateIn] = Field(default_factory=list, max_length=3)
    history: list[str] = Field(default_factory=list, max_length=4)
    datasheet: Optional[DatasheetIn] = None
    lang: str = "zh"


def _ready() -> None:
    snap = readiness.snapshot()
    if snap["status"] != "ready":
        raise HTTPException(status_code=503, detail=snap.get("error") or "器件库尚未就绪。")


def _ui_lang(raw: str | None) -> str:
    return "en" if str(raw or "").lower().startswith("en") else "zh"


def _attach_shortlist(result: dict, shortlist: dict, lang: str = "zh") -> dict:
    result["recommendations"] = shortlist.get("recommendations") or []
    result["disclaimer"] = shortlist.get("disclaimer")
    result["rejected_by_hard_constraints"] = shortlist.get("rejected_by_hard_constraints")
    result["mode"] = shortlist.get("mode") or result.get("intent")
    if result.get("intent") == "compare" and result.get("compare"):
        result["answer"] = nl_compare.explain_compare(result["compare"], shortlist, lang=lang)
    else:
        result["answer"] = nl_brief.for_shortlist(
            result["recommendations"],
            lang=lang,
            application=result.get("application"),
            series_prefix=result.get("series_prefix"),
        )
    return result


@router.post("/api/parse-requirements")
def parse_requirements(body: ParseBody) -> dict:
    try:
        return nl_must.parse_requirements(body.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="需求解析失败，请改填左侧表单。") from exc


@router.post("/api/parse-datasheet")
def parse_datasheet(file: Optional[UploadFile] = File(default=None)) -> dict:
    if file is None:
        raise HTTPException(status_code=400, detail="请上传 PDF 规格书或清晰截图。")
    try:
        # Read one byte past the cap instead of the whole upload: the limit has to bite
        # before the bytes are in memory, or an oversized post can exhaust the instance.
        data = file.file.read(nl_datasheet.MAX_BYTES + 1)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="无法读取上传文件。") from exc
    if len(data) > nl_datasheet.MAX_BYTES:
        raise HTTPException(status_code=413, detail="文件请控制在 8 MB 以内。")
    try:
        return nl_datasheet.parse_bytes(data, file.filename or "upload", file.content_type or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="规格书解析失败，请把主频、Flash、封装写进输入框。") from exc


@router.post("/api/turn")
def turn(body: TurnBody) -> dict:
    lang = _ui_lang(body.lang)
    try:
        result = nl_turn.handle(
            body.text,
            body.must,
            body.application,
            body.unknown_policy,
            [item.model_dump() for item in body.candidates],
            body.history,
            body.datasheet.model_dump() if body.datasheet else None,
            lang,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="无法处理这句话，请改写需求、竞品对照或订货号。") from exc
    if result.get("inspect_part"):
        _ready()
        result["inspect"] = engine_adapter.inspect_part(result["inspect_part"])
        return result
    if result.get("compare"):
        _ready()
        try:
            shortlist = engine_adapter.compare(result["compare"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _attach_shortlist(result, shortlist, lang)
    if not result.get("rerecommend"):
        return result
    _ready()
    try:
        shortlist = engine_adapter.recommend({
            "must": result.get("must") or {},
            "application": result.get("application"),
            "unknown_policy": result.get("unknown_policy") or "allow_risk",
            "limit": 3,
            "series_prefix": result.get("series_prefix") or [],
            "lang": lang,
        })
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _attach_shortlist(result, shortlist, lang)
