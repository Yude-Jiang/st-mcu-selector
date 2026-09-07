"""Follow-up turns. Retrieval still owns part numbers; chat may recommend, compare, inspect, or explain."""

from __future__ import annotations

import json
import re
from typing import Any

import nl_compare
import nl_must

EXPLAIN_HINTS = (
    "为什么", "哪颗", "哪一颗", "差别", "区别", "对比这", "解释", "怎么选",
    "推荐理由", "有什么不同", "谁更", "第一颗", "第二颗", "第三颗",
)
INSPECT_HINTS = ("查看", "查一下", "核对", "订货号", "是什么", "这颗料")
REFUSE_RE = re.compile(r"价格|交期|lead\s*time|便宜|引脚兼容|pin[\s-]?compat", re.I)
STM32_RE = re.compile(r"\b(STM32[A-Z0-9]{5,})\b", re.I)
EXPLAIN_PROMPT = """你根据给定的 STM32 短名单 JSON 和用户问题作答。
只输出 JSON：{"intent":"explain","answer":"中文","notes":[]}
规则：
- 禁止提出 JSON 里没有的订货号，禁止价格、交期、引脚兼容承诺。
- 问题若超出这三颗（例如改规格、对照竞品），在 answer 里说明应改硬约束或做竞品对照，不要编新料。
- 用户上一轮的模型文字不是事实来源。
"""


def handle(
    text: str,
    must: dict[str, Any] | None,
    application: str | None,
    unknown_policy: str,
    candidates: list[dict[str, Any]],
    history: list[str],
) -> dict[str, Any]:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) < 2:
        raise ValueError("请写出需求、竞品对照或要问的问题。")
    if len(cleaned) > nl_must.MAX_CHARS:
        raise ValueError(f"请控制在 {nl_must.MAX_CHARS} 字以内。")
    slim = [slim_candidate(item) for item in candidates][:3]
    current_must = dict(must or {})
    policy = unknown_policy if unknown_policy in {"allow_risk", "exclude"} else "allow_risk"
    intent = classify(cleaned, slim)
    if intent == "refuse":
        return _payload(
            "refuse",
            "本工具不承诺价格、交期或引脚兼容。可以改硬约束重新推荐，或一句话做竞品对照。",
            current_must,
            application,
            policy,
            "rules",
        )
    if intent == "inspect":
        part = _stm32_part(cleaned) or ""
        result = _payload("inspect", f"正在核对 {part} 在库里的身份。", current_must, application, policy, "rules")
        result["inspect_part"] = part
        return result
    if intent == "compare":
        draft = nl_compare.parse_competitor(cleaned)
        recalled = bool(draft.get("recalled_specs"))
        result = _payload(
            "compare",
            "已按竞品规格对照 STM32。规格若来自模型回忆，须核对厂家 datasheet。",
            current_must,
            application,
            policy,
            "model" if recalled else "rules",
            notes=list(draft.get("notes") or []),
        )
        result["compare"] = {
            key: draft[key]
            for key in ("manufacturer", "part_number", "source_note", "specs", "essential", "limit")
        }
        return result
    if intent == "refine_must":
        draft = nl_must.parse_requirements(cleaned)
        merged = dict(current_must)
        merged.update(draft.get("must") or {})
        app = draft.get("application") or application
        return _payload(
            "refine_must",
            "已按这句话更新硬约束并重新推荐。左侧表单可再改。",
            merged,
            app,
            draft.get("unknown_policy") or policy,
            draft.get("source") or "rules",
            notes=list(draft.get("notes") or []),
            rerecommend=True,
        )
    if not slim:
        raise ValueError("请先写一句需求或竞品对照并点推荐，或在左侧改硬约束后推荐。")
    return _payload(
        "explain",
        explain(cleaned, slim, history),
        current_must,
        application,
        policy,
        "model" if nl_must.llm_configured() else "rules",
    )


def classify(text: str, candidates: list[dict[str, Any]]) -> str:
    if REFUSE_RE.search(text):
        return "refuse"
    if _looks_like_inspect(text):
        return "inspect"
    if nl_compare.looks_like_compare(text):
        return "compare"
    new_must = bool(nl_must.parse_with_rules(text).get("must"))
    asking = any(hint in text for hint in EXPLAIN_HINTS)
    if candidates and asking and not new_must:
        return "explain"
    if new_must:
        return "refine_must"
    if candidates:
        return "explain"
    return "refine_must"


def _stm32_part(text: str) -> str | None:
    match = STM32_RE.search(text)
    return match.group(1).upper() if match else None


def _looks_like_inspect(text: str) -> bool:
    part = _stm32_part(text)
    if not part:
        return False
    remainder = STM32_RE.sub("", text)
    for hint in INSPECT_HINTS:
        remainder = remainder.replace(hint, "")
    leftover = remainder.strip(" ，。,.!?：:、")
    return any(hint in text for hint in INSPECT_HINTS) or len(leftover) < 2


def explain(text: str, candidates: list[dict[str, Any]], history: list[str]) -> str:
    fallback = explain_with_facts(candidates)
    if not nl_must.llm_configured():
        return fallback
    user = json.dumps(
        {
            "question": text,
            "user_history": [str(item) for item in history[-4:] if str(item).strip()],
            "shortlist": candidates,
        },
        ensure_ascii=False,
    )
    try:
        raw = nl_must.complete_json(EXPLAIN_PROMPT, user, timeout=20) or {}
    except Exception:
        return fallback + "\n大模型暂不可用，以上仅复述库内事实。"
    answer = str(raw.get("answer") or "").strip()
    return answer or fallback


def explain_with_facts(candidates: list[dict[str, Any]]) -> str:
    names = [str(item.get("part_number") or "") for item in candidates if item.get("part_number")]
    lines = [f"当前短名单是 {'、'.join(names)}。以下只复述库内事实，不是设计签核。"]
    for item in candidates:
        part = item.get("part_number") or "未知订货号"
        facts = item.get("facts") or {}
        bits = []
        for key, label in (
            ("frequency_mhz", "主频"),
            ("flash_kb", "Flash"),
            ("ram_kb", "RAM"),
            ("package", "封装"),
            ("pin_count", "引脚"),
            ("fdcan", "FDCAN"),
            ("usb", "USB"),
        ):
            value = facts.get(key)
            if value not in (None, "", []):
                bits.append(f"{label} {value}")
        lines.append(f"{part}：{'，'.join(bits) if bits else '库内规格见卡片。'}")
    lines.append("也可改硬约束重新推荐，或一句话做竞品对照。")
    return "\n".join(lines)


def slim_candidate(item: dict[str, Any]) -> dict[str, Any]:
    facts = item.get("facts") if isinstance(item.get("facts"), dict) else {}
    return {
        "part_number": str(item.get("part_number") or "")[:120],
        "score": item.get("score"),
        "facts": {key: facts[key] for key in list(facts)[:16]},
        "matches": [str(row) for row in (item.get("matches") or [])[:8]],
        "risks": [str(row) for row in (item.get("risks") or [])[:8]],
    }


def _payload(
    intent: str,
    answer: str,
    must: dict[str, Any],
    application: str | None,
    unknown_policy: str,
    source: str,
    notes: list[str] | None = None,
    rerecommend: bool = False,
) -> dict[str, Any]:
    return {
        "intent": intent,
        "answer": answer,
        "must": must,
        "application": application if application in nl_must.APPLICATIONS else None,
        "unknown_policy": unknown_policy,
        "source": source,
        "notes": notes or [],
        "rerecommend": rerecommend,
    }
