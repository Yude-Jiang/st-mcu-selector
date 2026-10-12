#!/usr/bin/env python3
"""Harvest GigaDevice ordering codes from their product selector, one page per code.

The page title must name the exact code, numbers must sit next to their label,
and anything else leaves the cell blank. Specs differ between siblings of one
series (GD32H759IIT6 is 2048K Flash, GD32H759IIK6 is BGA176), so nothing is ever
inherited from a series and series names are never assembled into a code.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "server" / "engine"))

import competitor_spec  # noqa: E402

VENDOR = "GigaDevice"
BASE = "https://www.gigadevice.com/product/mcu/mcus-product-selector/"
ALLOWED_HOSTS = frozenset({"www.gigadevice.com", "gigadevice.com"})
USER_AGENT = "st-mcu-selector/1.0 (internal part lookup; contact ST FAE)"
DELAY_SECONDS = 2.0
TIMEOUT_SECONDS = 20
# A complete GigaDevice code carries package and temperature suffixes after the
# series. GD32H779 is a series name and 404s, so it is rejected before a request.
MIN_SUFFIX_CHARS = 7


class PairParser(HTMLParser):
    """Collect label/value pairs from table rows and definition lists.

    A label whose value differs between occurrences is dropped: that is what a
    multi-part listing page looks like, and there is no way to tell which row
    belongs to the code we asked for.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._row: list[str] = []
        self._cell: list[str] | None = None
        self._pending_label = ""
        self._seen: dict[str, set[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
        elif tag == "tr":
            self._row = []
        elif tag in {"td", "th", "dt", "dd"}:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag in {"td", "th"} and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr":
            if len(self._row) >= 2:
                self._record(self._row[0], self._row[1])
            self._row = []
        elif tag == "dt" and self._cell is not None:
            self._pending_label = " ".join("".join(self._cell).split())
            self._cell = None
        elif tag == "dd" and self._cell is not None:
            self._record(self._pending_label, " ".join("".join(self._cell).split()))
            self._cell = None
            self._pending_label = ""

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif self._cell is not None:
            self._cell.append(data)

    def _record(self, label: str, value: str) -> None:
        label = label.strip().rstrip(":：").strip()
        if label and value:
            self._seen.setdefault(label.lower(), set()).add(value)

    @property
    def pairs(self) -> dict[str, str]:
        return {label: next(iter(values)) for label, values in self._seen.items() if len(values) == 1}

    @property
    def dropped(self) -> list[str]:
        return sorted(label for label, values in self._seen.items() if len(values) > 1)


def part_url(part_number: str) -> str:
    return BASE + part_number.strip().lower()


def looks_complete(part_number: str) -> bool:
    code = competitor_spec.normalize_pn(part_number)
    return code.startswith("GD32") and len(code) - 4 >= MIN_SUFFIX_CHARS


def fetch(url: str) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            final = urllib.parse.urlsplit(response.geturl()).hostname or ""
            # Re-check the host after redirects, not only on the candidate URL.
            if final.lower() not in ALLOWED_HOSTS:
                return 0, ""
            charset = response.headers.get_content_charset() or "utf-8"
            return response.status, response.read().decode(charset, "replace")
    except urllib.error.HTTPError as error:
        return error.code, ""
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, ""


def harvest_html(part_number: str, html: str, url: str) -> dict[str, object]:
    parser = PairParser()
    parser.feed(html)
    if not competitor_spec.title_matches(parser.title, part_number):
        return blank(part_number, url, "title-mismatch", title=parser.title.strip()[:120])
    row = competitor_spec.build_row(part_number, parser.pairs, url, stamp())
    row["vendor"] = VENDOR
    if parser.dropped:
        row["ambiguous_labels"] = parser.dropped
    return row


def blank(part_number: str, url: str, status: str, **extra: object) -> dict[str, object]:
    """A failed page is still recorded, so a blank cell is distinguishable from an untried one."""
    return {
        "vendor": VENDOR,
        "part_number": part_number.upper(),
        "url": url,
        "fetched_at": stamp(),
        "status": status,
        "cells": {},
        **extra,
    }


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_codes(path: pathlib.Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.split("#")[0].strip() for line in lines if line.split("#")[0].strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codes", type=pathlib.Path, help="file of full ordering codes, one per line")
    parser.add_argument("--code", action="append", default=[], help="a single ordering code")
    parser.add_argument("--out", type=pathlib.Path, default=catalogue_path())
    parser.add_argument("--fixture", type=pathlib.Path, help="read saved HTML instead of fetching")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, touch nothing")
    args = parser.parse_args(argv)

    codes = list(args.code) + (read_codes(args.codes) if args.codes else [])
    if not codes:
        parser.error("give --code or --codes")

    stubs = [code for code in codes if not looks_complete(code)]
    for code in stubs:
        print(f"skip {code}: not a complete ordering code", file=sys.stderr)
    codes = [code for code in codes if looks_complete(code)]

    if args.dry_run:
        print(f"would write {len(codes)} row(s) to {args.out}")
        for code in codes:
            print(f"  GET {part_url(code)}")
        return 0

    rows = []
    for index, code in enumerate(codes):
        url = part_url(code)
        if args.fixture:
            status, html = 200, args.fixture.read_text(encoding="utf-8")
        else:
            if index:
                time.sleep(DELAY_SECONDS)
            status, html = fetch(url)
        if status != 200 or not html:
            rows.append(blank(code, url, f"http-{status or 'unreachable'}"))
        else:
            rows.append(harvest_html(code, html, url))
        print(f"{rows[-1]['status']:>16}  {code}  {len(rows[-1]['cells'])} cell(s)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} row(s) to {args.out}")
    return 0


def catalogue_path() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2] / "data" / "competitor" / "gigadevice.jsonl"


if __name__ == "__main__":
    raise SystemExit(main())
