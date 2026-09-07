"""Follow-up turns. Retrieval still owns part numbers; chat may recommend, compare, inspect, or explain."""

from __future__ import annotations

import json
import re
from typing import Any

import nl_brief
import nl_compare
import nl_intent
import nl_must

EXPLAIN_HINTS = (
    "为什么", "哪颗", "哪一颗", "差别", "区别", "对比这", "解释", "怎么选",
    "推荐理由", "有什么不同", "谁更", "第一颗", "第二颗", "第三颗",
)
INSPECT_HINTS = ("查看", "查一下", "核对", "订货号", "是什么", "这颗料")
REFUSE_RE = re.compile(r"价格|交期|lead\s*time|便宜|引脚兼容|pin[\s-]?compat", re.I)
STM32_RE = re.compile(r"(?<![A-Z0-9])(STM32[A-Z0-9]{5,})(?![A-Z0-9])", re.I)
EXPLAIN_PROMPT = """你根据给定的 STM32 短名单 JSON 和用户问题作答。
只输出 JSON：{"intent":"explain","answer":"中文","notes":[]}
规则：
- 禁止提出 JSON 里没有的订货号，禁止价格、交期、引脚兼容承诺。
- answer 用 2～4 段中文，段与段之间空行：先共同规格，再三颗差别，再风险或须核对。
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
    datasheet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) < 2:
        raise ValueError("请写出需求、竞品对照或要问的问题。")
    if len(cleaned) > nl_must.MAX_CHARS:
        raise ValueError(f"请控制在 {nl_must.MAX_CHARS} 字以内。")
    slim = [slim_candidate(item) for item in candidates][:3]
    current_must = dict(must or {})
    policy = unknown_policy if unknown_policy in {"allow_risk", "exclude"} else "allow_risk"
    series_prefix = nl_intent.extract_series_prefix(cleaned)
    intent = classify(cleaned, slim)
    overlay = None
    if intent != "refuse" and not (slim and intent == "explain"):
        overlay = nl_intent.from_model(cleaned)
    if overlay:
        if overlay.get("intent"):
            intent = overlay["intent"]
        current_must = dict(current_must)
        current_must.update(overlay.get("must") or {})
        for token in overlay.get("series_prefix") or []:
            if token not in series_prefix:
                series_prefix.append(token)
        if overlay.get("application"):
            application = overlay["application"]
        notes_extra = list(overlay.get("notes") or [])
    else:
        notes_extra = []
    if overlay and overlay.get("intent") == "recommend":
        intent = "refine_must"
    if overlay and (overlay.get("competitor") or {}).get("part_number"):
        intent = "compare"
    if nl_compare.datasheet_ready(datasheet) and intent not in {"refuse", "inspect"}:
        intent = "compare"
    if intent == "refuse":
        return _payload(
            "refuse",
            "本工具不承诺价格、交期或引脚兼容。可以改硬约束重新推荐，或一句话做竞品对照。",
            current_must,
            application,
            policy,
            "rules",
            series_prefix=series_prefix,
        )
    if intent == "inspect":
        part = (overlay or {}).get("inspect_part") or _stm32_part(cleaned) or ""
        if not part:
            return _clarify(current_must, application, policy, series_prefix)
        result = _payload(
            "inspect",
            f"正在核对 {part} 在库里的身份。",
            current_must,
            application,
            policy,
            "rules",
            series_prefix=series_prefix,
        )
        result["inspect_part"] = part
        return result
    if intent == "compare":
        try:
            draft = nl_compare.parse_competitor(cleaned, datasheet=datasheet)
        except ValueError:
            if current_must or series_prefix:
                intent = "refine_must"
                draft = None
            else:
                return _clarify(current_must, application, policy, series_prefix)
        if draft is not None:
            if (overlay or {}).get("competitor"):
                vendor = overlay["competitor"].get("manufacturer")
                if vendor:
                    draft["manufacturer"] = vendor
            recalled = bool(draft.get("recalled_specs"))
            result = _payload(
                "compare",
                "已按竞品规格对照 STM32。规格若来自模型回忆，须核对厂家 datasheet。",
                current_must,
                application,
                policy,
                "model" if recalled else "rules",
                notes=list(draft.get("notes") or []) + notes_extra,
                series_prefix=series_prefix,
            )
            result["compare"] = {
                key: draft[key]
                for key in ("manufacturer", "part_number", "source_note", "specs", "essential", "limit")
            }
            result["compare"]["series_prefix"] = series_prefix
            return result
    if intent == "refine_must":
        merged = dict(current_must)
        source = "model" if overlay else "rules"
        notes = list(notes_extra)
        if not overlay:
            draft = _try_requirements(cleaned)
            if not draft:
                if not series_prefix and not merged and not application:
                    return _clarify(merged, application, policy, series_prefix)
                draft = {"must": {}, "notes": []}
            merged.update(draft.get("must") or {})
            application = draft.get("application") or application
            policy = draft.get("unknown_policy") or policy
            source = draft.get("source") or source
            notes = list(draft.get("notes") or [])
        elif not merged and not series_prefix:
            draft = _try_requirements(cleaned)
            if not draft:
                if not application:
                    return _clarify(merged, application, policy, series_prefix)
                draft = {"must": {}, "notes": []}
            merged.update(draft.get("must") or {})
            application = draft.get("application") or application
            notes.extend(draft.get("notes") or [])
        return _payload(
            "refine_must",
            "已按这句话更新硬约束并重新推荐。左侧表单可再改。",
            merged,
            application,
            policy,
            source,
            notes=notes,
            rerecommend=True,
            series_prefix=series_prefix,
        )
    if not slim:
        return _clarify(current_must, application, policy, series_prefix)
    return _payload(
        "explain",
        explain(cleaned, slim, history),
        current_must,
        application,
        policy,
        "model" if nl_must.llm_configured() else "rules",
        notes=notes_extra,
        series_prefix=series_prefix,
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
    return nl_brief.for_shortlist(candidates)


def slim_candidate(item: dict[str, Any]) -> dict[str, Any]:
    facts = item.get("facts") if isinstance(item.get("facts"), dict) else {}
    return {
        "part_number": str(item.get("part_number") or "")[:120],
        "score": item.get("score"),
        "facts": {key: facts[key] for key in list(facts)[:16]},
        "matches": [str(row) for row in (item.get("matches") or [])[:8]],
        "risks": [str(row) for row in (item.get("risks") or [])[:8]],
    }


def _try_requirements(text: str) -> dict[str, Any] | None:
    try:
        return nl_must.parse_requirements(text)
    except ValueError:
        return None


def _clarify(
    must: dict[str, Any],
    application: str | None,
    unknown_policy: str,
    series_prefix: list[str],
) -> dict[str, Any]:
    return _payload(
        "explain",
        nl_intent.CLARIFY,
        must,
        application,
        unknown_policy,
        "rules",
        series_prefix=series_prefix,
    )


def _payload(
    intent: str,
    answer: str,
    must: dict[str, Any],
    application: str | None,
    unknown_policy: str,
    source: str,
    notes: list[str] | None = None,
    rerecommend: bool = False,
    series_prefix: list[str] | None = None,
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
        "series_prefix": series_prefix or [],
    }
