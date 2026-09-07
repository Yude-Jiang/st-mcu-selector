"""Human-readable spec gaps from library numbers only. Never invent CoreMark."""

from __future__ import annotations

from typing import Any

import ui_copy

RATIO_KEYS = ("frequency_mhz", "flash_kb", "ram_kb")
UNITS = {"frequency_mhz": " MHz", "flash_kb": " KB", "ram_kb": " KB"}
NEAR = 1.08
SERIES_GAP = 1.8


def format_times(ratio: float) -> str:
    if ratio >= 10:
        return str(int(round(ratio)))
    text = f"{ratio:.1f}"
    return text[:-2] if text.endswith(".0") else text


def _ratio(st_value: Any, other: Any) -> float | None:
    try:
        left, right = float(st_value), float(other)
    except (TypeError, ValueError):
        return None
    if left <= 0 or right <= 0:
        return None
    return max(left, right) / min(left, right)


def _fact(item: dict[str, Any], key: str) -> Any:
    facts = item.get("facts") if isinstance(item.get("facts"), dict) else {}
    return facts.get(key)


def _common(items: list[dict[str, Any]], key: str) -> Any:
    values = [_fact(item, key) for item in items]
    if not values or values[0] in (None, "", []):
        return None
    return values[0] if all(value == values[0] for value in values) else None


def contrast_line(key: str, st_value: Any, other: Any, lang: str = "zh") -> str:
    copy = ui_copy.brief(lang)
    labels = ui_copy.labels(lang)
    ratio = _ratio(st_value, other)
    if ratio is None:
        return ""
    unit = UNITS.get(key, "")
    label = labels.get(key, key)
    if ratio < NEAR:
        return copy["times_near"].format(label=label, st=st_value, unit=unit, other=other)
    times = format_times(ratio)
    if float(other) > float(st_value):
        return copy["times_comp"].format(
            label=label, times=times, st=st_value, unit=unit, other=other
        )
    return copy["times_st"].format(label=label, times=times, st=st_value, unit=unit, other=other)


def contrast_lines(
    competitor: dict[str, Any] | None,
    cards: list[dict[str, Any]],
    lang: str = "zh",
) -> list[str]:
    specs = (competitor or {}).get("specs") if competitor else {}
    if not isinstance(specs, dict):
        return []
    lines: list[str] = []
    for key in RATIO_KEYS:
        st_value = _common(cards, key)
        other = specs.get(key)
        if st_value in (None, "", []) or other in (None, ""):
            continue
        line = contrast_line(key, st_value, other, lang)
        if line:
            lines.append(line)
    return lines


def series_gap_line(
    competitor: dict[str, Any] | None,
    cards: list[dict[str, Any]],
    series_prefix: list[str] | None,
    lang: str = "zh",
) -> str:
    if not series_prefix:
        return ""
    specs = (competitor or {}).get("specs") if competitor else {}
    if not isinstance(specs, dict):
        return ""
    for key in ("frequency_mhz", "flash_kb"):
        st_value = _common(cards, key)
        other = specs.get(key)
        ratio = _ratio(st_value, other)
        if ratio is not None and ratio >= SERIES_GAP and float(other) > float(st_value):
            return ui_copy.brief(lang)["series_gap"]
    return ""


def has_human_ratio(text: str) -> bool:
    raw = str(text or "")
    lower = raw.lower()
    if "倍" in raw or "×" in raw:
        return True
    return any(token in lower for token in ("times", "x higher", "x lower", "differs by"))


def paragraph(
    competitor: dict[str, Any] | None,
    cards: list[dict[str, Any]],
    lang: str = "zh",
) -> str:
    copy = ui_copy.brief(lang)
    return copy["semi"].join(contrast_lines(competitor, cards, lang))


def ensure_ratio_talk(
    answer: str,
    competitor: dict[str, Any] | None,
    items: list[dict[str, Any]],
    lang: str = "zh",
) -> str:
    extras: list[str] = []
    contrast = paragraph(competitor, items, lang)
    if contrast and not has_human_ratio(answer):
        extras.append(contrast)
    gap = series_gap_line(competitor, items, (competitor or {}).get("series_prefix"), lang)
    if gap and gap not in (answer or ""):
        extras.append(gap)
    if extras:
        return "\n\n".join(extras + [answer])
    return answer
