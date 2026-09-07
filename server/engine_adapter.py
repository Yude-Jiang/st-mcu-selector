from __future__ import annotations

import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

ENGINE_SCRIPTS = Path(__file__).resolve().parent / "engine"
if str(ENGINE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ENGINE_SCRIPTS))

import mcu_recommender as engine  # noqa: E402

ALLOWED_FIELDS = frozenset(engine.FIELD_ALIASES)


def database_path() -> Path:
    explicit = os.environ.get("ST_MCU_DB")
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"ST MCU database does not exist: {path}")
        return path
    data_dir = os.environ.get("ST_MCU_DATA_DIR")
    if data_dir:
        path = Path(data_dir).expanduser().resolve() / "cube-finder-db.db"
        if not path.is_file():
            raise FileNotFoundError(f"ST MCU database does not exist: {path}")
        return path
    return engine.find_database()


def _validate_field_names(groups: dict[str, dict[str, Any]]) -> None:
    unknown: set[str] = set()
    for values in groups.values():
        unknown.update(set(values) - ALLOWED_FIELDS)
    if unknown:
        supported = ", ".join(sorted(ALLOWED_FIELDS))
        raise ValueError(
            f"Unsupported normalized fields: {', '.join(sorted(unknown))}. "
            f"Supported fields: {supported}"
        )


def recommend(request_data: dict[str, Any]) -> dict[str, Any]:
    _validate_field_names({
        "must": request_data.get("must") or {},
        "prefer": request_data.get("prefer") or {},
    })
    result = engine.recommend(database_path(), request_data)
    result.pop("database", None)
    return result


def compare(competitor: dict[str, Any]) -> dict[str, Any]:
    specs = competitor.get("specs") or {}
    _validate_field_names({"specs": specs})
    essential = set(competitor.get("essential") or [])
    if not essential.issubset(specs):
        missing = ", ".join(sorted(essential - set(specs)))
        raise ValueError(f"Essential fields must also exist in specs: {missing}")
    weights = set((competitor.get("weights") or {}).keys())
    if not weights.issubset(specs):
        missing = ", ".join(sorted(weights - set(specs)))
        raise ValueError(f"Weighted fields must also exist in specs: {missing}")
    result = engine.compare(database_path(), competitor)
    result.pop("database", None)
    return result


def inspect_part(part_number: str, include_attributes: bool = False) -> dict[str, Any]:
    result = engine.inspect_part(database_path(), part_number)
    if not include_attributes:
        result.pop("attributes", None)
        rpn = result.get("rpn")
        if isinstance(rpn, dict):
            keep = {"rpn", "marketingStatus", "description", "path"}
            result["rpn"] = {key: value for key, value in rpn.items() if key in keep}
    return result


def suggest_parts(query: str, limit: int = 12) -> list[dict[str, str]]:
    needle = re.sub(r"[^A-Za-z0-9]", "", query).upper()
    if len(needle) < 2:
        return []
    cap = max(1, min(int(limit), 20))
    like = f"{needle}%"
    with engine.connect_readonly(database_path()) as connection:
        rpns = connection.execute(
            "SELECT rpn FROM rpn WHERE UPPER(rpn) LIKE ? ORDER BY LENGTH(rpn), rpn LIMIT ?",
            (like, cap),
        ).fetchall()
        cpns = connection.execute(
            "SELECT cpn FROM cpn WHERE UPPER(cpn) LIKE ? ORDER BY LENGTH(cpn), cpn LIMIT ?",
            (like, cap),
        ).fetchall()
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rpns:
        value = str(row[0] if not isinstance(row, sqlite3.Row) else row["rpn"])
        key = value.upper()
        if not value or key in seen:
            continue
        seen.add(key)
        items.append({"value": value, "kind": "系列型号"})
    for row in cpns:
        value = str(row[0] if not isinstance(row, sqlite3.Row) else row["cpn"])
        key = value.upper()
        if not value or key in seen:
            continue
        seen.add(key)
        items.append({"value": value, "kind": "订货号"})
        if len(items) >= cap:
            break
    return items[:cap]


def database_status() -> dict[str, Any]:
    path = database_path()
    with engine.connect_readonly(path) as connection:
        integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
        version_row = connection.execute("SELECT * FROM version LIMIT 1").fetchone()
        counts = {
            "cpn": connection.execute("SELECT COUNT(*) FROM cpn").fetchone()[0],
            "rpn": connection.execute("SELECT COUNT(*) FROM rpn").fetchone()[0],
            "attributes": connection.execute("SELECT COUNT(*) FROM attribute").fetchone()[0],
        }
    return {
        "ready": integrity == "ok",
        "database_name": path.name,
        "database_bytes": path.stat().st_size,
        "integrity": integrity,
        "version": dict(version_row) if version_row else None,
        "counts": counts,
    }


def validate_database(path: Path) -> None:
    uri = f"file:{path.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        result = connection.execute("PRAGMA quick_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError(f"SQLite quick_check failed: {result}")
        required = {"cpn", "rpn", "attribute", "version"}
        present = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        missing = required - present
        if missing:
            raise RuntimeError(f"Database is missing required tables: {sorted(missing)}")
    finally:
        connection.close()
