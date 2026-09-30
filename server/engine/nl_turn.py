"""Follow-up turns. Retrieval still owns part numbers; chat may recommend, compare, inspect, or explain."""

from __future__ import annotations

import json
import re
import threading
from typing import Any

import nl_brief
import nl_compare
import nl_ground
import nl_intent
import nl_must
import ui_copy

EXPLAIN_HINTS = (
    "为什么", "哪颗", "哪一颗", "差别", "区别", "对比这", "解释", "怎么选",
    "推荐理由", "有什么不同", "谁更", "第一颗", "第二颗", "第三颗",
    "why", "difference", "differences", "versus", "how to choose", "which one",
)
INSPECT_HINTS = (
    "查看", "查一下", "核对", "订货号", "是什么", "这颗料",
    "look up", "inspect", "orderable", "what is",
)
REFUSE_RE = re.compile(
    r"交期|lead\s*time|引脚兼容|pin[\s-]?compat|lead-time",
    re.I,
)
STM32_RE = re.compile(r"(?<![A-Z0-9])(STM32[A-Z0-9]{5,})(?![A-Z0-9])", re.I)
_TURN = threading.local()
EXPLAIN_PROMPT = {
    "zh": """你根据给定的 STM32 短名单 JSON 和用户问题作答。
只输出 JSON：{"intent":"explain","answer":"中文","notes":[]}
规则：
- 禁止提出 JSON 里没有的订货号，禁止价格、交期、引脚兼容承诺。
- answer 用 2～4 段中文，段与段之间空行：先共同规格，再三颗差别，再风险或须核对。
- 问题若超出这三颗（例如改规格、对照竞品），在 answer 里说明应改硬约束或做竞品对照，不要编新料。
- 用户上一轮的模型文字不是事实来源。
""",
    "en": """Answer from the STM32 shortlist JSON and the engineer's question.
Output JSON only: {"intent":"explain","answer":"English","notes":[]}
Rules:
- Do not name any STM32 orderable part that is not in the JSON. No price, lead-time, or pin-compatibility claims.
- Write answer in natural native US English, 2–4 short paragraphs separated by blank lines: shared specs, then differences among the three, then risks or datasheet checks.
- Do not sound translated. Prefer "clock", "orderable part number", and "shortlist".
- If the question goes beyond these three parts, say to edit hard constraints or run a competitor compare. Do not invent parts.
- Prior model prose is not a source of facts.
""",
}


def handle(
    text: str,
    must: dict[str, Any] | None,
    application: str | None,
    unknown_policy: str,
    candidates: list[dict[str, Any]],
    history: list[str],
    datasheet: dict[str, Any] | None = None,
    lang: str = "zh",
    compact_package: bool = False,
) -> dict[str, Any]:
    cleaned = " ".join(str(text or "").split())
    copy = ui_copy.turn(lang)
    price_hit = nl_must.mentions_price(cleaned)
    if len(cleaned) < 2:
        raise ValueError(copy["need"])
    if len(cleaned) > nl_must.MAX_CHARS:
        raise ValueError(f"请控制在 {nl_must.MAX_CHARS} 字以内。")
    slim = [slim_candidate(item) for item in candidates][:3]
    form_must = dict(must or {})
    current_must = dict(form_must)
    policy = unknown_policy if unknown_policy in {"allow_risk", "exclude"} else "allow_risk"
    user_series = nl_intent.extract_series_prefix(cleaned)
    intent = classify(cleaned, slim)
    overlay = None
    if intent != "refuse" and not (slim and intent == "explain"):
        overlay = nl_intent.from_model(cleaned)
    notes_extra = []
    browse_not_compare = False
    if overlay:
        if overlay.get("intent"):
            intent = overlay["intent"]
        current_must = dict(current_must)
        current_must.update(overlay.get("must") or {})
        current_must.update(form_must)
        if overlay.get("application"):
            application = overlay["application"]
        notes_extra = list(overlay.get("notes") or [])
    if not application:
        application = nl_must.parse_with_rules(cleaned).get("application") or application
    series_prefix = nl_intent.merge_series_prefix(
        user_series,
        (overlay or {}).get("series_prefix") if overlay else None,
    )
    if intent == "refuse" and not REFUSE_RE.search(cleaned):
        intent = "refine_must"
    rules_now = nl_must.parse_with_rules(cleaned)
    for key, value in (rules_now.get("must") or {}).items():
        if key not in form_must:
            current_must[key] = value
    compact = bool(
        compact_package
        or rules_now.get("compact_package")
        or (overlay or {}).get("compact_package")
    )
    _TURN.compact = compact
    _TURN.price = price_hit
    _TURN.copy = copy
    if overlay and overlay.get("intent") == "recommend":
        intent = "refine_must"
    if overlay and (overlay.get("competitor") or {}).get("part_number"):
        intent = "compare"
    if nl_compare.datasheet_ready(datasheet) and intent not in {"refuse", "inspect"}:
        intent = "compare"
    # A named STM32 outside the current shortlist is a lookup, not an essay about
    # the previous three cards (e.g. "STM32H5E5ZJT6 为什么不是最合适的").
    outside = _stm32_outside_shortlist(cleaned, slim)
    if outside and intent in {"explain", "refine_must"}:
        intent = "inspect"
    if intent == "refuse":
        return _payload(
            "refuse",
            copy["refuse"],
            current_must,
            application,
            policy,
            "rules",
            series_prefix=series_prefix,
        )
    if intent == "inspect":
        part = (overlay or {}).get("inspect_part") or outside or _stm32_part(cleaned) or ""
        if not part:
            return _clarify(current_must, application, policy, series_prefix, lang)
        result = _payload(
            "inspect",
            copy["inspect"].format(part=part),
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
        except nl_compare.NeedSpecs:
            # No verified competitor specs: never invent them. If the engineer named an
            # STM32 series (or already has must), browse that series from the database
            # and label it as browse-not-compare. Otherwise ask for a datasheet.
            if series_prefix or current_must:
                intent = "refine_must"
                draft = None
                browse_not_compare = True
                notes_extra = notes_extra + [copy["series_browse"]]
            else:
                return _payload(
                    "need_specs",
                    copy["need_specs"],
                    current_must,
                    application,
                    policy,
                    "rules",
                    series_prefix=series_prefix,
                )
        except ValueError:
            if current_must or series_prefix:
                intent = "refine_must"
                draft = None
            else:
                return _clarify(current_must, application, policy, series_prefix, lang)
        if draft is not None:
            if (overlay or {}).get("competitor"):
                vendor = overlay["competitor"].get("manufacturer")
                if vendor:
                    draft["manufacturer"] = vendor
            result = _payload(
                "compare",
                copy["compare"],
                current_must,
                application,
                policy,
                "rules",
                notes=list(draft.get("notes") or []) + notes_extra,
                series_prefix=series_prefix,
            )
            result["compare"] = {
                key: draft[key]
                for key in ("manufacturer", "part_number", "source_note", "specs", "essential", "limit")
            }
            result["compare"]["series_prefix"] = series_prefix
            result["compare"]["lang"] = ui_copy.normalize_lang(lang)
            result["compare"]["application"] = application
            if series_prefix:
                result["compare"]["essential"] = []
                result["notes"] = list(result.get("notes") or []) + [copy["series_note"]]
            return result
    if intent == "refine_must":
        merged = dict(current_must)
        source = "model" if overlay else "rules"
        notes = list(notes_extra)
        if not overlay:
            draft = _try_requirements(cleaned)
            if not draft:
                if not series_prefix and not merged and not application and not compact:
                    return _clarify(merged, application, policy, series_prefix, lang)
                draft = {"must": {}, "notes": []}
            merged = _keep_form(merged, draft.get("must"), form_must)
            application = draft.get("application") or application
            policy = draft.get("unknown_policy") or policy
            source = draft.get("source") or source
            notes = list(draft.get("notes") or [])
        elif not merged and not series_prefix:
            draft = _try_requirements(cleaned)
            if not draft:
                if not application and not compact:
                    return _clarify(merged, application, policy, series_prefix, lang)
                draft = {"must": {}, "notes": []}
            merged = _keep_form(merged, draft.get("must"), form_must)
            application = draft.get("application") or application
            notes.extend(draft.get("notes") or [])
        return _payload(
            "refine_must",
            copy["series_browse"] if browse_not_compare else copy["refine"],
            merged,
            application,
            policy,
            source,
            notes=notes,
            rerecommend=True,
            series_prefix=series_prefix,
            browse_not_compare=browse_not_compare,
        )
    if not slim:
        return _clarify(current_must, application, policy, series_prefix, lang)
    return _payload(
        "explain",
        explain(cleaned, slim, history, lang),
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


def _stm32_outside_shortlist(text: str, candidates: list[dict[str, Any]]) -> str | None:
    """Return a named STM32 that is not one of the current shortlist cards."""
    part = _stm32_part(text)
    if not part:
        return None
    allowed = [str(item.get("part_number") or "").upper() for item in candidates if item.get("part_number")]
    if not allowed:
        return None
    for token in allowed:
        if part == token or part.startswith(token) or token.startswith(part):
            return None
    return part


def _looks_like_inspect(text: str) -> bool:
    part = _stm32_part(text)
    if not part:
        return False
    remainder = STM32_RE.sub("", text)
    for hint in INSPECT_HINTS:
        remainder = remainder.replace(hint, "")
    leftover = remainder.strip(" ，。,.!?：:、")
    return any(hint in text for hint in INSPECT_HINTS) or len(leftover) < 2


def explain(text: str, candidates: list[dict[str, Any]], history: list[str], lang: str = "zh") -> str:
    fallback = nl_brief.for_shortlist(candidates, lang=lang)
    copy = ui_copy.turn(lang)
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
        raw = nl_must.complete_json(EXPLAIN_PROMPT[ui_copy.normalize_lang(lang)], user, timeout=20) or {}
    except Exception:
        return fallback + "\n" + copy["llm_down"]
    answer = str(raw.get("answer") or "").strip()
    # Ground against the retrieved shortlist only. The question and history are the
    # engineer's own words, so numbers they typed must not license numbers we print.
    return nl_ground.enforce(answer, fallback, candidates, candidates)


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


def _keep_form(base: dict[str, Any], incoming: dict[str, Any] | None, form_must: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in (incoming or {}).items():
        if key not in form_must:
            merged[key] = value
    merged.update(form_must)
    return merged


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
    lang: str = "zh",
) -> dict[str, Any]:
    return _payload(
        "explain",
        ui_copy.turn(lang)["clarify"],
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
    browse_not_compare: bool = False,
) -> dict[str, Any]:
    payload = {
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
    if browse_not_compare:
        payload["browse_not_compare"] = True
    payload["compact_package"] = bool(getattr(_TURN, "compact", False))
    if getattr(_TURN, "price", False):
        copy = getattr(_TURN, "copy", None) or ui_copy.turn("zh")
        note = copy["price_ignored"]
        payload["ignored_price"] = True
        notes = [note] + [item for item in payload["notes"] if item != note]
        payload["notes"] = notes
        answer = str(payload.get("answer") or "")
        if note not in answer:
            payload["answer"] = f"{note}\n\n{answer}".strip()
    return payload
