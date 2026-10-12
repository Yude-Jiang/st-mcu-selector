"""Confirmation card for a competitor orderable. Recommendation starts only after the engineer submits values."""

from __future__ import annotations

import re
from typing import Any

import competitor_fetch
import competitor_parse
import nl_compare
import ui_copy

_FIELDS = (
    ("frequency_mhz", "主频 MHz", "Clock MHz", 1, 1000, False),
    ("flash_kb", "Flash KB", "Flash KB", 2, 8192, True),
    ("ram_kb", "RAM KB", "RAM KB", 1, 4096, True),
    ("i2c", "I2C", "I2C", 1, 16, False),
)
_STATUS = {
    "ok": "confirm_lead",
    "series": "confirm_series",
    "empty": "confirm_empty",
    "title-mismatch": "confirm_mismatch",
    "fetch-failed": "confirm_fetch_failed",
    "search-unavailable": "confirm_search_off",
    "not-found": "confirm_not_found",
    "rate-limited": "confirm_rate",
    "no-source": "confirm_no_source",
}
_VENDORS = (
    ("GD32", "GigaDevice"),
    ("APM32", "Geehy"),
    ("AT32", "Artery"),
    ("PY32", "Puya"),
    ("N32", "Nations"),
    ("CH32", "WCH"),
)


def _vendor(part: str) -> str:
    code = part.upper()
    for prefix, name in _VENDORS:
        if code.startswith(prefix):
            return name
    return ""


def _user_number(value: Any, low: float, high: float, scale_m: bool) -> int | float | None:
    text = str(value or "").strip()
    if not text or competitor_parse.has_hedge(text):
        return None
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(mhz|kb|k|mb|m)?", text, re.I)
    if not match:
        return None
    number = float(match.group(1))
    unit = (match.group(2) or "").lower()
    if scale_m and unit in {"m", "mb"}:
        number *= 1024
    if not (low <= number <= high):
        return None
    return int(number) if number.is_integer() else number


def user_specs(raw: dict[str, Any]) -> dict[str, Any]:
    specs: dict[str, Any] = {}
    for key, _zh, _en, low, high, scale_m in _FIELDS:
        number = _user_number(raw.get(key), low, high, scale_m)
        if number is not None:
            specs[key] = number
    package = competitor_parse.package_cell(str(raw.get("package") or "")[:80])
    if package:
        specs["package_type"] = package["package_type"]
        if package["pin_count"]:
            specs["pin_count"] = package["pin_count"]
    return nl_compare.sanitize_specs(specs)


def sheet_from_confirmed(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    incoming = raw.get("specs")
    if not isinstance(incoming, dict):
        return None
    specs = user_specs(incoming)
    if not specs:
        return None
    part = re.sub(r"[^A-Za-z0-9]", "", str(raw.get("part_number") or "")).upper()[:120]
    if part.startswith("STM32"):
        return None
    url = str(raw.get("source_url") or "")
    if not competitor_fetch.host_allowed(url):
        url = ""
    note = f"用户确认。页面 {url}" if url else "用户确认的竞品规格。"
    return {
        "specs": specs,
        "part_number": part,
        "manufacturer": _vendor(part),
        "source_note": note[:1000],
    }


def _field(key: str, label: str, cell: dict | None) -> dict[str, Any]:
    if not cell:
        return {"key": key, "label": label, "value": None, "raw": "", "url": ""}
    url = cell.get("url") if competitor_fetch.host_allowed(str(cell.get("url") or "")) else ""
    return {
        "key": key,
        "label": label,
        "value": cell.get("value"),
        "raw": str(cell.get("raw") or "")[:120],
        "url": url or "",
    }


def card_for(text: str, lang: str) -> dict[str, Any]:
    copy = ui_copy.turn(lang)
    english = ui_copy.normalize_lang(lang) == "en"
    part = nl_compare.competitor_part(text)
    try:
        found = competitor_fetch.lookup(part) if part else {"status": "no-source", "url": "", "cells": {}}
    except Exception:
        found = {"status": "fetch-failed", "url": "", "cells": {}}
    status = str(found.get("status") or "empty")
    cells = found.get("cells") if isinstance(found.get("cells"), dict) else {}
    url = found.get("url") if competitor_fetch.host_allowed(str(found.get("url") or "")) else ""
    fields = []
    for key, zh, en, _low, _high, _scale in _FIELDS:
        if key == "i2c":
            continue
        fields.append(_field(key, en if english else zh, cells.get(key)))
    fields.append(_field("package", "Package" if english else "封装", cells.get("package")))
    if "i2c" in cells:
        fields.append(_field("i2c", "I2C", cells.get("i2c")))
    return {
        "answer": copy.get(_STATUS.get(status, "confirm_empty"), copy["confirm_lead"]),
        "confirm_card": {
            "part_number": part,
            "status": status,
            "source_url": url or "",
            "fields": fields,
        },
    }
