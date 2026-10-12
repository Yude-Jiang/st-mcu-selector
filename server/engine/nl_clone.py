"""Recognise a competitor ordering code and prefill a card the user must confirm.

A harvested cell is evidence from one vendor page, not a verified spec, so this
module never feeds the engine directly. It fills a card, names its source, and
leaves the confirming to the user — DOMAIN rule 2 stays with the person.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
from typing import Any

import competitor_spec

# Prefixes we can recognise. Being here only means a code is read as a
# competitor's; whether any numbers exist depends on the catalogue.
VENDORS = (
    ("GD32", "GigaDevice"),
    ("APM32", "Geehy"),
    ("CMS32", "Cmsemicon"),
    ("CS32", "Chipsea"),
    ("PY32", "Puya"),
    ("N32", "Nations"),
    ("FM33", "FudanMicro"),
    ("FU68", "Fortior"),
    ("SH79F", "SinoWealth"),
    ("SH88F", "SinoWealth"),
    ("ESP32", "Espressif"),
)
# The harvest speaks the vendor page's vocabulary; the engine has its own names.
FIELD_ALIASES = {"sram_kb": "ram_kb"}
# Asked when the catalogue has nothing: the smallest set that narrows a shortlist.
ASK_FIELDS = ("frequency_mhz", "flash_kb", "package")
# A product selector states none of these, and they carry the engine's heaviest
# weights (mcu_recommender.DEFAULT_WEIGHTS), so a harvest never replaces the card.
NEVER_PUBLISHED = ("adc_channels", "opamps", "comparators", "motor_timers", "hrtim", "fdcan")

_PN_RE = re.compile(
    r"(?<![A-Za-z0-9])(" + "|".join(prefix for prefix, _ in VENDORS) + r")([A-Za-z0-9]{3,})",
    re.I,
)
_catalogue: dict[str, dict[str, Any]] | None = None


def catalogue_dir() -> pathlib.Path:
    override = str(os.environ.get("ST_MCU_COMPETITOR_DIR") or "").strip()
    if override:
        return pathlib.Path(override)
    return pathlib.Path(__file__).resolve().parents[2] / "data" / "competitor"


def load_catalogue(refresh: bool = False) -> dict[str, dict[str, Any]]:
    """Index harvested rows by exact ordering code. Rows without cells are kept
    so a page we tried and failed reads differently from one never attempted."""
    global _catalogue
    if _catalogue is not None and not refresh:
        return _catalogue
    rows: dict[str, dict[str, Any]] = {}
    directory = catalogue_dir()
    for path in sorted(directory.glob("*.jsonl")) if directory.is_dir() else []:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            code = competitor_spec.normalize_pn(row.get("part_number"))
            if code:
                rows[code] = row
    _catalogue = rows
    return rows


def detect(text: Any) -> dict[str, str] | None:
    """First competitor code in the text, with its vendor. STM32 never matches."""
    hit = _PN_RE.search(str(text or ""))
    if not hit:
        return None
    prefix = hit.group(1).upper()
    vendor = next(name for known, name in VENDORS if known == prefix)
    return {"part_number": (prefix + hit.group(2)).upper(), "vendor": vendor}


def lookup(part_number: Any) -> dict[str, Any] | None:
    """Exact code only. A sibling of the same series is a different part:
    GD32H759IIT6 has 2048K Flash where GD32H759IIK6 is a BGA176 — inheriting
    across a series is how a cross-reference tool does real damage."""
    code = competitor_spec.normalize_pn(part_number)
    return load_catalogue().get(code) if code else None


def confirm_card(text: Any) -> dict[str, Any] | None:
    """The card shown before any retrieval runs, or None when no code is present."""
    found = detect(text)
    if not found:
        return None
    row = lookup(found["part_number"])
    cells = dict((row or {}).get("cells") or {})
    known = {
        FIELD_ALIASES.get(field, field): {
            "value": cell.get("value"),
            "raw": cell.get("raw"),
            "url": (row or {}).get("url", ""),
            "fetched_at": (row or {}).get("fetched_at", ""),
        }
        for field, cell in cells.items()
        if isinstance(cell, dict)
    }
    return {
        "vendor": found["vendor"],
        "part_number": found["part_number"],
        "known": known,
        "ask": [field for field in ASK_FIELDS if FIELD_ALIASES.get(field, field) not in known],
        "never_published": list(NEVER_PUBLISHED),
        "status": (row or {}).get("status", "not-harvested"),
        "needs_confirm": True,
    }


def confirmed_specs(card: dict[str, Any], answers: dict[str, Any] | None = None) -> dict[str, Any]:
    """Specs to retrieve on, once the user has confirmed the card.

    The user's answer beats a harvested cell: they are looking at the datasheet
    and the harvest is one page read by a scraper.
    """
    specs = {
        field: cell.get("value")
        for field, cell in (card.get("known") or {}).items()
        if cell.get("value") is not None
    }
    for field, value in (answers or {}).items():
        key = FIELD_ALIASES.get(field, field)
        if value is not None and value != "":
            specs[key] = value
    return specs


def source_note(card: dict[str, Any]) -> str:
    """One line per harvested number, so a disputed value can be traced."""
    lines = []
    for field, cell in sorted((card.get("known") or {}).items()):
        url = cell.get("url") or "—"
        lines.append(f"{field}={cell.get('value')}（原文 {cell.get('raw')}；{url}）")
    if not lines:
        return "目录中没有这颗料号的抓取记录，请填写规格。"
    return "以下数字抓自厂商页面，未经 datasheet 核对，请确认：\n" + "\n".join(lines)
