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
        self.assertIn("./parse.js", response.text)
        self.assertIn("./turn.js", response.text)
        self.assertIn("id=\"brief\"", response.text)
        self.assertIn("id=\"followup\"", response.text)
        self.assertNotIn("followup-chips", response.text)
        self.assertNotIn("为什么是这三颗", response.text)
        self.assertNotIn("继续问", response.text)
        self.assertIn("showBrief", Path(ROOT / "web" / "turn.js").read_text(encoding="utf-8"))
        self.assertIn("name=\"motor_timers\"", response.text)
        self.assertIn("name=\"hrtim\"", response.text)
        self.assertIn("name=\"usb\"", response.text)
        facts = Path(ROOT / "web" / "facts.js").read_text(encoding="utf-8")
        self.assertIn("即将供货", facts)
        self.assertIn("st.com/en/microcontrollers-microprocessors", facts)
        self.assertIn("matchLines", facts)
        self.assertIn("SHORTLIST_KEYS", facts)
        self.assertIn("class=\"title-bar\"", response.text)
        self.assertIn(">推荐<", response.text)
        self.assertNotIn("填入下方表单", response.text)
        self.assertNotIn("给出短名单", response.text)
        self.assertNotIn("tab-competitor", response.text)
        self.assertIn("ST 产品页", Path(ROOT / "web" / "app.js").read_text(encoding="utf-8"))
        self.assertIn("最多给出三个订货号。这是短名单，不是设计签核。", response.text)
        self.assertIn("数据库匹配只给候选；最多给出三个订货号", response.text)
        self.assertIn("helon.chen@st.com", response.text)
        self.assertIn("yude.jiang@st.com", response.text)
        self.assertIn("footer-date", response.text)
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

    def test_parse_requirements_does_not_need_database(self) -> None:
        os.environ.pop("VITE_DEEPSEEK_API_KEY", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        os.environ.pop("ST_MCU_LLM_KEY", None)
        response = self.client.post(
            "/api/parse-requirements",
            json={"text": "电机控制，主频至少 170 MHz，LQFP64，要 FDCAN"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["application"], "motor_control")
        self.assertEqual(payload["must"]["frequency_mhz"], {"min": 170})
        self.assertNotIn("recommendations", payload)

    def test_turn_explains_without_new_shortlist(self) -> None:
        os.environ.pop("VITE_DEEPSEEK_API_KEY", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        os.environ.pop("ST_MCU_LLM_KEY", None)
        response = self.client.post(
            "/api/turn",
            json={
                "text": "为什么是这三颗？",
                "must": {"flash_kb": {"min": 512}},
                "candidates": [{
                    "part_number": "STM32G474RET3",
                    "score": 91,
                    "facts": {"frequency_mhz": 170, "flash_kb": 512},
                }],
                "history": [],
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "explain")
        self.assertIn("STM32G474RET3", payload["answer"])
        self.assertNotIn("recommendations", payload)

    def test_turn_refine_reruns_recommend(self) -> None:
        os.environ.pop("VITE_DEEPSEEK_API_KEY", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        os.environ.pop("ST_MCU_LLM_KEY", None)
        readiness.mark_ready()
        fake = {
            "mode": "requirements",
            "recommendations": [{"part_number": "STM32G474RET3", "score": 91, "facts": {}, "matches": [], "risks": []}],
            "disclaimer": "check datasheet",
        }
        with patch("routes.parse.engine_adapter.recommend", return_value=fake):
            response = self.client.post(
                "/api/turn",
                json={
                    "text": "再加 USB",
                    "must": {"flash_kb": {"min": 512}},
                    "candidates": [{"part_number": "STM32G431RBT6", "facts": {}}],
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "refine_must")
        self.assertEqual(payload["must"]["usb"], {"min": 1})
        self.assertEqual(payload["recommendations"][0]["part_number"], "STM32G474RET3")
        self.assertIn("STM32G474RET3", payload.get("answer") or "")

    def test_turn_compare_uses_competitor_sentence(self) -> None:
        os.environ.pop("VITE_DEEPSEEK_API_KEY", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        os.environ.pop("ST_MCU_LLM_KEY", None)
        readiness.mark_ready()
        fake = {
            "mode": "competitor",
            "recommendations": [{"part_number": "STM32F429ZIT6", "score": 88, "facts": {}, "comparisons": ["主频：ST=180"]}],
        }
        with patch("routes.parse.engine_adapter.compare", return_value=fake) as mocked:
            response = self.client.post(
                "/api/turn",
                json={
                    "text": "对照 NXP MK64FN1M0VLL12，主频 120 MHz，Flash 1MB，LQFP100，来源 datasheet Rev 3",
                    "candidates": [],
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["intent"], "compare")
        self.assertEqual(payload["recommendations"][0]["part_number"], "STM32F429ZIT6")
        self.assertIn("STM32F429ZIT6", payload.get("answer") or "")
        self.assertIn("MK64FN1M0VLL12", payload.get("answer") or "")
        mocked.assert_called_once()
        body = mocked.call_args[0][0]
        self.assertEqual(body["manufacturer"], "NXP")
        self.assertEqual(body["part_number"], "MK64FN1M0VLL12")
        self.assertEqual(body["specs"]["frequency_mhz"], 120)
        self.assertEqual(body["specs"]["flash_kb"], 1024)

    def test_inspect_not_found_is_structured(self) -> None:
        readiness.mark_ready()
        fake = {"found": False, "part_number": "ZZZ", "suggestions": ["STM32G474RET3"]}
        with patch("routes.selection.engine_adapter.inspect_part", return_value=fake):
            response = self.client.get("/api/inspect", params={"part_number": "ZZZPART"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["found"])

    def test_health_reports_llm_without_exposing_key(self) -> None:
        os.environ.pop("VITE_DEEPSEEK_API_KEY", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        os.environ.pop("ST_MCU_LLM_KEY", None)
        readiness.mark_ready()
        with patch("routes.health.engine_adapter.database_status", return_value={"counts": {"cpn": 1}}):
            response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["llm"]["configured"])
        self.assertEqual(payload["llm"]["model"], "deepseek-chat")
        dumped = str(payload).lower()
        self.assertNotIn("api_key", dumped)
        self.assertNotIn("sk-", dumped)

    def test_health_llm_configured_reads_vite_secret_name(self) -> None:
        os.environ["VITE_DEEPSEEK_API_KEY"] = "test"
        readiness.mark_ready()
        try:
            with patch("routes.health.engine_adapter.database_status", return_value={"counts": {"cpn": 1}}):
                response = self.client.get("/api/health")
        finally:
            os.environ.pop("VITE_DEEPSEEK_API_KEY", None)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["llm"]["configured"])

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
        self.assertIn("/api/parse-requirements", text)

    def test_miniprogram_production_uses_aliyun_legal_host(self) -> None:
        text = Path(ROOT / "miniprogram" / "config.js").read_text(encoding="utf-8")
        self.assertIn("https://mp.microelectronics.com", text)
        self.assertIn("mp.microelectronics.com", text)
        self.assertNotIn("REPLACE-WITH-ICP-DOMAIN", text)


if __name__ == "__main__":
    unittest.main()
