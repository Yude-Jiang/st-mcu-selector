"""Turn a requirement sentence into editable must fields. Never invent part numbers."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any

APPLICATIONS = {
    "motor_control": ("电机", "马达", "motor"),
    "power_conversion": ("电源", "pfc", "power"),
    "bms": ("电池", "bms"),
    "industrial_control": ("工业", "industrial"),
    "iot": ("物联网", "iot"),
}
MIN_FIELDS = {
    "frequency_mhz", "flash_kb", "ram_kb", "temperature_max_c",
    "fdcan", "usb", "motor_timers", "hrtim",
}
PACKAGES = ("LQFP", "QFN", "BGA", "WLCSP")
MAX_CHARS = 500
LLM_KEY_ENV = ("VITE_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY", "ST_MCU_LLM_KEY")

SYSTEM_PROMPT = """你把工程师的中文或英文需求改写成 JSON，供 STM32 短名单检索使用。
只输出 JSON 对象，不要料号，不要价格、交期、引脚兼容。
字段只能用：
- application: motor_control | power_conversion | bms | industrial_control | iot 或省略
- unknown_policy: allow_risk | exclude
- must: 对象。数值约束用 {"min": 数字}，引脚用 {"max": 数字}，封装用 ["LQFP"] 这类。
允许的 must 键：frequency_mhz, flash_kb, ram_kb, pin_count, temperature_max_c, fdcan, usb, motor_timers, hrtim, package_type。
用户没说的字段不要编。忽略价格和交期，可在 notes 数组说明忽略了什么。
"""


def parse_requirements(text: str) -> dict[str, Any]:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) < 4:
        raise ValueError("请用一句话写出可核对的规格，例如主频、Flash、封装。")
    if len(cleaned) > MAX_CHARS:
        raise ValueError(f"需求请控制在 {MAX_CHARS} 字以内。")
    rules = parse_with_rules(cleaned)
    model: dict[str, Any] | None = None
    notes = list(rules.get("notes") or [])
    try:
        model = call_model(cleaned)
    except Exception:
        if llm_configured():
            notes.append("大模型暂不可用，已用关键词抽取。")
    merged = merge_drafts(rules, model) if model else rules
    merged["notes"] = notes + list(merged.get("notes") or [])
    merged["source"] = "model" if model else "rules"
    if not merged.get("must") and not merged.get("application"):
        raise ValueError("没有抽出可检索的硬约束。请写主频、Flash、封装等，不要写价格或交期。")
    if not llm_configured() and merged["source"] == "rules":
        merged["notes"] = ["未配置大模型，已按关键词填入。请核对表单后再给出短名单。"] + list(merged["notes"])
    return merged


def llm_configured() -> bool:
    return bool(llm_api_key())


def llm_api_key() -> str:
    for name in LLM_KEY_ENV:
        value = str(os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def parse_with_rules(text: str) -> dict[str, Any]:
    lower = text.lower()
    notes: list[str] = []
    must: dict[str, Any] = {}
    application = next((key for key, words in APPLICATIONS.items() if any(word in lower for word in words)), None)
    freq = _first_number(r"(\d+(?:\.\d+)?)\s*mhz", lower)
    if freq:
        must["frequency_mhz"] = {"min": freq}
    flash = _first_number(r"flash\s*(\d+(?:\.\d+)?)\s*k", lower) or _first_number(
        r"(\d+(?:\.\d+)?)\s*kb?\s*flash", lower
    )
    if flash:
        must["flash_kb"] = {"min": flash}
    ram = _first_number(r"ram\s*(\d+(?:\.\d+)?)\s*k", lower) or _first_number(
        r"(\d+(?:\.\d+)?)\s*kb?\s*ram", lower
    )
    if ram:
        must["ram_kb"] = {"min": ram}
    temp = _temperature_max_c(text)
    if temp:
        must["temperature_max_c"] = {"min": temp}
    package_hit = re.search(r"\b(lqfp|qfn|bga|wlcsp)\s*-?\s*(\d{2,3})?\b", lower)
    if package_hit:
        must["package_type"] = [package_hit.group(1).upper()]
        if package_hit.group(2):
            must["pin_count"] = {"max": int(package_hit.group(2))}
    pins = _first_number(r"(\d{2,3})\s*引脚", text)
    if pins and "pin_count" not in must:
        must["pin_count"] = {"max": pins}
    if re.search(r"fdcan", lower):
        must["fdcan"] = {"min": 1}
    if re.search(r"\busb\b", lower):
        must["usb"] = {"min": 1}
    if "hrtim" in lower:
        must["hrtim"] = {"min": 1}
    if "电机定时器" in text or "motor timer" in lower:
        must["motor_timers"] = {"min": 1}
    if re.search(r"价格|交期|lead\s*time|price", lower):
        notes.append("已忽略价格和交期，本工具不承诺供货。")
    return {"must": must, "application": application, "unknown_policy": "allow_risk", "notes": notes}


def merge_drafts(rules: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    clean = sanitize_draft(model)
    must = dict(rules.get("must") or {})
    must.update(clean.get("must") or {})
    application = clean.get("application") or rules.get("application")
    policy = clean.get("unknown_policy") or rules.get("unknown_policy") or "allow_risk"
    notes = list(clean.get("notes") or [])
    return {"must": must, "application": application, "unknown_policy": policy, "notes": notes}


def sanitize_draft(raw: dict[str, Any] | None) -> dict[str, Any]:
    source = raw or {}
    must: dict[str, Any] = {}
    incoming = source.get("must") if isinstance(source.get("must"), dict) else {}
    for key, value in incoming.items():
        if key in MIN_FIELDS:
            number = _constraint_number(value, "min")
            if number is not None:
                must[key] = {"min": number}
        elif key == "pin_count":
            number = _constraint_number(value, "max") or _constraint_number(value, "min")
            if number is not None:
                must["pin_count"] = {"max": number}
        elif key == "package_type":
            names = value if isinstance(value, list) else [value]
            allowed = [str(item).upper() for item in names if str(item).upper() in PACKAGES]
            if allowed:
                must["package_type"] = allowed[:1]
    application = source.get("application")
    if application not in APPLICATIONS:
        application = None
    policy = source.get("unknown_policy")
    if policy not in {"allow_risk", "exclude"}:
        policy = "allow_risk"
    notes = [str(item) for item in source.get("notes") or [] if str(item).strip()]
    return {"must": must, "application": application, "unknown_policy": policy, "notes": notes}


def call_model(text: str) -> dict[str, Any] | None:
    return complete_json(SYSTEM_PROMPT, text, timeout=12)


def complete_json(system_prompt: str, user_text: str, timeout: int = 12) -> dict[str, Any] | None:
    api_key = llm_api_key()
    if not api_key:
        return None
    endpoint = os.environ.get("ST_MCU_LLM_URL", "https://api.deepseek.com/chat/completions")
    model = os.environ.get("ST_MCU_LLM_MODEL", "deepseek-chat")
    payload = json.dumps({
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    }).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"DeepSeek HTTP {exc.code}", file=sys.stderr, flush=True)
        raise
    content = body["choices"][0]["message"]["content"]
    return extract_json(content)


def extract_json(text: str) -> dict[str, Any]:
    cleaned = str(text).strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned)
    cleaned = re.sub(r"```$", "", cleaned).strip()
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("模型未返回对象")
    return parsed


def _temperature_max_c(text: str) -> float | None:
    explicit = _first_number(
        r"(\d+(?:\.\d+)?)\s*°\s*c|(\d+(?:\.\d+)?)\s*度|(\d+(?:\.\d+)?)\s*deg(?:ree)?s?\s*c",
        text,
    )
    if explicit is not None:
        return explicit
    contextual = _first_number(
        r"(?:工作温度|耐温|温度|ambient|\btemps?\b|\btemperature\b)[^\d]{0,16}(\d+(?:\.\d+)?)",
        text,
    )
    if contextual is not None:
        return contextual
    return _first_number(r"(?<![A-Za-z])(\d+(?:\.\d+)?)\s*c\b", text)


def _first_number(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    raw = next((group for group in match.groups() if group), None)
    if raw is None:
        return None
    number = float(raw)
    return int(number) if number.is_integer() else number


def _constraint_number(value: Any, key: str) -> float | None:
    if isinstance(value, dict):
        value = value.get(key, value.get("min") if key == "max" else value.get("max"))
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return int(number) if float(number).is_integer() else number
