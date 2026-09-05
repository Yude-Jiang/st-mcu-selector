from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

ENGINE = Path(__file__).resolve().parents[1] / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))
import nl_must  # noqa: E402

router = APIRouter()


class ParseBody(BaseModel):
    text: str = Field(min_length=4, max_length=500)


@router.post("/api/parse-requirements")
def parse_requirements(body: ParseBody) -> dict:
    try:
        return nl_must.parse_requirements(body.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="需求解析失败，请改填下方表单。") from exc
