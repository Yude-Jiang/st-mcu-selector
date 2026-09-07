"""Keep model prose grounded in retrieved data.

The engine owns every fact. DeepSeek only phrases what retrieval already returned,
so an answer may name a part or quote a number only if that value was in the JSON
we sent it. Anything else is treated as invention and the caller falls back to the
deterministic brief in nl_brief.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

PART_TOKEN = re.compile(r"STM32[A-Z0-9]+", re.I)
NUMBER_TOKEN = re.compile(r"\d+(?:\.\d+)?")
# Identifiers carry digits that are not measurements: STM32G474RET6 would otherwise
# donate 474 to the whitelist and license a nearby invented "480 MHz". Anything that
# starts with a letter and contains a digit is a name, so drop it before counting.
IDENTIFIER_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_\-]*\d[A-Za-z0-9_\-]*")

# Ranks and shortlist size ("第 2 颗", "these 3 parts") are about the answer's own
# structure, not about product data, so they never need a source row.
FREE_INTEGERS = frozenset({0.0, 1.0, 2.0, 3.0})
TOLERANCE = 0.05


def allowed_parts(items: Iterable[dict[str, Any]]) -> list[str]:
    parts: list[str] = []
    for item in items or []:
        value = str((item or {}).get("part_number") or "").strip().upper()
        if value and value not in parts:
            parts.append(value)
    return parts


def invented_part(answer: str, items: Iterable[dict[str, Any]]) -> bool:
    """True when the prose names an STM32 part the shortlist does not contain."""
    allowed = allowed_parts(items)
    tokens = PART_TOKEN.findall(str(answer or ""))
    if not allowed:
        return bool(tokens)
    for token in tokens:
        upper = token.upper()
        # A series prefix (STM32G4) or a suffix variant of a listed part is fine;
        # both still point at something retrieval actually returned.
        if any(part.startswith(upper) or upper.startswith(part) for part in allowed):
            continue
        return True
    return False


def measurements(text: str) -> list[float]:
    """Numbers that state a quantity, with names such as STM32G474RET6 removed first."""
    stripped = IDENTIFIER_TOKEN.sub(" ", str(text or ""))
    values: list[float] = []
    for token in NUMBER_TOKEN.findall(stripped):
        try:
            values.append(float(token))
        except ValueError:
            continue
    return values


def payload_numbers(payload: Any) -> set[float]:
    """Every number the model was given, as the whitelist for numbers it may write."""
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, ensure_ascii=False, default=str)
    return set(measurements(text))


def _near(value: float, target: float) -> bool:
    return abs(value - target) <= TOLERANCE * max(abs(target), 1.0)


def _derived(target: float) -> tuple[float, ...]:
    """Restatements of one source number that stay faithful to it."""
    return (
        target,
        round(target),
        round(target, 1),
        target / 1024.0,          # KB quoted as MB
        target * 1024.0,          # MB quoted as KB
        (target - 1.0) * 100.0,   # ratio quoted as "40% higher"
        target * 100.0,           # ratio quoted as a percentage
    )


def grounded_number(value: float, allowed: set[float]) -> bool:
    if value in FREE_INTEGERS:
        return True
    for target in allowed:
        for candidate in _derived(target):
            if _near(value, candidate):
                return True
    return False


def invented_number(answer: str, allowed: set[float]) -> bool:
    """True when the prose quotes a figure that was not in the retrieved data."""
    return any(not grounded_number(value, allowed) for value in measurements(answer))


def verify(answer: str, items: Iterable[dict[str, Any]], payload: Any) -> bool:
    """True when every part number and figure in the prose traces back to retrieval."""
    text = str(answer or "").strip()
    if not text:
        return False
    if invented_part(text, items):
        return False
    return not invented_number(text, payload_numbers(payload))


def enforce(answer: str, fallback: str, items: Iterable[dict[str, Any]], payload: Any) -> str:
    """Return the model prose when it is grounded, otherwise the deterministic brief."""
    return answer if verify(answer, items, payload) else fallback
