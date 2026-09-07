"""Bilingual labels and brief sentences for shortlist answers."""

from __future__ import annotations

from typing import Any

LABELS = {
    "zh": {
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
    },
    "en": {
        "core": "Core",
        "frequency_mhz": "Clock",
        "flash_kb": "Flash",
        "ram_kb": "RAM",
        "package": "Package",
        "package_type": "Package type",
        "pin_count": "Pins",
        "temperature_max_c": "Max operating temperature",
        "fdcan": "FDCAN",
        "usb": "USB",
        "ethernet": "Ethernet",
        "motor_timers": "Motor timers",
        "hrtim": "HRTIM",
    },
}

BRIEF = {
    "zh": {
        "disclaimer": "这是短名单，不是设计签核。封装引脚、外设并发、认证、价格和供货须核对当前 datasheet。",
        "empty": "没有满足硬约束的候选。可改硬约束后再推荐。",
        "shared": "当前短名单是 {names}。三颗共同规格：{shared}。",
        "cards": "当前短名单是 {names}。规格见右侧卡片。",
        "compare": "对照 {title}，短名单是 {names}。{body}。",
        "compare_short": "对照 {title}，短名单是 {names}。",
        "higher": "{label} {st}{unit}，高于竞品的 {other}{unit}",
        "lower": "{label} {st}{unit}，低于竞品的 {other}{unit}",
        "same": "{label} {st}{unit}，与竞品相同",
        "times_comp": "{label}差约 {times} 倍（竞品 {other}{unit}，短名单 {st}{unit}）",
        "times_st": "{label}短名单约高 {times} 倍（{st}{unit}，竞品 {other}{unit}）",
        "times_near": "{label}接近（短名单 {st}{unit}，竞品 {other}{unit}）",
        "series_gap": "点名系列里主频或存储达不到竞品；下列是该系列内最接近的候选，不是性能对等。",
        "app_para": "你点了{app}。工程上先看库内是否有{keys}；有值不代表引脚和并发已核对。",
        "app_card": "{app}：库内有 {has}；未见 {miss}。这是库内字段，不是设计签核。",
        "app_none": "无",
        "diff": "三颗之间的差别：{chunks}。",
        "extra": "{part} 另有 {extras}",
        "risk": "须注意：{notes}。",
        "temp": "最高工作温度 {st} °C，低于竞品的 {other} °C",
        "competitor": "竞品",
        "list": "、",
        "clause": "，",
        "semi": "；",
    },
    "en": {
        "disclaimer": "This is a shortlist, not a design sign-off. Package pins, concurrent peripherals, certification, price, and supply need the current datasheet.",
        "empty": "No candidates meet the hard constraints. Change the constraints and recommend again.",
        "shared": "Current shortlist: {names}. Shared specs: {shared}.",
        "cards": "Current shortlist: {names}. Specs are on the cards.",
        "compare": "Compared with {title}, the shortlist is {names}. {body}.",
        "compare_short": "Compared with {title}, the shortlist is {names}.",
        "higher": "{label} {st}{unit}, higher than the competitor's {other}{unit}",
        "lower": "{label} {st}{unit}, lower than the competitor's {other}{unit}",
        "same": "{label} {st}{unit}, matching the competitor",
        "times_comp": "{label} differs by about {times}× (competitor {other}{unit} vs shortlist {st}{unit})",
        "times_st": "{label} on the shortlist is about {times}× higher ({st}{unit} vs competitor {other}{unit})",
        "times_near": "{label} is close (shortlist {st}{unit}, competitor {other}{unit})",
        "series_gap": "In the named series, clock or memory cannot match the competitor. These are the closest in-series parts, not performance peers.",
        "app_para": "You named {app}. Check whether the library shows {keys}; a value is not a pinmux or concurrency sign-off.",
        "app_card": "{app}: library shows {has}; not seen: {miss}. Library fields only, not a design sign-off.",
        "app_none": "none",
        "diff": "Where the three differ: {chunks}.",
        "extra": "{part} also has {extras}",
        "risk": "Check: {notes}.",
        "temp": "Max operating temperature {st} °C, lower than the competitor's {other} °C",
        "competitor": "competitor",
        "list": ", ",
        "clause": ", ",
        "semi": "; ",
    },
}

TURN = {
    "zh": {
        "need": "请写出需求、竞品对照或要问的问题。",
        "refuse": "本工具不承诺价格、交期或引脚兼容。可以改硬约束重新推荐，或一句话做竞品对照。",
        "inspect": "正在核对 {part} 在库里的身份。",
        "compare": "已按竞品规格对照 STM32。规格若来自模型回忆，须核对厂家 datasheet。",
        "refine": "已按这句话更新硬约束并重新推荐。左侧表单可再改。",
        "series_note": "点名系列优先：竞品主频/存储只作接近排序，不要求 STM32 达到同等数字。",
        "clarify": "这句话还不够检索。请补主频、Flash、封装或应用，或一颗要对标的竞品订货号，或 STM32 系列。也可以直接查看某颗 STM32 订货号。",
        "llm_down": "大模型暂不可用，以上仅复述库内事实。",
        "empty_compare": "指定系列里没有筛出短名单卡片，不能据此编造 STM32 订货号。竞品规格若来自模型回忆，主频或 Flash 可能远高于该系列。请在该系列内按接近程度再查，或放宽系列后对照。",
    },
    "en": {
        "need": "Describe a requirement, a competitor compare, or a question.",
        "refuse": "This tool does not quote price, lead time, or pin compatibility. Tighten the hard constraints and recommend again, or compare a competitor part in one sentence.",
        "inspect": "Checking how {part} is listed in the library.",
        "compare": "STM32 parts are ranked against the competitor specs. If those specs were recalled by the model, confirm them on the vendor datasheet.",
        "refine": "Hard constraints were updated from that sentence and the shortlist was rebuilt. You can still edit the form on the left.",
        "series_note": "The named series is the filter. Competitor clock and memory only rank closeness; STM32 does not have to match those numbers.",
        "clarify": "That is not enough to search. Add clock, Flash, package, or application; a competitor orderable part number; or an STM32 series. You can also look up a specific STM32 part.",
        "llm_down": "The language model is unavailable; the text above only restates library facts.",
        "empty_compare": "No shortlist cards in the named series, so this tool will not invent STM32 part numbers. Recalled competitor clock or Flash may sit well above that series. Search for closeness inside the series, or widen the series and compare again.",
    },
}

ENGINE = {
    "zh": {
        "unknown_db": "{label}：数据库无值",
        "unparsed": "{label}：无法解析 {value}",
        "mismatch": "{label}={value} 不匹配 {choices}",
        "st_missing": "{label}：ST 数据缺失",
        "cant_compare": "{label}：无法比较",
        "vs": "{label}：ST={st}，竞品={other}",
        "lifecycle": "生命周期状态需确认：{status}",
        "not_active": "库内状态不是量产，匹配度减 {delta}",
        "not_active_sim": "库内状态不是量产，相似度按 {pct}% 计",
        "score12": "{detail}，匹配度减 12",
        "over": "{label}明显高于需求，匹配度减 {delta}",
        "prefer_ok": "偏好满足：{detail}",
        "prefer_wait": "偏好待确认：{detail}",
        "prefer_wait_pen": "偏好待确认：{detail}，匹配度减 {delta}",
        "prefer_miss": "偏好未满足：{detail}，匹配度减 {delta}",
        "app_miss": "应用「{app}」库中未见{label}，匹配度减 {delta}",
        "disclaimer_req": "数据库筛选结果；PinMux、并发外设、精确模拟性能、认证、价格和供货需用最新官方资料确认。",
        "disclaimer_cmp": "相似度只基于已提供且可比较的规格；必须继续核对官方数据手册、封装引脚、生命周期和供货。",
        "pin": "{n} 引脚",
    },
    "en": {
        "unknown_db": "{label}: not in the library",
        "unparsed": "{label}: cannot parse {value}",
        "mismatch": "{label}={value} does not match {choices}",
        "st_missing": "{label}: missing on the ST record",
        "cant_compare": "{label}: cannot compare",
        "vs": "{label}: ST={st}, competitor={other}",
        "lifecycle": "Confirm lifecycle status: {status}",
        "not_active": "Library status is not Active; match score −{delta}",
        "not_active_sim": "Library status is not Active; similarity counted at {pct}%",
        "score12": "{detail}; match score −12",
        "over": "{label} is well above the need; match score −{delta}",
        "prefer_ok": "Preference met: {detail}",
        "prefer_wait": "Preference unverified: {detail}",
        "prefer_wait_pen": "Preference unverified: {detail}; match score −{delta}",
        "prefer_miss": "Preference not met: {detail}; match score −{delta}",
        "app_miss": "Application “{app}”: {label} not seen in the library; match score −{delta}",
        "disclaimer_req": "Library screen only. Confirm pinout, concurrent peripherals, analog performance, certification, price, and supply against current official data.",
        "disclaimer_cmp": "Similarity uses only the specs that can be compared. Confirm the official datasheet, package pins, lifecycle, and supply.",
        "pin": "{n} pins",
    },
}


def normalize_lang(lang: str | None) -> str:
    return "en" if str(lang or "").lower().startswith("en") else "zh"


def labels(lang: str | None) -> dict[str, str]:
    return LABELS[normalize_lang(lang)]


def brief(lang: str | None) -> dict[str, str]:
    return BRIEF[normalize_lang(lang)]


def turn(lang: str | None) -> dict[str, str]:
    return TURN[normalize_lang(lang)]


def engine(lang: str | None) -> dict[str, str]:
    return ENGINE[normalize_lang(lang)]


def field_label(field: str, lang: str | None = "zh") -> str:
    table = labels(lang)
    return table.get(field, field)


def fmt(key: str, value: Any, lang: str | None = "zh") -> str:
    units = {
        "frequency_mhz": " MHz",
        "flash_kb": " KB",
        "ram_kb": " KB",
        "temperature_max_c": " °C",
    }
    return f"{field_label(key, lang)} {value}{units.get(key, '')}"
