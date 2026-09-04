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


if __name__ == "__main__":
    unittest.main()
