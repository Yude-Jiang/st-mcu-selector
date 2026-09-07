"""Paragraph-style shortlist conclusion. Facts only; never invent part numbers."""

from __future__ import annotations

from typing import Any

LABELS = {
    "core": "内核",
    "frequency_mhz": "主频",
    "flash_kb": "Flash",
    "ram_kb": "RAM",
    "package": "封装",
    "package_type": "封装类型",
    "pin_count": "引脚",
    "temperature_max_c": "最高工作温度",
    "fdcan": "FDCAN",
    "usb": "USB",
    "ethernet": "Ethernet",
    "motor_timers": "电机定时器",
    "hrtim": "HRTIM",
}
UNITS = {
    "frequency_mhz": " MHz",
    "flash_kb": " KB",
    "ram_kb": " KB",
    "temperature_max_c": " °C",
}
SHARED_KEYS = (
    "core", "frequency_mhz", "flash_kb", "ram_kb",
    "package", "package_type", "pin_count", "motor_timers",
)
DIFF_KEYS = ("usb", "fdcan", "ethernet", "hrtim", "temperature_max_c")
DISCLAIMER = "这是短名单，不是设计签核。封装引脚、外设并发、认证、价格和供货须核对当前 datasheet。"


def for_shortlist(items: list[dict[str, Any]], competitor: dict[str, Any] | None = None) -> str:
    cards = [item for item in items if item.get("part_number")][:3]
    if not cards:
        return "没有满足硬约束的候选。可改硬约束后再推荐。\n\n" + DISCLAIMER
    names = "、".join(str(item["part_number"]) for item in cards)
    paras: list[str] = []
    shared = _shared_bits(cards)
    if competitor:
        paras.append(_lead_compare(competitor, names, cards, shared))
    elif shared:
        paras.append(f"当前短名单是 {names}。三颗共同规格：{'，'.join(shared)}。")
    else:
        paras.append(f"当前短名单是 {names}。规格见右侧卡片。")
    diff = _diff_paragraph(cards)
    if diff:
        paras.append(diff)
    risk = _risk_paragraph(cards, competitor)
    if risk:
        paras.append(risk)
    paras.append(_closing(competitor))
    return "\n\n".join(paras)


def for_compare(competitor: dict[str, Any], items: list[dict[str, Any]]) -> str:
    return for_shortlist(items, competitor)


def _fact(item: dict[str, Any], key: str) -> Any:
    facts = item.get("facts") if isinstance(item.get("facts"), dict) else {}
    return facts.get(key)


def _common(items: list[dict[str, Any]], key: str) -> Any:
    values = [_fact(item, key) for item in items]
    if not values or values[0] in (None, "", []):
        return None
    return values[0] if all(value == values[0] for value in values) else None


def _fmt(key: str, value: Any) -> str:
    label = LABELS.get(key, key)
    unit = UNITS.get(key, "")
    return f"{label} {value}{unit}"


def _shared_bits(items: list[dict[str, Any]]) -> list[str]:
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
        bits.append(_fmt(key, value))
    return bits


def _lead_compare(
    competitor: dict[str, Any],
    names: str,
    cards: list[dict[str, Any]],
    shared: list[str],
) -> str:
    vendor = str(competitor.get("manufacturer") or "").strip()
    part = str(competitor.get("part_number") or "竞品").strip()
    title = f"{vendor} {part}".strip()
    specs = competitor.get("specs") if isinstance(competitor.get("specs"), dict) else {}
    contrasts: list[str] = []
    for key, unit in (("frequency_mhz", " MHz"), ("flash_kb", " KB"), ("ram_kb", " KB")):
        st_value = _common(cards, key)
        other = specs.get(key)
        if st_value in (None, "", []) or other in (None, ""):
            continue
        try:
            st_num, other_num = float(st_value), float(other)
        except (TypeError, ValueError):
            continue
        label = LABELS[key]
        if st_num > other_num:
            contrasts.append(f"{label} {st_value}{unit}，高于竞品的 {other}{unit}")
        elif st_num < other_num:
            contrasts.append(f"{label} {st_value}{unit}，低于竞品的 {other}{unit}")
        else:
            contrasts.append(f"{label} {st_value}{unit}，与竞品相同")
    extra = [bit for bit in shared if not bit.startswith(("主频 ", "Flash ", "RAM "))]
    body = "；".join(contrasts + extra)
    if body:
        return f"对照 {title}，短名单是 {names}。{body}。"
    return f"对照 {title}，短名单是 {names}。"


def _diff_paragraph(cards: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for item in cards:
        extras: list[str] = []
        for key in DIFF_KEYS:
            if _common(cards, key) is not None:
                continue
            value = _fact(item, key)
            if value in (None, "", [], 0):
                continue
            extras.append(_fmt(key, value))
        if extras:
            chunks.append(f"{item['part_number']} 另有 {'、'.join(extras)}")
    if not chunks:
        return ""
    return "三颗之间的差别：" + "；".join(chunks) + "。"


def _risk_paragraph(cards: list[dict[str, Any]], competitor: dict[str, Any] | None) -> str:
    notes: list[str] = []
    specs = (competitor or {}).get("specs") if competitor else {}
    st_temp = _common(cards, "temperature_max_c")
    other_temp = specs.get("temperature_max_c") if isinstance(specs, dict) else None
    if st_temp not in (None, "") and other_temp not in (None, ""):
        try:
            if float(st_temp) < float(other_temp):
                notes.append(f"最高工作温度 {st_temp} °C，低于竞品的 {other_temp} °C")
        except (TypeError, ValueError):
            pass
    for item in cards:
        for row in (item.get("risks") or [])[:2]:
            if row:
                notes.append(f"{item.get('part_number')}：{row}")
    if not notes:
        return ""
    return "须注意：" + "；".join(notes[:4]) + "。"


def _closing(competitor: dict[str, Any] | None) -> str:
    source = str((competitor or {}).get("source_note") or "").strip()
    if source:
        return f"{source} {DISCLAIMER}"
    return DISCLAIMER
