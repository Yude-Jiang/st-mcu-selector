"""Fetch one official page for a competitor orderable. Never read a search snippet as a spec."""

from __future__ import annotations

import json
import os
import re
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

import competitor_parse

_UA = "st-mcu-selector/1.0"
_MAX_BYTES = 2_000_000
# An unauthenticated HTTP_PROXY answers 407 and hides a page that opens directly.
_OPENER = build_opener(ProxyHandler({}))
_BUDGET = 8
_HITS: list[float] = []
ALLOWED_HOSTS = frozenset({
    "www.gigadevice.com",
    "gigadevice.com",
    "www.geehy.com",
    "global.geehy.com",
    "geehy.com",
    "www.arterychip.com",
    "arterychip.com",
    "www.puyasemi.com",
    "puyasemi.com",
    "www.nationstech.com",
    "nationstech.com",
    "www.wch.cn",
    "wch.cn",
})
_SITES = (
    ("APM32", ("www.geehy.com", "global.geehy.com", "geehy.com")),
    ("AT32", ("www.arterychip.com", "arterychip.com")),
    ("PY32", ("www.puyasemi.com", "puyasemi.com")),
    ("N32", ("www.nationstech.com", "nationstech.com")),
    ("CH32", ("www.wch.cn", "wch.cn")),
)


def reset_budget() -> None:
    _HITS.clear()


def host_of(url: str) -> str:
    match = re.match(r"https://([^/?#]+)", str(url or ""), re.I)
    return match.group(1).lower() if match else ""


def host_allowed(url: str) -> bool:
    return host_of(url) in ALLOWED_HOSTS


def gigadevice_url(part: str) -> str | None:
    """Full GD32 orderables have a stable selector URL. Series names such as GD32H779 do not."""
    code = part.upper()
    if not re.fullmatch(r"GD32[A-Z0-9]+", code):
        return None
    if len(code) - 4 < 7:
        return None
    return "https://www.gigadevice.com/product/mcu/mcus-product-selector/" + code.lower()


def sites_for(part: str) -> tuple[str, ...]:
    code = part.upper()
    for prefix, hosts in _SITES:
        if code.startswith(prefix):
            return hosts
    return ()


def baidu_configured() -> bool:
    return bool(os.environ.get("BAIDU_QIANFAN_API_KEY") or os.environ.get("QIANFAN_API_KEY"))


def _allow() -> bool:
    now = time.monotonic()
    _HITS[:] = [stamp for stamp in _HITS if now - stamp < 60]
    if len(_HITS) >= _BUDGET:
        return False
    _HITS.append(now)
    return True


def fetch_html(url: str) -> tuple[str, str]:
    if not host_allowed(url):
        raise ValueError("host")
    request = Request(url, headers={"User-Agent": _UA})
    with _OPENER.open(request, timeout=8) as response:
        final = response.geturl()
        if not host_allowed(final):
            raise ValueError("redirect")
        data = response.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        raise ValueError("size")
    return final, data.decode("utf-8", "replace")


def search_urls(part: str, sites: tuple[str, ...]) -> list[str]:
    """Return official URLs only. Snippet and content fields are not specs."""
    key = os.environ.get("BAIDU_QIANFAN_API_KEY") or os.environ.get("QIANFAN_API_KEY") or ""
    if not key or not sites:
        return []
    payload = {
        "messages": [{"role": "user", "content": part[:72]}],
        "search_source": "baidu_search_v2",
        "resource_type_filter": [{"type": "web", "top_k": 5}],
        "search_filter": {"match": {"site": list(sites)[:20]}},
        "enable_rewrite": False,
    }
    request = Request(
        "https://qianfan.baidubce.com/v2/ai_search/web_search",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": _UA,
        },
        method="POST",
    )
    with _OPENER.open(request, timeout=8) as response:
        body = json.loads(response.read(200_000).decode("utf-8", "replace"))
    found: list[str] = []
    for item in body.get("references") or body.get("result") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        title = str(item.get("title") or "")
        if not host_allowed(url):
            continue
        if part.lower() not in url.lower() and part.lower() not in title.lower():
            continue
        found.append(url)
    return found


def _read(part: str, url: str) -> dict:
    try:
        final, html = fetch_html(url)
    except (URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError):
        return {"status": "fetch-failed", "url": "", "cells": {}}
    parsed = competitor_parse.parse_page(html, part)
    if parsed["status"] == "title-mismatch":
        return {"status": "title-mismatch", "url": "", "cells": {}}
    cells = parsed["cells"]
    for cell in cells.values():
        cell["url"] = final
    return {"status": "ok" if cells else "empty", "url": final, "cells": cells}


def lookup(part: str) -> dict:
    code = re.sub(r"[^A-Za-z0-9]", "", str(part or "")).upper()
    if not code:
        return {"status": "no-source", "url": "", "cells": {}}
    if code.startswith("GD32") and gigadevice_url(code) is None:
        return {"status": "series", "url": "", "cells": {}}
    if not _allow():
        return {"status": "rate-limited", "url": "", "cells": {}}
    direct = gigadevice_url(code)
    if direct:
        return _read(code, direct)
    sites = sites_for(code)
    if not sites:
        return {"status": "no-source", "url": "", "cells": {}}
    if not baidu_configured():
        return {"status": "search-unavailable", "url": "", "cells": {}}
    try:
        urls = search_urls(code, sites)
    except (URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError):
        return {"status": "not-found", "url": "", "cells": {}}
    if not urls:
        return {"status": "not-found", "url": "", "cells": {}}
    return _read(code, urls[0])
