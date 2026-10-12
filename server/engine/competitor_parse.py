"""Copy competitor hard specs only when a number sits next to its label.

Page text is data. A sentence in the HTML is not a spec, and a series-wide
"up to" is not one orderable. Callers pass the exact part they asked for.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

import package_norm

_HEDGE = re.compile(r"up\s*to|maximum|最多|至多|最大|高达", re.I)
_SIZE = re.compile(r"(\d+(?:\.\d+)?)\s*([KkMm])(?:[Bb](?:yte|ytes)?)?\b")
_MHZ = re.compile(r"(\d+(?:\.\d+)?)\s*mhz\b", re.I)
_BARE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*$")
_PKG = re.compile(
    r"\b(UFQFPN|VFQFPN|WFQFPN|VQFPN|UQFN|QFN|LQFP|TQFP|UFBGA|TFBGA|LFBGA|VFBGA|EWLCSP|WLCSP|TSSOP|BGA|SO)"
    r"\s*-?\s*(\d{2,3})?\b",
    re.I,
)
_I2C_VAL = re.compile(
    r"^(?:i2c\s*)?(\d+)\s*(?:路|个|通道|ch|channels?|x|×)?$",
    re.I,
)
_I2C_TAIL = re.compile(
    r"^(\d+)\s*(?:路|个|通道|ch|channels?|x|×)?\s*i2c$",
    re.I,
)
_TOKEN = re.compile(r"\b([A-Z]{2,8}\d[A-Z0-9]{4,})\b", re.I)
_LABELS = (
    ("frequency_mhz", ("max speed", "cpu frequency", "frequency", "主频", "最高主频")),
    ("flash_kb", ("flash",)),
    ("ram_kb", ("sram", "ram")),
    ("package", ("package", "封装")),
    ("i2c", ("i2c",)),
)


def has_hedge(value: str) -> bool:
    return bool(_HEDGE.search(str(value or "")))


def _whole(number: float) -> int | float:
    return int(number) if float(number).is_integer() else number


def label_key(label: str) -> str | None:
    text = re.sub(r"\(.*?\)", "", str(label or "")).strip().lower()
    text = text.replace("：", "").replace(":", "").strip()
    for key, names in _LABELS:
        if text in names:
            return key
    return None


def memory_kb(value: str, low: float, high: float) -> int | float | None:
    if has_hedge(value):
        return None
    hits = _SIZE.findall(str(value or ""))
    if len(hits) != 1:
        return None
    number, unit = hits[0]
    kb = float(number) * (1024 if unit.lower() == "m" else 1)
    if not (low <= kb <= high):
        return None
    return _whole(kb)


def frequency_mhz(value: str) -> int | float | None:
    text = str(value or "")
    hits = _MHZ.findall(text)
    if len(hits) == 1:
        number = float(hits[0])
    else:
        bare = _BARE.match(_HEDGE.sub(" ", text).strip())
        if not bare:
            return None
        number = float(bare.group(1))
    if not (1 <= number <= 1000):
        return None
    return _whole(number)


def package_cell(value: str) -> dict | None:
    if has_hedge(value):
        return None
    hits = list(_PKG.finditer(str(value or "")))
    if len(hits) != 1:
        return None
    family = package_norm.canonical_package(hits[0].group(1))
    if not family:
        return None
    pins = hits[0].group(2)
    pin_count = int(pins) if pins and 8 <= int(pins) <= 400 else None
    token = re.sub(r"\s+", "", hits[0].group(0)).upper()
    return {"value": token, "package_type": family, "pin_count": pin_count}


def i2c_count(value: str) -> int | None:
    if has_hedge(value):
        return None
    text = str(value or "").strip()
    match = _I2C_VAL.match(text) or _I2C_TAIL.match(text)
    if not match:
        return None
    count = int(match.group(1))
    if not (1 <= count <= 16):
        return None
    return count


def _parse_one(key: str, value: str):
    if key == "frequency_mhz":
        return frequency_mhz(value)
    if key == "flash_kb":
        return memory_kb(value, 2, 8192)
    if key == "ram_kb":
        return memory_kb(value, 1, 4096)
    if key == "package":
        return package_cell(value)
    if key == "i2c":
        return i2c_count(value)
    return None


def _identity(parsed) -> tuple:
    if isinstance(parsed, dict):
        return (parsed.get("package_type"), parsed.get("pin_count"), parsed.get("value"))
    return (parsed,)


def cells_from_pairs(pairs: list[tuple[str, str]]) -> dict:
    bucket: dict[str, list] = {}
    for label, value in pairs:
        key = label_key(label)
        parsed = _parse_one(key, value) if key else None
        if parsed is None:
            continue
        bucket.setdefault(key, []).append((parsed, " ".join(str(value).split())[:120]))
    cells = {}
    for key, items in bucket.items():
        if len({_identity(item[0]) for item in items}) != 1:
            continue
        parsed, raw = items[0]
        if isinstance(parsed, dict):
            cells[key] = {"value": parsed["value"], "raw": raw, "package_type": parsed["package_type"], "pin_count": parsed["pin_count"]}
        else:
            cells[key] = {"value": parsed, "raw": raw}
    return cells


def title_decision(title: str, wanted: str) -> str:
    """exact: this page is the orderable. other: it is a different orderable. generic: series or untitled."""
    wanted = wanted.upper()
    parts = [match.group(1).upper() for match in _TOKEN.finditer(title or "")]
    if wanted in parts or (title or "").strip().upper() == wanted:
        return "exact"
    foreign = [
        part for part in parts
        if not part.startswith("STM32") and not wanted.startswith(part) and part != wanted
    ]
    if foreign:
        return "other"
    return "generic"


_VOID = {"meta", "link", "img", "br", "hr", "input", "source", "base", "col", "wbr"}


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.capture = ""
        self.buf: list[str] = []
        self.title: list[str] = []
        self.pairs: list[tuple[str, str]] = []
        self.rows: list[list[str]] = []
        self._row: list[str] = []
        self._pending = ""
        self._stack: list[dict] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self.skip += 1
            return
        if self.skip:
            return
        if tag in {"title", "dt", "dd", "th", "td"}:
            self.capture = tag
            self.buf = []
        elif tag == "tr":
            self._row = []
        if tag not in _VOID:
            self._stack.append({"tag": tag, "parts": [], "divs": []})

    def handle_startendtag(self, tag: str, attrs) -> None:
        return

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self.skip:
            self.skip -= 1
            return
        if self.skip:
            return
        text = " ".join("".join(self.buf).split())
        if tag == "title" and self.capture == "title":
            self.title.append(text)
        elif tag == "dt" and self.capture == "dt":
            self._pending = text
        elif tag == "dd" and self.capture == "dd" and self._pending:
            self.pairs.append((self._pending, text))
            self._pending = ""
        elif tag in {"th", "td"} and self.capture == tag:
            self._row.append(text)
        elif tag == "tr" and self._row:
            self.rows.append(self._row)
            self._row = []
        if tag == self.capture:
            self.capture = ""
        self._close_div_pair(tag)

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        if self.capture:
            self.buf.append(data)
        if self._stack:
            self._stack[-1]["parts"].append(data)

    def _close_div_pair(self, tag: str) -> None:
        # GigaDevice prints each spec as two sibling divs, not a table or a dl.
        if not self._stack or self._stack[-1]["tag"] != tag:
            return
        node = self._stack.pop()
        text = " ".join("".join(node["parts"]).split())
        if tag == "div" and len(node["divs"]) == 2:
            left, right = node["divs"]
            if left and right and len(left) <= 60 and len(right) <= 80:
                self.pairs.append((left, right))
        if not self._stack:
            return
        if tag == "div":
            self._stack[-1]["divs"].append(text)
        if text:
            self._stack[-1]["parts"].append(text)


def _matching_row(rows: list[list[str]], part: str) -> list[str] | None:
    wanted = part.upper()
    found: list[str] | None = None
    for row in rows:
        if any(cell.upper() == wanted for cell in row):
            if found is not None:
                return None
            found = row
    return found


def _header_row(rows: list[list[str]], part: str) -> list[str] | None:
    wanted = part.upper()
    for row in rows:
        if len(row) >= 3 and all(cell.upper() != wanted for cell in row):
            return row
    return None


def cells_from_row(rows: list[list[str]], part: str) -> dict:
    row = _matching_row(rows, part)
    header = _header_row(rows, part) if row else None
    if not row or not header:
        return {}
    return cells_from_pairs(list(zip(header, row)))


def parse_page(html: str, part: str) -> dict:
    parser = _PageParser()
    parser.feed(html or "")
    parser.close()
    title = " ".join(parser.title)
    pairs = list(parser.pairs)
    for row in parser.rows:
        if len(row) == 2:
            pairs.append((row[0], row[1]))
    decision = title_decision(title, part)
    if decision == "other":
        return {"status": "title-mismatch", "cells": {}}
    if decision == "exact":
        cells = cells_from_pairs(pairs) or cells_from_row(parser.rows, part)
    else:
        # A series title must not donate its "up to" bullets. Only the orderable's own row.
        cells = cells_from_row(parser.rows, part)
    return {"status": "ok" if cells else "empty", "cells": cells}
