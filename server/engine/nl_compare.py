"""Parse a competitor-comparison sentence into compare() input. Never invent ST part numbers."""

from __future__ import annotations

import json
import re
from typing import Any

import nl_brief
import nl_contrast
import nl_ground
import nl_must
import ui_copy


class NeedSpecs(ValueError):
    """The engineer named a competitor part but gave nothing verifiable to match on."""


COMPARE_HINTS = (
    "对照", "竞品", "对标", "替代", "替换",
    "nxp", "freescale", "infineon", "renesas", "microchip",
    "gigadevice", "nuvoton", "gd32", "mk64", "英飞凌",
    "瑞萨", "兆易", "新唐", "德州",
)
SIMILAR_HINTS = (
    "接近", "相当", "类似", "对标", "对照", "替换", "替代", "竞品",
    "close", "similar", "comparable", "equivalent", "replace", "replacement", "versus",
)
MANUFACTURERS = (
    ("NXP", ("nxp", "freescale", "飞思卡尔")),
    ("Infineon", ("infineon", "英飞凌", "cypress")),
    ("Renesas", ("renesas", "瑞萨")),
    ("TI", ("texas instruments", "德州", " ti")),
    ("Microchip", ("microchip", "atmel")),
    ("GigaDevice", ("gigadevice", "兆易", "gd32")),
    ("Nuvoton", ("nuvoton", "新唐")),
    ("Holtek", ("holtek", "合泰")),
    ("MindMotion", ("mindmotion", "灵动")),
)
SKIP_PARTS = re.compile(r"^(STM32|FDCAN|HRTIM|USB|LQFP|QFN|BGA|WLCSP|FLASH|RAM)\d*$", re.I)
PART_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{1,8}\d[A-Z0-9\-]{3,})(?![A-Z0-9])", re.I)
SOURCE_RE = re.compile(r"(来源|datasheet|数据手册|手册)\s*[:：]?\s*(.+)$", re.I)
URL_RE = re.compile(r"https?://\S+", re.I)
SPEC_KEYS = (
    "frequency_mhz", "flash_kb", "ram_kb", "pin_count", "package_type",
    "temperature_max_c", "fdcan", "usb", "motor_timers", "hrtim",
)
CORE_KEYS = {"frequency_mhz", "flash_kb", "ram_kb", "pin_count", "package_type"}
NEED_SPECS = (
    "只有竞品订货号还不能对照——本工具不凭料号推测规格。"
    "请上传该竞品的 datasheet（PDF 或清晰截图），"
    "或直接写出主频、Flash、RAM、封装等已核实的参数。"
)
REASON_PROMPT = {
    "zh": """根据竞品规格和 STM32 短名单 JSON，用中文说明为什么是这三颗。
只输出 JSON：{"answer":"中文"}。
answer 必须是 2～4 段，段与段空行：先写相对竞品的共同规格（内核、主频、存储器、封装），用人话写出倍数（例如主频差约 2.4 倍），再写三颗之间的外设差别，再写点名应用时库内有没有电机定时器/HRTIM 等，再写风险（如温度）和须核对项。
禁止提出 JSON 里没有的 STM32 订货号。禁止价格、交期、引脚兼容承诺。禁止编造 CoreMark、以太网或 JSON 没有的规格。
竞品规格来自用户上传的 datasheet 或用户自己填写，仍须核对厂家原始资料。这是短名单不是设计签核。
""",
    "en": """From the competitor specs and the STM32 shortlist JSON, explain why these three parts.
Output JSON only: {"answer":"English"}.
Write answer in natural native US English, 2–4 short paragraphs separated by blank lines: shared specs versus the competitor (core, clock, memory, package) with human ratios from the JSON numbers (for example clock differs by about 2.4×), then peripheral differences among the three, then named-application library fields such as motor timers or HRTIM, then risks (temperature, for example) and datasheet checks.
Do not name any STM32 orderable part that is not in the JSON. No price, lead-time, or pin-compatibility claims. Do not invent CoreMark, Ethernet, or any spec that is not in the JSON.
Competitor specs came from the engineer's upload or their own input; say they still must be checked against the vendor datasheet. This is a shortlist, not a design sign-off.
""",
}


def looks_like_compare(text: str) -> bool:
    lower = text.lower()
    part = _part_number(text)
    similar = any(word in text for word in SIMILAR_HINTS)
    vendor = any(hint in lower or hint in text for hint in COMPARE_HINTS)
    return bool(part and (similar or vendor)) or bool(vendor and similar)


def datasheet_ready(datasheet: dict[str, Any] | None) -> bool:
    if not isinstance(datasheet, dict):
        return False
    specs = datasheet.get("specs")
    return isinstance(specs, dict) and bool(sanitize_specs(specs))


def parse_competitor(text: str, datasheet: dict[str, Any] | None = None) -> dict[str, Any]:
    sheet = datasheet if isinstance(datasheet, dict) else {}
    sheet_specs = sanitize_specs(sheet.get("specs") if isinstance(sheet.get("specs"), dict) else {})
    if sheet_specs:
        return _from_datasheet(text, sheet, sheet_specs)
    cleaned = " ".join(str(text or "").split())
    rules = nl_must.parse_with_rules(cleaned)
    specs = _specs_from_must(rules.get("must") or {})
    mb = re.search(r"(\d+(?:\.\d+)?)\s*m\s*b(?:yte)?s?\s*(?:flash)?|flash\s*(\d+(?:\.\d+)?)\s*m", cleaned, re.I)
    if mb and "flash_kb" not in specs:
        specs["flash_kb"] = int(float(next(g for g in mb.groups() if g)) * 1024)
    manufacturer = next(
        (name for name, words in MANUFACTURERS if any(word in cleaned.lower() or word in text for word in words)),
        "",
    )
    part_number = _part_number(cleaned)
    source_note = _source_note(cleaned)
    notes = list(rules.get("notes") or [])
    if not part_number:
        raise ValueError("请写出要对标的竞品订货号，或改说需求规格、STM32 系列。")
    # No specs means no verifiable input. Asking the model to recall them from a part
    # number would make retrieval run on invented numbers, so stop and ask instead.
    if not specs:
        raise NeedSpecs(NEED_SPECS)
    if not source_note:
        source_note = "用户口述规格，未写 datasheet 出处；对照结果须自行核对官方资料。"
        notes.append(source_note)
    if not manufacturer:
        manufacturer = "未注明厂商"
    return {
        "manufacturer": str(manufacturer)[:120],
        "part_number": part_number[:120],
        "source_note": source_note[:1000],
        "specs": specs,
        "essential": list(specs),
        "limit": 3,
        "notes": notes,
    }


def explain_compare(competitor: dict[str, Any], shortlist: dict[str, Any], lang: str = "zh") -> str:
    items = shortlist.get("recommendations") or []
    if not items:
        return ui_copy.turn(lang)["empty_compare"]
    fallback = _reason_from_cards(competitor, items, lang)
    if not nl_must.llm_configured():
        return fallback
    # Everything here is retrieved or user-supplied, so it doubles as the whitelist the
    # answer is checked against. source_note stays out of it: it is free text, not data.
    grounding = {
        "competitor_specs": competitor.get("specs") or {},
        "contrast": nl_contrast.contrast_lines(competitor, items, lang),
        "shortlist": [
            {
                "part_number": item.get("part_number"),
                "score": item.get("score"),
                "facts": item.get("facts") or {},
                "comparisons": (item.get("comparisons") or [])[:8],
                "penalties": (item.get("penalties") or [])[:6],
                "decision_note": item.get("decision_note"),
            }
            for item in items[:3]
        ],
    }
    user = json.dumps(
        {
            "competitor": {
                "manufacturer": competitor.get("manufacturer"),
                "part_number": competitor.get("part_number"),
                "specs": grounding["competitor_specs"],
                "source_note": competitor.get("source_note"),
                "application": competitor.get("application"),
            },
            "contrast": grounding["contrast"],
            "shortlist": grounding["shortlist"],
        },
        ensure_ascii=False,
    )
    try:
        raw = nl_must.complete_json(REASON_PROMPT[ui_copy.normalize_lang(lang)], user, timeout=20) or {}
    except Exception:
        return fallback
    answer = nl_ground.enforce(str(raw.get("answer") or "").strip(), fallback, items, grounding)
    if answer == fallback:
        return fallback
    return nl_contrast.ensure_ratio_talk(answer, competitor, items, lang)


def sanitize_specs(raw: dict[str, Any]) -> dict[str, Any]:
    specs: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in SPEC_KEYS:
            continue
        if key == "package_type":
            name = str(value).upper()
            if name in nl_must.PACKAGES:
                specs[key] = name
            continue
        number = nl_must._constraint_number(value, "min")
        if number is not None:
            specs[key] = number
    return specs


def _reason_from_cards(competitor: dict[str, Any], items: list[dict[str, Any]], lang: str = "zh") -> str:
    return nl_brief.for_compare(competitor, items, lang=lang)


def _part_number(text: str) -> str:
    for match in PART_RE.finditer(text):
        token = match.group(1).upper()
        if SKIP_PARTS.match(token) or token.startswith("STM32"):
            continue
        return token
    return ""


def _source_note(text: str) -> str:
    url = URL_RE.search(text)
    if url:
        return url.group(0)
    hit = SOURCE_RE.search(text)
    if hit:
        return hit.group(0).strip()
    return ""


def _from_datasheet(text: str, sheet: dict[str, Any], specs: dict[str, Any]) -> dict[str, Any]:
    cleaned = " ".join(str(text or "").split())
    raw_part = str(sheet.get("part_number") or "").strip()
    if raw_part.upper().startswith("STM32"):
        raise ValueError("规格书订货号不能是 STM32。请上传竞品 datasheet，或把竞品规格粘进输入框。")
    part_number = raw_part.upper() if raw_part else _part_number(cleaned)
    if part_number.startswith("STM32"):
        raise ValueError("规格书订货号不能是 STM32。请上传竞品 datasheet，或把竞品规格粘进输入框。")
    if not part_number:
        part_number = "DATASHEET"
    manufacturer = str(sheet.get("manufacturer") or "").strip()
    if not manufacturer:
        manufacturer = next(
            (name for name, words in MANUFACTURERS if any(word in cleaned.lower() or word in text for word in words)),
            "",
        ) or "未注明厂商"
    source_note = str(sheet.get("source_note") or "").strip()
    if not source_note:
        source_note = "规格来自用户上传的 datasheet 摘录（未保存文件）。"
    notes = [str(item) for item in (sheet.get("notes") or []) if str(item).strip()]
    return {
        "manufacturer": manufacturer[:120],
        "part_number": part_number[:120],
        "source_note": source_note[:1000],
        "specs": specs,
        "essential": list(specs),
        "limit": 3,
        "notes": notes,
    }


def _specs_from_must(must: dict[str, Any]) -> dict[str, Any]:
    specs: dict[str, Any] = {}
    for key, value in must.items():
        if key == "package_type" and isinstance(value, list) and value:
            specs["package_type"] = value[0]
        elif isinstance(value, dict) and "min" in value:
            specs[key] = value["min"]
        elif isinstance(value, dict) and "max" in value:
            specs[key] = value["max"]
    return specs
