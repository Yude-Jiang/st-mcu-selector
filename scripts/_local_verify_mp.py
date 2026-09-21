from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

BASE = "http://127.0.0.1:8080"
ROOT = Path(__file__).resolve().parents[1]


def get(path: str) -> tuple[int, str]:
    with urlopen(BASE + path) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def main() -> None:
    for path in ["/", "/?mp=1", "/mp.js", "/gate.js", "/styles.css", "/i18n.js", "/healthz", "/api/health"]:
        status, body = get(path)
        print(f"{status} {path} ({len(body)} bytes)")
        if status != 200:
            raise SystemExit(f"unexpected status for {path}")

    query = parse_qs(urlparse(BASE + "/?mp=1").query)
    assert query.get("mp", [None])[0] == "1"

    _, html = get("/?mp=1")
    _, mp_js = get("/mp.js")
    _, gate_js = get("/gate.js")
    _, css = get("/styles.css")
    _, i18n = get("/i18n.js")

    assert 'src="./mp.js"' in html
    assert "window.ST_MCU_MP" in mp_js
    assert "if (window.ST_MCU_MP)" in gate_js
    assert "showMainApp()" in gate_js
    assert "html.is-mp #gate" in css
    assert "html.is-mp .langs" in css
    assert 'window.ST_MCU_MP ? "zh"' in i18n
    assert "if (!window.ST_MCU_MP) bindLangTabs()" in i18n

    cfg = (ROOT / "miniprogram" / "config.js").read_text(encoding="utf-8")
    wxml = (ROOT / "miniprogram" / "pages" / "index" / "index.wxml").read_text(encoding="utf-8")
    assert "http://127.0.0.1:8080" in cfg
    assert "/?mp=1" in cfg
    assert "<web-view" in wxml

    print("web-view target: http://127.0.0.1:8080/?mp=1")
    print("gate skip + zh-only path: OK")
    print("PASS")


if __name__ == "__main__":
    main()
