"""Map ST package strings (UFQFPN, UFBGA) onto the families engineers actually say."""

from __future__ import annotations

import re
from typing import Any

FAMILIES = ("LQFP", "QFN", "BGA", "WLCSP", "TSSOP", "SO")

# Longest token first so UFQFPN is not read as QFP.
_ALIASES = (
    ("UFQFPN", "QFN"),
    ("VFQFPN", "QFN"),
    ("WFQFPN", "QFN"),
    ("VQFPN", "QFN"),
    ("UQFN", "QFN"),
    ("QFN", "QFN"),
    ("LQFP", "LQFP"),
    ("TQFP", "LQFP"),
    ("UFBGA", "BGA"),
    ("TFBGA", "BGA"),
    ("LFBGA", "BGA"),
    ("VFBGA", "BGA"),
    ("EWLCSP", "WLCSP"),
    ("WLCSP", "WLCSP"),
    ("TSSOP", "TSSOP"),
    ("BGA", "BGA"),
    ("SO", "SO"),
)

_TOKEN_RE = re.compile(
    r"\b(" + "|".join(name for name, _ in _ALIASES) + r")(?![A-Za-z])",
    re.I,
)
_COMPOUND_RE = re.compile(
    r"\b(" + "|".join(name for name, _ in _ALIASES) + r")\s*-?\s*(\d{2,3})?(?![A-Za-z0-9])",
    re.I,
)
_PIN_BUDGET_RE = re.compile(
    r"(?:不超过|最多|以内|至多|不大于|max(?:imum)?)\s*(\d{2,3})\s*(?:引脚|脚|pins?)"
    r"|(\d{2,3})\s*(?:引脚|脚|pins?)\s*(?:以内|以下|及以下)",
    re.I,
)
_PIN_MENTION_RE = re.compile(
    r"(\d{2,3})\s*(?:引脚|脚|-?\s*pins?)\b",
    re.I,
)


def canonical_package(value: Any) -> str:
    text = str(value or "").upper()
    hit = _TOKEN_RE.search(text.replace("_", " "))
    if not hit:
        return ""
    token = hit.group(1).upper()
    for name, family in _ALIASES:
        if token == name:
            return family
    return ""


def package_matches(value: Any, choices: list[Any]) -> bool:
    got = canonical_package(value)
    if not got:
        haystack = str(value or "").lower()
        return any(str(choice).lower() in haystack for choice in choices)
    wanted = {canonical_package(item) for item in choices}
    wanted.discard("")
    return got in wanted


def normalize_package_name(value: Any) -> str:
    family = canonical_package(value)
    if family:
        return family
    raw = str(value or "").strip().upper()
    return raw if raw in FAMILIES else ""


def parse_package_and_pins(text: str) -> dict[str, Any]:
    must: dict[str, Any] = {}
    hit = _COMPOUND_RE.search(text)
    if hit:
        family = canonical_package(hit.group(1))
        if family:
            must["package_type"] = [family]
        if hit.group(2):
            pins = int(hit.group(2))
            must["pin_count"] = {"min": pins, "max": pins}
    budget = _PIN_BUDGET_RE.search(text)
    if budget:
        number = int(next(group for group in budget.groups() if group))
        must["pin_count"] = {"max": number}
        return must
    if "pin_count" not in must:
        mention = _PIN_MENTION_RE.search(text)
        if mention:
            must["pin_count"] = {"max": int(mention.group(1))}
    return must
