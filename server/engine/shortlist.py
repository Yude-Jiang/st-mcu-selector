"""Shortlist grouping and Chinese copy. Scoring math stays in mcu_recommender."""

from __future__ import annotations

import re
from typing import Any

FIELD_LABELS = {
    "core": "内核",
    "frequency_mhz": "主频",
    "flash_kb": "Flash",
    "ram_kb": "RAM",
    "package": "封装",
    "package_type": "封装类型",
    "pin_count": "引脚",
    "temperature_min_c": "最低工作温度",
    "temperature_max_c": "最高工作温度",
    "voltage_min_v": "最低电压",
    "voltage_max_v": "最高电压",
    "adc_channels": "ADC 通道",
    "adc_units": "ADC 单元",
    "opamps": "运放",
    "comparators": "比较器",
    "dac_channels": "DAC 通道",
    "can": "CAN",
    "fdcan": "FDCAN",
    "usb": "USB",
    "usb_types": "USB 类型",
    "ethernet": "Ethernet",
    "ethernet_speed_mbps": "Ethernet 速率",
    "motor_timers": "电机定时器",
    "hrtim": "HRTIM",
    "timers": "定时器",
    "fpu": "FPU",
    "security": "安全能力",
}

APPLICATION_LABELS = {
    "motor_control": "电机控制",
    "power_conversion": "电源变换",
    "bms": "电池管理",
    "industrial_control": "工业控制",
    "iot": "物联网",
}

# STM32H503CBT6 → STM32H503; STM32L4R5ZI → STM32L4R5; STM32WBA52CE → STM32WBA52
_SERIES = re.compile(r"^(STM32(?:WBA|WB|WL|MP|[A-Z])\d+(?:[A-Z]\d+)?)", re.IGNORECASE)
_PACKING = re.compile(r"[-_]?TR$", re.IGNORECASE)


def field_label(field: str) -> str:
    return FIELD_LABELS.get(field, field)


def application_label(application: str) -> str:
    key = str(application or "").lower()
    return APPLICATION_LABELS.get(key, application)


def format_points(value: float) -> str:
    return f"{round(float(value), 1):g}"


def series_group(part_number: str, rpn: str | None = None) -> str:
    for raw in (rpn, part_number):
        text = _PACKING.sub("", str(raw or "").strip().upper())
        match = _SERIES.match(text)
        if match:
            return match.group(1).upper()
    fallback = str(rpn or part_number or "").strip().upper()
    return fallback or "UNKNOWN"


def package_alt(item: dict[str, Any]) -> str:
    facts = item.get("facts") or {}
    package = facts.get("package") or facts.get("package_type") or ""
    pins = facts.get("pin_count")
    part = str(item.get("part_number") or "")
    bits = [str(package)] if package else []
    if pins not in (None, ""):
        bits.append(f"{pins:g} 引脚" if isinstance(pins, float) else f"{pins} 引脚")
    if part:
        bits.append(part)
    return " · ".join(bits)


def diversify_by_series(ranked: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    extras: dict[str, list[str]] = {}
    for item in ranked:
        series = series_group(str(item.get("part_number") or ""), item.get("rpn"))
        item["series"] = series
        if series not in extras:
            if len(picked) >= limit:
                continue
            extras[series] = []
            picked.append(item)
            continue
        alt = package_alt(item)
        if alt and alt not in extras[series]:
            extras[series].append(alt)
    for item in picked:
        item["other_packages"] = extras.get(item["series"], [])[:6]
    return picked
