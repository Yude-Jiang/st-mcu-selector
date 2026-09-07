"""Paragraph-style shortlist conclusion. Facts only; never invent part numbers."""

from __future__ import annotations

from typing import Any

import app_fit
import nl_contrast
import ui_copy

SHARED_KEYS = (
    "core", "frequency_mhz", "flash_kb", "ram_kb",
    "package", "package_type", "pin_count", "motor_timers",
)
DIFF_KEYS = ("usb", "fdcan", "ethernet", "hrtim", "temperature_max_c")
DISCLAIMER = ui_copy.BRIEF["zh"]["disclaimer"]
LABELS = ui_copy.LABELS["zh"]
UNITS = {
    "frequency_mhz": " MHz",
    "flash_kb": " KB",
    "ram_kb": " KB",
    "temperature_max_c": " °C",
}


def for_shortlist(
    items: list[dict[str, Any]],
    competitor: dict[str, Any] | None = None,
    lang: str = "zh",
    application: str | None = None,
    series_prefix: list[str] | None = None,
) -> str:
    copy = ui_copy.brief(lang)
    cards = [item for item in items if item.get("part_number")][:3]
    if not cards:
        return copy["empty"] + "\n\n" + copy["disclaimer"]
    names = copy["list"].join(str(item["part_number"]) for item in cards)
    application = application or (competitor or {}).get("application")
    series_prefix = series_prefix or (competitor or {}).get("series_prefix")
    paras: list[str] = []
    shared = _shared_bits(cards, lang)
    if competitor:
        paras.append(_lead_compare(competitor, names, cards, shared, lang))
        gap = nl_contrast.series_gap_line(competitor, cards, series_prefix, lang)
        if gap:
            paras.append(gap)
    elif shared:
        paras.append(copy["shared"].format(names=names, shared=copy["clause"].join(shared)))
    else:
        paras.append(copy["cards"].format(names=names))
    app_para = app_fit.brief_paragraph(application, lang)
    if app_para:
        paras.append(app_para)
    diff = _diff_paragraph(cards, lang)
    if diff:
        paras.append(diff)
    risk = _risk_paragraph(cards, competitor, lang)
    if risk:
        paras.append(risk)
    paras.append(_closing(competitor, lang))
    return "\n\n".join(paras)


def for_compare(competitor: dict[str, Any], items: list[dict[str, Any]], lang: str = "zh") -> str:
    return for_shortlist(items, competitor, lang=lang)


def _fact(item: dict[str, Any], key: str) -> Any:
    facts = item.get("facts") if isinstance(item.get("facts"), dict) else {}
    return facts.get(key)


def _common(items: list[dict[str, Any]], key: str) -> Any:
    values = [_fact(item, key) for item in items]
    if not values or values[0] in (None, "", []):
        return None
    return values[0] if all(value == values[0] for value in values) else None


def _shared_bits(items: list[dict[str, Any]], lang: str) -> list[str]:
    bits: list[str] = []
    seen_package = False
    for key in SHARED_KEYS:
        value = _common(items, key)
        if value in (None, "", []):
            continue
        if key in {"package", "package_type"}:
            if seen_package:
                continue
            seen_package = True
        bits.append(ui_copy.fmt(key, value, lang))
    return bits


def _lead_compare(
    competitor: dict[str, Any],
    names: str,
    cards: list[dict[str, Any]],
    shared: list[str],
    lang: str,
) -> str:
    copy = ui_copy.brief(lang)
    labels = ui_copy.labels(lang)
    vendor = str(competitor.get("manufacturer") or "").strip()
    part = str(competitor.get("part_number") or copy["competitor"]).strip()
    title = f"{vendor} {part}".strip()
    specs = competitor.get("specs") if isinstance(competitor.get("specs"), dict) else {}
    contrasts = nl_contrast.contrast_lines(competitor, cards, lang)
    for key, unit in (("frequency_mhz", " MHz"), ("flash_kb", " KB"), ("ram_kb", " KB")):
        if any(bit.startswith(labels[key]) for bit in contrasts):
            continue
        st_value = _common(cards, key)
        other = specs.get(key)
        if st_value in (None, "", []) or other in (None, ""):
            continue
        try:
            st_num, other_num = float(st_value), float(other)
        except (TypeError, ValueError):
            continue
        label = labels[key]
        if st_num > other_num:
            contrasts.append(copy["higher"].format(label=label, st=st_value, unit=unit, other=other))
        elif st_num < other_num:
            contrasts.append(copy["lower"].format(label=label, st=st_value, unit=unit, other=other))
        else:
            contrasts.append(copy["same"].format(label=label, st=st_value, unit=unit, other=other))
    skip = tuple(f"{labels[key]} " for key in ("frequency_mhz", "flash_kb", "ram_kb"))
    extra = [bit for bit in shared if not bit.startswith(skip)]
    body = copy["semi"].join(contrasts + extra)
    if body:
        return copy["compare"].format(title=title, names=names, body=body)
    return copy["compare_short"].format(title=title, names=names)


def _diff_paragraph(cards: list[dict[str, Any]], lang: str) -> str:
    copy = ui_copy.brief(lang)
    chunks: list[str] = []
    for item in cards:
        extras: list[str] = []
        for key in DIFF_KEYS:
            if _common(cards, key) is not None:
                continue
            value = _fact(item, key)
            if value in (None, "", [], 0):
                continue
            extras.append(ui_copy.fmt(key, value, lang))
        if extras:
            chunks.append(copy["extra"].format(part=item["part_number"], extras=copy["list"].join(extras)))
    if not chunks:
        return ""
    return copy["diff"].format(chunks=copy["semi"].join(chunks))


def _risk_paragraph(cards: list[dict[str, Any]], competitor: dict[str, Any] | None, lang: str) -> str:
    copy = ui_copy.brief(lang)
    notes: list[str] = []
    specs = (competitor or {}).get("specs") if competitor else {}
    st_temp = _common(cards, "temperature_max_c")
    other_temp = specs.get("temperature_max_c") if isinstance(specs, dict) else None
    if st_temp not in (None, "") and other_temp not in (None, ""):
        try:
            if float(st_temp) < float(other_temp):
                notes.append(copy["temp"].format(st=st_temp, other=other_temp))
        except (TypeError, ValueError):
            pass
    for item in cards:
        for row in (item.get("risks") or [])[:2]:
            if row:
                notes.append(f"{item.get('part_number')}：{row}" if lang != "en" else f"{item.get('part_number')}: {row}")
    if not notes:
        return ""
    return copy["risk"].format(notes=copy["semi"].join(notes[:4]))


def _closing(competitor: dict[str, Any] | None, lang: str) -> str:
    copy = ui_copy.brief(lang)
    source = str((competitor or {}).get("source_note") or "").strip()
    if source:
        return f"{source} {copy['disclaimer']}"
    return copy["disclaimer"]
