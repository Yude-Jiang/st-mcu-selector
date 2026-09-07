from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "engine"))
os.chdir(ROOT)

import nl_datasheet  # noqa: E402
import nl_must  # noqa: E402
import nl_ocr  # noqa: E402

TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)
EXCERPT = (
    "NXP MK64FN1M0VLL12 120 MHz Flash 1024 KB RAM 256 KB LQFP100 FDCAN USB "
    "this excerpt is long enough for the datasheet parser minimum character check"
)
FAKE = {
    "manufacturer": "NXP",
    "part_number": "MK64FN1M0VLL12",
    "specs": {
        "frequency_mhz": 120,
        "flash_kb": 1024,
        "package_type": "LQFP",
        "price": 9,
        "stm32_pn": "STM32G474RET3",
    },
    "notes": ["摘录"],
}


class NlDatasheetTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("VITE_DEEPSEEK_API_KEY", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        os.environ.pop("ST_MCU_LLM_KEY", None)

    def test_pdf_extract_uses_excerpt_not_recall(self) -> None:
        os.environ["DEEPSEEK_API_KEY"] = "test"
        try:
            with patch.object(nl_datasheet, "extract_pdf_text", return_value=EXCERPT):
                with patch.object(nl_must, "complete_json", return_value=FAKE) as llm:
                    result = nl_datasheet.parse_bytes(b"%PDF-1.4 excerpt", "mk64.pdf", "application/pdf")
        finally:
            os.environ.pop("DEEPSEEK_API_KEY", None)
        llm.assert_called_once()
        self.assertEqual(result["part_number"], "MK64FN1M0VLL12")
        self.assertEqual(result["specs"]["frequency_mhz"], 120)
        self.assertNotIn("price", result["specs"])
        self.assertNotIn("stm32_pn", result["specs"])
        self.assertIn("mk64.pdf", result["source_note"])
        self.assertIn("未保存文件", result["source_note"])

    def test_image_extract_uses_ocr_then_same_json(self) -> None:
        os.environ["DEEPSEEK_API_KEY"] = "test"
        try:
            with patch.object(nl_ocr, "ocr_bytes", return_value=EXCERPT) as ocr:
                with patch.object(nl_must, "complete_json", return_value=FAKE):
                    result = nl_datasheet.parse_bytes(TINY_PNG, "shot.png", "image/png")
        finally:
            os.environ.pop("DEEPSEEK_API_KEY", None)
        ocr.assert_called_once()
        self.assertEqual(result["specs"]["flash_kb"], 1024)
        self.assertIn("shot.png", result["source_note"])

    def test_rejects_huge_file(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            nl_datasheet.parse_bytes(b"x" * (nl_datasheet.MAX_BYTES + 1), "big.pdf")
        self.assertIn("8 MB", str(ctx.exception))

    def test_rejects_empty_pdf_text(self) -> None:
        with patch.object(nl_datasheet, "extract_pdf_text", side_effect=ValueError(nl_datasheet.PDF_SCAN_ERROR)):
            with self.assertRaises(ValueError) as ctx:
                nl_datasheet.parse_bytes(b"%PDF-1.4 empty", "scan.pdf")
        self.assertIn("无法从 PDF 抽出文字", str(ctx.exception))

    def test_rejects_unreadable_image(self) -> None:
        with patch.object(nl_ocr, "ocr_bytes", return_value="模糊"):
            with self.assertRaises(ValueError) as ctx:
                nl_datasheet.parse_bytes(TINY_PNG, "blur.jpg", "image/jpeg")
        self.assertIn("无法从图片抽出文字", str(ctx.exception))

    def test_rejects_stm32_part_number(self) -> None:
        os.environ["DEEPSEEK_API_KEY"] = "test"
        fake = dict(FAKE, part_number="STM32G474RET3")
        try:
            with patch.object(nl_datasheet, "extract_pdf_text", return_value=EXCERPT):
                with patch.object(nl_must, "complete_json", return_value=fake):
                    with self.assertRaises(ValueError) as ctx:
                        nl_datasheet.parse_bytes(b"%PDF-1.4 excerpt", "st.pdf")
        finally:
            os.environ.pop("DEEPSEEK_API_KEY", None)
        self.assertIn("STM32", str(ctx.exception))

    def test_requires_deepseek(self) -> None:
        with patch.object(nl_datasheet, "extract_pdf_text", return_value=EXCERPT):
            with self.assertRaises(ValueError) as ctx:
                nl_datasheet.parse_bytes(b"%PDF-1.4 excerpt", "a.pdf")
        self.assertIn("DeepSeek", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
