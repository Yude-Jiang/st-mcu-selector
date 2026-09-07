"""Decompose a free-form question with DeepSeek. Never invent STM32 part numbers."""

from __future__ import annotations

import re
from typing import Any

import nl_must

INTENT_PROMPT = """你把工程师的任意一句话改写成 JSON，供 STM32 短名单检索。
只输出 JSON。禁止编造 STM32 订货号。禁止价格、交期、引脚兼容承诺。
可接受：新需求、任意厂商替换/性能接近、指定 STM32 系列、查看订货号、追问差别。
字段：
- intent: recommend | compare | inspect | explain | refuse
- inspect_part: 仅 inspect 时填用户写出的 STM32 订货号
- competitor: 要对标/替换/接近某颗非 STM32 料时 {"manufacturer":"厂商","part_number":"订货号"}。任意厂商。
- must: 硬约束。数值 {"min":数字}，引脚 {"max":数字}，封装 ["LQFP"]
  允许键 frequency_mhz, flash_kb, ram_kb, pin_count, temperature_max_c, fdcan, usb, motor_timers, hrtim, package_type
- series_prefix: 用户点名的 STM32 系列，如「从H5中找」→ ["STM32H5"]。没说不要编。
- application: motor_control | power_conversion | bms | industrial_control | iot 或省略
- notes: 字符串数组
intent：非 STM32 料要对标/接近/替换 → compare；只查一颗 STM32 → inspect；新需求出短名单 → recommend；问已给出的三颗为什么/差别 → explain；价格交期引脚兼容 → refuse。
用户没说的 must 不要编。不要在此 JSON 里编竞品规格数字，也不要编 STM32 料号。
"""
SERIES_STM32 = re.compile(r"(?<![A-Z0-9])STM32([A-Z][A-Z0-9]{0,6})(?![A-Z0-9])", re.I)
SERIES_SHORT = re.compile(
    r"(?:从|在)\s*([A-Z]\d)\s*(?:中|里|系列)?|(?:系列|里)\s*([A-Z]\d)\b|([A-Z]\d)\s*系列",
    re.I,
)
CLARIFY = (
    "这句话还不够检索。请补主频、Flash、封装或应用，"
    "或一颗要对标的竞品订货号，或 STM32 系列。"
    "也可以直接查看某颗 STM32 订货号。"
)


def extract_series_prefix(text: str) -> list[str]:
    found: list[str] = []
    for match in SERIES_STM32.finditer(text):
        token = normalize_prefix("STM32" + match.group(1))
        if token:
            found.append(token)
    for match in SERIES_SHORT.finditer(text):
        token = normalize_prefix(next((group for group in match.groups() if group), ""))
        if token:
            found.append(token)
    unique: list[str] = []
    for item in found:
        if item not in unique:
            unique.append(item)
    return unique[:3]


def normalize_prefix(raw: str) -> str:
    token = re.sub(r"[^A-Z0-9]", "", str(raw or "").upper())
    if not token:
        return ""
    if not token.startswith("STM32"):
        token = "STM32" + token
    if len(token) < 6:
        return ""
    return token[:12]


def from_model(text: str) -> dict[str, Any] | None:
    if not nl_must.llm_configured():
        return None
    try:
        raw = nl_must.complete_json(INTENT_PROMPT, text, timeout=16)
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    return sanitize(raw)


def sanitize(raw: dict[str, Any]) -> dict[str, Any]:
    intent = str(raw.get("intent") or "").strip()
    if intent not in {"recommend", "compare", "inspect", "explain", "refuse"}:
        intent = ""
    clean = nl_must.sanitize_draft({"must": raw.get("must") if isinstance(raw.get("must"), dict) else {}})
    series_prefix: list[str] = []
    raw_series = raw.get("series_prefix") or []
    if isinstance(raw_series, str):
        raw_series = [raw_series]
    for item in raw_series:
        token = normalize_prefix(str(item))
        if token and token not in series_prefix:
            series_prefix.append(token)
    competitor = raw.get("competitor") if isinstance(raw.get("competitor"), dict) else None
    part = str((competitor or {}).get("part_number") or "").strip().upper()
    vendor = str((competitor or {}).get("manufacturer") or "").strip()
    if part.startswith("STM32"):
        competitor = None
        part = ""
        if intent == "compare":
            intent = "recommend"
    elif part:
        competitor = {"manufacturer": vendor[:120], "part_number": part[:120]}
    inspect_part = str(raw.get("inspect_part") or "").strip().upper()
    if inspect_part and not inspect_part.startswith("STM32"):
        inspect_part = ""
    notes = [str(item) for item in (raw.get("notes") or []) if str(item).strip()]
    return {
        "intent": intent,
        "must": clean.get("must") or {},
        "series_prefix": series_prefix[:3],
        "competitor": competitor,
        "inspect_part": inspect_part or None,
        "application": clean.get("application"),
        "notes": notes,
        "source": "model",
    }
