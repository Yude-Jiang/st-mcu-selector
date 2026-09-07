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

TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)
PARSED = {
    "specs": {"frequency_mhz": 120, "flash_kb": 1024, "package_type": "LQFP"},
    "part_number": "MK64FN1M0VLL12",
    "manufacturer": "NXP",
    "notes": [],
    "source_note": "规格来自用户上传的 datasheet 摘录（mk64.pdf，未保存文件）。",
}


class ParseDatasheetApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        os.environ.pop("VITE_DEEPSEEK_API_KEY", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        os.environ.pop("ST_MCU_LLM_KEY", None)

    def test_missing_file_is_400(self) -> None:
        response = self.client.post("/api/parse-datasheet", data={"keep": "multipart"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("上传", response.json()["detail"])

    def test_bad_pdf_is_400(self) -> None:
        readiness.mark_error(RuntimeError("器件库尚未就绪。"))
        response = self.client.post(
            "/api/parse-datasheet",
            files={"file": ("note.pdf", b"not-a-pdf", "application/pdf")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("PDF", response.json()["detail"])

    def test_parse_pdf_does_not_need_database(self) -> None:
        readiness.mark_error(RuntimeError("器件库尚未就绪。"))
        with patch("routes.parse.nl_datasheet.parse_bytes", return_value=PARSED):
            response = self.client.post(
                "/api/parse-datasheet",
                files={"file": ("mk64.pdf", b"%PDF-1.4 excerpt", "application/pdf")},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["part_number"], "MK64FN1M0VLL12")

    def test_parse_image_uses_same_payload(self) -> None:
        parsed = dict(PARSED, source_note="规格来自用户上传的 datasheet 摘录（shot.png，未保存文件）。")
        with patch("routes.parse.nl_datasheet.parse_bytes", return_value=parsed) as mocked:
            response = self.client.post(
                "/api/parse-datasheet",
                files={"file": ("shot.png", TINY_PNG, "image/png")},
            )
        self.assertEqual(response.status_code, 200)
        mocked.assert_called_once()
        self.assertIn("shot.png", response.json()["source_note"])

    def test_turn_datasheet_skips_the_model(self) -> None:
        readiness.mark_ready()
        fake = {
            "mode": "competitor",
            "recommendations": [{"part_number": "STM32F429ZIT6", "score": 88, "facts": {}}],
            "disclaimer": "check datasheet",
        }
        with patch("routes.parse.engine_adapter.compare", return_value=fake) as mocked:
            with patch("routes.parse.nl_turn.nl_must.complete_json") as complete:
                response = self.client.post(
                    "/api/turn",
                    json={
                        "text": "对照这颗",
                        "datasheet": {
                            "specs": {"frequency_mhz": 120, "flash_kb": 512, "package_type": "LQFP"},
                            "part_number": "GD32H779",
                            "manufacturer": "GigaDevice",
                            "source_note": "规格来自用户上传的 datasheet 摘录（x.pdf，未保存文件）。",
                        },
                    },
                )
        self.assertEqual(response.status_code, 200)
        complete.assert_not_called()
        payload = response.json()
        self.assertEqual(payload["intent"], "compare")
        self.assertEqual(payload["source"], "rules")
        body = mocked.call_args[0][0]
        self.assertEqual(body["part_number"], "GD32H779")
        self.assertEqual(body["specs"]["frequency_mhz"], 120)


if __name__ == "__main__":
    unittest.main()
