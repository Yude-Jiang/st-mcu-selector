"""Application-fit notes from library fields. Not CubeMX or design sign-off."""

from __future__ import annotations

from typing import Any

from shortlist import application_label, field_label
import ui_copy

CARE_KEYS = {
    "motor_control": ("motor_timers", "hrtim", "adc_channels", "opamps", "fdcan"),
    "power_conversion": ("hrtim", "motor_timers", "adc_channels", "comparators"),
    "bms": ("adc_channels", "fdcan", "can", "temperature_max_c"),
    "industrial_control": ("fdcan", "can", "ethernet", "temperature_max_c"),
    "iot": ("usb", "security", "ram_kb"),
}


def _present(value: Any) -> bool:
    if value in (None, "", [], 0, "0"):
        return False
    return True


def judge_item(facts: dict[str, Any] | None, application: str | None, lang: str = "zh") -> str:
    app = str(application or "").lower()
    keys = CARE_KEYS.get(app)
    if not keys:
        return ""
    source = facts if isinstance(facts, dict) else {}
    copy = ui_copy.brief(lang)
    has_bits: list[str] = []
    miss_bits: list[str] = []
    for key in keys:
        label = field_label(key, lang)
        value = source.get(key)
        if _present(value):
            has_bits.append(f"{label} {value}")
        else:
            miss_bits.append(label)
    app_name = application_label(app, lang)
    has_text = copy["list"].join(has_bits) if has_bits else copy["app_none"]
    miss_text = copy["list"].join(miss_bits) if miss_bits else copy["app_none"]
    return copy["app_card"].format(app=app_name, has=has_text, miss=miss_text)


def care_labels(application: str | None, lang: str = "zh") -> str:
    keys = CARE_KEYS.get(str(application or "").lower()) or ()
    return ui_copy.brief(lang)["list"].join(field_label(key, lang) for key in keys)


def brief_paragraph(application: str | None, lang: str = "zh") -> str:
    app = str(application or "").lower()
    if app not in CARE_KEYS:
        return ""
    copy = ui_copy.brief(lang)
    return copy["app_para"].format(
        app=application_label(app, lang),
        keys=care_labels(app, lang),
    )


def annotate(items: list[dict[str, Any]], application: str | None, lang: str = "zh") -> None:
    if not application or str(application).lower() not in CARE_KEYS:
        return
    for item in items:
        note = judge_item(item.get("facts") if isinstance(item, dict) else {}, application, lang)
        if note:
            item["decision_note"] = note
