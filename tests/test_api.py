from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
os.chdir(ROOT)

from fastapi.testclient import TestClient  # noqa: E402

import readiness  # noqa: E402
from app import app  # noqa: E402


class SelectionApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_home_page_has_forms(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("id=\"root\"", response.text)
        self.assertIn("./facts.js", response.text)
        facts = Path(ROOT / "web" / "facts.js").read_text(encoding="utf-8")
        self.assertIn("即将供货", facts)
        self.assertIn("st.com/content/st_com/en/search.html", facts)
        self.assertIn("/api/recommend", Path(ROOT / "web" / "app.js").read_text(encoding="utf-8"))

    def test_recommend_rejects_before_database_ready(self) -> None:
        readiness.mark_error(RuntimeError("器件库尚未就绪。"))
        response = self.client.post("/api/recommend", json={"must": {"flash_kb": {"min": 512}}})
        self.assertEqual(response.status_code, 503)

    def test_recommend_returns_shortlist(self) -> None:
        readiness.mark_ready()
        fake = {
            "mode": "requirements",
            "recommendations": [{"part_number": "STM32G474RET3", "score": 91, "facts": {}, "matches": [], "risks": []}],
            "disclaimer": "check datasheet",
        }
        with patch("routes.selection.engine_adapter.recommend", return_value=fake):
            response = self.client.post("/api/recommend", json={"must": {"flash_kb": {"min": 512}}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recommendations"][0]["part_number"], "STM32G474RET3")

    def test_inspect_not_found_is_structured(self) -> None:
        readiness.mark_ready()
        fake = {"found": False, "part_number": "ZZZ", "suggestions": ["STM32G474RET3"]}
        with patch("routes.selection.engine_adapter.inspect_part", return_value=fake):
            response = self.client.get("/api/inspect", params={"part_number": "ZZZPART"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["found"])

    def test_cors_allows_wechat_origin(self) -> None:
        response = self.client.get(
            "/api/health",
            headers={"Origin": "https://servicewechat.com"},
        )
        self.assertIn(response.status_code, (200, 503))
        self.assertEqual(response.headers.get("access-control-allow-origin"), "*")

    def test_cors_preflight_recommend(self) -> None:
        response = self.client.options(
            "/api/recommend",
            headers={
                "Origin": "https://servicewechat.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertIn(response.status_code, (200, 204))
        self.assertTrue(response.headers.get("access-control-allow-origin"))

    def test_miniprogram_calls_same_skill_paths(self) -> None:
        text = Path(ROOT / "miniprogram" / "utils" / "api.js").read_text(encoding="utf-8")
        self.assertIn("/api/recommend", text)
        self.assertIn("/api/compare", text)
        self.assertIn("/api/inspect", text)
        self.assertIn("/api/health", text)


if __name__ == "__main__":
    unittest.main()
