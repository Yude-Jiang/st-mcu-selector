#!/usr/bin/env python3
"""Deterministic ST MCU selection against the exported MCUFinder SQLite database."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable

from shortlist import application_label, field_label, format_points, pick_shortlist

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


MCU_CLASSES = (1734, 1735, 1738)
INACTIVE_STATUSES = {"obsolete", "nrnd", "not recommended for new designs"}

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "frequency_mhz": ("freqCore1Max", "freqCore1", "freqCore1_typ"),
    "flash_kb": ("flash",),
    "ram_kb": ("cpnd_ramtotal", "ram", "onchip_SRAM"),
    "core": ("core",),
    "fpu": ("fpu",),
    "adc_channels": ("adc16bit", "adc14bit", "adc12bit", "adc10bit", "adc12bit_stm8"),
    "adc_units": ("cpnd_adctotal", "adc16bit_number", "adc14bit_number", "adc12bit_number"),
    "dac_channels": ("dac12bit",),
    "opamps": ("opamp",),
    "comparators": ("comp",),
    "can": ("cpnd_cantotal", "can", "can2_0"),
    "fdcan": ("fdcan",),
    "usb": ("nb_usb2_itf", "usbs"),
    "usb_types": ("usbs",),
    "ethernet": ("ethernet_port",),
    "ethernet_speed_mbps": ("ethernet",),
    "motor_timers": ("AMCTimer",),
    "hrtim": ("HRTIM", "hrtim"),
    "timers": ("cpnd_timertotal", "cpnd_gptimerstotal"),
    "timers_16bit": ("timer16bit",),
    "timers_32bit": ("timer32bit",),
    "timers_8bit": ("timer8bit",),
    "package": ("package",),
    "package_type": ("package_type",),
    "pin_count": ("package_pin_count",),
    "temperature_min_c": ("temperatureMin",),
    "temperature_max_c": ("temperatureMax",),
    "voltage_min_v": ("voltageMin",),
    "voltage_max_v": ("voltageMax",),
    "security": ("securityFunctions",),
    "other_timer_functions": ("otherTimerFunctions",),
    "firmware_package": ("fw_pack_name",),
}

NUMERIC_FIELDS = {
    "frequency_mhz", "flash_kb", "ram_kb", "adc_channels", "adc_units",
    "dac_channels", "opamps", "comparators", "can", "fdcan", "usb",
    "ethernet", "ethernet_speed_mbps", "motor_timers", "hrtim", "timers", "timers_16bit",
    "timers_32bit", "timers_8bit", "pin_count", "temperature_min_c", "temperature_max_c",
    "voltage_min_v", "voltage_max_v",
}

DEFAULT_WEIGHTS = {
    "frequency_mhz": 1.0, "flash_kb": 1.0, "ram_kb": 1.0,
    "adc_channels": 1.1, "adc_units": 1.0, "dac_channels": 0.8,
    "opamps": 1.2, "comparators": 1.2, "can": 1.0, "fdcan": 1.2,
    "usb": 0.8, "ethernet": 1.0, "motor_timers": 1.4, "hrtim": 1.4,
    "timers": 0.8, "pin_count": 0.8, "temperature_min_c": 1.0,
    "temperature_max_c": 1.0, "voltage_min_v": 0.8, "voltage_max_v": 0.8,
    "package_type": 1.0, "core": 0.8, "fpu": 0.8, "security": 0.8,
}

APPLICATION_PROFILES = {
    "motor_control": {
        "motor_timers": 1.5, "hrtim": 1.5, "adc_channels": 1.2,
        "opamps": 1.2, "comparators": 1.2, "fdcan": 0.8,
    },
    "power_conversion": {
        "hrtim": 1.5, "motor_timers": 1.2, "adc_channels": 1.2,
        "comparators": 1.2, "opamps": 1.0,
    },
    "bms": {
        "adc_channels": 1.3, "can": 1.0, "fdcan": 1.2,
        "security": 0.8, "temperature_max_c": 0.8,
    },
    "industrial_control": {
        "fdcan": 1.1, "can": 1.0, "ethernet": 1.0,
        "timers": 0.8, "temperature_max_c": 0.8,
    },
    "iot": {
        "security": 1.1, "usb": 0.8, "ram_kb": 0.8,
    },
}


def default_database_candidates() -> list[Path]:
    candidates: list[Path] = []
    if os.environ.get("ST_MCU_DB"):
        candidates.append(Path(os.environ["ST_MCU_DB"]))
    candidates.extend([
        Path.home() / ".st-mcu-recommender" / "data" / "cube-finder-db.db",
        Path.home() / ".stmcufinder" / "plugins" / "mcufinder" / "mcu" / "cube-finder-db.db",
    ])
    return candidates


def find_database(override: str | None = None) -> Path:
    candidates = [Path(override)] if override else default_database_candidates()
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    tried = "\n".join(f"- {path}" for path in candidates)
    raise FileNotFoundError(
        "未找到 cube-finder-db.db。请先运行 update_database.py，设置 ST_MCU_DB，"
        f"或使用 --db。\n已检查：\n{tried}"
    )


def connect_readonly(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def json_dump(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def chunks(values: list[int], size: int = 800) -> Iterable[list[int]]:
    for index in range(0, len(values), size):
        yield values[index:index + size]


def parse_scalar(str_value: Any, num_value: Any) -> Any:
    if str_value is not None and str(str_value).strip() != "":
        text = str(str_value).strip()
        if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", text):
            return float(text) if "." in text else int(text)
        return text
    return num_value


def numeric(value: Any, allow_negative: bool = False) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value).replace(",", ""))
        if not match:
            return None
        number = float(match.group())
    if not math.isfinite(number) or (number < 0 and not allow_negative):
        return None
    return number


def resolve_attribute_ids(db: sqlite3.Connection) -> tuple[dict[int, str], set[int]]:
    wanted_names = {name.lower() for aliases in FIELD_ALIASES.values() for name in aliases}
    id_to_name: dict[int, str] = {}
    for row in db.execute("SELECT id, name FROM attribute"):
        if row["name"] and row["name"].lower() in wanted_names:
            id_to_name[row["id"]] = row["name"]
    return id_to_name, set(id_to_name)


def fetch_values(
    db: sqlite3.Connection,
    table: str,
    owner_column: str,
    attribute_ids: set[int],
) -> dict[int, dict[str, Any]]:
    if not attribute_ids:
        return {}
    id_to_name = {
        row["id"]: row["name"]
        for row in db.execute(
            f"SELECT id,name FROM attribute WHERE id IN ({','.join('?' * len(attribute_ids))})",
            tuple(attribute_ids),
        )
    }
    result: dict[int, dict[str, Any]] = {}
    placeholders = ",".join("?" * len(attribute_ids))
    query = (
        f"SELECT {owner_column} owner_id, attribute_id, strValue, numValue "
        f"FROM {table} WHERE attribute_id IN ({placeholders})"
    )
    for row in db.execute(query, tuple(attribute_ids)):
        result.setdefault(row["owner_id"], {})[id_to_name[row["attribute_id"]]] = parse_scalar(
            row["strValue"], row["numValue"]
        )
    return result


def first_value(attributes: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    lower = {key.lower(): value for key, value in attributes.items()}
    for alias in aliases:
        value = lower.get(alias.lower())
        if value is not None and value != "" and value != -1:
            return value
    return None


def derive_fields(attributes: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for logical, aliases in FIELD_ALIASES.items():
        values = [
            first_value(attributes, (alias,))
            for alias in aliases
        ]
        values = [value for value in values if value is not None]
        if not values:
            fields[logical] = None
            continue
        if logical in {"adc_channels", "adc_units", "ram_kb", "can"}:
            numbers = [numeric(value) for value in values]
            fields[logical] = max((value for value in numbers if value is not None), default=None)
        elif logical == "usb":
            numeric_count = numeric(values[0])
            fields[logical] = numeric_count if numeric_count is not None else 1
        elif logical == "ethernet_speed_mbps":
            fields[logical] = numeric(values[0])
        else:
            fields[logical] = values[0]

    other_timer_functions = str(fields.get("other_timer_functions") or "")
    if fields.get("hrtim") is None and re.search(r"\bHR\s*timer\b", other_timer_functions, re.IGNORECASE):
        fields["hrtim"] = 1
    if fields.get("timers") is None:
        timer_counts = [
            numeric(fields.get("timers_16bit")),
            numeric(fields.get("timers_32bit")),
            numeric(fields.get("timers_8bit")),
        ]
        known_counts = [value for value in timer_counts if value is not None]
        fields["timers"] = sum(known_counts) if known_counts else None

    if fields.get("package_type") is None and fields.get("package"):
        match = re.match(r"([A-Za-z]+)", str(fields["package"]))
        fields["package_type"] = match.group(1).upper() if match else None
    if fields.get("pin_count") is None and fields.get("package"):
        match = re.search(r"\b(\d{2,3})\b", str(fields["package"]))
        fields["pin_count"] = int(match.group(1)) if match else None
    return fields


def load_candidates(db: sqlite3.Connection, include_inactive: bool = False) -> list[dict[str, Any]]:
    _, attribute_ids = resolve_attribute_ids(db)
    cpn_values = fetch_values(db, "cpn_has_attribute", "cpn_id", attribute_ids)
    rpn_values = fetch_values(db, "rpn_has_attribute", "rpn_id", attribute_ids)
    class_placeholders = ",".join("?" * len(MCU_CLASSES))
    query = f"""
        SELECT c.id cpn_id, c.cpn, c.refname, r.id rpn_id, r.rpn,
               r.marketingStatus, r.class_id, r.description
        FROM cpn c
        JOIN rpn_has_cpn rc ON rc.cpn_id=c.id
        JOIN rpn r ON r.id=rc.rpn_id
        WHERE r.class_id IN ({class_placeholders})
    """
    candidates: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in db.execute(query, MCU_CLASSES):
        if row["cpn_id"] in seen:
            continue
        seen.add(row["cpn_id"])
        status = (row["marketingStatus"] or "").strip()
        if not include_inactive and status.lower() in INACTIVE_STATUSES:
            continue
        attributes = dict(rpn_values.get(row["rpn_id"], {}))
        attributes.update(cpn_values.get(row["cpn_id"], {}))
        candidates.append({
            "part_number": row["cpn"],
            "reference": row["refname"] or row["rpn"],
            "rpn": row["rpn"],
            "status": status or "Unknown",
            "description": row["description"] or "",
            "fields": derive_fields(attributes),
        })
    return candidates


def normalize_constraint(field: str, raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if field in NUMERIC_FIELDS:
        if isinstance(raw, bool):
            return {"min": 1 if raw else 0}
        return {"min": raw}
    if isinstance(raw, list):
        return {"any_of": raw}
    return {"any_of": [raw]}


def text_matches(value: Any, choices: list[Any]) -> bool:
    haystack = str(value).lower()
    return any(str(choice).lower() in haystack for choice in choices)


def evaluate_constraint(field: str, value: Any, raw_constraint: Any) -> tuple[str, str]:
    constraint = normalize_constraint(field, raw_constraint)
    label = field_label(field)
    if value is None or value == "":
        return "unknown", f"{label}：数据库无值"
    if field in NUMERIC_FIELDS:
        number = numeric(value, allow_negative=field in {"temperature_min_c"})
        if number is None:
            return "unknown", f"{label}：无法解析 {value!r}"
        if "min" in constraint and number < float(constraint["min"]):
            return "fail", f"{label}={number:g} < {constraint['min']}"
        if "max" in constraint and number > float(constraint["max"]):
            return "fail", f"{label}={number:g} > {constraint['max']}"
        return "pass", f"{label}={number:g}"
    choices = constraint.get("any_of") or constraint.get("contains")
    if choices is not None and not text_matches(value, list(choices)):
        return "fail", f"{label}={value!r} 不匹配 {choices}"
    if "equals" in constraint and str(value).lower() != str(constraint["equals"]).lower():
        return "fail", f"{label}={value!r} != {constraint['equals']!r}"
    return "pass", f"{label}={value}"


def overqualification_penalty(field: str, value: Any, raw_constraint: Any) -> float:
    if field not in NUMERIC_FIELDS:
        return 0.0
    constraint = normalize_constraint(field, raw_constraint)
    if "min" not in constraint or field in {
        "temperature_max_c", "voltage_max_v", "fdcan", "can", "usb", "ethernet",
        "opamps", "comparators", "motor_timers", "hrtim",
    }:
        return 0.0
    target = float(constraint["min"])
    actual = numeric(value)
    if not actual or target <= 0 or actual <= target:
        return 0.0
    ratio = actual / target
    return min(8.0, max(0.0, (ratio - 1.25) * 4.0))


def compact_facts(fields: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "core", "frequency_mhz", "flash_kb", "ram_kb", "package", "pin_count",
        "temperature_min_c", "temperature_max_c", "adc_channels", "opamps",
        "comparators", "motor_timers", "fdcan", "can", "usb", "ethernet",
        "usb_types", "ethernet_speed_mbps", "hrtim", "timers",
    )
    return {key: fields.get(key) for key in keys if fields.get(key) is not None}


def recommend(database: Path, request_data: dict[str, Any]) -> dict[str, Any]:
    with connect_readonly(database) as db:
        candidates = load_candidates(db, bool(request_data.get("include_inactive")))
        version = dict(db.execute("SELECT * FROM version LIMIT 1").fetchone())
    must = request_data.get("must") or {}
    prefer = request_data.get("prefer") or {}
    unknown_policy = request_data.get("unknown_policy", "allow_risk")
    profile = APPLICATION_PROFILES.get(str(request_data.get("application", "")).lower(), {})
    ranked: list[dict[str, Any]] = []
    rejected = 0
    app_name = application_label(str(request_data.get("application") or ""))

    for candidate in candidates:
        fields = candidate["fields"]
        score = 100.0
        matches: list[str] = []
        risks: list[str] = []
        penalties: list[str] = []
        failures: list[str] = []
        status_lower = candidate["status"].lower()
        if "active" not in status_lower:
            delta = 8.0 if "coming soon" in status_lower else 4.0
            score -= delta
            risks.append(f"生命周期状态需确认：{candidate['status']}")
            penalties.append(f"库内状态不是量产，匹配度减 {format_points(delta)}")
        for field, constraint in must.items():
            status, detail = evaluate_constraint(field, fields.get(field), constraint)
            if status == "fail":
                failures.append(detail)
            elif status == "unknown":
                if unknown_policy == "exclude":
                    failures.append(detail)
                else:
                    risks.append(detail)
                    score -= 12.0
                    penalties.append(f"{detail}，匹配度减 12")
            else:
                matches.append(detail)
                extra = overqualification_penalty(field, fields.get(field), constraint)
                if extra:
                    score -= extra
                    penalties.append(f"{field_label(field)}明显高于需求，匹配度减 {format_points(extra)}")
        if failures:
            rejected += 1
            continue

        for field, constraint in prefer.items():
            status, detail = evaluate_constraint(field, fields.get(field), constraint)
            weight = float(DEFAULT_WEIGHTS.get(field, 1.0))
            if status == "pass":
                matches.append(f"偏好满足：{detail}")
            elif status == "unknown":
                delta = 1.5 * weight
                risks.append(f"偏好待确认：{detail}")
                score -= delta
                penalties.append(f"偏好待确认：{detail}，匹配度减 {format_points(delta)}")
            else:
                delta = 4.0 * weight
                score -= delta
                penalties.append(f"偏好未满足：{detail}，匹配度减 {format_points(delta)}")

        for field, weight in profile.items():
            value = fields.get(field)
            present = numeric(value) if field in NUMERIC_FIELDS else value
            if present is None or present == 0 or present == "":
                delta = 2.0 * weight
                score -= delta
                penalties.append(
                    f"应用「{app_name}」库中未见{field_label(field)}，匹配度减 {format_points(delta)}"
                )

        ranked.append({
            **{key: candidate[key] for key in ("part_number", "reference", "rpn", "status", "description")},
            "score": round(max(0.0, min(100.0, score)), 1),
            "facts": compact_facts(fields),
            "matches": matches,
            "risks": risks,
            "penalties": penalties,
        })

    ranked.sort(key=lambda item: (-item["score"], item["part_number"]))
    limit = max(1, min(int(request_data.get("limit", 3)), 20))
    diversified = pick_shortlist(ranked, limit)
    return {
        "mode": "requirements",
        "database": str(database),
        "database_version": version,
        "request": request_data,
        "candidate_count": len(candidates),
        "rejected_by_hard_constraints": rejected,
        "recommendations": diversified[:limit],
        "disclaimer": "数据库筛选结果；PinMux、并发外设、精确模拟性能、认证、价格和供货需用最新官方资料确认。",
    }


def similarity(field: str, candidate: Any, target: Any) -> tuple[float, str]:
    label = field_label(field)
    if candidate is None:
        return 0.0, f"{label}：ST 数据缺失"
    if field in NUMERIC_FIELDS:
        actual = numeric(candidate, allow_negative=field == "temperature_min_c")
        wanted = numeric(target, allow_negative=field == "temperature_min_c")
        if actual is None or wanted is None:
            return 0.0, f"{label}：无法比较"
        scale = max(abs(wanted), 1.0)
        closeness = max(0.0, 1.0 - abs(actual - wanted) / scale)
        return closeness, f"{label}：ST={actual:g}，竞品={wanted:g}"
    matched = text_matches(candidate, target if isinstance(target, list) else [target])
    return (1.0 if matched else 0.0), f"{label}：ST={candidate}，竞品={target}"


def compare(database: Path, competitor: dict[str, Any]) -> dict[str, Any]:
    specs = competitor.get("specs") or {}
    if not specs:
        raise ValueError("竞品 JSON 必须包含非空 specs 对象")
    essential = set(competitor.get("essential") or [])
    custom_weights = competitor.get("weights") or {}
    with connect_readonly(database) as db:
        candidates = load_candidates(db, bool(competitor.get("include_inactive")))
        version = dict(db.execute("SELECT * FROM version LIMIT 1").fetchone())
    ranked: list[dict[str, Any]] = []

    for candidate in candidates:
        fields = candidate["fields"]
        failures: list[str] = []
        comparisons: list[str] = []
        risks: list[str] = []
        penalties: list[str] = []
        weighted_score = 0.0
        total_weight = 0.0
        for field, target in specs.items():
            value = fields.get(field)
            weight = float(custom_weights.get(field, DEFAULT_WEIGHTS.get(field, 1.0)))
            closeness, detail = similarity(field, value, target)
            if field in essential:
                if value is None:
                    failures.append(f"{field_label(field)}：ST 数据缺失")
                elif field in NUMERIC_FIELDS and numeric(value, field == "temperature_min_c") is not None:
                    actual = numeric(value, field == "temperature_min_c")
                    wanted = numeric(target, field == "temperature_min_c")
                    if field in {"temperature_min_c", "voltage_min_v", "pin_count"}:
                        if actual is not None and wanted is not None and actual > wanted:
                            failures.append(detail)
                    elif actual is not None and wanted is not None and actual < wanted:
                        failures.append(detail)
                elif closeness == 0:
                    failures.append(detail)
            if value is None:
                risks.append(detail)
            else:
                comparisons.append(detail)
            weighted_score += closeness * weight
            total_weight += weight
        if failures:
            continue
        score = 100.0 * weighted_score / total_weight if total_weight else 0.0
        status_lower = candidate["status"].lower()
        if "active" not in status_lower:
            factor = 0.88 if "coming soon" in status_lower else 0.95
            score *= factor
            risks.append(f"生命周期状态需确认：{candidate['status']}")
            penalties.append(f"库内状态不是量产，相似度按 {int(factor * 100)}% 计")
        ranked.append({
            **{key: candidate[key] for key in ("part_number", "reference", "rpn", "status", "description")},
            "score": round(score, 1),
            "facts": compact_facts(fields),
            "comparisons": comparisons,
            "risks": risks,
            "penalties": penalties,
        })

    ranked.sort(key=lambda item: (-item["score"], item["part_number"]))
    limit = max(1, min(int(competitor.get("limit", 3)), 20))
    diversified = pick_shortlist(ranked, limit)
    return {
        "mode": "competitor",
        "database": str(database),
        "database_version": version,
        "competitor": competitor,
        "candidate_count": len(candidates),
        "recommendations": diversified[:limit],
        "disclaimer": "相似度只基于已提供且可比较的规格；必须继续核对官方数据手册、封装引脚、生命周期和供货。",
    }


def inspect_part(database: Path, part_number: str) -> dict[str, Any]:
    target = part_number.strip().upper()
    with connect_readonly(database) as db:
        cpn = db.execute("SELECT * FROM cpn WHERE UPPER(cpn)=?", (target,)).fetchone()
        rpn = None
        if cpn:
            rpn = db.execute(
                "SELECT r.* FROM rpn r JOIN rpn_has_cpn rc ON rc.rpn_id=r.id WHERE rc.cpn_id=? LIMIT 1",
                (cpn["id"],),
            ).fetchone()
        if not rpn:
            rpn = db.execute("SELECT * FROM rpn WHERE UPPER(rpn)=?", (target,)).fetchone()
        if not cpn and not rpn:
            suggestions = [row[0] for row in db.execute(
                "SELECT cpn FROM cpn WHERE UPPER(cpn) LIKE ? ORDER BY LENGTH(cpn),cpn LIMIT 20",
                (f"%{target}%",),
            )]
            return {"found": False, "part_number": target, "suggestions": suggestions}

        attributes: dict[str, dict[str, Any]] = {}
        if rpn:
            for row in db.execute(
                "SELECT a.name,a.sourceName,a.unit,a.type,v.strValue,v.numValue "
                "FROM rpn_has_attribute v JOIN attribute a ON a.id=v.attribute_id WHERE v.rpn_id=?",
                (rpn["id"],),
            ):
                attributes[row["name"]] = {
                    "value": parse_scalar(row["strValue"], row["numValue"]),
                    "label": row["sourceName"], "unit": row["unit"], "type": row["type"],
                    "source": "rpn",
                }
        if cpn:
            for row in db.execute(
                "SELECT a.name,a.sourceName,a.unit,a.type,v.strValue,v.numValue "
                "FROM cpn_has_attribute v JOIN attribute a ON a.id=v.attribute_id WHERE v.cpn_id=?",
                (cpn["id"],),
            ):
                attributes[row["name"]] = {
                    "value": parse_scalar(row["strValue"], row["numValue"]),
                    "label": row["sourceName"], "unit": row["unit"], "type": row["type"],
                    "source": "cpn",
                }
        raw = {key: value["value"] for key, value in attributes.items()}
        return {
            "found": True,
            "part_number": cpn["cpn"] if cpn else None,
            "reference": (cpn["refname"] if cpn else None) or (rpn["rpn"] if rpn else None),
            "rpn": dict(rpn) if rpn else None,
            "normalized": derive_fields(raw),
            "attributes": attributes,
        }


def load_json_argument(path: str | None, inline: str | None) -> dict[str, Any]:
    if inline:
        return json.loads(inline)
    if not path:
        raise ValueError("需要 --input-file 或 --input-json")
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Independent ST MCU recommendation engine")
    parser.add_argument("--db", help="cube-finder-db.db 路径；默认自动发现")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("locate", help="显示当前数据库路径与版本")
    inspect_parser = subparsers.add_parser("inspect", help="查询一个 ST 订货型号或系列型号")
    inspect_parser.add_argument("part_number")
    recommend_parser = subparsers.add_parser("recommend", help="根据结构化客户需求推荐")
    recommend_parser.add_argument("--input-file")
    recommend_parser.add_argument("--input-json")
    compare_parser = subparsers.add_parser("compare", help="根据已验证竞品规格匹配 ST 型号")
    compare_parser.add_argument("--input-file")
    compare_parser.add_argument("--input-json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        database = find_database(args.db)
        if args.command == "locate":
            with connect_readonly(database) as db:
                version = dict(db.execute("SELECT * FROM version LIMIT 1").fetchone())
                counts = {
                    "cpn": db.execute("SELECT COUNT(*) FROM cpn").fetchone()[0],
                    "rpn": db.execute("SELECT COUNT(*) FROM rpn").fetchone()[0],
                    "attributes": db.execute("SELECT COUNT(*) FROM attribute").fetchone()[0],
                }
            json_dump({"database": str(database), "version": version, "counts": counts})
        elif args.command == "inspect":
            json_dump(inspect_part(database, args.part_number))
        elif args.command == "recommend":
            json_dump(recommend(database, load_json_argument(args.input_file, args.input_json)))
        elif args.command == "compare":
            json_dump(compare(database, load_json_argument(args.input_file, args.input_json)))
        return 0
    except (FileNotFoundError, ValueError, OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
