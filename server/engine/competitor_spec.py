"""Judge harvested competitor cells. Every rejection yields a blank, never a guess."""

from __future__ import annotations

import re
from typing import Any

import package_norm

# The six fields a vendor product page states next to a label. Peripheral counts
# beyond I2C, ADC channels and op-amps are not on these pages, so the shortlist
# engine still cannot be driven from a harvest alone — the card asks the user.
FIELDS = ("core", "frequency_mhz", "flash_kb", "sram_kb", "package", "pin_count", "i2c")

# A unit misread would otherwise enter the catalogue as a plausible number.
# Out-of-band turns it into a blank, which the card then asks about.
BANDS = {
    "frequency_mhz": (1, 1000),
    "flash_kb": (2, 8192),
    "sram_kb": (1, 4096),
    "pin_count": (8, 400),
    "i2c": (1, 16),
}

# "up to" is how a maximum clock is written, so frequency keeps it. For a memory
# size or an interface count on a single-part page it means we are on a series
# page instead, where the number belongs to the family's largest member.
_HEDGE_RE = re.compile(r"\b(?:up\s+to|max(?:imum)?)\b|最多|至多|最大", re.I)
# Vendors render the same core as "Cortex-M0+", "Cortex M0+" or "ARM(R) Cortex(R)-M7",
# so the separator is optional everywhere and the marks are stripped first.
_CORE_RE = re.compile(
    r"(?:ARM\s*)?(Cortex[\s-]?M\s?\d+\+?|RISC[\s-]?V|Xtensa\s*LX\d+|8051)", re.I
)
_MARKS_RE = re.compile(r"[\u00ae\u2122\u00a9]")
_CORE_FORMS = (
    (re.compile(r"cortex-?m(\d+\+?)", re.I), "Cortex-M{0}"),
    (re.compile(r"risc-?v", re.I), "RISC-V"),
    (re.compile(r"xtensa\s*lx(\d+)", re.I), "Xtensa LX{0}"),
    (re.compile(r"8051", re.I), "8051"),
)
# A size must carry its own K/M. The column header may say Bytes while the cell
# says 3840K; a bare 3840 could be either and is rejected rather than guessed.
_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([KMkm])(?:B|Bytes?)?(?![A-Za-z0-9])")
_FREQ_RE = re.compile(r"(\d+(?:\.\d+)?)\s*M?Hz|(\d+(?:\.\d+)?)\s*M(?![A-Za-z0-9])", re.I)
_COUNT_RE = re.compile(r"(?<![A-Za-z0-9.])(\d{1,2})(?![A-Za-z0-9.])")
# Digits must hang off the package token itself, so a GPIO count elsewhere in
# the cell cannot become a pin count.
_PKG_PINS_RE = re.compile(
    r"\b(" + "|".join(name for name, _ in package_norm._ALIASES) + r")\s*-?\s*(\d{2,3})\b",
    re.I,
)


def normalize_pn(value: Any) -> str:
    """Ordering codes are compared without punctuation or case."""
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def title_matches(title: Any, part_number: Any) -> bool:
    """The page title must name this exact part, or we fetched the wrong page.

    A product selector that renders client-side returns a shell whose title is
    generic. Failing here is what keeps an empty SPA from looking like a part
    with no specs.
    """
    wanted = normalize_pn(part_number)
    if not wanted:
        return False
    return wanted in {normalize_pn(piece) for piece in re.split(r"[|\-–—:：]", str(title or ""))}


def hedged(raw: Any) -> bool:
    return bool(_HEDGE_RE.search(str(raw or "")))


def in_band(field: str, value: Any) -> bool:
    bounds = BANDS.get(field)
    if bounds is None or value is None:
        return value is not None
    return bounds[0] <= value <= bounds[1]


def read_core(raw: Any) -> str:
    """Canonical core name. Vendor pages carry (R) and (TM) inside the core string."""
    hit = _CORE_RE.search(_MARKS_RE.sub("", str(raw or "")))
    if not hit:
        return ""
    token = re.sub(r"\s+", "", hit.group(1))
    for pattern, template in _CORE_FORMS:
        form = pattern.fullmatch(token)
        if form:
            return template.format(*form.groups())
    return token


def read_frequency_mhz(raw: Any) -> int | None:
    text = str(raw or "")
    hit = _FREQ_RE.search(text)
    if not hit:
        return None
    number = float(hit.group(1) or hit.group(2))
    if "khz" in text.lower():
        number = number / 1000
    value = int(round(number))
    return value if in_band("frequency_mhz", value) else None


def read_size_kb(raw: Any, field: str) -> int | None:
    """KB from a value that carries its own K or M. A bare number is rejected."""
    if hedged(raw):
        return None
    hit = _SIZE_RE.search(str(raw or ""))
    if not hit:
        return None
    number = float(hit.group(1))
    if hit.group(2).upper() == "M":
        number *= 1024
    value = int(round(number))
    return value if in_band(field, value) else None


def read_package(raw: Any) -> tuple[str, int | None]:
    """Family plus the pin count encoded in the package token, never elsewhere."""
    family = package_norm.canonical_package(raw)
    if not family:
        return "", None
    hit = _PKG_PINS_RE.search(str(raw or ""))
    pins = int(hit.group(2)) if hit else None
    if pins is not None and not in_band("pin_count", pins):
        pins = None
    return family, pins


def read_interface_count(raw: Any) -> int | None:
    """Count of an interface, or None when the cell only names it.

    A spec table that prints a bare "I2C" says the peripheral exists and not how
    many there are. nl_must reads a bare mention as 1 because a user asking for
    I2C wants at least one; harvesting the same way would write invented counts.
    """
    text = str(raw or "")
    if hedged(text):
        return None
    hit = _COUNT_RE.search(text)
    if not hit:
        return None
    value = int(hit.group(1))
    return value if in_band("i2c", value) else None


def cell(value: Any, raw: Any) -> dict[str, Any] | None:
    """A kept value carries the source text, so a disputed number stays auditable."""
    if value is None or value == "":
        return None
    return {"value": value, "raw": " ".join(str(raw or "").split())[:120]}


def build_row(part_number: str, pairs: dict[str, str], url: str, fetched_at: str) -> dict[str, Any]:
    """Map label/value pairs onto cells. A field no rule accepts is simply absent."""
    cells: dict[str, Any] = {}
    readers = (
        ("core", ("core", "内核", "cpu"), lambda raw: read_core(raw)),
        ("frequency_mhz", ("speed", "frequency", "主频", "最高速度"), read_frequency_mhz),
        ("flash_kb", ("flash",), lambda raw: read_size_kb(raw, "flash_kb")),
        ("sram_kb", ("sram", "ram"), lambda raw: read_size_kb(raw, "sram_kb")),
        ("i2c", ("i2c", "i²c"), read_interface_count),
    )
    for field, labels, reader in readers:
        raw = first_label(pairs, labels)
        if raw is None:
            continue
        kept = cell(reader(raw), raw)
        if kept is not None:
            cells[field] = kept

    raw_package = first_label(pairs, ("package", "封装"))
    if raw_package is not None:
        family, pins = read_package(raw_package)
        for field, value in (("package", family), ("pin_count", pins)):
            kept = cell(value, raw_package)
            if kept is not None:
                cells[field] = kept

    return {
        "part_number": str(part_number).upper(),
        "url": url,
        "fetched_at": fetched_at,
        "status": "ok" if cells else "empty",
        "cells": cells,
    }


def first_label(pairs: dict[str, str], labels: tuple[str, ...]) -> str | None:
    """Longest label wins, so "SRAM" is not served by a looser "RAM" entry."""
    lowered = {str(key).strip().lower(): value for key, value in pairs.items()}
    for label in labels:
        for key in sorted(lowered, key=len, reverse=True):
            if key == label or key.startswith(label + " ") or label in key.split():
                return lowered[key]
    return None
